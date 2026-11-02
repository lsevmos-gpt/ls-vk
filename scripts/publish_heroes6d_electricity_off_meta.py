"""One-shot direct Meta Story for the exact Heroes6D power-outage image."""
import hashlib,json,os,subprocess,time,sys
from pathlib import Path
from urllib.request import Request,urlopen
from datetime import datetime,timezone
from scripts.instagram_collab import MetaClient
from scripts.instagram_meta_calendar import publish_via_meta

ID="ls-heroes6d-electricity-off-20261102"
SHA="b49ca56bfee78725407f5172f52d53106c93fca3b9e7cb82eff5999ffd95ecbb"
QA=Path("results/verification/"+ID+"-stage.json")
RELEASE=Path("requests/campaigns/"+ID+"-release.json")
RECEIPT=Path("results/campaigns/"+ID+"-ig.json")
URL="https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/"+ID+"-meta.jpg"

def git(*args):
    p=subprocess.run(["git",*args],capture_output=True,text=True,timeout=90)
    if p.returncode:raise RuntimeError("git "+" ".join(args[:2])+" failed: "+(p.stderr or p.stdout)[-250:])

def checkpoint(doc,first=False):
    doc["updatedAtUTC"]=datetime.now(timezone.utc).isoformat()
    RECEIPT.parent.mkdir(parents=True,exist_ok=True)
    with RECEIPT.open("x" if first else "w") as f:
        json.dump(doc,f,ensure_ascii=False,indent=2);f.write("\n")
    git("add","--",str(RECEIPT))
    git("commit","-m","Record Heroes6D outage Meta Story "+doc["status"]+" [skip ci]")
    for i in range(6):
        try:
            git("pull","--rebase","origin","main")
            git("push","origin","HEAD:main")
            return
        except RuntimeError:
            if i==5:raise
            time.sleep(i+1)

def preflight():
    if (os.getenv("GITHUB_REPOSITORY")!="lsevmos-gpt/ls-vk" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_ACTOR")!="lsevmos-gpt" or
        os.getenv("GITHUB_EVENT_NAME")!="push" or
        not os.getenv("GITHUB_RUN_ID","").isdecimal()):
        raise RuntimeError("Unauthorized GitHub publishing context")
    git("pull","--ff-only","origin","main")
    if RECEIPT.exists():
        print("EXISTING_IG_RECEIPT_DO_NOT_REPOST",flush=True)
        return False
    r=json.loads(RELEASE.read_text())
    q=json.loads(QA.read_text())
    if not (r["id"]==q["id"]==ID and r["approved"] is True and
        r["publicContent"] is True and r["submitNow"] is True and
        r["instagram"]=="liniya__sporta" and r["vkGroupId"]==48198173 and
        r["stories"]==["electricity-off-heroes6d"] and q["ok"] is True and
        q["stagingOnly"] is True and q["originalVKUnchanged"] is True and
        q["sourceSha256"]==SHA and q["sourceBytes"]==3223258 and
        q["jpgQuality"]==100 and q["width"]==1080 and q["height"]==1920):
        raise RuntimeError("Release or QA mismatch")
    jpg=Path(q["jpgPath"]);png=Path(q["pngPath"])
    if (jpg.as_posix()!="media/"+ID+"-meta.jpg" or
        png.as_posix()!="media/"+ID+".png" or
        jpg.stat().st_size!=q["jpgBytes"] or
        png.stat().st_size!=q["sourceBytes"]):
        raise RuntimeError("Unexpected file size/path")
    if hashlib.sha256(png.read_bytes()).hexdigest()!=SHA or hashlib.sha256(jpg.read_bytes()).hexdigest()!=q["jpgSHA256"]:
        raise RuntimeError("Image hash mismatch")
    for n in range(5):
        try:
            with urlopen(Request(URL,method="HEAD"),timeout=30) as response:
                if response.status==200:break
        except Exception:
            if n==4:raise
            time.sleep(3)
    return True

def main():
    if not preflight():return
    client=MetaClient(os.getenv("META_IG_ACCESS_TOKEN",""),os.getenv("META_IG_USER_ID",""),graph_version="v26.0")
    client.verify_account()
    git("config","user.name","ls-story-meta")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    if RECEIPT.exists():
        print("EXISTING_IG_RECEIPT_SKIP");return
    doc={"id":ID,"provider":"meta","account":"liniya__sporta","postType":"story",
         "status":"submission_started","sourceSha256":SHA,"runId":os.getenv("GITHUB_RUN_ID"),
         "uploadFormat":"JPEG quality 100 1080x1920","createAttempts":1}
    checkpoint(doc,True)
    try:
        ident=publish_via_meta(client,{"postType":"story","media":[{"type":"image","url":URL}],"text":""})
        if not str(ident).isdecimal():raise RuntimeError("Meta did not return Media ID")
        doc["instagramMediaId"]=str(ident)
        doc["status"]="published_readback_pending"
        checkpoint(doc)
        try:
            detail=client._api("GET",str(ident),{"fields":"id,media_type,timestamp,permalink"})
            doc["readbackConfirmed"]=str(detail.get("id"))==str(ident)
            doc["permalink"]=detail.get("permalink")
            doc["timestamp"]=detail.get("timestamp")
            doc["status"]="published_verified_by_meta" if doc["readbackConfirmed"] else "published_readback_pending"
        except Exception as err:
            doc["readbackConfirmed"]=False
            doc["readbackError"]=type(err).__name__
        checkpoint(doc)
        print("HEROES6D_META_STORY",json.dumps({"mediaId":ident,"status":doc["status"],"permalink":doc.get("permalink")}))
    except Exception as err:
        doc["status"]="manual_review_required"
        doc["error"]=str(err)[:240]
        doc["note"]="Do not replay. Meta outcome may be uncertain."
        try:checkpoint(doc)
        except Exception as cp:print("RECEIPT_SYNC_ERROR",type(cp).__name__,file=sys.stderr)
        raise

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("::error::HEROES6D_META_STORY "+str(exc)[:350],file=sys.stderr)
        raise SystemExit(1)
