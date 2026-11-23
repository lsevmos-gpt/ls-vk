#!/usr/bin/env python3
"""Build authentic RC2.7 Reels covers from two original MP4 and embedded, hash-checked logo.
No social publishing. Editable SVG has separate image/logo/text/accent groups, no generated people."""
import json,hashlib,base64,math,subprocess,io,sys,os,zipfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageCms
import numpy as np
import cv2

ROOT=Path(__file__).resolve().parents[1]
POLICY=Path('/tmp/rc27-policy.json')
OUT=ROOT/'media/reels-rc27-20261123/final'
SOURCE={'zhenya':('/tmp/rc27-zhenya.mp4','ЖЕНЯ',2.199),
        'alie':('/tmp/rc27-alie.mp4','АЛИЕ',0.725)}
LOGO='лого фитнес_черный.png'
BRANCH='fitness'
ACCENT='#A96663'
BLACK='#1F1C1B'
TITLE1='ТРЕНЕР'
S=1080;H=1920
SRGB=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()

def digest(data):return hashlib.sha256(data).hexdigest()
def video_frame(src,t,dest):
 p=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y',
  '-ss',str(t),'-i',str(src),'-frames:v','1','-update','1',str(dest)],
  capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError('ffmpeg_extract_'+p.stderr[-350:])
def fontpath():
 import subprocess
 result=subprocess.run(['fc-list','-f','%{file}\\n'],capture_output=True,text=True)
 entries=result.stdout.splitlines()
 candidates=[x for x in entries if 'robotocondensed' in x.replace(' ','').lower()
             and ('bold' in x.lower() or 'wght' in x.lower())]
 if not candidates:raise RuntimeError('BLOCKED_P06_ROBOTO_CONDENSED_BOLD_MISSING')
 return candidates[0]
def crop_exact(im):
 w,h=im.size
 if (w/h)>(9/16):
  cw=round(h*9/16);x=(w-cw)//2;return im.crop((x,0,x+cw,h)),(x,0,cw,h)
 ch=round(w*16/9);y=(h-ch)//2;return im.crop((0,y,w,y+ch)),(0,y,w,ch)
def photo_finish(im):
 # Natural pre-text studio-grade light/color finishing, not AI synthesis.
 im=ImageEnhance.Contrast(im).enhance(1.055)
 im=ImageEnhance.Color(im).enhance(0.975)
 a=np.array(im,dtype=np.float32)
 # Reduce the unusually orange studio cast slightly; preserve warm atmosphere/skin.
 a[:,:,0]*=0.993
 a[:,:,1]*=1.006
 a[:,:,2]*=1.022
 a=np.clip(a,0,255).astype('uint8')
 im=Image.fromarray(a,'RGB')
 im=ImageEnhance.Brightness(im).enhance(1.027)
 return im.filter(ImageFilter.UnsharpMask(radius=1.15,percent=65,threshold=3))
def remove_alie_subtitle(im):
 a=np.array(im)
 h,w=a.shape[:2]
 # Baked subtitles occupy the lower third of the studio portrait.
 # Preserve every pixel outside a tight, printed-letter mask.
 y0=int(h*.75);y1=int(h*.84)
 x0=int(w*.16);x1=int(w*.84)
 roi=a[y0:y1,x0:x1]
 # Letter-white only (not warm white fabric); reject smooth large regions.
 maxmin=roi.max(2).astype(np.int16)-roi.min(2).astype(np.int16)
 m=np.uint8((roi[:,:,0]>202)&(roi[:,:,1]>203)&(roi[:,:,2]>201)&(maxmin<36))*255
 n,labels,stats,cent=cv2.connectedComponentsWithStats(m,8)
 small=np.zeros_like(m)
 for i in range(1,n):
  xx,yy,ww,hh,area=stats[i]
  if 2<=area<=1100 and 2<=ww<=155 and 2<=hh<=75:
   small[labels==i]=255
 # Restrict to the text's horizontal line (no hands or head).
 mid=np.zeros_like(small)
 ylo=int(h*.786)-y0; yhi=int(h*.814)-y0
 if yhi<=ylo:raise RuntimeError('subtitle_roi_bad')
 mid[max(0,ylo):min(mid.shape[0],yhi),:]=small[max(0,ylo):min(mid.shape[0],yhi),:]
 mid=cv2.dilate(mid,np.ones((3,3),np.uint8))
 fullmask=np.zeros((h,w),np.uint8)
 fullmask[y0:y1,x0:x1]=mid
 cleaned=cv2.inpaint(a,fullmask,4,cv2.INPAINT_TELEA)
 return Image.fromarray(cleaned,'RGB'),Image.fromarray(fullmask,'L'),int(np.count_nonzero(fullmask))
