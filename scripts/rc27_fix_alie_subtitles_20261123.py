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
 # This is the known bounded lower-torso subtitle strip from the original 0.725 s frame.
 # IMPORTANT: outside these coordinates, including the whole face and all visible hands,
 # pixels remain untouched; no generative face/body reconstruction.
 x0,x1=int(w*.238),int(w*.802)
 y0,y1=int(h*.779),int(h*.831)
 mask=np.zeros((h,w),np.uint8)
 cv2.rectangle(mask,(x0,y0),(x1,y1),255,-1)
 # Telea local content-aware fill, with a feathered mask boundary to prevent seams.
 cleaned=cv2.inpaint(a,mask,12,cv2.INPAINT_TELEA)
 alpha=cv2.GaussianBlur(mask,(0,0),sigmaX=9,sigmaY=9).astype(np.float32)/255
 blended=np.uint8(np.clip(a*(1-alpha[:,:,None])+cleaned*alpha[:,:,None],0,255))
 return Image.fromarray(blended,'RGB'),Image.fromarray(mask,'L'),int(np.count_nonzero(mask))

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
