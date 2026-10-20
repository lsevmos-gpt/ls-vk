import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs
from urllib.error import HTTPError

from scripts.instagram_collab import (
    CollabError, MetaClient, load_job, normalize_collaborators,
    normalize_username, validate_job,
)
from scripts.instagram_collab_guard import (
    APPROVAL_PHRASE, finalize, reserve,
)


def sample_job(**changes):
    job = {
        "id": "collab20261020",
        "type": "instagram-reel",
        "postType": "reel",
        "handle": "liniya__sporta",
        "approved": True,
        "publicContent": True,
        "text": "Reels caption",
        "media": [{"type": "video", "url": "https://cdn.example.com/video.mp4"}],
        "coverUrl": "https://cdn.example.com/cover.jpg",
        "collaborators": ["@partner.one", "https://www.instagram.com/partner_two/"],
        "shouldShareToFeed": True,
    }
    job.update(changes)
    return job


class FakeMeta:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, request, *, timeout):
        self.calls.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return io.BytesIO(json.dumps(item).encode())


class InstagramCollabTests(unittest.TestCase):
    def test_profile_links_and_usernames(self):
        self.assertEqual(normalize_username("https://www.instagram.com/Partner.Name/?igsh=tracking"), "partner.name")
        self.assertEqual(normalize_username(" @Partner_42 "), "partner_42")
        self.assertEqual(normalize_collaborators(["partner_42"]), ["partner_42"])

    def test_invalid_profile_or_collaborators(self):
        for value in ["http://instagram.com/someone", "https://evil.com/user", "https://www.instagram.com/p/shortcode",
                      "foo..bar", "@", "a/b"]:
            with self.subTest(value=value), self.assertRaises(CollabError):
                normalize_username(value)
        for values in [[], ["a", "a"], ["a", "b", "c", "d"], ["liniya__sporta"]]:
            with self.subTest(values=values), self.assertRaises(CollabError):
                normalize_collaborators(values)

    def test_valid_request_normalizes_collaborators(self):
        result = validate_job(sample_job(), "collab20261020.json")
        self.assertEqual(result["collaborators"], ["partner.one", "partner_two"])
        self.assertEqual(result["cover_url"], "https://cdn.example.com/cover.jpg")

    def test_reject_unsafe_request_data(self):
        edits = [
            {"approved": False},
            {"publicContent": False},
            {"handle": "wrong-account"},
            {"postType": "story"},
            {"type": "instagram"},
            {"collaborators": []},
            {"dueAt": "2026-10-21T12:00:00Z"},
            {"media": [{"type": "image", "url": "https://cdn.example.com/a.png"}]},
            {"media": [{"type": "video", "url": "https://drive.google.com/file/d/x/view"}]},
            {"coverUrl": "http://example.com/cover.jpg"},
            {"shouldShareToFeed": "true"},
        ]
        for edit in edits:
            with self.subTest(edit=edit), self.assertRaises(CollabError):
                validate_job(sample_job(**edit), "collab20261020.json")

    def test_reject_wrong_filename_and_non_request_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "requests" / "instagram-meta"
            folder.mkdir(parents=True)
            (folder / "collab20261020.json").write_text(json.dumps(sample_job()))
            self.assertEqual(load_job("requests/instagram-meta/collab20261020.json", root)["id"], "collab20261020")
            with self.assertRaises(CollabError):
                load_job("requests/instagram-meta/../collab20261020.json", root)
            with self.assertRaises(CollabError):
                load_job("requests/instagram-meta/other.json", root)

    def test_correct_meta_requests_and_no_token_in_url(self):
        fake = FakeMeta([
            {"id": "12345678", "username": "liniya__sporta"},
            {"id": "222222"},
            {"status_code": "IN_PROGRESS"},
            {"status_code": "FINISHED"},
            {"id": "333333"},
        ])
        client = MetaClient("secret-token", "12345678", opener=fake, sleeper=lambda _: None)
        result = client.publish_reel(validate_job(sample_job(), "collab20261020.json"), attempts=3, interval_seconds=0)
        self.assertEqual(result["published_media_id"], "333333")
        self.assertEqual(len(fake.calls), 5)
        post = fake.calls[1]
        self.assertTrue(post.full_url.endswith("/12345678/media"))
        self.assertNotIn("secret-token", post.full_url)
        fields = parse_qs(post.data.decode())
        self.assertEqual(fields["media_type"], ["REELS"])
        self.assertEqual(fields["share_to_feed"], ["true"])
        self.assertEqual(json.loads(fields["collaborators"][0]), ["partner.one", "partner_two"])
        self.assertEqual(fields["cover_url"], ["https://cdn.example.com/cover.jpg"])
        self.assertTrue(fake.calls[4].full_url.endswith("/12345678/media_publish"))

    def test_account_mismatch_blocks_container_creation(self):
        fake = FakeMeta([{"id": "12345678", "username": "somebody_else"}])
        client = MetaClient("secret-token", "12345678", opener=fake)
        with self.assertRaisesRegex(CollabError, "publish blocked"):
            client.publish_reel(validate_job(sample_job(), "collab20261020.json"))
        self.assertEqual(len(fake.calls), 1)

    def test_processing_failure_never_publishes(self):
        fake = FakeMeta([
            {"id": "12345678", "username": "liniya__sporta"},
            {"id": "222222"}, {"status_code": "ERROR"},
        ])
        client = MetaClient("secret-token", "12345678", opener=fake, sleeper=lambda _: None)
        with self.assertRaises(CollabError):
            client.publish_reel(validate_job(sample_job(), "collab20261020.json"))
        self.assertEqual(len(fake.calls), 3)

    def test_error_response_redacts_token(self):
        payload = json.dumps({"error": {"code": 190, "message": "invalid secret-token"}}).encode()
        fake = FakeMeta([HTTPError("https://graph.facebook.com/v26.0/me", 400, "Bad Request", {}, io.BytesIO(payload))])
        client = MetaClient("secret-token", "12345678", opener=fake)
        with self.assertRaises(CollabError) as caught:
            client.verify_account()
        self.assertNotIn("secret-token", str(caught.exception))


