"""Stage approved AeroStretch Reels from exact shared Google Drive source.
Delivery to Instagram/VK remains DIRECT official Meta/VK APIs via GitHub Actions.
This stage does not call social providers. One-time, strict QA, no silent fallback.
"""
from __future__ import annotations
import hashlib, json, os, subprocess, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JOB="aerostretch-20261116-1830"
REQ=ROOT/f"requests/campaigns/{JOB}.json"
OUT=ROOT/f"media/{JOB}-reel.mp4"
COVER_OUT=ROOT/f"media/{JOB}-cover-meta.jpg"
COVER_PNG=ROOT/f"media/{JOB}-cover-original.png"
QA=ROOT/f"results/verification/{JOB}.json"
TMP=Path("/tmp/ls-aero-20261116")
SOURCE=TMP/"aero-original.mp4"
COVER=TMP/"aero-cover.png"

def sha(path:Path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

def run(*args, **kwargs):
    subprocess.run(list(map(str,args)),check=True,**kwargs)

def info(p):
    return json.loads(subprocess.check_output(["ffprobe","-v","error","-show_entries",
      "format=duration,bit_rate:stream=codec_type,codec_name,width,height,avg_frame_rate,bit_rate,sample_rate",
      "-of","json",str(p)],text=True))

def git(*args):
    cp=subprocess.run(["git",*args],cwd=ROOT,text=True,capture_output=True,timeout=180)
    if cp.returncode:
        raise RuntimeError("GIT_"+args[0]+"_FAILED "+(cp.stderr or cp.stdout)[-270:])

def main():
    if not (os.getenv("GITHUB_REPOSITORY")=="lsevmos-gpt/ls-vk"
      and os.getenv("GITHUB_REF")=="refs/heads/main"
      and os.getenv("GITHUB_EVENT_NAME")=="push"
      and os.getenv("GITHUB_ACTOR")=="lsevmos-gpt"
      and str(os.getenv("GITHUB_RUN_ID","")).isdecimal()):
        raise RuntimeError("UNAUTHORIZED_REPO_ACTOR_EVENT")
    m=json.loads(REQ.read_text(encoding="utf8"))
    assert m["id"]==JOB and m["approved"] is True and m["publicContent"] is True and m["authorizedByUser"] is True
    assert m["publishAt"]=="2026-11-16T18:30:00+03:00" and m["publishNow"] is False
    assert m["sourceDriveFileId"]=="1tCWqXsjp1jeZTZVSkg73IGuCvHbxwvh-" and m["sourceFileName"]=="аэро.mp4"
    assert m["sourceBytes"]==703019625 and m["coverDriveFileId"]=="1b5yTEOnpvngGDXZgj51T3jLKskndRwCM"
    assert m["coverSHA256"]=="16b2bc2df6265488b256cfb114c0bb70cd4b0c8599b4a78b2e55fdc9902acb07"
    assert m["instagram"]=={"handle":"liniya__sporta","collaborators":["ulianakabanova246"],"nativeInviteRequired":True,"shareToFeed":True}
    assert m["vk"]=={"groupId":48198173,"publishWall":True,"noCoauthor":True}
    assert len(m["caption"])>100 and len(m["caption"])<=2200
    if QA.exists() or OUT.exists():
        raise RuntimeError("AERO_ALREADY_STAGED_NO_REPLAY")
    TMP.mkdir(parents=True,exist_ok=True);OUT.parent.mkdir(parents=True,exist_ok=True);QA.parent.mkdir(parents=True,exist_ok=True)
    # gdown is only the file downloader for the user-selected public Drive source.
    # It is NOT an Instagram/VK publication channel or fallback.
    import gdown
    for file_id,out in ((m["sourceDriveFileId"],SOURCE),(m["coverDriveFileId"],COVER)):
        result=gdown.download(id=file_id,output=str(out),quiet=False,fuzzy=False,verify=True)
        if result is None or not out.is_file():raise RuntimeError("APPROVED_DRIVE_MEDIA_DOWNLOAD_FAILED")
    if SOURCE.stat().st_size!=703019625:raise RuntimeError("SOURCE_BYTES_MISMATCH_OR_DRIVE_INTERSTITIAL")
    if sha(COVER)!=m["coverSHA256"]:raise RuntimeError("ORIGINAL_COVER_HASH_MISMATCH")
    from PIL import Image
    with Image.open(COVER) as im:
        if im.size!=(1080,1920) or im.format!="PNG":raise RuntimeError("COVER_NOT_EXACT_1080x1920_PNG")
        im.save(COVER_PNG,"PNG",optimize=True)
        im.convert("RGB").save(COVER_OUT,"JPEG",quality=100,subsampling=0,optimize=True)
    f=info(SOURCE);v=next((s for s in f["streams"] if s["codec_type"]=="video"),None)
    a=next((s for s in f["streams"] if s["codec_type"]=="audio"),None)
    if not v or not a:raise RuntimeError("ORIGINAL_VIDEO_OR_AUDIO_MISSING")
    w,h=int(v["width"]),int(v["height"])
    if abs(w/h-9/16)>0.008 or w<720 or h<1280:raise RuntimeError("SOURCE_NOT_TRUE_VERTICAL_9X16")
    fr=v.get("avg_frame_rate","0/0")
    n,d=map(int,fr.split("/"));fps=n/d if d else 0
    dur=float(f["format"]["duration"])
    if not (23<=fps<=60 and 4<=dur<=180):
        raise RuntimeError("SOURCE_FPS_OR_DURATION_INCOMPATIBLE")
    # For native >= 1440x2560 use 1440x2560, for smaller native use its true
    # resolution. Do not fabricate detail, faces, or add generated frames.
    if w>=1440 and h>=2560:tw,th=1440,2560
    elif w>=1080 and h>=1920:tw,th=1080,1920
    else:tw,th=w//2*2,h//2*2
    # GitHub's 100 MB max-per-file limit: use the best feasible two-pass H264
    # bitrate under a conservative 92 MiB target, AAC 192 kbps.
    max_bytes=92*1024*1024
    abr=192000
    vbr=min(15000000,max(2500000,int(max_bytes*8/dur - abr - 250000)))
    vf=f"scale={tw}:{th}:flags=lanczos,setsar=1"
    base=["ffmpeg","-hide_banner","-nostdin","-loglevel","error","-y","-i",str(SOURCE),
          "-map","0:v:0","-sn","-dn","-vf",vf,"-c:v","libx264",
          "-preset","medium","-pix_fmt","yuv420p","-b:v",str(vbr),
          "-maxrate",str(round(vbr*1.25)),"-bufsize",str(round(vbr*2)),
          "-passlogfile",str(TMP/"pass"),"-pass"]
    run(*(base+["1","-an","-f","null",os.devnull]))
    run(*(base+["2","-map","0:a:0","-c:a","aac","-b:a","192k","-ar","48000","-movflags","+faststart",str(OUT)]))
    if not (1000000<OUT.stat().st_size<98_000_000):
        raise RuntimeError("ENCODE_EXCEEDS_GITHUB_100MB_OR_IS_EMPTY")
    q=info(OUT);vv=next(x for x in q["streams"] if x["codec_type"]=="video")
    aa=next(x for x in q["streams"] if x["codec_type"]=="audio")
    if (int(vv["width"]),int(vv["height"]),vv["codec_name"],aa["codec_name"])!=(tw,th,"h264","aac"):
        raise RuntimeError("TRANSCODE_QA_CODEC_RESOLUTION_FAILED")
    if abs(float(q["format"]["duration"])-dur)>0.5:raise RuntimeError("TRANSCODE_DURATION_CHANGED")
    report={"id":JOB,"ok":True,"stagingOnly":True,"published":False,
      "sourceDriveFileId":m["sourceDriveFileId"],"sourceBytes":SOURCE.stat().st_size,
      "sourceSha256":sha(SOURCE),"sourceResolution":f"{w}x{h}","sourceFps":fps,
      "videoPath":str(OUT.relative_to(ROOT)),"videoSha256":sha(OUT),
      "videoBytes":OUT.stat().st_size,"videoResolution":f"{tw}x{th}",
      "videoFps":fps,"videoCodec":"h264","audioCodec":"aac",
      "videoBitrateTarget":vbr,"videoDownsampled":(w,h)!=(tw,th),
      "noAiReconstruction":True,
      "coverOriginalSha256":sha(COVER),"coverMetaSha256":sha(COVER_OUT),
      "coverMetaPath":str(COVER_OUT.relative_to(ROOT)),
      "coverOriginalPath":str(COVER_PNG.relative_to(ROOT)),
      "requestedTime":"2026-11-16T18:30:00+03:00"}
    QA.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    git("config","user.name","ls-aero-stage");git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    git("add","--",str(OUT.relative_to(ROOT)),str(COVER_OUT.relative_to(ROOT)),
        str(COVER_PNG.relative_to(ROOT)),str(QA.relative_to(ROOT)))
    git("commit","-m","Stage exact approved AeroStretch source and cover for DIRECT Meta/VK [skip ci]")
    for i in range(6):
        try:
            git("pull","--rebase","origin","main");git("push","origin","HEAD:main");break
        except RuntimeError:
            if i==5:raise
            time.sleep(2*(i+1))
    print("AERO_STAGED_APPROVED_SOURCE_QA",json.dumps(
      {"sourceSha256":report["sourceSha256"],"videoSha256":report["videoSha256"],
       "videoBytes":report["videoBytes"],"resolution":report["videoResolution"]}))
    # Media URLs from original approved repo must resolve publicly for Meta.
    from urllib.request import Request,urlopen
    for name in (OUT.name,COVER_OUT.name):
        url="https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/"+name
        for n in range(12):
            try:
                with urlopen(Request(url,method="HEAD"),timeout=40) as resp:
                    if resp.status==200:break
            except Exception:
                if n==11:raise RuntimeError("GITHUB_RAW_MEDIA_NOT_REACHABLE")
                time.sleep(6)
        else:raise RuntimeError("GITHUB_RAW_MEDIA_NOT_REACHABLE")

if __name__=="__main__":
    main()
