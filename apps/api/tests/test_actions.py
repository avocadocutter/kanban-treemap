import json
import os
import tempfile
from datetime import date

os.environ.setdefault("KANBAN_TREEMAP_HOME", tempfile.mkdtemp())
os.environ.setdefault("LLM_PROVIDER", "api")
os.environ.setdefault("LLM_BASE_URL", "http://x")
os.environ.setdefault("LLM_MODEL", "m")
os.environ.setdefault("LLM_API_KEY", "k")
os.environ.setdefault("CLICKUP_API_TOKEN", "x")
os.environ.setdefault("PORT", "8765")

from kanban_treemap import actions, db

PROJECTS = [{"id": "web", "name": "Website", "importance": 5, "description": "d"}]


def test_actions_are_saved_validated_and_cached(monkeypatch):
    c = db.conn()
    c.execute("delete from items")
    c.execute("delete from project_actions")
    c.execute(
        "insert into items(id,source,title,body,url,people,updated_at,last_from_me,project,needs_reply) "
        "values('gmail:1','gmail','Logo','Laura: v3 by Friday?','u','','2026-09-27',0,'web',1)"
    )
    calls = []

    def fake_llm(s, system, user):
        calls.append(user)
        return json.dumps({"actions": [
            {"text": "Send logo v3 to Laura", "item_id": "gmail:1", "due": "2026-10-02"},
            {"text": "Invented thread", "item_id": "nope", "due": None},
            {"text": "  ", "item_id": "gmail:1"},
        ]})

    monkeypatch.setattr(actions, "ask_llm", fake_llm)
    assert actions.run(c, PROJECTS, date(2026, 9, 28)) == 1
    saved = actions.load(c)["web"]
    assert saved == [
        {"text": "Send logo v3 to Laura", "item_id": "gmail:1", "source": "gmail", "due": "2026-10-02"},
        {"text": "Invented thread", "item_id": None, "source": None, "due": None},
    ]
    assert actions.run(c, PROJECTS, date(2026, 9, 28)) == 0
    assert len(calls) == 1
    assert actions.run(c, PROJECTS, date(2026, 9, 29)) == 1