class InstagramCollabGuardTests(unittest.TestCase):
    def setUp(self):
        context = tempfile.TemporaryDirectory()
        self.addCleanup(context.cleanup)
        self.root = Path(context.name)
        directory = self.root / "requests" / "instagram-meta"
        directory.mkdir(parents=True)
        (directory / "collab20261020.json").write_text(json.dumps(sample_job()))

    def reserve(self, **kw):
        kwargs = dict(actor="lsevmos-gpt", event="workflow_dispatch", branch="refs/heads/main", run_id="run42")
        kwargs.update(kw)
        return reserve(self.root, "collab20261020", APPROVAL_PHRASE, **kwargs)

    def test_reserves_and_blocks_replay(self):
        self.assertTrue(self.reserve().is_file())
        with self.assertRaisesRegex(ValueError, "earlier publication"):
            self.reserve()

    def test_rejects_other_actor_or_branch(self):
        for kw in [{"actor": "other"}, {"event": "push"}, {"branch": "refs/heads/feature"}]:
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.reserve(**kw)

    def test_failed_outcome_is_manual_review(self):
        self.reserve()
        result = finalize(self.root, "collab20261020", "run42", "1")
        self.assertEqual(json.loads(result.read_text())["status"], "manual_review_required")

    def test_published_receipt_does_not_expose_credentials(self):
        self.reserve()
        outcome = self.root / "instagram-meta-results" / "collab20261020.json"
        outcome.parent.mkdir()
        outcome.write_text(json.dumps({
            "ok": True, "id": "collab20261020",
            "result": {"published_media_id": "333333", "creation_id": "222222"}
        }))
        marker = finalize(self.root, "collab20261020", "run42", "0")
        state = json.loads(marker.read_text())
        self.assertEqual(state["status"], "published")
        self.assertEqual(state["instagram_media_id"], "333333")
        self.assertNotIn("creation_id", state)


if __name__ == "__main__":
    unittest.main()
