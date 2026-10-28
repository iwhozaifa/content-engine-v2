"""Build Notion property payloads and read plain values back. Keeps commands free of API shapes."""
from services.notion import prop_value

CHUNK = 1900  # Notion caps one rich_text item at 2000 characters


def _chunks(s, limit=100):
    s = "" if s is None else str(s)
    return [{"type": "text", "text": {"content": s[i:i + CHUNK]}} for i in range(0, len(s), CHUNK)][:limit]


def title(s):
    return {"title": _chunks(s, 1)}


def text(s):
    return {"rich_text": _chunks(s)}


def number(n):
    return {"number": None if n is None else n}


def select(name):
    return {"select": {"name": str(name)[:100]} if name else None}


def multi(names):
    return {"multi_select": [{"name": str(n)[:100].replace(",", " ")} for n in names or [] if n]}


def checkbox(b):
    return {"checkbox": bool(b)}


def date(start):
    return {"date": {"start": start} if start else None}


def url(u):
    return {"url": u or None}


def relation(ids):
    return {"relation": [{"id": i} for i in ids if i]}


def values(page):
    """{property name: plain value} for a page from the API."""
    return {name: prop_value(p) for name, p in page.get("properties", {}).items()}


def clean(props):
    """Drop properties whose value is None/empty so updates never blank a field by accident."""
    out = {}
    for k, v in props.items():
        inner = next(iter(v.values()))
        if inner is None or inner == [] and "multi_select" not in v and "relation" not in v:
            continue
        out[k] = v
    return out


# Block helpers for page bodies
def _rt(s):
    return {"rich_text": _chunks(s)}


def heading(s, level=2):
    return {"type": f"heading_{level}", f"heading_{level}": _rt(s)}


def para(s):
    return {"type": "paragraph", "paragraph": _rt(s)}


def bullet(s):
    return {"type": "bulleted_list_item", "bulleted_list_item": _rt(s)}


def bullets(items):
    return [bullet(i) for i in items if i]