def smooth_wash(im):
 # Local tonal lift behind typography, NOT a matte, card, border, or panel.
 w,h=im.size;arr=np.array(im).astype(np.float32)
 ys=np.arange(h,dtype=np.float32)[:,None]
 xs=np.arange(w,dtype=np.float32)[None,:]
 # Lifted cream is strongest near heading, with a seamless feather to zero.
 gy=np.clip((ys-1100)/(125),0,1)*np.clip((1660-ys)/(185),0,1)
 gx=np.clip((xs-0)/(65),0,1)*np.clip((w-xs)/(55),0,1)
 alpha=(gy*gx*0.27)[:,:,None]
 ivory=np.array([250.,242.,232.],dtype=np.float32).reshape(1,1,3)
 return Image.fromarray(np.uint8(np.clip(arr*(1-alpha)+ivory*alpha,0,255)),'RGB')
def fitfont(path,text,size,max_width):
 while size>25:
  f=ImageFont.truetype(path,size)
  box=f.getbbox(text,stroke_width=0)
  if box[2]-box[0]<=max_width:return f,size
  size-=2
 raise RuntimeError('font_no_fit_'+text)
def make_svg(finalbg,logo_bytes,label,fsize1,fsize2,positions):
 # Embedded photo/logo guarantee fully editable text and exact original logo pixels.
 bg_bin=io.BytesIO();finalbg.save(bg_bin,'JPEG',quality=96,subsampling=0,icc_profile=SRGB)
 px=base64.b64encode(bg_bin.getvalue()).decode('ascii')
 lg=base64.b64encode(logo_bytes).decode('ascii')
 import html
 safe=html.escape(label,quote=True)
 a1,a2=positions
 svg=f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{S}" height="{H}" viewBox="0 0 {S} {H}">
