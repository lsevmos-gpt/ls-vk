"""One-shot approved Vlad news Reel via the SAME direct Meta Graph API route as 8 Nov TABATA, without Google Drive."""
from __future__ import annotations
import hashlib,json,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from scripts.instagram_collab import MetaClient

ROOT=Path(__file__).resolve().parents[1]
REQ=ROOT/"requests/campaigns/vlad-news-20261109.json"
QA=ROOT/"results/verification/vlad-news-20261109.json"
RESULT=ROOT/"results/campaigns/vlad-news-20261109-meta.json"
VIDEO=ROOT/"media/vlad-news-20261109-reel-1080x1920.mp4"
COVER=ROOT/"media/vlad-news-20261109-cover-meta.jpg"
RAW="https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/"
SOURCE_SHA="0ae828d45a93f1cb194294ab4c34ac60a3a91ea9785081987ea5e81d7b95ef74"
COVER_SHA="e9325f8f0df778a4ce33c99fe2d0d5dd703cae5968ed01f14c2d0941d7e657bd"

def sha(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def git(*args):
    p=subprocess.run(["git",*args],cwd=ROOT,capture_output=True,text=True,timeout=105)
    if p.returncode:raise RuntimeError("git_"+args[0]+"_failed "+(p.stderr or p.stdout)[-240:])

def checkpoint(r,initial=False):
    r["updatedAtUTC"]=datetime.now(timezone.utc).isoformat()
    RESULT.parent.mkdir(parents=True,exist_ok=True)
    with RESULT.open("x" if initial else "w",encoding="utf8") as f:
        json.dump(r,f,ensure_ascii=False,indent=2)
        f.write("\n")
    git("add","--",str(RESULT.relative_to(ROOT)))
    git("commit","-m","Vlad news Meta "+r["status"]+" [skip ci]")
    for n in range(9):
        try:
            git("pull","--rebase","origin","main")
            git("push","origin","HEAD:main")
            return
        except RuntimeError:
            if n==8:raise
            time.sleep(n+1)

def main():
    if (os.getenv("GITHUB_REPOSITORY")!="lsevmos-gpt/ls-vk"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("GITHUB_EVENT_NAME")!="push"
        or os.getenv("GITHUB_ACTOR")!="lsevmos-gpt"
        or not os.getenv("GITHUB_RUN_ID","").isdigit()):
        raise RuntimeError("unapproved_workflow_context")
    git("pull","--ff-only","origin","main")
    if RESULT.exists():
        print("VLAD_META_EXISTING_RECEIPT_NO_REPLAY",flush=True)
        return
    r=json.loads(REQ.read_text(encoding="utf8"))
    q=json.loads(QA.read_text(encoding="utf8"))
    if not (r.get("id")=="vlad-news-20261109" and r.get("approved") is True
            and r.get("publicContent") is True and r.get("publishNow") is True
            and r.get("authorizedByUser") is True
            and r.get("sourceSHA256")==SOURCE_SHA and r.get("coverSHA256")==COVER_SHA
            and r.get("instagram")=={"handle":"liniya__sporta","shareToFeed":True,"collaborators":[]}
            and r.get("vk")=={"groupId":48198173,"publishWall":True}
            and isinstance(r.get("caption"),str) and 20<len(r["caption"])<=2200
            and q.get("ok") is True and q.get("stagingOnly") is True
            and q.get("sourceSha256")==SOURCE_SHA and q.get("coverOriginalSha256")==COVER_SHA
            and q.get("videoResolution")=="1080x1920" and q.get("videoFps")==25
            and q.get("videoStreamUnchanged") is True
            and VIDEO.is_file() and q.get("videoSha256")==sha(VIDEO)
            and q.get("videoBytes")==VIDEO.stat().st_size
            and COVER.is_file() and q.get("coverMetaSha256")==sha(COVER)):
        raise RuntimeError("VLAD_APPROVED_SOURCE_CAPTION_OR_QA_MISMATCH")
    for u in (RAW+VIDEO.name,RAW+COVER.name):
        with urlopen(Request(u,method="HEAD",headers={"User-Agent":"Liniya-Sporta-Vlad-20261109"}),timeout=65) as resp:
            if resp.status!=200:raise RuntimeError("media_host_not_ready")
    client=MetaClient(os.environ["META_IG_ACCESS_TOKEN"],os.environ["META_IG_USER_ID"],graph_version="v26.0")
    client.verify_account()
    git("config","user.name","ls-vlad-meta-publisher")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    d={"id":"vlad-news-20261109","provider":"instagram","account":"liniya__sporta",
        "videoSha256":q["videoSha256"],"coverSha256":q["coverMetaSha256"],
        "videoResolution":"1080x1920","runId":os.environ["GITHUB_RUN_ID"],
        "status":"submission_started_before_meta_api","creationId":None,"publishedMediaId":None,
        "noRetries":True,"createdAtUTC":datetime.now(timezone.utc).isoformat()}
    checkpoint(d,initial=True)
    try:
        payload={"media_type":"REELS","video_url":RAW+VIDEO.name,"cover_url":RAW+COVER.name,
                "caption":r["caption"],"share_to_feed":"true"}
        media=client._api("POST",client.ig_user_id+"/media",payload)
        creation_id=str(media.get("id") or "")
        if not creation_id.isdecimal():raise RuntimeError("META_CREATION_ID_MISSING")
        d["creationId"]=creation_id
        d["status"]="meta_container_created"
        checkpoint(d)
        for attempt in range(60):
            status=client._api("GET",creation_id,{"fields":"status_code,status"})
            state=str(status.get("status_code","")).upper()
            if state=="FINISHED":break
            if state in {"ERROR","EXPIRED"}:raise RuntimeError("META_MEDIA_PROCESSING_"+state)
            if attempt<59:time.sleep(12)
        else:raise RuntimeError("META_PROCESSING_TIMED_OUT_MANUAL_REVIEW")
        published=client._api("POST",client.ig_user_id+"/media_publish",{"creation_id":creation_id})
        pid=str(published.get("id") or "")
        if not pid.isdecimal():raise RuntimeError("META_PUBLISH_ID_UNCONFIRMED")
        d["publishedMediaId"]=pid
        d["status"]="meta_api_published_readback_pending"
        checkpoint(d)
        try:
            details=client._api("GET",pid,{"fields":"id,permalink,media_type,username"})
            if str(details.get("id"))==pid and details.get("permalink"):
                d["permalink"]=details["permalink"]
                d["mediaType"]=details.get("media_type")
                d["status"]="published_readback_confirmed"
        except Exception:
            d["readbackNote"]="Meta accepted publication; permalink readback unavailable"
        checkpoint(d)
        print("VLAD_META_RESULT",json.dumps({"status":d["status"],"mediaId":pid,"permalink":d.get("permalink")},ensure_ascii=False),flush=True)
    except Exception as e:
        d["status"]="manual_reconciliation_required"
        d["errorClass"]=type(e).__name__
        d["note"]="Meta may have accepted container/publication; do not retry without reconciliation"
        try:checkpoint(d)
        except Exception as ce:print("VLAD_META_RECEIPT_PERSIST_FAILED",type(ce).__name__,flush=True)
        raise

if __name__=="__main__":
    main()
