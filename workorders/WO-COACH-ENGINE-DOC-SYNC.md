# WO-COACH-ENGINE-DOC-SYNC

**Status:** READY  
**Depends:** `main` ≥ `ecc42f7` (#263)

## Goal

Bring `canon/engine/coaching-engine.md` back in sync with code after the
coach/status wire tranche (#258–#263). Docs currently claim producers and
unreachable cards that no longer match tip — docs win, so update the canon
paragraphs to today's truth.

## Known drift (verify on tip, then rewrite)

In the "Trigger inputs are partial…" / "Authored but unreachable…" block:

- **Now supplied (remove from "no producer" list):** `dead_end_count`,
  `has_port`, `explore_mode`, `fighters_aboard` (and related status wires),
  `loop_depleting` via intervention → decisions.
- **Still no status producer:** `genesis_count` (needs
  `catalog_provider.genesis_candidates` / formations catalog).
- **Still deliberately absent:** `prompt` (credential risk — keep the
  permanent-by-design language).
- **Still authored-unreachable:** only `planet_management` /
  `planet_production` (update the "two cards never fire" claim).
- Re-check `docked_at_port` / `port_trade` / `cim_report` wording against
  current `classify_screen` + `has_port` path — do not invent classifier
  capability; describe what tip actually does.

## Scope

- `canon/engine/coaching-engine.md` only (plus this WO file).
- Optional: one-line cross-ref in FINDINGS if that file has a matching stale
  row — only if already present and wrong.
- No product code. No strategies.json edit (card stays authored).

## Constraints

- Lead-seat direct. Public-repo safe. Explicit paths only.
- Do not re-introduce `prompt` to status. Do not mark `planet_management`
  wired without a producer.

## Accept

1. Canon prose matches tip: which trigger inputs decisions passes, which
   status keys exist, which single authored card remains unreachable.
2. No product/test changes required for green suite (docs-only).
3. Offline suite still green (no-op expected).
4. live-prove `n/a` (docs).

## Proof

```bash
# prose review against tip decisions.py + protocol.py + coach_engine.py
pytest -q -m "not live_login and not pty_ui"   # expect green; no code delta
```

## Refs

- PRs #258–#263 · `cockpit/decisions.py` · `session/protocol.py`
- Plan: Nebuspace `.samantha/plans/coach-engine-doc-sync-2026-07-30.md`
