# Google Drive → Meta 2K: Reels / Video Stories

This route is separate from the existing Instagram calendar, VK, and Buffer. It
does not choose videos automatically, and it **never publishes without a specific
approved manifest** committed under requests/instagram-drive/ and two positive
flags: approved=true and publicContent=true.

## One-time connection required

1. In Google Cloud, create a service account and enable Google Drive API.
   Create a JSON key for that account. Never commit this JSON.
2. Share only the Google Drive folder **Линия спорта** with the service-account
   email as **Viewer**. Project folder ID:
   1esCJqiZdf5f2-GGJP0UTGDZODPfp3o1c.
3. In GitHub repository secrets for lsevmos-gpt/ls-vk add
   GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON with the complete account JSON.
   These secrets are consumed by GitHub Actions, **not** the ChatGPT Google
   Drive connector. No access automatically transfers between them.
4. Confirm existing repository secrets META_IG_ACCESS_TOKEN and
   META_IG_USER_ID are healthy using meta-ig-readiness.yml. The route is for
   **@liniya__sporta only** and uses Meta Graph API v26.0.
5. Test offline via the Validate job in instagram-drive-meta-2k.yml.
   Validate makes no provider calls. A separate explicitly approved test
   publication is needed to verify binary Meta upload for each content type.
6. A source must belong to the project Drive tree and must be an MP4 with
   correct 9:16 framing and 23–60 FPS, plus an audio stream.

## How to request a publication

On a specific user command, ChatGPT identifies the exact approved Google Drive
video and creates a *new* file under requests/instagram-drive/.
Example shape **for reference only; do not commit without approval**:

    {
      "id": "reel-20261103-1200-example",
      "handle": "liniya__sporta",
      "postType": "reel",
      "driveFileId": "REPLACE_WITH_REAL_DRIVE_FILE_ID",
      "text": "Final approved caption",
      "shouldShareToFeed": true,
      "approved": true,
      "publicContent": true
    }

For video Stories use postType="story" and omit text, coverUrl,
collaborators, and shouldShareToFeed. Each Story is one video/manifest.
The GitHub push workflow validates the manifest, downloads the *original*
source privately with the dedicated Drive credential, inspects it with
ffprobe, prepares Meta-compatible media without upscaling, reserves a durable
job receipt in results/instagram-drive/, then uploads bytes directly to
Meta (no public Drive URL or public video repository copy) and publishes.

There are no automatic retries on ambiguous Meta errors. A result named
published must include an Instagram media ID; manual_review_required means
manually check Instagram for a possible publication before any new attempt.

## 2K and quality policy

- 4K (2160 × 3840) → 1440 × 2560 using Lanczos / H.264, with AAC audio.
- Original 1440 × 2560 is sent without re-encoding when compatible with Meta.
- Original 1080 × 1920 is **not upscaled** and remains unchanged when compatible.
- No cropping, added frames, changed faces, redrawn logos, or forced overlays.
- Reels: 300 MB conservative safety cap; Stories: 100 MB cap.
- A file that fails duration, pixel ratio, size or codec validation is blocked;
  never silently publish a lower-quality alternative.
- Meta can recompress after upload, so final viewer resolution is not guaranteed.
- Stories use the same Meta direct-video upload route but must be verified with
  one approved test Story before declaring production readiness.

## Scope and cautions

- Video Reels and video Stories are supported by this bridge.
- Images, photo Stories, and carousels still use the pre-existing Meta calendar
  with public media URLs; they are **not** covered by this direct-video bridge.
- Exact minute scheduling remains the existing Meta calendar's responsibility.
  This route publishes approved videos after GitHub receives the manifest.
- Stories that require link stickers, music/stickers, or UI interactions must
  be handled with the appropriate native Instagram workflow.
- The GitHub repository is PUBLIC: never commit passwords, tokens, private
  source videos, private client data, or unpublished confidential captions.
  Publication IDs and some source identifiers are visible in manifests.
- A user command is required for every publication or explicitly approved
  schedule. Having access to a folder does not authorize posting every file.

Workflow: .github/workflows/instagram-drive-meta-2k.yml
Implementation: scripts/instagram_drive_meta.py
Offline checks: tests/test_instagram_drive_meta.py
