#!/usr/bin/env python3
"""Update the user's ORIGINAL self-contained 4.34 MB Reels RC2.7 JSON to integrated RC2.8.
Preserve embedded original master logo bytes and all non-targeted content. No separate amendment.
"""
from __future__ import annotations
import base64, copy, hashlib, json, sys
from pathlib import Path

SOURCE = Path("temp/RC2_7_original_user_uploaded_20261123.json")
DEST = Path("docs/Liniya_Sporta_Reels_RC2_8_2026-11-23_FULL.json")
REPORT = Path("docs/Liniya_Sporta_Reels_RC2_8_2026-11-23_validation.json")
DATE = "2026-11-23"
FITNESS = "#9A2635"
CLUB_HORIZONTAL = "#288436"
CLUB_VERTICAL = "#008D44"

def require(condition, message):
    if not condition: raise ValueError(message)
def edit_check(d, key, expected, new):
    require(d[key] == expected, "Unexpected old value at "+key+": "+str(d[key])[:180])
    d[key]=new
def qa_by_id(j, group, identifier):
    v=[r for r in j["quality_assurance"][group] if r["id"]==identifier]
    require(len(v)==1, "QA ID not unique: "+group+" "+identifier)
    return v[0]

def logo_hashes(obj):
    logos = obj["embedded_assets"]["logos"]
    policies = obj["logo_policy"]["approved_logos"]
    require(len(logos)==len(policies)==12,"Logo inventory mismatch")
    hashes={}
    for name, payload in logos.items():
        require(name in policies, "Unregistered logo "+name)
        raw=base64.b64decode(payload,validate=True)
        digest=hashlib.sha256(raw).hexdigest()
        require(digest==policies[name]["sha256"],"Embedded logo changed or source mismatched "+name)
        require(raw.startswith(b"\x89PNG\r\n\x1a\n"),"Logo PNG signature invalid: "+name)
        hashes[name]=digest
    return hashes

