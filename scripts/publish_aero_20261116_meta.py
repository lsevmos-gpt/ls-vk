"""One-shot approved Aerostretch Instagram Reel: direct Meta Graph API only."""
from __future__ import annotations
import hashlib,json,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from scripts.instagram_collab import MetaClient

ROOT=Path(__file__).resolve().parents[1]
JOB="aerostretch-20261116-1830"
REQ=ROOT/f"requests/campaigns/{JOB}.json"
QA=ROOT/f"results/verification/{JOB}.json"
VIDEO=ROOT/f"media/{JOB}-reel.mp4"
COVER=ROOT/f"media/{JOB}-cover-meta.jpg"
RECEIPT=ROOT/f"results/campaigns/{JOB}-meta.json"
RAW="https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/"
START=datetime(2026,11,16,15,30,tzinfo=timezone.utc)
DEADLINE=datetime(2026,11,16,15,31,tzinfo=timezone.utc)
COAUTHOR="ulianakabanova246"
def now():return datetime.now(timezone.utc)
def sha(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def git(*args):
    p=subprocess.run(["git",*args],cwd=ROOT,capture_output=True,text=True,timeout=120)
    if p.returncode:raise RuntimeError("GIT_"+args[0]+"_FAILED "+(p.stderr or p.stdout)[-230:])
def checkpoint(d,first=False):
    d["updatedAtUTC"]=now().isoformat()
    RECEIPT.parent.mkdir(parents=True,exist_ok=True)
    with RECEIPT.open("x" if first else "w",encoding="utf8") as f:
        json.dump(d,f,ensure_ascii=False,indent=2);f.write("\n")
    git("add","--",str(RECEIPT.relative_to(ROOT)))
    git("commit","-m","Aero approved Meta "+d["status"]+" [skip ci]")
    for i in range(8):
        try:
            git("pull","--rebase","origin","main")
            git("push","origin","HEAD:main")
            return
        except RuntimeError:
            if i==7:raise
            time.sleep(1+i)
def main():
    if not (os.getenv("GITHUB_REPOSITORY")=="lsevmos-gpt/ls-vk" and
            os.getenv("GITHUB_REF")=="refs/heads/main" and
            os.getenv("GITHUB_EVENT_NAME")=="push" and
            os.getenv("GITHUB_ACTOR")=="lsevmos-gpt" and
            str(os.getenv("GITHUB_RUN_ID","")).isdecimal()):
        raise RuntimeError("AERO_META_UNAUTHORIZED_RUN")
    git("pull","--ff-only","origin","main")
    if RECEIPT.exists():
        print("AERO_META_PRIOR_RECEIPT_NO_REPLAY");return
    if now()>=START:raise RuntimeError("AERO_META_STARTED_TOO_LATE_DO_NOT_POST")
    m=json.loads(REQ.read_text(encoding="utf8"))
    q=json.loads(QA.read_text(encoding="utf8"))
    if not(m["id"]==JOB and m["approved"] is True and m["publicContent"] is True
       and m["authorizedByUser"] is True and m["publishNow"] is False
       and m["publishAt"]=="2026-11-16T18:30:00+03:00"
       and m["sourceDriveFileId"]=="1tCWqXsjp1jeZTZVSkg73IGuCvHbxwvh-"
       and m["coverSHA256"]=="16b2bc2df6265488b256cfb114c0bb70cd4b0c8599b4a78b2e55fdc9902acb07"
       and m["instagram"]=={"handle":"liniya__sporta","collaborators":[COAUTHOR],"nativeInviteRequired":True,"shareToFeed":True}
       and 100<=len(m["caption"])<=2200
       and q["id"]==JOB and q["ok"] is True and q["stagingOnly"] is True
       and q["sourceBytes"]==703019625 and q["sourceDriveFileId"]==m["sourceDriveFileId"]
       and q["coverOriginalSha256"]==m["coverSHA256"]
       and q["videoPath"]==str(VIDEO.relative_to(ROOT)) and VIDEO.is_file()
       and q["videoSha256"]==sha(VIDEO) and VIDEO.stat().st_size==q["videoBytes"]<98_000_000
       and q["coverMetaPath"]==str(COVER.relative_to(ROOT)) and COVER.is_file()
       and q["coverMetaSha256"]==sha(COVER)):
        raise RuntimeError("AERO_META_APPROVAL_SOURCE_OR_QA_MISMATCH")
    media=RAW+VIDEO.name;cover=RAW+COVER.name
    for url in (media,cover):
        with urlopen(Request(url,method="HEAD"),timeout=60) as resp:
            if resp.status!=200:raise RuntimeError("GITHUB_MEDIA_NOT_PUBLIC_FOR_META")
    client=MetaClient(os.environ["META_IG_ACCESS_TOKEN"],os.environ["META_IG_USER_ID"],graph_version="v26.0")
    client.verify_account()
    fields=MetaClient.create_fields({"video_url":media,"cover_url":cover,"caption":m["caption"],
                                     "share_to_feed":True,"collaborators":[COAUTHOR]})
    if json.loads(fields["collaborators"])!=[COAUTHOR] or fields["cover_url"]!=cover:
        raise RuntimeError("NATIVE_META_COLLAB_OR_COVER_MISSING")
    git("config","user.name","ls-aero-meta");git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    d={"id":JOB,"provider":"instagram","account":"liniya__sporta",
       "sourceDriveFileId":m["sourceDriveFileId"],"videoSha256":q["videoSha256"],
       "coverMetaSha256":q["coverMetaSha256"],"videoResolution":q["videoResolution"],
       "collaborator":COAUTHOR,"collaboratorAccepted":False,
       "scheduledAt":"2026-11-16T18:30:00+03:00",
       "status":"reserved_before_any_meta_api_mutation",
       "runId":os.environ["GITHUB_RUN_ID"],"mediaId":None,"containerId":None,
       "noRetries":True,"createdAtUTC":now().isoformat()}
    checkpoint(d,first=True)
    try:
        d["status"]="meta_container_call_started";checkpoint(d)
        created=client._api("POST",client.ig_user_id+"/media",fields)
        cid=str(created.get("id") or "")
        if not cid.isdecimal():raise RuntimeError("META_CREATION_ID_MISSING")
        d["containerId"]=cid
        d["status"]="meta_container_created_collaborator_invited_pending_acceptance";checkpoint(d)
        for n in range(100):
            status=client._api("GET",cid,{"fields":"status_code,status"})
            val=str(status.get("status_code","")).upper()
            if val=="FINISHED":break
            if val in ("ERROR","EXPIRED"):raise RuntimeError("META_MEDIA_PROCESSING_"+val)
            if now()>DEADLINE:raise RuntimeError("META_PROCESSING_EXCEEDED_RELEASE_WINDOW")
            if n<99:time.sleep(8)
        else:raise RuntimeError("META_MEDIA_PROCESSING_TIMEOUT")
        d["status"]="meta_container_ready_waiting_for_1830";checkpoint(d)
        while now()<START:time.sleep(min(10,max(.1,(START-now()).total_seconds())))
        if now()>DEADLINE:raise RuntimeError("RELEASE_WINDOW_MISSED_NO_LATE_META_POST")
        d["status"]="meta_media_publish_call_started";checkpoint(d)
        result=client._api("POST",client.ig_user_id+"/media_publish",{"creation_id":cid})
        media_id=str(result.get("id") or "")
        if not media_id.isdecimal():raise RuntimeError("META_PUBLISH_ID_UNCONFIRMED")
        d["mediaId"]=media_id;d["status"]="meta_published_id_received_readback_pending";checkpoint(d)
        try:
            data=client._api("GET",media_id,{"fields":"id,permalink,media_type,username"})
            if str(data.get("id"))==media_id and data.get("permalink"):
                d["permalink"]=data["permalink"];d["status"]="published_readback_confirmed"
        except Exception as e:
            d["readbackNote"]="Published ID accepted; permalink readback pending"
        checkpoint(d)
        print("AERO_META_FINAL",json.dumps({"status":d["status"],"mediaId":media_id,
              "permalink":d.get("permalink"),"collaborator":COAUTHOR},ensure_ascii=False))
    except Exception as e:
        d["status"]="manual_reconciliation_required";d["errorClass"]=type(e).__name__
        d["note"]="Meta API may have accepted mutation. No retry until provider readback."
        try:checkpoint(d)
        except Exception:pass
        raise
if __name__=="__main__":main()
