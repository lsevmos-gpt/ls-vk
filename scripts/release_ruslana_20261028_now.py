"""Immediate owner-approved Instagram Story of Ruslana, 28 October 2026.
ONE IMAGE ONLY. Intro Girls video cancelled. No provider retries.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from scripts.publish_ruslana_birthday_20261028_ig import (
    ROOT, RECEIPT, PREFIX, META_PHOTO_SHA, preflight, checkpoint, git, utcnow
)
from scripts.instagram_meta_calendar import await_ready

RELEASE = ROOT / "requests/campaigns/ruslana-birthday-20261028-immediate.json"
PHOTO = "media/ruslana-20261028-birthday-meta.jpg"
DUE = datetime(2026,10,28,7,0,tzinfo=timezone.utc)
END = datetime(2026,10,28,20,59,59,tzinfo=timezone.utc)

def main():
    if (os.getenv("GITHUB_REPOSITORY") != "lsevmos-gpt/ls-vk"
        or os.getenv("GITHUB_REF") != "refs/heads/main"
        or os.getenv("GITHUB_EVENT_NAME") != "push"
        or os.getenv("GITHUB_ACTOR") != "lsevmos-gpt"
        or not os.getenv("GITHUB_RUN_ID","").isdigit()):
        raise RuntimeError("Unauthorized execution context")
    if not DUE <= utcnow() <= END:
        raise RuntimeError("Wrong date for birthday, no publishing")
    release=json.loads(RELEASE.read_text(encoding="utf8"))
    assert release == {
      "id":"ruslana-birthday-20261028-immediate",
      "approved":True,"publicContent":True,"submitNow":True,
      "instagram":"liniya__sporta","onlyStory":"ruslana-birthday",
      "introCancelled":True,"media":PHOTO,"sha256":META_PHOTO_SHA,
      "originalFailedCronRun":"40651393272"
    }, "Invalid authorized release"
    if RECEIPT.exists():
        print("ALREADY_ATTEMPTED_NO_DUPLICATE")
        return
    client=preflight()
    if client is None: return
    live=client._api("GET", client.ig_user_id+"/stories",
                    {"fields":"id,timestamp,media_type","limit":"50"})
    after=[]
    for story in live.get("data",[]):
        try:
            when=datetime.fromisoformat(story["timestamp"].replace("Z","+00:00"))
            if when.astimezone(timezone.utc)>=DUE:
                after.append(str(story.get("id")))
        except (ValueError,TypeError,KeyError):
            pass
    print("READ_ONLY_STORIES_SINCE_10_MSK",len(after),flush=True)
    if after:
        raise RuntimeError("Other Story already exists since 10:00 MSK; manual reconciliation required before posting")
    git("pull","--ff-only","origin","main")
    if RECEIPT.exists(): return
    git("config","user.name","ls-ruslana-meta-once-bot")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    rec={
      "id":"ruslana-birthday-20261028-instagram",
      "platform":"instagram","provider":"meta","account":"liniya__sporta",
      "releaseMode":"immediate-user-approved","status":"reserved_before_provider_call",
      "runId":os.environ["GITHUB_RUN_ID"],"createdAtUTC":utcnow().isoformat(),
      "introCancelled":True,"stories":["ruslana-birthday"],
      "published":[],"providerAttempts":0
    }
    checkpoint(rec,first=True)
    container=None
    try:
        rec["status"]="submission_started"
        rec["providerAttempts"]=1
        checkpoint(rec)
        created=client._api("POST",client.ig_user_id+"/media",
             {"media_type":"STORIES","image_url":PREFIX+PHOTO})
        container=str(created.get("id",""))
        if not container.isdecimal(): raise RuntimeError("No valid Meta container ID")
        rec["containerId"]=container
        checkpoint(rec)
        await_ready(client,container,attempts=35,interval=6)
        time.sleep(40)
        status=client._api("GET",container,{"fields":"status_code,status"})
        if status.get("status_code")!="FINISHED":
            raise RuntimeError("Meta container not FINISHED after settle window")
        posted=client._api("POST",client.ig_user_id+"/media_publish",
                            {"creation_id":container})
        media_id=str(posted.get("id",""))
        if not media_id.isdecimal():raise RuntimeError("Meta returned no published media ID")
    except Exception as e:
        rec["status"]="manual_review_required"
        rec["error"]=str(e)[:400]
        try:checkpoint(rec)
        except Exception:pass
        raise
    try:
        details=client._api("GET",media_id,{"fields":"id,media_type,timestamp,permalink"})
    except Exception:
        details={}
    verified=str(details.get("id",""))==media_id
    rec.update({"status":"published" if verified else "submitted_to_meta_verify_pending",
                "instagramMediaId":media_id,
                "permalink":details.get("permalink"),
                "metaReadbackConfirmed":verified,
                "publishedAtUTC":utcnow().isoformat(),
                "published":[{"name":"ruslana-birthday","instagramMediaId":media_id}]})
    checkpoint(rec)
    print("RUSLANA_META_STORY_ID",media_id,"META_READBACK",verified,flush=True)
    print("PERMALINK",details.get("permalink"),flush=True)

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("::error::RUSLANA_META_IMMEDIATE",str(e)[:400],file=sys.stderr)
        raise SystemExit(1)
