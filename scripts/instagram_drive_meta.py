"""Approved Google Drive video -> Instagram Meta direct upload.

Only user-approved manifests in requests/instagram-drive/ are eligible.
No media or credentials are committed to GitHub. Stories/Reels are video-only;
photos and carousels continue to use the existing Meta calendar.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from .instagram_collab import MetaClient

ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "requests/instagram-drive"
RESULTS = ROOT / "results/instagram-drive"
DRIVE_ROOT_ID = "1esCJqiZdf5f2-GGJP0UTGDZODPfp3o1c"
HANDLE = "liniya__sporta"
REPO = "lsevmos-gpt/ls-vk"
FILE_ID = re.compile(r"^[A-Za-z0-9_-]{15,100}$")
JOB_ID = re.compile(r"^[a-z][a-z0-9_-]{7,99}$")
GRAPH_VERSION = re.compile(r"^v\d{1,2}\.\d{1,2}$")
VIDEO_MAX_BYTES = {"reel": 300_000_000, "story": 100_000_000}


class DriveMetaError(ValueError):
    pass


def manifest_from_path(path: Path) -> dict:
    if path.parent.resolve() != REQUESTS.resolve() or path.is_symlink():
        raise DriveMetaError("Manifest must be a direct file in requests/instagram-drive")
    if not path.is_file() or path.stat().st_size > 16_000:
        raise DriveMetaError("Manifest missing or too large")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise DriveMetaError("Manifest must be an object")
    allowed = {"id", "handle", "postType", "driveFileId", "text", "approved",
               "publicContent", "shouldShareToFeed", "coverUrl", "collaborators"}
    if set(data) - allowed:
        raise DriveMetaError("Unsupported manifest fields")
    if not JOB_ID.fullmatch(str(data.get("id", ""))) or path.name != data["id"] + ".json":
        raise DriveMetaError("Invalid or mismatched job ID")
    if data.get("handle") != HANDLE or data.get("approved") is not True or data.get("publicContent") is not True:
        raise DriveMetaError("Instagram handle and explicit approval/publicContent required")
    if data.get("postType") not in VIDEO_MAX_BYTES:
        raise DriveMetaError("This route supports video Reels and Stories only")
    if not FILE_ID.fullmatch(str(data.get("driveFileId", ""))):
        raise DriveMetaError("Invalid Drive file ID")
    caption = data.get("text", "")
    if not isinstance(caption, str) or len(caption) > 2200:
        raise DriveMetaError("Caption must be <= 2200 characters")
    if data["postType"] == "story" and caption:
        raise DriveMetaError("Stories cannot have captions via this Meta API")
    if not isinstance(data.get("shouldShareToFeed", True), bool):
        raise DriveMetaError("shouldShareToFeed must be boolean")
    if data["postType"] == "story" and ("shouldShareToFeed" in data or "coverUrl" in data or "collaborators" in data):
        raise DriveMetaError("Story does not accept Reel-only properties")
    if "coverUrl" in data:
        u = urlsplit(data["coverUrl"])
        if (u.scheme != "https" or not u.hostname or not u.path.lower().endswith((".jpg", ".jpeg"))
                or u.username or u.password or u.fragment):
            raise DriveMetaError("Cover must be a public HTTPS JPEG URL")
    from .instagram_collab import normalize_collaborators
    collabs = data.get("collaborators", [])
    if not isinstance(collabs, list) or len(collabs) > 3:
        raise DriveMetaError("Maximum three collaborators")
    if collabs:
        normalize_collaborators(collabs)
    return data


def sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def assert_in_liniya_folder(session, headers: dict, parents: list[str]) -> None:
    """Allow approved files only within the project's Google Drive hierarchy."""
    checked = set()
    frontier = list(parents)
    for _ in range(14):
        if DRIVE_ROOT_ID in frontier:
            return
        nxt = []
        for fid in frontier:
            if fid in checked:
                continue
            checked.add(fid)
            if not FILE_ID.fullmatch(fid):
                raise DriveMetaError("Invalid parent folder")
            resp = session.get("https://www.googleapis.com/drive/v3/files/" + fid,
                               params={"fields": "id,parents", "supportsAllDrives": "true"},
                               headers=headers, timeout=35)
            resp.raise_for_status()
            nxt.extend(resp.json().get("parents") or [])
        frontier = nxt
        if not frontier:
            break
    raise DriveMetaError("The source must be inside the approved Liniya Sporta Drive root")


