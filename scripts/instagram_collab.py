"""Safe, opt-in Instagram Reels Collab publisher via the official Meta Graph API.

This does NOT use Buffer credentials. It never publishes without an explicitly
approved request and a matching durable GitHub Actions reservation.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .validate_social import safe_public_media_url

ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "requests" / "instagram-meta"
TRANSIENT_RESULTS = ROOT / "instagram-meta-results"
RECEIPTS = ROOT / "results" / "instagram-meta"
PRIMARY_HANDLE = "liniya__sporta"
MAX_COLLABORATORS = 3
JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")
USERNAME = re.compile(r"^[A-Za-z0-9_.]{1,30}$")
GRAPH_VERSION = re.compile(r"^v[0-9]{1,2}\.[0-9]{1,2}$")


class CollabError(ValueError):
    """Expected validation, readiness or publishing error without credentials."""


def normalize_username(raw: str) -> str:
    if not isinstance(raw, str):
        raise CollabError("Each collaborator must be an Instagram username or profile URL")
    username = raw.strip()
    if username.startswith("https://"):
        parsed = urlsplit(username)
        if parsed.hostname not in {"instagram.com", "www.instagram.com"} or parsed.port not in {None, 443}:
            raise CollabError("Collaborator URLs must use https://www.instagram.com/<username>/")
        segments = [part for part in parsed.path.split("/") if part]
        if len(segments) != 1 or parsed.username or parsed.password:
            raise CollabError("Collaborator URL must point to a single Instagram profile")
        username = segments[0]
    else:
        username = username.lstrip("@")
    if not USERNAME.fullmatch(username) or username.startswith(".") or username.endswith(".") or ".." in username:
        raise CollabError("Invalid Instagram collaborator username")
    return username.lower()


def normalize_collaborators(values: object) -> list[str]:
    if not isinstance(values, list) or not (1 <= len(values) <= MAX_COLLABORATORS):
        raise CollabError("Provide 1-3 collaborator usernames or profile links")
    normalized = [normalize_username(value) for value in values]
    if len(normalized) != len(set(normalized)):
        raise CollabError("Duplicate Instagram collaborator")
    if PRIMARY_HANDLE in normalized:
        raise CollabError("The publishing account cannot be its own collaborator")
    return normalized


def validate_job(job: object, filename: str) -> dict:
    if not isinstance(job, dict):
        raise CollabError("Request must be a JSON object")
    allowed = {
        "id", "type", "handle", "postType", "approved", "publicContent",
        "text", "media", "coverUrl", "collaborators", "shouldShareToFeed",
    }
    extra = set(job) - allowed
    if extra:
        raise CollabError("Unsupported fields: " + ", ".join(sorted(extra)))
    job_id = job.get("id")
    if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id) or filename != job_id + ".json":
        raise CollabError("Request id must match its filename and be 8-128 safe characters")
    if job.get("type") != "instagram-reel" or job.get("postType") != "reel":
        raise CollabError("Only an Instagram Reel is supported on this route")
    if job.get("handle") != PRIMARY_HANDLE:
        raise CollabError("The only authorized Instagram account is @" + PRIMARY_HANDLE)
    if job.get("approved") is not True or job.get("publicContent") is not True:
        raise CollabError("Explicit approved=true and publicContent=true are required")
    media = job.get("media")
    if (not isinstance(media, list) or len(media) != 1
            or not isinstance(media[0], dict) or set(media[0]) != {"type", "url"}
            or media[0].get("type") != "video" or not safe_public_media_url(media[0].get("url"))):
        raise CollabError("Reel requires exactly one public HTTPS video in media[]")
    cover = job.get("coverUrl")
    if cover is not None and not safe_public_media_url(cover):
        raise CollabError("coverUrl must be a public HTTPS image URL")
    caption = job.get("text", "")
    if not isinstance(caption, str) or len(caption) > 2200:
        raise CollabError("text must be a string up to 2200 characters")
    share = job.get("shouldShareToFeed", True)
    if not isinstance(share, bool):
        raise CollabError("shouldShareToFeed must be boolean")
    return {
        "id": job_id,
        "video_url": media[0]["url"],
        "cover_url": cover,
        "caption": caption,
        "share_to_feed": share,
        "collaborators": normalize_collaborators(job.get("collaborators")),
    }


def load_job(job_path: str | Path, root: Path = ROOT) -> dict:
    path = Path(job_path)
    if path.is_absolute():
        raise CollabError("Request path must be relative")
    allowed_dir = root / "requests" / "instagram-meta"
    target = root / path
    if path.parent.as_posix() != "requests/instagram-meta":
        raise CollabError("Request must be in requests/instagram-meta/")
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 128_000:
        raise CollabError("Request file is missing, a symlink, or too large")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CollabError("Request is not valid UTF-8 JSON") from exc
    return validate_job(payload, target.name)


class MetaClient:
    def __init__(self, access_token: str, ig_user_id: str, *,
                 graph_version: str = "v26.0", opener=urlopen, sleeper=time.sleep):
        if not isinstance(access_token, str) or not access_token.strip():
            raise CollabError("META_IG_ACCESS_TOKEN is not configured")
        if not re.fullmatch(r"[0-9]{5,30}", str(ig_user_id)):
            raise CollabError("META_IG_USER_ID must be a numeric Instagram professional account ID")
        if not GRAPH_VERSION.fullmatch(graph_version):
            raise CollabError("Invalid Meta Graph API version")
        self._token = access_token
        self.ig_user_id = str(ig_user_id)
        self._base = "https://graph.facebook.com/" + graph_version + "/"
        self._opener = opener
        self._sleep = sleeper

    def _api(self, method: str, resource: str, fields: dict | None = None) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_/,]+", resource):
            raise CollabError("Invalid Meta API resource")
        endpoint = self._base + resource
        if method == "GET" and fields:
            endpoint += "?" + urlencode(fields)
        body = urlencode(fields).encode("utf-8") if method == "POST" and fields is not None else None
        request = Request(endpoint, data=body, method=method, headers={
            "Authorization": "Bearer " + self._token,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        })
        try:
            with self._opener(request, timeout=45) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                error = json.loads(exc.read().decode("utf-8")).get("error", {})
                code = error.get("code", "unknown")
                message = str(error.get("message", "Meta rejected the request"))
            except (UnicodeError, ValueError, AttributeError):
                code, message = "unknown", "Meta rejected the request"
            raise CollabError("Meta API HTTP " + str(exc.code) + " code=" + str(code) +
                              ": " + message.replace(self._token, "[REDACTED]")) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise CollabError("Meta API transport failed: " +
                              str(exc).replace(self._token, "[REDACTED]")) from None
        except (UnicodeError, ValueError) as exc:
            raise CollabError("Meta API did not return valid JSON") from exc
        if not isinstance(result, dict) or result.get("error"):
            raise CollabError("Meta API returned an error response")
        return result

    def verify_account(self) -> dict:
        profile = self._api("GET", self.ig_user_id, {"fields": "id,username"})
        if str(profile.get("id")) != self.ig_user_id or str(profile.get("username", "")).lower() != PRIMARY_HANDLE:
            raise CollabError("Meta token does not point to @" + PRIMARY_HANDLE + "; publish blocked")
        return {"id": self.ig_user_id, "username": PRIMARY_HANDLE}

    @staticmethod
    def create_fields(job: dict) -> dict[str, str]:
        fields = {
            "media_type": "REELS",
            "video_url": job["video_url"],
            "caption": job["caption"],
            "share_to_feed": "true" if job["share_to_feed"] else "false",
            "collaborators": json.dumps(job["collaborators"], ensure_ascii=False, separators=(",", ":")),
        }
        if job["cover_url"]:
            fields["cover_url"] = job["cover_url"]
        return fields

    def publish_reel(self, job: dict, *, attempts: int = 40, interval_seconds: int = 15) -> dict:
        self.verify_account()
        created = self._api("POST", self.ig_user_id + "/media", self.create_fields(job))
        container_id = str(created.get("id", ""))
        if not re.fullmatch(r"[0-9]+", container_id):
            raise CollabError("Meta did not return a media container ID; manual review required")
        for attempt in range(attempts):
            state = self._api("GET", container_id, {"fields": "status_code,status"})
            status = str(state.get("status_code", "")).upper()
            if status == "FINISHED":
                break
            if status in {"ERROR", "EXPIRED"}:
                raise CollabError("Meta media processing failed (" + status + "); manual review required")
            if attempt < attempts - 1:
                self._sleep(interval_seconds)
        else:
            raise CollabError("Meta container is not ready; do not retry without manual reconciliation")
        published = self._api("POST", self.ig_user_id + "/media_publish", {"creation_id": container_id})
        media_id = str(published.get("id", ""))
        if not re.fullmatch(r"[0-9]+", media_id):
            raise CollabError("Publish returned no media ID; manual reconciliation required")
        return {
            "published_media_id": media_id,
            "creation_id": container_id,
            "collaborator_invites": "requested; acceptance unverified",
        }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2 or argv[0] not in {"validate", "check", "publish"}:
        print("Usage: python -m scripts.instagram_collab <validate|check|publish> requests/instagram-meta/<id>.json")
        return 2
    phase, request_path = argv
    try:
        job = load_job(request_path)
        if phase == "validate":
            print("VALID Instagram Collab request: " + job["id"] + "; no API calls or publishing")
            return 0
        client = MetaClient(
            os.environ.get("META_IG_ACCESS_TOKEN", ""),
            os.environ.get("META_IG_USER_ID", ""),
            graph_version=os.environ.get("META_GRAPH_VERSION", "v26.0"),
        )
        if phase == "check":
            account = client.verify_account()
            print("META_READY @" + account["username"] + "; no publication performed")
            return 0
        marker_path = RECEIPTS / (job["id"] + ".json")
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if (marker.get("status") != "submission_started"
                or not os.environ.get("GITHUB_RUN_ID")
                or marker.get("run_id") != os.environ["GITHUB_RUN_ID"]
                or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
                or os.environ.get("GITHUB_REF") != "refs/heads/main"):
            raise CollabError("GitHub Actions reservation does not match this authorized run")
        result = client.publish_reel(job)
        TRANSIENT_RESULTS.mkdir(parents=True, exist_ok=True)
        (TRANSIENT_RESULTS / (job["id"] + ".json")).write_text(
            json.dumps({"ok": True, "id": job["id"], "result": result}) + "\n", encoding="utf-8")
        print("META_PUBLISHED id=" + result["published_media_id"] + "; collaborator acceptance pending")
        return 0
    except (CollabError, OSError, ValueError, TypeError) as exc:
        print("::error::Instagram Collab: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
