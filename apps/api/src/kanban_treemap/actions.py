import hashlib
import json
import logging
import time
from datetime import UTC, datetime, timedelta

from .classify import ask_llm, parse_json, strict_object
from .config import settings

log = logging.getLogger("kanban_treemap")
MAX_THREADS = 40
FEEDBACK_STATES = {"done", "snoozed", "dismissed"}
DONE_MEMORY_DAYS = 14
MAX_FEEDBACK_IN_PROMPT = 30

ACTIONS_SCHEMA = strict_object(
    {
        "why": {"type": "string"},
        "confidence": {"type": "number"},
        "actions": {
            "type": "array",
            "items": strict_object(
                {
                    "text": {"type": "string"},
                    "due": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                    "sources": {
                        "type": "array",
                        "items": strict_object({"item_id": {"type": "string"}, "quote": {"type": "string"}}),
                    },
                }
            ),
        },
    }
)

PROMPT = """You are my work assistant. Today is {today}.
Below are the recent message threads of my project "{name}" ({description}).

List EVERY concrete action I still need to take for this project, ranked with the
most urgent and important first. Rules:
- Merge duplicates: the same task mentioned in several threads is one action.
- Skip FYIs, newsletters, and anything I already handled (e.g. I sent the last message and nothing is pending).
- Each action: imperative, at most 12 words, include who and any deadline mentioned.
- sources: EVERY thread this action comes from. For each: item_id (the thread id) and quote
  (the exact words from that thread's text that show the action, copied verbatim, at most 15 words).
- due: YYYY-MM-DD if a deadline is mentioned or implied (resolve words like "Friday" using today's date), else null.
- confidence: 0.0-1.0, how sure you are this is a real action for me.
- why: one sentence on why this project needs my attention now, or that it doesn't.
- project confidence: 0.0-1.0, how sure you are about the overall assessment.
{feedback}
Respond with JSON only:
{{"why": "...", "confidence": 0.9, "actions": [{{"text": "...", "due": null, "confidence": 0.9, "sources": [{{"item_id": "...", "quote": "..."}}]}}]}}
Use an empty actions list if there is nothing to do."""


def norm(text):
    return " ".join(text.lower().split())


def set_feedback(c, project_id, text, state, today):
    if state is None:
        c.execute("delete from action_feedback where project_id=? and norm=?", [project_id, norm(text)])
        return
    if state not in FEEDBACK_STATES:
        raise ValueError(f"state must be one of {sorted(FEEDBACK_STATES)} or null")
    until = (today + timedelta(days=1)).isoformat() if state == "snoozed" else None
    c.execute(
        """insert into action_feedback(project_id, norm, text, state, until, created_at) values(?, ?, ?, ?, ?, ?)
        on conflict(project_id, norm) do update set text=excluded.text, state=excluded.state,
        until=excluded.until, created_at=excluded.created_at""",
        [project_id, norm(text), text, state, until, datetime.now(UTC).isoformat()],
    )


def active_feedback(c, project_id, today):
    rows = c.execute(
        "select * from action_feedback where project_id=? order by created_at desc", [project_id]
    ).fetchall()
    return [dict(r) for r in rows if r["state"] != "snoozed" or r["until"] > today.isoformat()]


def _feedback_prompt(feedback, today):
    done_cutoff = (today - timedelta(days=DONE_MEMORY_DAYS)).isoformat()
    groups = {
        "Already done by me (do not list again unless a newer message asks for more)": [
            f["text"] for f in feedback if f["state"] == "done" and f["created_at"][:10] >= done_cutoff
        ],
        "Not actions, I dismissed them (never suggest these or similar ones)": [
            f["text"] for f in feedback if f["state"] == "dismissed"
        ],
        "Snoozed by me (do not list before the date)": [
            f"{f['text']} (until {f['until']})" for f in feedback if f["state"] == "snoozed"
        ],
    }
    lines = [
        f"- {title}:\n" + "\n".join(f"  * {t}" for t in texts[:MAX_FEEDBACK_IN_PROMPT])
        for title, texts in groups.items()
        if texts
    ]
    return "\nMy feedback on earlier suggestions, respect it:\n" + "\n".join(lines) + "\n" if lines else ""


def _hash(project, items, today, feedback):
    key = ["v3", project.get("name"), project.get("description"), today.isoformat()]
    key += [(i["id"], i["updated_at"], i["needs_reply"]) for i in items]
    key += [(f["norm"], f["state"], f["until"]) for f in feedback]
    return hashlib.sha1(json.dumps(key, default=str).encode()).hexdigest()


def _confidence(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


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
        feedback = active_feedback(c, p["id"], today)
        key = _hash(p, items, today, feedback)
        row = c.execute("select items_hash from project_actions where project_id=?", [p["id"]]).fetchone()
        if row and row["items_hash"] == key:
            continue
        payload = [
            {k: it[k] for k in ("id", "source", "title", "summary", "needs_reply", "last_from_me", "updated_at")}
            | {"text": (it["body"] or "")[:600]}
            for it in items
        ]
        started = time.monotonic()
        answer = parse_json(
            ask_llm(
                s,
                PROMPT.format(
                    today=today.isoformat(),
                    name=p["name"],
                    description=p.get("description", ""),
                    feedback=_feedback_prompt(feedback, today),
                ),
                json.dumps(payload, ensure_ascii=False),
                f'actions for "{p["name"]}" ({len(items)} threads)',
                ACTIONS_SCHEMA,
            )
        )
        by_id = {it["id"]: it for it in items}
        actions = []
        for a in answer.get("actions", []):
            text = str(a.get("text") or "").strip()
            if not text:
                continue
            sources = []
            for src in a.get("sources") or []:
                item = by_id.get(src.get("item_id")) if isinstance(src, dict) else None
                if item and item["id"] not in [x["item_id"] for x in sources]:
                    sources.append(
                        {
                            "item_id": item["id"],
                            "source": item["source"],
                            "title": item["title"],
                            "quote": str(src.get("quote") or "").strip(),
                        }
                    )
            actions.append(
                {
                    "text": text,
                    "due": a.get("due") or None,
                    "confidence": _confidence(a.get("confidence")),
                    "sources": sources,
                }
            )
        result = {
            "why": str(answer.get("why") or "").strip(),
            "confidence": _confidence(answer.get("confidence")),
            "latency": round(time.monotonic() - started, 1),
            "actions": actions,
        }
        c.execute(
            """insert into project_actions(project_id, items_hash, actions_json) values(?, ?, ?)
            on conflict(project_id) do update set items_hash=excluded.items_hash, actions_json=excluded.actions_json""",
            [p["id"], key, json.dumps(result, ensure_ascii=False)],
        )
        c.commit()
        updated += 1
        log.info('actions for "%s": %d actions saved', p["name"], len(actions))
    return updated


def load(c, today):
    feedback = {}
    for r in c.execute("select * from action_feedback"):
        if r["state"] != "snoozed" or r["until"] > today.isoformat():
            feedback[(r["project_id"], r["norm"])] = r["state"]
    result = {}
    for r in c.execute("select * from project_actions"):
        data = json.loads(r["actions_json"])
        if isinstance(data, list):
            data = {"why": "", "confidence": None, "latency": None, "actions": data}
        for a in data["actions"]:
            a["feedback"] = feedback.get((r["project_id"], norm(a["text"])))
        result[r["project_id"]] = data
    return result
