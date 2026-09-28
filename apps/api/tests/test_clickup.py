from datetime import UTC, datetime

from kanban_treemap import clickup

NOW_MS = int(datetime.now(UTC).timestamp() * 1000)
OLD_MS = NOW_MS - 30 * 86400 * 1000

RESPONSES = {
    "/v2/user": {"user": {"id": 7}},
    "/v2/team": {"teams": [{"id": "900"}]},
    "/v3/workspaces/900/chat/channels": {"data": [{"id": "c1", "name": "acme-launch"}, {"id": "c2", "name": "old"}]},
    "/v3/workspaces/900/chat/channels/c1/messages": {
        "data": [
            {"user_id": "3", "content": "can you review the copy?", "date": NOW_MS},
            {"user_id": 7, "content": "draft is up", "date": NOW_MS - 1000},
        ]
    },
    "/v3/workspaces/900/chat/channels/c2/messages": {"data": [{"user_id": "3", "content": "hi", "date": OLD_MS}]},
}


def test_chats_keeps_recent_channels_and_marks_sender(monkeypatch):
    monkeypatch.setattr(clickup, "_get", lambda path, **_: RESPONSES[path])
    items = list(clickup.chats(days=14))
    assert [i["id"] for i in items] == ["clickup:c1"]
    assert items[0]["body"] == "me: draft is up\nthem: can you review the copy?"
    assert items[0]["last_from_me"] is False
    assert items[0]["url"] == "https://app.clickup.com/900/chat/r/c1"
