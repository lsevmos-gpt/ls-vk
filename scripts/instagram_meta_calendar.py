"""Monthly Instagram calendar publisher: one Meta API connection, no Buffer.

GitHub Actions checks the month-organized, explicitly approved public jobs.
Run is one-shot, reserve-before-publish, and never automatically retries an
uncertain Meta outcome. GitHub cron is BEST EFFORT, not a hard real-time SLA.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .instagram_collab import CollabError, MetaClient, normalize_collaborators
from .validate_social import safe_public_media_url

ROOT = Path(__file__).resolve().parents[1]
CALENDAR = Path("calendar/instagram")
RESULTS = Path("results/scheduled/instagram")
JOB_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{7,127}$")
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
MAX_EARLY = timedelta(seconds=280)
MAX_LATE = timedelta(minutes=15)
PUBLISH_TYPES = {"reel", "photo", "carousel", "story"}
MAX_CAPTION = 2200
OWNER = "lsevmos-gpt"
ACCOUNT = "liniya__sporta"


class CalendarError(ValueError):
    pass


def _when(value: object) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+03:00", value
    ):
        raise CalendarError("publishAt must be YYYY-MM-DDTHH:MM:SS+03:00 (Simferopol / Moscow)")
    try:
        date = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CalendarError("Invalid publishAt date or time") from exc
    return date.astimezone(timezone.utc)


def _media(item: object) -> dict:
    if (not isinstance(item, dict) or set(item) != {"type", "url"}
            or item["type"] not in {"image", "video"}
            or not safe_public_media_url(item["url"])):
        raise CalendarError("Every media item requires type=image|video and a public HTTPS url")
    ext = urlsplit(item["url"]).path.lower().rsplit(".", 1)[-1]
    if item["type"] == "image" and ext not in {"jpg", "jpeg"}:
        raise CalendarError("Meta images must be public .jpg/.jpeg files")
    if item["type"] == "video" and ext not in {"mp4", "mov"}:
        raise CalendarError("Meta videos must be public .mp4/.mov files")
    return {"type": item["type"], "url": item["url"]}


def validate_manifest(doc: object, path: Path, *, permit_draft: bool = True) -> dict | None:
    if not isinstance(doc, dict):
        raise CalendarError("Calendar job must be a JSON object")
    accepted = {
        "id", "handle", "postType", "publishAt", "text", "media",
        "coverUrl", "collaborators", "shouldShareToFeed", "approved", "publicContent",
    }
    unknown = set(doc) - accepted
    if unknown:
        raise CalendarError("Unknown fields: " + ", ".join(sorted(unknown)))
    job_id = doc.get("id")
    if (not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id)
            or path.name != job_id + ".json"):
        raise CalendarError("id must be 8-128 lowercase safe characters and match the filename")
    if not MONTH.fullmatch(path.parent.name):
        raise CalendarError("Calendar files must be in a YYYY-MM folder")
    if doc.get("handle") != ACCOUNT:
        raise CalendarError("Only Instagram @" + ACCOUNT + " is authorized")
    publish_at = _when(doc.get("publishAt"))
    if path.parent.name != publish_at.astimezone(timezone(timedelta(hours=3))).strftime("%Y-%m"):
        raise CalendarError("Calendar folder month does not match publishAt")
    approved = doc.get("approved") is True
    if not approved:
        if doc.get("approved") is not False or not permit_draft:
            raise CalendarError("Job must explicitly have approved=true or approved=false")
        return None
    if doc.get("publicContent") is not True:
        raise CalendarError("Approved post must have publicContent=true; repository is PUBLIC")
    post_type = doc.get("postType")
    if post_type not in PUBLISH_TYPES:
        raise CalendarError("postType must be reel, photo, carousel, or story")
    media = doc.get("media")
    if not isinstance(media, list) or not media:
        raise CalendarError("Media array required")
    media = [_media(m) for m in media]
    n = len(media)
    if post_type == "reel" and (n != 1 or media[0]["type"] != "video"):
        raise CalendarError("Reel requires one video")
    if post_type == "photo" and (n != 1 or media[0]["type"] != "image"):
        raise CalendarError("Photo post requires one JPEG")
    if post_type == "story" and n != 1:
        raise CalendarError("Story requires one image or video")
    if post_type == "carousel" and not (2 <= n <= 10):
        raise CalendarError("Carousel requires 2-10 image/video assets")
    caption = doc.get("text", "")
    if not isinstance(caption, str) or len(caption) > MAX_CAPTION:
        raise CalendarError("Caption must be <=2200 characters")
    if post_type == "story" and caption:
        raise CalendarError("Stories via API have no caption or clickable link stickers")
    cover = doc.get("coverUrl")
    if cover is not None:
        if (post_type != "reel" or not safe_public_media_url(cover)
                or urlsplit(cover).path.lower().rsplit(".", 1)[-1] not in {"jpg", "jpeg"}):
            raise CalendarError("coverUrl only supported for Reels with a public JPEG")
    raw_collabs = doc.get("collaborators", [])
    if not isinstance(raw_collabs, list) or len(raw_collabs) > 3:
        raise CalendarError("collaborators must be a list of up to three accounts")
    try:
        collabs = normalize_collaborators(raw_collabs) if raw_collabs else []
    except CollabError as exc:
        raise CalendarError(str(exc)) from exc
    if collabs and post_type != "reel":
        raise CalendarError("Collaborators currently validated only for Reels")
    share = doc.get("shouldShareToFeed", True)
    if not isinstance(share, bool):
        raise CalendarError("shouldShareToFeed must be boolean")
    if post_type != "reel" and "shouldShareToFeed" in doc:
        raise CalendarError("shouldShareToFeed only applies to Reels")
    return {
        "id": job_id, "source_path": str(path.as_posix()), "postType": post_type,
        "publishAt": publish_at, "text": caption, "media": media,
        "coverUrl": cover, "collaborators": collabs, "shouldShareToFeed": share,
    }


def load_calendar(root: Path = ROOT) -> list[dict]:
    folder = root / CALENDAR
    jobs: list[dict] = []
    seen: set[str] = set()
    if not folder.exists():
        return jobs
    for path in sorted(folder.glob("*/*.json")):
        relative = path.relative_to(root)
        if path.is_symlink() or path.stat().st_size > 128_000:
            raise CalendarError("Untrusted calendar file: " + str(relative))
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise CalendarError("Invalid JSON: " + str(relative)) from exc
        job_id = doc.get("id") if isinstance(doc, dict) else None
        if job_id in seen:
            raise CalendarError("Duplicate calendar ID: " + str(job_id))
        seen.add(job_id)
        try:
            job = validate_manifest(doc, relative)
        except CalendarError as exc:
            raise CalendarError(str(relative) + ": " + str(exc)) from exc
        if job:
            jobs.append(job)
    jobs.sort(key=lambda job: (job["publishAt"], job["id"]))
    return jobs


def find_candidate(jobs: list[dict], root: Path, now: datetime) -> dict | None:
    now = now.astimezone(timezone.utc)
    for job in jobs:
        marker = root / RESULTS / (job["id"] + ".json")
        if marker.exists():
            continue
        if job["publishAt"] <= now + MAX_EARLY:
            return job
        break
    return None


def run_git(root: Path, *args: str) -> None:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True,
                            text=True, timeout=75, check=False)
    if result.returncode:
        raise CalendarError("Git commit/push failed; do not publish. Reconcile the queue.")


def record(root: Path, job: dict, state: str, *, run_id: str, media_id: str | None = None,
           note: str = "") -> Path:
    receipt_path = root / RESULTS / (job["id"] + ".json")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "id": job["id"], "status": state, "source": job["source_path"],
        "publishAtUTC": job["publishAt"].isoformat(),
        "runId": run_id, "updatedAtUTC": datetime.now(timezone.utc).isoformat(),
        "note": note,
    }
    if media_id:
        rec["instagramMediaId"] = media_id
    receipt_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_git(root, "add", "--", str(receipt_path.relative_to(root)))
    run_git(root, "commit", "-m", "Instagram calendar " + job["id"] + ": " + state + " [skip ci]")
    run_git(root, "pull", "--rebase", "origin", "main")
    run_git(root, "push", "origin", "HEAD:main")
    return receipt_path


def await_ready(client: MetaClient, container_id: str, *, attempts: int = 45,
                interval: int = 12) -> None:
    for i in range(attempts):
        outcome = client._api("GET", container_id, {"fields": "status_code,status"})
        status = str(outcome.get("status_code", "")).upper()
        if status == "FINISHED":
            return
        if status in {"ERROR", "EXPIRED", "PUBLISHED"}:
            raise CalendarError("Meta container status " + status + "; manual review required")
        if i < attempts - 1:
            client._sleep(interval)
    raise CalendarError("Media processing timeout; manual review required")


def create_container(client: MetaClient, fields: dict) -> str:
    response = client._api("POST", client.ig_user_id + "/media", fields)
    ident = str(response.get("id", ""))
    if not ident.isdecimal():
        raise CalendarError("Meta returned no valid container ID")
    return ident


def publish_via_meta(client: MetaClient, job: dict) -> str:
    """Call only after durable reservation is committed. No auto retries."""
    client.verify_account()
    kind, media = job["postType"], job["media"]
    caption = job["text"]
    if kind == "reel":
        fields = {
            "media_type": "REELS", "video_url": media[0]["url"], "caption": caption,
            "share_to_feed": "true" if job["shouldShareToFeed"] else "false",
        }
        if job["coverUrl"]:
            fields["cover_url"] = job["coverUrl"]
        if job["collaborators"]:
            fields["collaborators"] = json.dumps(job["collaborators"], separators=(",", ":"))
        parent = create_container(client, fields)
        await_ready(client, parent)
    elif kind == "photo":
        parent = create_container(client, {"image_url": media[0]["url"], "caption": caption})
        await_ready(client, parent)
    elif kind == "story":
        single = media[0]
        fields = {"media_type": "STORIES", ("image_url" if single["type"] == "image" else "video_url"): single["url"]}
        parent = create_container(client, fields)
        await_ready(client, parent)
    elif kind == "carousel":
        child_ids = []
        for item in media:
            fields = {
                "is_carousel_item": "true",
                ("image_url" if item["type"] == "image" else "video_url"): item["url"],
            }
            if item["type"] == "video":
                fields["media_type"] = "VIDEO"
            ident = create_container(client, fields)
            await_ready(client, ident)
            child_ids.append(ident)
        parent = create_container(client, {
            "media_type": "CAROUSEL", "children": ",".join(child_ids), "caption": caption,
        })
        await_ready(client, parent)
    else:
        raise CalendarError("Unsupported content type")
    result = client._api("POST", client.ig_user_id + "/media_publish", {"creation_id": parent})
    media_id = str(result.get("id", ""))
    if not media_id.isdecimal():
        raise CalendarError("Meta returned no media ID; outcome uncertain")
    return media_id


def check_environment() -> None:
    if (os.environ.get("GITHUB_REPOSITORY") != OWNER + "/ls-vk"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"):
        raise CalendarError("Calendar worker only runs on authorized GitHub main")
    event = os.environ.get("GITHUB_EVENT_NAME")
    if event not in {"schedule", "workflow_dispatch"}:
        raise CalendarError("Only approved schedule or manual dispatcher is allowed")
    if event == "workflow_dispatch" and os.environ.get("GITHUB_ACTOR") != OWNER:
        raise CalendarError("Manual dispatch restricted to owner")


def run(root: Path = ROOT, *, now_fn=None, sleep_fn=None) -> str:
    check_environment()
    now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    sleep_fn = sleep_fn or time.sleep
    run_git(root, "pull", "--ff-only", "origin", "main")
    jobs = load_calendar(root)
    candidate = find_candidate(jobs, root, now_fn())
    if candidate is None:
        print("CALENDAR_IDLE: no approved unpublished posts due in the next 280 seconds")
        return "idle"
    run_id = os.environ.get("GITHUB_RUN_ID")
    if not run_id or not run_id.isdecimal():
        raise CalendarError("Missing GitHub run ID")
    delay = (candidate["publishAt"] - now_fn()).total_seconds()
    if delay > 0:
        print("CALENDAR_WAIT id=" + candidate["id"] + " seconds=" + str(round(delay)))
        sleep_fn(delay)
    if now_fn() - candidate["publishAt"] > MAX_LATE:
        record(root, candidate, "missed_window", run_id=run_id,
               note="Too late due to runner delay. No request sent to Meta; review manually.")
        raise CalendarError("MISSED " + candidate["id"] + ": publication window expired")
    # The Meta account check is read-only and happens before reserving and committing.
    token = os.environ.get("META_IG_ACCESS_TOKEN", "")
    ig_id = os.environ.get("META_IG_USER_ID", "")
    client = MetaClient(token, ig_id, graph_version=os.environ.get("META_GRAPH_VERSION", "v26.0"))
    client.verify_account()
    receipt_path = root / RESULTS / (candidate["id"] + ".json")
    if receipt_path.exists():
        raise CalendarError("Another run reserved this job; no duplicate publication")
    record(root, candidate, "submission_started", run_id=run_id,
           note="Durable reservation before Meta mutation. Never retry same ID automatically.")
    try:
        media_id = publish_via_meta(client, candidate)
    except Exception:
        record(root, candidate, "manual_review_required", run_id=run_id,
               note="Provider may have partially published. Check Instagram manually before new attempt.")
        raise
    record(root, candidate, "published", run_id=run_id, media_id=media_id,
           note="Meta returned published media ID. Collaborator acceptance not verified.")
    print("CALENDAR_PUBLISHED id=" + candidate["id"] + " media_id=" + media_id)
    return "published"


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "validate"
    try:
        if action == "validate":
            jobs = load_calendar()
            print("CALENDAR_VALID approved_posts=" + str(len(jobs)))
            return 0
        if action == "preview":
            now = datetime.now(timezone.utc)
            jobs = load_calendar()
            remaining = [j for j in jobs if not (ROOT / RESULTS / (j["id"] + ".json")).exists()]
            for j in remaining:
                print(j["publishAt"].isoformat(), j["postType"], j["id"])
            print("CALENDAR_PREVIEW pending=" + str(len(remaining)))
            return 0
        if action == "run":
            run()
            return 0
        raise CalendarError("Usage: python -m scripts.instagram_meta_calendar <validate|preview|run>")
    except (CalendarError, CollabError, OSError, ValueError) as exc:
        print("::error::Meta calendar: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
