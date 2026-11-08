"""One-shot revised TABATA 18+ Instagram Reels publisher, Meta Graph v26 native collaboration."""
from __future__ import annotations
import hashlib,json,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from scripts.instagram_collab import MetaClient,load_job

ROOT=Path(__file__).resolve().parents[1]
REQ=ROOT/"requests/campaigns/tabata-20261108-v2.json"
IG=ROOT/"requests/instagram-meta/tabata-20261108-v2-polonskayaaleksandra.json"
QA=ROOT/"results/verification/tabata-20261108-v2.json"
RESULT=ROOT/"results/campaigns/tabata-20261108-v2-meta.json"
VIDEO=ROOT/"media/tabata-20261108-2k-ig-vk.mp4"
COVER=ROOT/"media/tabata-20261108-v2-meta-cover.jpg"
RAW="https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/"
SOURCE_SHA="9455b7574ca79cc684b9d92d2458b3b09c97e63b79cbf2dcf1ebf04659529f71"
VIDEO_SHA="f8bd7069cfb34cc9286f69c36015d634e23780209efb3da3ce9e830562d5d969"
COVER_SHA="947919e203f619e7c0c1de9695d4162ab19c23df8f4ba7d593a6cd100216ff2b"

def sha(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def git(*args):
    p=subprocess.run(["git",*args],cwd=ROOT,capture_output=True,text=True,timeout=95)
    if p.returncode:raise RuntimeError("git_"+args[0]+"_failed "+(p.stderr or p.stdout)[-210:])

def checkpoint(r,initial=False):
    r["updatedAtUTC"]=datetime.now(timezone.utc).isoformat()
    RESULT.parent.mkdir(parents=True,exist_ok=True)
    with RESULT.open("x" if initial else "w",encoding="utf8") as f:
        json.dump(r,f,ensure_ascii=False,indent=2);f.write("\n")
    git("add","--",str(RESULT.relative_to(ROOT)))
    git("commit","-m","TABATA v2 Meta "+r["status"]+" [skip ci]")
    for n in range(8):
        try:
            git("pull","--rebase","origin","main")
            git("push","origin","HEAD:main")
            return
        except RuntimeError:
            if n==7:raise
            time.sleep(n+1)

def main():
    if (os.getenv("GITHUB_REPOSITORY")!="lsevmos-gpt/ls-vk" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_EVENT_NAME")!="push" or
        os.getenv("GITHUB_ACTOR")!="lsevmos-gpt" or
        not os.getenv("GITHUB_RUN_ID","").isdigit()):
        raise RuntimeError("unapproved_workflow_context")
    git("pull","--ff-only","origin","main")
    if RESULT.exists():
        print("TABATA_V2_META_EXISTING_ATTEMPT_NO_REPLAY",flush=True)
        return
    r=json.loads(REQ.read_text(encoding="utf8"))
    qa=json.loads(QA.read_text(encoding="utf8"))
    job=load_job(str(IG.relative_to(ROOT)))
    correct=(
        r.get("id")=="tabata-20261108-v2" and
        r.get("approved") is True and r.get("publicContent") is True and r.get("publishNow") is True and
        r.get("sourceSHA256")==SOURCE_SHA and
        r.get("coverSHA256")==COVER_SHA and
        r.get("instagram")=={"handle":"liniya__sporta","collaborators":["polonskayaaleksandra"],"nativeInviteRequired":True} and
        r.get("vk")=={"groupId":48198173,"publishWall":True,"noCoauthor":True} and
        job["id"]=="tabata-20261108-v2-polonskayaaleksandra" and
        job["caption"]==r["caption"] and
        job["collaborators"]==["polonskayaaleksandra"] and
        job["share_to_feed"] is True and
        job["video_url"]==RAW+"media/tabata-20261108-2k-ig-vk.mp4" and
        job["cover_url"]==RAW+"media/tabata-20261108-v2-meta-cover.jpg" and
        qa.get("ok") is True and qa.get("stagingOnly") is True and
        qa.get("sourceSha256")==SOURCE_SHA and qa.get("videoSha256")==VIDEO_SHA and
        qa.get("videoResolution")=="1440x2560" and
        qa.get("coverOriginalSha256")==COVER_SHA and
        qa.get("coverMetaSha256")==sha(COVER) and
        VIDEO.is_file() and sha(VIDEO)==VIDEO_SHA and VIDEO.stat().st_size==86051299
    )
    if not correct:raise RuntimeError("approved_source_cover_caption_collaborator_or_2k_mismatch")
    for u in (job["video_url"],job["cover_url"]):
        with urlopen(Request(u,method="HEAD",headers={"User-Agent":"Liniya-Sporta-Publication/1"}),timeout=55) as resp:
            if resp.status!=200:raise RuntimeError("media_host_unavailable")
    client=MetaClient(os.environ["META_IG_ACCESS_TOKEN"],os.environ["META_IG_USER_ID"],graph_version="v26.0")
    client.verify_account()
    git("config","user.name","ls-tabata-v2-meta-publisher")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    d={"id":"tabata-20261108-v2","provider":"instagram","account":"liniya__sporta",
       "collaborator":"polonskayaaleksandra","collaboratorAcceptanceConfirmed":False,
       "coverSha256":qa["coverMetaSha256"],"videoSha256":VIDEO_SHA,"videoResolution":"1440x2560",
       "runId":os.environ["GITHUB_RUN_ID"],"status":"submission_started_before_Meta_API",
       "publishedMediaId":None,"noRetries":True,
       "createdAtUTC":datetime.now(timezone.utc).isoformat()}
    checkpoint(d,initial=True)
    try:
        result=client.publish_reel(job,attempts=54,interval_seconds=12)
        d["creationId"]=result["creation_id"]
        d["publishedMediaId"]=result["published_media_id"]
        d["status"]="meta_api_published_readback_pending"
        checkpoint(d)
        try:
            details=client._api("GET",d["publishedMediaId"],{"fields":"id,permalink,media_type,username"})
            if str(details.get("id"))==str(d["publishedMediaId"]):
                d["permalink"]=details.get("permalink")
                d["mediaType"]=details.get("media_type")
                d["status"]="published_readback_confirmed"
        except Exception:
            d["readbackNote"]="Meta accepted media; permalink not yet confirmed"
        checkpoint(d)
        print("TABATA_V2_META_RESULT",json.dumps({
            "status":d["status"],"mediaId":d["publishedMediaId"],"permalink":d.get("permalink"),
            "collab":"native_invitation_requested; acceptance_not_confirmed"},ensure_ascii=False),flush=True)
    except Exception as e:
        d["status"]="manual_reconciliation_required"
        d["error"]=str(e).replace(os.getenv("META_IG_ACCESS_TOKEN","__"),"[REDACTED]")[:240]
        d["note"]="Meta may have accepted container or publication; DO NOT replay"
        try:checkpoint(d)
        except Exception as sync:print("RECEIPT_PERSIST_FAILED",type(sync).__name__,flush=True)
        raise

if __name__=="__main__":
    main()
