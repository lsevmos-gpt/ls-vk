"""One-shot approved TABATA 18+ Instagram Reel via Meta Graph API."""
import hashlib, json, os, subprocess, time
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from scripts.instagram_collab import MetaClient, load_job

ROOT = Path(__file__).resolve().parents[1]
REQ = ROOT / "requests/campaigns/tabata-20261108.json"
COLLAB = ROOT / "requests/instagram-meta/tabata-20261108-polonskayaaleksandra.json"
QA = ROOT / "results/verification/tabata-20261108-2k.json"
RESULT = ROOT / "results/campaigns/tabata-20261108-meta.json"
RAW = "https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/"
SRC_SHA = "9455b7574ca79cc684b9d92d2458b3b09c97e63b79cbf2dcf1ebf04659529f71"
COVER_SHA = "46ba40861605ade03564f3413ccb40ea2a3533f29d5ceaca06453b612a29243b"

def git(*a):
    p=subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, timeout=105)
    if p.returncode: raise RuntimeError("git_"+a[0]+"_failed "+(p.stderr or p.stdout)[-250:])

def digest(p):
    with p.open("rb") as f: return hashlib.file_digest(f, "sha256").hexdigest()

def checkpoint(d, initial=False):
    d["updatedAtUTC"] = datetime.now(timezone.utc).isoformat()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    with RESULT.open("x" if initial else "w", encoding="utf8") as f:
        json.dump(d,f,ensure_ascii=False,indent=2); f.write("\n")
    git("add","--",str(RESULT.relative_to(ROOT)))
    git("commit","-m","Tabata 20261108 Instagram Meta "+d["status"]+" [skip ci]")
    for i in range(8):
        try:
            git("pull","--rebase","origin","main")
            git("push","origin","HEAD:main")
            return
        except RuntimeError:
            if i==7: raise
            time.sleep(i+1)

def main():
    if (os.getenv("GITHUB_REPOSITORY")!="lsevmos-gpt/ls-vk" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_EVENT_NAME")!="push" or
        not os.getenv("GITHUB_RUN_ID","").isdigit()):
        raise RuntimeError("unauthorized_github_context")
    git("pull","--ff-only","origin","main")
    if RESULT.exists():
        print("TABATA_META_RECEIPT_EXISTS_NO_RETRY"); return
    req=json.loads(REQ.read_text(encoding="utf8"))
    qa=json.loads(QA.read_text(encoding="utf8"))
    job=load_job(str(COLLAB.relative_to(ROOT)))
    video=ROOT / "media/tabata-20261108-2k-ig-vk.mp4"
    cover=ROOT / "media/tabata-20261108-meta-cover.jpg"
    checks=(
        req.get("id")=="tabata-20261108" and
        req.get("approved") is True and req.get("publicContent") is True and
        req.get("postNow") is True and req.get("sourceSHA256")==SRC_SHA and
        req.get("coverSHA256")==COVER_SHA and
        req.get("instagram")=={"handle":"liniya__sporta","collaborators":["polonskayaaleksandra"],"nativeInviteRequired":True} and
        job["id"]=="tabata-20261108-polonskayaaleksandra" and
        job["collaborators"]==["polonskayaaleksandra"] and
        job["caption"]==req["caption"] and
        job["share_to_feed"] is True and
        job["video_url"]==RAW+"media/tabata-20261108-2k-ig-vk.mp4" and
        job["cover_url"]==RAW+"media/tabata-20261108-meta-cover.jpg" and
        qa["ok"] is True and qa["sourceSha256"]==SRC_SHA and
        qa["coverOriginalSha256"]==COVER_SHA and
        qa["videoResolution"]=="1440x2560" and
        qa["videoSha256"]==digest(video) and
        qa["videoBytes"]==video.stat().st_size and video.stat().st_size<95_000_000 and
        qa["coverMetaSha256"]==digest(cover)
    )
    if not checks: raise RuntimeError("source_caption_coauthor_or_video_qa_mismatch")
    for u in (job["video_url"],job["cover_url"]):
        with urlopen(Request(u,method="HEAD"),timeout=35) as r:
            if r.status!=200: raise RuntimeError("public_media_not_available")
    client=MetaClient(os.environ["META_IG_ACCESS_TOKEN"],os.environ["META_IG_USER_ID"],graph_version="v26.0")
    client.verify_account()
    git("config","user.name","ls-tabata-meta-publisher")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    record={"id":"tabata-20261108","provider":"instagram","account":"liniya__sporta",
       "collaborator":"polonskayaaleksandra","collaboratorAcceptanceConfirmed":False,
       "sourceSha256":SRC_SHA,"videoSha256":qa["videoSha256"],
       "videoResolution":qa["videoResolution"],"runId":os.environ["GITHUB_RUN_ID"],
       "status":"submission_started","publishedMediaId":None,"createdAtUTC":datetime.now(timezone.utc).isoformat(),
       "noRetries":True}
    checkpoint(record,initial=True)
    try:
        result=client.publish_reel(job,attempts=48,interval_seconds=10)
        record["creationId"]=result["creation_id"]
        record["publishedMediaId"]=result["published_media_id"]
        record["status"]="meta_api_published_readback_pending"
        checkpoint(record)
        try:
            details=client._api("GET",str(record["publishedMediaId"]),{"fields":"id,permalink,media_type,username"})
            if str(details.get("id"))==str(record["publishedMediaId"]):
                record["permalink"]=details.get("permalink")
                record["readbackMediaType"]=details.get("media_type")
                record["status"]="published_readback_confirmed"
        except Exception:
            record["readbackNote"]="Meta media accepted, readback not yet confirmed"
        checkpoint(record)
        print("TABATA_META_RESULT",json.dumps({"status":record["status"],"mediaId":record["publishedMediaId"],"permalink":record.get("permalink"),"collaboratorInvite":"requested, acceptance pending"},ensure_ascii=False),flush=True)
    except Exception as e:
        record["status"]="manual_reconciliation_required"
        record["error"]=str(e)[:260]
        record["noRetries"]=True
        try: checkpoint(record)
        except Exception as ee: print("META_RECEIPT_PERSIST_FAILED",str(ee)[:120])
        raise

if __name__=="__main__":
    main()
