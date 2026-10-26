# AGENTS.md — LS-VK AI workflow policy

This repository publishes approved social content. Do not change publishing, credentials, API access, schedules or the live environment merely because a prompt is being drafted.

## MANDATORY Seedance trigger
If the user asks to CREATE, REWRITE, AUDIT, FIX, EXTEND or STORYBOARD a video prompt for **Seedance**, including voice spellings "Сиденс", "Седенс", "Сиданс", "Седанс", "Sedens", or "CDC" only when clearly referring to video generation:
1. BEFORE drafting, read all FOUR skill manifests at:
   - .agents/skills/seedance-studio/SKILL.md
   - .agents/skills/seedance-os-director/SKILL.md
   - .agents/skills/seedance-forge-qa/SKILL.md
   - .agents/skills/seedance-clean-visuals/SKILL.md
2. Run the Seedance Studio three-method review for EVERY prompt, including short prompts and corrections, without requiring the user to say "activate".
3. If Seedance **2.0** is specified: OS is model-specific director; Forge applies model-neutral QA; Clean applies naturalism and realism.
4. If Seedance **2.5** is specified: Forge is model-specific prompt compiler and QC; OS applies general storytelling, camera and shot continuity; Clean applies naturalism and realism.
5. NEVER carry numeric capabilities, tag syntax, or model controls from 2.0 to 2.5 or vice versa; verify using official documentation for the actual provider/interface.
6. If ANY skill cannot be read, state that and do not claim the mandatory three-method review completed.

These are **reusable AI instruction skills**, not three independently executing agents, and they do not by themselves access a video generation service.

## Quality and permissions
Preserve the user's exact brief, real identities and approved assets. For «Линия спорта», original logo only; real faces, skin, anatomy, equipment and source video must remain authentic. Prefer exact logos/prices/Cyrillic copy as post-production elements. Supply one paste-ready prompt per generation, settings only where verified, and brief QC. Never generate paid video, publish, spend credits, or upload personal assets without a separate request. Apply this Seedance workflow only to relevant prompts; other tasks follow existing social policies.

## MANDATORY Wan3 / Prime trigger (Evmos integration)
For any prompt, storyboard, rewrite, audit or repair for **Wan 3.0**, **Wan 3.0 Prime**, or obvious spellings **Van 3.0 / Ван 3.0**:
1. BEFORE drafting, read `.agents/skills/wan3-studio/SKILL.md`, `references/model-settings.md`, `references/prompt-template.md`, `references/quality-check.md` in that skill.
2. When local Evmos is installed, also read its eight roles and Wan3 model-specific `wan3-method.md`, `wan-30.md` or `wan-30-prime.md`; otherwise state those files unavailable and use the repo's self-contained Wan skill without claiming full Evmos installation.
3. Apply shot-direction, prompt-compilation and independent physics/continuity checks; subagent execution can only be claimed when agents actually ran.
4. Never mix Seedance UI syntax or unverified parameter ranges into Wan. Preserve original assets, brand-specific routing and EVS-RCG-01; user approval required for any credit-consuming generation.
5. Return one complete copy-ready prompt, separately validated Higgsfield settings and references. Standard ID `wan3_0`, Prime ID `wan3_0_prime`.

The official Alibaba `wan3-pe` download was not copied into this repository; this studio skill is our independently authored adaptation from public official docs.
