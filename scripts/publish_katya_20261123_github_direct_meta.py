"""Single user-approved Katya Instagram Reels recovery via existing GitHub Actions and direct Meta Graph API.

One durable GitHub reservation, one video container, one rupload transfer, one publish call.
VK and Cloudflare scheduling are never mutated. No automatic retries after unknown Meta outcomes.
"""
from __future__ import annotations
import hashlib, json, os, re, subprocess, sys, time
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from scripts.instagram_collab import MetaClient, CollabError

ROOT=Path(__file__).resolve().parents[1]
JOB='katya-shapovalova-20261123-github-direct'
REQ=ROOT/'requests/instagram-meta'/(JOB+'.json')
RECEIPT=ROOT/'results/instagram-meta'/(JOB+'.json')
VIDEO=ROOT/'media/katya-shapovalova-reel-meta-2k-20261123.mp4'
COVER=ROOT/'media/katya-shapovalova-cover-meta-2k-20261123.jpg'
PREPARED=Path('/tmp/katya-github-meta-2k-128k.mp4')
VIDEO_SHA='2fea1288daf7cc3c37ca7dd0468138303760885163622038367e18dda6dd008d'
COVER_SHA='05a82e0d76a414a480fb0d2b795522f963792d96631705650866bca1572dccd3'
COVER_URL='https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/katya-shapovalova-cover-meta-2k-20261123.jpg'
ACCOUNT='liniya__sporta'
COLLABS=['katia_shap']
UTC=lambda:datetime.now(timezone.utc).isoformat()
def sha(p):
    with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def git(*args):
    cp=subprocess.run(['git',*args],cwd=ROOT,timeout=130,text=True,capture_output=True)
    if cp.returncode:raise RuntimeError('GIT_'+args[0]+'_ERROR '+(cp.stderr or cp.stdout)[-180:])
    return cp.stdout.strip()
def record(d,initial=False):
    d['updatedAtUTC']=UTC()
    RECEIPT.parent.mkdir(parents=True,exist_ok=True)
    with RECEIPT.open('x' if initial else 'w',encoding='utf-8') as f:
        json.dump(d,f,ensure_ascii=False,indent=2);f.write('\n')
    git('add','--',str(RECEIPT.relative_to(ROOT)))
    git('commit','-m','Katya GitHub direct Meta '+d['status']+' [skip ci]')
    for k in range(6):
        try:git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return
        except Exception:
            if k==5:raise
            time.sleep(k+2)
