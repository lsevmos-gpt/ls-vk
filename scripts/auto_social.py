"""Publish only explicitly approved, public VK Stories or Buffer Instagram Stories.

Use before-due durable reservations and NO retries after uncertain provider calls.
Buffer uses provider-native dueAt; VK Stories wait in an already-running worker.
GitHub scheduled workflow start times are NOT guaranteed. If too late, skip.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{7,127}$')
PUBLIC_SOURCE = {'lsevmos-gpt/ls-vk'}
DISALLOWED_HOSTS = {'github.com', 'api.github.com', 'drive.google.com', 'docs.google.com',
                    'private-user-images.githubusercontent.com', 'localhost'}
RESTRICTED_KEYS = {'password', 'token', 'secret', 'authorization', 'apikey', 'api_key', 'key'}
VK_MAX_ARM_SECONDS = 50 * 60
VK_LATE_TOLERANCE_SECONDS = 5
MAX_BUFFER_FUTURE_DAYS = 90


def at_utc(value: object) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)', value):
        raise ValueError('publishAt and dueAt must be exact ISO-8601 seconds with timezone')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('Invalid ISO-8601 time') from exc
    if dt.tzinfo is None:
        raise ValueError('Timezone offset required')
    return dt.astimezone(timezone.utc)


def public_url(url: object) -> bool:
    if not isinstance(url, str) or not url.startswith('https://') or len(url) > 2048:
        return False
    try:
        p = urlsplit(url)
        host = (p.hostname or '').lower()
    except ValueError:
        return False
    if not host or host in DISALLOWED_HOSTS or host.endswith('.internal') or host.endswith('.localhost'):
        return False
    if p.username or p.password or p.port not in (None, 443) or p.fragment or re.search(r'(?i)(access_token|api_key|apikey|token|secret|signature|sig)=', p.query):
        return False
    if host == 'raw.githubusercontent.com':
        return p.path.startswith('/lsevmos-gpt/ls-vk/main/media/') and '..' not in p.path
    if host.endswith('.githubusercontent.com'):
        return False
    return True


def safe_repo_media(value: object, root: Path) -> bool:
    if not isinstance(value, str) or not value.startswith('media/'):
        return False
    p = Path(value)
    if p.is_absolute() or '..' in p.parts or '\\' in value or p.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.mp4', '.webm'}:
        return False
    full = root / p
    if not full.is_file() or full.is_symlink() or full.stat().st_size == 0:
        return False
    with full.open('rb') as f:
        data=f.read(16)
    ext=p.suffix.lower()
    if ext == '.png':
        return data.startswith(b'\x89PNG\r\n\x1a\n')
    if ext in ('.jpg','.jpeg'):
        return data.startswith(b'\xff\xd8\xff')
    if ext == '.mp4':
        return data[4:8] == b'ftyp'
    if ext == '.webm':
        return data.startswith(b'\x1a\x45\xdf\xa3')
    return False


def no_sensitive_keys(payload: object) -> bool:
    if isinstance(payload, dict):
        return all(k.lower() not in RESTRICTED_KEYS and no_sensitive_keys(v) for k,v in payload.items())
    if isinstance(payload, list):
        return all(no_sensitive_keys(x) for x in payload)
    return True


def validate(platform: str, path: Path, root: Path, now: datetime | None = None) -> tuple[dict, datetime]:
    now = now or datetime.now(timezone.utc)
    if platform not in {'vk', 'buffer'}:
        raise ValueError('Unsupported platform')
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 128000:
        raise ValueError('Invalid manifest file')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(manifest, dict):
        raise ValueError('Expected object')
    job_id = manifest.get('id')
    if not isinstance(job_id, str) or not ID.fullmatch(job_id) or job_id != path.stem:
        raise ValueError('id must match filename and contain 8–128 safe characters')
    if manifest.get('approved') is not True or manifest.get('publicContent') is not True:
        raise ValueError('Explicit approved=true and publicContent=true required')
    if not no_sensitive_keys(manifest):
        raise ValueError('Sensitive key detected in a PUBLIC repository manifest')
    due = at_utc(manifest.get('publishAt'))
    if due <= now:
        raise ValueError('Time in the past; never publish late')
    if due > now + timedelta(days=MAX_BUFFER_FUTURE_DAYS):
        raise ValueError('Time is more than 90 days ahead')
    if platform == 'vk':
        if manifest.get('type') not in {'story', 'story-batch'}:
            raise ValueError('Only VK Stories are permitted in automatic scheduler')
        stories = ([manifest] if manifest['type'] == 'story' else manifest.get('stories'))
        if not isinstance(stories, list) or not (1 <= len(stories) <= 10):
            raise ValueError('Expected 1–10 VK Stories')
        for item in stories:
            if not isinstance(item, dict) or item.get('storyType') not in {'photo','video'}:
                raise ValueError('Explicit VK Story photo/video type required')
            if not (public_url(item.get('mediaUrl')) or safe_repo_media(item.get('media'), root)):
                raise ValueError('VK Story must use publicly accessible HTTPS media or committed public media/')
            suffix = item.get('mediaUrl', item.get('media','')).lower().split('?')[0]
            if item.get('storyType') == 'photo' and suffix.endswith(('.mp4','.webm')):
                raise ValueError('Video source cannot be posted as photo')
            if item.get('storyType') == 'video' and suffix.endswith(('.jpg','.jpeg','.png')):
                raise ValueError('Photo source cannot be posted as video')
    else:
        if manifest.get('type') != 'instagram' or manifest.get('postType') != 'story' or manifest.get('publishNow') is not False:
            raise ValueError('Only Instagram Story, publishNow=false is permitted')
        if manifest.get('handle') != 'liniya__sporta' or manifest.get('channelId'):
            raise ValueError('Expected Instagram handle liniya__sporta; direct channelId is forbidden')
        if manifest.get('text', '') != '':
            raise ValueError('Instagram Story cannot have external caption text')
        if at_utc(manifest.get('dueAt')) != due:
            raise ValueError('Buffer dueAt must equal publishAt exactly')
        media = manifest.get('media')
        if not isinstance(media, list) or len(media)!=1 or not isinstance(media[0],dict) or media[0].get('type') not in {'image','video'} or not public_url(media[0].get('url')):
            raise ValueError('Instagram Story requires one public HTTPS image/video')
        if not isinstance(manifest.get('isAiGenerated'),bool):
            raise ValueError('isAiGenerated must be explicit')
    return manifest, due


def candidates(platform: str, root: Path, now: datetime | None = None) -> list[tuple[datetime, Path]]:
    now = now or datetime.now(timezone.utc)
    folder = root/'requests'/'scheduled'/platform
    result=[]
    for path in folder.glob('*.json'):
        if not path.is_file() or path.is_symlink():
            continue
        job_id=path.stem
        if (root/'results'/'scheduled'/platform/f'{job_id}.json').exists():
            continue
        # Strict historical deduplication across legacy and new results.
        if any((root/p).exists() for p in [f'results/{job_id}.json',f'buffer-results/{job_id}.json',f'results/manual/{platform}/{job_id}.json']):
            continue
        try:
            _, due=validate(platform, path, root, now=now)
        except (ValueError, OSError, json.JSONDecodeError):
            continue
        if platform=='vk' and (due-now).total_seconds() > VK_MAX_ARM_SECONDS:
            continue
        result.append((due,path))
    return sorted(result, key=lambda x:(x[0],str(x[1])))


def git(root: Path,*args: str) -> None:
    subprocess.run(['git',*args],cwd=root,check=True,capture_output=True,text=True,timeout=60)


def reserve(root: Path,platform: str,path:Path,due:datetime) -> Path:
    job_id=path.stem
    git(root,'pull','--ff-only','origin','main')
    path=root/'requests'/'scheduled'/platform/(job_id+'.json')
    validate(platform,path,root)
    target=root/'results'/'scheduled'/platform/(job_id+'.json')
    if target.exists() or any((root/p).exists() for p in [f'results/{job_id}.json',f'buffer-results/{job_id}.json',f'results/manual/{platform}/{job_id}.json']):
        raise ValueError('Already attempted: do not post duplicates')
    target.parent.mkdir(parents=True,exist_ok=True)
    receipt={'id':job_id,'platform':platform,'status':'reserved_before_provider_call',
             'publishAtUTC':due.isoformat().replace('+00:00','Z'),
             'reservedAtUTC':datetime.now(timezone.utc).isoformat(),
             'runId':os.environ.get('GITHUB_RUN_ID',''),
             'note':'One durable attempt marker; never retry without manual reconciliation'}
    with target.open('x',encoding='utf-8') as f:
        json.dump(receipt,f,ensure_ascii=False,indent=2);f.write('\n')
    git(root,'config','user.name','ls-auto-social-bot')
    git(root,'config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git(root,'add','--',target.relative_to(root).as_posix())
    git(root,'commit','-m','Reserve one scheduled social attempt [skip ci]')
    git(root,'push','origin','HEAD:main')
    return target


def await_target(due:datetime, sleep=time.sleep, now_fn=lambda: datetime.now(timezone.utc)) -> None:
    while True:
        remain=(due-now_fn()).total_seconds()
        if remain <= 0:
            if remain < -VK_LATE_TOLERANCE_SECONDS:
                raise ValueError('Missed exact publish time; publication skipped, NO late retry')
            return
        sleep(min(remain,20.0))


def run_once(root:Path, platform:str, path:Path, due:datetime) -> bool:
    job_id=path.stem
    target=reserve(root,platform,path,due)
    status='provider_status_unknown'
    error=None
    receipt_data=None
    try:
        if platform=='vk':
            await_target(due)
        else:
            if datetime.now(timezone.utc)>=due:
                raise ValueError('Buffer schedule is now in the past; skipped')
        cmd=['node','scripts/publish-job.js' if platform=='vk' else 'scripts/buffer-job.js',
             str(path.relative_to(root))]
        call=subprocess.run(cmd,cwd=root,check=False,capture_output=True,text=True,timeout=180)
        receipt_path=root/('results' if platform=='vk' else 'buffer-results')/(job_id+'.json')
        provider=json.loads(receipt_path.read_text(encoding='utf-8')) if receipt_path.is_file() else {}
        if call.returncode!=0 or provider.get('ok') is not True or provider.get('id')!=job_id:
            raise RuntimeError('Provider action failed; check GitHub logs (no automatic retry)')
        value=provider.get('result',{})
        if platform=='buffer':
            post=value.get('post') if isinstance(value,dict) else None
            if not isinstance(post,dict) or not post.get('id') or at_utc(post.get('dueAt')) != due:
                raise RuntimeError('Buffer response lacks matching ID and scheduled dueAt; manual review needed')
            receipt_data={'post_id':str(post['id']),'dueAt':post.get('dueAt'),
                          'provider_status':post.get('status'),'channel_id':post.get('channelId')}
            status='scheduled_in_buffer'
        else:
            ids=[]
            items=value if isinstance(value,list) else [value]
            for it in items:
                if isinstance(it,dict):
                    for obj in ([it]+([it['result']] if isinstance(it.get('result'),dict) else [])):
                        if isinstance(obj,dict) and isinstance(obj.get('id'),int):
                            ids.append(obj['id'])
            receipt_data={'returned_story_ids':ids,'reported_count':len(items)}
            status='submitted_to_vk'
    except Exception as exc:
        error=str(exc)[:400]
        status='manual_reconciliation_required'
    old=json.loads(target.read_text(encoding='utf-8'))
    old.update({'status':status,'finishedAtUTC':datetime.now(timezone.utc).isoformat(),
                'provider':receipt_data,'error':error})
    target.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    git(root,'add','--',target.relative_to(root).as_posix())
    git(root,'commit','-m','Finalize scheduled social receipt [skip ci]')
    git(root,'pull','--rebase','origin','main')
    git(root,'push','origin','HEAD:main')
    return status in {'scheduled_in_buffer','submitted_to_vk'}


def main(argv:list[str]) -> int:
    if len(argv)!=3 or argv[1] not in {'vk','buffer'} or argv[2] not in {'validate','probe','process'}:
        print('Usage: python -m scripts.auto_social <vk|buffer> <validate|probe|process>');return 2
    platform,mode=argv[1:]
    if os.environ.get('GITHUB_ACTIONS')=='true' and (os.environ.get('GITHUB_REPOSITORY')!='lsevmos-gpt/ls-vk' or os.environ.get('GITHUB_REF')!='refs/heads/main'):
        print('::error::Unexpected repository or branch');return 1
    folder=ROOT/'requests'/'scheduled'/platform
    errors=[]
    for path in sorted(folder.glob('*.json')):
        if (ROOT/'results'/'scheduled'/platform/(path.stem+'.json')).exists():continue
        try:validate(platform,path,ROOT)
        except Exception as exc:
            # Past jobs don't publish; flag as EXPIRED rather than failing all future jobs.
            if 'past' in str(exc).lower():
                print('EXPIRED, not publishing:',path.name);continue
            errors.append(f'{path.name}: {exc}')
    if errors:
        for err in errors:print('::error::'+err)
        return 1
    if mode=='validate':
        print('SCHEDULE_VALIDATION=PASS; no provider requests');return 0
    if mode=='probe':
        count=len(candidates(platform,ROOT))
        print(f'PENDING_AUTO_JOBS={count} platform={platform}')
        output=os.environ.get('GITHUB_OUTPUT')
        if output:
            with open(output,'a',encoding='utf-8') as handle:
                handle.write('has_jobs='+('true' if count else 'false')+'\n')
        return 0
    successes=0
    while True:
        work=candidates(platform,ROOT)
        if not work:break
        due,path=work[0]
        try:
            ok=run_once(ROOT,platform,path,due)
        except Exception as exc:
            print('::error::Unable to reserve or finalize:',str(exc)[:250]);return 1
        if not ok:return 1
        successes+=1
    print(f'SCHEDULED_REQUESTS_PROCESSED={successes} platform={platform}')
    return 0

if __name__=='__main__':
    raise SystemExit(main(sys.argv))