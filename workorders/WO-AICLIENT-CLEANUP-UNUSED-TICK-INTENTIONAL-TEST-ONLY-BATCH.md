# WO-AICLIENT-CLEANUP-UNUSED-TICK-INTENTIONAL-TEST-ONLY-BATCH

**Priority:** LOW  
**Claimed-by:** impl-aiclient-h1  
**Result:** DONE (disposition ledger marks — no product code change)

## Goal

Drain the unused-code-tick `tip_check=12` batch from
`unused-code-20260815T1149Z.md` so Half-2 stops re-surfacing intentional
test-only / parked surfaces. Mark `closed_kept` / `false_positive` in
`.samantha/audit/unused-code-disposition.json` via
`unused-code-tick.py --mark`.

## Tip-check table (same action)

| Subject | Fate | Evidence |
|---|---|---|
| `candidate_mining:CandidateMining` | `closed_kept` | Intentional `mine_ledger` alias pin (`test_miner`) |
| `cockpit.panic:PANIC_TOKEN` | `closed_kept` | Calm-path `P` retired; spelling/absence pins retained |
| `cockpit.panic:PANIC_INTENT` | `closed_kept` | Halt contract + future rebind; app still has panic action |
| `cockpit.panic:PANIC_TONE` | `closed_kept` | chrome-not-danger pin |
| `cockpit.panic:resolve_panic_key` | `closed_kept` | Bare resolver; `handle_key` no longer calls it |
| `cockpit.reflex_controls:REFLEX_TOKEN` | `closed_kept` | Retired-from-band spelling pin |
| `cockpit.rules_library:RULES_TOKEN` | `closed_kept` | Retired-from-band spelling pin |
| `game_data:save_world_game_data` | `closed_kept` | Wholesale API; live capture uses `persist_*_row` (docstring) |
| `menu.crawler:crawl_menus` | `closed_kept` | Parked BFS library pending Max-gated driver rebuild — not retire |
| `rule_engine:document_from_dicts` | `closed_kept` | In-memory helper; disk via `rules/store`+`writer` |
| `rule_engine:document_to_dicts` | `closed_kept` | Inverse of `document_from_dicts` |
| `session.trade_chain:DEFAULT_PASS_COUNT` | `false_positive` | Product CLI imports as `_CHAIN_PASS_COUNT` (`session/cli.py`) — ImportFrom-alias blind spot |

Already dispositioned outside this batch (report still lists; ledger skips):
`HOLD_TOKEN` / `OFFER_TOKEN` / `GATHER_HINT` → `false_positive`;
`load_coach_port_economics_params` → `hold`.

## Proof

```bash
python3 ../.samantha/scripts/unused-code-tick.py --propose 20
# → findings=16 actionable=0 proposed=0
```

- live-prove: **n/a** (hub disposition ledger + WO record; no send/session path)

## Accept

- [x] All 12 prior `tip_check` subjects marked `closed_kept` or `false_positive`
- [x] `--propose 20` → `proposed=0` for this batch
- [x] Tip-check evidence recorded in this WO
