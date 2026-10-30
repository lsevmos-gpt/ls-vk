"""Strict RC2.2 Reels1 cover: genuine source frame, literal Roboto Condensed Bold,
SHA-256-verified original fitness logo, independent editable SVG layers,
a single Dusty Rose accent, exact 1080x1920 sRGB and crop previews.
NO social publication, no human/background regeneration.
"""
from pathlib import Path
import os,sys,json,base64,hashlib,subprocess
from xml.sax.saxutils import escape
from PIL import Image,ImageDraw,ImageFont,ImageCms,ImageOps
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT=Path.cwd()
SRC=ROOT/"media-prep/reels1-review-20261030/sample_03.jpg"
META=ROOT/"media-prep/reels1-review-20261030/inspection.json"
REQUEST=ROOT/"media-prep/reels1-cover-20261030-render.json"
OUTPUT=ROOT/"media-prep/reels1-rc22-cover-20261030"
LOGO=Path("/tmp/reels1-fitness-original.png")
FONT_VARIABLE=Path("/tmp/RobotoCondensed-variable.ttf")
FONT_BOLD=Path("/tmp/RobotoCondensed-Bold.ttf")
EXPECTED_VIDEO_SHA="b55744a423c4ee8685b51ad4680a6f94cfe550959e48dac814f0edd3d9ec0398"
EXPECTED_LOGO_SHA="e145980feff7d744c5c718aa7f0f59a47fc992fdad7f2260906b98c81e2ecb39"
HEADLINE=["РАЗМИНКА","ДЛЯ СПИНЫ"]
WIDTH,HEIGHT=1080,1920
COLORS={"panel":"#F3EAE2","headline":"#1F1C1B","line":"#A96663"}

