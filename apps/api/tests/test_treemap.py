from datetime import date

from kanban_treemap.treemap import alias_match, project_nodes, sort_items

TODAY = date(2026, 9, 25)
PROJECTS = [
    {"id": "a", "name": "A", "importance": 5, "aliases": ["@acme.com"], "deadline": date(2026, 9, 30)},
    {"id": "b", "name": "B", "importance": 2},
    {"id": "c", "name": "C", "importance": 3},
]


def item(project, source="gmail", needs_reply=0, due_at=None, updated_at="2026-09-20"):
    return {"project": project, "source": source, "needs_reply": needs_reply, "due_at": due_at, "updated_at": updated_at}


def test_size_and_status():
    items = [
        item("a", source="clickup", due_at="2026-10-10"),
        item("b", needs_reply=1),
        item("b", needs_reply=1),
        item("b", source="clickup", due_at="2026-09-01"),
        item(None),
    ]
    nodes = {n["id"]: n for n in project_nodes(PROJECTS, items, TODAY)}
    assert nodes["a"]["status"] == "behind" and nodes["a"]["value"] == 5
    assert nodes["b"]["status"] == "behind" and nodes["b"]["value"] == 2 * (1 + 1 + 2)
    assert nodes["c"]["status"] == "ok" and nodes["c"]["count"] == 0
    assert nodes["other"]["count"] == 1


def test_reply_status_and_no_empty_other():
    nodes = {n["id"]: n for n in project_nodes(PROJECTS, [item("c", needs_reply=1)], TODAY)}
    assert nodes["c"]["status"] == "reply"
    assert "other" not in nodes


def test_sort_items_puts_urgent_first():
    items = [item("b", updated_at="2026-09-24"), item("b", needs_reply=1), item("b", due_at="2026-09-01", updated_at="2026-09-01")]
    ordered = sort_items(items, TODAY)
    assert ordered[0]["overdue"] and ordered[1]["needs_reply"] and ordered[2]["updated_at"] == "2026-09-24"


def test_alias_match():
    assert alias_match({"title": "Re: logo", "people": "Laura <laura@acme.com>"}, PROJECTS) == "a"
    assert alias_match({"title": "hi", "people": "x@y.com"}, PROJECTS) is None
