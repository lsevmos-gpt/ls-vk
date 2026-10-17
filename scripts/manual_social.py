"""Fail-closed guard for explicit manual VK and Buffer submissions.

Creates durable attempt markers; prevents replay of historical and new jobs.
Never calls providers itself. Accepts exclusively user-approved public content.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .validate_social import JOB_ID, PUBLISH, validate_job

ROOT = Path(__file__).resolve().parents[1]
APPROVAL_PHRASE = 'PUBLISH_APPROVED_CONTENT'


def paths(root: Path, platform: str, job_id: str) -> tuple[Path, Path, Path]:
    if platform not in PUBLISH or not JOB_ID.fullmatch(job_id):
        raise ValueError('Invalid platform or job id')
    source = root / 'requests' / platform / (job_id + '.json')
    target = root / 'results' / 'manual' / platform / (job_id + '.json')
    legacy = root / ('results' if platform == 'vk' else 'buffer-results') / (job_id + '.json')
    return source, target, legacy


def reserve(root: Path, platform: str, job_id: str, confirmation: str,
            *, actor: str, event: str, branch: str, run_id: str,
            private: bool) -> Path:
    # Public repos are allowed: only explicitly approved public assets can be dispatched.
    if (actor, event, branch) != ('lsevmos-gpt', 'workflow_dispatch', 'refs/heads/main'):
        raise ValueError('Only lsevmos-gpt may manually publish from main')
    if confirmation != APPROVAL_PHRASE:
        raise ValueError('Incorrect explicit publication confirmation')
    source, target, legacy = paths(root, platform, job_id)
    if not source.is_file() or source.is_symlink() or source.stat().st_size > 128_000:
        raise ValueError('Source request missing, symlink or oversized')
    body = json.loads(source.read_text(encoding='utf-8'))
    failures = validate_job(platform, source.name, body)
    if failures:
        raise ValueError('; '.join(failures))
    if body.get('publicContent') is not True:
        raise ValueError('Only explicitly approved publicContent=true may be published')
    if body['type'] not in PUBLISH[platform]:
        raise ValueError('Read-only and delete operations cannot be published')
    if legacy.exists() or target.exists():
        raise ValueError('An earlier attempt or receipt exists; do not replay job')
    target.parent.mkdir(parents=True, exist_ok=True)
    marker = {
        'id': job_id, 'platform': platform, 'type': body['type'],
        'status': 'submission_started', 'run_id': run_id,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'note': 'A provider request may be partial. Never automatically retry this ID.',
    }
    with target.open('x', encoding='utf-8') as file:
        json.dump(marker, file, ensure_ascii=False, indent=2)
        file.write('\n')
    return target


def finalize(root: Path, platform: str, job_id: str, run_id: str,
             exit_code: str) -> Path:
    _, target, legacy = paths(root, platform, job_id)
    old = json.loads(target.read_text(encoding='utf-8'))
    if old.get('status') != 'submission_started' or old.get('run_id') != run_id:
        raise ValueError('Reservation does not match run')
    provider = json.loads(legacy.read_text(encoding='utf-8')) if legacy.is_file() else {}
    success = exit_code == '0' and provider.get('ok') is True and provider.get('id') == job_id
    # Only non-sensitive summary is committed; the legacy full provider receipt is ephemeral.
    receipt = {
        **old,
        'status': 'submitted_to_provider' if success else 'manual_review_required',
        'finished_at': datetime.now(timezone.utc).isoformat(),
        'provider_ok': success,
        'note': ('Provider accepted submission; actual platform publication not verified.'
                 if success else 'Check provider manually; partial posting possible. Never retry this id.'),
    }
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return target


def main() -> int:
    platform = os.environ.get('SOCIAL_PLATFORM', '')
    job_id = os.environ.get('SOCIAL_JOB_ID', '')
    phase = sys.argv[1] if len(sys.argv) > 1 else ''
    try:
        if phase == 'reserve':
            target = reserve(
                ROOT, platform, job_id, os.environ.get('SOCIAL_CONFIRMATION', ''),
                actor=os.environ.get('GITHUB_ACTOR', ''),
                event=os.environ.get('GITHUB_EVENT_NAME', ''),
                branch=os.environ.get('GITHUB_REF', ''),
                run_id=os.environ.get('GITHUB_RUN_ID', ''),
                private=os.environ.get('SOCIAL_REPO_PRIVATE', 'false') == 'true')
        elif phase == 'finalize':
            target = finalize(ROOT, platform, job_id, os.environ.get('GITHUB_RUN_ID', ''),
                              os.environ.get('PUBLISH_EXIT_CODE', ''))
        else:
            raise ValueError('Expected reserve or finalize')
        print('RECEIPT=' + target.relative_to(ROOT).as_posix())
        return 0
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print('::error::Manual social guard: ' + str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())