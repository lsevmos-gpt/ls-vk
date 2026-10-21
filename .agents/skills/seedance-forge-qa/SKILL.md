---
name: seedance-forge-qa
description: Mandatory compilation, reference-role mapping, repair and QA for every Seedance 2.0/2.5 video prompt; adapted from Seedance Prompt Forge methodology.
---

# Prompt structure and audit lens — Forge

Source: https://github.com/silentbuilds/seedance-prompt-forge (MIT-licensed Seedance 2.5 Prompt Forge). This is an independently worded compact adapter, not the complete upstream source.

Compile concrete Subject + Action/Event + Environment + Visual Treatment + Camera/Cuts + Audio; omit slots that do not apply. Put generation interface settings separately unless the selected mode needs limited mention.

Bind each ACTUALLY PROVIDED image/video/audio to an explicit role. A reference may control face, environment, first frame, camera, motion, dialogue or style; do not silently make one asset control unrelated properties. Preserve exact user's names, quoted words and chronological order. Do not invent tags, uploads, API parameters, spoken dialogue or unsupported platform settings.

Audit: clear opening action; one primary change/event per moment; stable identity, wardrobe, prop ownership, geography, hand contacts and sound continuity; no unused or contradictory instructions, placeholders or impossible camera combinations. For failed generations identify likely failure, edit minimum necessary constraints and compare next render. Textual audit ≠ guaranteed rendering quality.

2.5: primary version-specific prompt compiler and technical guide, based on CURRENT official selected-provider information. 2.0: model-neutral structure and QA only, not 2.5 model capabilities.