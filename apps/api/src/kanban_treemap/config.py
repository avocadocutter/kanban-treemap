import os
import shutil
from functools import cache
from pathlib import Path

import yaml

HOME = Path(os.environ.get("KANBAN_TREEMAP_HOME") or Path.home() / ".kanban-treemap")
CONFIG_FILE = HOME / "config.yaml"
PROJECTS_FILE = HOME / "projects.yaml"
KEYS = ["LLM_PROVIDER", "PORT"]
SOURCE_KEYS = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "CLICKUP_API_TOKEN"]
API_KEYS = ["LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"]
PROVIDERS = ["codex", "api"]

CONFIG_TEMPLATE = """\
port: 8765
llm_provider: codex
google_client_id: ""
google_client_secret: ""
clickup_api_token: ""
"""


def init_home():
    HOME.mkdir(parents=True, exist_ok=True)
    created = []
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(CONFIG_TEMPLATE)
        CONFIG_FILE.chmod(0o600)
        created.append(CONFIG_FILE)
    if not PROJECTS_FILE.exists():
        shutil.copy(Path(__file__).parent / "projects.example.yaml", PROJECTS_FILE)
        created.append(PROJECTS_FILE)
    return created


@cache
def settings():
    file_cfg = (yaml.safe_load(CONFIG_FILE.read_text()) or {}) if CONFIG_FILE.exists() else {}
    values = {k: str(os.environ.get(k) or file_cfg.get(k.lower()) or "").strip() for k in KEYS + API_KEYS + SOURCE_KEYS}
    required = KEYS + (API_KEYS if values["LLM_PROVIDER"] == "api" else [])
    missing = [k.lower() for k in required if not values[k]]
    if missing:
        raise RuntimeError(f"Missing config: {', '.join(missing)}. Set them in {CONFIG_FILE} (or as upper-case env vars).")
    if bool(values["GOOGLE_CLIENT_ID"]) != bool(values["GOOGLE_CLIENT_SECRET"]):
        raise RuntimeError(f"Set both google_client_id and google_client_secret in {CONFIG_FILE}, or neither.")
    if not values["GOOGLE_CLIENT_ID"] and not values["CLICKUP_API_TOKEN"]:
        raise RuntimeError(f"Connect at least one source: set clickup_api_token and/or the google_client_* keys in {CONFIG_FILE}.")
    if values["LLM_PROVIDER"] not in PROVIDERS:
        raise RuntimeError(f"llm_provider must be one of: {', '.join(PROVIDERS)}")
    if values["LLM_PROVIDER"] == "codex" and not shutil.which("codex"):
        raise RuntimeError("llm_provider is codex but the codex CLI is not installed. Install it or switch llm_provider to api.")
    values["PORT"] = int(values["PORT"])
    values["WEB_URL"] = os.environ.get("WEB_URL") or f"http://localhost:{values['PORT']}"
    return values
