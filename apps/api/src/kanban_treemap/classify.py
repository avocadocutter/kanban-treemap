import hashlib
import json
import logging
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from .config import settings
from .treemap import alias_match

BATCH = 15
log = logging.getLogger("kanban_treemap")
RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRY_WAITS = [5, 15, 45]

PROMPT = """You triage my work messages into projects.

Projects:
{projects}

For each item return:
- project: one of the project ids above, or "other" if none fits
- needs_reply: true only if a real person is waiting for an answer or action from me. False for newsletters, notifications, automated mail, FYIs, or when last_from_me is true.
- summary: at most 15 words, what this is about and what (if anything) I must do

Respond with JSON only: {{"items": [{{"id": "...", "project": "...", "needs_reply": false, "summary": "..."}}]}}"""


HEARTBEAT_SECONDS = 15


def strict_object(properties):
    return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}


SORT_SCHEMA = strict_object(
    {
        "items": {
            "type": "array",
            "items": strict_object(
                {
                    "id": {"type": "string"},
                    "project": {"type": "string"},
                    "needs_reply": {"type": "boolean"},
                    "summary": {"type": "string"},
                }
            ),
        }
    }
)


def describe_provider(s):
    if s["LLM_PROVIDER"] == "claude":
        return f"claude ({s['LLM_MODEL'] or 'haiku'})"
    if s["LLM_PROVIDER"] == "codex":
        return "codex"
    return f"{s['LLM_MODEL']} at {s['LLM_BASE_URL']}"


def ask_llm(s, system, user, label, schema):
    provider = describe_provider(s)
    log.info("%s: asking %s...", label, provider)
    started = time.monotonic()
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(_ask, s, system, user, schema)
        while True:
            try:
                answer = future.result(timeout=HEARTBEAT_SECONDS)
                break
            except TimeoutError:
                log.info("%s: still waiting for %s (%ds so far)", label, provider, time.monotonic() - started)
    log.info("%s: answer received in %.1fs", label, time.monotonic() - started)
    return answer


def _ask(s, system, user, schema):
    if s["LLM_PROVIDER"] == "claude":
        return ask_claude(system, user, s["LLM_MODEL"] or "haiku", schema)
    if s["LLM_PROVIDER"] == "codex":
        return ask_codex(system, user, schema)
    for wait in [*RETRY_WAITS, None]:
        r = requests.post(
            f"{s['LLM_BASE_URL'].rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {s['LLM_API_KEY']}"},
            json={
                "model": s["LLM_MODEL"],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "response", "schema": schema, "strict": True},
                },
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=180,
        )
        if r.status_code not in RETRY_STATUSES or wait is None:
            break
        log.warning("AI provider busy (%s), retrying in %ss", r.status_code, wait)
        time.sleep(wait)
    if not r.ok:
        raise RuntimeError(f"{r.status_code} from {r.url}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def ask_claude(system, user, model, schema):
    with tempfile.TemporaryDirectory() as tmp:
        p = subprocess.run(
            [
                "claude", "-p", "--output-format", "json", "--model", model, "--tools", "",
                "--system-prompt", system, "--setting-sources", "", "--strict-mcp-config",
                "--mcp-config", '{"mcpServers":{}}', "--disable-slash-commands", "--no-session-persistence",
                "--json-schema", json.dumps(schema),
            ],
            input=user,
            capture_output=True,
            text=True,
            cwd=tmp,
            timeout=600,
            check=False,
        )
    try:
        out = json.loads(p.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude failed (try running `claude` and /login): {(p.stderr or p.stdout).strip()[-400:]}") from None
    if p.returncode != 0 or out.get("is_error"):
        raise RuntimeError(f"claude failed (try running `claude` and /login): {out.get('result', '')[:400]}")
    if "structured_output" not in out:
        raise RuntimeError(f"claude returned no structured output: {str(out.get('result', ''))[:400]}")
    return json.dumps(out["structured_output"])


def ask_codex(system, user, schema):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "answer.txt"
        schema_file = Path(tmp) / "schema.json"
        schema_file.write_text(json.dumps(schema))
        p = subprocess.run(
            [
                "codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only",
                "--output-schema", str(schema_file), "-o", str(out), "-",
            ],
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
    log.info("sorting: %d new or changed messages to sort", len(todo))
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
        label = f"sorting batch {i // BATCH + 1}/{-(-len(todo) // BATCH)} ({len(batch)} messages)"
        answer = ask_llm(s, PROMPT.format(projects=listing), json.dumps(payload, ensure_ascii=False), label, SORT_SCHEMA)
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
