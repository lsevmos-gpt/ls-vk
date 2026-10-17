"""Offline validation for NEW lsevmos-gpt social requests; never publishes.

Legacy queue/ and buffer-queue/ are intentionally excluded. No network calls.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
INBOXES = {'vk': ROOT / 'requests' / 'vk', 'buffer': ROOT / 'requests' / 'buffer'}
READONLY = {'vk': {'check', 'check-story', 'inspect-media', 'inspect-stories'},
            'buffer': {'check-buffer'}}
PUBLISH = {'vk': {'post', 'photo', 'video', 'clip', 'story', 'story-batch'},
           'buffer': {'instagram', 'instagram-batch'}}
JOB_ID = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{7,127}$')
MAX_BYTES = 128_000
BLOCKED_HOSTS = {'github.com', 'api.github.com',
                 'private-user-images.githubusercontent.com', 'drive.google.com',
                 'docs.google.com', 'localhost'}


def safe_public_media_url(url: object) -> bool:
    if not isinstance(url, str) or not url.startswith('https://'):
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    host = (parsed.hostname or '').lower()
    if (not host or host in BLOCKED_HOSTS or
            (host == 'raw.githubusercontent.com' and not parsed.path.startswith('/lsevmos-gpt/ls-vk/main/media/')) or
            (host.endswith('.githubusercontent.com') and host != 'raw.githubusercontent.com')
            or host.endswith('.internal') or host.endswith('.localhost')
            or parsed.username or parsed.password or parsed.fragment
            or parsed.port not in (None, 443)):
        return False
    if any(p in url.lower() for p in ('access_token=', 'apikey=', 'api_key=', 'authorization=')):
        return False
    return True


def safe_local_media(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith('media/'):
        return False
    p = Path(value)
    return not p.is_absolute() and '..' not in p.parts and len(p.parts) > 1


def validate_job(platform: str, filename: str, body: object) -> list[str]:
    if platform not in INBOXES or not isinstance(body, dict):
        return ['Unsupported platform or JSON root is not object']
    errors: list[str] = []
    job_id = body.get('id')
    if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id) or job_id != Path(filename).stem:
        errors.append('id must match the JSON filename and use 8-128 safe characters')
    kind = body.get('type')
    if kind not in READONLY[platform] | PUBLISH[platform]:
        return errors + ['Unsupported or destructive job type']
    if kind in PUBLISH[platform] and body.get('approved') is not True:
        errors.append('Publication requires approved=true')
    if kind in PUBLISH[platform] and body.get('publicContent') is not True:
        errors.append('Only publicContent=true may be sent from public repository')
    if platform == 'buffer':
        if body.get('channelId'):
            errors.append('Direct channelId bypass is forbidden: resolve unique Instagram handle instead')
        if body.get('handle', 'liniya__sporta') != 'liniya__sporta':
            errors.append('Wrong Instagram handle')
        if kind in {'instagram', 'instagram-batch'}:
            posts = [body] if kind == 'instagram' else body.get('posts')
            if not isinstance(posts, list) or not posts:
                errors.append('Instagram requires a nonempty post list')
            else:
                for post in posts:
                    if not isinstance(post, dict) or not isinstance(post.get('media'), list) or not post['media']:
                        errors.append('Every Instagram post requires media[]')
                        continue
                    for asset in post['media']:
                        if (not isinstance(asset, dict) or asset.get('type', 'image') not in {'image', 'video'}
                                or not safe_public_media_url(asset.get('url'))):
                            errors.append('Instagram media must be a public HTTPS URL with type image/video')
    if platform == 'vk':
        if kind == 'post' and not str(body.get('text', '')).strip():
            errors.append('VK wall post requires text')
        if kind in {'story', 'story-batch'}:
            stories = [body] if kind == 'story' else body.get('stories')
            if not isinstance(stories, list) or not stories or len(stories) > 12:
                errors.append('Stories require 1-12 entries')
            else:
                for item in stories:
                    if not isinstance(item, dict) or item.get('storyType') not in {'photo', 'video'}:
                        errors.append('Story item requires explicit photo/video storyType')
                        continue
                    if not (safe_public_media_url(item.get('mediaUrl')) or safe_local_media(item.get('media'))):
                        errors.append('Story needs a public HTTPS mediaUrl or safe relative media/ file')
        if kind in {'photo', 'video', 'clip'}:
            medias = body.get('media')
            if kind == 'photo':
                if not isinstance(medias, list) or not medias or any(not safe_local_media(x) for x in medias):
                    errors.append('VK wall photos require media[] relative local paths')
            elif not (safe_public_media_url(body.get('mediaUrl')) or safe_local_media(medias)):
                errors.append('VK video/clip needs supported source')
    if kind == 'inspect-media' and not safe_public_media_url(body.get('mediaUrl')):
        errors.append('Inspect-media requires a public HTTPS URL')
    return errors


def validate_directory(platform: str, directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    errors = []
    for file in sorted(directory.glob('*.json')):
        try:
            if file.is_symlink() or file.stat().st_size > MAX_BYTES:
                raise ValueError('Invalid size or symlink')
            payload = json.loads(file.read_text(encoding='utf-8'))
            errors.extend(file.name + ': ' + e for e in validate_job(platform, file.name, payload))
        except (OSError, ValueError, UnicodeError) as exc:
            errors.append(file.name + ': ' + str(exc))
    return errors


def main() -> int:
    errors = [e for p, d in INBOXES.items() for e in validate_directory(p, d)]
    for err in errors:
        print('::error::' + err)
    print('NEW_SOCIAL_REQUESTS=' + ('BLOCKED' if errors else 'VALID') + '; no publish or API calls')
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())