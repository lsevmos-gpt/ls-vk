#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p media results/verification /tmp/ls-vlad
python -m pip install --disable-pip-version-check 'Pillow>=10,<13'

SOURCE='/tmp/ls-vlad/vlad-original.mov'
COVER='/tmp/ls-vlad/vlad-cover-original.png'
VIDEO='media/vlad-news-20261109-reel-1080x1920.mp4'
META_COVER='media/vlad-news-20261109-cover-meta.jpg'

echo 'Download original approved Vlad video and exact approved cover using yesterday media transfer channel'
curl --fail --silent --show-error --location --retry 2 --connect-timeout 25 --max-time 500 'https://at.adobe.com/WKS3zaRET2cbv056' -o "$SOURCE"
curl --fail --silent --show-error --location --retry 2 --connect-timeout 25 --max-time 230 'https://at.adobe.com/pxPNQu1hI9ehIpiA' -o "$COVER"
test "$(stat -c%s "$SOURCE")" -eq 54910580
test "$(stat -c%s "$COVER")" -eq 3193049
printf '%s  %s\n' '0ae828d45a93f1cb194294ab4c34ac60a3a91ea9785081987ea5e81d7b95ef74' "$SOURCE" | sha256sum --check
printf '%s  %s\n' 'e9325f8f0df778a4ce33c99fe2d0d5dd703cae5968ed01f14c2d0941d7e657bd' "$COVER" | sha256sum --check

python3 - <<'PY'
import json,subprocess
from PIL import Image
from pathlib import Path
p=Path('/tmp/ls-vlad/vlad-original.mov')
d=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,codec_name,width,height,pix_fmt,avg_frame_rate,sample_rate,channels','-of','json',str(p)]))
v=next(s for s in d['streams'] if s['codec_type']=='video')
a=next(s for s in d['streams'] if s['codec_type']=='audio')
assert (v['width'],v['height'],v['codec_name'],v['avg_frame_rate'],v['pix_fmt'])==(1080,1920,'h264','25/1','yuv420p'),v
assert a['codec_name']=='pcm_s24le' and a['sample_rate']=='48000' and a['channels']==2,a
assert abs(float(d['format']['duration'])-25.2)<0.07
with Image.open('/tmp/ls-vlad/vlad-cover-original.png') as im:
 assert im.size==(1080,1920), im.size
 im.convert('RGB').save('media/vlad-news-20261109-cover-meta.jpg','JPEG',quality=100,subsampling=0,optimize=True)
print('VLAD_AUTHENTIC_1080x1920_25FPS_AND_APPROVED_COVER_VERIFIED')
PY

# Copy original H.264 compressed video bytes; only PCM audio needs a Meta/VK-compatible AAC encoding.
ffmpeg -hide_banner -nostdin -loglevel error -y -i "$SOURCE" -map 0:v:0 -map 0:a:0 -sn -dn -c:v copy -c:a aac -b:a 128k -ar 48000 -ac 2 -movflags +faststart "$VIDEO"

python3 - <<'PY'
import json,hashlib,subprocess
from pathlib import Path
from PIL import Image
p=Path('media/vlad-news-20261109-reel-1080x1920.mp4')
c=Path('media/vlad-news-20261109-cover-meta.jpg')
def sha(x):
 with x.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
d=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,pix_fmt,sample_rate,channels,bit_rate','-of','json',str(p)]))
v=next(s for s in d['streams'] if s['codec_type']=='video')
a=next(s for s in d['streams'] if s['codec_type']=='audio')
assert 40_000_000<p.stat().st_size<70_000_000,p.stat().st_size
assert (v['width'],v['height'],v['codec_name'],v['avg_frame_rate'])==(1080,1920,'h264','25/1')
assert a['codec_name']=='aac' and a['sample_rate']=='48000' and a['channels']==2,a
assert 0<int(a.get('bit_rate') or 0)<160_000,a
assert abs(float(d['format']['duration'])-25.2)<0.15
with Image.open(c) as i:assert i.size==(1080,1920) and i.format=='JPEG'
source_sha='0ae828d45a93f1cb194294ab4c34ac60a3a91ea9785081987ea5e81d7b95ef74'
cover_sha='e9325f8f0df778a4ce33c99fe2d0d5dd703cae5968ed01f14c2d0941d7e657bd'
r={'id':'vlad-news-20261109','ok':True,'stagingOnly':True,'published':False,
'sourceSha256':source_sha,'sourceBytes':54910580,'sourceResolution':'1080x1920','sourceFps':25,
'videoSha256':sha(p),'videoBytes':p.stat().st_size,'videoResolution':'1080x1920','videoFps':25,
'videoCodec':'h264','videoBitrate':int(v['bit_rate']),'audioCodec':'aac','audioBitrate':int(a['bit_rate']),
'videoStreamUnchanged':True,'coverOriginalSha256':cover_sha,'coverOriginalResolution':'1080x1920',
'coverMetaSha256':sha(c),'coverMetaBytes':c.stat().st_size,'coverMetaResolution':'1080x1920'}
Path('results/verification/vlad-news-20261109.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('VLAD_MAX_NATIVE_VIDEO_QA',json.dumps({'videoBytes':r['videoBytes'],'resolution':r['videoResolution'],'bitrate':r['videoBitrate'],'coverBytes':r['coverMetaBytes'],'videoSha256':r['videoSha256']}))
PY

git config user.name 'ls-vlad-media-stage'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add -- "$VIDEO" "$META_COVER" results/verification/vlad-news-20261109.json
git commit -m 'Stage exact Vlad news original H264 and approved cover for native Meta/VK [skip ci]'
for i in 1 2 3 4 5 6; do
 if git pull --rebase origin main && git push origin HEAD:main; then break;fi
 if [[ "$i" -eq 6 ]];then echo '::error::VLAD_GITHUB_ASSET_STAGE_FAILED';exit 1;fi
 sleep "$i"
done
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
 if curl -fsSLI --max-time 55 'https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/vlad-news-20261109-reel-1080x1920.mp4' >/dev/null && \
    curl -fsSLI --max-time 45 'https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/vlad-news-20261109-cover-meta.jpg' >/dev/null; then
   echo 'VLAD_APPROVED_VIDEO_AND_COVER_PUBLIC_FOR_META'
   exit 0
 fi
 if [[ "$i" -eq 12 ]];then echo '::error::VLAD_PUBLIC_MEDIA_HOST_UNAVAILABLE';exit 1;fi
 sleep 8
done
