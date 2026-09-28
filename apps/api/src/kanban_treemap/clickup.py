import logging
from datetime import UTC, datetime

import requests

from .config import settings

API = "https://api.clickup.com/api"
log = logging.getLogger("kanban_treemap")


def _get(path, **params):
    r = requests.get(f"{API}{path}", headers={"Authorization": settings()["CLICKUP_API_TOKEN"]}, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _iso_ms(ms):
    return datetime.fromtimestamp(int(ms) / 1000, UTC).isoformat()


def chats(window_ms, since_ms):
    my_id = str(_get("/v2/user")["user"]["id"])
    log.info("clickup: channels with messages since %s", _iso_ms(since_ms))
    for team in _get("/v2/team")["teams"]:
        ws = team["id"]
        cursor = None
        while True:
            page = _get(
                f"/v3/workspaces/{ws}/chat/channels",
                with_message_since=since_ms,
                limit=100,
                **({"cursor": cursor} if cursor else {}),
            )
            channels = page.get("data", [])
            log.info("clickup: workspace %s, %d active channels", ws, len(channels))
            for n, ch in enumerate(channels, 1):
                log.info("clickup: reading channel %d/%d %s", n, len(channels), ch.get("name") or "(direct message)")
                msgs = _get(
                    f"/v3/workspaces/{ws}/chat/channels/{ch['id']}/messages", limit=15, content_format="text/plain"
                ).get("data", [])
                msgs = [m for m in msgs if m["date"] >= window_ms]
                if not msgs:
                    continue
                yield {
                    "id": f"clickup:{ch['id']}",
                    "source": "clickup",
                    "title": ch.get("name") or "Direct message",
                    "body": "\n".join(
                        f"{'me' if str(m['user_id']) == my_id else 'them'}: {m['content'][:300]}" for m in reversed(msgs)
                    ),
                    "url": f"https://app.clickup.com/{ws}/chat/r/{ch['id']}",
                    "people": ch.get("name") or "",
                    "updated_at": _iso_ms(msgs[0]["date"]),
                    "due_at": None,
                    "last_from_me": str(msgs[0]["user_id"]) == my_id,
                }
            cursor = page.get("next_cursor")
            if not cursor:
                break
