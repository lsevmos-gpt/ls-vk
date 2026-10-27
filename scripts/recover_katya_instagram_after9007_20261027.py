"""Second and final one-shot Meta recovery after READ-ONLY reconciliation.

The initial 10:57 MSK provider submission failed with 9007 and the 11:00 MSK
Meta /stories read-back confirmed NO story created after 10:00.
This only runs after atomic, durable GitHub attempt reservation; never retries
a failed Meta POST, nor changes the previously user-approved JPEG.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from scripts.instagram_collab import MetaClient
from scripts.instagram_meta_calendar import validate_manifest, await_ready

REPO="lsevmos-gpt/ls-vk"
ROOT=Path(__file__).resolve().parents[1]
PRIMARY="results/scheduled/instagram/ig-20261027-1000-katya-birthday-story.json"
RECEIPT="results/recovery/instagram/katya-story-meta-after9007-20261027.json"
JOB="calendar/instagram/2026-10/ig-20261027-1000-katya-birthday-story.json"
IMAGE="media/2026-10-27-katya-birthday-approved-meta-1080x1920.jpg"
IMAGE_BLOB="45f7408d7629aad1026141529d5b6d9f55eca15f"
JOB_BLOB="67665443291dad299b5da633a386636b24bad703"
IMAGE_URL="https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/"+IMAGE
UNTIL=datetime(2026,10,27,9,0,tzinfo=timezone.utc)
HEADERS={"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json","User-Agent":"ls-ig-recovery-after9007"}
TOKEN=""

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def git_blob(b:bytes)->str:
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()

def gh(method,path,payload=None):
    if path not in (PRIMARY,RECEIPT):raise RuntimeError("Non-whitelisted result path")
    headers=dict(HEADERS)
    headers["Authorization"]="Bearer "+TOKEN
    body=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
    req=Request("https://api.github.com/repos/"+REPO+"/contents/"+path,
                data=body,method=method,headers=headers)
    try:
        with urlopen(req,timeout=40) as r:return json.loads(r.read())
    except HTTPError as e:raise RuntimeError("GitHub API error "+str(e.code)+" before/after attempt; never repeat Meta") from None
    except URLError:raise RuntimeError("GitHub API unreachable; no automatic Meta retry") from None

def read(path):
    r=gh("GET",path)
    b=base64.b64decode(r.get("content",""))
    return json.loads(b),str(r.get("sha",""))

def write(doc,sha,state):
    data=(json.dumps(doc,indent=2,ensure_ascii=False)+"\n").encode()
    r=gh("PUT",RECEIPT,{"message":"Record final Katya Instagram recovery "+state+" [skip ci]",
                        "content":base64.b64encode(data).decode(),"sha":sha,"branch":"main"})
    if not r.get("commit",{}).get("sha"):raise RuntimeError("Did not confirm durable "+state)
    print("DURABLE_SECOND_RECEIPT",state,flush=True)

def check_approved():
    b=(ROOT/JOB).read_bytes()
    image=(ROOT/IMAGE).read_bytes()
    if git_blob(b)!=JOB_BLOB or git_blob(image)!=IMAGE_BLOB or not image.startswith(b"\xff\xd8\xff"):
        raise RuntimeError("Original approved media or manifest changed; STOP")
    obj=json.loads(b)
    if(obj.get("id")!="ig-20261027-1000-katya-birthday-story" or
       obj.get("approved") is not True or obj.get("publicContent") is not True or
       obj.get("handle")!="liniya__sporta" or obj.get("postType")!="story" or
       obj.get("publishAt")!="2026-10-27T10:00:00+03:00" or
       obj.get("media")!=[{"type":"image","url":IMAGE_URL}] or obj.get("text")!=""):
        raise RuntimeError("Approved Instagram job mismatched; STOP")
    validate_manifest(obj,Path(JOB),permit_draft=False)
    with urlopen(Request(IMAGE_URL,method="HEAD"),timeout=25) as r:
        if r.status!=200:raise RuntimeError("Meta asset not accessible")
    print("APPROVED_IMAGE_AND_MANIFEST_MATCH",len(image),flush=True)

def recent_stories(client):
    r=client._api("GET",client.ig_user_id+"/stories",{"fields":"id,timestamp,media_type","limit":"40"})
    count=0
    for item in r.get("data",[]):
        ts=item.get("timestamp","")
        try:t=datetime.fromisoformat(ts.replace("Z","+00:00")).astimezone(timezone.utc)
        except (ValueError,AttributeError):continue
        if t>=datetime(2026,10,27,7,0,tzinfo=timezone.utc):
            count+=1
    print("READ_ONLY_META_STORIES_AFTER_1000_MSK",count,flush=True)
    return count

def main():
    global TOKEN
    run=os.environ.get("GITHUB_RUN_ID","")
    if(os.environ.get("GITHUB_REPOSITORY")!=REPO or
       os.environ.get("GITHUB_REF")!="refs/heads/main" or
       os.environ.get("GITHUB_EVENT_NAME")!="push" or not run.isdecimal()):
        raise RuntimeError("Unapproved GitHub Actions context")
    if datetime.now(timezone.utc)>UNTIL:
        print("DEADLINE_PASSED_NO_PROVIDER_CALL");return
    TOKEN=os.getenv("GITHUB_TOKEN","")
    if not TOKEN or not os.getenv("META_IG_ACCESS_TOKEN") or not os.getenv("META_IG_USER_ID"):
        raise RuntimeError("Missing GitHub/Meta token; zero mutations")
    check_approved()
    prior,_=read(PRIMARY)
    if(prior.get("status")!="manual_review_required" or
       prior.get("attemptCount")!=1 or
       prior.get("error")!="Meta API HTTP 400 code=9007: Media ID is not available"):
        raise RuntimeError("Original failed attempt record changed; STOP")
    record,sha=read(RECEIPT)
    if(record.get("status")!="verified_rejected_9007_no_story_at_readback" or
       record.get("providerAttempts")!=0 or
       record.get("approvedImageGitBlobSHA")!=IMAGE_BLOB or
       record.get("sourceFailedRunId")!="40470253617" or
       record.get("reconciliationRunId")!="40470569214" or
       record.get("account")!="liniya__sporta"):
        print("SECOND_RECOVERY_ALREADY_HANDLED_OR_UNAUTHORIZED",record.get("status"),flush=True)
        return
    client=MetaClient(os.environ["META_IG_ACCESS_TOKEN"],os.environ["META_IG_USER_ID"],graph_version="v26.0")
    client.verify_account()
    if recent_stories(client)!=0:
        print("NEW_STORY_EXISTS_AFTER_1000_MSK_ABORT_TO_AVOID_DUPLICATE",flush=True)
        return
    record2,sha=read(RECEIPT)
    if record2.get("status")!="verified_rejected_9007_no_story_at_readback" or record2.get("providerAttempts")!=0:
        print("ANOTHER_WORKER_STARTED; NO DUPLICATE");return
    if datetime.now(timezone.utc)>UNTIL:
        print("DEADLINE_PASSED_NO_PROVIDER_CALL");return
    record2.update({"status":"provider_call_started","providerAttempts":1,
                    "runId":run,"attemptAtUTC":now(),
                    "note":"Second attempt after direct Meta reconciliation. Exactly one new container and one publish POST. No retries."})
    write(record2,sha,"provider_call_started")
    seen,_=read(RECEIPT)
    if seen.get("status")!="provider_call_started" or seen.get("runId")!=run or seen.get("providerAttempts")!=1:
        raise RuntimeError("Durable reservation not readable; STOP BEFORE META")
    print("META_SECOND_ATTEMPT_ONCE_STARTED",flush=True)
    container=None
    try:
        result=client._api("POST",client.ig_user_id+"/media",{"media_type":"STORIES","image_url":IMAGE_URL})
        container=str(result.get("id",""))
        if not container.isdecimal():raise RuntimeError("Meta returned invalid media container ID")
        print("META_CONTAINER_CREATED",container,flush=True)
        await_ready(client,container,attempts=45,interval=12)
        print("META_CONTAINER_FINISHED_WAIT_45_SECONDS",flush=True)
        time.sleep(45)
        confirm=client._api("GET",container,{"fields":"status_code,status"})
        if str(confirm.get("status_code","")).upper()!="FINISHED":
            raise RuntimeError("Container not FINISHED after settle window; no media_publish")
        posted=client._api("POST",client.ig_user_id+"/media_publish",{"creation_id":container})
        media_id=str(posted.get("id",""))
        if not media_id.isdecimal():raise RuntimeError("Meta returned no published ID")
    except Exception as exc:
        failed,latest=read(RECEIPT)
        if failed.get("runId")==run and failed.get("status")=="provider_call_started":
            failed.update({"status":"manual_review_required","error":str(exc)[:300],
                           "containerId":container,"updatedAtUTC":now(),
                           "note":"ONE SECOND ATTEMPT FAILED. NO FURTHER META POST. Manual reconciliation required."})
            try:write(failed,latest,"manual_review_required")
            except Exception as mark_error:print("MARKER_FINALIZATION_FAILED",str(mark_error),file=sys.stderr)
        raise
    readback={}
    try:readback=client._api("GET",media_id,{"fields":"id,media_type,timestamp,permalink"})
    except Exception as exc:print("META_READBACK_UNAVAILABLE",type(exc).__name__,flush=True)
    done,sha=read(RECEIPT)
    if done.get("runId")==run and done.get("status")=="provider_call_started":
        done.update({"status":"published","instagramMediaId":media_id,
                     "publishedAtUTC":now(),"containerId":container,
                     "permalink":readback.get("permalink"),
                     "metaReadbackConfirmed":str(readback.get("id",""))==media_id,
                     "note":"Meta /media_publish returned published media id. No retries."})
        try:write(done,sha,"published")
        except Exception as exc:print("PUBLISHED_BUT_RECEIPT_WRITE_FAILED",str(exc),file=sys.stderr)
    print("KATYA_STORY_PUBLISHED_META_ID",media_id,"PERMALINK",readback.get("permalink",""),flush=True)

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("::error::KATYA_AFTER_9007 "+str(e)[:320],file=sys.stderr)
        raise SystemExit(1)
