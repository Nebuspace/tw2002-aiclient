#!/usr/bin/env bash
# hub-live-prove-check.sh — Post the `live-prove` required Check Run via gh.
#
# ORCHESTRATOR-ONLY. Do NOT run this from a workflow (that would defeat the gate).
# This script is documentation + a runnable helper for the hub seat.
#
# The `live-prove` check is a required status check on the `main` branch ruleset.
# Only the orchestrator may mark it, and only after actually running live tests
# (or confirming an explicit docs-only n/a). No workflow may auto-green it.
#
# Prerequisites:
#   gh auth status    # must be authenticated (gh auth login, or GITHUB_TOKEN env)
#   The `gh` token needs: checks:write permission on Nebuspace/tw2002-aiclient
#
# Usage:
#   # After live tests passed on the orchestrator's laptop:
#   ./scripts/hub-live-prove-check.sh <HEAD_SHA> success "hosts: anet, rogue · N of M passed"
#
#   # For a docs/protocol-only PR where live tests were deliberately skipped:
#   ./scripts/hub-live-prove-check.sh <HEAD_SHA> n/a "docs-only: no live-login test path changed"
#
#   # After live tests failed:
#   ./scripts/hub-live-prove-check.sh <HEAD_SHA> failure "live-login failed: <brief reason>"
#
# Argument 3 is the SUMMARY text. No secrets — hosts and result counts only.

set -euo pipefail

REPO="Nebuspace/tw2002-aiclient"
CHECK_NAME="live-prove"

HEAD_SHA="${1:-}"
RESULT="${2:-}"   # "success" | "failure" | "n/a"
SUMMARY="${3:-}"

if [[ -z "$HEAD_SHA" || -z "$RESULT" || -z "$SUMMARY" ]]; then
  echo "Usage: $0 <head-sha> <success|failure|n/a> <summary-text>"
  echo ""
  echo "  success  — live tests ran and passed on orchestrator laptop"
  echo "  failure  — live tests ran and failed"
  echo "  n/a      — docs-only PR; live tests deliberately skipped (state reason in summary)"
  exit 1
fi

# Map n/a to a GitHub conclusion.
# GitHub accepts: success | failure | neutral | cancelled | skipped | timed_out | action_required
if [[ "$RESULT" == "n/a" ]]; then
  CONCLUSION="success"
  TITLE="Orchestrator live prove — n/a (docs only)"
elif [[ "$RESULT" == "success" ]]; then
  CONCLUSION="success"
  TITLE="Orchestrator laptop live prove — passed"
elif [[ "$RESULT" == "failure" ]]; then
  CONCLUSION="failure"
  TITLE="Orchestrator laptop live prove — FAILED"
else
  echo "ERROR: result must be 'success', 'failure', or 'n/a'. Got: $RESULT"
  exit 1
fi

echo "Posting live-prove Check Run to $REPO @ $HEAD_SHA"
echo "  conclusion : $CONCLUSION"
echo "  title      : $TITLE"
echo "  summary    : $SUMMARY"
echo ""

gh api "repos/${REPO}/check-runs" \
  -f "name=${CHECK_NAME}" \
  -f "head_sha=${HEAD_SHA}" \
  -f "status=completed" \
  -f "conclusion=${CONCLUSION}" \
  -f "output[title]=${TITLE}" \
  -f "output[summary]=${SUMMARY}" \
  --jq '.id'

echo "Done — Check Run posted."
echo ""
echo "Next: gh pr checks <PR-number>   # verify live-prove is green before merging"
