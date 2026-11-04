"""One-time immediate Meta Reel for Sofia Bulatetskaya. Native Collab, no provider retries."""
from __future__ import annotations
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from scripts.instagram_collab import MetaClient,load_job
ROOT=Path(__file__).resolve().parents[1]
ID="sofiya-bulatetskaya-20261104-reel"
M=ROOT/"requests/campaigns/sofiya-bulatetskaya-20261104-reel.json"
C=ROOT/"requests/instagram-meta/sofiya-bulatetskaya-20261104-reel.json"
QA=ROOT/"results/verification/sofiya-bulatetskaya-20261104-reel-qa.json"
REC=ROOT/"results/instagram-meta/sofiya-bulatetskaya-20261104-reel.json"
VIDEO=ROOT/"media/sofiya-bulatetskaya-20261104-reel-meta.mp4"
COVER=ROOT/"media/sofiya-bulatetskaya-20261104-reel-meta-cover.jpg"
NOT_BEFORE=datetime(2026,11,4,15,30,tzinfo=timezone.utc)
DEADLINE=datetime(2026,11,4,16,30,tzinfo=timezone.utc)
RAW="https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/"
def now(): return datetime.now(timezone.utc)
def iso(): return now().isoformat()
def sha(p):
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def git(*args):
    p=subprocess.run(["git",*args],cwd=ROOT,capture_output=True,text=True,timeout=110)
    if p.returncode:raise RuntimeError("git "+ " ".join(args[:2])+" error "+(p.stderr or p.stdout)[-280:])
def checkpoint(rec,first=False):
    rec["updatedAtUTC"]=iso()
    REC.parent.mkdir(parents=True,exist_ok=True)
    with REC.open("x" if first else "w",encoding="utf-8") as f:
        json.dump(rec,f,indent=2,ensure_ascii=False); f.write("\n")
    git("add","--",str(REC.relative_to(ROOT)))
    git("commit","-m","Record Sofia Bulatetskaya one-time native Meta Reel "+rec["status"]+" [skip ci]")
    for n in range(6):
        try:
            git("pull","--rebase","origin","main")
            git("push","origin","HEAD:main")
            return
        except RuntimeError:
            if n==5:raise
            time.sleep(n+1)
def preflight():
    if (os.environ.get("GITHUB_REPOSITORY")!="lsevmos-gpt/ls-vk" or
        os.environ.get("GITHUB_REF")!="refs/heads/main" or
        os.environ.get("GITHUB_EVENT_NAME")!="push" or
        os.environ.get("GITHUB_ACTOR")!="lsevmos-gpt" or
        not os.environ.get("GITHUB_RUN_ID","").isdecimal()):
        raise RuntimeError("Unexpected action context")
    git("pull","--ff-only","origin","main")
    if REC.exists():
        print("SOFIYA_META_RESERVED_SKIP_NO_DUPLICATE",flush=True);return None
    m=json.loads(M.read_text())
    q=json.loads(QA.read_text())
    job=load_job(str(C.relative_to(ROOT)))
    if not (m["id"]==q["id"]==ID and m["approved"] is True and m["publicContent"] is True
      and m["requestedFor"]=="2026-11-04T18:30:00+03:00"
      and m["instagram"]["account"]=="liniya__sporta"
      and m["instagram"]["nativeCollaborator"]=="sofiya_bulat"
      and m["vk"]["status"]=="blocked_unverified_vk_native_collaborator"
      and m["vk"]["noPublishWithoutNativeCoauth"] is True
      and job["id"]==ID and job["collaborators"]==["sofiya_bulat"]
      and job["share_to_feed"] is True and job["caption"]==m["caption"]
      and q["ok"] is True and q["stagingOnly"] is True and q["published"] is False
      and q["sourceMovSHA256"]==m["video"]["originalSHA256"]
      and q["coverPngSHA256"]==m["cover"]["sourceSHA256"]
      and q["videoPath"]==str(VIDEO.relative_to(ROOT))
      and q["coverMetaPath"]==str(COVER.relative_to(ROOT))
      and q["videoWidth"]==1080 and q["videoHeight"]==1920 and q["fps"]==25
      and q["videoCodec"]=="h264" and q["audioCodec"]=="aac"
      and q["videoStreamUnchanged"] is True
      and q["metaJPEGQuality"]==100
      and 1000000<q["videoBytes"]<95000000):
        raise RuntimeError("Source, approval, native collaborator or quality mismatch")
    for p,size,dig in ((VIDEO,q["videoBytes"],q["videoSHA256"]),(COVER,q["metaJPEGBytes"],q["metaJPEGSHA256"])):
        if not p.is_file() or p.stat().st_size!=size or sha(p)!=dig:
            raise RuntimeError("Media SHA256 or size mismatch")
    for u in (job["video_url"],job["cover_url"]):
        if not u.startswith(RAW):raise RuntimeError("Unapproved media host")
        with urlopen(Request(u,method="HEAD"),timeout=55) as r:
            if r.status!=200:raise RuntimeError("Media not publicly accessible")
    fields=MetaClient.create_fields(job)
    if (fields.get("media_type")!="REELS"
         or json.loads(fields["collaborators"])!=["sofiya_bulat"]
         or fields.get("caption")!=m["caption"] or fields.get("share_to_feed")!="true"
         or fields.get("video_url")!=job["video_url"] or fields.get("cover_url")!=job["cover_url"]):
        raise RuntimeError("Meta native collaborator or caption missing")
    c=MetaClient(os.environ.get("META_IG_ACCESS_TOKEN",""),os.environ.get("META_IG_USER_ID",""),graph_version="v26.0")
    c.verify_account()
    return c,fields,job,q
