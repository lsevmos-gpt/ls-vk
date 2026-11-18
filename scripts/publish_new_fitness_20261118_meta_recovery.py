"""Single approved immediate recovery for missed New Fitness Reel, direct Meta Graph API only.
Never resubmit after uncertain provider outcome. Every reservation and receipt is durable.
"""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from scripts.instagram_collab import MetaClient

ROOT=Path(__file__).resolve().parents[1]
JOB="new-fitness-20261118-1830"
REQ=ROOT/"requests/campaigns/new-fitness-20261118-1830.json"
TRIGGER=ROOT/"requests/campaigns/new-fitness-20261118-1830-meta-release.json"
QA=ROOT/"results/verification/new-fitness-20261118-1830.json"
RESULT=ROOT/"results/campaigns/new-fitness-20261118-1830-meta.json"
SCHEDULED=ROOT/"results/scheduled/instagram/new-fitness-20261118-1830.json"
VIDEO=ROOT/"media/new-fitness-20261118-1830-reel-1080x1920.mp4"
COVER=ROOT/"media/new-fitness-20261118-1830-cover-meta.jpg"
RAW="https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/"
VIDEO_SHA="5321de6d1f92bd548f5912bce9fdd1971f5e9ead32213daee3282e582606b868"
COVER_4K_SHA="058eb6d440a4c712336a6a6c16c3164f430945c458d30259b6cd04ab1f5716b4"
COVER_JPG_SHA="6d3c5b22fde6821840c2534bafbf41ce07d19985f06759c730e62f4229f2e1c4"
COLLABS=["katia_shap","sir_ena06","_alie_13_"]
REQUESTED=["katia_shap","sir_ena06","_alie_13_","pisareva.jump.simf"]

def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

def git(*args):
    p=subprocess.run(["git",*args],cwd=ROOT,text=True,capture_output=True,timeout=120)
    if p.returncode:
        raise RuntimeError("GIT_"+args[0]+"_FAILED "+(p.stderr or p.stdout)[-350:])

