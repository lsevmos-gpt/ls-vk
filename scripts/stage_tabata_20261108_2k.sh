#!/usr/bin/env bash
set -euo pipefail
mkdir -p media results/verification /tmp/ls-tabata
python -m pip install --disable-pip-version-check 'Pillow>=10,<13'
command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null
echo 'Downloading exact native 4K TABATA video'
curl -fSsL --retry 2 --connect-timeout 20 --max-time 550 'https://at.adobe.com/zfg5Ao6KoN01Q9Sz' -o /tmp/ls-tabata/original.mp4
test "$(stat -c%s /tmp/ls-tabata/original.mp4)" -eq 501411605
printf '%s  %s\n' '9455b7574ca79cc684b9d92d2458b3b09c97e63b79cbf2dcf1ebf04659529f71' /tmp/ls-tabata/original.mp4 | sha256sum --check
echo 'Downloading exact approved original 2160x3840 PNG cover'
curl -fSsL --retry 2 --connect-timeout 20 --max-time 200 'https://at.adobe.com/s7r6LlnRXxBRZVl0' -o media/tabata-20261108-original-cover.png
test "$(stat -c%s media/tabata-20261108-original-cover.png)" -eq 4549624
printf '%s  %s\n' '46ba40861605ade03564f3413ccb40ea2a3533f29d5ceaca06453b612a29243b' media/tabata-20261108-original-cover.png | sha256sum --check
python3 - <<'PY'
from PIL import Image
import subprocess,json
data=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_name,codec_type,width,height,avg_frame_rate,color_transfer','-of','json','/tmp/ls-tabata/original.mp4']))
v=next(s for s in data['streams'] if s['codec_type']=='video')
a=next(s for s in data['streams'] if s['codec_type']=='audio')
assert (v['width'],v['height'],v['avg_frame_rate'],v['codec_name'])==(2160,3840,'24/1','h264')
assert a['codec_name']=='aac' and abs(float(data['format']['duration'])-51.904)<0.05
assert v.get('color_transfer') not in ('arib-std-b67','smpte2084')
with Image.open('media/tabata-20261108-original-cover.png') as i:
 assert i.size==(2160,3840)
 i.convert('RGB').save('media/tabata-20261108-meta-cover.jpg',format='JPEG',quality=97,subsampling=0,optimize=True)
print('NATIVE_SOURCE_AND_ORIGINAL_COVER_VERIFIED')
PY
ffmpeg -hide_banner -nostdin -loglevel error -stats -y -i /tmp/ls-tabata/original.mp4 -map 0:v:0 -map 0:a:0 -sn -dn -vf 'scale=1440:2560:flags=lanczos,format=yuv420p' -c:v libx264 -preset medium -profile:v high -level 5.1 -b:v 14000k -maxrate 16500k -bufsize 36000k -g 48 -keyint_min 24 -sc_threshold 0 -c:a aac -b:a 120k -ar 48000 -ac 2 -movflags +faststart media/tabata-20261108-2k-ig-vk.mp4
python3 - <<'PY'
import json,hashlib,subprocess
from pathlib import Path
from PIL import Image
p=Path('media/tabata-20261108-2k-ig-vk.mp4')
cover=Path('media/tabata-20261108-original-cover.png')
jpg=Path('media/tabata-20261108-meta-cover.jpg')
assert 45_000_000 < p.stat().st_size < 95_000_000, 'Video size outside verified 2K GitHub staging budget'
assert 1_000<jpg.stat().st_size<8_000_000
data=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,pix_fmt,bit_rate,sample_rate,channels','-of','json',str(p)]))
v=next(x for x in data['streams'] if x['codec_type']=='video')
a=next(x for x in data['streams'] if x['codec_type']=='audio')
assert (v['width'],v['height'],v['avg_frame_rate'],v['codec_name'],v['pix_fmt'])==(1440,2560,'24/1','h264','yuv420p')
assert a['codec_name']=='aac' and a['sample_rate']=='48000' and a['channels']==2
assert abs(float(data['format']['duration'])-51.904)<0.3
assert 8_000_000<int(v['bit_rate'])<25_000_000
with Image.open(jpg) as img: assert img.size==(2160,3840)
def sha(f):
 with f.open('rb') as handle: return hashlib.file_digest(handle,'sha256').hexdigest()
qa={'id':'tabata-20261108-2k','ok':True,'stagingOnly':True,'published':False,
 'sourceSha256':'9455b7574ca79cc684b9d92d2458b3b09c97e63b79cbf2dcf1ebf04659529f71',
 'sourceBytes':501411605,'sourceResolution':'2160x3840',
 'coverOriginalSha256':sha(cover),'coverOriginalResolution':'2160x3840',
 'videoResolution':'1440x2560','videoFps':24,'videoCodec':'h264','audioCodec':'aac',
 'videoBitrate':int(v['bit_rate']),'videoSha256':sha(p),'videoBytes':p.stat().st_size,
 'coverMetaSha256':sha(jpg),'coverMetaBytes':jpg.stat().st_size,
 'nativeCollaborator':'polonskayaaleksandra'}
Path('results/verification/tabata-20261108-2k.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
print('TABATA_TRUE_2K_VERIFIED',json.dumps({'bytes':qa['videoBytes'],'bitrate':qa['videoBitrate'],'coverBytes':qa['coverMetaBytes']}))
PY
git config user.name 'ls-tabata-media-stage'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add -- media/tabata-20261108-2k-ig-vk.mp4 media/tabata-20261108-original-cover.png media/tabata-20261108-meta-cover.jpg results/verification/tabata-20261108-2k.json
git commit -m 'Stage original approved TABATA 2K and cover [skip ci]'
git pull --rebase origin main
git push origin HEAD:main
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsSLI --max-time 60 'https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/tabata-20261108-2k-ig-vk.mp4' >/dev/null && curl -fsSLI --max-time 30 'https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/tabata-20261108-meta-cover.jpg' >/dev/null; then
    echo 'TABATA_PUBLIC_ASSETS_READY'
    break
  fi
  if [ "$attempt" -eq 10 ]; then echo '::error::PUBLIC_MEDIA_HOST_UNAVAILABLE'; exit 1; fi
  sleep 8
done
