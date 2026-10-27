"""One-time approved 27 Oct 2026 Shpagat Reel direct Meta Collab at 19:00 Moscow.

Reserves same durable receipt used by automatic calendar, so neither path can
publish a duplicate. Cover and video URLs are fixed to user-approved media.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from scripts.instagram_collab import MetaClient, load_job

ROOT=Path(__file__).resolve().parents[1]
ID="20261027-shpagat-1900-sir-ena06"
REQUEST=ROOT/"requests/instagram-meta/20261027-shpagat-exact-1900.json"
CALENDAR=ROOT/f"calendar/instagram/2026-10/{ID}.json"
RECEIPT=ROOT/f"results/scheduled/instagram/{ID}.json"
COVER=ROOT/"media/2026-10-27-shpagat-approved-cover-meta.jpg"
VIDEO_URL="https://static.metricool.com/planner/202610/7014498-file-3201710570030047514.mp4"
COVER_URL="https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/2026-10-27-shpagat-approved-cover-meta.jpg"
PREFLIGHT=dt.datetime.fromisoformat("2026-10-27T18:52:00+03:00").timestamp()
PUBLISH=dt.datetime.fromisoformat("2026-10-27T19:00:00+03:00").timestamp()
DEADLINE=dt.datetime.fromisoformat("2026-10-27T19:12:00+03:00").timestamp()
REC=None

def iso():return dt.datetime.now(dt.timezone.utc).isoformat()
def git(*args):
    p=subprocess.run(["git",*args],cwd=ROOT,text=True,capture_output=True,timeout=90)
    if p.returncode:raise RuntimeError("GIT_PERSISTENCE_FAILED")
def persist(rec,first=False):
    rec["updatedAtUtc"]=iso()
    RECEIPT.parent.mkdir(parents=True,exist_ok=True)
    if first:
        with RECEIPT.open("x",encoding="utf-8") as f:json.dump(rec,f,indent=2,ensure_ascii=False);f.write("\n")
    else:RECEIPT.write_text(json.dumps(rec,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    git("add","--",str(RECEIPT.relative_to(ROOT)))
    git("commit","-m","Reserve/update approved shpagat Meta one-shot 19:00 [skip ci]")
    for k in range(7):
        try:
            git("pull","--rebase","origin","main")
            git("push","origin","HEAD:main")
            return
        except RuntimeError:
            if k==6:raise
            time.sleep(1.5*(k+1))
def wait_until(unix_time):
    while time.time()<unix_time:time.sleep(min(15.0,unix_time-time.time()))
def small_get(url,header):
    req=urllib.request.Request(url,headers={"Range":"bytes=0-2047","User-Agent":"LS-approved-reels-preflight/1.0"})
    with urllib.request.urlopen(req,timeout=40) as r: start=r.read(2048)
    if not start.startswith(header):raise RuntimeError("PUBLIC_MEDIA_SIGNATURE_INVALID")
def validate_and_reserve():
    if (os.environ.get("GITHUB_REPOSITORY")!="lsevmos-gpt/ls-vk"
            or os.environ.get("GITHUB_REF")!="refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME")!="push"):
        raise RuntimeError("UNAUTHORIZED_RUN")
    if time.time()>DEADLINE:raise RuntimeError("APPROVED_WINDOW_CLOSED")
    git("pull","--ff-only","origin","main")
    if RECEIPT.exists():raise RuntimeError("EXISTING_RECEIPT_NO_DUPLICATE")
    req=load_job(str(REQUEST.relative_to(ROOT)))
    c=json.loads(CALENDAR.read_text(encoding="utf-8"))
    if (req["id"]!="20261027-shpagat-exact-1900"
       or req["video_url"]!=VIDEO_URL or req["cover_url"]!=COVER_URL
       or req["collaborators"]!=["sir_ena06"] or not req["share_to_feed"]
       or req["caption"]!=c["text"]
       or c["id"]!=ID or c["publishAt"]!="2026-10-27T19:00:00+03:00"
       or c["approved"] is not True or c["collaborators"]!=["sir_ena06"]
       or c["media"]!=[{"type":"video","url":VIDEO_URL}]
       or c["coverUrl"]!=COVER_URL):
        raise RuntimeError("APPROVED_META_REQUEST_MISMATCH")
    if hashlib.sha256(COVER.read_bytes()).hexdigest()!="abb51cc603d2b8497d316b0ea081a9948bc075434554ea6230e75504a160aff5":
        raise RuntimeError("APPROVED_COVER_SHA256_MISMATCH")
    small_get(VIDEO_URL,b"\x00\x00") # ISO-BMFF file starts with a 32-bit box length.
    small_get(COVER_URL,b"\xff\xd8\xff")
    return req
def main():
    global REC
    job=validate_and_reserve()
    client=MetaClient(os.environ.get("META_IG_ACCESS_TOKEN",""),os.environ.get("META_IG_USER_ID",""),
                      graph_version=os.environ.get("META_GRAPH_VERSION","v26.0"))
    client.verify_account()
    git("config","user.name","ls-meta-collab-shpagat")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    REC={"id":ID,"status":"reserved_for_exact_time_meta","platform":"instagram-meta",
         "scheduledFor":"2026-10-27T19:00:00+03:00","runId":os.environ["GITHUB_RUN_ID"],
         "invitedCollaborator":"sir_ena06","source":"requests/instagram-meta/20261027-shpagat-exact-1900.json",
         "note":"Authorised direct Meta Collab, one-shot. This receipt blocks calendar duplicate."}
    persist(REC,first=True)
    try:
        wait_until(PREFLIGHT)
        if time.time()>DEADLINE:raise RuntimeError("META_APPROVED_WINDOW_CLOSED")
        fields=MetaClient.create_fields(job)
        created=client._api("POST",client.ig_user_id+"/media",fields)
        container=str(created.get("id",""))
        if not container.isdecimal():raise RuntimeError("META_CREATION_OUTCOME_UNCERTAIN")
        REC.update(status="container_created",containerId=container)
        persist(REC)
        for k in range(90):
            result=client._api("GET",container,{"fields":"status_code,status"})
            st=str(result.get("status_code","")).upper()
            if st=="FINISHED":break
            if st in ("ERROR","EXPIRED","PUBLISHED"):raise RuntimeError("META_CONTAINER_"+st)
            if time.time()>DEADLINE:raise RuntimeError("META_CONTAINER_PROCESSING_LATE")
            time.sleep(8)
        else:raise RuntimeError("META_CONTAINER_NOT_READY")
        REC.update(status="container_ready",readyAtUtc=iso())
        persist(REC)
        wait_until(PUBLISH)
        if time.time()>DEADLINE:raise RuntimeError("META_PUBLICATION_WINDOW_CLOSED")
        REC.update(status="publish_call_started",publishAttemptAtUtc=iso())
        persist(REC)
        result=client._api("POST",client.ig_user_id+"/media_publish",{"creation_id":container})
        mid=str(result.get("id",""))
        if not mid.isdecimal():raise RuntimeError("META_PUBLISH_OUTCOME_UNCERTAIN")
        REC.update(status="published",instagramMediaId=mid,publishedAtUtc=iso(),
                   invitationStatus="requested; collaborator acceptance not verified")
        try:
            detail=client._api("GET",mid,{"fields":"id,permalink,media_type,timestamp"})
            REC["permalink"]=detail.get("permalink")
            REC["metaReadbackConfirmed"]=str(detail.get("id"))==mid
        except Exception:REC["metaReadbackConfirmed"]=False
        persist(REC)
        print("SHPAGAT_META_PUBLISHED",json.dumps({"mediaId":mid,"permalink":REC.get("permalink"),"collaborator":"sir_ena06","readbackConfirmed":REC["metaReadbackConfirmed"]}))
    except Exception as exc:
        if REC and REC.get("status")!="published":
            REC.update(status="manual_review_required",error=str(exc)[:300],
                       note="No automatic retry. Meta outcome uncertain; reconcile before any attempt.")
            try:persist(REC)
            except Exception:pass
        raise
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("::error::SHPAGAT_META "+str(exc)[:300],file=sys.stderr)
        raise SystemExit(1)