def main():
    if now()>DEADLINE:raise RuntimeError("Publication window closed; do not post late")
    checked=preflight()
    if checked is None:return
    client,fields,job,q=checked
    while now()<NOT_BEFORE:time.sleep(min(2,(NOT_BEFORE-now()).total_seconds()))
    if now()>DEADLINE:raise RuntimeError("Approved window closed")
    git("pull","--ff-only","origin","main")
    if REC.exists():return
    git("config","user.name","ls-meta-sofiya-reel")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    rec={"id":ID,"platform":"instagram-meta","type":"REELS","account":"liniya__sporta",
         "status":"reserved_before_mutation","originalVideoSHA256":q["sourceMovSHA256"],
         "preparedVideoSHA256":q["videoSHA256"],"resolution":"1080x1920","videoStreamUnchanged":True,
         "collaboratorInvited":"sofiya_bulat","collaborationStatus":"NOT_SENT",
         "caption":job["caption"],"runId":os.environ["GITHUB_RUN_ID"],"createdAtUTC":iso()}
    checkpoint(rec,True)
    try:
        rec["status"]="container_creation_started"
        checkpoint(rec)
        result=client._api("POST",client.ig_user_id+"/media",fields)
        cid=str(result.get("id",""))
        if not cid.isdecimal():raise RuntimeError("No Meta container ID")
        rec.update(status="container_created",creationId=cid,collaborationStatus="native_invitation_requested_in_container_fields")
        checkpoint(rec)
        for _ in range(65):
            status=client._api("GET",cid,{"fields":"status_code,status"})
            code=str(status.get("status_code","")).upper()
            if code=="FINISHED":break
            if code in ("ERROR","EXPIRED","PUBLISHED"):raise RuntimeError("Meta container "+code)
            if now()>DEADLINE:raise RuntimeError("Meta processing exceeded allowed window")
            time.sleep(12)
        else:raise RuntimeError("Meta processing timeout; no repeat")
        rec["status"]="container_ready"
        checkpoint(rec)
        if now()>DEADLINE:raise RuntimeError("Meta publish deadline passed")
        rec["status"]="publish_call_started"
        checkpoint(rec)
        published=client._api("POST",client.ig_user_id+"/media_publish",{"creation_id":cid})
        mid=str(published.get("id",""))
        if not mid.isdecimal():raise RuntimeError("No Meta Media ID, manual reconciliation")
        rec.update(status="published_meta_id_received",mediaId=mid,publishedAtUTC=iso(),
                   collaborationStatus="native_invitation_requested; acceptance_not_independently_confirmed")
        checkpoint(rec)
        try:
            detail=client._api("GET",mid,{"fields":"id,media_type,timestamp,permalink"})
            rec["mediaType"]=detail.get("media_type")
            rec["permalink"]=detail.get("permalink")
            rec["metaTimestamp"]=detail.get("timestamp")
            rec["metaReadbackConfirmed"]=str(detail.get("id"))==mid and detail.get("media_type") in ("VIDEO","REELS")
            rec["status"]="published_readback_confirmed" if rec["metaReadbackConfirmed"] else "published_readback_pending"
        except Exception as e:
            rec["status"]="published_readback_pending";rec["readbackError"]=type(e).__name__
        checkpoint(rec)
        print("SOFIYA_META_REEL_RESULT",json.dumps({"mediaId":mid,"status":rec["status"],"permalink":rec.get("permalink")},ensure_ascii=False),flush=True)
    except Exception as e:
        if rec.get("status") not in ("published_readback_confirmed","published_readback_pending"):
            rec["status"]="manual_review_required";rec["error"]=str(e)[:320]
            rec["note"]="Meta outcome might be uncertain. Never retry or publish a duplicate."
            try:checkpoint(rec)
            except Exception as ee:print("Receipt commit failed",type(ee).__name__,file=sys.stderr)
        raise
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("::error::SOFIYA_REEL "+str(e)[:400],file=sys.stderr);raise SystemExit(1)
