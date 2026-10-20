"""Owner-only self-service 'Add planned Instagram post' form in GitHub Actions.

No posting or Meta token is used here. This creates only an explicitly approved,
publicly shareable calendar manifest. Posting is performed later by the calendar
worker at its configured time.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .instagram_meta_calendar import ROOT, CALENDAR, CalendarError, _when, validate_manifest

SAFE_JOB = re.compile(r"^[a-z0-9][a-z0-9._-]{7,127}$")


def plan_from_form(env: dict[str, str], now: datetime | None = None) -> tuple[Path, dict]:
    if (env.get("GITHUB_REPOSITORY") != "lsevmos-gpt/ls-vk"
            or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("GITHUB_ACTOR") != "lsevmos-gpt"):
        raise CalendarError("Only owner can register Instagram calendar posts on main")
    if env.get("FORM_APPROVED") != "true" or env.get("FORM_PUBLIC") != "true":
        raise CalendarError("Explicit approved + publicContent confirmations are required")
    post_type = env.get("FORM_KIND", "")
    if post_type not in {"reel", "photo", "story", "carousel"}:
        raise CalendarError("Unsupported content type")
    local = env.get("FORM_TIME", "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", local):
        raise CalendarError("Enter Moscow local publish time YYYY-MM-DD HH:MM")
    iso = local.replace(" ", "T") + ":00+03:00"
    date = _when(iso)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if date < now + timedelta(minutes=20) or date > now + timedelta(days=365):
        raise CalendarError("Choose a publish time between 20 minutes and 365 days ahead")
    run_id = env.get("GITHUB_RUN_ID", "")
    if not run_id.isdecimal():
        raise CalendarError("Missing GitHub run ID")
    id_ = "ig-" + date.astimezone(timezone(timedelta(hours=3))).strftime("%Y%m%d-%H%M") + "-" + run_id
    if not SAFE_JOB.fullmatch(id_):
        raise CalendarError("Invalid generated job ID")
    raw_urls = env.get("FORM_MEDIA_URLS", "").strip()
    if not raw_urls:
        raise CalendarError("Provide public media URL(s); carousel uses ; between URLs")
    urls = [x.strip() for x in raw_urls.replace("\n", ";").split(";") if x.strip()]
    if len(urls) > 10:
        raise CalendarError("At most ten assets per post")
    media = []
    for raw in urls:
        if raw.startswith("image:"):
            kind, url = "image", raw[6:]
        elif raw.startswith("video:"):
            kind, url = "video", raw[6:]
        else:
            url = raw
            extension = urlsplit(url).path.lower().rsplit(".", 1)[-1]
            kind = "video" if extension in {"mp4", "mov"} else "image"
        media.append({"type": kind, "url": url})
    collabs = [s.strip() for s in env.get("FORM_COLLABORATORS", "").split(",") if s.strip()]
    caption = env.get("FORM_CAPTION", "")
    cover = env.get("FORM_COVER_URL", "").strip()
    manifest = {
        "id": id_, "handle": "liniya__sporta", "publishAt": iso,
        "postType": post_type, "text": caption, "media": media,
        "approved": True, "publicContent": True,
    }
    if cover:
        manifest["coverUrl"] = cover
    if collabs:
        manifest["collaborators"] = collabs
    if post_type == "reel":
        manifest["shouldShareToFeed"] = env.get("FORM_SHARE_TO_FEED") == "true"
    month = iso[:7]
    relative = CALENDAR / month / (id_ + ".json")
    normalized = validate_manifest(manifest, relative, permit_draft=False)
    if normalized is None:
        raise CalendarError("Approved job validation failed")
    return relative, manifest


def main() -> int:
    try:
        relative, manifest = plan_from_form(dict(os.environ))
        path = ROOT / relative
        if path.exists():
            raise CalendarError("Calendar job already exists; no overwrite allowed")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as file:
            file.write(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        print("CALENDAR_REGISTERED id=" + manifest["id"] + " at " + manifest["publishAt"])
        return 0
    except (CalendarError, OSError, ValueError) as exc:
        print("::error::Register Instagram calendar post: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
