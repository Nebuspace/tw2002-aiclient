# WO-WIRE-STRATEGY-CARD-TRADEOFFS-OKF-REFS — surface tradeoffs/okf_refs (AI-TRANCHE-7)

**Status:** DONE
**Branch:** `wo/AI-TRANCHE-7-STRATEGY-CARD`

## Tip finding

`coach_kb.py` requires (and schema-validates) `StrategyCard.tradeoffs` /
`StrategyCard.okf_refs` on every load, but `coach_engine.py`
`compose_decisions_coach` — the only product consumer, feeding
`cockpit/decisions.py`'s DECISIONS pane — only reads `.title` / `.what` /
`.steps[0]`. Zero product path ever renders `tradeoffs` or `okf_refs`; both
validated fields were orphaned.

## Goal

Wire a minimal, tip-honest render path so `tradeoffs` and `okf_refs` reach an
operator, without widening the width-budgeted DECISIONS gutter.

## Scope

- New `tw2002_aiclient/coach_cli.py` — filesystem-only `tw coach show [id]`
  verb (mirrors `catalog_cli.py` / `mine_cli.py` / `players_cli.py`
  conventions; never opens the session socket).
  - No `id` → brief listing of all shipped cards (id / trigger / priority /
    title), same shape whether or not the DECISIONS renderer is running.
  - Given `id` → full authored card as text, including bulleted
    `tradeoffs` and `okf_refs`.
  - `--json` → structured output (full card fields, incl. `tradeoffs` /
    `okf_refs`) for both the list and single-card shapes.
  - `--strategies PATH` override for testability, matching the existing
    `--inventory` / `--ledger` override convention.
- Wire `add_coach_parsers(sub)` into `tw2002_aiclient/session/cli.py`
  `build_parser()`, alongside the other line-cap-motivated sibling CLI
  modules.
- `tests/test_cli_coach.py` — new coverage: parser registration, text +
  `--json` shapes carry `tradeoffs`/`okf_refs`, unverified-card badge,
  unknown-id fail-closed (text + json), omitted-id listing omits the wide
  fields, `--strategies` override, malformed-file fail-closed, every shipped
  card renders without raising.
- `tests/test_cli_log.py` `_SHIPPED_VERBS` allowlist — add `coach`.

## Out of scope

- No change to `coach_engine.py` / `cockpit/decisions.py` — the DECISIONS
  pane's tight per-tick width budget is untouched; this is a standalone
  filesystem read, not a wider panel dump.
- No new CLI verb group beyond `coach show` (no separate `coach list` —
  `show` with an omitted id already covers discovery).

## Accept

1. `tw coach show <id>` renders that card's full authored content, including
   `tradeoffs` and `okf_refs`, in both text and `--json` shapes.
2. `tw coach show` (no id) lists all shipped cards briefly — no
   `tradeoffs`/`okf_refs` dump in the default listing.
3. Unknown id fails closed (exit 1) in both text and `--json`.
4. `tests/test_cli_coach.py` + `tests/test_coach_engine.py` +
   `tests/test_cli_log.py` green.

## Proof

- `.venv/bin/python -m pytest tests/test_cli_coach.py tests/test_coach_engine.py
  tests/test_cli_log.py -q` — green.
- Manual smoke: `tw coach show pair_trade_loop` / `--json` / bare
  `tw coach show` — tradeoffs/okf_refs present; DECISIONS pane untouched
  (no code change in `coach_engine.py` / `cockpit/decisions.py`).
