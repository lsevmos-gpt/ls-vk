"""Publish exactly three approved 27 Oct Bar Instagram Stories, once, via Meta.
Immediate owner-approved release, durable pre-provider and per-item receipts; no API posting retries.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from scripts.instagram_collab import MetaClient
from scripts.instagram_meta_calendar import publish_via_meta

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "results/verification/bar-stories-20261027-stage.json"
MANIFEST = ROOT / "media-prep/bar-stories-20261027.json"
RECEIPT = ROOT / "results/campaigns/bar-stories-20261027-instagram.json"
PREFIX = "https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/"
ORDER = ("intro-bar", "smoothie-breakfast", "pretrain")
URL_PATHS = ("media/bar-20261027-intro-meta.mp4", "media/bar-20261027-smoothie-meta.mp4", "media/bar-20261027-pretrain-meta.mp4")


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso() -> str:
    return now().isoformat()


def git(*args: str) -> None:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=100)
    if result.returncode:
        raise RuntimeError("Git " + " ".join(args[:2]) + " failed: " + (result.stderr or result.stdout)[-350:])


def check_context() -> None:
    if not (os.getenv("GITHUB_REPOSITORY") == "lsevmos-gpt/ls-vk"
            and os.getenv("GITHUB_REF") == "refs/heads/main"
            and os.getenv("GITHUB_EVENT_NAME") == "push"
            and os.getenv("GITHUB_ACTOR") == "lsevmos-gpt"
            and (os.getenv("GITHUB_RUN_ID") or "").isdecimal()):
        raise RuntimeError("Unauthorized scheduled workflow context")


def preflight() -> MetaClient:
    check_context()
    git("pull", "--ff-only", "origin", "main")
    if RECEIPT.exists():
        raise RuntimeError("Instagram already attempted; no duplicate posting")
    release = json.loads((ROOT / "requests/campaigns/bar-stories-20261027-release.json").read_text(encoding="utf-8"))
    if not (release["id"] == "bar-stories-20261027-release"
            and release["approved"] is True and release["publicContent"] is True
            and release["submitNow"] is True
            and release["instagram"] == "liniya__sporta" and release["vkGroupId"] == 48198173
            and release["stories"] == list(ORDER)):
        raise RuntimeError("Unapproved immediate release manifest")
    job = json.loads(MANIFEST.read_text())
    qa = json.loads(QA.read_text())
    if not (job["id"] == "bar-stories-20261027"
            and job["approved"] is True and job["publicContent"] is True
            and job["publishMode"] == "immediate"
            and job["instagram"] == "liniya__sporta"
            and qa["id"] == job["id"] and qa["ok"] is True
            and qa["sourceOriginalsVerified"] is True
            and qa["videoStreamsUnchangedInMeta"] is True):
        raise RuntimeError("Manifest/QA mismatch")
    if [x["id"] for x in job["sequence"]] != list(ORDER):
        raise RuntimeError("Original story order changed")
    if [x["id"] for x in qa["sequence"]] != list(ORDER):
        raise RuntimeError("Prepared story order changed")
    for approved, staged, rel in zip(job["sequence"], qa["sequence"], URL_PATHS):
        if staged["metaPath"] != rel or staged["sourceDriveSHA256"] != approved["sha256"]:
            raise RuntimeError("Wrong Meta asset mapping")
        path = ROOT / rel
        if not path.is_file() or path.is_symlink() or path.stat().st_size != staged["metaBytes"]:
            raise RuntimeError("Staged Meta asset missing or changed")
        with path.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != staged["metaSHA256"]:
                raise RuntimeError("Meta media digest mismatch: " + rel)
        if not (0 < staged["metaAudioBitrate"] <= 128000
                and staged["dimensions"] == "1080x1920" and staged["fps"] == 24):
            raise RuntimeError("Incompatible media quality")
        req = Request(PREFIX + rel, method="HEAD")
        with urlopen(req, timeout=20) as response:
            if response.status != 200:
                raise RuntimeError("Media not public to Meta")
    client = MetaClient(os.environ.get("META_IG_ACCESS_TOKEN", ""),
                        os.environ.get("META_IG_USER_ID", ""),
                        graph_version=os.environ.get("META_GRAPH_VERSION", "v26.0"))
    client.verify_account()
    return client


def checkpoint(record: dict, first: bool = False) -> None:
    record["updatedAtUTC"] = iso()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if first else "w"
    with RECEIPT.open(mode, encoding="utf-8") as out:
        json.dump(record, out, ensure_ascii=False, indent=2)
        out.write("\n")
    git("add", "--", str(RECEIPT.relative_to(ROOT)))
    git("commit", "-m", "Record 27 Oct IG Bar Stories " + record["status"] + " [skip ci]")
    for n in range(4):
        try:
            git("pull", "--rebase", "origin", "main")
            git("push", "origin", "HEAD:main")
            print("IG_CHECKPOINT", record["status"], len(record["published"]), flush=True)
            return
        except RuntimeError:
            if n == 3:
                raise
            time.sleep(1 + n)


def main() -> None:
    if RECEIPT.exists():
        print("27 Oct Instagram attempt already has receipt; no duplicate execution", flush=True)
        return
    client = preflight()
    # Approved immediate release. No previous scheduled-time barrier.
    git("pull", "--ff-only", "origin", "main")
    if RECEIPT.exists():
        print("Instagram already reserved by another runner; no action", flush=True)
        return
    git("config", "user.name", "ls-story-meta-bot")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    record = {
        "id": "bar-stories-20261027-instagram", "provider": "meta",
        "account": "liniya__sporta", "releaseMode": "immediate",
        "status": "reserved_before_provider_call",
        "runId": os.environ["GITHUB_RUN_ID"], "createdAtUTC": iso(), "published": [],
        "note": "Only three explicitly approved Stories. No provider mutation retries."
    }
    checkpoint(record, first=True)
    for index, (story_id, rel) in enumerate(zip(ORDER, URL_PATHS), start=1):
        try:
            record["status"] = "submission_started"
            record["attemptingIndex"] = index
            record["attemptingItem"] = story_id
            checkpoint(record)
            media_id = publish_via_meta(client, {
                "postType": "story", "media": [{"type": "video", "url": PREFIX + rel}], "text": ""
            })
            if not str(media_id).isdecimal():
                raise RuntimeError("Meta returned no numeric Media ID; outcome uncertain")
            detail = {}
            try:
                detail = client._api("GET", str(media_id), {"fields": "id,media_type,timestamp,permalink"})
            except Exception:
                pass
            record["published"].append({
                "index": index, "name": story_id, "instagramMediaId": str(media_id),
                "publishedAtUTC": iso(), "permalink": detail.get("permalink"),
                "metaReadbackConfirmed": str(detail.get("id")) == str(media_id)
            })
            record["status"] = "published" if index == 3 else "partial_published"
            record.pop("attemptingIndex", None)
            record.pop("attemptingItem", None)
            checkpoint(record)
            print("IG_STORY_PUBLISHED", index, story_id, media_id, flush=True)
            if index < 3:
                time.sleep(3)
        except Exception as exc:
            record["status"] = "manual_review_required"
            record["error"] = str(exc)[:350]
            record["note"] = "Uncertain/rejected submission; DO NOT REPLAY. Read platform before any other attempt."
            try:
                checkpoint(record)
            except Exception as log_exc:
                print("Failed to save final receipt; prior attempt reservation retained:", log_exc, file=sys.stderr)
            raise
    print("INSTAGRAM_3_BAR_STORIES_PUBLISHED", json.dumps(record["published"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("::error::IG_BAR_20261027 " + str(exc)[:450], file=sys.stderr)
        raise SystemExit(1)
