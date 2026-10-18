"""ProofPay's AI agent.

Three jobs:
  * plan_milestones  - turn a messy brief into fundable milestones with
                       objective, checkable acceptance criteria
  * review           - grade a submission criterion-by-criterion with evidence
  * dispute_pack     - write a neutral evidence summary when parties disagree

Design rule: the model JUDGES, deterministic policy DECIDES. The LLM returns
per-criterion verdicts; `decide()` turns them into release / revise / dispute
so money never moves on free-form model text.

Providers (first one configured wins): Anthropic Claude -> OpenAI -> offline
heuristic (keeps the app fully runnable for judges with zero keys).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import requests

STOP = set(
    """a an the and or of to in on for with by is are be as at it this that from must should
    include includes including have has using use page each all any per least one two three
    clearly clear provided provide deliver delivered final section""".split()
)

PLAN_SYSTEM = """You are ProofPay's escrow planner. Convert a freelance brief into 2-4 sequential
milestones that a client can fund separately through PayPal escrow.
Rules:
- Amounts must sum exactly to the budget.
- Each milestone has 3-5 acceptance criteria that can be VERIFIED from the submitted
  deliverable alone (no taste-based criteria like "looks nice").
- Mark a criterion "must": true if failing it should block payment.
Return ONLY JSON: {"project_title": str, "milestones": [{"title": str, "amount": number,
"deliverable": str, "criteria": [{"id": "c1", "text": str, "must": bool}]}]}"""

REVIEW_SYSTEM = """You are ProofPay's impartial work verifier. Money is held in PayPal escrow and
will be released based on your verdicts, so be precise and fair to BOTH sides.
For every acceptance criterion decide pass / partial / fail and quote short evidence
from the submission (or say what is missing). Do not invent requirements that are not
in the criteria. Return ONLY JSON:
{"criteria": [{"id": str, "verdict": "pass"|"partial"|"fail", "evidence": str, "note": str}],
 "summary": str, "revision_notes": [str]}"""

DISPUTE_SYSTEM = """You are ProofPay's dispute analyst. Write a neutral, factual evidence pack in
Markdown for a PayPal dispute reviewer: the agreed criteria, what was delivered,
each review round's verdicts, and which side the evidence supports. Under 300 words."""


@dataclass
class AIConfig:
    provider: str  # anthropic | openai | offline
    model: str
    api_key: str | None = None

    @property
    def label(self) -> str:
        return {
            "anthropic": f"Claude ({self.model})",
            "openai": f"OpenAI ({self.model})",
            "offline": "Offline heuristic verifier (add an API key for LLM review)",
        }[self.provider]


def load_config(secrets: dict | None = None) -> AIConfig:
    secrets = secrets or {}
    get = lambda k: secrets.get(k) or os.getenv(k)  # noqa: E731
    if get("ANTHROPIC_API_KEY"):
        return AIConfig("anthropic", get("ANTHROPIC_MODEL") or "claude-sonnet-5-5", get("ANTHROPIC_API_KEY"))
    if get("OPENAI_API_KEY"):
        return AIConfig("openai", get("OPENAI_MODEL") or "gpt-4o-mini", get("OPENAI_API_KEY"))
    return AIConfig("offline", "heuristic-v1")


# --------------------------------------------------------------------- LLM io
def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