def download_from_drive(file_id: str, destination: Path, service_account_json: str) -> dict:
    import requests
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    if not service_account_json:
        raise DriveMetaError("Google Drive service-account secret not configured")
    try:
        account = json.loads(service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            account, scopes=["https://www.googleapis.com/auth/drive.readonly"])
        credentials.refresh(Request())
    except (ValueError, KeyError) as exc:
        raise DriveMetaError("Invalid Google Drive service-account configuration") from exc
    headers = {"Authorization": "Bearer " + credentials.token}
    with requests.Session() as session:
        meta = session.get("https://www.googleapis.com/drive/v3/files/" + file_id,
                           params={"fields": "id,name,mimeType,size,parents", "supportsAllDrives": "true"},
                           headers=headers, timeout=35)
        meta.raise_for_status()
        record = meta.json()
        if record.get("id") != file_id or record.get("mimeType") != "video/mp4":
            raise DriveMetaError("Source must be an MP4 stored in Google Drive")
        if int(record.get("size") or 0) > 1_200_000_000 or int(record.get("size") or 0) < 1_000:
            raise DriveMetaError("Source size is outside safe bounds")
        assert_in_liniya_folder(session, headers, record.get("parents") or [])
        with session.get("https://www.googleapis.com/drive/v3/files/" + file_id,
                         params={"alt": "media", "supportsAllDrives": "true"},
                         headers=headers, stream=True, timeout=(35, 180)) as response:
            response.raise_for_status()
            with destination.open("wb") as output:
                total = 0
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        total += len(chunk)
                        if total > 1_200_000_000:
                            raise DriveMetaError("Download size limit exceeded")
                        output.write(chunk)
        if destination.stat().st_size != int(record["size"]):
            raise DriveMetaError("Google Drive download incomplete")
    return {"sourceName": record.get("name", ""), "sourceBytes": destination.stat().st_size,
            "sourceSha256": sha256(destination)}


def probe(path: Path) -> dict:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,size:stream=codec_type,codec_name,width,height,avg_frame_rate,"
         "pix_fmt,sample_rate,bit_rate", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=65, check=True)
    value = json.loads(p.stdout)
    video = next((s for s in value.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in value.get("streams", []) if s.get("codec_type") == "audio"), None)
    if video is None or audio is None:
        raise DriveMetaError("Video and audio streams required")
    return {"video": video, "audio": audio, "duration": float(value["format"]["duration"])}


def render_meta_2k(source: Path, destination: Path, post_type: str) -> tuple[Path, dict]:
    """No upscale. Preserve the original byte stream if already Meta-compatible."""
    from fractions import Fraction
    meta = probe(source)
    v, a = meta["video"], meta["audio"]
    w, h = int(v["width"]), int(v["height"])
    fps = float(Fraction(v["avg_frame_rate"]))
    if not 23 <= fps <= 60 or abs(w / h - 9 / 16) > 0.014:
        raise DriveMetaError("Source fps/aspect incompatible; manual review, no cropping")
    if not (3 <= meta["duration"] <= (60 if post_type == "story" else 900)):
        raise DriveMetaError("Source duration incompatible with destination")
    # Avoid a source above Meta's 25 Mb/s video limit, even if its resolution is compatible.
    # Allow headroom for variable-bitrate peaks; no artificial pixel upscaling.
    resize = w > 1440 or h > 2560
    source_average_bps = source.stat().st_size * 8 / meta["duration"]
    source_video_bps = int(v.get("bit_rate") or 0) or source_average_bps
    bitrate_too_high = source_video_bps > 23_000_000 or source_average_bps > 24_000_000
    video_ok = v["codec_name"] in ("h264", "hevc") and v.get("pix_fmt") in ("yuv420p", "yuvj420p")
    audio_ok = (a.get("codec_name") == "aac" and int(a.get("sample_rate") or 0) == 48000
                and 0 < int(a.get("bit_rate") or 0) <= 128_000)
    if (not resize and video_ok and audio_ok and not bitrate_too_high
            and source.stat().st_size <= VIDEO_MAX_BYTES[post_type]):
        return source, {"sourceResolution": f"{w}x{h}", "outputResolution": f"{w}x{h}",
                        "reencoded": False, "reason": "Original Meta-compatible video and audio"}
    command = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", str(source),
               "-map", "0:v:0", "-map", "0:a:0", "-sn", "-dn"]
    # For oversized 2K Story, reduce bitrate but keep pixels and composition.
    if resize or not video_ok or bitrate_too_high or source.stat().st_size > VIDEO_MAX_BYTES[post_type]:
        filter_ = ("scale=1440:2560:flags=lanczos,format=yuv420p"
                   if resize else "format=yuv420p")
        bitrate = "10000k" if post_type == "story" else "18000k"
        command += ["-vf", filter_, "-c:v", "libx264", "-preset", "slow",
                    "-crf", "17", "-maxrate", bitrate, "-bufsize",
                    "20000k" if post_type == "story" else "36000k"]
    else:
        command += ["-c:v", "copy"]
    if audio_ok:
        command += ["-c:a", "copy"]
    else:
        command += ["-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2"]
    command += ["-movflags", "+faststart", str(destination)]
    subprocess.run(command, timeout=2200, check=True, capture_output=True)
    out = probe(destination)
    ov = out["video"]
    if (int(ov["width"]) > 1440 or int(ov["height"]) > 2560
            or int(destination.stat().st_size) > VIDEO_MAX_BYTES[post_type]
            or (int(ov.get("bit_rate") or 0) or destination.stat().st_size * 8 / out["duration"]) > 24_000_000):
        raise DriveMetaError("Rendered media exceeds 2K or Meta size limit; publishing blocked")
    return destination, {"sourceResolution": f"{w}x{h}",
                         "outputResolution": f"{ov['width']}x{ov['height']}",
                         "reencoded": True, "reason": "Meta compatibility or 2K downscale"}


