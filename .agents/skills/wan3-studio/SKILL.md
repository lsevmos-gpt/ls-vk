---
name: wan3-studio
description: >-
  Wan 3.0 / Wan 3.0 Prime / Van 3.0 prompt expert for Higgsfield:
  multi-shot directing, advertising prompt compilation, sound and continuity QA.
---

# Evmos Wan3 Studio · v1.0.0 (Higgsfield)

This is an original Evmos adapter **based on** official Alibaba Cloud Wan3 documentation. It is **not** the vendor's separate downloadable `wan3-pe.zip` and does not execute or install vendor code.

## Automatic trigger
For requests to draft, edit, audit or storyboard prompts for "Wan 3.0", "Wan 3.0 Prime", "Van 3.0" or "Ван 3.0": activate this workflow; do not require an extra activation message.

1. Use the Evmos Video Studio eight specialist roles when installed: creative → screenwriter → director → camera → storyboard → editor → ai-video → quality. If not installed, run the equivalent checks sequentially and explicitly state missing files. These instructions are not independently running agents.
2. Read `references/model-settings.md`, `references/prompt-template.md`, and `references/quality-check.md`. In local Evmos also read `~/.agents/skills/evmos-video-studio/references/wan3-method.md` and the right Wan model adapter where available.
3. Apply three targeted reviews: **Wan3 Shot Director** (timed, motivated edits), **Wan3 Prompt Forge** (one clean paste-ready prompt in correct model grammar), **Wan3 Continuity & Physics QA** (visual reality, reference binding, brand accuracy).
4. If real Codex multi-agents are configured and invoked, use `evmos_wan3_shot_director`, `evmos_wan3_prompt_engineer`, `evmos_wan3_continuity_critic`. Claim a subagent ran only if it actually ran; otherwise perform these reviews manually.
5. Preserve the Evmos reference gate EVS-RCG-01, compare real master reference images and START/MID/END before **any paid generation**. A text prompt may remain a draft when media are unavailable. Never claim visual preflight PASS without examining source pixels.
6. Output **one** model PROMPT, separately UI SETTINGS / REFERENCE MAP / QC. No API calls, paid generation, publication or asset transmission without explicit request.
7. Neutral brand defaults to `brand_id: null`. Choose «Линия спорта» assets only when that project is explicitly named. Do not impose its color palette on independent projects or restrict artistic advertising colors unless requested.
8. Do not copy Seedance 2.0/2.5 limits, flags, or format; those three Seedance OS/Forge/Clean reviews apply only to Seedance video prompts.

References: Alibaba prompt guide (2026-10-16): https://www.alibabacloud.com/help/en/model-studio/wan3-video-generation-prompt-guide ; Higgsfield model presentation: https://higgsfield.ai/wan-3-0 .
