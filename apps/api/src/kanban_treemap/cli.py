import argparse
import threading
import webbrowser

import uvicorn

from .config import CONFIG_FILE, HOME, PROJECTS_FILE, init_home, settings

SETUP = """
kanban-treemap needs a few keys before it can run.
I created two files for you in {home}

STEP 1 - Open {config} and fill in:

  llm_provider  (nothing to do if you have ChatGPT / Codex)
    Uses your Codex subscription. Not logged in? Run: codex login

    ! PRIVACY: except Ollama, every option sends message excerpts (subjects,
      senders, message snippets) to that AI company. Using work accounts?
      Check your company's AI policy first. Your company's own AI plan
      (e.g. ChatGPT Business/Enterprise) is usually the approved option.
      Personal AI plans may use your data for training unless you opt out.
      Ollama keeps everything local.

    No Codex? Replace `llm_provider: codex` with one of these:

      Groq - free key at console.groq.com/keys
        llm_provider: api
        llm_base_url: https://api.groq.com/openai/v1
        llm_model: openai/gpt-oss-120b
        llm_api_key: "<key>"

      OpenAI - key at platform.openai.com/api-keys
        llm_provider: api
        llm_base_url: https://api.openai.com/v1
        llm_model: <model>
        llm_api_key: "<key>"

      Gemini - key at aistudio.google.com/apikey
        llm_provider: api
        llm_base_url: https://generativelanguage.googleapis.com/v1beta/openai
        llm_model: <model>
        llm_api_key: "<key>"

      OpenRouter - key at openrouter.ai/keys
        llm_provider: api
        llm_base_url: https://openrouter.ai/api/v1
        llm_model: <model>
        llm_api_key: "<key>"

      Ollama - free, local, no key
        llm_provider: api
        llm_base_url: http://localhost:11434/v1
        llm_model: <model from `ollama list`>
        llm_api_key: "ollama"

  Sources: fill in the ones you use (at least one), leave the rest empty.

  clickup_api_token  (1 min)
    In ClickUp: your avatar > Settings > Apps > API Token > Generate > paste it.

  google_client_id + google_client_secret  (about 10 min, only once)
    a. Go to https://console.cloud.google.com and create a project.
    b. APIs & Services > Library > enable "Gmail API" and "Google Chat API".
    c. Google Chat API > Configuration > fill the required fields > Save.
       (Google Chat only works with work/Workspace accounts. Skip it otherwise.)
    d. OAuth consent screen > External > add your own email as a test user.
    e. Credentials > Create credentials > OAuth client ID > Web application.
       Authorized redirect URI: http://localhost:8765/api/auth/google/callback
    f. Copy the Client ID and Client secret into config.yaml.

STEP 2 - Open {projects} and list your projects.

  Easiest way: paste this prompt into ChatGPT or Claude and copy the result:
  ----------------------------------------------------------------
  Help me write a projects.yaml file listing my current work projects.
  First ask me what my projects are, how important each one is and
  any deadlines. Then output only YAML in exactly this format:

  projects:
    - id: short-kebab-case-id
      name: Human readable name
      importance: 1-5 (5 = most important to me right now)
      description: one line on what the project is about
      deadline: YYYY-MM-DD (omit if none)
  ----------------------------------------------------------------

STEP 3 - Run the same command again. Your browser opens:
  click "Connect Google", then "Sync".

  Tip: install it once to get a short `kanban-treemap` command:
    uv tool install git+https://github.com/avocadocutter/kanban-treemap
"""


def main():
    parser = argparse.ArgumentParser(prog="kanban-treemap", description="Treemap of what needs your attention")
    parser.add_argument("--no-browser", action="store_true", help="don't open the browser")
    args = parser.parse_args()

    created = init_home()
    if created:
        print(SETUP.format(home=HOME, config=CONFIG_FILE, projects=PROJECTS_FILE))
        return
    try:
        port = settings()["PORT"]
    except RuntimeError as e:
        raise SystemExit(str(e))

    url = f"http://localhost:{port}"
    print(f"kanban-treemap running at {url}  (log: {HOME / 'kanban-treemap.log'})")
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, [url]).start()
    uvicorn.run("kanban_treemap.main:app", host="127.0.0.1", port=port, log_level="warning")
