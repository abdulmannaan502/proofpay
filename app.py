"""ProofPay - AI-verified escrow for freelance work, powered by PayPal.

Run:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from proofpay import ai_agent, store
from proofpay.paypal_client import PayPalClient, PayPalError
from proofpay.samples import SAMPLES

st.set_page_config(page_title="ProofPay - AI-verified escrow", page_icon="🛡️", layout="wide")


# ----------------------------------------------------------------- config
def _secrets() -> dict:
    try:
        return dict(st.secrets)
    except Exception:  # no secrets.toml
        return {}


SECRETS = _secrets()
if "paypal" not in st.session_state:
    st.session_state.paypal = PayPalClient.from_env(SECRETS)
PP: PayPalClient = st.session_state.paypal
AI = ai_agent.load_config(SECRETS)
APP_URL = (SECRETS.get("APP_URL") or "http://localhost:8501").rstrip("/")
THRESHOLD = int(SECRETS.get("RELEASE_THRESHOLD", 80))

st.markdown(
    """
<style>
  .block-container {padding-top: 1.6rem; max-width: 1180px;}
  .pp-hero {background: linear-gradient(120deg,#0b1f44 0%,#123a7a 60%,#1f6feb 100%);
            color:#fff; border-radius:16px; padding:22px 26px; margin-bottom:18px;}
  .pp-hero h1 {color:#fff; margin:0; font-size:2rem; letter-spacing:-.5px;}
  .pp-hero p {color:#d6e4ff; margin:.3rem 0 0 0; font-size:1.02rem;}
  .pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.78rem;
         font-weight:600; margin-right:6px;}
  .s-Draft {background:#eef1f6; color:#44506a;}
  .s-Awaiting {background:#fff4d6; color:#7a5a00;}
  .s-Funded {background:#e3efff; color:#0b4fb3;}
  .s-Submitted {background:#efe6ff; color:#5a2db3;}
  .s-Changes {background:#ffe9d9; color:#9a4500;}
  .s-Released {background:#dcf7e6; color:#0d7a3a;}
  .s-Disputed {background:#ffe0e0; color:#a11616;}
  .s-Refunded {background:#eceff3; color:#5b6472;}
  .crit {border-left:4px solid #ccd5e3; padding:6px 12px; margin:6px 0; border-radius:4px; background:#fafbfd;}
  .crit.pass {border-color:#1aa260;} .crit.partial {border-color:#e3a008;} .crit.fail {border-color:#d93025;}
  .muted {color:#6b7588; font-size:.88rem;}
  .ref {font-family:ui-monospace,monospace; font-size:.82rem; background:#f1f4f9; padding:1px 6px; border-radius:4px;}
</style>
""",
    unsafe_allow_html=True,
)


def pill(status: str) -> str:
    return f'<span class="pill s-{status.split()[0]}">{status}</span>'


def money(v: float, cur: str) -> str:
    return f"{cur} {v:,.2f}"


# ------------------------------------------------- PayPal return handling
def handle_paypal_return() -> None:
    qp = st.query_params
    token = qp.get("token")
    if not token:
        return
    project, ms = store.find_by_order(token)
    if project and ms and ms["status"] == store.AWAITING_APPROVAL:
        try:
            auth = PP.authorize_order(token)
            ms.update(status=store.FUNDED, authorization_id=auth["authorization_id"], auth_expires=auth["expires"])
            store.log(project, "paypal", "authorize_order", f"Hold placed for milestone {ms['n']}", auth["authorization_id"])
            store.put(project)
            st.session_state.open_project = project["id"]
            st.toast(f"Milestone {ms['n']} funded - money is held in escrow", icon="🔒")
        except PayPalError as e:
            st.error(f"PayPal authorization failed: {e}")
    st.query_params.clear()


handle_paypal_return()

# ----------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### 🛡️ ProofPay")
    page = st.radio("Navigate", ["New escrow", "Projects", "How it works"],
                    index=1 if st.session_state.get("open_project") else 0, label_visibility="collapsed")
    st.divider()
    st.caption("PAYMENTS")
    st.markdown(f"{'🟡' if PP.demo else '🟢'} {PP.mode_label}")
    st.caption("AI VERIFIER")
    st.markdown(f"{'🟡' if AI.provider == 'offline' else '🟢'} {AI.label}")
    st.caption("RELEASE POLICY")
    st.markdown(f"All MUST criteria pass and score ≥ **{THRESHOLD}**")
    if PP.demo or AI.provider == "offline":
        with st.expander("Connect real keys"):
            st.markdown(
                "Add to `.streamlit/secrets.toml` (or Streamlit Cloud → Secrets):\n"
                "```toml\nPAYPAL_CLIENT_ID = \"...\"\nPAYPAL_CLIENT_SECRET = \"...\"\n"
                "ANTHROPIC_API_KEY = \"...\"\nAPP_URL = \"https://your-app.streamlit.app\"\n```"
            )

st.markdown(
    """<div class="pp-hero"><h1>ProofPay</h1>
    <p>Clients fund milestones into PayPal escrow. An AI agent checks the delivered work against
    the agreed criteria and releases payment, requests changes, or files an evidence pack.</p></div>""",
    unsafe_allow_html=True,
)

# ============================================================== NEW ESCROW
if page == "New escrow":
    st.subheader("1 · Describe the job")
    c1, c2 = st.columns([3, 2])
    with c2:
        if st.button("Load sample brief (bakery website)", use_container_width=True):
            st.session_state.brief = ai_agent.SAMPLE_BRIEF
            st.session_state.client_name = "Lakshmi - Sweet Crumbs Bakery"
            st.session_state.freelancer_name = "Abdul - freelance web developer"
            st.session_state.budget = 300.0
        client = st.text_input("Client", key="client_name", placeholder="Who is paying")
        freelancer = st.text_input("Freelancer", key="freelancer_name", placeholder="Who is doing the work")
        b1, b2 = st.columns(2)
        st.session_state.setdefault("budget", 300.0)
        budget = b1.number_input("Budget", min_value=1.0, step=10.0, key="budget")
        currency = b2.selectbox("Currency", ["USD", "EUR", "GBP", "AUD", "CAD"])
    with c1:
        brief = st.text_area("Project brief (paste the client's message as-is)", key="brief", height=262)

    if st.button("✨ Generate milestones with AI", type="primary", disabled=not brief.strip()):
        with st.spinner("Agent is turning the brief into fundable, checkable milestones…"):
            try:
                st.session_state.plan = ai_agent.plan_milestones(AI, brief, budget, currency)
            except Exception as e:  # noqa: BLE001
                st.error(f"AI planning failed: {e}")

    plan = st.session_state.get("plan")
    if plan:
        st.subheader("2 · Review the escrow plan")
        st.markdown(f"**{plan['project_title']}**")
        cols = st.columns(len(plan["milestones"]))
        for col, m in zip(cols, plan["milestones"]):
            with col.container(border=True):
                st.markdown(f"**{m['title']}**")
                st.markdown(f"### {money(m['amount'], currency)}")
                st.caption(m["deliverable"])
                for c in m["criteria"]:
                    st.markdown(f"{'🔒' if c.get('must') else '◽'} {c['text']}")
        st.caption("🔒 = MUST criterion (blocks payment if not met)")
        if st.button("Create escrow project →", type="primary"):
            p = store.new_project(plan, brief, client or "Client", freelancer or "Freelancer", currency, budget)
            st.session_state.plan = None
            st.session_state.open_project = p["id"]
            st.rerun()

# ================================================================ PROJECTS
elif page == "Projects":
    projects = store.all_projects()
    if not projects:
        st.info("No escrow projects yet. Create one from **New escrow**.")
        st.stop()
    ids = [p["id"] for p in projects]
    default = ids.index(st.session_state.open_project) if st.session_state.get("open_project") in ids else 0
    pid = st.selectbox("Project", ids, index=default, format_func=lambda i: f"{i} · {store.get(i)['title']}")
    st.session_state.open_project = pid
    project = store.get(pid)
    cur = project["currency"]
    ms_all = project["milestones"]

    held = sum(m["amount"] for m in ms_all if m["status"] in (store.FUNDED, store.SUBMITTED, store.CHANGES, store.DISPUTED))
    released = sum(m["amount"] for m in ms_all if m["status"] == store.RELEASED)
    refunded = sum(m["amount"] for m in ms_all if m["status"] == store.REFUNDED)
    k = st.columns(4)
    k[0].metric("Contract value", money(project["budget"], cur))
    k[1].metric("Held in PayPal escrow", money(held, cur))
    k[2].metric("Released to freelancer", money(released, cur))
    k[3].metric("Refunded to client", money(refunded, cur))
    st.progress(released / project["budget"] if project["budget"] else 0.0,
                text=f"{project['client']}  →  {project['freelancer']}")

    left, right = st.columns([7, 3])
    with left:
        for m in ms_all:
            n = m["n"]
            with st.container(border=True):
                h1, h2 = st.columns([5, 2])
                h1.markdown(f"#### {n}. {m['title']}")
                h2.markdown(f"<div style='text-align:right;padding-top:10px'>{pill(m['status'])}"
                            f"<b>{money(m['amount'], cur)}</b></div>", unsafe_allow_html=True)
                st.caption(m["deliverable"])
                refs = []
                if m.get("order_id"):
                    refs.append(f"Order <span class='ref'>{m['order_id']}</span>")
                if m.get("authorization_id"):
                    refs.append(f"Authorization <span class='ref'>{m['authorization_id']}</span>")
                if m.get("capture_id"):
                    refs.append(f"Capture <span class='ref'>{m['capture_id']}</span>")
                if refs:
                    st.markdown("<span class='muted'>PayPal · " + " · ".join(refs) + "</span>", unsafe_allow_html=True)

                with st.expander("Acceptance criteria", expanded=m["status"] in (store.DRAFT,)):
                    for c in m["criteria"]:
                        st.markdown(f"{'🔒' if c.get('must') else '◽'} {c['text']}")

                # ---- CLIENT: fund
                if m["status"] == store.DRAFT:
                    if st.button(f"💳 Fund {money(m['amount'], cur)} with PayPal", key=f"fund{n}", type="primary"):
                        try:
                            order = PP.create_order(
                                amount=m["amount"], currency=cur, reference_id=f"{pid}-M{n}",
                                description=f"ProofPay escrow: {m['title']}"[:127],
                                return_url=APP_URL, cancel_url=APP_URL,
                            )
                            m.update(status=store.AWAITING_APPROVAL, order_id=order["id"], approve_url=order["approve_url"])
                            store.log(project, "paypal", "create_order", f"AUTHORIZE order for milestone {n}", order["id"])
                            store.put(project)
                            st.rerun()
                        except PayPalError as e:
                            st.error(str(e))

                elif m["status"] == store.AWAITING_APPROVAL:
                    st.info("Client approves the payment on PayPal. Funds are **authorized and held**, not paid out.")
                    a, b = st.columns(2)
                    if PP.demo:
                        if a.button("✅ Approve on PayPal (sandbox buyer)", key=f"appr{n}", type="primary"):
                            st.query_params["token"] = m["order_id"]
                            st.rerun()
                    else:
                        a.link_button("Open PayPal to approve ↗", m["approve_url"], type="primary")
                        if b.button("I've approved - confirm hold", key=f"conf{n}"):
                            st.query_params["token"] = m["order_id"]
                            st.rerun()

                # ---- FREELANCER: submit
                elif m["status"] in (store.FUNDED, store.CHANGES):
                    if m["status"] == store.CHANGES and m["reviews"]:
                        st.warning("Revision requested: " + " · ".join(m["reviews"][-1]["result"].get("revision_notes", [])[:3]))
                    samples = SAMPLES.get(n, {}) if "Sweet Crumbs" in project["title"] else {}
                    if samples:
                        sc = st.columns(len(samples))
                        for col, (label, text) in zip(sc, samples.items()):
                            if col.button(f"Load sample: {label}", key=f"s{n}{label}"):
                                st.session_state[f"sub{n}"] = text
                    up = st.file_uploader("Upload deliverable (.html, .md, .txt, .py, .css, .js)", key=f"up{n}",
                                          type=["html", "md", "txt", "py", "css", "js", "json"])
                    if up is not None:
                        st.session_state[f"sub{n}"] = up.read().decode("utf-8", "ignore")
                    sub = st.text_area("…or paste the deliverable / links", key=f"sub{n}", height=180)
                    if st.button("📤 Submit work for AI verification", key=f"go{n}", type="primary", disabled=not sub.strip()):
                        m["submissions"].append(sub)
                        m["status"] = store.SUBMITTED
                        store.log(project, "freelancer", "submit", f"Round {len(m['submissions'])} for milestone {n}")
                        with st.spinner("AI verifier is checking each criterion…"):
                            try:
                                result = ai_agent.review(AI, m, sub)
                            except Exception as e:  # noqa: BLE001
                                st.error(f"AI review failed: {e}")
                                store.put(project)
                                st.stop()
                        decision = ai_agent.decide(m, result, THRESHOLD, round_no=len(m["submissions"]))
                        m["reviews"].append({"result": result, "decision": decision})
                        store.log(project, "agent", "review", f"Score {decision['score']}/100 → {decision['action']}")
                        # ---- agent acts on the policy decision
                        try:
                            if decision["action"] == "release":
                                cap = PP.capture_authorization(m["authorization_id"], f"{m['title']} verified by ProofPay")
                                m.update(status=store.RELEASED, capture_id=cap["capture_id"])
                                store.log(project, "agent", "capture_authorization", f"Released {money(m['amount'], cur)}", cap["capture_id"])
                            elif decision["action"] == "revise":
                                m["status"] = store.CHANGES
                            else:
                                m["status"] = store.DISPUTED
                                m["dispute"] = ai_agent.dispute_pack(AI, project, m)
                                store.log(project, "agent", "dispute_pack", f"Escalated milestone {n} with evidence")
                        except PayPalError as e:
                            st.error(str(e))
                        store.put(project)
                        st.rerun()
                    if st.button("Cancel milestone & refund client", key=f"void{n}"):
                        PP.void_authorization(m["authorization_id"])
                        m["status"] = store.REFUNDED
                        store.log(project, "client", "void_authorization", f"Hold released for milestone {n}", m["authorization_id"])
                        store.put(project)
                        st.rerun()

                # ---- latest review
                if m["reviews"]:
                    r = m["reviews"][-1]
                    d = r["decision"]
                    icon = {"release": "✅", "revise": "✏️", "dispute": "⚖️"}[d["action"]]
                    with st.expander(f"{icon} AI review · round {len(m['reviews'])} · score {d['score']}/100 · {d['action'].upper()}",
                                     expanded=True):
                        st.markdown(f"**{r['result'].get('summary', '')}** <span class='muted'>{d['reason']}</span>", unsafe_allow_html=True)
                        crit = {c["id"]: c for c in m["criteria"]}
                        for v in r["result"]["criteria"]:
                            c = crit.get(v["id"], {"text": v["id"]})
                            st.markdown(
                                f"<div class='crit {v['verdict']}'><b>{v['verdict'].upper()}</b> · {c['text']}"
                                f"{' 🔒' if c.get('must') else ''}<br><span class='muted'>{v['note']} "
                                f"{('· evidence: <code>' + v['evidence'][:90].replace('<', '&lt;') + '</code>') if v['verdict'] != 'fail' else ''}"
                                f"</span></div>", unsafe_allow_html=True)

                # ---- human override on disputes
                if m["status"] == store.DISPUTED:
                    st.error("Escalated: the AI and policy could not release this milestone.")
                    if m.get("dispute"):
                        with st.expander("⚖️ Evidence pack for PayPal dispute review", expanded=True):
                            st.markdown(m["dispute"])
                    a, b = st.columns(2)
                    if a.button("Client overrides: release anyway", key=f"ovr{n}"):
                        cap = PP.capture_authorization(m["authorization_id"], "Released by client override")
                        m.update(status=store.RELEASED, capture_id=cap["capture_id"])
                        store.log(project, "client", "capture_authorization", "Manual override release", cap["capture_id"])
                        store.put(project)
                        st.rerun()
                    if b.button("Refund client (void hold)", key=f"ref{n}"):
                        PP.void_authorization(m["authorization_id"])
                        m["status"] = store.REFUNDED
                        store.log(project, "client", "void_authorization", f"Refunded milestone {n}", m["authorization_id"])
                        store.put(project)
                        st.rerun()

    with right:
        st.markdown("##### 🤖 Agent & PayPal activity")
        icons = {"agent": "🤖", "paypal": "💳", "client": "🧑‍💼", "freelancer": "🧑‍💻"}
        for e in reversed(project.get("log", [])[-14:]):
            ref = f"<br><span class='ref'>{e['ref']}</span>" if e.get("ref") else ""
            st.markdown(f"<div class='muted' style='margin-bottom:8px'>{icons.get(e['actor'],'•')} <b>{e['action']}</b> · {e['t']}"
                        f"<br>{e['detail']}{ref}</div>", unsafe_allow_html=True)
        st.divider()
        if st.button("Delete project", type="secondary"):
            store.delete(pid)
            st.session_state.open_project = None
            st.rerun()

# ============================================================ HOW IT WORKS
else:
    st.subheader("How ProofPay works")
    st.markdown(
        f"""
| Step | Who | What happens | PayPal API |
|---|---|---|---|
| 1 | AI agent | Turns the brief into milestones with objective acceptance criteria | - |
| 2 | Client | Funds a milestone; money is **authorized and held** | `POST /v2/checkout/orders` (intent `AUTHORIZE`) → `/authorize` |
| 3 | Freelancer | Submits the deliverable | - |
| 4 | AI agent | Grades every criterion with evidence | - |
| 5 | Policy | All MUST criteria pass and score ≥ {THRESHOLD} → release | `POST /v2/payments/authorizations/{{id}}/capture` |
| 6 | Policy | Otherwise request changes; after 3 failed rounds → evidence pack | - |
| 7 | Client | Cancel or refund at any point before release | `POST /v2/payments/authorizations/{{id}}/void` |

**Why the AI never moves money on its own words:** the model returns per-criterion verdicts as JSON;
a deterministic policy (`decide()`) converts them into release / revise / dispute, and only that
policy calls PayPal. Clients can always override.
"""
    )
