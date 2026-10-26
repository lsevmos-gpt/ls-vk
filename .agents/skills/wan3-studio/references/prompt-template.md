# Wan3 prompt compiler: production structure

## Sequence
1. Identify exact `wan3_0` vs `wan3_0_prime` and T2V vs image-to-video vs reference-to-video. Confirm reference media actually exist.
2. First sentence: what is being advertised, where, lighting, visual language, aspect ratio, intended duration, product identity and constraints.
3. Add named references **only if supplied and supported**: `Image 1`, `Video 1`, `Audio 1`. Keep a mapping OUTSIDE final prompt.
4. Describe explicit cuts using adjacent `Shot 1 [0-2s]`, `Shot 2 [2-4s]`; each with a clear action, camera, light, start condition and end state. Do NOT overload four-second intros with six shots. Editorial timecodes are intentions, not a pixel-perfect guarantee.
5. End with action-matched audio, `No dialogue` if appropriate, and negative controls. Use postproduction for exact Cyrillic labels, prices and approved logos.
6. Put model selection, resolution, ratio, duration, audio/thinking switches OUTSIDE the clean model prompt.

## Paste-ready example: 4-second unbranded beverage transition

```text
A 4-second premium photorealistic vertical beverage teaser in a warm, atmospheric bar, natural optical refraction and studio-grade product lighting. The same transparent glass, ice geometry, and liquid color remain consistent across both shots. No people.
Shot 1 [0-2s]: Extreme macro: fresh ice cubes fall into an empty transparent glass, naturally collide and settle; subtle push-in, textured highlights. Crisp ice impact and glass contact sounds. Hard cut.
Shot 2 [2-4s]: Close hero angle on the same glass: a single clear stream of colorful juice begins pouring naturally over the settled ice; realistic liquid displacement, droplets, accurate glass optics; end with a steady product-visible hero frame. Liquid pour sound.
No dialogue. No generated typography, invented logos, extra hands, sudden object morphs or gravity-defying liquid.
```

The example is a structure guide, not a request to generate a video.
