import hashlib
import json
import logging
import time

from .classify import ask_llm, parse_json
from .config import settings

log = logging.getLogger("kanban_treemap")
MAX_THREADS = 40

PROMPT = """You are my work assistant. Today is {today}.
Below are the recent message threads of my project "{name}" ({description}).

List EVERY concrete action I still need to take for this project, ranked with the
most urgent and important first. Rules:
- Merge duplicates: the same task mentioned in several threads is one action.
- Skip FYIs, newsletters, and anything I already handled (e.g. I sent the last message and nothing is pending).
- Each action: imperative, at most 12 words, include who and any deadline mentioned.
- item_id: the id of the thread where the action comes from.
- due: YYYY-MM-DD if a deadline is mentioned or implied (resolve words like "Friday" using today's date), else null.

Respond with JSON only: {{"actions": [{{"text": "...", "item_id": "...", "due": null}}]}}
Return {{"actions": []}} if there is nothing to do."""


def _hash(project, items, today):
    key = [project.get("name"), project.get("description"), today.isoformat()]
    key += [(i["id"], i["updated_at"], i["needs_reply"]) for i in items]
    return hashlib.sha1(json.dumps(key, default=str).encode()).hexdigest()


def run(c, projects, today):
    s = settings()
    updated = 0
    for p in projects:
        items = [
            dict(r)
            for r in c.execute(
                "select * from items where project=? order by updated_at desc limit ?", [p["id"], MAX_THREADS]
            )
        ]
        if not items:
            c.execute("delete from project_actions where project_id=?", [p["id"]])
            continue
        key = _hash(p, items, today)
        row = c.execute("select items_hash from project_actions where project_id=?", [p["id"]]).fetchone()
        if row and row["items_hash"] == key:
            continue
        payload = [
            {k: it[k] for k in ("id", "source", "title", "summary", "needs_reply", "last_from_me", "updated_at")}
            | {"text": (it["body"] or "")[:600]}
            for it in items
        ]
        t = time.monotonic()
        log.info("actions: %s (%d threads)...", p["name"], len(items))
        answer = ask_llm(
            s,
            PROMPT.format(today=today.isoformat(), name=p["name"], description=p.get("description", "")),
            json.dumps(payload, ensure_ascii=False),
        )
        by_id = {it["id"]: it for it in items}
        actions = []
        for a in parse_json(answer).get("actions", []):
            text = str(a.get("text") or "").strip()
            if not text:
                continue
            item = by_id.get(a.get("item_id"))
            actions.append(
                {
                    "text": text,
                    "item_id": item["id"] if item else None,
                    "source": item["source"] if item else None,
                    "due": a.get("due") or None,
                }
            )
        c.execute(
            """insert into project_actions(project_id, items_hash, actions_json) values(?, ?, ?)
            on conflict(project_id) do update set items_hash=excluded.items_hash, actions_json=excluded.actions_json""",
            [p["id"], key, json.dumps(actions, ensure_ascii=False)],
        )
        c.commit()
        updated += 1
        log.info("actions: %s -> %d actions in %.1fs", p["name"], len(actions), time.monotonic() - t)
    return updated


def load(c):
    return {r["project_id"]: json.loads(r["actions_json"]) for r in c.execute("select * from project_actions")}
