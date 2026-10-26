# Wan3 Continuity & Physics QA

Mandatory checks:
- Exact model and interface; none of the Seedance-only controls or assumptions.
- Continuous shot time windows, suitable shot count, visible beginning/end state and real motivation for cuts.
- Reference IDs match **real** submitted media; supported combinations confirmed in provider interface.
- Same product, vessel, label, geometry, placement, light and color across the cut; actual master and START/MID/END images inspected when used.
- Product physics: believable gravity, viscosity, splash direction, refraction, reflections, ice displacement, fill level, no changing glass or disappearing ingredients.
- No contradictory camera instruction; avoid simultaneous fixed shot and orbital camera in one shot.
- Audio stays synchronized with visibly occurring actions; no surprise narration/voice when none intended.
- Correct brand routing: `brand_id: null` unless project explicitly selects a brand; exact text/logos generated as post overlays when required.
- No fabricated pricing or claimed superior Prime quality; estimate costs on current provider before paid generation.
- If media cannot be inspected, mark visual preflight **UNVERIFIED** rather than PASS.
- Mark `SCRIPT READY` for a draft only, `GENERATION READY` only when model, references and user-approved spend are all confirmed.

Use reference continuity gate EVS-RCG-01 from Evmos core when installed.
