"""One-time 4 Nov 2026 18:30 MSK yoga Reel via native Meta collaboration.

The parent video container is created only after 18:00 MSK, with @sir_ena06
in Meta's native collaborators parameter.  Exactly one media publish attempt
is allowed. A durable GitHub receipt precedes every Meta mutation.
No VK publication in this job.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, urlopen

from scripts.instagram_collab import MetaClient, load_job

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "requests/campaigns/yoga-reel-20261104-1830.json"
COLLAB = ROOT / "requests/instagram-meta/yoga-reel-20261104-1830-sirena06.json"
QA = ROOT / "results/verification/yoga-reel-20261103-2k.json"
VIDEO = ROOT / "media/yoga-reel-20261103-2k-ig-vk.mp4"
COVER = ROOT / "media/yoga-reel-20261103-meta-cover.jpg"
RECEIPT = ROOT / "results/instagram-meta/yoga-reel-20261104-1830-sirena06.json"
RAW = "https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/"
START_CONTAINER = dt.datetime(2026, 11, 4, 15, 0, tzinfo=dt.timezone.utc)  # 18:00 MSK
PUBLISH_AT = dt.datetime(2026, 11, 4, 15, 30, tzinfo=dt.timezone.utc)     # 18:30 MSK
DEADLINE = dt.datetime(2026, 11, 4, 15, 45, tzinfo=dt.timezone.utc)       # 18:45 MSK
EXPECTED_SOURCE_SHA = "9f30f07afe04ddc881e390a8c54c6e055ed4745ce1d6e5dda72798d0c9aa9028"
EXPECTED_COVER_PNG_SHA = "e9dea808b97a2b32605242c2b3bcc290c5d7125dc1667dce9d0d1a73de18824a"
EXPECTED_COLLAB = "sir_ena06"

def now():
    return dt.datetime.now(dt.timezone.utc)

def iso():
    return now().isoformat()

def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT,
                       capture_output=True, text=True, timeout=105)
    if p.returncode:
        raise RuntimeError("Git " + " ".join(args[:2]) + " error: " + (p.stderr or p.stdout)[-350:])

def sha256(path: Path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def wait_until(target):
    while now() < target:
        time.sleep(max(0.2, min((target - now()).total_seconds(), 15)))

def checkpoint(data: dict, first=False):
    data["updatedAtUTC"] = iso()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    with RECEIPT.open("x" if first else "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    git("add", "--", str(RECEIPT.relative_to(ROOT)))
    git("commit", "-m", "Record one Yoga Nov04 18:30 Meta native-collab Reel " + data["status"] + " [skip ci]")
    for i in range(8):
        try:
            git("pull", "--rebase", "origin", "main")
            git("push", "origin", "HEAD:main")
            print("YOGA_META_RECEIPT", data["status"], flush=True)
            return
        except RuntimeError:
            if i == 7:
                raise
            time.sleep(i + 1)

def check_head(url):
    if not url.startswith(RAW) or not url.endswith((".mp4", ".jpg")):
        raise RuntimeError("Unexpected media host or suffix")
    with urlopen(Request(url, method="HEAD", headers={"User-Agent": "Liniya-Sporta-Yoga-QA/1"}),
                 timeout=50) as response:
        if response.status != 200:
            raise RuntimeError("Media not reachable by Meta (HTTP " + str(response.status) + ")")

def preflight():
    if (os.getenv("GITHUB_REPOSITORY") != "lsevmos-gpt/ls-vk"
            or os.getenv("GITHUB_REF") != "refs/heads/main"
            or os.getenv("GITHUB_EVENT_NAME") != "schedule"
            or not os.getenv("GITHUB_RUN_ID", "").isdecimal()):
        raise RuntimeError("Unauthorized scheduled repository/ref/event")
    if now() > DEADLINE:
        raise RuntimeError("18:30 MSK release window closed, DO NOT PUBLISH LATE")
    git("pull", "--ff-only", "origin", "main")
    if RECEIPT.exists():
        print("YOGA_META_ALREADY_RESERVED_OR_PUBLISHED_NO_REPLAY", flush=True)
        return None
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    qa = json.loads(QA.read_text(encoding="utf-8"))
    job = load_job(str(COLLAB.relative_to(ROOT)))
    frozen = json.loads((ROOT / "requests/staging/yoga-reel-20261103.json").read_text(encoding="utf-8"))
    if not (
        release["id"] == "yoga-reel-20261104-1830"
        and release["postType"] == "reel"
        and release["approved"] is True
        and release["publicContent"] is True
        and release["scheduledFor"] == "2026-11-04T18:30:00+03:00"
        and release["instagram"]["account"] == "liniya__sporta"
        and release["instagram"]["collaborators"] == [EXPECTED_COLLAB]
        and release["instagram"]["nativeInviteRequired"] is True
        and release["sourceDriveFileId"] == "1P4g1twKNQJwKneQqLwEzWhzwnae8QSdx"
        and release["sourceSHA256"] == EXPECTED_SOURCE_SHA
        and release["vk"]["status"] == "blocked_pending_verified_vk_native_coauthor"
        and release["vk"]["mayPostWithoutNativeCoauthor"] is False
        and job["id"] == "yoga-reel-20261104-1830-sirena06"
        and job["collaborators"] == [EXPECTED_COLLAB]
        and job["share_to_feed"] is True
        and job["caption"] == release["caption"] == frozen["caption"]
        and job["video_url"] == RAW + str(VIDEO.relative_to(ROOT))
        and job["cover_url"] == RAW + str(COVER.relative_to(ROOT))
        and qa["id"] == "yoga-reel-20261103"
        and qa["ok"] is True
        and qa["stagingOnly"] is True
        and qa["published"] is False
        and qa["sourceDriveFileId"] == release["sourceDriveFileId"]
        and qa["sourceSHA256"] == EXPECTED_SOURCE_SHA
        and qa["sourceBytes"] == 466126262
        and qa["videoPath"] == str(VIDEO.relative_to(ROOT))
        and qa["videoResolution"] == "1440x2560"
        and abs(float(qa["videoFps"]) - 25.0) < 0.1
        and qa["videoCodec"] == "h264"
        and qa["audioCodec"] == "aac"
        and qa["audioRate"] == 48000
        and 8_000_000 < qa["videoBitrate"] < 25_000_000
        and 1_000_000 < qa["videoBytes"] < 95_000_000
        and qa["coverMetaPath"] == str(COVER.relative_to(ROOT))
        and qa["coverOriginalSHA256"] == EXPECTED_COVER_PNG_SHA
        and qa["coverJpegQuality"] == 100
        and qa["collaboratorInstagram"] == EXPECTED_COLLAB
        and qa["instagramAccount"] == "liniya__sporta"
    ):
        raise RuntimeError("Approval / 2K source / exact caption / cover / native collaborator mismatch")
    if (not VIDEO.is_file() or VIDEO.is_symlink() or VIDEO.stat().st_size != qa["videoBytes"]
            or sha256(VIDEO) != qa["videoSHA256"]):
        raise RuntimeError("Verified 2K video unavailable or changed")
    if (not COVER.is_file() or COVER.is_symlink()
            or sha256(COVER) != qa["coverMetaSHA256"]):
        raise RuntimeError("Verified approved Meta cover unavailable or changed")
    fields = MetaClient.create_fields(job)
    if (fields.get("media_type") != "REELS"
            or json.loads(fields.get("collaborators", "[]")) != [EXPECTED_COLLAB]
            or fields.get("share_to_feed") != "true"
            or fields.get("cover_url") != job["cover_url"]
            or fields.get("video_url") != job["video_url"]
            or fields.get("caption") != frozen["caption"]):
        raise RuntimeError("Native Meta collaborator/caption not present in POST fields")
    check_head(job["video_url"])
    check_head(job["cover_url"])
    client = MetaClient(os.getenv("META_IG_ACCESS_TOKEN", ""),
                        os.getenv("META_IG_USER_ID", ""),
                        graph_version=os.getenv("META_GRAPH_VERSION", "v26.0"))
    client.verify_account()
    print("YOGA_2K_COVER_NATIVE_COLLAB_CAPTION_READINESS_VERIFIED_NO_POST", flush=True)
    return client, job, qa, fields

def main():
    if RECEIPT.exists():
        print("YOGA_META_PRIOR_RECEIPT_EXISTS_NO_REPEAT", flush=True)
        return
    checked = preflight()
    if checked is None:
        return
    client, job, qa, fields = checked
    wait_until(START_CONTAINER)
    if now() > DEADLINE:
        raise RuntimeError("Missed 18:30 publication window before Meta container")
    git("pull", "--ff-only", "origin", "main")
    if RECEIPT.exists():
        print("Another worker reserved Yoga Reel; DO NOT REPOST", flush=True)
        return
    git("config", "user.name", "ls-yoga-reel-native-meta-once")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    record = {
        "id": job["id"],
        "account": "liniya__sporta",
        "platform": "instagram-meta",
        "type": "REELS",
        "scheduledAt": "2026-11-04T18:30:00+03:00",
        "approvedCover": str(COVER.relative_to(ROOT)),
        "videoPath": str(VIDEO.relative_to(ROOT)),
        "videoSHA256": sha256(VIDEO),
        "videoResolution": "1440x2560",
        "caption": job["caption"],
        "nativeCollaboratorInvited": EXPECTED_COLLAB,
        "collaborationStatus": "NOT_YET_INVITED",
        "status": "reserved_before_any_provider_mutation",
        "runId": os.getenv("GITHUB_RUN_ID"),
        "createdAtUTC": iso(),
        "noRetries": True,
    }
    checkpoint(record, first=True)
    try:
        record["status"] = "container_create_call_started"
        checkpoint(record)
        result = client._api("POST", client.ig_user_id + "/media", fields)
        container_id = str(result.get("id", ""))
        if not container_id.isdecimal():
            raise RuntimeError("Meta did not return container ID. Manual reconciliation required.")
        record.update(
            status="container_created",
            creationId=container_id,
            collaborationStatus="native_invitation_requested_in_container_fields",
        )
        checkpoint(record)
        for i in range(105):
            state = client._api("GET", container_id, {"fields": "status_code,status"})
            code = str(state.get("status_code", "")).upper()
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED", "PUBLISHED"):
                raise RuntimeError("Meta media container error: " + code)
            if now() > DEADLINE:
                raise RuntimeError("Meta 2K Reel not processed within publication window")
            if i < 104:
                time.sleep(10)
        else:
            raise RuntimeError("Meta 2K processing timeout, do not retry")
        record["status"] = "container_ready"
        record["readyAtUTC"] = iso()
        checkpoint(record)
        wait_until(PUBLISH_AT)
        if now() > DEADLINE:
            raise RuntimeError("Missed the latest allowed Instagram publishing time")
        record["status"] = "publish_call_started"
        record["publishAttemptUTC"] = iso()
        checkpoint(record)
        published = client._api("POST", client.ig_user_id + "/media_publish", {"creation_id": container_id})
        media_id = str(published.get("id", ""))
        if not media_id.isdecimal():
            raise RuntimeError("Meta media_publish returned no ID; DO NOT RETRY")
        record.update(
            status="published_meta_id_received",
            mediaId=media_id,
            publishedAtUTC=iso(),
            collaborationStatus="native_invitation_requested; acceptance_not_confirmed",
        )
        checkpoint(record)
        try:
            readback = client._api("GET", media_id, {"fields": "id,permalink,media_type,timestamp"})
            record["permalink"] = readback.get("permalink")
            record["mediaType"] = readback.get("media_type")
            record["metaTimestamp"] = readback.get("timestamp")
            record["metaReadbackConfirmed"] = (
                str(readback.get("id")) == media_id
                and readback.get("media_type") in ("VIDEO", "REELS")
            )
            record["status"] = (
                "published_readback_confirmed"
                if record["metaReadbackConfirmed"]
                else "published_readback_incomplete"
            )
        except Exception as error:
            record["metaReadbackConfirmed"] = False
            record["status"] = "published_readback_pending"
            record["readbackError"] = type(error).__name__
        checkpoint(record)
        print("YOGA_REEL_1830_META_FINAL", json.dumps({
            "mediaId": media_id,
            "permalink": record.get("permalink"),
            "status": record["status"],
            "nativeCollaborator": EXPECTED_COLLAB,
            "acceptanceConfirmed": False,
        }, ensure_ascii=False), flush=True)
    except Exception as error:
        if record.get("status") not in (
            "published_readback_confirmed", "published_readback_incomplete",
            "published_readback_pending"
        ):
            record["status"] = "manual_reconciliation_required"
            record["error"] = str(error)[:320]
            record["note"] = "A Meta mutation may have occurred; DO NOT REPLAY"
            try:
                checkpoint(record)
            except Exception as sync_error:
                print("META_RECEIPT_SYNC_FAILED", type(sync_error).__name__, file=sys.stderr)
        raise

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("::error::YOGA_META_1830 " + str(error)[:400], file=sys.stderr)
        raise SystemExit(1)
