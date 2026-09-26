import argparse
import threading
import webbrowser

import uvicorn

from .config import CONFIG_FILE, PROJECTS_FILE, init_home, settings

SETUP = """Created:
{created}

Before the first run:
  1. {config}
     groq_api_key        https://console.groq.com/keys
     clickup_api_token   ClickUp > Settings > Apps > API Token
     google_client_*     Google Cloud Console:
                           - enable Gmail API and Google Chat API
                           - OAuth client type "Web application"
                           - redirect URI http://localhost:<port>/api/auth/google/callback
                           - add yourself as a test user on the consent screen
  2. {projects}
     your projects, their importance (1-5), aliases and deadlines

Then run kanban-treemap again."""


def main():
    parser = argparse.ArgumentParser(prog="kanban-treemap", description="Treemap of what needs your attention")
    parser.add_argument("--no-browser", action="store_true", help="don't open the browser")
    args = parser.parse_args()

    created = init_home()
    if created:
        print(SETUP.format(created="\n".join(f"  {p}" for p in created), config=CONFIG_FILE, projects=PROJECTS_FILE))
        return
    try:
        port = settings()["PORT"]
    except RuntimeError as e:
        raise SystemExit(str(e))

    url = f"http://localhost:{port}"
    print(f"kanban-treemap running at {url}")
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, [url]).start()
    uvicorn.run("kanban_treemap.main:app", host="127.0.0.1", port=port, log_level="warning")
