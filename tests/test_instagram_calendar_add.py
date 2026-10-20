import unittest
from datetime import datetime, timezone
from pathlib import Path
from scripts.instagram_calendar_add import plan_from_form
from scripts.instagram_meta_calendar import CalendarError, validate_manifest


class CalendarFormTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "GITHUB_REPOSITORY": "lsevmos-gpt/ls-vk",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_ACTOR": "lsevmos-gpt",
            "GITHUB_RUN_ID": "12345678",
            "FORM_KIND": "reel",
            "FORM_TIME": "2026-11-14 12:30",
            "FORM_MEDIA_URLS": "https://cdn.example.org/demo.mp4",
            "FORM_CAPTION": "Согласованный текст",
            "FORM_COVER_URL": "https://cdn.example.org/cover.jpeg",
            "FORM_COLLABORATORS": "@coach, trainer_one",
            "FORM_SHARE_TO_FEED": "true",
            "FORM_APPROVED": "true",
            "FORM_PUBLIC": "true",
        }
        self.now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)

    def test_owner_can_schedule_month_ahead_without_meta(self):
        path, doc = plan_from_form(self.env, now=self.now)
        self.assertEqual(path.parent, Path("calendar/instagram/2026-11"))
        self.assertEqual(doc["approved"], True)
        self.assertEqual(doc["publishAt"], "2026-11-14T12:30:00+03:00")
        self.assertEqual(doc["collaborators"], ["@coach", "trainer_one"])
        self.assertIsNotNone(validate_manifest(doc, path))

    def test_reject_wrong_owner_and_wrong_branch(self):
        for change in [{"GITHUB_ACTOR": "stranger"},
                       {"GITHUB_REF": "refs/heads/development"},
                       {"GITHUB_REPOSITORY": "stranger/fork"},
                       {"GITHUB_EVENT_NAME": "push"}]:
            with self.subTest(change=change), self.assertRaises(CalendarError):
                plan_from_form({**self.env, **change}, now=self.now)

    def test_reject_non_public_or_unapproved(self):
        for k in ["FORM_APPROVED", "FORM_PUBLIC"]:
            with self.subTest(key=k), self.assertRaises(CalendarError):
                plan_from_form({**self.env, k: "false"}, now=self.now)

    def test_reject_expired_and_invalid_dates(self):
        for text in ["2026-10-01 12:00", "tomorrow 12:00", "2027-12-03 12:00"]:
            with self.subTest(value=text), self.assertRaises(CalendarError):
                plan_from_form({**self.env, "FORM_TIME": text}, now=self.now)

    def test_add_carousel_with_two_assets(self):
        doc_env = {**self.env, "FORM_KIND": "carousel", "FORM_MEDIA_URLS": (
            "image:https://cdn.example.org/picture.jpg;video:https://cdn.example.org/video.mp4"
        ), "FORM_COLLABORATORS": "", "FORM_COVER_URL": ""}
        path, doc = plan_from_form(doc_env, now=self.now)
        self.assertEqual(doc["postType"], "carousel")
        self.assertEqual(len(doc["media"]), 2)
        self.assertEqual(doc["media"][1]["type"], "video")
        self.assertIsNotNone(validate_manifest(doc, path))

    def test_no_reel_field_for_story(self):
        doc_env = {**self.env, "FORM_KIND": "story", "FORM_MEDIA_URLS": "https://cdn.example.org/story.jpg",
                   "FORM_CAPTION": "", "FORM_COLLABORATORS": "", "FORM_COVER_URL": ""}
        path, doc = plan_from_form(doc_env, now=self.now)
        self.assertNotIn("shouldShareToFeed", doc)
        self.assertEqual(doc["postType"], "story")
        self.assertIsNotNone(validate_manifest(doc, path))

    def test_video_reel_without_collaborators_allowed(self):
        env = {**self.env, "FORM_COLLABORATORS": ""}
        path, doc = plan_from_form(env, now=self.now)
        self.assertNotIn("collaborators", doc)
        self.assertIsNotNone(validate_manifest(doc, path))


if __name__ == "__main__":
    unittest.main()
