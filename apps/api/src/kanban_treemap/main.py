import json
import logging
import time
from datetime import UTC, datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import actions, classify, clickup, db, gsuite, treemap
from .config import HOME, settings

LOG_FILE = HOME / "kanban-treemap.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=1)],
)
log = logging.getLogger("kanban_treemap")

cfg = settings()
log.info(
    "started: ai=%s%s, clickup=%s, google=%s, config=%s",
    cfg["LLM_PROVIDER"],
    f" ({cfg['LLM_MODEL']} @ {cfg['LLM_BASE_URL']})" if cfg["LLM_PROVIDER"] == "api" else "",
    "on" if cfg["CLICKUP_API_TOKEN"] else "off",
    "on" if cfg["GOOGLE_CLIENT_ID"] else "off",
    HOME,
)
app = FastAPI()


class Feedback(BaseModel):
    project_id: str
    text: str
    state: str | None


@app.exception_handler(Exception)
def log_unhandled(request: Request, exc: Exception):
    log.exception("%s %s failed", request.method, request.url.path)
    return JSONResponse({"detail": f"{type(exc).__name__}: {exc}"}, status_code=500)
STATIC = Path(__file__).parent / "static"


def _today():
    return datetime.now().astimezone().date()


@app.get("/api/auth/google")
def google_auth():
    return RedirectResponse(gsuite.auth_url())


@app.get("/api/auth/google/callback")
def google_callback(state: str, code: str):
    gsuite.finish_auth(state, code)
    log.info("google: connected")
    return RedirectResponse(settings()["WEB_URL"])


@app.post("/api/sync")
def sync(days: int = 14):
    cfg = settings()
    log.info("sync: started (last %s days)", days)
    fetched, warnings, sources = {}, [], {}
    started = datetime.now(UTC)
    window_start = started - timedelta(days=days)
    window_ms = int(window_start.timestamp() * 1000)
    if cfg["CLICKUP_API_TOKEN"]:
        with db.conn() as c:
            since_ms = max(window_ms, int(db.get_state(c, "clickup_synced_ms") or 0))
        sources["clickup"] = lambda: clickup.chats(window_ms, since_ms)
    if cfg["GOOGLE_CLIENT_ID"]:
        s = gsuite.session()
        if s:
            me = gsuite.me(s)
            sources["gmail"] = lambda: gsuite.gmail(s, me["email"], days)
            sources["chat"] = lambda: gsuite.chat(s, me["sub"], days)
        else:
            warnings.append("google: not connected yet, click Connect Google")
    fetch_started = time.monotonic()
    for name, fetch in sources.items():
        t = time.monotonic()
        log.info("sync: fetching %s...", name)
        try:
            fetched[name] = list(fetch())
            log.info("sync: %s fetched %d items in %.1fs", name, len(fetched[name]), time.monotonic() - t)
        except requests.HTTPError as e:
            warnings.append(f"{name}: {e.response.status_code} {e.response.text[:200]}")
    for w in warnings:
        log.warning("sync: %s", w)
    with db.conn() as c:
        for name, items in fetched.items():
            if name == "clickup":
                db.upsert(c, items)
                db.delete_older(c, "clickup", window_start.isoformat())
                db.set_state(c, "clickup_synced_ms", str(int(started.timestamp() * 1000)))
            else:
                db.replace_source(c, name, items)
    log.info("sync: saved fetched items")
    fetch_seconds = time.monotonic() - fetch_started
    classify_started = time.monotonic()
    classified = 0
    with db.conn() as c:
        try:
            classified = classify.run(c, db.load_projects())
        except (RuntimeError, requests.RequestException) as e:
            log.error("sync: AI classification failed: %s", e)
            warnings.append(f"AI classification failed, unsorted items are in Unclassified: {e}")
    classify_seconds = time.monotonic() - classify_started
    actions_started = time.monotonic()
    updated = 0
    with db.conn() as c:
        try:
            updated = actions.run(c, db.load_projects(), _today())
        except (RuntimeError, requests.RequestException) as e:
            log.error("sync: action list failed: %s", e)
            warnings.append(f"Action list failed, showing the previous one: {e}")
    last_run = {
        "at": datetime.now(UTC).isoformat(),
        "model": classify.describe_provider(cfg),
        "steps": [
            {"name": "fetch", "seconds": round(fetch_seconds, 1), "detail": " · ".join(f"{k} {len(v)}" for k, v in fetched.items())},
            {"name": "classify", "seconds": round(classify_seconds, 1), "detail": f"{classified} messages"},
            {"name": "actions", "seconds": round(time.monotonic() - actions_started, 1), "detail": f"{updated} projects updated"},
        ],
    }
    with db.conn() as c:
        db.set_state(c, "last_run", json.dumps(last_run))
    log.info("sync: done, %d items classified", classified)
    return {"fetched": {k: len(v) for k, v in fetched.items()}, "classified": classified, "warnings": warnings}


def _nodes(c):
    nodes = treemap.project_nodes(db.load_projects(), db.all_items(c), _today(), settings()["DEADLINE_WARNING_DAYS"])
    project_actions = actions.load(c, _today())
    for n in nodes:
        data = project_actions.get(n["id"], {})
        n["actions"] = data.get("actions", [])
        n["why"] = data.get("why", "")
        n["confidence"] = data.get("confidence")
        n["latency"] = data.get("latency")
    return nodes


@app.post("/api/actions/feedback")
def action_feedback(body: Feedback):
    try:
        with db.conn() as c:
            actions.set_feedback(c, body.project_id, body.text, body.state, _today())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    log.info("feedback: %s -> %s", body.text, body.state or "undo")
    return {"ok": True}


@app.get("/api/treemap")
def get_treemap():
    with db.conn() as c:
        nodes = _nodes(c)
        last_run = db.get_state(c, "last_run")
    return {
        "projects": nodes,
        "google_enabled": bool(settings()["GOOGLE_CLIENT_ID"]),
        "google_connected": gsuite.TOKEN.exists(),
        "last_run": json.loads(last_run) if last_run else None,
    }


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    with db.conn() as c:
        items = db.all_items(c)
        node = next((n for n in _nodes(c) if n["id"] == project_id), None)
    if not node:
        raise HTTPException(404, "Unknown project")
    mine = [i for i in items if (i["project"] or "other") == project_id]
    return {"project": node, "items": treemap.sort_items(mine, _today())}


if STATIC.exists():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        return FileResponse(STATIC / "index.html")
