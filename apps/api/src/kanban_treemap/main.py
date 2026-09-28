from datetime import UTC, datetime
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import classify, clickup, db, gsuite, treemap
from .config import settings

settings()
app = FastAPI()
STATIC = Path(__file__).parent / "static"
sync_state = {"synced_at": None}


def _today():
    return datetime.now().astimezone().date()


@app.get("/api/auth/google")
def google_auth():
    return RedirectResponse(gsuite.auth_url())


@app.get("/api/auth/google/callback")
def google_callback(state: str, code: str):
    gsuite.finish_auth(state, code)
    return RedirectResponse(settings()["WEB_URL"])


@app.post("/api/sync")
def sync(days: int = 14):
    cfg = settings()
    fetched, warnings, sources = {}, [], {}
    if cfg["CLICKUP_API_TOKEN"]:
        sources["clickup"] = lambda: clickup.chats(days)
    if cfg["GOOGLE_CLIENT_ID"]:
        s = gsuite.session()
        if s:
            me = gsuite.me(s)
            sources["gmail"] = lambda: gsuite.gmail(s, me["email"], days)
            sources["chat"] = lambda: gsuite.chat(s, me["sub"], days)
        else:
            warnings.append("google: not connected yet, click Connect Google")
    for name, fetch in sources.items():
        try:
            fetched[name] = list(fetch())
        except requests.HTTPError as e:
            warnings.append(f"{name}: {e.response.status_code} {e.response.text[:200]}")
    with db.conn() as c:
        for name, items in fetched.items():
            db.replace_source(c, name, items)
        try:
            classified = classify.run(c, db.load_projects())
        except (RuntimeError, requests.RequestException) as e:
            raise HTTPException(502, f"AI classification failed: {e}") from e
    sync_state["synced_at"] = datetime.now(UTC).isoformat()
    return {"fetched": {k: len(v) for k, v in fetched.items()}, "classified": classified, "warnings": warnings}


@app.get("/api/treemap")
def get_treemap():
    with db.conn() as c:
        items = db.all_items(c)
    return {
        "projects": treemap.project_nodes(db.load_projects(), items, _today()),
        "google_enabled": bool(settings()["GOOGLE_CLIENT_ID"]),
        "google_connected": gsuite.TOKEN.exists(),
        "synced_at": sync_state["synced_at"],
    }


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    with db.conn() as c:
        items = db.all_items(c)
    node = next((n for n in treemap.project_nodes(db.load_projects(), items, _today()) if n["id"] == project_id), None)
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
