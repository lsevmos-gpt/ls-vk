"""Approved ONE-SHOT 30 Oct 18:00 Moscow Instagram Reel with native Meta collaborator invitation.

Never submit before time; pre-create one media container earlier. Preserve immutable
GitHub receipt BEFORE any POST request; never retry uncertain provider mutation.
No Metricool or Buffer publishing. Do not publish VK from this job.
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

ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT/"requests/campaigns/reels1-back-mobility-20261030-1800.json"
COLLAB=ROOT/"requests/instagram-meta/reels1-back-mobility-20261030-1800-uliana.json"
QA_VIDEO=ROOT/"results/verification/reels1-back-mobility-20261030-hq.json"
QA_COVER=ROOT/"results/verification/reels1-back-mobility-20261030-cover-jpeg.json"
RECEIPT=ROOT/"results/instagram-meta/reels1-back-mobility-20261030-1800-uliana.json"
VIDEO=ROOT/"media/reels1-back-mobility-20261030-ig-vk-hq.mp4"
COVER=ROOT/"media/reels1-back-mobility-20261030-approved-cover-meta.jpg"
RAW="https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/"
EARLIEST_CONTAINER=dt.datetime(2026,10,30,14,35,tzinfo=dt.timezone.utc)  # 17:35 MSK
PUBLISH_AT=dt.datetime(2026,10,30,15,0,tzinfo=dt.timezone.utc)  # 18:00 MSK
DEADLINE=dt.datetime(2026,10,30,15,15,tzinfo=dt.timezone.utc)  # 18:15 MSK
EXPECTED_SOURCE="b55744a423c4ee8685b51ad4680a6f94cfe550959e48dac814f0edd3d9ec0398"
EXPECTED_COVER_PNG="150ae03abc93260e420e4738f5f25e0dbe513b5ccb2998606f4ab8b842c3c010"
EXPECTED_COLLAB="ulianakabanova246"

def now():
    return dt.datetime.now(dt.timezone.utc)

def iso():
    return now().isoformat()

def git(*args):
    p=subprocess.run(["git",*args],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                     encoding="utf-8",timeout=100)
    if p.returncode:
        raise RuntimeError("Git "+ " ".join(args[:2])+" failed: "+p.stderr.strip()[-280:])

def digest(p:Path)->str:
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def check_media(path:Path, expected_sha:str, expected_len:int):
    if (not path.is_file() or path.is_symlink()
        or path.stat().st_size!=expected_len or digest(path)!=expected_sha):
        raise RuntimeError("Media integrity failure "+path.name)

def wait_until(target):
    while now()<target:
        seconds=(target-now()).total_seconds()
        time.sleep(max(.3,min(seconds,20)))

def push_receipt(record:dict, *,first=False):
    record["lastUpdatedAtUTC"]=iso()
    RECEIPT.parent.mkdir(parents=True,exist_ok=True)
    with RECEIPT.open("x" if first else "w",encoding="utf-8") as f:
        json.dump(record,f,ensure_ascii=False,indent=2)
        f.write("\n")
    git("add","--",str(RECEIPT.relative_to(ROOT)))
    git("commit","-m","Save unique 30 Oct 18:00 Meta Uliana collaborator Reel receipt [skip ci]")
    for i in range(7):
        try:
            git("pull","--rebase","origin","main")
            git("push","origin","HEAD:main")
            print("META_COLLAB_RECEIPT",record["status"],flush=True)
            return
        except Exception:
            if i==6:raise
            time.sleep(1.0+i)

def read_http_head(url):
    if not url.startswith(RAW):
        raise RuntimeError("Not an expected GitHub exact-media URL")
    with urlopen(Request(url,method="HEAD",headers={"User-Agent":"LS-Reel-Readiness/1"}),timeout=60) as resp:
        if resp.status!=200:
            raise RuntimeError("Meta media public HEAD returned "+str(resp.status))
        return dict(resp.headers)

def preflight():
    if (os.getenv("GITHUB_REPOSITORY")!="lsevmos-gpt/ls-vk"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("GITHUB_EVENT_NAME")!="schedule"
        or not os.getenv("GITHUB_RUN_ID","").isdigit()):
        raise RuntimeError("Unauthorized scheduled repo/ref/context")
    if now()>DEADLINE:
        raise RuntimeError("Scheduled window expired; never post unexpectedly late")
    git("pull","--ff-only","origin","main")
    if RECEIPT.exists():
        print("META_COLLAB_PRIOR_RECEIPT_EXISTS_NO_RETRY",flush=True)
        return None
    source=json.loads(RELEASE.read_text(encoding="utf-8"))
    v=json.loads(QA_VIDEO.read_text(encoding="utf-8"))
    c=json.loads(QA_COVER.read_text(encoding="utf-8"))
    job=load_job(str(COLLAB.relative_to(ROOT)))
    if not (
       source["id"]=="reels1-back-mobility-20261030-1800" and
       source["scheduledFor"]=="2026-10-30T18:00:00+03:00" and
       source["approved"] is True and source["publicContent"] is True and
       source["sourceVideo"]["originalSHA256"]==EXPECTED_SOURCE and
       source["cover"]["sha256"]==EXPECTED_COVER_PNG and
       source["instagram"]["account"]=="liniya__sporta" and
       source["instagram"]["coauthors"]==[EXPECTED_COLLAB] and
       source["instagram"]["collaboratorInvitationsRequired"] is True and
       source["caption"]==job["caption"] and
       source["cover"]["approved"] is True and
       job["id"]=="reels1-back-mobility-20261030-1800-uliana" and
       job["collaborators"]==[EXPECTED_COLLAB] and
       job["share_to_feed"] is True and
       v["ok"] is True and v["doesNotPublish"] is True and
       v["sourceSHA256"]==EXPECTED_SOURCE and
       v["sourceDriveFileId"]=="1A3nRzmTg91ZihgjAC_SGk4LedMjoH1FX" and
       v["sourceBytes"]==386016210 and
       v["outputPath"]==str(VIDEO.relative_to(ROOT)) and
       v["coverSHA256"]==EXPECTED_COVER_PNG and
       c["ok"] is True and c["doesNotPublish"] is True and
       c["sourceSHA256"]==EXPECTED_COVER_PNG and
       c["outputJPEG"]==str(COVER.relative_to(ROOT)) and
       job["video_url"]==RAW+str(VIDEO.relative_to(ROOT)) and
       job["cover_url"]==RAW+str(COVER.relative_to(ROOT)) and
       v["width"]==1080 and v["height"]==1920 and v["fps"]==25 and
       v["audioCodec"]=="aac" and v["videoCodec"]=="h264" and
       v["outputBytes"]<95000000 and c["sizeBytes"]<8000000
    ):raise RuntimeError("Non-identical approved source, caption, exact cover or native collaborator")
    check_media(VIDEO,v["outputSHA256"],v["outputBytes"])
    check_media(COVER,c["outputSHA256"],c["sizeBytes"])
    assert v["faststartVerified"] and v["color420"]
    fields=MetaClient.create_fields(job)
    if (json.loads(fields["collaborators"])!=[EXPECTED_COLLAB] or
        fields.get("media_type")!="REELS" or fields.get("share_to_feed")!="true" or
        not fields.get("cover_url")):
        raise RuntimeError("Collaborator invite not included in native Reel API")
    read_http_head(job["video_url"])
    read_http_head(job["cover_url"])
    client=MetaClient(os.getenv("META_IG_ACCESS_TOKEN",""),os.getenv("META_IG_USER_ID",""),
        graph_version=os.getenv("META_GRAPH_VERSION","v26.0"))
    client.verify_account()
    print("READ_ONLY_PREFLIGHT_META_REEL_HQ_COVER_AND_ULIANA_COLLAB_OK",flush=True)
    return client,job

def main():
    if RECEIPT.exists():
        print("Instagram 18:00 campaign already reserved; no new attempt",flush=True)
        return
    result=preflight()
    if result is None:return
    client,job=result
    wait_until(EARLIEST_CONTAINER)
    if now()>DEADLINE:raise RuntimeError("Missed approved 18:00 MSK publish window")
    # Refresh main and recheck receipt after waiting. Preflight already established exact media SHA.
    git("pull","--ff-only","origin","main")
    if RECEIPT.exists():
        print("Meta 18:00 campaign reserved elsewhere; no duplicate",flush=True)
        return
    git("config","user.name","ls-meta-collab-reels-once")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    record={
      "id":job["id"],"platform":"instagram-meta","account":"liniya__sporta",
      "type":"REELS","approvedCover":str(COVER.relative_to(ROOT)),
      "videoPath":str(VIDEO.relative_to(ROOT)),"videoSHA256":digest(VIDEO),
      "scheduledAt":"2026-10-30T18:00:00+03:00","collaboratorInvited":EXPECTED_COLLAB,
      "collaborationStatus":"NOT_YET_INVITED",
      "status":"reserved_before_any_provider_mutation","runId":os.getenv("GITHUB_RUN_ID"),
      "createdAtUTC":iso(),
      "note":"Exactly one Meta media container and one publication call. NO RETRIES after uncertain mutations."
    }
    push_receipt(record,first=True)
    try:
        if now()>DEADLINE:raise RuntimeError("Deadline expired before media container")
        record["status"]="container_create_call_started"
        push_receipt(record)  # always BEFORE non-repeatable Meta POST
        result=client._api("POST",client.ig_user_id+"/media",client.create_fields(job))
        cid=str(result.get("id",""))
        if not cid.isdigit():raise RuntimeError("Meta did not return a container ID; manual review needed")
        record.update(status="container_created",creationId=cid,
                      collaborationStatus="invitation_requested_in_container_fields")
        push_receipt(record)
        for i in range(110):
            status=client._api("GET",cid,{"fields":"status_code,status"})
            code=str(status.get("status_code","")).upper()
            if code=="FINISHED":break
            if code in {"ERROR","EXPIRED"}:raise RuntimeError("Meta media processing "+code)
            if now()>DEADLINE:raise RuntimeError("Meta Reel not ready before 18:15; no second attempt")
            time.sleep(10)
        else:raise RuntimeError("Meta media processing timeout; do not duplicate")
        record["status"]="container_ready"
        record["readyAtUTC"]=iso()
        push_receipt(record)
        wait_until(PUBLISH_AT)
        if now()>DEADLINE:raise RuntimeError("Instagram collaboration release window closed")
        record["status"]="publish_call_started"
        record["publishAttemptUTC"]=iso()
        push_receipt(record)  # before final mutation
        published=client._api("POST",client.ig_user_id+"/media_publish",{"creation_id":cid})
        media_id=str(published.get("id",""))
        if not media_id.isdigit():
            raise RuntimeError("Meta publish outcome uncertain; never repeat")
        record["mediaId"]=media_id
        record["publishedAtUTC"]=iso()
        record["collaborationStatus"]="invitation_requested; acceptance not independently confirmed"
        record["status"]="published_meta_id_received"
        push_receipt(record)
        try:
            check=client._api("GET",media_id,{"fields":"id,permalink,media_type,timestamp"})
            record["permalink"]=check.get("permalink")
            record["mediaType"]=check.get("media_type")
            record["metaReadbackConfirmed"]=str(check.get("id"))==media_id and check.get("media_type") in ("VIDEO","REELS")
            record["status"]="published_readback_confirmed" if record["metaReadbackConfirmed"] else "published_readback_incomplete"
        except Exception as error:
            record["metaReadbackConfirmed"]=False
            record["status"]="published_readback_pending"
            record["readbackError"]=str(error)[:240]
        push_receipt(record)
        print("META_REELS_20261030_PUBLISHED",json.dumps({
           k:record.get(k) for k in ("mediaId","permalink","collaboratorInvited",
                                    "collaborationStatus","metaReadbackConfirmed","status")
        },ensure_ascii=False),flush=True)
    except Exception as error:
        if record.get("status") not in {"published_readback_confirmed","published_readback_incomplete","published_readback_pending"}:
            record["status"]="manual_reconciliation_required"
            record["error"]=str(error)[:380]
            record["note"]="Provider mutation could have occurred; DO NOT RETRY from any job"
            try:push_receipt(record)
            except Exception as e:print("RECEIPT_UPDATE_FAILED_BASE_RESERVATION_RETAINED",str(e)[:120],file=sys.stderr)
        raise

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("::error::REELS1_META_ULIANA_20261030 "+str(e)[:420],file=sys.stderr)
        raise SystemExit(1)