def checked_rupload_uri(value: str, version: str, container_id: str) -> str:
    target = value or f"https://rupload.facebook.com/ig-api-upload/{version}/{container_id}"
    parsed = urlsplit(target)
    if (parsed.scheme != "https" or parsed.hostname != "rupload.facebook.com"
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path != f"/ig-api-upload/{version}/{container_id}"):
        raise DriveMetaError("Unexpected Meta upload destination")
    return target


def publish_video(meta_client: MetaClient, job: dict, video_path: Path) -> str:
    import requests
    meta_client.verify_account()
    fields = {"media_type": "REELS" if job["postType"] == "reel" else "STORIES",
              "upload_type": "resumable"}
    if job["postType"] == "reel":
        fields.update({"caption": job.get("text", ""),
                       "share_to_feed": "true" if job.get("shouldShareToFeed", True) else "false"})
        if job.get("coverUrl"):
            fields["cover_url"] = job["coverUrl"]
        if job.get("collaborators"):
            fields["collaborators"] = json.dumps(job["collaborators"], ensure_ascii=False)
    result = meta_client._api("POST", meta_client.ig_user_id + "/media", fields)
    container_id = str(result.get("id", ""))
    if not container_id.isdecimal():
        raise DriveMetaError("Meta did not return a container ID; manual review required")
    version = os.environ.get("META_GRAPH_VERSION", "v26.0")
    if not GRAPH_VERSION.fullmatch(version):
        raise DriveMetaError("Invalid Graph version")
    upload_uri = checked_rupload_uri(str(result.get("uri") or ""), version, container_id)
    with video_path.open("rb") as binary:
        response = requests.post(
            upload_uri, data=binary,
            headers={"Authorization": "OAuth " + meta_client._token,
                     "offset": "0", "file_size": str(video_path.stat().st_size),
                     "Content-Type": "application/octet-stream"}, timeout=(35, 1200))
        if response.status_code >= 300:
            # Do not leak body or token from provider error response.
            raise DriveMetaError(f"Meta binary upload HTTP {response.status_code}; reconcile manually")
    for _ in range(45):
        status = meta_client._api("GET", container_id, {"fields": "status_code,status"})
        state = str(status.get("status_code", "")).upper()
        if state == "FINISHED":
            break
        if state in ("ERROR", "EXPIRED", "PUBLISHED"):
            raise DriveMetaError("Meta container status " + state + "; reconcile manually")
        time.sleep(12)
    else:
        raise DriveMetaError("Meta processing timeout; do not automatically retry")
    published = meta_client._api("POST", meta_client.ig_user_id + "/media_publish",
                                 {"creation_id": container_id})
    media_id = str(published.get("id", ""))
    if not media_id.isdecimal():
        raise DriveMetaError("Meta publishing outcome uncertain; manual review required")
    return media_id


