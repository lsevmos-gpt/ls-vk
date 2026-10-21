"""ONE-SHOT authorized Bar -> Berry -> Creatine Instagram Stories publisher.
No retries. Persist each published media ID before starting the next story.
"""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts.instagram_collab import MetaClient
from scripts.instagram_meta_calendar import publish_via_meta

ROOT = Path(__file__).resolve().parents[1]
JOB_ID = "bar-three-stories-20261021-ig"
MANIFEST = ROOT / "requests/campaigns/bar-three-stories-20261021-instagram.json"
STAGE = ROOT / "results/verification/bar-three-stories-20261021-stage.json"
AUDIO_STAGE = ROOT / "results/verification/bar-three-stories-20261021-meta-audio.json"
RECEIPT = ROOT / "results/campaigns/bar-three-stories-20261021-instagram.json"
PREFIX = "https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/"
SOURCE_ITEMS = [
    ("bar-intro", "media/bar-20261021-intro-original.mp4", "96a269ddf1e5dc65e8a33bfddbbd1463b7943a22bab92079d149b128540eba3e"),
    ("berry-smoothie-v2", "media/bar-20261021-berry-v2-original.mp4", "edc6d12b52992e66b730dc4c925906288855822968f2f500a4a63980d1ee48fb"),
    ("creatine", "media/bar-20261021-creatine-meta-vk-hq.mp4", "ecf2ed306a49840b549a44962dd1136a3c67ff126786818bf7457436f227cb97"),
]
ITEMS = [
    ("bar-intro", "media/bar-20261021-intro-meta-audio.mp4"),
    ("berry-smoothie-v2", "media/bar-20261021-berry-v2-meta-audio.mp4"),
    ("creatine", "media/bar-20261021-creatine-meta-audio.mp4"),
]

def now():
    return datetime.now(timezone.utc).isoformat()

def git(*args):
    subprocess.run(["git",*args],cwd=ROOT,check=True,capture_output=True,text=True,timeout=90)

def checkpoint(record:dict):
    record["updatedAtUTC"]=now()
    RECEIPT.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    git("add","--",str(RECEIPT.relative_to(ROOT)))
    git("commit","-m","Record single-shot Meta Bar Stories "+record["status"]+" [skip ci]")
    git("pull","--rebase","origin","main")
    git("push","origin","HEAD:main")
    print("META_STORY_CHECKPOINT",json.dumps({"status":record["status"],"count":len(record["published"])},ensure_ascii=False),flush=True)

