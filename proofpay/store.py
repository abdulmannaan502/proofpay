"""Tiny JSON-file store for projects, milestones and the agent's action log."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "projects.json"

# milestone lifecycle
DRAFT, AWAITING_APPROVAL, FUNDED, SUBMITTED, CHANGES, RELEASED, DISPUTED, REFUNDED = (
    "Draft", "Awaiting PayPal approval", "Funded (held)", "Submitted", "Changes requested",
    "Released", "Disputed", "Refunded",
)


def _load() -> dict:
    if DATA.exists():
        try:
            return json.loads(DATA.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save(db: dict) -> None:
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(db, indent=2, ensure_ascii=False))


def all_projects() -> list[dict]:
    return sorted(_load().values(), key=lambda p: p["created"], reverse=True)


def get(pid: str) -> dict | None:
    return _load().get(pid)


def put(project: dict) -> None:
    db = _load()
    db[project["id"]] = project
    _save(db)


def delete(pid: str) -> None:
    db = _load()
    db.pop(pid, None)
    _save(db)


def new_project(plan: dict, brief: str, client: str, freelancer: str, currency: str, budget: float) -> dict:
    pid = "PP-" + uuid.uuid4().hex[:6].upper()
    ms = []
    for i, m in enumerate(plan["milestones"], 1):
        ms.append({**m, "n": i, "status": DRAFT, "order_id": None, "authorization_id": None,
                   "capture_id": None, "submissions": [], "reviews": [], "dispute": None})
    project = {"id": pid, "title": plan["project_title"], "brief": brief, "client": client,
               "freelancer": freelancer, "currency": currency, "budget": budget,
               "created": time.time(), "milestones": ms, "log": []}
    log(project, "agent", "plan_milestones", f"Split brief into {len(ms)} milestones with acceptance criteria")
    put(project)
    return project


def log(project: dict, actor: str, action: str, detail: str, ref: str | None = None) -> None:
    project.setdefault("log", []).append(
        {"t": time.strftime("%H:%M:%S"), "actor": actor, "action": action, "detail": detail, "ref": ref}
    )


def find_by_order(order_id: str) -> tuple[dict, dict] | tuple[None, None]:
    for p in _load().values():
        for m in p["milestones"]:
            if m.get("order_id") == order_id:
                return p, m
    return None, None