def validated():
    if not (os.getenv('GITHUB_REPOSITORY')=='lsevmos-gpt/ls-vk'
        and os.getenv('GITHUB_REF')=='refs/heads/main'
        and os.getenv('GITHUB_EVENT_NAME')=='push'
        and os.getenv('GITHUB_ACTOR')=='lsevmos-gpt'
        and (os.getenv('GITHUB_RUN_ID') or '').isdigit()):
        raise RuntimeError('UNAUTHORIZED_GITHUB_CONTEXT')
    git('pull','--ff-only','origin','main')
    if RECEIPT.exists():
        print('KATYA_IG_ATTEMPT_ALREADY_RESERVED_NO_DUPLICATE',flush=True)
        return None
    req=json.loads(REQ.read_text('utf-8'))
    if not (req.get('id')==JOB and req.get('type')=='instagram-reel'
        and req.get('handle')==ACCOUNT and req.get('postType')=='reel'
        and req.get('approved') is True and req.get('publicContent') is True
        and req.get('shouldShareToFeed') is True and req.get('publishNow') is True
        and req.get('route')=='GITHUB_ACTIONS_DIRECT_META_GRAPH_RUPLOAD'
        and req.get('collaborators')==COLLABS
        and req.get('coverUrl')==COVER_URL
        and req.get('media')==[{'type':'video','url':'https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/katya-shapovalova-reel-meta-2k-20261123.mp4'}]
        and req.get('sourceVideoSHA256')==VIDEO_SHA and req.get('coverSHA256')==COVER_SHA
        and isinstance(req.get('text'),str) and req['text'].startswith('Знакомьтесь — Екатерина Шаповалова! ✨')
        and req['text'].endswith('Героев Сталинграда, 6Д')
        and 300<len(req['text'])<2200):
        raise RuntimeError('EXACT_APPROVAL_AND_CAPTION_MISMATCH')
    if not VIDEO.is_file() or VIDEO.stat().st_size!=47593685 or sha(VIDEO)!=VIDEO_SHA:
        raise RuntimeError('SOURCE_MP4_SHA256_MISMATCH')
    if not COVER.is_file() or COVER.stat().st_size!=949002 or sha(COVER)!=COVER_SHA:
        raise RuntimeError('APPROVED_2K_COVER_SHA256_MISMATCH')
    p=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-i',str(VIDEO),
        '-map','0:v:0','-map','0:a:0','-sn','-dn','-c:v','copy','-c:a','aac','-b:a','128k',
        '-ar','48000','-ac','2','-movflags','+faststart',str(PREPARED)],
        timeout=400,capture_output=True,text=True)
    if p.returncode:raise RuntimeError('AUDIO_META_CONVERSION_FAILED '+p.stderr[-180:])
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(PREPARED)],timeout=40))
    video=next(x for x in info['streams'] if x['codec_type']=='video')
    audio=next(x for x in info['streams'] if x['codec_type']=='audio')
    if not (video['codec_name']=='h264' and video['pix_fmt']=='yuv420p'
        and (video['width'],video['height'])==(1440,2560)
        and video['avg_frame_rate']=='25/1' and audio['codec_name']=='aac'
        and audio['sample_rate']=='48000' and audio['channels']==2
        and int(audio.get('bit_rate',0))<135000
        and 46<float(info['format']['duration'])<47
        and 0<PREPARED.stat().st_size<95000000):
        raise RuntimeError('META_ENCODING_CONFORMANCE_FAILED')
    return req

def existing_reel(client,caption):
    # Fail closed if the read-only Meta list is not accessible. Avoid creating a duplicate.
    res=client._api('GET',client.ig_user_id+'/media',
                    {'fields':'id,caption,permalink,media_type,media_product_type,timestamp','limit':'60'})
    if not isinstance(res.get('data'),list):raise RuntimeError('IG_LIST_RESPONSE_UNAVAILABLE')
    for row in res['data']:
        if row.get('caption','').strip()==caption.strip() or (
          'Знакомьтесь — Екатерина Шаповалова!' in row.get('caption','')
          and row.get('media_product_type')=='REELS'):
            return {'id':row.get('id'),'permalink':row.get('permalink')}
    return None

def rupload(uri,token,path):
    u=urlsplit(uri)
    if u.scheme!='https' or u.hostname!='rupload.facebook.com' or not u.path.startswith('/ig-api-upload/'):
        raise RuntimeError('UNEXPECTED_META_BINARY_UPLOAD_TARGET')
    body=path.read_bytes()
    request=Request(uri,data=body,method='POST',headers={
        'Authorization':'OAuth '+token,'offset':'0','file_size':str(len(body)),
        'Content-Type':'application/octet-stream','Accept':'application/json'
    })
    try:
        with urlopen(request,timeout=480) as resp:
            ans=json.loads(resp.read(12000).decode('utf-8'))
    except HTTPError as exc:
        try:code=json.loads(exc.read(12000).decode()).get('error',{}).get('code','unknown')
        except Exception:code='unknown'
        raise RuntimeError('META_RUPLOAD_HTTP_'+str(exc.code)+'_CODE_'+str(code)) from None
    except (URLError,TimeoutError,OSError) as exc:
        raise RuntimeError('META_RUPLOAD_TRANSPORT_'+type(exc).__name__) from None
    if ans.get('success') is not True:raise RuntimeError('META_RUPLOAD_NOT_CONFIRMED')
    return True