def run():
    if (os.environ.get("GITHUB_REPOSITORY")!="lsevmos-gpt/ls-vk"
            or os.environ.get("GITHUB_REF")!="refs/heads/main"
            or os.environ.get("GITHUB_ACTOR")!="lsevmos-gpt"):
        raise RuntimeError("Unauthorized workflow context")
    run_id=os.environ.get("GITHUB_RUN_ID","")
    if not run_id.isdecimal():raise RuntimeError("Missing GitHub run ID")
    git("pull","--ff-only","origin","main")
    if RECEIPT.exists():raise RuntimeError("Existing Instagram Bar Story attempt, no duplicate publishing")
    doc=json.loads(MANIFEST.read_text(encoding="utf-8"))
    stage=json.loads(STAGE.read_text(encoding="utf-8"))
    audio_stage=json.loads(AUDIO_STAGE.read_text(encoding="utf-8"))
    if not(doc["approved"] is True and doc["publicContent"] is True
           and doc["id"]==JOB_ID and doc["platform"]=="instagram"
           and doc["account"]=="liniya__sporta"
           and doc["submitNow"] is True and stage["ok"] is True
           and audio_stage["ok"] is True and audio_stage["videoStreamsCopiedWithoutReencode"] is True):
        raise RuntimeError("Manifest not approved or stage invalid")
    expected=[{"id":x[0],"type":"video","mediaUrl":PREFIX+x[1]} for x in ITEMS]
    if doc["stories"]!=expected:raise RuntimeError("Unapproved order or wrong media")
    if stage["orderedMedia"]!=[x[1] for x in SOURCE_ITEMS]:
        raise RuntimeError("Staging source sequence mismatch")
    if audio_stage["order"]!=[x[0] for x in ITEMS] or len(audio_stage["files"])!=3:
        raise RuntimeError("Meta audio output order mismatch")
    for _,path,expected_sha in SOURCE_ITEMS:
        file=ROOT/path
        if not file.is_file() or file.is_symlink():raise RuntimeError("Missing original media "+path)
        with file.open("rb") as handle:
            actual=hashlib.file_digest(handle,"sha256").hexdigest()
        if actual!=expected_sha or actual!=stage["files"][path]["sha256"]:
            raise RuntimeError("Unauthorized source bytes "+path)
    for index,(item_id,path) in enumerate(ITEMS):
        item=audio_stage["files"][index]
        if item["meta"]!=path or item["source"]!=SOURCE_ITEMS[index][1]:
            raise RuntimeError("Unapproved Meta derivative "+item_id)
        file=ROOT/path
        if not file.is_file() or file.is_symlink():raise RuntimeError("Missing Meta media "+path)
        with file.open("rb") as handle:
            actual=hashlib.file_digest(handle,"sha256").hexdigest()
        if actual!=item["sha256"] or int(item["audioBitrate"])>128000:
            raise RuntimeError("Invalid Meta media bytes/audio "+path)
    client=MetaClient(os.environ.get("META_IG_ACCESS_TOKEN",""),
                      os.environ.get("META_IG_USER_ID",""),
                      graph_version=os.environ.get("META_GRAPH_VERSION","v26.0"))
    client.verify_account() # read-only PRE-reservation verification
    git("config","user.name","ls-meta-story-bot")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    RECEIPT.parent.mkdir(parents=True,exist_ok=True)
    marker={"id":JOB_ID,"account":"liniya__sporta","provider":"meta",
            "status":"reserved_before_provider_call","runId":run_id,
            "source":"requests/campaigns/bar-three-stories-20261021-instagram.json",
            "createdAtUTC":now(),"published":[],
            "note":"Exactly one attempt. Never replay after uncertain provider result."}
    with RECEIPT.open("x",encoding="utf-8") as f:
        f.write(json.dumps(marker,ensure_ascii=False,indent=2)+"\n")
    git("add","--",str(RECEIPT.relative_to(ROOT)))
    git("commit","-m","Reserve approved 3 Instagram Bar Stories [skip ci]")
    git("push","origin","HEAD:main")
    for idx,(item_id,path) in enumerate(ITEMS,1):
        marker["status"]="submission_started"
        marker["attemptingIndex"]=idx
        marker["attemptingItem"]=item_id
        checkpoint(marker)
        try:
            result=publish_via_meta(client,{"postType":"story","media":[{"type":"video","url":PREFIX+path}],"text":""})
            if not(result and result.isdecimal()):
                raise RuntimeError("Meta media_publish returned no numeric Media ID")
            details={}
            try:
                details=client._api("GET",result,{"fields":"id,media_type,timestamp,permalink"})
            except Exception:
                details={}
            row={"index":idx,"name":item_id,"instagramMediaId":result,
                 "publishedAtUTC":now(),"permalink":details.get("permalink"),
                 "metaReadbackConfirmed":details.get("id")==result}
            marker["published"].append(row)
            marker["status"]="partial_published" if idx<len(ITEMS) else "published"
            marker.pop("attemptingIndex",None)
            marker.pop("attemptingItem",None)
            checkpoint(marker)
            print("META_STORY_PUBLISHED",idx,item_id,result,flush=True)
            if idx<len(ITEMS):time.sleep(3)
        except Exception as e:
            marker["status"]="manual_review_required"
            marker["error"]=str(e)[:300]
            marker["note"]="Uncertain or rejected provider result: DO NOT RETRY; read Instagram before any new attempt."
            checkpoint(marker)
            raise
    print("BAR_INSTAGRAM_THREE_STORIES_PUBLISHED",json.dumps(marker["published"],ensure_ascii=False),flush=True)

if __name__=="__main__":
    try:run()
    except Exception as e:
        print("::error::INSTAGRAM_BAR_SEQUENCE "+str(e)[:350],file=sys.stderr)
        raise SystemExit(1)
