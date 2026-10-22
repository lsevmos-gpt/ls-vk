"""Publish precisely one approved second-floor Instagram Collab Reel at 18:30 MSK.
Preprocess official Meta Reel container before release time; preserve durable markers.
All credentials are read solely from GitHub Actions secrets; never leak them to logs.
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

from scripts.instagram_collab import MetaClient, load_job

ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / "requests/instagram-meta/second-floor-20261022-1830-nadir.json"
RECEIPT = ROOT / "results/instagram-meta/second-floor-20261022-1830-nadir.json"
QA = ROOT / "results/verification/second-floor-reel-20261022-prepared.json"
START = dt.datetime.fromisoformat("2026-10-22T18:20:00+03:00")
PUBLISH_AT = dt.datetime.fromisoformat("2026-10-22T18:30:00+03:00")
LATEST = dt.datetime.fromisoformat("2026-10-22T18:50:00+03:00")
VIDEO = ROOT / "media/second-floor-20261022-reel-meta-vk.mp4"
COVER = ROOT / "media/second-floor-20261022-cover-meta.jpg"
ORIGINAL_COVER = ROOT / "media/second-floor-20261022-cover-original.png"
URL_PREFIX = "https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/"

def now():
    return dt.datetime.now(dt.timezone.utc).astimezone(PUBLISH_AT.tzinfo)

def iso():
    return now().isoformat()

def run_git(*args):
    p=subprocess.run(["git", *args],cwd=ROOT,capture_output=True,text=True,timeout=90)
    if p.returncode:
        raise RuntimeError("GitHub receipt operation failed: "+p.stderr[:280])

def push_receipt(data, *, first=False):
    data["lastUpdatedAt"]=iso()
    RECEIPT.parent.mkdir(parents=True,exist_ok=True)
    if first:
        with RECEIPT.open("x",encoding="utf-8") as out:
            out.write(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
    else:
        RECEIPT.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    run_git("add",str(RECEIPT.relative_to(ROOT)))
    run_git("commit","-m","Save unique scheduled IG second-floor Collab receipt [skip ci]")
    for i in range(8):
        pull=subprocess.run(["git","pull","--rebase","origin","main"],cwd=ROOT,capture_output=True,text=True,timeout=90)
        if pull.returncode:raise RuntimeError("Could not safely rebase Instagram receipt")
        push=subprocess.run(["git","push","origin","HEAD:main"],cwd=ROOT,capture_output=True,text=True,timeout=90)
        if push.returncode==0:
            print("IG_RECEIPT_COMMITTED",data["status"],flush=True)
            return
        time.sleep(1+i)
    raise RuntimeError("Instagram receipt could not be saved to GitHub; no safe retry")

def digest(p):
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def until(target):
    while now() < target:
        time.sleep(min(15,max(0.25,(target-now()).total_seconds())))

def assert_requirements():
    if os.environ.get("GITHUB_REPOSITORY")!="lsevmos-gpt/ls-vk" or os.environ.get("GITHUB_REF")!="refs/heads/main":
        raise RuntimeError("Wrong GitHub repository or branch")
    if not (os.environ.get("GITHUB_EVENT_NAME") in {"schedule","workflow_dispatch"}):
        raise RuntimeError("Not an approved scheduled workflow")
    if not os.environ.get("GITHUB_RUN_ID","").isdigit():
        raise RuntimeError("GitHub run ID missing")
    run_git("pull","--ff-only","origin","main")
    if RECEIPT.exists():
        raise RuntimeError("This Reel is already reserved or published. Never retry.")
    qa=json.loads(QA.read_text(encoding="utf-8"))
    assert qa["ok"] is True and qa["id"]=="second-floor-reel-20261022"
    assert qa["scheduledTime"]=="2026-10-22T18:30:00+03:00"
    assert qa["originalSizeBytes"]==535389636
    assert qa["sourceGoogleDriveFileId"]=="1G7CvPTEmxeRNhyCXCj_Jv1ZhHYnlYHBg"
    assert qa["cropped"] is False and qa["alteredLogoOrFace"] is False
    for file,sha in [(VIDEO,qa["videoSHA256"]),(COVER,qa["coverJPEG_SHA256"]),(ORIGINAL_COVER,"96d00095cc4bfd8af7b6182f783fe95140c378619582af5233d6ce7c35b085ef")]:
        if not file.is_file() or file.is_symlink() or digest(file)!=sha:
            raise RuntimeError("Approved media SHA-256 is wrong: "+file.name)
    job=load_job(str(REQUEST.relative_to(ROOT)))
    if job["id"]!="second-floor-20261022-1830-nadir" or job["collaborators"]!=["kurtvafov_nadir"]:
        raise RuntimeError("Collaborator mismatch")
    if job["video_url"]!=URL_PREFIX+VIDEO.name or job["cover_url"]!=URL_PREFIX+COVER.name:
        raise RuntimeError("Unexpected public video/cover URL")
    if not job["share_to_feed"] or not job["caption"].startswith("🔥 Мы создаём возможности для вас!"):
        raise RuntimeError("The approved Reel caption or share to feed has changed")
    return job

def main():
    job=assert_requirements()
    if now()>LATEST:raise RuntimeError("Release window closed; no delayed surprise publication")
    until(START)
    client=MetaClient(os.environ.get("META_IG_ACCESS_TOKEN",""),
                      os.environ.get("META_IG_USER_ID",""),
                      graph_version=os.environ.get("META_GRAPH_VERSION","v26.0"))
    client.verify_account()   # Preflight after authorized run starts.
    run_git("config","user.name","ls-meta-reels-bot")
    run_git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    record={"id":job["id"],"platform":"instagram-meta","account":"liniya__sporta",
            "status":"reserved","runId":os.environ["GITHUB_RUN_ID"],
            "invitedCollaborator":"kurtvafov_nadir","scheduledFor":"2026-10-22T18:30:00+03:00",
            "createdAt":iso(),"mediaId":None,"note":"Do not repeat after any provider API mutation."}
    push_receipt(record,first=True)
    try:
        created=client._api("POST",client.ig_user_id+"/media",client.create_fields(job))
        container=str(created.get("id",""))
        if not container.isdigit():raise RuntimeError("Meta returned no creation id; manual review only")
        record.update(status="container_created",creationId=container)
        push_receipt(record)
        for poll in range(90):
            state=client._api("GET",container,{"fields":"status_code,status"})
            code=str(state.get("status_code","")).upper()
            if code=="FINISHED":break
            if code in {"ERROR","EXPIRED"}:raise RuntimeError("Meta media processing "+code)
            if now()>LATEST:raise RuntimeError("Meta media did not finish within the agreed window")
            time.sleep(10)
        else:raise RuntimeError("Meta media container processing timeout")
        record.update(status="container_ready",readyAt=iso())
        push_receipt(record)
        until(PUBLISH_AT)
        if now()>LATEST:raise RuntimeError("Publishing late beyond authorized window")
        record.update(status="publish_call_started",publicationAttemptAt=iso())
        push_receipt(record)
        response=client._api("POST",client.ig_user_id+"/media_publish",{"creation_id":container})
        mid=str(response.get("id",""))
        if not mid.isdigit():raise RuntimeError("Meta returned no Reel ID; outcome uncertain")
        record.update(status="published",mediaId=mid,publishedAt=iso(),
                      invitationStatus="requested; collaborator acceptance not verified")
        try:
            info=client._api("GET",mid,{"fields":"id,permalink,media_type,timestamp"})
            record["permalink"]=info.get("permalink")
            record["mediaType"]=info.get("media_type")
            record["metaReadbackConfirmed"]=str(info.get("id"))==mid
        except Exception:
            record["metaReadbackConfirmed"]=False
        push_receipt(record)
        print("SECOND_FLOOR_META_REEL_PUBLISHED",json.dumps({k:record.get(k) for k in ["mediaId","permalink","invitedCollaborator","metaReadbackConfirmed"]},ensure_ascii=False),flush=True)
    except Exception as exc:
        if record.get("status")!="published":
            record.update(status="manual_review_required",error=str(exc)[:350])
            try:push_receipt(record)
            except Exception:pass
        raise

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("::error::SECOND_FLOOR_IG_REEL "+str(exc)[:420],file=sys.stderr)
        raise SystemExit(1)
