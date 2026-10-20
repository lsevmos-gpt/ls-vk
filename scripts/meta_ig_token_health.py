"""Read-only Meta Instagram credential and optional expiry inspection.

Never prints access tokens or App Secret. Never creates/publishes media.
An optional Meta App ID + App Secret enables Graph /debug_token introspection.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .instagram_collab import MetaClient, CollabError

GRAPH_BASE = "https://graph.facebook.com/v26.0/"
EXPIRY_WARNING_DAYS = 14


def get_token_metadata(token: str, app_id: str, app_secret: str, *, opener=urlopen) -> dict:
    """Official read-only Graph debug_token; never return or print secrets."""
    if not (app_id.isdecimal() and app_secret and token):
        raise ValueError("Meta App ID, App Secret and IG token are required for token metadata")
    url = GRAPH_BASE + "debug_token?" + urlencode({"input_token": token})
    request = Request(
        url, method="GET",
        headers={"Authorization": "Bearer " + app_id + "|" + app_secret,
                 "Accept": "application/json"},
    )
    try:
        with opener(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError("Meta debug_token HTTP " + str(exc.code)) from None
    except (URLError, TimeoutError, OSError):
        raise RuntimeError("Meta debug_token unavailable") from None
    except (ValueError, UnicodeError, AttributeError):
        raise RuntimeError("Meta debug_token returned invalid JSON") from None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError("Meta debug_token did not return metadata")
    return data


def days_until(epoch: object, now: datetime | None = None) -> float | None:
    """Meta 0 or null means no fixed expiry, not guaranteed permanent validity."""
    if epoch in (None, 0, "0", ""):
        return None
    if not isinstance(epoch, (int, float)) or epoch <= 0:
        raise ValueError("Unsupported Meta expiration value")
    now = now or datetime.now(timezone.utc)
    return (datetime.fromtimestamp(epoch, tz=timezone.utc) - now).total_seconds() / 86400


def inspect_metadata(data: dict, *, now: datetime | None = None) -> tuple[str, bool]:
    """Return sanitized summary and whether credential needs attention."""
    if data.get("is_valid") is not True:
        return "TOKEN_VALID=false", True
    token_type = str(data.get("type", "unknown"))
    fixed_exp = days_until(data.get("expires_at"), now)
    data_exp = days_until(data.get("data_access_expires_at"), now)
    msg = "TOKEN_VALID=true TYPE=" + token_type
    alert = False
    if fixed_exp is None:
        msg += " EXPIRES_AT=no_fixed_date_reported"
    else:
        msg += " EXPIRES_IN_DAYS=" + str(round(fixed_exp, 1))
        if fixed_exp <= EXPIRY_WARNING_DAYS:
            alert = True
    if data_exp is not None:
        msg += " DATA_ACCESS_EXPIRES_IN_DAYS=" + str(round(data_exp, 1))
        if data_exp <= EXPIRY_WARNING_DAYS:
            alert = True
    scopes = data.get("scopes", [])
    if isinstance(scopes, list) and scopes:
        if "instagram_content_publish" not in scopes:
            msg += " WARNING=content_publish_scope_not_reported"
    return msg, alert


def main() -> int:
    try:
        token = os.environ.get("META_IG_ACCESS_TOKEN", "")
        user_id = os.environ.get("META_IG_USER_ID", "")
        if not token or not user_id:
            raise RuntimeError("META_IG_ACCESS_TOKEN or META_IG_USER_ID missing")
        client = MetaClient(token, user_id,
                            graph_version=os.environ.get("META_GRAPH_VERSION", "v26.0"))
        info = client.verify_account()   # Actual, read-only Graph API GET.
        print("META_ACCOUNT_OK @" + info["username"] + " (read only)")
        app_id = os.environ.get("META_APP_ID", "")
        secret = os.environ.get("META_APP_SECRET", "")
        if bool(app_id) != bool(secret):
            print("::warning::Meta app credentials incomplete; expiry inspection disabled")
            return 0
        if not app_id:
            print("::warning::Meta App ID/Secret not configured; token expiry cannot be checked proactively")
            return 0
        details = get_token_metadata(token, app_id, secret)
        if str(details.get("app_id", "")) != app_id:
            raise RuntimeError("Meta token was issued by an unexpected app")
        line, urgent = inspect_metadata(details)
        print(line)
        if urgent:
            print("::error::Meta credential invalid or expiration/data access within 14 days")
            return 1
        return 0
    except (RuntimeError, ValueError, CollabError) as exc:
        print("::error::Meta credential health: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
