import html
import os
from datetime import UTC, datetime, timedelta

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from .config import HOME, settings

os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.messages.readonly",
]
TOKEN = HOME / "google_token.json"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
CHAT = "https://chat.googleapis.com/v1"

_pending_flows = {}


def auth_url():
    s = settings()
    redirect = f"{s['WEB_URL']}/api/auth/google/callback"
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": s["GOOGLE_CLIENT_ID"],
                "client_secret": s["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect],
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect,
    )
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    _pending_flows[state] = flow
    return url


def finish_auth(state, code):
    flow = _pending_flows.pop(state)
    flow.fetch_token(code=code)
    TOKEN.write_text(flow.credentials.to_json())


def session():
    if not TOKEN.exists():
        return None
    return AuthorizedSession(Credentials.from_authorized_user_file(str(TOKEN), SCOPES))


def _get(s, url, **params):
    r = s.get(url, params=params)
    r.raise_for_status()
    return r.json()


def me(s):
    return _get(s, "https://openidconnect.googleapis.com/v1/userinfo")


def _iso_ms(ms):
    return datetime.fromtimestamp(int(ms) / 1000, UTC).isoformat()


def _sender(m):
    return next((h["value"] for h in m["payload"]["headers"] if h["name"] == "From"), "?")


def gmail(s, my_email, days):
    q = f"in:inbox newer_than:{days}d -category:promotions -category:social"
    threads = _get(s, f"{GMAIL}/threads", q=q, maxResults=100).get("threads", [])
    for t in threads:
        msgs = _get(s, f"{GMAIL}/threads/{t['id']}", format="metadata", metadataHeaders=["From", "To", "Subject"])["messages"]
        first = {h["name"]: h["value"] for h in msgs[0]["payload"]["headers"]}
        last = {h["name"]: h["value"] for h in msgs[-1]["payload"]["headers"]}
        yield {
            "id": f"gmail:{t['id']}",
            "source": "gmail",
            "title": first.get("Subject") or "(no subject)",
            "body": "\n---\n".join(f"{_sender(m)}: {html.unescape(m.get('snippet', ''))}" for m in msgs[-3:]),
            "url": f"https://mail.google.com/mail/u/0/#all/{t['id']}",
            "people": f"{first.get('From', '')} {last.get('From', '')} {last.get('To', '')}",
            "updated_at": _iso_ms(msgs[-1]["internalDate"]),
            "due_at": None,
            "last_from_me": my_email.lower() in last.get("From", "").lower(),
        }


def chat(s, my_user_id, days):
    since = datetime.now(UTC) - timedelta(days=days)
    me_name = f"users/{my_user_id}"
    token = None
    while True:
        page = _get(s, f"{CHAT}/spaces", pageSize=1000, **({"pageToken": token} if token else {}))
        for sp in page.get("spaces", []):
            active = sp.get("lastActiveTime")
            if not active or datetime.fromisoformat(active) < since:
                continue
            msgs = _get(
                s,
                f"{CHAT}/{sp['name']}/messages",
                filter=f'createTime > "{since.strftime("%Y-%m-%dT%H:%M:%SZ")}"',
                orderBy="createTime desc",
                pageSize=15,
            ).get("messages", [])
            if not msgs:
                continue
            space_id = sp["name"].split("/")[1]
            is_dm = sp.get("spaceType") == "DIRECT_MESSAGE"
            yield {
                "id": f"chat:{sp['name']}",
                "source": "chat",
                "title": sp.get("displayName") or "Direct message",
                "body": "\n".join(
                    f"{'me' if m['sender']['name'] == me_name else 'them'}: {m.get('text', '')}" for m in reversed(msgs)
                ),
                "url": f"https://chat.google.com/{'dm' if is_dm else 'room'}/{space_id}",
                "people": sp.get("displayName", ""),
                "updated_at": msgs[0]["createTime"],
                "due_at": None,
                "last_from_me": msgs[0]["sender"]["name"] == me_name,
            }
        token = page.get("nextPageToken")
        if not token:
            return
