"""One authorized, no-retry recovery for Katya's approved Instagram Story, 27 Oct 2026.

The original 10:00 Moscow calendar dispatch missed its deadline before any Meta POST.
A durable receipt already exists. This worker must atomically transition it in GitHub
BEFORE calling Meta; failure to persist stops all provider mutations.
No Buffer/Metricool. No alternative media. No other IDs.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from scripts.instagram_collab import MetaClient
from scripts.instagram_meta_calendar import validate_manifest, publish_via_meta

REPO = "lsevmos-gpt/ls-vk"
ROOT = Path(__file__).resolve().parents[1]
JOB = "ig-20261027-1000-katya-birthday-story"
CALENDAR = "calendar/instagram/2026-10/" + JOB + ".json"
RECEIPT = "results/scheduled/instagram/" + JOB + ".json"
MEDIA = "media/2026-10-27-katya-birthday-approved-meta-1080x1920.jpg"
ORIGINAL_CALENDAR_BLOB = "67665443291dad299b5da633a386636b24bad703"
ORIGINAL_MEDIA_BLOB = "45f7408d7629aad1026141529d5b6d9f55eca15f"
MEDIA_URL = "https://raw.githubusercontent.com/" + REPO + "/main/" + MEDIA
END_UTC = datetime(2026, 10, 27, 8, 30, 0, tzinfo=timezone.utc)
EXPECTED_FIRST = "recovery_authorized_no_meta_call"
API_PREFIX = "https://api.github.com/repos/" + REPO + "/contents/"
_TOKEN = ""

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()

def api(method: str, path: str, payload: dict | None = None) -> dict:
    if path not in (RECEIPT, CALENDAR):
        raise RuntimeError("GitHub path is not allowlisted")
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    request = Request(API_PREFIX + path, data=data, method=method,
        headers={"Authorization": "Bearer " + _TOKEN,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "Content-Type": "application/json",
                 "User-Agent": "ls-katya-recovery-20261027"})
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        if exc.code in (403, 409, 422):
            raise RuntimeError("GitHub content reservation blocked, HTTP " + str(exc.code) + "; no Meta request") from None
        raise RuntimeError("GitHub API failed HTTP " + str(exc.code) + "; no provider retry") from None
    except URLError:
        raise RuntimeError("GitHub API unreachable; no Meta request") from None

def fetch_state() -> tuple[dict, str]:
    item = api("GET", RECEIPT)
    encoded = item.get("content")
    if not isinstance(encoded, str):
        raise RuntimeError("Receipt content missing")
    record = json.loads(base64.b64decode(encoded))
    return record, str(item.get("sha", ""))

def update_state(record: dict, blob_sha: str, label: str) -> None:
    raw = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode()
    response = api("PUT", RECEIPT, {
        "message": "Katya Instagram one-shot recovery " + label + " [skip ci]",
        "content": base64.b64encode(raw).decode(),
        "sha": blob_sha,
        "branch": "main",
    })
    if not response.get("commit", {}).get("sha"):
        raise RuntimeError("GitHub did not confirm durable " + label + "; Meta not attempted")
    print("DURABLE_RECEIPT_COMMITTED", label, flush=True)

def verify_approved_job() -> dict:
    path = ROOT / CALENDAR
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Approved calendar file missing")
    source = path.read_bytes()
    if git_blob(source) != ORIGINAL_CALENDAR_BLOB:
        raise RuntimeError("Calendar manifest changed; blocked")
    doc = json.loads(source)
    if (doc.get("id") != JOB or doc.get("handle") != "liniya__sporta"
            or doc.get("postType") != "story" or doc.get("approved") is not True
            or doc.get("publicContent") is not True
            or doc.get("publishAt") != "2026-10-27T10:00:00+03:00"
            or doc.get("text") != ""
            or doc.get("media") != [{"type": "image", "url": MEDIA_URL}]):
        raise RuntimeError("Original image or approved intent changed")
    validated = validate_manifest(doc, Path(CALENDAR), permit_draft=False)
    file = ROOT / MEDIA
    if file.is_symlink() or not file.is_file():
        raise RuntimeError("Approved JPEG absent")
    content = file.read_bytes()
    if git_blob(content) != ORIGINAL_MEDIA_BLOB or not content.startswith(b"\xff\xd8\xff"):
        raise RuntimeError("Approved JPEG blob SHA mismatch")
    with urlopen(Request(MEDIA_URL, method="HEAD",
                         headers={"User-Agent": "ls-katya-recovery-check"}), timeout=25) as response:
        if response.status != 200:
            raise RuntimeError("Media inaccessible via HTTPS")
    print("EXACT_APPROVED_JPEG_AND_CALENDAR_VALIDATED", len(content), flush=True)
    return validated

def main() -> None:
    global _TOKEN
    run = os.environ.get("GITHUB_RUN_ID", "")
    if (os.environ.get("GITHUB_REPOSITORY") != REPO
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME") != "push"
            or not run.isdecimal()):
        raise RuntimeError("Recovery may run only for the authorized repository push")
    if datetime.now(timezone.utc) > END_UTC:
        print("RECOVERY_DEADLINE_PASSED_NO_META_CALL", flush=True)
        return
    _TOKEN = os.environ.get("GITHUB_TOKEN", "")
    if not _TOKEN:
        raise RuntimeError("GitHub token not provided; no Meta call")
    if not os.environ.get("META_IG_ACCESS_TOKEN") or not os.environ.get("META_IG_USER_ID"):
        raise RuntimeError("Meta credentials not configured; no Meta call")
    job = verify_approved_job()

    receipt, sha = fetch_state()
    if (receipt.get("id") != JOB
            or receipt.get("source") != CALENDAR
            or receipt.get("media") != MEDIA
            or receipt.get("sourceBlobSHA") != ORIGINAL_CALENDAR_BLOB
            or receipt.get("mediaBlobSHA") != ORIGINAL_MEDIA_BLOB
            or receipt.get("recoveryApproved") is not True
            or receipt.get("publishAt") != "2026-10-27T10:00:00+03:00"):
        raise RuntimeError("Durable recovery authorization mismatched; no Meta call")
    if receipt.get("status") != EXPECTED_FIRST or receipt.get("attemptCount") != 0:
        print("RECOVERY_ALREADY_RESERVED_OR_ATTEMPTED_NO_RETRY",receipt.get("status"),flush=True)
        return

    client = MetaClient(os.environ["META_IG_ACCESS_TOKEN"],
                        os.environ["META_IG_USER_ID"],
                        graph_version="v26.0")
    client.verify_account()  # read-only, before committing a provider attempt
    # Ensure no other recovery reserved it while we checked Meta:
    second, sha = fetch_state()
    if second.get("status") != EXPECTED_FIRST or second.get("attemptCount") != 0:
        print("RECOVERY_OTHER_WORKER_RESERVED_NO_DUPLICATE",flush=True)
        return
    if datetime.now(timezone.utc) > END_UTC:
        print("RECOVERY_DEADLINE_PASSED_NO_META_CALL",flush=True)
        return

    second.update({
        "status": "provider_call_started",
        "attemptCount": 1,
        "attemptRunId": run,
        "attemptAtUTC": now_iso(),
        "note": "Durably recorded one authorized Meta submission attempt BEFORE API mutation. Never retry if outcome is uncertain."
    })
    update_state(second, sha, "provider_call_started")

    # Require durable marker readback before touching Meta:
    confirmed, _ = fetch_state()
    if (confirmed.get("status") != "provider_call_started"
            or confirmed.get("attemptCount") != 1
            or confirmed.get("attemptRunId") != run):
        raise RuntimeError("Reservation readback mismatch: NO META POST ALLOWED")

    print("META_ONCE_SUBMISSION_STARTED", JOB, flush=True)
    try:
        media_id = publish_via_meta(client, job)
        if not str(media_id).isdecimal():
            raise RuntimeError("Meta returned no valid media ID; outcome uncertain")
    except Exception as exc:
        problem, new_sha = fetch_state()
        if problem.get("attemptRunId") == run and problem.get("status") == "provider_call_started":
            problem.update({
                "status": "manual_review_required",
                "error": str(exc)[:300],
                "updatedAtUTC": now_iso(),
                "note": "One attempt made; potential provider side effect. DO NOT REPLAY."
            })
            try:
                update_state(problem, new_sha, "manual_review_required")
            except Exception as receipt_error:
                print("Receipt finalization failed; initial provider_call_started reservation remains durable",
                      str(receipt_error), file=sys.stderr)
        raise

    readback = {}
    try:
        readback = client._api("GET", str(media_id),
                               {"fields": "id,media_type,timestamp,permalink"})
    except Exception as exc:
        print("MEDIA_READBACK_UNAVAILABLE_AFTER_SUCCESS", type(exc).__name__, flush=True)
    published, published_sha = fetch_state()
    if published.get("attemptRunId") == run and published.get("status") == "provider_call_started":
        published.update({
            "status": "published",
            "instagramMediaId": str(media_id),
            "publishedAtUTC": now_iso(),
            "permalink": readback.get("permalink"),
            "metaReadbackConfirmed": str(readback.get("id", "")) == str(media_id),
            "note": "Meta /media_publish returned this media ID. No retries performed."
        })
        try:
            update_state(published, published_sha, "published")
        except Exception as final_exc:
            print("PUBLISHED_BUT_RECEIPT_UPDATE_FAILED", str(final_exc), file=sys.stderr)
    print("KATYA_INSTAGRAM_PUBLISHED_ONCE media_id="+str(media_id)
          +" readback="+str(readback.get("id", "")), flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("::error::KATYA_INSTAGRAM_RECOVERY " + str(exc)[:350], file=sys.stderr)
        raise SystemExit(1)
