#!/usr/bin/env bash
#
# Sends a real GitHub PR's diff to the whyer backend for AI review + Telegram
# approval. Requires the GitHub CLI (gh, already authenticated) and jq.
#
# Usage:
#   ./scripts/review-pr.sh <owner/repo> <pr_number>
#
# The backend URL defaults to the Railway production deployment; override
# with WHYER_URL for local testing, e.g.:
#   WHYER_URL=http://localhost:3115 ./scripts/review-pr.sh owner/repo 42

set -euo pipefail

REPO="${1:-}"
PR_NUMBER="${2:-}"
WHYER_URL="${WHYER_URL:-https://whyer-app-production.up.railway.app}"

if [[ -z "$REPO" || -z "$PR_NUMBER" ]]; then
  echo "Usage: $0 <owner/repo> <pr_number>" >&2
  exit 1
fi

echo "Fetching PR #$PR_NUMBER from $REPO..." >&2

PR_TITLE="$(gh pr view "$PR_NUMBER" --repo "$REPO" --json title -q .title)"
DIFF="$(gh pr diff "$PR_NUMBER" --repo "$REPO")"

if [[ -z "$DIFF" ]]; then
  echo "Error: empty diff for PR #$PR_NUMBER -- nothing to review." >&2
  exit 1
fi

PAYLOAD="$(jq -n \
  --arg repo_name "$REPO" \
  --argjson pr_number "$PR_NUMBER" \
  --arg pr_title "$PR_TITLE" \
  --arg diff "$DIFF" \
  '{repo_name: $repo_name, pr_number: $pr_number, pr_title: $pr_title, diff: $diff}')"

RESPONSE="$(curl -sf -X POST "$WHYER_URL/reviews" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")"

echo "$RESPONSE"
echo "Review sent to Telegram for approval." >&2