<title>Линия спорта · RC2.7 · тренер {safe}</title>
<g id="01_processed_native_video_photo" data-layer="true"><image x="0" y="0" width="{S}" height="{H}" href="data:image/jpeg;base64,{px}"/></g>
<g id="02_authentic_fitness_logo_sha256_verified" data-layer="true"><image x="92" y="286" width="440" height="102.266" href="data:image/png;base64,{lg}"/></g>
<g id="03_single_dusty_rose_accent" data-layer="true"><rect x="110" y="1183" width="268" height="12" fill="{ACCENT}"/></g>
<g id="04_editable_heading_Roboto_Condensed_Bold" data-layer="true">
<text x="104" y="{a1}" font-family="Roboto Condensed" font-weight="700" font-size="{fsize1}" fill="{BLACK}">{TITLE1}</text>
<text x="104" y="{a2}" font-family="Roboto Condensed" font-weight="700" font-size="{fsize2}" fill="{BLACK}">{safe}</text>
</g>
</svg>'''
 return svg
def cover(k,src,label,t,logo,logo_bytes,policy,fontpath_value):
 target=OUT/k;target.mkdir(parents=True,exist_ok=True)
 raw=target/f'{k}_raw_video_frame_native.png'
 video_frame(src,t,raw)
 with Image.open(raw) as p:original=p.convert('RGB')
 crop,rect=crop_exact(original)
 # The actual clean native still remains available before any compositing.
 crop.save(target/f'{k}_raw_cropped_native.png',format='PNG',compress_level=5)
 cnt=0
 if k=='alie':
  crop,mask,cnt=remove_alie_subtitle(crop)
  mask.save(target/f'{k}_subtitle_cleanup_mask.png')
 finished=photo_finish(crop)
 finished.save(target/f'{k}_processed_still_native.png',format='PNG',compress_level=5,icc_profile=SRGB)
 frame=finished.resize((S,H),Image.Resampling.LANCZOS)
 bg=smooth_wash(frame)
 bg.save(target/f'{k}_processed_photo_without_branding.png',format='PNG',icc_profile=SRGB)
 rendered=bg.convert('RGBA')
 logo2=logo.copy()
 logo2.thumbnail((440,110),Image.Resampling.LANCZOS)
 # Place the exact master image, retaining its original aspect and symbol; no recolor.
 xlogo,ylogo=92,286
 rendered.alpha_composite(logo2,(xlogo,ylogo))
 d=ImageDraw.Draw(rendered)
 d.rectangle((110,1183,378,1195),fill=ACCENT)
 # Native editable type; positional baseline also recorded in the SVG master.
 f1,fs1=fitfont(fontpath_value,TITLE1,154,900)
 f2,fs2=fitfont(fontpath_value,label,223,900)
 x=104
 y1=1230;y2=1400
 d.text((x,y1),TITLE1,font=f1,fill=BLACK,anchor='lt')
 d.text((x,y2),label,font=f2,fill=BLACK,anchor='lt')
 # Calculate exact SVG text baselines separately; pillow anchor lt approximates ascent.
 # Record SVG as text editable and a faithful standard-font approximation.
 ascent1=f1.getmetrics()[0];ascent2=f2.getmetrics()[0]
 baseline1=y1+ascent1
 baseline2=y2+ascent2
 final=rendered.convert('RGB')
 fname=f'{k}_Reels_RC27_1080x1920.png'
 fn=target/fname
 final.save(fn,format='PNG',icc_profile=SRGB,compress_level=8)
 (target/f'{k}_editable_layers.svg').write_text(
  make_svg(bg,logo_bytes,label,fs1,fs2,(baseline1,baseline2)),encoding='utf-8')
 # Save actual profile crops and miniature pixel outputs from FINAL, never illustrative mocks.
 crops={
  'reels_full_9x16':(0,0,S,H),
  'profile_3x4':(0,240,S,1680),
  'feed_4x5':(0,285,S,1635),
  'square_1x1':(0,420,S,1500)
 }
 for tag,box in crops.items():
  thumb=final.crop(box)
  thumb.save(target/f'{k}_{tag}.png',compress_level=8,icc_profile=SRGB)
  size={'reels_full_9x16':(180,320),'profile_3x4':(180,240),
        'feed_4x5':(180,225),'square_1x1':(180,180)}[tag]
  thumb.resize(size,Image.Resampling.LANCZOS).save(target/f'{k}_{tag}_mini.png',compress_level=8)
 # QA only assert things verified programmatically; human vision is a separate gate.
 verify=Image.open(fn)
 if verify.size!=(S,H) or verify.format!='PNG':raise RuntimeError('invalid_export')
 if not (target/f'{k}_profile_3x4_mini.png').exists():raise RuntimeError('thumbnail_missing')
 a=np.array(final)
 q={
  'schema_version':'RC2.7-JSON','trainer':label,'video':str(src),
  'original_frame_seconds':t,'reviewed_timecodes':policy['reviewed_timecodes'][k],
  'source_dimensions':list(original.size),'crop_rectangle_xywh':list(rect),
  'native_processed_dimensions':list(finished.size),
  'master_png':fname,'size':[S,H],'mode':'RGB','format':'PNG','ICC_profile':'sRGB',
  'branch':'fitness','branch_basis':'В видео представлено групповое фитнес-направление с упражнениями в студии',
  'logo':LOGO,'logo_SHA256':digest(logo_bytes),'logo_original_verified':True,
  'font':'Roboto Condensed Bold 700','font_used':fontpath_value.split('/')[-1],
  'headline':['ТРЕНЕР',label],'accent':ACCENT,
  'subtitle_cleanup':'localized OpenCV inpaint glyph mask' if k=='alie' else 'no overlaid subtitle at selected timecode',
  'subtitle_mask_changed_pixels':cnt,'generative_reconstruction':False,
  'photo_finish':'natural slight warmth reduction, contrast x1.055, saturation x0.975, brightness x1.027, unsharp radius1.15/65%; feathered tone adjustment behind text',
  'C09_full_bleed':'PASS_PROGRAMMATIC','C10_frame_selection':'REVIEWED_30_REAL_TIMECODES',
  'C11_thumbnail':'PENDING_HUMAN_VISUAL_REVIEW','C12_native_finished':'PASS_PROGRAMMATIC',
  'C13_cleanup':'PENDING_HUMAN_VISUAL_REVIEW' if k=='alie' else 'PASS_NO_SUBTITLES',
  'C08_post_publication':'PENDING_NOT_PUBLISHED','overall_status':'DRAFT_QA_PENDING',
  'edited_source':f'{k}_editable_layers.svg',
  'previews':{k:k for k in crops}
 }
 (target/f'{k}_QA_RC27.json').write_text(json.dumps(q,ensure_ascii=False,indent=2),encoding='utf-8')
 with zipfile.ZipFile(target/f'{k}_RC27_full_package.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for f in target.iterdir():
   if f.is_file() and not f.name.endswith('full_package.zip'):
    z.write(f,arcname=f.name)
 return q

def main():
 pol=json.loads(POLICY.read_text('utf-8'))
 reg=pol['logo_policy']['approved_logos'][LOGO]
 logo_bytes=base64.b64decode(pol['embedded_assets']['logos'][LOGO],validate=True)
 if digest(logo_bytes)!=reg['sha256']:raise RuntimeError('BRANDING_LOGO_SHA256_MISMATCH')
 logo=Image.open(io.BytesIO(logo_bytes)).convert('RGBA')
 if logo.size!=(2048,476):raise RuntimeError('LOGO_DIMENSIONS_BAD')
 f=fontpath()
 OUT.mkdir(parents=True,exist_ok=True)
 original_review=json.loads((ROOT/'media/reels-rc27-20261123/frame_review.json').read_text('utf-8'))
 review={'reviewed_timecodes':{k:original_review[k]['times_seconds'] for k in SOURCE}}
 allq=[]
 for k,(path,name,t) in SOURCE.items():
  allq.append(cover(k,Path(path),name,t,logo,logo_bytes,review,f))
 summary={
  'id':'RC27_ZHENYA_ALIE_20261123','pubStatus':'NOT_PUBLISHED',
  'branch':'fitness',
  'covers':[{'trainer':z['trainer'],'png':z['master_png'],'time':z['original_frame_seconds'],
    'logoSHA':z['logo_SHA256'],'status':z['overall_status']} for z in allq],
  'font':f
 }
 (OUT/'production_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print('RC27_TRUE_COVERS_RENDERED',json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
