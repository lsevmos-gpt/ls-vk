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
 # Reconstruct only baked-in subtitle glyphs from a REAL earlier frame (0.06 s),
 # in which the subtitles do not yet exist. The real person's face/hair/body
 # outside this tiny mask is byte-identical to the 0.725 s frame.
 target=np.asarray(im.convert('RGB')).copy()
 h,w=target.shape[:2]
 donor_path=ROOT/'media/reels-rc27-20261123/alie-early-fast/alie_1_60ms.jpg'
 if not donor_path.is_file():raise RuntimeError('clean_real_donor_frame_missing')
 with Image.open(donor_path) as d:
  donor=d.convert('RGB')
  if donor.height!=h or donor.width<w:raise RuntimeError('donor_frame_dimensions_incompatible')
  left=(donor.width-w)//2
  donor=np.asarray(donor.crop((left,0,left+w,h)),dtype=np.float32)
 # The verified white-glyph mask from the preceding inspection is now a map
 # for original pixels (not for diffusion/inpainting).
 mpath=DIR/'alie_subtitle_cleanup_mask.png'
 with Image.open(mpath) as m:
  mask=np.asarray(m.convert('L')).copy()
 if mask.shape!=(h,w):raise RuntimeError('glyph_mask_dimensions_bad')
 mask=cv2.dilate(mask,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(19,17)),iterations=1)
 restricted=np.zeros_like(mask)
 y0=int(h*.765);y1=int(h*.843)
 restricted[y0:y1,:]=mask[y0:y1,:]
 mask=restricted
 n=int(np.count_nonzero(mask))
 if n<3500 or n>175000:raise RuntimeError('donor_mask_bad_'+str(n))
 # Match exposure of the neighboring video frames in an unaffected shirt ROI.
 x0,x1=int(w*.36),int(w*.65)
 sy0,sy1=int(h*.62),int(h*.73)
 ref=target[sy0:sy1,x0:x1].astype(np.float32)
 prev=donor[sy0:sy1,x0:x1]
 delta=np.median((ref-prev).reshape(-1,3),axis=0)
 delta=np.clip(delta,-14,14)
 donor=np.clip(donor+delta,0,255)
 # Feather just the glyph edges; no rectangular wash, no generated pixels.
 alpha=cv2.GaussianBlur(mask,(0,0),sigmaX=2.6,sigmaY=2.6).astype(np.float32)/255.0
 result=np.uint8(np.clip(target.astype(np.float32)*(1-alpha[:,:,None])+
      donor*alpha[:,:,None],0,255))
 return Image.fromarray(result,'RGB'),Image.fromarray(mask,'L'),n

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
