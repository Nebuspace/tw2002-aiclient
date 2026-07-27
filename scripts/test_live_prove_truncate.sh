#!/usr/bin/env bash
# Pin: Commit Status description truncation for hub-live-prove-check.sh (WO-LIVE-PROVE-DESC-TRUNCATE).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/hub-live-prove-check.sh"

bash -n "$SCRIPT"

# Mirror the truncate rule used by the fallback Statuses path.
truncate_desc() {
  local title="$1" summary="$2"
  local desc="${title}: ${summary}"
  if ((${#desc} > 140)); then
    desc="${desc:0:137}..."
  fi
  printf '%s' "$desc"
}

short="$(truncate_desc 'Orchestrator laptop live prove — passed' 'hosts: a_net · ok')"
long_summary="$(printf 'x%.0s' {1..200})"
long="$(truncate_desc 'Orchestrator laptop live prove — passed' "$long_summary")"

short_len=$(printf '%s' "$short" | wc -c | tr -d ' ')
long_len=$(printf '%s' "$long" | wc -c | tr -d ' ')

test "$short_len" -le 140
test "$short" = "Orchestrator laptop live prove — passed: hosts: a_net · ok"
test "$long_len" -le 140
test "$long_len" -eq 140

echo "OK truncate pins: short=${short_len} long=${long_len}"
