from datetime import UTC, datetime

import requests

from .config import settings

API = "https://api.clickup.com/api/v2"


def _get(path, **params):
    r = requests.get(f"{API}{path}", headers={"Authorization": settings()["CLICKUP_API_TOKEN"]}, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _iso_ms(ms):
    return datetime.fromtimestamp(int(ms) / 1000, UTC).isoformat() if ms else None


def tasks():
    user_id = _get("/user")["user"]["id"]
    for team in _get("/team")["teams"]:
        page = 0
        while True:
            r = _get(
                f"/team/{team['id']}/task",
                **{"assignees[]": user_id, "subtasks": "true", "include_closed": "false", "page": page},
            )
            for t in r["tasks"]:
                where = " / ".join(x.get("name", "") for x in (t.get("space") or {}, t.get("folder") or {}, t.get("list") or {}))
                yield {
                    "id": f"clickup:{t['id']}",
                    "source": "clickup",
                    "title": t["name"],
                    "body": f"[{t['status']['status']}] {(t.get('text_content') or '')[:600]}",
                    "url": t["url"],
                    "people": where,
                    "updated_at": _iso_ms(t["date_updated"]),
                    "due_at": _iso_ms(t.get("due_date")),
                    "last_from_me": False,
                }
            if r.get("last_page", True) or not r["tasks"]:
                break
            page += 1
