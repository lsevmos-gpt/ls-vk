# Instagram: Cloudflare direct Meta video upload (23.11.2026)

## Status

Production deployed and end-to-end tested **without publishing**. Instagram Reels and video Stories now use a Cloudflare-to-Meta **binary** resumable upload, rather than asking Meta to fetch the video from a `video_url`.

Current workers:
- Scheduler: `ls-instagram-publisher` (deployed version `956f4933-c83d-4ac8-9cfa-05d755716d7e`).
- Credential-bearing RPC gateway: `shrill-brook-15a0-ls-light-bot` (deployed version `602b363e-8361-4417-9fc4-4f331246f8c0`).
- Cron remains `* * * * *`, with D1 job state, Meta readback, owner notifications and collaborator fields unchanged.
- Secret `META_IG_ACCESS_TOKEN` stays exclusively in the gateway's Cloudflare secret binding.

## How direct video upload works

1. Scheduler reserves approved D1 job and verifies the correct Instagram account.
2. `POST /{ig-id}/media` uses `upload_type=resumable` and the existing approved caption, custom `cover_url` when specified, `share_to_feed`, and collaborator usernames. It does **not** pass `video_url` to Meta.
3. D1 records the returned container ID and state `uploading` before any MP4 transfer.
4. Gateway reads the video from an approved HTTPS origin, validates type and byte length (optional `media_json[].bytes`), and streams through Cloudflare `FixedLengthStream` using automatic `Content-Length`. It posts directly to `https://rupload.facebook.com/ig-api-upload/v26.0/{container-id}` with `Authorization: OAuth`, `offset: 0`, and `file_size`. The whole video is never buffered in Worker memory.
5. The gateway requires Meta's `{"success":true}` response; scheduler records accepted byte count and waits for `status_code=FINISHED`.
6. At the requested publish time it calls `media_publish` exactly once, then verifies and saves the Meta media ID/permalink.
7. If transfer/publish outcome is uncertain, job enters `review_required`, **no automatic repeat**, to avoid duplicates.

Supported approved video origins: permanent GitHub raw files in `lsevmos-gpt/ls-vk/main/media/`, plus the pre-existing `ls-social-media-bridge.ls-evmos.workers.dev` MP4 path. Strongly prefer permanent GitHub files rather than expiring Adobe short URLs. Per-request video limit currently 95,000,000 bytes. Video input should be Meta-compatible H.264/AAC MP4 before scheduling. Video carousel children also call the new binary uploader. Image/photo Stories keep the existing public `image_url` flow.

**Custom cover limitation:** Instagram Graph API still requires a public JPEG `cover_url` for an independently designed cover; Meta fetches that small image. The video itself is uploaded directly. Alternatively `thumb_offset` can choose an existing video frame, but that is not equivalent to the approved custom cover. Store custom covers at a persistent URL, such as GitHub raw, rather than an expiring Adobe URL.

## Non-public acceptance tests (23.11.2026)

| Test ID | Kind | Transfer bytes | Meta result | Public post |
|---|---|---:|---|---|
| `diag-direct-rupload-20261123-no-publish` | Reels, 1440×2560 | 47,593,685 | `FINISHED`, D1 `validated` | Never called |
| `diag-video-story-direct-20261123-no-publish` | Video Stories | 2,921,685 | `FINISHED`, D1 `validated` | Never called |

Both diagnostic D1 records have `approved=0`, `media_id=NULL`; no pending jobs remain. Existing Story-image jobs and the prior published Reels records were untouched.

## Rollback

Cloudflare keeps deploy versions. Prior *production* versions before this change:
- Scheduler: `e2344c36-64dc-4a95-b4a2-8d1c6c76436d`.
- Gateway: `ab7d5c96-7b42-4627-ac90-73e917324b23`.

Roll back by creating a Cloudflare Worker deployment selecting each previous version at 100%. Roll back both workers together if the direct-mode RPC ever becomes incompatible; do not change DNS, other Workers, or D1 schema. Preserve any later work before rolling back.

## Future deployment guardrails

Use `bindings_inherit=strict` when updating either script; verify D1/service/secret bindings survive. Do not leak Meta access tokens to D1, GitHub, logs or browser. Run binary-upload diagnostics with `extra_json.test_only=true` and a future publish time so `media_publish` cannot be called. Deactivate test jobs after validation. No further public publication was initiated by the migration.
