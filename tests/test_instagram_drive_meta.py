"""Offline safety tests: no Google, GitHub or Meta network access."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import instagram_drive_meta as mod


class DriveMetaValidationTests(unittest.TestCase):
    def _manifest(self, kind="reel"):
        return {
            "id": "reel-test-2026", "handle": "liniya__sporta", "postType": kind,
            "driveFileId": "1C-0j_Dv8Vcgmp2miVcEq2a5FxOw3Zqy6",
            "approved": True, "publicContent": True,
        }

    def test_reel_valid_with_direct_drive_file_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "reel-test-2026.json"
            path.write_text(json.dumps(self._manifest()), encoding="utf-8")
            with patch.object(mod, "REQUESTS", folder):
                self.assertEqual(mod.manifest_from_path(path)["postType"], "reel")

    def test_story_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "reel-test-2026.json"
            path.write_text(json.dumps(self._manifest("story")), encoding="utf-8")
            with patch.object(mod, "REQUESTS", folder):
                self.assertEqual(mod.manifest_from_path(path)["postType"], "story")

    def test_story_caption_forbidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "reel-test-2026.json"
            m = self._manifest("story")
            m["text"] = "caption"
            path.write_text(json.dumps(m), encoding="utf-8")
            with patch.object(mod, "REQUESTS", folder):
                with self.assertRaises(mod.DriveMetaError):
                    mod.manifest_from_path(path)

    def test_not_approved_blocks_publishing(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "reel-test-2026.json"
            m = self._manifest()
            m["approved"] = False
            path.write_text(json.dumps(m), encoding="utf-8")
            with patch.object(mod, "REQUESTS", folder):
                with self.assertRaises(mod.DriveMetaError):
                    mod.manifest_from_path(path)

    def test_outside_queue_folder_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reel-test-2026.json"
            path.write_text(json.dumps(self._manifest()), encoding="utf-8")
            with self.assertRaises(mod.DriveMetaError):
                mod.manifest_from_path(path)

    def test_strict_uri_host_validation(self):
        cid = "1800000000000"
        self.assertEqual(
            mod.checked_rupload_uri("", "v26.0", cid),
            "https://rupload.facebook.com/ig-api-upload/v26.0/" + cid)
        with self.assertRaises(mod.DriveMetaError):
            mod.checked_rupload_uri(
                "https://evil.example/ig-api-upload/v26.0/" + cid, "v26.0", cid)
        with self.assertRaises(mod.DriveMetaError):
            mod.checked_rupload_uri(
                "https://rupload.facebook.com/ig-api-upload/v26.0/" + cid + "?access_token=bad",
                "v26.0", cid)

    def test_preserve_compatible_1080p_without_upscaling(self):
        meta = {"duration": 12.0,
                "video": {"width": 1080, "height": 1920, "avg_frame_rate": "30/1",
                          "codec_name": "h264", "pix_fmt": "yuv420p"},
                "audio": {"codec_name": "aac", "sample_rate": "48000", "bit_rate": "128000"}}
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            source.write_bytes(b"x" * 1000)
            with patch.object(mod, "probe", return_value=meta):
                target, quality = mod.render_meta_2k(source, Path(tmp) / "output.mp4", "reel")
            self.assertEqual(target, source)
            self.assertEqual(quality["outputResolution"], "1080x1920")
            self.assertFalse(quality["reencoded"])

    def test_wrong_ratio_no_implicit_cropping(self):
        meta = {"duration": 12.0,
                "video": {"width": 1080, "height": 1080, "avg_frame_rate": "30/1",
                          "codec_name": "h264", "pix_fmt": "yuv420p"},
                "audio": {"codec_name": "aac", "sample_rate": "48000", "bit_rate": "128000"}}
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            source.write_bytes(b"x" * 1000)
            with patch.object(mod, "probe", return_value=meta):
                with self.assertRaises(mod.DriveMetaError):
                    mod.render_meta_2k(source, Path(tmp) / "out.mp4", "reel")


if __name__ == "__main__":
    unittest.main()
