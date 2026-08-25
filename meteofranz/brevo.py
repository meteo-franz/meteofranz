from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .config import env


API_ROOT = "https://api.brevo.com/v3"


def _request(method: str, path: str, payload: dict | None = None):
    api_key = env("BREVO_API_KEY", required=True)
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{API_ROOT}{path}",
        data=body,
        method=method,
        headers={
            "api-key": api_key,
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": "MeteoFranz/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Errore Brevo {exc.code}: {details}") from exc


def resolve_list_id(list_name: str) -> int:
    offset = 0
    while offset < 1000:
        data = _request("GET", f"/contacts/lists?limit=50&offset={offset}&sort=desc")
        lists = data.get("lists", [])
        for item in lists:
            if item.get("name", "").strip().casefold() == list_name.strip().casefold():
                return int(item["id"])
        if len(lists) < 50:
            break
        offset += 50
    raise RuntimeError(f"Lista Brevo non trovata: {list_name}")


def create_campaign(
    *, html_content: str, subject: str, send_at: datetime | None = None
) -> int:
    list_name = env("BREVO_LIST_NAME", "MeteoFranz – amici")
    list_id = resolve_list_id(list_name)
    sender_email = env("BREVO_SENDER_EMAIL", required=True)
    sender_name = env("BREVO_SENDER_NAME", "MeteoFranz")
    now_label = datetime.now().strftime("%Y-%m-%d %H:%M")
    payload: dict = {
        "sender": {"name": sender_name, "email": sender_email},
        "name": f"MeteoFranz {now_label}",
        "subject": subject,
        "htmlContent": html_content,
        "recipients": {"listIds": [list_id]},
    }
    if send_at is not None:
        payload["scheduledAt"] = (
            send_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        )
    response = _request("POST", "/emailCampaigns", payload)
    return int(response["id"])


def send_now(campaign_id: int) -> None:
    _request("POST", f"/emailCampaigns/{campaign_id}/sendNow", {})
