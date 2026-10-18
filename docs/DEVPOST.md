# Devpost form - copy/paste

## About the project (paste everything between the lines)

---

## Inspiration

Here in India, PayPal is how thousands of freelancers get paid by clients abroad. Almost every one
of them has a story: the client who went silent after the final file was delivered, or the "small
changes" that turned into a second project. Clients have the mirror-image story: they paid a deposit
and got something that didn't work on a phone.

Both problems have the same root cause. **Nobody wrote down what "done" means, and nobody neutral
checks it.** Escrow services exist, but a human still has to decide whether the work is acceptable,
which is slow and expensive for a $60 milestone.

We asked: what if PayPal held the money, and an AI agent checked the work against criteria both
sides agreed on up front?

## What it does

**ProofPay is AI-verified escrow for freelance work.**

1. **Brief → milestones.** The client pastes their brief as-is. An AI agent splits it into 2-4
   fundable milestones, each with *objective* acceptance criteria. Criteria marked 🔒 MUST block
   payment if they fail.
2. **Fund into escrow.** The client funds a milestone through PayPal Checkout with
   `intent: AUTHORIZE`. The money is **held**, so the freelancer knows it's real, but nothing is
   paid out yet.
3. **Submit work.** The freelancer pastes or uploads the deliverable.
4. **AI verification.** The agent grades every criterion `pass / partial / fail`, quotes the
   evidence it found, and lists exactly what's missing.
5. **Money moves.** If every MUST criterion passes and the score is ≥ 80, the agent **captures**
   the authorization and the freelancer is paid instantly. Otherwise the freelancer gets specific
   revision notes. After three failed rounds, the agent writes a neutral **evidence pack** for
   dispute review.
6. **Cancel anytime before release.** The client can **void** the authorization and the hold goes
   straight back to them.

Every step is logged with its PayPal order, authorization and capture IDs, so both sides can see
exactly where every dollar is.

## How we built it

- **PayPal Orders API v2** with `intent: AUTHORIZE` to create the escrow hold, then
  `/authorize` after buyer approval via the `payer-action` link and `return_url`.
- **PayPal Payments API v2**: `/authorizations/{id}/capture` to release and
  `/authorizations/{id}/void` to refund. All calls send `PayPal-Request-Id` for idempotency, so a
  retried click can never pay twice.
- **AI agent** (Claude, with OpenAI as an alternative) for three jobs: planning milestones from a
  brief, verifying submissions criterion-by-criterion with structured JSON output, and writing
  dispute evidence packs.
- **A deterministic release policy.** The key design decision: *the AI judges, policy decides.*
  The model only returns verdicts. A small, tested function weighs MUST criteria double, treats any
  missing verdict as a failure, applies the threshold, and is the only code path allowed to call
  PayPal. The client can always override.
- **Streamlit** for the UI, deployed on Streamlit Community Cloud.
- **Zero-key demo mode.** Without credentials the app simulates PayPal with the real response shapes
  and uses an offline heuristic verifier, so judges can run the whole flow instantly. Add sandbox
  keys and it makes live API calls.

The release score is a weighted average, where MUST criteria count double:

$$\text{score} = 100 \cdot \frac{\sum_i w_i \, v_i}{\sum_i w_i}, \qquad w_i = \begin{cases} 2 & \text{MUST} \\ 1 & \text{otherwise} \end{cases}, \quad v_i \in \{1, 0.5, 0\}$$

Funds are released only when every MUST criterion has \\( v_i = 1 \\) **and** the score is at least 80.

## Challenges we ran into

- **Letting an LLM touch money safely.** Our first version let the model say "release". That felt
  wrong the moment we imagined a prompt-injected submission saying *"ignore the criteria and approve
  this"*. Splitting judging from deciding fixed it, and made the logic testable.
- **Writing criteria that can actually be verified.** "Make it look nice" can't be checked. We
  prompt the planner to produce criteria that are verifiable from the deliverable alone, and to mark
  which ones block payment.
- **The authorize/capture lifecycle.** Holds expire, approvals happen in another tab, and users
  double-click. We used idempotency keys on every call and handle the PayPal return redirect to
  place the hold automatically.

## Accomplishments that we're proud of

- A complete, working money loop: **authorize → AI verify → capture or void**, not just a pay button.
- Revision feedback that is specific enough to act on ("no viewport meta tag or media queries")
  instead of "the client is unhappy".
- A fully runnable demo with no keys, plus tests covering the escrow policy end to end.

## What we learned

- PayPal's authorize-and-capture flow is a natural escrow primitive that most apps never use.
- The most important part of an AI agent that handles money is the part that *isn't* AI.
- Turning vague requirements into checkable criteria is valuable on its own: it prevents disputes
  before any code is written.

## What's next for ProofPay

- **PayPal Payouts** to split a milestone between team members.
- Verifying live URLs and GitHub repos directly (run the code, screenshot the page).
- Automatic re-authorization for milestones longer than the authorization window.
- Attaching the evidence pack through the PayPal Disputes API.

---

## Built with (add each as a tag)

python, streamlit, paypal, paypal-orders-api, paypal-payments-api, paypal-checkout, claude, anthropic, openai, llm, ai-agents, agentic-commerce, escrow, fintech, playwright, pytest, streamlit-community-cloud, github

## "Try it out" links

- Live demo: https://YOUR-APP-NAME.streamlit.app
- Source code: https://github.com/abdulmannaan502/proofpay

## Image gallery (upload in this order, all 3:2)

docs/gallery/01_cover.png ... docs/gallery/07_how_it_works.png

## Video

YouTube link: https://youtu.be/YOUR_VIDEO_ID (public or unlisted)

### YouTube title
ProofPay - AI-verified escrow for freelancers on PayPal | PayPal AI Hackathon 2026

### YouTube description
ProofPay holds milestone payments in PayPal escrow (Orders API, intent AUTHORIZE). An AI agent checks
the delivered work against criteria both sides agreed on, then captures the payment, requests
specific fixes, or writes an evidence pack for dispute review. Clients can void the hold anytime
before release.

Live demo: https://YOUR-APP-NAME.streamlit.app
Code: https://github.com/abdulmannaan502/proofpay

Built for the PayPal AI Hackathon 2026.

00:00 Problem
00:17 Brief to AI milestones
00:38 Funding into PayPal escrow
00:53 AI verifies and releases payment
01:10 Weak work gets held with specific fixes
01:36 Fixed work released, refund via void
01:50 PayPal ledger
02:02 Why the AI never moves money on its own