def _chat(cfg: AIConfig, system: str, user: str, max_tokens: int = 2000) -> str:
    if cfg.provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=cfg.api_key)
        msg = client.messages.create(
            model=cfg.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    if cfg.provider == "openai":
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {cfg.api_key}"},
            json={
                "model": cfg.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"},
            },
            timeout=90,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    raise ValueError("offline provider has no chat")


# ------------------------------------------------------------------ planning
SAMPLE_PLAN = {
    "project_title": "Sweet Crumbs Bakery - landing page with online orders",
    "milestones": [
        {
            "title": "Wireframe & copy",
            "amount": 60,
            "deliverable": "Markdown doc with page sections, headline copy and menu text",
            "criteria": [
                {"id": "c1", "text": "Lists every page section: hero, menu, about, order, contact", "must": True,
                 "keywords": [["hero"], ["menu"], ["about"], ["order"], ["contact"]]},
                {"id": "c2", "text": "Headline and call-to-action copy written for the hero", "must": True,
                 "keywords": [["headline"], ["call to action", "cta", "button"]]},
                {"id": "c3", "text": "Menu text covers at least 6 items with prices in INR", "must": False,
                 "keywords": [["₹", "inr", "rs."]]},
            ],
        },
        {
            "title": "Responsive landing page",
            "amount": 160,
            "deliverable": "Single HTML/CSS page implementing the approved wireframe",
            "criteria": [
                {"id": "c1", "text": "Mobile responsive layout using a viewport meta tag and media queries", "must": True,
                 "keywords": [["viewport"], ["@media"]]},
                {"id": "c2", "text": "Menu section shows item names with prices in INR", "must": True,
                 "keywords": [["menu"], ["₹", "inr"]]},
                {"id": "c3", "text": "Contact section with phone number, address and opening hours", "must": True,
                 "keywords": [["contact"], ["tel:", "phone", "+91"], ["address", "vijayawada"], ["hours", "open"]]},
                {"id": "c4", "text": "Images include alt text for accessibility", "must": False,
                 "keywords": [["alt="]]},
            ],
        },
        {
            "title": "Online ordering with PayPal",
            "amount": 80,
            "deliverable": "Order form wired to PayPal Checkout plus deployment link",
            "criteria": [
                {"id": "c1", "text": "Order form captures item, quantity and pickup time", "must": True,
                 "keywords": [["form"], ["quantity", "qty"], ["pickup"]]},
                {"id": "c2", "text": "PayPal JS SDK button renders and creates an order", "must": True,
                 "keywords": [["paypal.com/sdk/js", "paypal.buttons"], ["createorder"]]},
                {"id": "c3", "text": "Page is deployed at a public URL", "must": True,
                 "keywords": [["https://"]]},
            ],
        },
    ],
}

SAMPLE_BRIEF = """Hi! I run Sweet Crumbs, a small home bakery in Vijayawada. I need a simple one-page
website: a nice hero with a headline and an 'Order now' button, our menu (cakes, cookies,
brownies - with prices in rupees), a short about-us story, and a contact section with our
phone, address and opening hours. It must look good on phones because most customers come
from Instagram. Later I want people to order and pay online with PayPal for pickup.
Budget: $300."""


def _offline_plan(brief: str, budget: float) -> dict:
    if "sweet crumbs" in brief.lower():
        plan = json.loads(json.dumps(SAMPLE_PLAN))
        scale = budget / 300 if budget else 1
        for m in plan["milestones"]:
            m["amount"] = round(m["amount"] * scale, 2)
        return plan
    # generic: split the brief into sentences -> criteria, 2 milestones
    sentences = [s.strip() for s in re.split(r"[.\n]+", brief) if len(s.strip()) > 25][:8]
    half = max(1, len(sentences) // 2)
    groups = [sentences[:half], sentences[half:]] if len(sentences) > 3 else [sentences]
    ms = []
    for i, g in enumerate(groups):
        ms.append(
            {
                "title": "First draft" if i == 0 else "Final delivery",
                "amount": round(budget / len(groups), 2),
                "deliverable": "Work covering the requirements below",
                "criteria": [{"id": f"c{j+1}", "text": s, "must": j < 2} for j, s in enumerate(g)],
            }
        )
    return {"project_title": (sentences[0][:60] if sentences else "Freelance project"), "milestones": ms}


def plan_milestones(cfg: AIConfig, brief: str, budget: float, currency: str) -> dict:
    if cfg.provider == "offline":
        return _offline_plan(brief, budget)
    user = f"Budget: {budget:.2f} {currency}\n\nBrief:\n{brief}"
    plan = _extract_json(_chat(cfg, PLAN_SYSTEM, user))
    # normalise amounts so they always sum to budget
    total = sum(float(m["amount"]) for m in plan["milestones"]) or 1
    for m in plan["milestones"]:
        m["amount"] = round(float(m["amount"]) * budget / total, 2)
    drift = round(budget - sum(m["amount"] for m in plan["milestones"]), 2)
    plan["milestones"][-1]["amount"] = round(plan["milestones"][-1]["amount"] + drift, 2)
    return plan


# -------------------------------------------------------------------- review
def _keywords_from_text(text: str) -> list[list[str]]:
    words = [w for w in re.findall(r"[a-zA-Z₹@][a-zA-Z0-9₹@:\-]{3,}", text.lower()) if w not in STOP]
    seen, out = set(), []
    for w in words:
        if w not in seen:
            seen.add(w)
            out.append([w])
    return out[:5]


def _find(sub_lower: str, opts: list[str]) -> str | None:
    for o in opts:
        idx = sub_lower.find(o.lower())
        if idx >= 0:
            return o
    return None


def _snippet(sub: str, needle: str, width: int = 50) -> str:
    i = sub.lower().find(needle.lower())
    if i < 0:
        return ""
    s = sub[max(0, i - 15) : i + width].replace("\n", " ").strip()
    return f"…{s}…"


def _offline_review(milestone: dict, submission: str) -> dict:
    sub_l = submission.lower()
    results, notes = [], []
    for c in milestone["criteria"]:
        groups = c.get("keywords") or _keywords_from_text(c["text"])
        hits, misses, ev = 0, [], ""
        for g in groups:
            f = _find(sub_l, g)
            if f:
                hits += 1
                ev = ev or _snippet(submission, f)
            else:
                misses.append(" / ".join(g))
        ratio = hits / max(1, len(groups))
        verdict = "pass" if ratio == 1 else "partial" if ratio >= 0.5 else "fail"
        note = "All required elements found." if verdict == "pass" else f"Missing: {', '.join(misses)}"
        if verdict != "pass":
            notes.append(f"{c['text']} - {note}")
        results.append({"id": c["id"], "verdict": verdict, "evidence": ev or "No matching content found.", "note": note})
    passed = sum(r["verdict"] == "pass" for r in results)
    summary = f"{passed} of {len(results)} acceptance criteria fully met."
    return {"criteria": results, "summary": summary, "revision_notes": notes}


def review(cfg: AIConfig, milestone: dict, submission: str) -> dict:
    if cfg.provider == "offline":
        return _offline_review(milestone, submission)
    crit = "\n".join(f"- {c['id']} ({'MUST' if c.get('must') else 'nice-to-have'}): {c['text']}" for c in milestone["criteria"])
    user = (
        f"Milestone: {milestone['title']}\nExpected deliverable: {milestone['deliverable']}\n"
        f"Acceptance criteria:\n{crit}\n\n--- SUBMISSION START ---\n{submission[:60000]}\n--- SUBMISSION END ---"
    )
    out = _extract_json(_chat(cfg, REVIEW_SYSTEM, user, max_tokens=2500))
    ids = {c["id"] for c in milestone["criteria"]}
    out["criteria"] = [r for r in out.get("criteria", []) if r.get("id") in ids]
    for c in milestone["criteria"]:  # never let a missing verdict count as a pass
        if c["id"] not in {r["id"] for r in out["criteria"]}:
            out["criteria"].append({"id": c["id"], "verdict": "fail", "evidence": "Not assessed", "note": "No verdict returned"})
    return out


# -------------------------------------------------------------------- policy
WEIGHT = {"pass": 1.0, "partial": 0.5, "fail": 0.0}


def decide(milestone: dict, result: dict, threshold: int = 80, round_no: int = 1, max_rounds: int = 3) -> dict:
    """Deterministic escrow policy. The LLM never directly moves money."""
    by_id = {r["id"]: r for r in result["criteria"]}
    total_w = earned = 0.0
    blocking = []
    for c in milestone["criteria"]:
        w = 2.0 if c.get("must") else 1.0
        v = by_id.get(c["id"], {}).get("verdict", "fail")
        total_w += w
        earned += w * WEIGHT.get(v, 0)
        if c.get("must") and v != "pass":
            blocking.append(c["text"])
    score = round(100 * earned / total_w) if total_w else 0
    if not blocking and score >= threshold:
        action, reason = "release", "All MUST criteria passed and score meets the release threshold."
    elif round_no >= max_rounds:
        action, reason = "dispute", f"Still failing after {round_no} review rounds - escalating with an evidence pack."
    else:
        action, reason = "revise", f"{len(blocking)} blocking criteria not yet met."
    return {"score": score, "action": action, "reason": reason, "blocking": blocking}


# ------------------------------------------------------------------- dispute
def dispute_pack(cfg: AIConfig, project: dict, milestone: dict) -> str:
    rounds = milestone.get("reviews", [])
    if cfg.provider != "offline":
        user = json.dumps({"project": project.get("title"), "milestone": milestone["title"],
                           "criteria": milestone["criteria"], "reviews": rounds}, ensure_ascii=False)[:50000]
        return _chat(cfg, DISPUTE_SYSTEM, user, max_tokens=900)
    lines = [f"### Evidence pack - {milestone['title']}", "",
             f"**Escrowed amount:** {milestone['amount']:.2f} {project['currency']}  ",
             f"**Review rounds:** {len(rounds)}", "", "**Agreed acceptance criteria**"]
    lines += [f"- {'MUST' if c.get('must') else 'nice'}: {c['text']}" for c in milestone["criteria"]]
    for i, r in enumerate(rounds, 1):
        lines += ["", f"**Round {i} - score {r['decision']['score']}/100 ({r['decision']['action']})**"]
        crit = {c["id"]: c["text"] for c in milestone["criteria"]}
        lines += [f"- {v['verdict'].upper()}: {crit.get(v['id'], v['id'])} - {v['note']}" for v in r["result"]["criteria"]]
    last = rounds[-1]["decision"] if rounds else {"blocking": []}
    lines += ["", "**Assessment:** The evidence supports the client on the unmet MUST criteria: "
              + "; ".join(last["blocking"]) if last["blocking"] else "**Assessment:** Evidence supports the freelancer."]
    return "\n".join(lines)
