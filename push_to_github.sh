#!/usr/bin/env bash
# One-time: pushes this folder to a new public GitHub repo named "proofpay".
# Needs the GitHub CLI (https://cli.github.com) and `gh auth login` done once.
set -e
cd "$(dirname "$0")"
[ -d .git ] || git init -b main
git add -A
git commit -m "ProofPay: AI-verified escrow on PayPal" || true
gh repo create proofpay --public --source=. --remote=origin --push \
  --description "AI-verified escrow for freelance work, powered by PayPal Orders + Payments APIs"
gh repo edit --add-topic paypal,ai,escrow,streamlit,hackathon
echo "Done: $(gh repo view --json url -q .url)"