def main():
    req=validated()
    if req is None:return
    token=os.environ.get('META_IG_ACCESS_TOKEN','')
    client=MetaClient(token,os.environ.get('META_IG_USER_ID',''),graph_version='v26.0')
    client.verify_account()
    prev=existing_reel(client,req['text'])
    if prev:
        print('ALREADY_PUBLISHED_SKIP_DUPLICATE',json.dumps(prev),flush=True)
        return
    if RECEIPT.exists():raise RuntimeError('PRIOR_ATTEMPT_GUARD')
    git('config','user.name','ls-katya-ig-github-direct')
    git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    receipt=dict(id=JOB,status='reserved_before_meta_container',
      route='GITHUB_ACTIONS_DIRECT_META_GRAPH_RUPLOAD',account=ACCOUNT,
      collaborator=COLLABS[0],collaboratorAcceptance='pending',
      videoSourceSHA256=VIDEO_SHA,videoUploadSHA256=sha(PREPARED),
      coverSHA256=COVER_SHA,mediaCreatedId=None,publishedMediaId=None,
      runId=os.environ['GITHUB_RUN_ID'],createdAtUTC=UTC(),noAutomaticRetries=True)
    record(receipt,initial=True)
    try:
        fields={'media_type':'REELS','upload_type':'resumable','caption':req['text'],
            'share_to_feed':'true','collaborators':json.dumps(COLLABS,separators=(',',':')),
            'cover_url':COVER_URL}
        container=client._api('POST',client.ig_user_id+'/media',fields)
        cid=str(container.get('id',''))
        if not cid.isdecimal():raise RuntimeError('META_RESUMABLE_CONTAINER_ID_MISSING')
        receipt.update(status='container_created',mediaCreatedId=cid)
        record(receipt)
        uri=container.get('uri') or 'https://rupload.facebook.com/ig-api-upload/v26.0/'+cid
        receipt['status']='binary_upload_started'
        record(receipt)
        rupload(uri,token,PREPARED)
        receipt['status']='binary_upload_api_confirmed'
        record(receipt)
        for i in range(40):
            s=client._api('GET',cid,{'fields':'status_code,status'})
            state=str(s.get('status_code','')).upper()
            if state=='FINISHED':break
            if state in ('ERROR','EXPIRED','PUBLISHED'):
                receipt['metaContainerStatus']=str(s.get('status',''))[:330]
                raise RuntimeError('META_CONTAINER_'+state+' '+receipt['metaContainerStatus'])
            if i<39:time.sleep(15)
        else:raise RuntimeError('META_CONTAINER_PROCESSING_TIMEOUT_NO_AUTORETRY')
        receipt['status']='ready_to_publish'
        record(receipt)
        receipt['status']='publish_call_started'
        record(receipt)
        published=client._api('POST',client.ig_user_id+'/media_publish',{'creation_id':cid})
        media_id=str(published.get('id') or '')
        if not media_id.isdecimal():raise RuntimeError('MEDIA_PUBLISH_NO_ID_UNCERTAIN')
        receipt.update(status='meta_api_publish_accepted',publishedMediaId=media_id,
                       collaboratorAcceptance='invitation_requested_not_accepted')
        record(receipt)
        for i in range(8):
            try:
                readback=client._api('GET',media_id,{'fields':'id,permalink,username,media_type,timestamp'})
                if str(readback.get('id'))==media_id and readback.get('username')==ACCOUNT and readback.get('permalink'):
                    receipt.update(status='published_readback_confirmed',permalink=readback['permalink'],
                                   mediaType=readback.get('media_type'))
                    break
            except Exception:pass
            if i<7:time.sleep(5)
        record(receipt)
        print('KATYA_INSTAGRAM_RESULT '+json.dumps({
            'status':receipt['status'],'mediaId':media_id,
            'permalink':receipt.get('permalink'),'collaborator':'katia_shap',
            'invitationAcceptance':'unconfirmed'},ensure_ascii=False),flush=True)
    except Exception as exc:
        receipt['status']='manual_reconciliation_required'
        receipt['errorType']=type(exc).__name__
        receipt['errorMessage']=str(exc).replace(token,'[REDACTED]')[:360]
        receipt['note']='Do not retry automatically; reconcile Meta container/media and IG profile.'
        try:record(receipt)
        except Exception as persist:print('KATYA_RECEIPT_UPDATE_FAILED '+type(persist).__name__,flush=True)
        raise

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('::error::KATYA_INSTAGRAM_GITHUB '+str(e).replace(os.getenv('META_IG_ACCESS_TOKEN','UNSETTOKEN'),'[REDACTED]')[:360],file=sys.stderr)
        sys.exit(1)