def main():
    require(SOURCE.is_file(), "Original uploaded JSON not downloaded")
    src=SOURCE.read_bytes()
    require(len(src)==4341298, f"Original uploaded JSON size mismatch {len(src)}")
    obj=json.loads(src.decode("utf-8"))
    require(obj["schema_id"]=="liniya_sporta_reels_cover_ai_instruction","Wrong source schema")
    require(obj["schema_version"]=="1.6.0","Unexpected source schema version")
    require(obj["document_revision"]=="RC2.7-JSON","Unexpected source revision")
    old=copy.deepcopy(obj)
    hashes=logo_hashes(obj)

    obj["schema_version"]="1.7.0"
    obj["document_revision"]="RC2.8-JSON"
    obj["revised_on"]=DATE
    obj["revision_note_rc28"] = (
      "Изменены непосредственно нормативные поля этого единого JSON, а не сделано отдельное дополнение. "
      "По указанию пользователя от 23.11.2026: фирменная черта точно цвета символа исходного логотипа "
      "в выбранной бренд-ветви; композиции серии индивидуальны; при правках существующей обложки "
      "допускаются только локальные изменения без подмены реального человека, фона и логотипа."
    )

    obj["how_to_use"]["user_message_to_send"] += (
      " RC2.8: акцентная черта — точный цвет фирменного символа выбранного оригинального логотипа "
      "(фитнес #9A2635, клуб #288436 у горизонтального или #008D44 у вертикального). "
      "Не копируй одну и ту же компоновку имени, логотипа и линии на всех тренеров: "
      "по сюжету выбирай разные положения (сбоку вертикально, снизу горизонтально и другие уместные). "
      "Если пользователь просит слегка поправить готовую обложку, РЕДАКТИРУЙ её подлинные исходные "
      "слои, не создавай новую девушку, зал, логотип или позу; улучшай портрет только "
      "очень мягко и локально без изменения личности."
    )
    obj["ai_execution_contract"]["precise_existing_cover_edits_rc28"] = (
      "Если дан готовый макет и запрос — немного улучшить/передвинуть элементы, "
      "сохранить выбранный настоящий кадр, лицо, позу, тело, интерьер и исходные зарегистрированные "
      "PNG-логотипы. Менять только прямо названные элементы и очень мягкую коррекцию "
      "света/тона реального лица; никаких новых вымышленных людей или полной генерации вместо ретуши."
    )
    obj["ai_execution_contract"]["exact_logo_symbol_accent_rc28"] = (
      "Цвет единственной бренд-черты брать из зарегистрированного оригинального PNG логотипа, "
      "точно совпадая с цветом ЗНАКА, а не примерной палитрой. "
      "Логотип НЕ перекрашивать. Фитнес #9A2635; клуб horizontal #288436 / vertical #008D44."
    )
    obj["ai_execution_contract"]["non_template_series_rc28"] = (
      "Для двух и более роликов не повторять механически сетку текста, черты и логотипа. "
      "Разрешено переносить надписи левее/правее/выше/ниже и располагать черту вертикально сбоку "
      "либо горизонтально под текстом, в пределах безопасных зон, сохраняя лицо открытым. "
      "Единые оригинальные фирменные активы и гарнитуру сохранять."
    )

    cl=obj["branch_classifier"]["club"]
    ft=obj["branch_classifier"]["fitness"]
    edit_check(cl,"accent_line_colors",["#1F822E","#30B852"],[CLUB_HORIZONTAL,CLUB_VERTICAL])
    cl["notes"] += (
      " RC2.8: фирменная черта должна соответствовать точному цвету знака выбранного "
      "исходного логотипа: #288436 для горизонтального, #008D44 для вертикального; "
      "не заменять его условным цветом из палитры."
    )
    edit_check(ft,"accent_line_colors",["#A96663"],[FITNESS])
    ft["notes"] += (
      " RC2.8: для отдельной акцентной черты используется именно цвет бордового знака "
      "оригинального фитнес-логотипа #9A2635. Цвет пыльной розы #A96663 сохраняется "
      "в общей палитре для других, небрендовых оттенков и не используется для этой линии."
    )
    obj["branch_classifier"]["mixed_content"] += (
       " Акцентная линия берёт точный цвет символа подлинного логотипа выбранной ветви."
    )
    decision=obj["branch_classifier"]["reels_service_based_decision_rc26"]
    edit_check(decision["branch_decision"]["club"],"accent_line_hex_allowed",
               ["#1F822E","#30B852"],[CLUB_HORIZONTAL,CLUB_VERTICAL])
    decision["branch_decision"]["club"]["accent_line_selection"]=(
       "Соответствие исходному зарегистрированному символу: при горизонтальном логотипе "
       "#288436, при вертикальном #008D44; если нужен иной контраст, "
       "переместить черту или скорректировать фон локально, но не перекрашивать логотип и черту."
    )
    edit_check(decision["branch_decision"]["fitness"],"accent_line_hex_required","#A96663",FITNESS)
    decision["decision_workflow"][4] = (
       "5. Установить акцентную линию ТОЧНО цвета знака выбранного оригинального логотипа "
       "(фитнес #9A2635, клуб horizontal #288436 / vertical #008D44) отдельным слоем; "
       "не допускать смешения палитр."
    )
    edit_check(decision["required_classification_record"],"accent_line_hex",
               "#1F822E|#30B852|#A96663|null",
               "#288436|#008D44|#9A2635|null")

    # Logo images and SHA digests are immutable. Modify only the explanatory text.
    logo=obj["logo_policy"]
    logo["note"]=(
       "Цвета пикселей исходных MASTER-логотипов неизменны: club horizontal #288436, "
       "club vertical #008D44, fitness #9A2635. Акцентная черта — отдельный слой "
       "точно цвета ЗНАКА фактически выбранного оригинального PNG. "
       "Нельзя изменять логотип, имитировать его отрисовкой или применять чужой фирменный цвет."
    )

    ty=obj["typography"]
    ty["approved_series_rule"]=(
      "У однотипной серии сохранять одну фирменную семью, Roboto Condensed Bold 700, "
      "узнаваемый масштаб оригинального логотипа и общую редакционную иерархию, "
      "НО НЕ повторять неизменную сетку координат. Положение заголовка, линии и логотипа "
      "подбирать индивидуально по реальному кадру: например, в одной обложке имя справа "
      "и линия вертикально сбоку, в другой — имя слева и линия горизонтально снизу."
    )

    brand=obj["brand_accent_line"]
    edit_check(brand,"club_colors",["#1F822E","#30B852"],[CLUB_HORIZONTAL,CLUB_VERTICAL])
    edit_check(brand,"fitness_colors",["#A96663"],[FITNESS])
    brand["color_identity_policy_rc28"] = {
      "rule":"Точный цвет видимого фирменного символа в конкретном исходном MASTER PNG логотипа; "
             "ни близкий тон, ни адаптированный брендовый акцент.",
      "fitness":"#9A2635",
      "club_horizontal":"#288436",
      "club_vertical":"#008D44",
      "logo_mutation":"FORBIDDEN",
      "dusty_rose_legacy_accent_discontinued":"#A96663 не использовать для фирменной черты фитнес Reels; "
                                             "он остаётся допустимым цветом общей фитнес-палитры."
    }
    brand["positioning"]=(
       "Индивидуально связано с заголовком или другим ключевым элементом; черта может "
       "располагаться слева/справа вертикально, снизу горизонтально или в другом подходящем "
       "месте, если это согласуется с композицией, не перекрывает человека и не является рамкой. "
       "Длина, толщина, отступ и координаты не копируются с предыдущих работ."
    )
    brand["never"].extend([
      "использовать пыльно-розовую #A96663 вместо точного бордового #9A2635 знака фитнес-логотипа",
      "ставить одинаковую черту в одних и тех же координатах в серии тренеров без учёта фото",
      "делать черту вокруг фото как рамку"
    ])

    comp=obj["composition_and_image"]
    comp["anti_template_series_layout_rc28"]={
       "priority":"MANDATORY",
       "principle":"Каждая обложка должна оставаться узнаваемой частью единого бренда, "
                   "но иметь собственную композицию по лицу, позе, свету и свободному пространству.",
       "vary":["положение названия/имени","линия: вертикально сбоку или горизонтально снизу",
               "положение оригинального логотипа в пределах safe-zone",
               "размер заголовка, межстрочные расстояния и выравнивание"],
       "fixed":["подлинный неизменный логотип","цвет линии точно в цвет символа",
                "Roboto Condensed Bold 700","правильная клубная/фитнес ветвь",
                "full bleed настоящего исходного кадра","безопасность/читаемость"],
       "example_without_fixed_coordinates":{
          "cover_A":"оригинальный логотип слева, надпись справа, линия вертикально сбоку",
          "cover_B":"оригинальный логотип сдвинут правее, надпись внизу слева, линия горизонтально под ней"
       }
    }
    comp["existing_cover_minimal_edit_rc28"] = (
       "Когда пользователь просит только слегка украсить ранее созданную обложку, "
       "не заменять оригинальный кадр/человека генерацией. "
       "Редактировать существующие слои: положение текста/линии/логотипа "
       "и ограниченную естественную коррекцию лица без изменения личности, одежды и анатомии."
    )

    # Integrate rule in production stages, not in a separate addendum.
    steps={x["step"]:x for x in obj["production_workflow"]}
    for num in (5,8,9,10,11,12):
        require(num in steps,"Missing production stage "+str(num))
    steps[5]["action"] += " RC2.8: оттенок фирменной линии должен совпадать с цветом знака оригинального логотипа."
    steps[8]["action"] += " RC2.8: использовать нешаблонное индивидуальное расположение текста/логотипа/линии; при правке готовой обложки не менять человека и кадр."
    steps[9]["action"] += " RC2.8: фирменная линия — точного цвета знака зарегистрированного логотипа и отдельным редактируемым слоем."
    steps[10]["action"] += " RC2.8: проверить, что положения блоков в серии не являются механически повторённой сеткой."
    steps[11]["action"] += " RC2.8: при изменении уже готовой обложки сравнить лицо и фон с исходным макетом, исключить перегенерацию и пластику."
    steps[12]["action"] += " RC2.8: отдельно подтвердить совпадение цвета черты со знаком исходного логотипа и вариативность композиции серии."

    p17=qa_by_id(obj,"general_P01_to_P18","P17")
    p17["pass"] += " В серии реальных людей композиция свободная, координаты текста/логотипа/линии не должны механически совпадать."
    p18=qa_by_id(obj,"general_P01_to_P18","P18")
    p18["pass"]=(
       "Фирменная черта одним отдельным редактируемым слоем точно цвета знака подлинного "
       "логотипа соответствующего направления: клуб горизонтальный #288436, "
       "клуб вертикальный #008D44, фитнес #9A2635. Размещение может быть вертикально "
       "сбоку или горизонтально снизу по индивидуальной композиции. "
       "Никаких зелёных брендовых элементов у фитнеса и никакой перекраски логотипа. "
       "Сохранять читаемость, safe zones, смысловую связь с текстом."
    )
    f03=qa_by_id(obj,"fitness_F01_to_F08","F03")
    f03["name"]="Акцентная черта в цвет знака фитнес-логотипа"
    f03["pass"]="Ровно #9A2635 — точный бордовый цвет знака подлинного фитнес-логотипа; одна прямая линия отдельным слоем. Положение — по конкретному фото (сбоку вертикально, снизу горизонтально и т.п.)."
    br02=qa_by_id(obj,"brand_branch_selection_gates_rc26","BR02")
    br02["pass"]=(
       "club -> только оригинальный MASTER зелёный знак и линия ТОЧНО цвета знака выбранной "
       "ориентации (#288436 horizontal / #008D44 vertical); fitness -> только оригинальный "
       "MASTER бордовый знак и линия точно #9A2635. Логотип не перерисован и не перекрашен."
    )
    # These two notes originally said that base gates had never been changed; retain truthful history.
    obj["quality_assurance"]["base_checks_preserved_and_extensions_rc25"] += (
       " Оперативная ревизия RC2.8 (23.11.2026): на уровне данного JSON уточнены "
       "тексты P17/P18, F03 и BR02 по прямому поручению пользователя; "
       "это НЕ означает утверждение изменений во внешнем Visual System MASTER v1.8."
    )
    obj["quality_assurance"]["rc28_style_alignment"]={
      "logo_colored_accent":"PASS only when exact symbol pixel color is used (#9A2635 fitness; #288436/#008D44 club).",
      "non_template_series":"PASS only when compositions vary meaningfully without changing real people.",
      "existing_cover_precision":"PASS only when previous real frames, faces, and exact original master logos are retained during local editing."
    }

    required=obj["expected_ai_response"]["required_fields"]
    for term in ("rc28_logo_color_exact_match","rc28_series_non_template_check","rc28_existing_cover_not_regenerated"):
        require(term not in required,"Unexpected duplicate expected field")
        required.append(term)
    report=obj["expected_ai_response"]["report_template"]
    report["rc28_logo_color_exact_match"]="NOT_RUN"
    report["rc28_series_non_template_check"]="NOT_RUN"
    report["rc28_existing_cover_not_regenerated"]="NOT_RUN"
    rest=obj["restrictions_and_limits"]
    rest["require_accent_exact_original_logo_symbol_color_rc28"]=True
    rest["ban_repetitive_trainer_poster_grid_rc28"]=True
    rest["ban_regenerating_original_people_when_existing_cover_edit_requested_rc28"]=True

    # Verify old logo originals and original source links weren't mutated.
    require(obj["logo_policy"]["approved_logos"]==old["logo_policy"]["approved_logos"],
            "Registered logo metadata unexpectedly changed")
    require(obj["embedded_assets"]==old["embedded_assets"],
            "Embedded asset data unexpectedly changed")
    require(logo_hashes(obj)==hashes, "Embedded logo bytes/hash changed")

    # Ensure no old accent still survives in a *normative line* field.
    require(obj["brand_accent_line"]["fitness_colors"]==[FITNESS],"Fitness line invalid")
    require(obj["brand_accent_line"]["club_colors"]==[CLUB_HORIZONTAL,CLUB_VERTICAL],"Club line invalid")
    require(ft["accent_line_colors"]==[FITNESS] and cl["accent_line_colors"]==[CLUB_HORIZONTAL,CLUB_VERTICAL],"Classifier line invalid")
    require(obj["logo_policy"]["approved_logos"]["лого фитнес_черный.png"]["sha256"]==
            "e145980feff7d744c5c718aa7f0f59a47fc992fdad7f2260906b98c81e2ecb39",
            "Fitness logo unexpectedly changed")
    require(obj["technical_canvas"]==old["technical_canvas"],"Technical canvas unexpectedly changed")
    require(obj["source_priority_and_verification"]==old["source_priority_and_verification"],
            "Source hierarchy unexpectedly changed")
    require(obj["approval_state"]==old["approval_state"],"Source approval state unexpectedly changed")

    DEST.parent.mkdir(parents=True,exist_ok=True)
    rendered=json.dumps(obj,ensure_ascii=False,indent=2)+"\n"
    DEST.write_text(rendered,encoding="utf-8")
    # Full round-trip check from actual saved UTF-8 file.
    out=json.loads(DEST.read_text(encoding="utf-8"))
    require(out==obj,"JSON round-trip mismatch")
    report={
        "generated_filename":DEST.name,
        "based_on_original_filename":"Liniya_Sporta_Reels_RC2_7_2026-11-17(5).json",
        "original_size_bytes":len(src),
        "original_sha256":hashlib.sha256(src).hexdigest(),
        "generated_size_bytes":DEST.stat().st_size,
        "generated_sha256":hashlib.sha256(DEST.read_bytes()).hexdigest(),
        "revision":out["document_revision"],
        "embedded_logos_count":len(hashes),
        "embedded_logos_sha256_verified":True,
        "all_embedded_assets_identical_to_source":True,
        "all_original_logo_registry_entries_identical_to_source":True,
        "source_pointer_and_canvas_unchanged":True,
        "colors":{"fitness":FITNESS,"club_horizontal":CLUB_HORIZONTAL,"club_vertical":CLUB_VERTICAL},
        "qc":"PASS_FILE_AND_LOGOS; visual QA for future covers must be done per cover",
        "source_approval_state_preserved":True
    }
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("RC28_MAIN_USER_JSON_COMPLETE "+json.dumps(report,ensure_ascii=False))

if __name__=="__main__":
    main()
