import os
import tempfile
from datetime import UTC, datetime

os.environ.setdefault("KANBAN_TREEMAP_HOME", tempfile.mkdtemp())

from kanban_treemap import clickup, db

NOW_MS = int(datetime.now(UTC).timestamp() * 1000)
DAY_MS = 86400 * 1000
WINDOW_MS = NOW_MS - 14 * DAY_MS
SINCE_MS = NOW_MS - DAY_MS


def fake_get(calls):
    responses = {
        "/v2/user": {"user": {"id": 7}},
        "/v2/team": {"teams": [{"id": "900"}]},
        "/v3/workspaces/900/chat/channels": {"data": [{"id": "c1", "name": "acme-launch"}, {"id": "c2", "name": "old"}]},
        "/v3/workspaces/900/chat/channels/c1/messages": {
            "data": [
                {"user_id": "3", "content": "can you review the copy?", "date": NOW_MS},
                {"user_id": 7, "content": "draft is up", "date": NOW_MS - 3 * DAY_MS},
                {"user_id": "3", "content": "kickoff", "date": NOW_MS - 20 * DAY_MS},
            ]
        },
        "/v3/workspaces/900/chat/channels/c2/messages": {"data": [{"user_id": "3", "content": "hi", "date": NOW_MS - 30 * DAY_MS}]},
    }

    def _get(path, **params):
        calls.append((path, params))
        return responses[path]

    return _get


def test_chats_asks_only_for_changed_channels_but_keeps_window_context(monkeypatch):
    calls = []
    monkeypatch.setattr(clickup, "_get", fake_get(calls))
    items = list(clickup.chats(WINDOW_MS, SINCE_MS))
    assert calls[2][1]["with_message_since"] == SINCE_MS
    assert [i["id"] for i in items] == ["clickup:c1"]
    assert items[0]["body"] == "me: draft is up\nthem: can you review the copy?"
    assert items[0]["last_from_me"] is False


def test_upsert_keeps_unchanged_items_and_delete_older_drops_stale():
    c = db.conn()
    row = {"source": "clickup", "title": "t", "body": "", "url": "", "people": "", "due_at": None, "last_from_me": 0}
    db.upsert(c, [row | {"id": "clickup:a", "updated_at": "2026-09-01T00:00:00+00:00"}, row | {"id": "clickup:b", "updated_at": "2026-09-20T00:00:00+00:00"}])
    db.upsert(c, [row | {"id": "clickup:c", "updated_at": "2026-09-27T00:00:00+00:00"}])
    db.delete_older(c, "clickup", "2026-09-14T00:00:00+00:00")
    assert sorted(r["id"] for r in c.execute("select id from items where source='clickup'")) == ["clickup:b", "clickup:c"]
    db.set_state(c, "k", "1")
    db.set_state(c, "k", "2")
    assert db.get_state(c, "k") == "2"
