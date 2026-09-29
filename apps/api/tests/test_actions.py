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
TODAY = date(2026, 9, 28)


def fresh_db():
    c = db.conn()
    for table in ("items", "project_actions", "action_feedback"):
        c.execute(f"delete from {table}")
    c.execute(
        "insert into items(id,source,title,body,url,people,updated_at,last_from_me,project,needs_reply) "
        "values('gmail:1','gmail','Logo','Laura: v3 by Friday?','u','','2026-09-27',0,'web',1)"
    )
    c.commit()
    return c


def test_actions_are_saved_validated_and_cached(monkeypatch):
    c = fresh_db()
    calls = []

    def fake_llm(s, system, user, label, schema):
        calls.append(system)
        return json.dumps({"why": "Laura is waiting", "confidence": 1.4, "actions": [
            {"text": "Send logo v3 to Laura", "due": "2026-10-02", "confidence": 0.9, "sources": [
                {"item_id": "gmail:1", "quote": "v3 by Friday?"},
                {"item_id": "gmail:1", "quote": "duplicate"},
                {"item_id": "nope", "quote": "invented thread"},
            ]},
            {"text": "No sources", "due": None, "confidence": "high"},
            {"text": "  ", "sources": [{"item_id": "gmail:1"}]},
        ]})

    monkeypatch.setattr(actions, "ask_llm", fake_llm)
    assert actions.run(c, PROJECTS, TODAY) == 1
    saved = actions.load(c, TODAY)["web"]
    assert saved["why"] == "Laura is waiting"
    assert saved["confidence"] == 1.0
    assert saved["actions"] == [
        {"text": "Send logo v3 to Laura", "due": "2026-10-02", "confidence": 0.9, "feedback": None, "sources": [
            {"item_id": "gmail:1", "source": "gmail", "title": "Logo", "quote": "v3 by Friday?"},
        ]},
        {"text": "No sources", "due": None, "confidence": None, "feedback": None, "sources": []},
    ]
    assert actions.run(c, PROJECTS, TODAY) == 0
    assert len(calls) == 1
    assert actions.run(c, PROJECTS, date(2026, 9, 29)) == 1
    c.close()


def test_feedback_is_shown_sent_to_ai_and_snooze_expires(monkeypatch):
    c = fresh_db()
    prompts = []

    def fake_llm(s, system, user, label, schema):
        prompts.append(system)
        return json.dumps({"why": "w", "confidence": 0.8, "actions": [
            {"text": "Send logo v3 to Laura", "confidence": 0.9, "sources": []},
            {"text": "Read the newsletter", "confidence": 0.3, "sources": []},
        ]})

    monkeypatch.setattr(actions, "ask_llm", fake_llm)
    actions.run(c, PROJECTS, TODAY)
    actions.set_feedback(c, "web", "Read  the Newsletter", "dismissed", TODAY)
    actions.set_feedback(c, "web", "Send logo v3 to Laura", "snoozed", TODAY)

    states = {a["text"]: a["feedback"] for a in actions.load(c, TODAY)["web"]["actions"]}
    assert states == {"Send logo v3 to Laura": "snoozed", "Read the newsletter": "dismissed"}

    assert actions.run(c, PROJECTS, TODAY) == 1
    assert "never suggest these" in prompts[-1] and "Read  the Newsletter" in prompts[-1]
    assert "until 2026-09-29" in prompts[-1]

    tomorrow = date(2026, 9, 29)
    states = {a["text"]: a["feedback"] for a in actions.load(c, tomorrow)["web"]["actions"]}
    assert states["Send logo v3 to Laura"] is None

    actions.set_feedback(c, "web", "Read the newsletter", None, TODAY)
    assert actions.active_feedback(c, "web", tomorrow) == []
    c.commit()
    c.close()
