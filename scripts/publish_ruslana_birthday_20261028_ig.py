"""28 Oct 2026 — user-approved two-Story Meta Instagram campaign, one time.

Order is strictly intro-girls VIDEO, then Ruslana birthday PHOTO.
Date-bound, scheduled-only, reserve-before-provider, fail-closed; no retries.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from scripts.instagram_collab import MetaClient
from scripts.instagram_meta_calendar import publish_via_meta

ROOT = Path(__file__).resolve().parents[1]
QA_PATH = ROOT / "results/verification/ruslana-birthday-20261028-stage.json"
RECEIPT = ROOT / "results/campaigns/ruslana-birthday-20261028-instagram.json"
PREFIX = "https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/"
DUE = datetime(2026, 10, 28, 7, 0, 0, tzinfo=timezone.utc)  # 10:00 Moscow
MAX_LATE = timedelta(minutes=7)
STORIES = (
    ("intro-girls", "media/ruslana-20261028-intro-meta.mp4", "video"),
    ("ruslana-birthday", "media/ruslana-20261028-birthday-meta.jpg", "image"),
)
ORIGINAL_VIDEO_SHA = "3ca7cde5ca132b59e9e825e31c9a39b3a94b454c231572bd15b598b51e0a9434"
META_PHOTO_SHA = "6d521ff85441e22c5ab8248d733422f3695601b3ac778540764eecbaf872f0d6"


def utcnow():
    return datetime.now(timezone.utc)


def git(*args):
    call = subprocess.run(("git",) + args, cwd=ROOT, capture_output=True, text=True, timeout=100)
    if call.returncode:
        raise RuntimeError("git " + " ".join(args[:2]) + ": " + (call.stderr or call.stdout)[-450:])


def checkpoint(record, *, first=False):
    record["updatedAtUTC"] = utcnow().isoformat()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    with RECEIPT.open("x" if first else "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    git("add", "--", str(RECEIPT.relative_to(ROOT)))
    git("commit", "-m", "Record approved Ruslana Meta birthday sequence " + record["status"] + " [skip ci]")
    for attempt in range(4):
        try:
            git("pull", "--rebase", "origin", "main")
            git("push", "origin", "HEAD:main")
            print("RUSLANA_META_CHECKPOINT", record["status"], len(record["published"]), flush=True)
            return
        except RuntimeError:
            if attempt == 3:
                raise
            time.sleep(attempt + 1)


def assert_context():
    if not (
        os.environ.get("GITHUB_REPOSITORY") == "lsevmos-gpt/ls-vk"
        and os.environ.get("GITHUB_REF") == "refs/heads/main"
        and os.environ.get("GITHUB_EVENT_NAME") == "schedule"
        and (os.environ.get("GITHUB_RUN_ID") or "").isdecimal()
    ):
        raise RuntimeError("Denied: only scheduled GitHub main execution is authorized")


def sha256(path: Path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def preflight():
    git("pull", "--ff-only", "origin", "main")
    if RECEIPT.exists():
        print("RUSLANA_META_ALREADY_RESERVED_OR_PUBLISHED: no duplicate", flush=True)
        return None
    qa = json.loads(QA_PATH.read_text(encoding="utf-8"))
    if not (
        qa.get("id") == "ruslana-birthday-20261028-stage"
        and qa.get("status") == "files_verified"
        and qa.get("approved") is True
        and qa.get("providerCalls") == 0
        and qa.get("storyOrder") == ["intro-girls", "ruslana-birthday"]
    ):
        raise RuntimeError("Approved source QA not found/valid")
    manifest = json.loads((ROOT / "requests/staging/ruslana-birthday-20261028-stage.json").read_text(encoding="utf-8"))
    if manifest.get("approved") is not True or manifest.get("publicContent") is not True:
        raise RuntimeError("Owner approval not present")
    intro = qa["media"]["media/ruslana-20261028-intro-vk.mp4"]
    if intro["sha256"] != ORIGINAL_VIDEO_SHA:
        raise RuntimeError("Source intro SHA mismatch")
    if sha256(ROOT / "media/ruslana-20261028-birthday-meta.jpg") != META_PHOTO_SHA:
        raise RuntimeError("Birthday artwork differs from user approved")
    for _name, rel, _kind in STORIES:
        p = ROOT / rel
        if p.is_symlink() or not p.is_file() or p.stat().st_size <= 0:
            raise RuntimeError("Missing staged public media: " + rel)
        expected = qa["media"][rel]
        if p.stat().st_size != expected["bytes"] or sha256(p) != expected["sha256"]:
            raise RuntimeError("Staged media SHA/size changed: " + rel)
        req = Request(PREFIX + rel, method="HEAD")
        with urlopen(req, timeout=35) as response:
            if response.status != 200:
                raise RuntimeError("Meta public media HEAD failed: " + rel)
    client = MetaClient(
        os.environ.get("META_IG_ACCESS_TOKEN", ""),
        os.environ.get("META_IG_USER_ID", ""),
        graph_version=os.environ.get("META_GRAPH_VERSION", "v26.0"),
    )
    client.verify_account()
    print("RUSLANA_META_PREFLIGHT_PASS: two immutable public assets, account verified", flush=True)
    return client


def main():
    assert_context()
    if not (DUE - timedelta(hours=1) <= utcnow() <= DUE + MAX_LATE):
        print("RUSLANA_META_OUTSIDE_SINGLE_DATE_TIME_WINDOW", flush=True)
        return
    if RECEIPT.exists():
        print("RUSLANA_META_EXISTING_RECEIPT: do not submit", flush=True)
        return
    client = preflight()
    if client is None:
        return
    seconds = (DUE - utcnow()).total_seconds()
    if seconds > 0:
        print("RUSLANA_META_WAIT_UNTIL_10AM_MSK seconds=" + str(round(seconds)), flush=True)
        time.sleep(seconds)
    if utcnow() - DUE > MAX_LATE:
        print("RUSLANA_META_MISSED_DEADLINE: no provider submissions", flush=True)
        return
    git("pull", "--ff-only", "origin", "main")
    if RECEIPT.exists():
        print("RUSLANA_META_ALREADY_RESERVED: no duplicate", flush=True)
        return
    git("config", "user.name", "ls-ruslana-story-bot")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    record = {
        "id": "ruslana-birthday-20261028-instagram",
        "platform": "instagram",
        "provider": "meta",
        "account": "liniya__sporta",
        "scheduledAtMoscow": "2026-10-28T10:00:00+03:00",
        "stories": ["intro-girls", "ruslana-birthday"],
        "runId": os.environ["GITHUB_RUN_ID"],
        "status": "reserved_before_provider_call",
        "createdAtUTC": utcnow().isoformat(),
        "published": [],
        "note": "Exactly two owner-approved Stories. One attempt per item, no retries after uncertain Meta response.",
    }
    checkpoint(record, first=True)
    for index, (name, rel, kind) in enumerate(STORIES, start=1):
        try:
            record["attemptingIndex"] = index
            record["attemptingItem"] = name
            record["status"] = "submission_started"
            checkpoint(record)
            media_id = publish_via_meta(client, {
                "postType": "story", "text": "",
                "media": [{"type": kind, "url": PREFIX + rel}],
            })
            if not str(media_id).isdecimal():
                raise RuntimeError("Meta response missing numeric media ID; outcome uncertain")
            details = {}
            try:
                details = client._api("GET", str(media_id), {"fields": "id,media_type,timestamp,permalink"})
            except Exception as exc:
                record["readbackNote"] = "Readback unavailable (do not retry publish): " + str(exc)[:150]
            record["published"].append({
                "index": index,
                "name": name,
                "source": rel,
                "instagramMediaId": str(media_id),
                "publishedAtUTC": utcnow().isoformat(),
                "permalink": details.get("permalink"),
                "metaReadbackConfirmed": str(details.get("id")) == str(media_id),
            })
            del record["attemptingIndex"]
            del record["attemptingItem"]
            record["status"] = "published" if index == 2 else "partial_published"
            checkpoint(record)
            print("RUSLANA_INSTAGRAM_STORY_PUBLISHED", index, name, media_id, flush=True)
            if index == 1:
                time.sleep(3)
        except Exception as exc:
            record["status"] = "manual_review_required"
            record["error"] = str(exc)[:400]
            record["note"] = "Uncertain/rejected Meta response; NEVER resubmit without manual readback."
            try:
                checkpoint(record)
            except Exception as secondary:
                print("Reservation already saved; final checkpoint error", secondary, file=sys.stderr)
            raise
    print("RUSLANA_INSTAGRAM_TWO_STORIES_PUBLISHED_IN_ORDER", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("::error::RUSLANA_META_20261028 " + str(exc)[:450], file=sys.stderr)
        raise SystemExit(1)