def digest(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def check_font():
    tt=TTFont(FONT_VARIABLE)
    cmap=tt.getBestCmap()
    for letter in "".join(HEADLINE):
        if letter!=" " and ord(letter) not in cmap: raise ValueError("Roboto Condensed font missing Russian glyph: "+letter)
    names={v.toUnicode() for v in tt["name"].names if v.nameID in (1,4,6)}
    if not any("Roboto Condensed" in n or "RobotoCondensed" in n for n in names):
        raise ValueError("Actual Roboto Condensed font not resolved: "+str(names)[:250])
    if "fvar" in tt:
        axis={a.axisTag for a in tt["fvar"].axes}
        assert "wght" in axis
        static=instantiateVariableFont(tt,{"wght":700},inplace=False)
        static.save(FONT_BOLD)
        font_status="Roboto Condensed, variable wght axis instantiated to exact 700"
    else:
        assert any("Bold" in name for name in names),"non-variable font is not Bold"
        FONT_BOLD.write_bytes(FONT_VARIABLE.read_bytes())
        font_status="Roboto Condensed Bold static TTF"
    return font_status

def main():
    req=json.loads(REQUEST.read_text())
    inspect=json.loads(META.read_text())
    assert req["sourceVideoFileId"]=="1A3nRzmTg91ZihgjAC_SGk4LedMjoH1FX"
    assert req["ruleFile"]=="Reels_RC2_2.json" and req["branch"]=="fitness"
    assert req["frameIndex"]==3 and req["headline"]==HEADLINE
    assert req["logoOriginalId"]=="1PeUzCGLsRLLEsiGzPkNp7To8inFXiQLU"
    assert inspect["originalSHA256"]==EXPECTED_VIDEO_SHA and inspect["sourceName"]=="рилс1.mp4"
    assert abs(inspect["frames"][3]["timecode_seconds"]-8.579)<0.003
    assert SRC.is_file() and SRC.stat().st_size>100000
    assert digest(LOGO)==EXPECTED_LOGO_SHA
    frame=Image.open(SRC)
    assert frame.size==(2160,3840),"Non-native source frame"
    logo=Image.open(LOGO)
    assert logo.size==(2048,476) and logo.mode=="RGBA","Original 2048x476 transparent logo was not preserved"
    font_status=check_font()
    logo_bytes=LOGO.read_bytes()
    video_frame_bytes=SRC.read_bytes()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    if (OUTPUT/"Reels1_RC2_2_1080x1920.png").exists():
        print("RC22_COVER_ALREADY_RENDERED; NO_REWRITE")
        return

    # Composition: one source hero, real face+body unchanged; editable text and original logo.
    # All essential layers and title fall inside RC2.2 central 1:1 crop.
    panel=(96,428,984,783)
    x_title=140
    y_lines=[480,596]
    title_size=108
    logo_width=278
    logo_x=682;logo_y=699
    logo_h=round(logo_width*476/2048)
    line=(140,732,514,741)
    bg=frame.convert("RGB").resize((WIDTH,HEIGHT),Image.Resampling.LANCZOS)
    original_bg=bg.copy()
    overlay=Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
    ov=ImageDraw.Draw(overlay)
    ov.rectangle(panel,fill=(243,234,226,239))
    bg=Image.alpha_composite(bg.convert("RGBA"),overlay)
    font=ImageFont.truetype(str(FONT_BOLD),title_size)
    draw=ImageDraw.Draw(bg)
    headings=[]
    for text,y in zip(HEADLINE,y_lines):
        bbox=draw.textbbox((x_title,y),text,font=font,anchor="lt")
        draw.text((x_title,y),text,font=font,fill=COLORS["headline"],anchor="lt")
        headings.append({"text":text,"visibleTextBBox":bbox})
    # One accent line in dusty-rose, independent of logo.
    draw.rectangle(line,fill=COLORS["line"])
    display_logo=logo.resize((logo_width,logo_h),Image.Resampling.LANCZOS)
    bg.alpha_composite(display_logo,(logo_x,logo_y))
    out=bg.convert("RGB")
    srgb_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    png=OUTPUT/"Reels1_RC2_2_1080x1920.png"
    out.save(png,format="PNG",optimize=True,icc_profile=srgb_profile)
    assert Image.open(png).size==(1080,1920)
    assert Image.open(png).info.get("icc_profile")

    # Portable, editable SVG: photo, solid backing, title text, accent line and original logo
    # are five independent named layers. No font bytes are bundled or distributed.
    photo_encoded=base64.b64encode(video_frame_bytes).decode("ascii")
    logo_encoded=base64.b64encode(logo_bytes).decode("ascii")
    svg=f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
 width="1080" height="1920" viewBox="0 0 1080 1920" color-interpolation="sRGB">
 <title>Рилс1 — РАЗМИНКА ДЛЯ СПИНЫ — RC2.2</title>
 <desc>Editable independent text, original SHA-256 verified logo and one accent line. Real video frame 00:08.579.</desc>
 <g id="photo-original" data-layer="01 Original video frame, unchanged">
  <image x="0" y="0" width="1080" height="1920" preserveAspectRatio="none"
   href="data:image/jpeg;base64,{photo_encoded}" />
 </g>
 <g id="editorial-panel" data-layer="02 Warm neutral support">
  <rect x="96" y="428" width="888" height="355" fill="#F3EAE2" opacity="0.937" />
 </g>
 <g id="live-title" data-layer="03 LIVE editable typography — Roboto Condensed Bold 700"
    fill="#1F1C1B" font-family="Roboto Condensed" font-weight="700" font-size="108">
  <text x="140" y="480" dominant-baseline="text-before-edge">РАЗМИНКА</text>
  <text x="140" y="596" dominant-baseline="text-before-edge">ДЛЯ СПИНЫ</text>
 </g>
 <g id="dusty-rose-accent" data-layer="04 One straight rose accent">
  <rect x="140" y="732" width="374" height="9" fill="#A96663" />
 </g>
 <g id="original-master-logo" data-layer="05 Original fitness MASTER logo e145980feff7d744c5c718aa7f0f59a47fc992fdad7f2260906b98c81e2ecb39">
  <image x="{logo_x}" y="{logo_y}" width="{logo_width}" height="{logo_h}"
   preserveAspectRatio="xMidYMid meet" href="data:image/png;base64,{logo_encoded}" />
 </g>
</svg>'''
    editable=OUTPUT/"Reels1_RC2_2_editable.svg"
    editable.write_text(svg,encoding="utf-8")

    # Reference crop tests on EXACT same 9:16 PNG. C08 actual profile grid pending.
    crops={"profile_3x4":(0,240,1080,1680),"feed_4x5":(0,285,1080,1635),
           "square_1x1":(0,420,1080,1500)}
    crop_files={}
    for key,box in crops.items():
        p=OUTPUT/(f"Reels1_RC2_2_preview_{key}.png")
        out.crop(box).save(p,icc_profile=srgb_profile,optimize=True)
        crop_files[key]=str(p)
    # Useful visual QA strip: simulated cuts labeled as references, not actual app preview.
    widths=[270,270,270,270]
    keys=["full_9x16","profile_3x4","feed_4x5","square_1x1"]
    images=[out,out.crop(crops["profile_3x4"]),out.crop(crops["feed_4x5"]),out.crop(crops["square_1x1"])]
    strip=Image.new("RGB",(1208,610),(245,241,234))
    dstrip=ImageDraw.Draw(strip)
    label_font=ImageFont.truetype(str(FONT_BOLD),30)
    for i,(k,im) in enumerate(zip(keys,images)):
        img=ImageOps.contain(im,(270,540))
        xx=16+i*300+(270-img.width)//2
        yy=55+(540-img.height)//2
        strip.paste(img,(xx,yy))
        dstrip.text((16+i*300,11),k,fill="#1F1C1B",font=label_font)
    strip.save(OUTPUT/"Reels1_RC2_2_crop_reference.jpg",quality=94,subsampling=0)

    # QA: checks never claim a real Instagram publication.
    assert all(96<=b[0] and b[2]<=984 and 420<=b[1] and b[3]<=1500 for b in headings)
    assert 96<=logo_x and logo_x+logo_width<=984
    assert 420<=logo_y and logo_y+logo_h<=1500
    qa={
      "document_rule":"Reels_RC2_2.json / RC2.2",
      "master_current":"Visual System v1.8 — 29.10.2026",
      "source_video":{"name":"рилс1.mp4","driveId":req["sourceVideoFileId"],
         "sha256":EXPECTED_VIDEO_SHA,"duration":inspect["durationSeconds"],
         "frame_timecode_seconds":inspect["frames"][3]["timecode_seconds"],
         "selected_still_from_original":True,"source_still_sha256":digest(SRC)},
      "branch":"fitness",
      "headline":"РАЗМИНКА ДЛЯ СПИНЫ",
      "font":{"family":"Roboto Condensed","weight":700,"verified":font_status},
      "logo":{"name":"лого фитнес_черный.png","driveId":req["logoOriginalId"],
        "originalSHA256":EXPECTED_LOGO_SHA,"computedSHA256":digest(LOGO),
        "originalDimensions":"2048x476","displayDimensions":f"{logo_width}x{logo_h}",
        "unaltered_logo_bytes_embedded_in_editable_SVG":True},
      "image":{"width":1080,"height":1920,"profile":"sRGB","iccEmbedded":True,
         "sourcePortraitRetouching":False,
         "photoOriginalApartFromWholeCanvasScaling":True,"oneAccent":"#A96663",
         "fitnessBrandGraphicsContainGreen":False},
      "editableMaster":"Reels1_RC2_2_editable.svg",
      "png":"Reels1_RC2_2_1080x1920.png",
      "cropReferences":crop_files,
      "qa":{"P01_to_P18":"checked for content, font, logo, format and proportions; visual review required on mobile",
        "C01":"PASS", "C02":"simulated only; actual Instagram app preview PENDING",
        "C03":"PASS by dimensions and visual preview, manual review encouraged",
        "C04":"PASS original fitness logo SHA256",
        "C05":"N_A no secondary caption",
        "C06":"PASS authentic source and independent layers",
        "C07":"N_A not embedded as video first frame",
        "C08":"PENDING not published",
        "F01":"PASS fitness style",
        "F02":"PASS no green graphics",
        "F03":"PASS dusty-rose line",
        "F04":"PASS original burgundy-logo",
        "F05":"PASS actual Roboto Condensed Bold 700",
        "F06":"PASS warm palette",
        "F07":"PASS real source frame",
        "F08":"PASS exact sRGB export plus modeled crops"},
      "status":"DRAFT_FOR_APPROVAL",
      "notes":["Actual Instagram preview cannot be proven from mathematical crops",
               "Editable SVG text requires Roboto Condensed installed on editing computer; font file not distributed",
               "No video or social media was published"],
      "sha256PNG":digest(png)
    }
    (OUTPUT/"Reels1_RC2_2_QA.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("RC22_REAL_VIDEO_COVER_RENDER_COMPLETE",json.dumps({
       "image":str(png),"svg":str(editable),"qa":str(OUTPUT/"Reels1_RC2_2_QA.json"),
       "font":font_status,"logoSHA":digest(LOGO),"frame":inspect["frames"][3]["timecode_seconds"],
       "pngBytes":png.stat().st_size},ensure_ascii=False))

if __name__=="__main__":
    main()
