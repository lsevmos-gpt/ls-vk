"""Targeted revision of the TWO ORIGINAL RC2.7 trainer covers.
No image generation or replacement people/logos. Change just local face tone, text/line positions and logo position.
"""
import base64, hashlib, io, json, shutil, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageCms

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "media/reels-rc27-20261123/final"
DST = ROOT / "media/reels-rc27-20261123/revised/20261123"
FONTPATH = Path("/usr/local/share/fonts/rc27/RobotoCondensed-Bold.ttf")
ACCENT = "#9A2635"  # Same as the genuine FITNESS logo SYMBOL, not club lime.
LOGOSHA = "e145980feff7d744c5c718aa7f0f59a47fc992fdad7f2260906b98c81e2ecb39"

SETTINGS = {
 "zhenya": {
   "trainer": "ЖЕНЯ",
   "src_sha": "3a2bff31a516ef0a4777587b3fcb30f3d1c9885c",
   "face_box": (437, 575, 775, 987),
   "logo_pos": (92, 286),  # leave the original logo in its original position
   "head": [(537, 1246, 126), (528, 1456, 183)],
   "line": {"x": 514, "y": 1153, "width": 12, "height": 341, "side": "vertical beside the heading"},
 },
 "alie": {
   "trainer": "АЛИЕ",
   "src_sha": "dcb5f43d96231716e25c8db8cbf90b69c80477d7",
   "face_box": (408, 565, 714, 1001),
   "logo_pos": (308, 286),  # move the original authentic logo right
   "head": [(112, 1253, 137), (111, 1451, 224)],
   "line": {"x": 116, "y": 1500, "width": 352, "height": 13, "side": "horizontal under name"},
 }
}
SVGNS = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", "http://www.w3.org/2000/svg")
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()

def sha(data): return hashlib.sha256(data).hexdigest()
def data_uri(bytes_,mime):
    return "data:"+mime+";base64,"+base64.b64encode(bytes_).decode("ascii")
def decode_uri(href):
    kind, raw=href.split(",",1)
    return base64.b64decode(raw), ("image/png" if "/png;" in kind else "image/jpeg")
def gently_lift_face(photo, box):
    # Image geometry and identity unchanged; mask only facial light/skin.
    base=photo.convert("RGB")
    bright=ImageEnhance.Brightness(base).enhance(1.047)
    bright=ImageEnhance.Contrast(bright).enhance(1.018)
    bright=ImageEnhance.Color(bright).enhance(0.987)
    # A very light blend of a tiny-radius softening, avoids plastic skin and keeps pores/eyes.
    micro=Image.blend(bright,bright.filter(ImageFilter.GaussianBlur(0.6)),0.055)
    mask=Image.new("L",base.size,0)
    d=ImageDraw.Draw(mask)
    d.ellipse(box,fill=236)
    mask=mask.filter(ImageFilter.GaussianBlur(72))
    return Image.composite(micro,base,mask),mask

def crop_test(master,who, folder):
    windows = {
        "9x16": (0,0,1080,1920),
        "3x4":(0,240,1080,1680),
        "4x5":(0,285,1080,1635),
        "1x1_optional":(0,420,1080,1500),
    }
    sizes={"9x16":(180,320),"3x4":(180,240),"4x5":(180,225),"1x1_optional":(180,180)}
    for key,box in windows.items():
        crop=master.crop(box)
        crop.save(folder/(who+"_"+key+"_reference.png"),pnginfo=None)
        crop.resize(sizes[key],Image.Resampling.LANCZOS).save(folder/(who+"_"+key+"_mini.png"))

