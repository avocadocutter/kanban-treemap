from datetime import date

OTHER = {"id": "other", "name": "Unclassified", "importance": 1, "description": "Messages that match no project"}
DEADLINE_WARNING_DAYS = 7


def alias_match(item, projects):
    hay = f"{item['title']} {item['people']}".lower()
    for p in projects:
        if any(a.lower() in hay for a in p.get("aliases", [])):
            return p["id"]
    return None


def is_overdue(item, today):
    return bool(item.get("due_at")) and item["due_at"][:10] < today.isoformat()


def project_nodes(projects, items, today: date):
    by_project = {}
    for it in items:
        by_project.setdefault(it.get("project") or "other", []).append(it)

    nodes = []
    for p in [*projects, OTHER]:
        its = by_project.get(p["id"], [])
        if p is OTHER and not its:
            continue
        overdue = sum(is_overdue(i, today) for i in its)
        replies = sum(bool(i.get("needs_reply")) for i in its)
        deadline = p.get("deadline")
        deadline_close = bool(deadline) and bool(its) and (date.fromisoformat(str(deadline)) - today).days <= DEADLINE_WARNING_DAYS
        nodes.append(
            {
                "id": p["id"],
                "name": p["name"],
                "description": p.get("description", ""),
                "importance": p["importance"],
                "deadline": str(deadline) if deadline else None,
                "count": len(its),
                "overdue": overdue,
                "replies": replies,
                "status": "behind" if overdue or deadline_close else "reply" if replies else "ok",
                "value": p["importance"] * (1 + overdue + replies),
            }
        )
    return nodes


def sort_items(items, today):
    for i in items:
        i["overdue"] = is_overdue(i, today)
    newest_first = sorted(items, key=lambda i: i["updated_at"] or "", reverse=True)
    return sorted(newest_first, key=lambda i: (not i["overdue"], not i.get("needs_reply")))
