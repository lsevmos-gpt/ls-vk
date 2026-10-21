---
name: seedance-studio
description: Automatically orchestrate three mandatory cinematic and prompt-quality skill reviews for any Seedance 2.0/2.5 video prompt, revision, critique, reference-to-video prompt or multi-shot commercial; includes Russian speech variants.
---

# Seedance Studio v1.1 — mandatory three-method coordinator

TRIGGER: Whenever a user requests a Seedance video prompt (incl. Сиденс, Седенс, Сиданс, Седанс, Sedens; CDC only in a Seedance-video context), run the steps below BEFORE drafting; no extra activation required.

## Mandatory prerequisite: load all three, every time
Read the following files in full:
- ../seedance-os-director/SKILL.md — filmed action, shot purpose, motivated camera and continuity (Skill OS lens).
- ../seedance-forge-qa/SKILL.md — structuring, reference roles, inconsistencies, rewrite/repair (Prompt Forge lens).
- ../seedance-clean-visuals/SKILL.md — physically plausible blocking, real skin, light, optics (Clean lens).

Each check is mandatory, not a menu. These three are adapted project-local skills; the original upstream repositories are separately credited in references/sources.md. Never claim to have installed or executed upstream software or spawned three separate model agents. If a file is unavailable, report the gap.

## Model version routing
- Seedance 2.0: OS directs and structures the scene using its 2.0 approach. Forge audits model-neutral structure only; Clean reviews realistic cinematography.
- Seedance 2.5: Forge structures the prompt and checks 2.5-specific modes. OS supplies general-purpose director/continuity craft only; Clean reviews realistic cinematography.
- Version not established: do not invent model-specific settings or asset syntax. Prefer a cross-version prompt if it is still useful.
- The current official documentation for the selected model AND provider overrides third-party technical advice.

## Execution sequence
1. Extract the explicit creative brief and given model, provider, target ratio, clip duration and actual uploaded media. Preserve approved exact dialogue, marketing facts and restrictions.
2. Run OS: identify the audience's goal, frame zero, visible primary action, blocking, one purposeful camera movement, light source, sound intent, and visible end-state.
3. Run Forge: bind each real reference asset to one primary role; compile subject + action/event + environment + look + camera/cut + audio. No invented @ tags or absent source files.
4. Run Clean: ensure gravity/contact, natural skin/eyes/body proportions, plausible gear, shadows, camera physics and non-artificial movement. Turn vague mood words into visible instructions.
5. Run final Forge QA and OS continuity check: remove contradictions, competing camera moves, invented branding, unsupported resolution/fps claims and excessive events per short clip.
6. Output a clean copy-ready prompt, reference mapping only for actual assets, provider/UI settings outside the prompt, and a short meaningful QC note. A multi-shot request needs a prompt for EACH generation and explicit continuity handoffs.

For «Линия спорта»: no re-created logos, fake reviews or invented prices; no face/skin/body redesign. Add exact Cyrillic offer copy/branding during editing unless the original compositing asset is explicitly supplied and supported.

Do not render paid video, publish, upload private reference files or commit production changes without separate user permission.