def main():
    assert FONTPATH.exists(), "Exact Roboto Condensed Bold font must be present"
    import cairosvg
    DST.mkdir(parents=True,exist_ok=True)
    all_report=[]
    for who, cfg in SETTINGS.items():
        folder = DST/who
        folder.mkdir(parents=True,exist_ok=True)
        input_svg = SRC/who/(who+"_editable_layers.svg")
        original_png = SRC/who/(who+"_Reels_RC27_1080x1920.png")
        assert original_png.is_file() and input_svg.is_file(), who+" original files missing"
        # The fixed SHA above is GitHub blob SHA, so git hash-object instead of sha256.
        object_id=subprocess.check_output(["git","hash-object",str(original_png)],cwd=ROOT,text=True).strip()
        assert object_id==cfg["src_sha"], (who,object_id)
        root=ET.parse(input_svg).getroot()
        assert root.attrib["width"]=="1080" and root.attrib["height"]=="1920"
        photo_el=root.find(".//*[@id='01_processed_native_video_photo']/"+SVGNS+"image")
        logo_el=root.find(".//*[@id='02_authentic_fitness_logo_sha256_verified']/"+SVGNS+"image")
        line_el=root.find(".//*[@id='03_single_dusty_rose_accent']/"+SVGNS+"rect")
        text_group=root.find(".//*[@id='04_editable_heading_Roboto_Condensed_Bold']")
        text_el=list(text_group)
        assert len(text_el)==2 and [x.text for x in text_el]==["ТРЕНЕР",cfg["trainer"]]
        photo_bytes,photo_mime=decode_uri(photo_el.attrib["href"])
        logo_bytes,logo_mime=decode_uri(logo_el.attrib["href"])
        assert sha(logo_bytes)==LOGOSHA, (who,sha(logo_bytes))
        assert logo_mime=="image/png"
        photo=Image.open(io.BytesIO(photo_bytes)).convert("RGB")
        assert photo.size==(1080,1920)
        fixed,mask=gently_lift_face(photo,cfg["face_box"])
        buf=io.BytesIO()
        fixed.save(buf,format="PNG",optimize=True,icc_profile=SRGB)
        photo_el.set("href",data_uri(buf.getvalue(),"image/png"))
        with open(folder/(who+"_photo_softly_refined_unbranded.png"),"wb") as f: f.write(buf.getvalue())
        # All other original image layers are preserved byte-for-byte.
        logo_el.set("x",str(cfg["logo_pos"][0]))
        logo_el.set("y",str(cfg["logo_pos"][1]))
        line=line_el.attrib
        line.update({k:str(v) for k,v in cfg["line"].items() if k in ("x","y","width","height")})
        line["fill"]=ACCENT
        root.find(".//*[@id='03_single_dusty_rose_accent']").set("id","03_fitness_logo_color_accent")
        for node, (x,y,size) in zip(text_el,cfg["head"]):
            node.set("x",str(x))
            node.set("y",str(y))
            node.set("font-size",str(size))
            node.set("font-family","Roboto Condensed")
            node.set("font-weight","700")
            node.set("fill","#1F1C1B")
        # Restore any embedded fixed original JPEG photo? No; only local tone pixels changed.
        root.find(SVGNS+"title").text="Линия спорта · RC2.7 original revised · тренер "+cfg["trainer"]
        svg_path=folder/(who+"_revised_editable.svg")
        ET.ElementTree(root).write(svg_path,encoding="utf-8",xml_declaration=True)
        rendered=cairosvg.svg2png(url=str(svg_path),output_width=1080,output_height=1920)
        final=Image.open(io.BytesIO(rendered)).convert("RGB")
        assert final.size==(1080,1920)
        final.save(folder/(who+"_revised_1080x1920.png"),format="PNG",optimize=True,icc_profile=SRGB)
        # Publication-friendly JPEG, original PNG retained.
        final.save(folder/(who+"_revised_meta_cover_1080x1920_q98.jpg"),
                   format="JPEG",quality=98,subsampling=0,optimize=True,icc_profile=SRGB)
        crop_test(final,who,folder)
        # Small difference evidence comparing original source photo and retouched one at 100%
        bx=cfg["face_box"]
        before=photo.crop(bx)
        after=fixed.crop(bx)
        panel=Image.new("RGB",(before.width*2,before.height))
        panel.paste(before,(0,0));panel.paste(after,(before.width,0))
        panel.save(folder/(who+"_face_before_after_100pct.png"),optimize=True)
        mask.save(folder/(who+"_face_adjustment_mask.png"))
        original_sha=sha(original_png.read_bytes())
        result_path=folder/(who+"_revised_1080x1920.png")
        qa={
            "status":"DRAFT_PENDING_HUMAN_VISUAL_REVIEW",
            "original_logo_exact_sha256":LOGOSHA,
            "logo_verified":True,"logo_changed":False,
            "original_cover_sha256":original_sha,
            "original_svg_git_blob":subprocess.check_output(["git","hash-object",str(input_svg)],cwd=ROOT,text=True).strip(),
            "original_video_frame_timecode_seconds":(2.199 if who=="zhenya" else 0.725),
            "source":"exact original RC2.7 layered SVG and its embedded real video photograph",
            "trainer":cfg["trainer"],"branch":"fitness",
            "accent_hex":ACCENT,"accent_position":cfg["line"]["side"],
            "logo_position":cfg["logo_pos"],"heading_positions":cfg["head"],
            "face_adjustment":"subtle feathered luminance +4.7%, local contrast +1.8%, color -1.3%, feather 72px; 5.5% radius0.6px softness ONLY in face ellipse",
            "face_anatomy_changed":False,"artificial_faces_generated":False,
            "photo_full_bleed":True,"size":[1080,1920],"color_profile":"sRGB",
            "C09":"PASS","C10":"SAME_REAL_FRAME_AS_RC27",
            "C11":"PENDING_HUMAN_180x240", "C12":"ACTUAL_PROCESSED_STILL_SAVED",
            "C13":"PENDING_HUMAN_CLEANUP_CHECK","C08":"PENDING_NOT_PUBLISHED",
            "result_sha256":sha(result_path.read_bytes())
        }
        (folder/(who+"_revision_QA.json")).write_text(json.dumps(qa,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        all_report.append({"trainer":who,"sha256":qa["result_sha256"],
                           "original_photo_unchanged_except_local_face_tone":True,
                           "logoSha256":qa["original_logo_exact_sha256"]})
    (DST/"revision_summary.json").write_text(json.dumps(all_report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("RC27_ORIGINAL_POSTERS_TARGETED_REVISION_COMPLETE",json.dumps(all_report,ensure_ascii=False))

if __name__=="__main__": main()
