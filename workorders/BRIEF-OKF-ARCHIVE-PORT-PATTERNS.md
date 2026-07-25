# Implementer Brief — Archive Port Patterns

**What landed:** `canon/research/archive-port-patterns.md` — an OKF Reference concept (type:
Reference, 14 patterns AP-01…AP-14) extracted from `archive/pre-rebirth-2026-07-23/code/twclient/`
covering the algorithms and data structures needed for the upcoming greenfield phases.

**Status:** landed on `origin/main` (see hub STATUS for SHA). `canon/index.md` updated (Research section added). Cross-links
added to `settle-detection.md` [7], `login-automaton.md` [6], `world-model.md` (last bullet),
`trade-loops.md` (chains bullet).

---

## Must-Read Before These Lanes

| WO area | Patterns to read first |
|---------|----------------------|
| Cockpit / autopilot spine (Phase 2–3) | AP-10 (WorldSnapshot/Decision model), AP-11 (frame_layout tiers), AP-13 (credits discipline) |
| Teach A/R/T hotkeys + macro record/replay | AP-04 (skill record/replay/play, halt-on-divergence, start_anchor) |
| Settle / screen-readiness polish | AP-02 (send_and_confirm, stability re-check, retry_unstable_idle) |
| Menu crawl (read-only introspection) | AP-12 (deny-by-default, A+C protocol, SAFE_ALLOWLIST) |
| Trade loops / chain discovery | AP-07 (DFS chain finder), AP-09 (priority engine earn-vs-search) |
| World model write hooks | AP-06 (per-sector store, nested-port merge, write_from_state) |
| Login / game_letter UX | AP-03 (reactive automaton loop, nuisance table, stagnant_rounds) |
| Priority ranking / GOALS panel | AP-09 (recommend_actions, stay_vs_leave), AP-10 (EconCaps) |
| Auto-haggle | AP-05 (evidence-backed price, desync fallback, _resolution_evidence) |
| Candidate mining / AI teacher dry-run | AP-14 (menu_signature, propose/compare, dry_run_step) |
| Frontier exploration | AP-08 (BFS frontier, _adjacent_hop_toward fix, path_to_sector) |

---

## Hard Pins

1. **AP-01 stale-scrollback discipline is a HARD correctness gate.** Gate anchors match ONLY the
   current prompt line. Content anchors may scan full text. Multi-signal game_select checks must
   be scoped to the range between anchor and current prompt — not the whole screen. Violating this
   is the stale-scrollback misfire class that caused live failures.

2. **AP-02 `send_and_confirm` stale pre-send guard is mandatory.** Capture `rx_count` BEFORE
   `send()`. A confirm_prompt match is only accepted after `rx_count > rx_at_send`. Skipping this
   lets a repeating prompt (prior round's offer screen) immediately "confirm" a send that hasn't
   been answered yet.

3. **AP-04 `start_anchor` is mandatory for every macro.** A skill without a `start_anchor` must
   refuse to replay by default (never silently unanchored). A mismatch between current sector and
   `start_anchor` raises `ReplayDivergence` — `force=True` waives only a missing/legacy anchor,
   never a detected mismatch.

4. **AP-05 `resolved=True` requires positive evidence.** The offer prompt disappearing alone is
   NOT proof of an accepted deal. Either a credits delta moving the right direction OR the current
   line positively matching a resolution shape (plus acceptance context) is required. Returning
   `resolved=True` without one of these is a money-path defect.

5. **AP-06 nested-port merge: never write `"class": null` on a plain visit.** `write_from_state()`
   must omit the `class` sub-key entirely when `parse_state()` didn't observe one — not write
   `{"class": null}`. The nested merge preserves whatever was already stored; an explicit null
   clobbers it.

6. **AP-08 `_adjacent_hop_toward` fix is non-negotiable.** Never hand back a frontier edge's `to`
   sector as `next_sector` directly. The frontier's `frm` may be several hops from the current
   sector. Always resolve to a single valid adjacent hop via `path_to_sector(graph, current, frm)[1]`.

7. **AP-13 credits-source discipline.** Stop-loss and floor checks MUST use `session.credits_snapshot()`
   (atomic, freshness-gated), never `parse_state().get("credits")`. The latter matches price
   quotes on port screens — the exact wrong value for a cash-floor decision.

8. **Negative patterns are firm.** The items in the Negative Patterns table (ap-01 through ap-14's
   do-not-port list) must not reappear in product code: no `ai_pilot` mode, no `autonomous` flag,
   no `actor="trainer"` ledger value, no autonomous loop that fires without stop-on-unknown.

---

## ACK Required

Post `🤝 ACK [BRIEF-OKF-ARCHIVE-PORT-PATTERNS]` on your outbox before building any of the above lanes to
confirm the hard pins above are understood, especially AP-01 (stale-scrollback) and AP-06
(nested-port merge null-omit rule).
