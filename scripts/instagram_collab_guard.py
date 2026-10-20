"""Reserve and finalize a one-shot Instagram Collab publication from GitHub Actions.

A reservation is committed BEFORE calling Meta, so uncertain outcomes cannot
silently result in duplicate Reels or duplicate invitations.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .instagram_collab import JOB_ID, ROOT, load_job

APPROVAL_PHRASE = "PUBLISH_APPROVED_COLLAB"


def receipt_paths(root: Path, job_id: str) -> tuple[Path, Path]:
    if not JOB_ID.fullmatch(job_id):
        raise ValueError("Invalid request id")
    return (
        root / "results" / "instagram-meta" / (job_id + ".json"),
        root / "instagram-meta-results" / (job_id + ".json"),
    )


def reserve(root: Path, job_id: str, confirmation: str, *,
            actor: str, event: str, branch: str, run_id: str) -> Path:
    if (actor, event, branch) != ("lsevmos-gpt", "workflow_dispatch", "refs/heads/main"):
        raise ValueError("Only owner-triggered GitHub Actions from main can publish Collab Reels")
    if confirmation != APPROVAL_PHRASE or not run_id:
        raise ValueError("Explicit confirmation and run ID are required")
    load_job(Path("requests/instagram-meta") / (job_id + ".json"), root=root)
    marker, transient = receipt_paths(root, job_id)
    if marker.exists() or transient.exists():
        raise ValueError("An earlier publication attempt exists; reconcile before creating a NEW id")
    marker.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "id": job_id,
        "platform": "instagram-meta",
        "status": "submission_started",
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "note": "Reserved before Meta mutation; DO NOT rerun or automatically retry this id.",
    }
    with marker.open("x", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return marker


def finalize(root: Path, job_id: str, run_id: str, exit_code: str) -> Path:
    marker, transient = receipt_paths(root, job_id)
    old = json.loads(marker.read_text(encoding="utf-8"))
    if old.get("status") != "submission_started" or old.get("run_id") != run_id:
        raise ValueError("Publication reservation mismatch")
    try:
        result = json.loads(transient.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        result = {}
    details = result.get("result") if isinstance(result, dict) else None
    media_id = details.get("published_media_id") if isinstance(details, dict) else None
    success = (exit_code == "0" and result.get("ok") is True
               and result.get("id") == job_id and isinstance(media_id, str) and media_id.isdecimal())
    record = {
        **old,
        "status": "published" if success else "manual_review_required",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "provider_ok": success,
        "note": ("Meta returned a media ID; invitation acceptance is not confirmed."
                 if success else "Meta outcome may be partial; inspect Instagram before any NEW attempt."),
    }
    if success:
        record["instagram_media_id"] = media_id
    marker.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return marker


def main() -> int:
    phase = sys.argv[1] if len(sys.argv) > 1 else ""
    job_id = os.environ.get("COLLAB_JOB_ID", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    try:
        if phase == "reserve":
            path = reserve(
                ROOT, job_id, os.environ.get("COLLAB_CONFIRMATION", ""),
                actor=os.environ.get("GITHUB_ACTOR", ""),
                event=os.environ.get("GITHUB_EVENT_NAME", ""),
                branch=os.environ.get("GITHUB_REF", ""),
                run_id=run_id,
            )
        elif phase == "finalize":
            path = finalize(ROOT, job_id, run_id, os.environ.get("PUBLISH_EXIT_CODE", ""))
        else:
            raise ValueError("Usage: python -m scripts.instagram_collab_guard <reserve|finalize>")
        print("COLLAB_RECEIPT=" + path.relative_to(ROOT).as_posix())
        return 0
    except (ValueError, OSError, TypeError, UnicodeError) as exc:
        print("::error::Instagram Collab guard: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
