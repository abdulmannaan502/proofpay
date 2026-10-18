"""End-to-end escrow flow in demo mode: plan -> fund -> weak work rejected -> fixed work released."""

from proofpay import ai_agent
from proofpay.paypal_client import PayPalClient
from proofpay.samples import M2_GOOD, M2_WEAK

CFG = ai_agent.AIConfig("offline", "heuristic-v1")


def test_plan_sums_to_budget():
    plan = ai_agent.plan_milestones(CFG, ai_agent.SAMPLE_BRIEF, 300, "USD")
    assert round(sum(m["amount"] for m in plan["milestones"]), 2) == 300
    assert all(m["criteria"] for m in plan["milestones"])


def test_weak_submission_is_held_then_fixed_is_released():
    m = ai_agent.plan_milestones(CFG, ai_agent.SAMPLE_BRIEF, 300, "USD")["milestones"][1]
    weak = ai_agent.decide(m, ai_agent.review(CFG, m, M2_WEAK), round_no=1)
    assert weak["action"] == "revise" and weak["blocking"]
    good = ai_agent.decide(m, ai_agent.review(CFG, m, M2_GOOD), round_no=2)
    assert good["action"] == "release" and good["score"] == 100


def test_third_failure_escalates():
    m = ai_agent.plan_milestones(CFG, ai_agent.SAMPLE_BRIEF, 300, "USD")["milestones"][1]
    d = ai_agent.decide(m, ai_agent.review(CFG, m, M2_WEAK), round_no=3)
    assert d["action"] == "dispute"


def test_missing_verdict_never_counts_as_pass():
    m = {"criteria": [{"id": "c1", "text": "x", "must": True}]}
    assert ai_agent.decide(m, {"criteria": []})["action"] != "release"


def test_demo_paypal_authorize_capture_void():
    pp = PayPalClient()
    assert pp.demo
    o = pp.create_order(amount=160, currency="USD", reference_id="T-M2", description="t",
                        return_url="http://x", cancel_url="http://x")
    assert o["approve_url"] and o["raw"]["request"]["intent"] == "AUTHORIZE"
    a = pp.authorize_order(o["id"])
    assert a["authorization_id"] and a["expires"]
    assert pp.capture_authorization(a["authorization_id"])["status"] == "COMPLETED"
    assert pp.void_authorization(a["authorization_id"])["status"] == "VOIDED"
