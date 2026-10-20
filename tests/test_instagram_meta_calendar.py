"""No-network regression tests for the independent Instagram monthly calendar."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.instagram_meta_calendar import (
    CalendarError, MAX_EARLY, MAX_LATE, _when, find_candidate,
    load_calendar, publish_via_meta, validate_manifest,
)


class FakeMeta:
    def __init__(self):
        self.ig_user_id = "17841458490047255"
        self.calls = []
        self.containers = 0
        self.verified = False
        self._sleep = lambda delay: None

    def verify_account(self):
        self.verified = True
        return {"id": self.ig_user_id, "username": "liniya__sporta"}

    def _api(self, method, path, fields=None):
        self.calls.append((method, path, fields))
        if method == "POST" and path.endswith("/media"):
            self.containers += 1
            return {"id": str(12000 + self.containers)}
        if method == "GET" and path.isdecimal():
            return {"status_code": "FINISHED"}
        if method == "POST" and path.endswith("/media_publish"):
            return {"id": "18180000000000000"}
        raise AssertionError("Unexpected fake API call: " + method + " " + path)


class CalendarTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.month = self.root / "calendar" / "instagram" / "2026-11"
        self.month.mkdir(parents=True)
        self.id = "ig-20261114-test001"
        self.json = self.month / (self.id + ".json")

    def manifest(self, **kw):
        doc = {
            "id": self.id, "handle": "liniya__sporta",
            "postType": "reel", "publishAt": "2026-11-14T12:30:00+03:00",
            "approved": True, "publicContent": True,
            "text": "Текст о тренировке",
            "media": [{"type": "video", "url": "https://cdn.example.org/reel.mp4"}],
            "coverUrl": "https://cdn.example.org/cover.jpg",
            "collaborators": ["@coach", "https://www.instagram.com/trainer_one/"],
            "shouldShareToFeed": True,
        }
        doc.update(kw)
        return doc

    def save(self, document=None):
        self.json.write_text(json.dumps(document or self.manifest(), ensure_ascii=False), encoding="utf-8")

    def test_read_valid_approved_month_and_collabs(self):
        self.save()
        posts = load_calendar(self.root)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["collaborators"], ["coach", "trainer_one"])
        self.assertEqual(posts[0]["publishAt"], datetime(2026, 11, 14, 9, 30, tzinfo=timezone.utc))

    def test_draft_is_not_published(self):
        self.save(self.manifest(approved=False, publicContent=False))
        self.assertEqual(load_calendar(self.root), [])

    def test_public_content_and_approval_required(self):
        self.save(self.manifest(publicContent=False))
        with self.assertRaisesRegex(CalendarError, "publicContent"):
            load_calendar(self.root)
        self.save(self.manifest(approved="true"))
        with self.assertRaises(CalendarError):
            load_calendar(self.root)

    def test_invalid_date_and_wrong_folder(self):
        self.save(self.manifest(publishAt="2026-12-14T12:30:00+03:00"))
        with self.assertRaisesRegex(CalendarError, "folder month"):
            load_calendar(self.root)
        with self.assertRaises(CalendarError):
            _when("2026-11-14T12:30:00Z")
        with self.assertRaises(CalendarError):
            _when("2026-11-44T12:30:00+03:00")

    def test_bad_media_and_unsupported_props(self):
        edits = [
            {"media": [{"type": "video", "url": "https://cdn.example.org/reel.webm"}]},
            {"media": [{"type": "video", "url": "https://drive.google.com/a.mp4"}]},
            {"media": [{"type": "image", "url": "https://cdn.example.org/a.png"}]},
            {"coverUrl": "https://cdn.example.org/cover.png"},
            {"collaborators": ["coach", "coach"]},
            {"handle": "not-our-instagram"},
            {"unsafe": "field"},
            {"shouldShareToFeed": "yes"},
            {"postType": "story", "text": "caption"},
            {"postType": "carousel"},
        ]
        for changes in edits:
            with self.subTest(changes=changes):
                with self.assertRaises(CalendarError):
                    validate_manifest(self.manifest(**changes), Path("calendar/instagram/2026-11") / self.json.name)

    def test_all_four_formats(self):
        docs = [
            self.manifest(postType="reel"),
            self.manifest(postType="photo", media=[{"type": "image", "url": "https://cdn.example.org/a.jpg"}],
                          coverUrl=None, collaborators=[], shouldShareToFeed=True),
            self.manifest(postType="story", text="", media=[{"type": "image", "url": "https://cdn.example.org/a.jpeg"}],
                          coverUrl=None, collaborators=[], shouldShareToFeed=True),
            self.manifest(postType="carousel", media=[
                {"type": "image", "url": "https://cdn.example.org/a.jpg"},
                {"type": "video", "url": "https://cdn.example.org/b.mp4"},
            ], coverUrl=None, collaborators=[], shouldShareToFeed=True),
        ]
        for obj in docs:
            if obj["postType"] != "reel":
                obj.pop("shouldShareToFeed")
            with self.subTest(kind=obj["postType"]):
                result = validate_manifest(obj, Path("calendar/instagram/2026-11") / self.json.name)
                self.assertEqual(result["postType"], obj["postType"])

    def test_duplicate_ids_rejected_across_months(self):
        self.save()
        other = self.root / "calendar" / "instagram" / "2026-12"
        other.mkdir()
        (other / self.json.name).write_text(json.dumps(self.manifest(publishAt="2026-12-14T12:30:00+03:00")))
        with self.assertRaisesRegex(CalendarError, "Duplicate calendar ID"):
            load_calendar(self.root)

    def test_candidate_early_window_and_no_duplicates(self):
        self.save()
        job = load_calendar(self.root)[0]
        due = job["publishAt"]
        self.assertIsNone(find_candidate([job], self.root, due - MAX_EARLY - timedelta(seconds=1)))
        self.assertEqual(find_candidate([job], self.root, due - MAX_EARLY), job)
        self.assertEqual(find_candidate([job], self.root, due + MAX_LATE), job)
        receipt = self.root / "results/scheduled/instagram" / (self.id + ".json")
        receipt.parent.mkdir(parents=True)
        receipt.write_text('{"status":"submission_started"}')
        self.assertIsNone(find_candidate([job], self.root, due + timedelta(seconds=1)))

    def test_publisher_reel_with_collaborators_and_cover(self):
        self.save()
        doc = load_calendar(self.root)[0]
        client = FakeMeta()
        media_id = publish_via_meta(client, doc)
        self.assertEqual(media_id, "18180000000000000")
        self.assertTrue(client.verified)
        body = client.calls[0][2]
        self.assertEqual(body["media_type"], "REELS")
        self.assertEqual(json.loads(body["collaborators"]), ["coach", "trainer_one"])
        self.assertEqual(body["cover_url"], "https://cdn.example.org/cover.jpg")
        self.assertEqual(body["share_to_feed"], "true")
        self.assertTrue(client.calls[-1][1].endswith("/media_publish"))

    def test_publisher_single_photo(self):
        self.save(self.manifest(postType="photo", media=[{"type": "image", "url": "https://cdn.example.org/a.jpg"}],
                                coverUrl=None, collaborators=[], shouldShareToFeed=True))
        doc = load_calendar(self.root)[0]
        fake = FakeMeta()
        publish_via_meta(fake, doc)
        self.assertEqual(fake.containers, 1)
        self.assertEqual(fake.calls[0][2]["image_url"], "https://cdn.example.org/a.jpg")

    def test_publisher_story_and_carousel(self):
        self.save(self.manifest(postType="story", media=[{"type": "video", "url": "https://cdn.example.org/a.mp4"}],
                                coverUrl=None, collaborators=[], text=""))
        fake = FakeMeta()
        publish_via_meta(fake, load_calendar(self.root)[0])
        self.assertEqual(fake.calls[0][2]["media_type"], "STORIES")
        self.assertIn("video_url", fake.calls[0][2])
        self.save(self.manifest(postType="carousel", media=[
            {"type": "image", "url": "https://cdn.example.org/a.jpg"},
            {"type": "video", "url": "https://cdn.example.org/b.mp4"},
        ], coverUrl=None, collaborators=[]))
        fake = FakeMeta()
        publish_via_meta(fake, load_calendar(self.root)[0])
        self.assertEqual(fake.containers, 3)
        self.assertEqual(fake.calls[0][2]["is_carousel_item"], "true")
        self.assertEqual(fake.calls[2][2]["media_type"], "VIDEO")
        parent = [req for req in fake.calls if req[0]=="POST" and req[1].endswith("/media")][-1][2]
        self.assertEqual(parent["media_type"], "CAROUSEL")
        self.assertEqual(parent["children"], "12001,12002")

    def test_no_network_when_not_due(self):
        self.save()
        now = datetime(2026, 11, 14, 5, 0, tzinfo=timezone.utc)
        self.assertIsNone(find_candidate(load_calendar(self.root), self.root, now))


if __name__ == "__main__":
    unittest.main()
