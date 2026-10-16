"""Offline visual quality preflight for LS social visual assets.

Never publishes content or calls any remote service. Machine checks are NOT
an artistic review, proof of a real person's identity, or permission to post.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / 'visual-qa' / 'submissions'
SAFE_ID = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{7,127}$')
SHA = re.compile(r'^[a-f0-9]{64}$')
DRIVE_ID = re.compile(r'^[A-Za-z0-9_-]{15,128}$')
CORE_RGB = [(10, 30, 30), (51, 63, 63), (31, 130, 46), (48, 184, 82),
            (218, 255, 218), (245, 243, 234), (214, 174, 93), (242, 201, 76)]
APPROVED_LOGOS = {
    'лого т_белый.png': 'be3937ff7c9df8e1f93adcbbbc7a574dbe85eae2fbaccf9b5e467f3eb611e66e',
    'лого т_зеленый(20261016-202449).png': 'acb8fb6bec4bb8fba45825204601d3d7feeed18293cfef66c57e4497b5b9e528',
    'лого т_черный.png': 'd62a4b11f09b0a72a0a7336c53811c050e1df29b1d2a99485e70c6e4dbd1f334',
    'лого фитнес_бежевый.png': '82e0380c36bcdef5e30252247e40d787d198f14dbe682a8fb277c147c345eb9c',
    'лого фитнес_белый.png': 'd2786a4e66a3ed1248ce328651dc7e5946980fe70753b6f50ddef3c4b87176de',
    'лого фитнес_черный.png': 'e145980feff7d744c5c718aa7f0f59a47fc992fdad7f2260906b98c81e2ecb39',
}
LIMITS = {'final': 30_000_000, 'photo': 40_000_000,
          'logo': 3_000_000, 'svg': 4_000_000}
ALLOWED_TARGETS = {'story': (1080, 1920), 'feed_4_5': (1080, 1350),
                   'square': (1080, 1080), 'horizontal_16_9': (1920, 1080)}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scalar(element: ET.Element, name: str) -> float:
    value = str(element.get(name, '')).strip()
    if not re.fullmatch(r'\d+(?:\.\d+)?(?:px)?', value):
        raise ValueError(f'SVG element {name} must be positive pixels without units/transforms')
    return float(value.removesuffix('px'))


def local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1].lower()


def _image_ratio(data: bytes) -> float:
    from io import BytesIO
    with Image.open(BytesIO(data)) as im:
        return im.width / im.height


def check_svg(data: bytes, *, original_photo: bytes, original_logo: bytes,
              target: tuple[int, int], expected_name: str) -> list[str]:
    errors: list[str] = []
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        return ['SVG DTD/entities are forbidden']
    try:
        root = ET.fromstring(data)
        if local_name(root.tag) != 'svg':
            return ['Editable source must be SVG']
        if abs(scalar(root, 'width') - target[0]) > 0.01 or abs(scalar(root, 'height') - target[1]) > 0.01:
            errors.append('SVG canvas does not match PNG target dimensions')
    except (ET.ParseError, ValueError) as exc:
        return ['Cannot inspect editable SVG: ' + str(exc)]
    bad_tags = {'foreignobject', 'script', 'filter', 'mask', 'clippath', 'pattern'}
    images: list[str] = []
    text_nodes: list[str] = []
    expected_aspects = {
        digest(original_photo): _image_ratio(original_photo),
        digest(original_logo): _image_ratio(original_logo),
    }
    for element in root.iter():
        name = local_name(element.tag)
        if name in bad_tags:
            errors.append('Forbidden SVG element: ' + name)
        if element.get('transform'):
            errors.append('SVG transforms are disallowed for original-photo/logo safety; use x/y and uniform width/height')
        if name == 'image':
            if element.get('opacity') or 'opacity' in element.get('style', '') or element.get('filter'):
                errors.append('Original photo and logo must not have filters or opacity changes')
            href = element.get('{http://www.w3.org/1999/xlink}href') or element.get('href', '')
            m = re.fullmatch(r'data:image/(?:jpeg|png);base64,([A-Za-z0-9+/=]+)', href)
            if not m:
                errors.append('Every SVG image must embed an original JPEG/PNG data URL')
                continue
            try:
                content = base64.b64decode(m.group(1), validate=True)
                this_hash = digest(content)
                images.append(this_hash)
                w, h = scalar(element, 'width'), scalar(element, 'height')
                if w <= 0 or h <= 0:
                    errors.append('SVG image has nonpositive dimensions')
                elif this_hash in expected_aspects and abs(w / h - expected_aspects[this_hash]) > 0.002:
                    errors.append('Nonuniform photo/logo scaling detected')
                if element.get('preserveAspectRatio') == 'none':
                    errors.append('SVG cannot stretch photo/logo with preserveAspectRatio=none')
            except (ValueError, TypeError) as exc:
                errors.append('Invalid embedded image/dimensions: ' + str(exc))
        if name == 'text':
            family = element.get('font-family', '') + ' ' + element.get('style', '')
            if not re.search(r'Roboto\s*Condensed|\bInter\b', family, flags=re.I):
                errors.append('Editable text must use Roboto Condensed or Inter')
            contents = ' '.join(''.join(element.itertext()).split())
            if contents:
                text_nodes.append(contents)
            try:
                # This is a *coarse* safety preflight, NOT rendered glyph bounds.
                x, y = scalar(element, 'x'), scalar(element, 'y')
                left = 96 if target == (1080, 1920) else 40
                top = 250 if target == (1080, 1920) else 40
                bottom = 340 if target == (1080, 1920) else 40
                if x < left or x > target[0] - left or y < top or y > target[1] - bottom:
                    errors.append('Text anchor outside coarse safe area (actual glyph boxes still need visual review)')
            except ValueError:
                errors.append('Editable text needs untransformed numeric x and y')
            if element.get('transform'):
                errors.append('Text transforms require an independent visual review and are disallowed')
    if sorted(images) != sorted([digest(original_photo), digest(original_logo)]):
        errors.append('SVG must embed exactly the original photo and approved logo bytes once each, no other raster images')
    if not text_nodes or expected_name.casefold() not in ' '.join(text_nodes).casefold():
        errors.append('Real editable text containing confirmed display name is required')
    return errors


def validate_package(package: Path, *, approved_logos: dict[str, str] | None = None) -> dict:
    """Fail closed; return honest technical status and unanswered human criteria."""
    approved_logos = APPROVED_LOGOS if approved_logos is None else approved_logos
    fail: list[str] = []
    files: dict[str, bytes] = {}
    name = package.name
    if not SAFE_ID.fullmatch(name) or not package.is_dir():
        return {'id': name, 'status': 'BLOCKED', 'failures': ['Invalid job directory/name']}
    manifest_path = package / 'manifest.json'
    try:
        if manifest_path.is_symlink() or manifest_path.stat().st_size > 100_000:
            raise ValueError('Manifest too large or symlink')
        m = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        return {'id': name, 'status': 'BLOCKED', 'failures': ['Missing/invalid manifest: ' + str(exc)]}
    if not isinstance(m, dict):
        return {'id': name, 'status': 'BLOCKED', 'failures': ['Manifest must be an object']}
    if m.get('schema_version') != 1 or m.get('id') != name:
        fail.append('Schema version 1 and exact matching id are required')
    fmt = m.get('format')
    if fmt not in ALLOWED_TARGETS:
        fail.append('Unsupported target format')
        target = None
    else:
        target = ALLOWED_TARGETS[fmt]
    source = m.get('source', {})
    if not isinstance(source, dict):
        source = {}
    display_name = source.get('display_name')
    if not isinstance(display_name, str) or not display_name.strip() or len(display_name) > 120:
        fail.append('Missing verified display name')
        display_name = 'INVALID'
    if not DRIVE_ID.fullmatch(str(source.get('google_drive_photo_id', ''))):
        fail.append('Original photo must have a real Drive file id')
    if not DRIVE_ID.fullmatch(str(source.get('registry_drive_file_id', ''))):
        fail.append('Verified registry must be identified by Drive file id')
    reported_photo_hash = source.get('photo_sha256')
    if not isinstance(reported_photo_hash, str) or not SHA.fullmatch(reported_photo_hash):
        fail.append('Source photo SHA256 must be declared')
    declared_files = m.get('files')
    if not isinstance(declared_files, dict):
        declared_files = {}
    for role in ('final', 'photo', 'logo', 'svg'):
        entry = declared_files.get(role)
        if (not isinstance(entry, str) or not entry or Path(entry).name != entry
                or entry in {'.', '..'} or '/' in entry or '\\' in entry):
            fail.append('Unsafe/missing asset filename for ' + role)
            continue
        path = package / entry
        try:
            if path.is_symlink() or path.stat().st_size > LIMITS[role]:
                raise ValueError('File is too large or symlink')
            files[role] = path.read_bytes()
        except (OSError, ValueError) as exc:
            fail.append('Asset missing/unreadable ' + role + ': ' + str(exc))
    if 'photo' in files and reported_photo_hash != digest(files['photo']):
        fail.append('Photo bytes differ from declared original SHA256 (P01/P03)')
    logo_name = source.get('logo_master_filename')
    logo_hash = source.get('logo_master_sha256')
    if logo_name not in approved_logos:
        fail.append('Logo filename not in approved 16 Oct 2026 MASTER list (P02)')
    elif logo_hash != approved_logos[logo_name]:
        fail.append('Logo SHA256 claim differs from approved MASTER manifest (P02)')
    elif 'logo' in files and digest(files['logo']) != approved_logos[logo_name]:
        fail.append('Actual logo differs from approved MASTER bytes (P02)')
    for role in ('photo', 'logo'):
        if role in files:
            try:
                with Image.open(package / declared_files[role]) as im:
                    im.verify()
            except (OSError, ValueError) as exc:
                fail.append('Corrupt source image ' + role + ': ' + str(exc))
    if 'final' in files:
        try:
            with Image.open(package / declared_files['final']) as im:
                if im.format != 'PNG' or im.mode not in {'RGB', 'RGBA'}:
                    fail.append('Export must be RGB/RGBA PNG (P10)')
                if target and im.size != target:
                    fail.append(f'Incorrect pixel dimensions: {im.size}, expected {target} (P04)')
                if not im.info.get('icc_profile') and im.info.get('srgb') is None:
                    fail.append('Output PNG must contain actual sRGB ICC or sRGB metadata (P10)')
                sample = im.convert('RGB')
                sample.thumbnail((270, 480))
                coverage = sum(any(all(abs(p[i] - c[i]) <= 8 for i in range(3))
                                   for c in CORE_RGB) for p in sample.get_flattened_data())
                if coverage < 100:
                    fail.append('Cannot verify visibly present core brand color (P07 technical only)')
        except (OSError, ValueError) as exc:
            fail.append('Final export unreadable: ' + str(exc))
    if target and {'svg', 'photo', 'logo'} <= files.keys():
        fail.extend(check_svg(files['svg'], original_photo=files['photo'],
                              original_logo=files['logo'], target=target,
                              expected_name=display_name.strip()))
    return {
        'id': name,
        'status': 'BLOCKED' if fail else 'TECHNICAL_PASS_REVIEW_REQUIRED',
        'failures': fail,
        'technical_scope': ['source bytes and claimed SHA256', 'approved logo SHA256',
                            'dimensions', 'embedded SVG original assets',
                            'editable text font/anchor preflight', 'sRGB PNG',
                            'visible brand color'],
        'human_review_required': [
            'Photo actually depicts the correct employee (registry not API-verified)',
            'No face/body change, obscuring, unusual scaling or AI artifacts in rendered output',
            'Actual font glyph bounds and all 96/250/340 safe-zone margins',
            'Artistic quality: composition, celebration, readability, absence of generic templates',
            'Factual copy and user approval before any publication',
        ],
        'publish_authorized': False,
    }


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == 'scan':
        packages = sorted(p for p in PACKAGE_DIR.glob('*') if p.is_dir()) if PACKAGE_DIR.exists() else []
        if not packages:
            print('NO_VISUAL_SUBMISSIONS: no visual is approved or published')
            return 0
        reports = [validate_package(p) for p in packages]
    elif len(argv) == 3 and argv[1] == 'job' and SAFE_ID.fullmatch(argv[2]):
        reports = [validate_package(PACKAGE_DIR / argv[2])]
    else:
        print('Usage: python -m scripts.visual_quality_gate scan | job <id>')
        return 2
    blocked = False
    for report in reports:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if report['status'] == 'BLOCKED':
            blocked = True
            for f in report['failures']:
                print('::error::Visual QA: ' + f)
    return 1 if blocked else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))