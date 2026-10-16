"""Offline adversarial tests for visual QA. No real uploads or publications."""
import base64
import hashlib
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageCms
from scripts.visual_quality_gate import validate_package


def png_bytes(size, color, *, icc=False):
    img = Image.new('RGB', size, color)
    out = BytesIO()
    kwargs = {}
    if icc:
        kwargs['icc_profile'] = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    img.save(out, format='PNG', **kwargs)
    return out.getvalue()


def jpg_bytes(size=(800, 1200)):
    img = Image.new('RGB', size, '#A3B4C5')
    out = BytesIO()
    img.save(out, format='JPEG', quality=90)
    return out.getvalue()


class VisualQualityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name) / 'birthday-test0001'
        self.directory.mkdir()
        photo = jpg_bytes()
        logo = png_bytes((2048, 476), '#288436')
        self.digest = lambda b: hashlib.sha256(b).hexdigest()
        self.logo_hash = self.digest(logo)
        self.approved = {'лого т_белый.png': self.logo_hash}
        a = base64.b64encode(photo).decode('ascii')
        b = base64.b64encode(logo).decode('ascii')
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1080" height="1920">
          <rect x="0" y="0" width="1080" height="1920" fill="#0A1E1E"/>
          <image x="410" y="370" width="400" height="600" xlink:href="data:image/jpeg;base64,{a}"/>
          <image x="120" y="1050" width="400" height="92.96875" xlink:href="data:image/png;base64,{b}"/>
          <text x="110" y="1250" font-family="Roboto Condensed" font-size="88">АННА</text>
          <text x="110" y="1450" font-family="Inter" font-size="40">С днём рождения!</text>
        </svg>'''
        self.svg = svg.encode('utf-8')
        self.photo = photo
        self.logo = logo
        self.original = {
            'schema_version': 1, 'id': self.directory.name, 'format': 'story',
            'source': {
                'display_name': 'АННА',
                'google_drive_photo_id': '1299EJ27_qt3FC9tQXfbH_RL_rLOzg_NT',
                'registry_drive_file_id': '16Zi0NH2QWtI8YujwmrMvLKfGE9m-Ow8A',
                'photo_sha256': self.digest(photo),
                'logo_master_filename': 'лого т_белый.png',
                'logo_master_sha256': self.logo_hash,
            },
            'files': {'final': 'final.png', 'photo': 'photo.jpg',
                      'logo': 'logo.png', 'svg': 'composition.svg'},
        }
        (self.directory / 'photo.jpg').write_bytes(photo)
        (self.directory / 'logo.png').write_bytes(logo)
        (self.directory / 'final.png').write_bytes(png_bytes((1080, 1920), '#0A1E1E', icc=True))
        (self.directory / 'composition.svg').write_bytes(self.svg)
        self.write_manifest(self.original)

    def write_manifest(self, m):
        (self.directory / 'manifest.json').write_text(json.dumps(m, ensure_ascii=False), encoding='utf-8')

    def result(self):
        return validate_package(self.directory, approved_logos=self.approved)

    def test_nominal_does_not_claim_artistic_approval(self):
        r = self.result()
        self.assertEqual(r['status'], 'TECHNICAL_PASS_REVIEW_REQUIRED', r['failures'])
        self.assertFalse(r['publish_authorized'])
        self.assertTrue(r['human_review_required'])

    def test_reject_tampered_photo(self):
        (self.directory / 'photo.jpg').write_bytes(self.photo + b'X')
        self.assertEqual(self.result()['status'], 'BLOCKED')

    def test_reject_unapproved_logo(self):
        (self.directory / 'logo.png').write_bytes(self.logo + b'X')
        self.assertEqual(self.result()['status'], 'BLOCKED')

    def test_reject_wrong_final_size(self):
        (self.directory / 'final.png').write_bytes(png_bytes((941, 1672), '#0A1E1E', icc=True))
        self.assertEqual(self.result()['status'], 'BLOCKED')

    def test_reject_missing_srgb_profile(self):
        (self.directory / 'final.png').write_bytes(png_bytes((1080, 1920), '#0A1E1E'))
        self.assertEqual(self.result()['status'], 'BLOCKED')

    def test_reject_extra_generated_person_image(self):
        svg = self.svg.decode().replace('</svg>',
            '<image x="110" y="350" width="80" height="120" xlink:href="data:image/jpeg;base64,'
            + base64.b64encode(jpg_bytes((80, 120))).decode() + '"/></svg>')
        (self.directory / 'composition.svg').write_text(svg, encoding='utf-8')
        self.assertEqual(self.result()['status'], 'BLOCKED')

    def test_reject_improper_font(self):
        (self.directory / 'composition.svg').write_bytes(self.svg.replace(b'Roboto Condensed', b'Arial'))
        self.assertEqual(self.result()['status'], 'BLOCKED')

    def test_reject_text_outside_safe_zone(self):
        (self.directory / 'composition.svg').write_bytes(self.svg.replace(b'y="1250"', b'y="1840"'))
        self.assertEqual(self.result()['status'], 'BLOCKED')

    def test_reject_missing_brand_core_color(self):
        (self.directory / 'final.png').write_bytes(png_bytes((1080, 1920), '#FFFFFF', icc=True))
        self.assertEqual(self.result()['status'], 'BLOCKED')

    def test_reject_manifest_path_escape(self):
        m = json.loads(json.dumps(self.original))
        m['files']['photo'] = '../photo.jpg'
        self.write_manifest(m)
        self.assertEqual(self.result()['status'], 'BLOCKED')

    def test_missing_manifest_blocked(self):
        (self.directory / 'manifest.json').unlink()
        self.assertEqual(self.result()['status'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()