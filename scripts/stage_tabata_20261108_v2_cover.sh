#!/usr/bin/env bash
set -euo pipefail
mkdir -p media results/verification
python -m pip install --disable-pip-version-check 'Pillow>=10,<13'
echo "Fetch exact approved TABATA revised cover (no AI or replacement)"
curl --fail --silent --show-error --location --retry 2 --connect-timeout 25 --max-time 190 'https://at.adobe.com/dmaVP4ZACnz12dc9' -o media/tabata-20261108-v2-cover-original.png
test "$(stat -c%s media/tabata-20261108-v2-cover-original.png)" -eq 1854126
printf '%s  %s\n' '947919e203f619e7c0c1de9695d4162ab19c23df8f4ba7d593a6cd100216ff2b' media/tabata-20261108-v2-cover-original.png | sha256sum --check
python3 - <<'PY'
import hashlib,json
from pathlib import Path
from PIL import Image
video=Path("media/tabata-20261108-2k-ig-vk.mp4")
original=Path("media/tabata-20261108-v2-cover-original.png")
meta=Path("media/tabata-20261108-v2-meta-cover.jpg")
vqa=json.loads(Path("results/verification/tabata-20261108-2k.json").read_text(encoding="utf8"))
r=json.loads(Path("requests/campaigns/tabata-20261108-v2.json").read_text(encoding="utf8"))
ig=json.loads(Path("requests/instagram-meta/tabata-20261108-v2-polonskayaaleksandra.json").read_text(encoding="utf8"))
def sha(file):
 with file.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
assert video.is_file() and video.stat().st_size==86051299
assert sha(video)=="f8bd7069cfb34cc9286f69c36015d634e23780209efb3da3ce9e830562d5d969"
assert vqa["ok"] is True and vqa["videoResolution"]=="1440x2560"
assert vqa["videoSha256"]==sha(video) and vqa["sourceSha256"]==r["sourceSHA256"]
assert r["id"]=="tabata-20261108-v2" and r["approved"] is True and r["publicContent"] is True and r["publishNow"] is True
assert r["coverSHA256"]==sha(original) and r["coverSHA256"]=="947919e203f619e7c0c1de9695d4162ab19c23df8f4ba7d593a6cd100216ff2b"
assert r["instagram"]=={"handle":"liniya__sporta","collaborators":["polonskayaaleksandra"],"nativeInviteRequired":True}
assert r["vk"]=={"groupId":48198173,"publishWall":True,"noCoauthor":True}
assert ig["text"]==r["caption"] and ig["collaborators"]==["polonskayaaleksandra"]
with Image.open(original) as img:
 assert img.size==(941,1672) and img.mode=="RGB"
 img.resize((1080,1920),Image.Resampling.LANCZOS).save(meta,format="JPEG",quality=100,subsampling=0,optimize=True)
with Image.open(meta) as cover:assert cover.size==(1080,1920) and cover.format=="JPEG"
assert meta.stat().st_size<8_000_000 and meta.stat().st_size>100_000
out={"id":"tabata-20261108-v2","ok":True,"stagingOnly":True,"published":False,
 "sourceSha256":vqa["sourceSha256"],"videoSha256":sha(video),"videoBytes":video.stat().st_size,
 "videoResolution":"1440x2560","videoFps":24,"videoBitrate":vqa["videoBitrate"],"videoCodec":"h264","audioCodec":"aac",
 "coverOriginalSha256":sha(original),"coverOriginalResolution":"941x1672",
 "coverMetaSha256":sha(meta),"coverMetaResolution":"1080x1920","coverMetaBytes":meta.stat().st_size,
 "captionSha256":hashlib.sha256(r["caption"].encode("utf8")).hexdigest(),
 "collaborator":"polonskayaaleksandra"}
Path("results/verification/tabata-20261108-v2.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print("TABATA_V2_MEDIA_QA_PASSED",json.dumps({"video":out["videoResolution"],"cover":out["coverMetaResolution"],"coverBytes":out["coverMetaBytes"],"sourceSHA256":out["sourceSha256"]}))
PY
git config user.name 'ls-tabata-v2-cover-stage'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add -- media/tabata-20261108-v2-cover-original.png media/tabata-20261108-v2-meta-cover.jpg results/verification/tabata-20261108-v2.json
git commit -m 'Stage exact revised TABATA cover with high quality Meta JPEG and QA [skip ci]'
git pull --rebase origin main
git push origin HEAD:main
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl --fail --silent --show-error --location --head --max-time 35 'https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/tabata-20261108-v2-meta-cover.jpg' >/dev/null && \
     curl --fail --silent --show-error --location --head --max-time 55 'https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/tabata-20261108-2k-ig-vk.mp4' >/dev/null; then
    echo 'TABATA_V2_VERIFIED_MEDIA_PUBLICLY_ACCESSIBLE_FOR_META'
    exit 0
  fi
  if [ "$i" -eq 10 ];then echo "::error::META_PUBLIC_COVER_OR_VIDEO_UNAVAILABLE"; exit 1;fi
  sleep 6
done
