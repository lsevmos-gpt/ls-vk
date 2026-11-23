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
 x0,x1=int(w*.221),int(w*.824)
 y0,y1=int(h*.769),int(h*.840)
 patch=a[y0:y1,x0:x1]
 # Pure neutral-white subtitle core, not the warmer cream fabric or skin.
 rgb=patch.astype(np.int16)
 core=(rgb[:,:,0]>238)&(rgb[:,:,1]>238)&(rgb[:,:,2]>236)&((rgb.max(2)-rgb.min(2))<13)
 local=np.uint8(core)*255
 # Expand text cores to cover their antialiased glow; NO rectangular reconstruction.
 local=cv2.dilate(local,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(11,9)),iterations=1)
 # Limit to baseline text line; avoid image elements outside.
 outer=np.zeros_like(local)
 start=max(0,int(h*.775)-y0);end=min(local.shape[0],int(h*.830)-y0)
 outer[start:end,:]=local[start:end,:]
 mask=np.zeros((h,w),dtype=np.uint8)
 mask[y0:y1,x0:x1]=outer
 changed=int(np.count_nonzero(mask))
 if changed<2100 or changed>190000:raise RuntimeError('subtitle_pixel_mask_out_of_bounds_'+str(changed))
 result=cv2.inpaint(a,mask,5,cv2.INPAINT_TELEA)
 return Image.fromarray(result,'RGB'),Image.fromarray(mask,'L'),changed

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