def checkpoint(data,initial=False):
    data["updatedAtUTC"]=datetime.now(timezone.utc).isoformat()
    RESULT.parent.mkdir(parents=True,exist_ok=True)
    with RESULT.open("x" if initial else "w",encoding="utf8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
        f.write("\n")
    git("add","--",str(RESULT.relative_to(ROOT)))
    git("commit","-m","New Fitness Meta "+data["status"]+" [skip ci]")
    for attempt in range(8):
        try:
            git("pull","--rebase","origin","main")
            git("push","origin","HEAD:main")
            return
        except RuntimeError:
            if attempt==7:
                raise
            time.sleep(attempt+2)

def main():
    if not (
        os.getenv("GITHUB_REPOSITORY")=="lsevmos-gpt/ls-vk"
        and os.getenv("GITHUB_REF")=="refs/heads/main"
        and os.getenv("GITHUB_EVENT_NAME")=="push"
        and os.getenv("GITHUB_ACTOR")=="lsevmos-gpt"
        and str(os.getenv("GITHUB_RUN_ID","")).isdigit()
    ):
        raise RuntimeError("UNAUTHORIZED_GITHUB_CONTEXT")

    git("pull","--ff-only","origin","main")
    if RESULT.exists() or SCHEDULED.exists():
        print("NEW_FITNESS_META_PRIOR_RECEIPT_EXISTS_NO_DUPLICATE",flush=True)
        return
    req=json.loads(REQ.read_text("utf8"))
    trigger=json.loads(TRIGGER.read_text("utf8"))
    qa=json.loads(QA.read_text("utf8"))
    if not (
        req.get("id")==JOB
        and req.get("approved") is True
        and req.get("authorizedByUser") is True
        and req.get("publicContent") is True
        and req.get("publishNow") is False
        and req.get("publishAt")=="2026-11-18T18:30:00+03:00"
        and req.get("sourceSHA256")==VIDEO_SHA
        and req.get("coverSHA256")==COVER_4K_SHA
        and req.get("collaboratorsRequested")==REQUESTED
        and isinstance(req.get("caption"),str) and len(req["caption"])<=2200
        and "23 ноября" in req["caption"]
        and trigger.get("id")==JOB
        and trigger.get("publishNow") is True
        and trigger.get("authorizedByUser") is True
        and trigger.get("userConfirmedMissingFromInstagram") is True
        and trigger.get("route")=="DIRECT_META_GRAPH_API_GITHUB_ACTIONS"
        and trigger.get("collaborators")==COLLABS
        and qa.get("id")==JOB and qa.get("ok") is True
        and qa.get("stagingOnly") is True and qa.get("published") is False
        and qa.get("sourceSha256")==VIDEO_SHA
        and qa.get("videoSha256")==VIDEO_SHA
        and qa.get("videoBytes")==35095341
        and qa.get("videoResolution")=="1080x1920"
        and qa.get("videoFps")==25
        and qa.get("videoStreamUnchanged") is True
        and qa.get("coverOriginalSha256")==COVER_4K_SHA
        and qa.get("coverMetaSha256")==COVER_JPG_SHA
        and VIDEO.is_file() and COVER.is_file()
        and VIDEO.stat().st_size==35095341
        and sha(VIDEO)==VIDEO_SHA and sha(COVER)==COVER_JPG_SHA
    ):
        raise RuntimeError("NEW_FITNESS_APPROVAL_OR_MEDIA_HASH_MISMATCH")
    for url in (RAW+VIDEO.name,RAW+COVER.name):
        with urlopen(Request(url,method="HEAD",headers={"User-Agent":"Liniya-Sporta-Meta-20261118"}),timeout=60) as resp:
            if resp.status!=200:
                raise RuntimeError("APPROVED_MEDIA_URL_NOT_READY")
    client=MetaClient(os.environ["META_IG_ACCESS_TOKEN"],os.environ["META_IG_USER_ID"],graph_version="v26.0")
    client.verify_account()
    git("config","user.name","ls-new-fitness-meta-publisher")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    d={
        "id":JOB,"provider":"instagram_meta_graph_api","account":"liniya__sporta",
        "videoSha256":VIDEO_SHA,"coverMetaSha256":COVER_JPG_SHA,
        "videoResolution":"1080x1920","runId":os.environ["GITHUB_RUN_ID"],
        "requestedReleaseAt":"2026-11-18T18:30:00+03:00",
        "recoveryRequestedAfterMissedSchedule":True,
        "collaboratorsRequested":REQUESTED,
        "collaboratorsSubmitted":COLLABS,
        "fourthCollaboratorNotSubmitted":"pisareva.jump.simf",
        "status":"submission_reserved_before_meta_api","creationId":None,
        "publishedMediaId":None,"noRetries":True,
        "createdAtUTC":datetime.now(timezone.utc).isoformat()
    }
    checkpoint(d,initial=True)
    try:
        fields={
            "media_type":"REELS","video_url":RAW+VIDEO.name,
            "cover_url":RAW+COVER.name,"caption":req["caption"],
            "share_to_feed":"true",
            "collaborators":json.dumps(COLLABS,ensure_ascii=False,separators=(",",":"))
        }
        result=client._api("POST",client.ig_user_id+"/media",fields)
        creation_id=str(result.get("id") or "")
        if not creation_id.isdecimal():
            raise RuntimeError("META_CREATION_ID_MISSING_DO_NOT_RETRY")
        d.update(status="meta_container_created",creationId=creation_id)
        checkpoint(d)
        for attempt in range(65):
            stat=client._api("GET",creation_id,{"fields":"status_code,status"})
            code=str(stat.get("status_code","")).upper()
            if code=="FINISHED":
                break
            if code in ("ERROR","EXPIRED"):
                raise RuntimeError("META_MEDIA_PROCESSING_"+code)
            if attempt<64:
                time.sleep(12)
        else:
            raise RuntimeError("META_PROCESSING_TIMEOUT_MANUAL_RECONCILIATION")
        d["status"]="meta_publish_call_started"
        checkpoint(d)
        publication=client._api("POST",client.ig_user_id+"/media_publish",{"creation_id":creation_id})
        pid=str(publication.get("id") or "")
        if not pid.isdecimal():
            raise RuntimeError("META_PUBLISH_ID_NOT_CONFIRMED")
        d.update(status="meta_api_published_readback_pending",
                 publishedMediaId=pid,collaboratorInvites="requested_acceptance_unverified")
        checkpoint(d)
        for attempt in range(8):
            try:
                detail=client._api("GET",pid,{"fields":"id,permalink,media_type,username"})
                if str(detail.get("id"))==pid and detail.get("permalink"):
                    d.update(status="published_readback_confirmed",
                             permalink=detail["permalink"],
                             mediaType=detail.get("media_type"),
                             username=detail.get("username"))
                    break
            except Exception as exc:
                d["readbackErrorClass"]=type(exc).__name__
            if attempt<7:
                time.sleep(5)
        checkpoint(d)
        print("NEW_FITNESS_META_PUBLICATION",json.dumps(
            {"status":d["status"],"mediaId":pid,"permalink":d.get("permalink"),
             "collaboratorsSubmitted":COLLABS},
            ensure_ascii=False),flush=True)
    except Exception as exc:
        d["status"]="manual_reconciliation_required"
        d["errorClass"]=type(exc).__name__
        d["errorMessage"]=str(exc)[:350]
        d["note"]="Meta may have accepted a container or publish. No automatic retry."
        try:
            checkpoint(d)
        except Exception as checkpoint_exc:
            print("NEW_FITNESS_META_RECEIPT_PERSIST_FAILED",type(checkpoint_exc).__name__,flush=True)
        raise

if __name__=="__main__":
    main()
