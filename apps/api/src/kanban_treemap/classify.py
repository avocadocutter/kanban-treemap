import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import requests

from .config import settings
from .treemap import alias_match

BATCH = 15

PROMPT = """You triage my work messages into projects.

Projects:
{projects}

For each item return:
- project: one of the project ids above, or "other" if none fits
- needs_reply: true only if a real person is waiting for an answer or action from me. False for newsletters, notifications, automated mail, FYIs, or when last_from_me is true.
- summary: at most 15 words, what this is about and what (if anything) I must do

Respond with JSON only: {{"items": [{{"id": "...", "project": "...", "needs_reply": false, "summary": "..."}}]}}"""


def ask_llm(s, system, user):
    if s["LLM_PROVIDER"] == "codex":
        return ask_codex(system, user)
    r = requests.post(
        f"{s['LLM_BASE_URL'].rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {s['LLM_API_KEY']}"},
        json={
            "model": s["LLM_MODEL"],
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        },
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def ask_codex(system, user):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "answer.txt"
        p = subprocess.run(
            ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only", "-o", str(out), "-"],
            input=f"{system}\n\nItems:\n{user}",
            capture_output=True,
            text=True,
            cwd=tmp,
            timeout=600,
            check=False,
        )
        if p.returncode != 0:
            raise RuntimeError(f"codex failed (try `codex login`): {p.stderr.strip()[-400:]}")
        return out.read_text()


def parse_json(text):
    return json.loads(text[text.find("{") : text.rfind("}") + 1])


def run(c, projects):
    phash = hashlib.sha1(json.dumps(projects, default=str, sort_keys=True).encode()).hexdigest()[:8]
    todo = [
        dict(r)
        for r in c.execute("select * from items")
        if r["classified_for"] != f"{r['updated_at']}|{phash}"
    ]
    if not todo:
        return 0
    s = settings()
    ids = {p["id"] for p in projects}
    listing = "\n".join(f"- {p['id']}: {p['name']} — {p.get('description', '')}" for p in projects)
    done = 0
    for i in range(0, len(todo), BATCH):
        batch = {it["id"]: it for it in todo[i : i + BATCH]}
        payload = [
            {k: it[k] for k in ("id", "source", "title", "people", "last_from_me")} | {"text": (it["body"] or "")[:800]}
            for it in batch.values()
        ]
        answer = ask_llm(s, PROMPT.format(projects=listing), json.dumps(payload, ensure_ascii=False))
        for out in parse_json(answer).get("items", []):
            it = batch.get(out.get("id"))
            if not it:
                continue
            project = alias_match(it, projects) or (out.get("project") if out.get("project") in ids else "other")
            needs_reply = bool(out.get("needs_reply")) and not it["last_from_me"]
            c.execute(
                "update items set project=?, needs_reply=?, summary=?, classified_for=? where id=?",
                [project, needs_reply, out.get("summary", ""), f"{it['updated_at']}|{phash}", it["id"]],
            )
            done += 1
        c.commit()
    return done
