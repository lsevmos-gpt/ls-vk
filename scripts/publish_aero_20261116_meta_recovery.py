"""Recover exactly one approved Aero Instagram Reel using EXISTING FINISHED Meta container.
Direct Meta Graph API only. Never recreate media, never double-submit.
"""
import json, os, time, subprocess
from datetime import datetime,timezone
from pathlib import Path
from scripts.instagram_collab import MetaClient

ROOT=Path(__file__).resolve().parents[1]
JOB="aerostretch-20261116-1830"
PREV=ROOT/f"results/campaigns/{JOB}-meta.json"
RESULT=ROOT/f"results/campaigns/{JOB}-meta-release-now.json"
REQ=ROOT/f"requests/campaigns/{JOB}.json"
QA=ROOT/f"results/verification/{JOB}.json"
EXPECTED_CONTAINER="18024354821949669"
EXPECTED_VIDEO="0bd97bf4018d9bda59ef4fcf6c644a8286278b488a5fe96aad22671496ef0fd8"
EXPECTED_COVER="b2ae50f669a1a32f172fc703a19a1f4ed28277247a0fa6668a59eea817fcfaa1"

def iso():return datetime.now(timezone.utc).isoformat()
def git(*args):
    p=subprocess.run(["git",*args],cwd=ROOT,text=True,capture_output=True,timeout=120)
    if p.returncode:raise RuntimeError("GIT_"+args[0]+"_FAILED "+(p.stderr or p.stdout)[-250:])
def save(d,first=False):
    d["updatedAtUTC"]=iso()
    RESULT.parent.mkdir(parents=True,exist_ok=True)
    with RESULT.open("x" if first else "w",encoding="utf8") as f:
        json.dump(d,f,ensure_ascii=False,indent=2);f.write("\n")
    git("add","--",str(RESULT.relative_to(ROOT)))
    git("commit","-m","One-shot Aero Meta recovery "+d["status"]+" [skip ci]")
    for i in range(8):
        try:git("pull","--rebase","origin","main");git("push","origin","HEAD:main");return
        except RuntimeError:
            if i==7:raise
            time.sleep(i+1)

def main():
    assert os.getenv("GITHUB_REPOSITORY")=="lsevmos-gpt/ls-vk"
    assert os.getenv("GITHUB_ACTOR")=="lsevmos-gpt"
    assert os.getenv("GITHUB_REF")=="refs/heads/main"
    assert os.getenv("GITHUB_EVENT_NAME")=="push"
    git("pull","--ff-only","origin","main")
    if RESULT.exists():
        print("AERO_RECOVERY_ALREADY_RECORDED_NO_REPLAY");return
    p=json.loads(PREV.read_text(encoding="utf8"))
    m=json.loads(REQ.read_text(encoding="utf8"))
    q=json.loads(QA.read_text(encoding="utf8"))
    assert p["status"]=="manual_reconciliation_required" and p["containerId"]==EXPECTED_CONTAINER
    assert p["mediaId"] is None and p["sourceDriveFileId"]=="1tCWqXsjp1jeZTZVSkg73IGuCvHbxwvh-"
    assert p["videoSha256"]==EXPECTED_VIDEO and p["coverMetaSha256"]==EXPECTED_COVER
    assert m["approved"] is True and m["authorizedByUser"] is True and m["publicContent"] is True
    assert m["instagram"]["collaborators"]==["ulianakabanova246"]
    assert q["videoSha256"]==EXPECTED_VIDEO and q["coverMetaSha256"]==EXPECTED_COVER
    client=MetaClient(os.environ["META_IG_ACCESS_TOKEN"],os.environ["META_IG_USER_ID"],graph_version="v26.0")
    client.verify_account()
    status=client._api("GET",EXPECTED_CONTAINER,{"fields":"id,status_code,status"})
    if str(status.get("id"))!=EXPECTED_CONTAINER or status.get("status_code")!="FINISHED":
        raise RuntimeError("AERO_CONTAINER_NOT_READY_OR_ID_MISMATCH "+str(status.get("status_code")))
    # Inspect latest publications BEFORE the one permitted POST to avoid a duplicate.
    items=client._api("GET",client.ig_user_id+"/media",{"fields":"id,caption,permalink,timestamp","limit":"50"}).get("data",[])
    for item in items:
        if item.get("caption")==m["caption"]:
            print("AERO_META_CAPTION_ALREADY_LIVE_STOP",json.dumps({"id":item.get("id"),"permalink":item.get("permalink")}))
            return
    git("config","user.name","ls-aero-meta-recovery")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    record={"id":JOB+"-meta-release-now","provider":"instagram","account":"liniya__sporta",
        "containerId":EXPECTED_CONTAINER,"videoSha256":EXPECTED_VIDEO,
        "coverMetaSha256":EXPECTED_COVER,"nativeCollaborator":"ulianakabanova246",
        "collaboratorAcceptanceConfirmed":False,"runId":os.environ["GITHUB_RUN_ID"],
        "status":"reserved_before_media_publish","publishedMediaId":None,
        "noRetries":True,"createdAtUTC":iso()}
    save(record,first=True)
    try:
        record["status"]="media_publish_call_started";save(record)
        response=client._api("POST",client.ig_user_id+"/media_publish",{"creation_id":EXPECTED_CONTAINER})
        mid=str(response.get("id") or "")
        if not mid.isdecimal():raise RuntimeError("META_PUBLISH_NO_MEDIA_ID_NO_RETRY")
        record["publishedMediaId"]=mid
        record["status"]="meta_api_published_id_received";save(record)
        try:
            details=client._api("GET",mid,{"fields":"id,permalink,media_type,username"})
            if str(details.get("id"))==mid and details.get("permalink"):
                record["permalink"]=details["permalink"]
                record["status"]="published_readback_confirmed"
        except Exception as e:
            record["readbackErrorClass"]=type(e).__name__
        save(record)
        print("AERO_META_PUBLISH_FINAL",json.dumps({"mediaId":mid,"status":record["status"],
            "permalink":record.get("permalink"),"collaborator":"ulianakabanova246"},ensure_ascii=False))
    except Exception as e:
        record["status"]="manual_reconciliation_required"
        record["errorClass"]=type(e).__name__
        record["note"]="Do not retry; read provider status first"
        try:save(record)
        except Exception as write_error:print("AERO_META_RECEIPT_WRITE_FAILED",type(write_error).__name__)
        raise

if __name__=="__main__":main()
