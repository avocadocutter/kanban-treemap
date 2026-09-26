import os
import shutil
from functools import cache
from pathlib import Path

import yaml

HOME = Path(os.environ.get("KANBAN_TREEMAP_HOME") or Path.home() / ".kanban-treemap")
CONFIG_FILE = HOME / "config.yaml"
PROJECTS_FILE = HOME / "projects.yaml"
KEYS = ["GROQ_API_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "CLICKUP_API_TOKEN", "PORT"]

CONFIG_TEMPLATE = """\
port: 8765
groq_api_key: ""
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
    values = {k: os.environ.get(k) or file_cfg.get(k.lower()) for k in KEYS}
    missing = [k.lower() for k, v in values.items() if not v]
    if missing:
        raise RuntimeError(f"Missing config: {', '.join(missing)}. Set them in {CONFIG_FILE} (or as upper-case env vars).")
    values["PORT"] = int(values["PORT"])
    values["WEB_URL"] = os.environ.get("WEB_URL") or f"http://localhost:{values['PORT']}"
    return values