def git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True, text=True, timeout=75)


def store_receipt(doc: dict, *, new: bool) -> None:
    destination = RESULTS / (doc["id"] + ".json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if new:
        with destination.open("x", encoding="utf-8") as out:
            json.dump(doc, out, ensure_ascii=False, indent=2)
            out.write("\n")
    else:
        destination.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git("config", "user.name", "ls-meta-drive-publisher")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "--", str(destination))
    git("commit", "-m", "Record approved Instagram Drive job " + doc["id"] + " [skip ci]")
    git("pull", "--rebase", "origin", "main")
    git("push", "origin", "HEAD:main")


def process_one(path: Path) -> None:
    job = manifest_from_path(path)
    if (RESULTS / (job["id"] + ".json")).exists():
        return
    if not os.environ.get("GITHUB_RUN_ID", "").isdecimal():
        raise DriveMetaError("GitHub Actions run ID required")
    account_token = os.environ.get("META_IG_ACCESS_TOKEN", "")
    account_id = os.environ.get("META_IG_USER_ID", "")
    service_json = os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "")
    if not service_json:
        raise DriveMetaError("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON GitHub secret is missing")
    client = MetaClient(account_token, account_id, graph_version=os.environ.get("META_GRAPH_VERSION", "v26.0"))
    # Read-only account verification before any reservation.
    client.verify_account()
    with tempfile.TemporaryDirectory(prefix="liniya-meta-") as temp:
        original = Path(temp) / "source.mp4"
        prepared = Path(temp) / "ready.mp4"
        info = download_from_drive(job["driveFileId"], original, service_json)
        candidate, media_info = render_meta_2k(original, prepared, job["postType"])
        size = candidate.stat().st_size
        receipt = {"id": job["id"], "status": "submission_started",
                   "type": job["postType"], "driveFileId": job["driveFileId"],
                   "sourceSha256": info["sourceSha256"], "sourceBytes": info["sourceBytes"],
                   "uploadSha256": sha256(candidate), "uploadBytes": size,
                   "quality": media_info, "runId": os.environ["GITHUB_RUN_ID"]}
        # Explicit durable reservation before first Meta mutation; never retry a
        # job with an existing receipt, including uncertain outcomes.
        git("pull", "--ff-only", "origin", "main")
        if (RESULTS / (job["id"] + ".json")).exists():
            raise DriveMetaError("Job is already reserved")
        store_receipt(receipt, new=True)
        try:
            media_id = publish_video(client, job, candidate)
            receipt.update({"status": "published", "instagramMediaId": media_id})
        except Exception:
            receipt.update({"status": "manual_review_required",
                            "note": "Meta may have published; verify Instagram before any new job"})
            store_receipt(receipt, new=False)
            raise
        store_receipt(receipt, new=False)
        print("INSTAGRAM_META_PUBLISHED job=" + job["id"] + " mediaId=" + media_id)


def main() -> int:
    try:
        files = sorted(REQUESTS.glob("*.json"))
        for p in files:
            manifest_from_path(p)
        if len(sys.argv) != 2 or sys.argv[1] not in {"validate", "process"}:
            raise DriveMetaError("Usage: python -m scripts.instagram_drive_meta validate|process")
        if sys.argv[1] == "validate":
            print("DRIVE_META_VALID_APPROVED_MANIFESTS=" + str(len(files)) + " (no publication)")
            return 0
        if (os.environ.get("GITHUB_REPOSITORY") != REPO
                or os.environ.get("GITHUB_REF") != "refs/heads/main"
                or os.environ.get("GITHUB_EVENT_NAME") not in {"push", "workflow_dispatch"}):
            raise DriveMetaError("Only authorized GitHub main can execute publication")
        for path in files:
            process_one(path)
        print("DRIVE_META_QUEUE_COMPLETE")
        return 0
    except Exception as exc:
        # Provider exception messages may contain request URLs or credentials;
        # intentionally emit only safe error class, not raw exceptions.
        if isinstance(exc, DriveMetaError):
            print("::error::Drive/Meta: " + str(exc), file=sys.stderr)
        else:
            print("::error::Drive/Meta failed (" + type(exc).__name__ + "); consult private logs",
                  file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
