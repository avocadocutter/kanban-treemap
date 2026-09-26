import hashlib
import json

from groq import Groq

from .config import settings
from .treemap import alias_match

MODEL = "openai/gpt-oss-120b"
BATCH = 15

PROMPT = """You triage my work messages and tasks into projects.

Projects:
{projects}

For each item return:
- project: one of the project ids above, or "other" if none fits
- needs_reply: true only if a real person is waiting for an answer or action from me. False for newsletters, notifications, automated mail, FYIs, or when last_from_me is true. Always false for clickup items.
- summary: at most 15 words, what this is about and what (if anything) I must do

Respond with JSON only: {{"items": [{{"id": "...", "project": "...", "needs_reply": false, "summary": "..."}}]}}"""


def run(c, projects):
    phash = hashlib.sha1(json.dumps(projects, default=str, sort_keys=True).encode()).hexdigest()[:8]
    todo = [
        dict(r)
        for r in c.execute("select * from items")
        if r["classified_for"] != f"{r['updated_at']}|{phash}"
    ]
    if not todo:
        return 0
    client = Groq(api_key=settings()["GROQ_API_KEY"])
    ids = {p["id"] for p in projects}
    listing = "\n".join(f"- {p['id']}: {p['name']} — {p.get('description', '')}" for p in projects)
    done = 0
    for i in range(0, len(todo), BATCH):
        batch = {it["id"]: it for it in todo[i : i + BATCH]}
        payload = [
            {k: it[k] for k in ("id", "source", "title", "people", "last_from_me")} | {"text": (it["body"] or "")[:800]}
            for it in batch.values()
        ]
        resp = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PROMPT.format(projects=listing)},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        for out in json.loads(resp.choices[0].message.content).get("items", []):
            it = batch.get(out.get("id"))
            if not it:
                continue
            project = alias_match(it, projects) or (out.get("project") if out.get("project") in ids else "other")
            needs_reply = bool(out.get("needs_reply")) and it["source"] != "clickup" and not it["last_from_me"]
            c.execute(
                "update items set project=?, needs_reply=?, summary=?, classified_for=? where id=?",
                [project, needs_reply, out.get("summary", ""), f"{it['updated_at']}|{phash}", it["id"]],
            )
            done += 1
        c.commit()
    return done
