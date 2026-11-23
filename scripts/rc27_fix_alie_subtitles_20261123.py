#!/usr/bin/env python3
"""Refine ONLY baked subtitles in genuine Alie frame, rebuilding same RC2.7 layers from saved sources."""
from pathlib import Path
from PIL import Image
import base64,hashlib,re,json,numpy as np,cv2
from scripts import rc27_render_zhenya_alie_20261123 as rc
ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/'media/reels-rc27-20261123/final/alie'
RAW=DIR/'alie_raw_video_frame_native.png'
EDIT=DIR/'alie_editable_layers.svg'
QA=DIR/'alie_QA_RC27.json'
EXPECTED_LOGO='e145980feff7d744c5c718aa7f0f59a47fc992fdad7f2260906b98c81e2ecb39'

def cleanup(im):
 a=np.asarray(im.convert('RGB')).copy()
 h,w=a.shape[:2]
 y0=int(h*.773);y1=int(h*.846)
 x0=int(w*.205);x1=int(w*.825)
 roi=a[y0:y1,x0:x1]
 rgb=roi.astype(np.int16)
 spread=rgb.max(axis=2)-rgb.min(axis=2)
 # High neutral-white is the burned-in subtitle, not the warm studio fabric.
 glyph=np.uint8((rgb[:,:,0]>224)&(rgb[:,:,1]>224)&(rgb[:,:,2]>223)&(spread<19))*255
 n,lab,stats,_=cv2.connectedComponentsWithStats(glyph,8)
 components=np.zeros_like(glyph)
 for i in range(1,n):
  xx,yy,cw,ch,area=stats[i]
  if 7<=area<=14500 and 2<=ch<=95 and 1<=cw<=880:
   components[lab==i]=255
 # Keep extraction ONLY on line carrying the subtitle (not skin/hair/other scene).
 restrict=np.zeros_like(components)
 top=max(0,int(h*.780)-y0)
 bottom=min(restrict.shape[0],int(h*.837)-y0)
 restrict[top:bottom,:]=components[top:bottom,:]
 restrict=cv2.dilate(restrict,np.ones((9,7),np.uint8),iterations=1)
 mask=np.zeros((h,w),np.uint8)
 mask[y0:y1,x0:x1]=restrict
 num=int(np.count_nonzero(mask))
 if not 2500<num<260000:raise RuntimeError('subtitle_mask_unexpected_area_'+str(num))
 b=cv2.inpaint(a,mask,7,cv2.INPAINT_TELEA)
 return Image.fromarray(b,'RGB'),Image.fromarray(mask,'L'),num

def main():
 assert RAW.exists() and EDIT.exists() and QA.exists()
 # The SVG embeds the ORIGINAL, unmodified, SHA-verified fitness master logo.
 s=EDIT.read_text('utf8')
 matches=re.findall('href="data:image/png;base64,([^"]+)"',s)
 if len(matches)!=1:raise RuntimeError('original_logo_not_uniquely_found')
 logo_bytes=base64.b64decode(matches[0],validate=True)
 if hashlib.sha256(logo_bytes).hexdigest()!=EXPECTED_LOGO:raise RuntimeError('fitness_logo_sha256_mismatch')
 import io
 logo=Image.open(io.BytesIO(logo_bytes)).convert('RGBA')
 original=rc.video_frame
 retouch=rc.remove_alie_subtitle
 try:
  # The full native frame was saved unchanged by the first build.
  rc.video_frame=lambda src,t,dest: None if Path(dest).exists() else (_ for _ in ()).throw(RuntimeError('native_frame_missing'))
  rc.remove_alie_subtitle=cleanup
  frames=json.loads((ROOT/'media/reels-rc27-20261123/frame_review.json').read_text('utf8'))
  evidence={'reviewed_timecodes':{'alie':frames['alie']['times_seconds']}}
  q=rc.cover('alie',Path('/tmp/rc27-alie.mp4'),'АЛИЕ',0.725,logo,logo_bytes,evidence,rc.fontpath())
 finally:
  rc.video_frame=original
  rc.remove_alie_subtitle=retouch
 (DIR/'alie_QA_RC27.json').write_text(json.dumps({**q,'revision':'second refined text-mask pass; original real frame preserved','C13_cleanup':'PENDING_HUMAN_VISUAL_REVIEW'},ensure_ascii=False,indent=2),encoding='utf8')
 print('ALIE_RETOUCH_PASS2',json.dumps({'masked_pixels':q['subtitle_mask_changed_pixels'],'output':q['master_png']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
