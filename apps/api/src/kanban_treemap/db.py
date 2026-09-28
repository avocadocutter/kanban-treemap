import sqlite3

import yaml

from .config import HOME, PROJECTS_FILE

FIELDS = ["id", "source", "title", "body", "url", "people", "updated_at", "due_at", "last_from_me"]


def load_projects():
    return yaml.safe_load(PROJECTS_FILE.read_text())["projects"]


def conn():
    c = sqlite3.connect(HOME / "items.db")
    c.row_factory = sqlite3.Row
    c.execute(
        """create table if not exists items(
        id text primary key, source text, title text, body text, url text, people text,
        updated_at text, due_at text, last_from_me int,
        project text, needs_reply int default 0, summary text, classified_for text)"""
    )
    c.execute("create table if not exists state(key text primary key, value text)")
    return c


def get_state(c, key):
    row = c.execute("select value from state where key=?", [key]).fetchone()
    return row["value"] if row else None


def set_state(c, key, value):
    c.execute("insert into state(key, value) values(?, ?) on conflict(key) do update set value=excluded.value", [key, value])


def upsert(c, items):
    c.executemany(
        f"""insert into items({",".join(FIELDS)}) values({",".join("?" * len(FIELDS))})
        on conflict(id) do update set {",".join(f"{f}=excluded.{f}" for f in FIELDS[1:])}""",
        [[i[f] for f in FIELDS] for i in items],
    )


def delete_older(c, source, before_iso):
    c.execute("delete from items where source=? and updated_at < ?", [source, before_iso])


def replace_source(c, source, items):
    upsert(c, items)
    ids = [i["id"] for i in items]
    c.execute(
        f"delete from items where source=? and id not in ({','.join('?' * len(ids))})",
        [source, *ids],
    )


def all_items(c):
    return [dict(r) for r in c.execute("select * from items")]
