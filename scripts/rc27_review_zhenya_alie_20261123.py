#!/usr/bin/env python3
"""Inspect uploaded original videos and output genuine frame contact sheets. Never publishes."""
from pathlib import Path
import json,subprocess,math,os,sys
from PIL import Image,ImageDraw,ImageFont
import concurrent.futures
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'media/reels-rc27-20261123'
SRC={'zhenya':Path('/tmp/rc27-zhenya.mp4'),'alie':Path('/tmp/rc27-alie.mp4')}
def check(call):
 p=subprocess.run(call,capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(str(p.stderr)[-900:])
 return p.stdout
def probe(p):
 return json.loads(check(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)]))
def sample(key, t, out):
 check(['ffmpeg','-hide_banner','-nostdin','-loglevel','error','-y','-ss',f'{t:.3f}',
        '-i',str(SRC[key]),'-frames:v','1','-update','1',str(out)])
def one(k,p):
 info=probe(p);dur=float(info['format']['duration'])
 v=next(x for x in info['streams'] if x['codec_type']=='video')
 if dur<2 or dur>900:raise RuntimeError(f'Unexpected video duration {dur} for {k}')
 # 30 real distinct timecodes spanning the whole clip, no generative frames.
 n=30
 ts=[max(0.2,min(dur-0.12,dur*(j+0.5)/n)) for j in range(n)]
 frames=OUT/k/'frames';frames.mkdir(parents=True,exist_ok=True)
 paths=[frames/f'frame_{j:02d}_{round(t*1000)}ms.jpg' for j,t in enumerate(ts)]
 def doit(record):j,t,path=record;sample(k,t,path)
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  list(pool.map(doit,[(j,t,paths[j]) for j,t in enumerate(ts)]))
 font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
 font=ImageFont.truetype(font_path,26)
 thumbs=[]
 for j,(t,pic) in enumerate(zip(ts,paths)):
  im=Image.open(pic).convert('RGB')
  im.thumbnail((360,590),Image.Resampling.LANCZOS)
  tile=Image.new('RGB',(380,650),(19,21,24))
  tile.paste(im,((380-im.width)//2,27+(600-im.height)//2))
  d=ImageDraw.Draw(tile)
  d.text((15,6),f'{j:02d} | {t:.2f}s',font=font,fill=(254,254,254))
  thumbs.append(tile)
 for s in range(3):
  sheet=Image.new('RGB',(4*380,3*650),(16,17,19))
  for z in range(12):
   j=s*12+z
   if j>=len(thumbs):break
   sheet.paste(thumbs[j],((z%4)*380,(z//4)*650))
  sheet.save(OUT/f'{k}_contact_{s+1}.jpg',quality=88,subsampling=0)
 return {'source':str(p),'duration_seconds':dur,'native':f"{v.get('width')}x{v.get('height')}",
         'fps':v.get('avg_frame_rate'),'codec':v.get('codec_name'),'times_seconds':[round(t,3) for t in ts],
         'frame_filenames':[q.name for q in paths],'sheets':[f'{k}_contact_{i+1}.jpg' for i in range(3)]}
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 data={k:one(k,p) for k,p in SRC.items()}
 (OUT/'frame_review.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
 print('RC27_REAL_VIDEO_FRAME_REVIEW',json.dumps({k:{'duration':x['duration_seconds'],'native':x['native'],'fps':x['fps']} for k,x in data.items()},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
