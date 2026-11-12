#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
JOB='anna-new-coach-20261112'
SOURCE='/tmp/ls-anna/anna-original.mov'
COVER='/tmp/ls-anna/anna-cover-original.png'
VIDEO="media/$JOB-reel-1080x1920.mp4"
META_COVER="media/$JOB-cover-meta.jpg"
PNG_COVER="media/$JOB-cover-original-1080x1920.png"
SOURCE_SHA='3feefb603e8112d907e1f7c09f4abfb903552fe8b732296008501a972f8a5366'
COVER_SHA='c8f39bdce905dbe0db1085432e179e7132e2e801f4ecbe08c15db6f128f8ae59'
mkdir -p media results/verification /tmp/ls-anna
python -m pip install --disable-pip-version-check 'Pillow>=10,<13'
echo 'Stage exact approved Anna media through existing Adobe media handoff; never publish during staging'
curl --fail --silent --show-error --location --retry 2 --connect-timeout 25 --max-time 500 'https://at.adobe.com/ej1XwhyzMvxuDxJH' -o "$SOURCE"
curl --fail --silent --show-error --location --retry 2 --connect-timeout 25 --max-time 240 'https://at.adobe.com/NHahx8nZL9qiniyP' -o "$COVER"
test "$(stat -c%s "$SOURCE")" -eq 63914801
test "$(stat -c%s "$COVER")" -eq 2537844
printf '%s  %s\n' "$SOURCE_SHA" "$SOURCE" | sha256sum --check
printf '%s  %s\n' "$COVER_SHA" "$COVER" | sha256sum --check
python3 - <<'PY'
import json,subprocess
from PIL import Image
from pathlib import Path
p=Path('/tmp/ls-anna/anna-original.mov')
d=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,codec_name,width,height,pix_fmt,avg_frame_rate,sample_rate,channels','-of','json',str(p)]))
v=next(s for s in d['streams'] if s['codec_type']=='video')
a=next(s for s in d['streams'] if s['codec_type']=='audio')
assert (v['width'],v['height'],v['codec_name'],v['avg_frame_rate'],v['pix_fmt'])==(1080,1920,'h264','25/1','yuv420p'),v
assert a['codec_name']=='pcm_s24le' and a['sample_rate']=='48000' and a['channels']==2,a
assert abs(float(d['format']['duration'])-29.12)<0.10,d
with Image.open('/tmp/ls-anna/anna-cover-original.png') as src:
 assert src.size==(941,1672),src.size
 im=src.convert('RGB').resize((1080,1920),Image.Resampling.LANCZOS)
 im.save('media/anna-new-coach-20261112-cover-original-1080x1920.png','PNG',optimize=True)
 im.save('media/anna-new-coach-20261112-cover-meta.jpg','JPEG',quality=100,subsampling=0,optimize=True)
print('ANNA_SOURCE_ORIGINAL_AND_USER_APPROVED_COVER_VERIFIED')
PY
# Preserve every original H.264 video packet; only PCM audio needs AAC conversion.
ffmpeg -hide_banner -nostdin -loglevel error -y -i "$SOURCE" -map 0:v:0 -map 0:a:0 -sn -dn -c:v copy -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart "$VIDEO"
python3 - <<'PY'
import hashlib,json,subprocess
from pathlib import Path
from PIL import Image
job='anna-new-coach-20261112'
source=Path('/tmp/ls-anna/anna-original.mov')
orig=Path('/tmp/ls-anna/anna-cover-original.png')
v=Path('media/'+job+'-reel-1080x1920.mp4')
c=Path('media/'+job+'-cover-meta.jpg')
p=Path('media/'+job+'-cover-original-1080x1920.png')
def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def media_info(path):
 return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,pix_fmt,sample_rate,channels,bit_rate','-of','json',str(path)]))
d=media_info(v)
s=media_info(source)
vd=next(x for x in d['streams'] if x['codec_type']=='video')
ad=next(x for x in d['streams'] if x['codec_type']=='audio')
def streamhash(path):
 return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:v:0','-c:v','copy','-f','streamhash','-hash','sha256','-'],text=True).strip()
stream_source=streamhash(source)
stream_pub=streamhash(v)
assert stream_source==stream_pub and 'c35d05f9da067d980a74f7361fa9650f4d209979b43cdb987ab1bd2a60269b5b' in stream_pub,(stream_source,stream_pub)
assert (vd['width'],vd['height'],vd['avg_frame_rate'],vd['codec_name'])==(1080,1920,'25/1','h264'),vd
assert ad['codec_name']=='aac' and ad['sample_rate']=='48000' and ad['channels']==2,ad
assert abs(float(d['format']['duration'])-29.12)<0.15
assert 48_000_000<v.stat().st_size<65_000_000
with Image.open(c) as i:assert i.size==(1080,1920) and i.format=='JPEG'
with Image.open(p) as i:assert i.size==(1080,1920) and i.format=='PNG'
r={'id':job,'ok':True,'stagingOnly':True,'published':False,
'sourceSha256':sha(source),'sourceBytes':source.stat().st_size,'sourceResolution':'1080x1920','sourceFps':25,
'videoSha256':sha(v),'videoBytes':v.stat().st_size,'videoResolution':'1080x1920','videoFps':25,
'videoCodec':'h264','videoBitrate':int(vd['bit_rate']),'audioCodec':'aac','audioBitrate':int(ad['bit_rate']),
'videoStreamUnchanged':True,'videoStreamSha256':stream_pub,
'coverOriginalSha256':sha(orig),'coverOriginalResolution':'941x1672',
'coverMetaSha256':sha(c),'coverMetaBytes':c.stat().st_size,'coverMetaResolution':'1080x1920',
'coverPngSha256':sha(p)}
Path('results/verification/'+job+'.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('ANNA_STAGED_QUALITY_VERIFIED',json.dumps({'source':r['sourceSha256'],'video':r['videoSha256'],'cover':r['coverMetaSha256'],'streamPreserved':True},ensure_ascii=False))
PY
git config user.name 'ls-anna-media-stage'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add -- "$VIDEO" "$META_COVER" "$PNG_COVER" "results/verification/$JOB.json"
git commit -m 'Stage approved Anna original H264 and cover for timed Meta/VK [skip ci]'
for i in 1 2 3 4 5 6; do
 if git pull --rebase origin main && git push origin HEAD:main; then break;fi
 if [[ "$i" -eq 6 ]];then echo '::error::ANNA_ASSET_STAGE_FAILED';exit 1;fi
 sleep "$i"
done
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
 if curl -fsSLI --max-time 55 "https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/$VIDEO" >/dev/null && \
    curl -fsSLI --max-time 45 "https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/$META_COVER" >/dev/null; then
   echo 'ANNA_VIDEO_AND_COVER_READY_FOR_DIRECT_META_VK'
   exit 0
 fi
 if [[ "$i" -eq 12 ]];then echo '::error::ANNA_PUBLIC_MEDIA_HOST_UNAVAILABLE';exit 1;fi
 sleep 8
done
