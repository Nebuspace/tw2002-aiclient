# WO-LOGIN-SCROLLBACK-SEARCH-AUDIT

**Status:** DONE · PR #31 · origin `94a29f4` (was IN PROGRESS · Cursor · `wo/LOGIN-SCROLLBACK-SEARCH-AUDIT` · tip `b06fbe4`)
**Posted:** 2026-07-26 · IDLE scout by impl-aiclient-cursor after Explore HOLD
**Amended:** 2026-07-26T20:55:00Z · hub fold — CC scout additions (#4, #5); Cursor retains build lane

## Goal

Inventory every whole-grid `.search(text)` call in the login decision path (`tw2002_aiclient/session/login.py`).
For each site: document whether the whole-grid match is intentional or a stale-scrollback hazard.
If `_CLEAR_AVOIDS_RE.search(text)` can false-fire on stale scrollback, scope it to
`_option_block_above_prompt` / prompt-line only (same helper as `MODULE_ENTRY`), or pin with a
comment proving the whole-grid match is required. Add regression pins for intentional sites.

## Evidence

`impl-aiclient-cursor` IDLE-scouted 2026-07-26T20:49:00Z; identified four whole-grid sites in
`_next_action_inner` and one hybrid. `MODULE_ENTRY` already fixed at tip `84bbd65` (#23) via
`_option_block_above_prompt`. Risk enumeration:

| Site | Call | Risk | Verdict |
|---|---|---|---|
| `_SHOW_LOG_RE` | `.search(text)` | Low — "show today's log" is a one-shot gate prompt, unlikely in stale cells | **Intentional** (the question appears above the prompt line) |
| `_CLEAR_AVOIDS_RE` | `.search(prompt) OR .search(text)` | **Elevated** — "clear avoids?" was answered in a prior step; pyte does not erase stale cells; text branch could re-fire | **Primary candidate** — scope or prove |
| `_INACTIVITY_RE` | `.search(text)` | Low — inactivity warning is ephemeral and always fresh | **Intentional** — keepalive nudge; whole-screen correct |
| `_PLANET_NAME_PROMPT_RE + _BOX_RE` | `.search(text)` + `.search(prompt)` | Low — already prompt-anchored via box RE on `prompt` | **Intentional hybrid** — box RE gates the text search |

## Scope

- `tw2002_aiclient/session/login.py` — the four sites above and their inline comments
- `tests/` — one or more regression pins for intentional whole-grid sites + the `_CLEAR_AVOIDS_RE` fix
- `workorders/WO-LOGIN-SCROLLBACK-SEARCH-AUDIT.md` — this file (already committed at WO-seed)

## Constraints

- **No `screen_class` invention.** This WO touches only the decision-path logic and its tests.
- **No Explore HOLD bypass.** Do not open new live connections or run proof_* scripts.
- **No live third-party proofs.** Offline/unit pins only; hub asks if live-prove is needed later.
- **Minimal footprint.** Prefer the smallest change that closes the stale-scrollback risk.
  A comment + pin proving whole-grid is correct is acceptable if the hazard is genuinely absent.
- **`_option_block_above_prompt` is the established helper** — reuse, do not reinvent.
- Do not touch classify.py, autoloop.py, or any path outside login.py + tests/.
- No new external dependencies.

## Accept

All three criteria must be met:

1. **Inventory documented.** Each of the four whole-grid sites has an inline comment (or adjacent
   docstring) stating: intentional (why whole-grid is required) OR scoped (why it is now
   prompt/block-anchored). The comment must reference the stale-scrollback hazard by name so a future
   reviewer understands the decision.

2. **`_CLEAR_AVOIDS_RE` hazard resolved.** Either:
   (a) `.search(text)` is removed or replaced with `_option_block_above_prompt`/prompt-only scope,
       AND a unit test proves the old whole-grid path no longer fires on stale scrollback content; OR
   (b) A pinning comment with a deterministic test proves the "clear avoids?" question never appears
       in stale pyte cells (i.e., the whole-grid match is safe by construction).

3. **Regression pins exist** for the two intentional whole-grid sites (`_SHOW_LOG_RE`,
   `_INACTIVITY_RE`) — one test per site asserting the RE fires when the phrase appears in the body
   of `text` (not just the last line), verifying the intentional reach is preserved.

4. **`_INACTIVITY_RE` "harmless blank" claim falsified.** The WO-seed comment calls the blank-Enter
   response "harmless." This must be tested: a test that passes stale inactivity text with a
   *different* live prompt (simulating pyte lingering) must NOT produce a blank send. If the test
   shows it does (i.e., the RE still fires on stale text), delete "harmless" from the comment and
   apply the same bounded-retry fix as `WO-MICRO-LOGIN-BLANK-REJECT`. If the test shows it is safe
   (RE only fires when the inactivity warning is the fresh current screen content), the "harmless"
   claim is confirmed and the test is the pin.

5. **Prompt-gate durability pins for two already-safe sites.**
   - `_OUTER_NAME_REJECTED_RE` (~line 563): gated under `_OUTER_NAME_PROMPT_RE.search(prompt)`.
     Add a pin that passes the rejection text in `text` with a *non-matching* `prompt` and asserts
     NO action is taken (i.e., the outer-name rejection does not fire when the prompt gate is absent).
   - `_PLANET_NAME_PROMPT_RE` (~line 697): gated under `_PLANET_NAME_BOX_RE.search(prompt)`.
     Add a pin that passes the planet-name text in `text` with a `prompt` that does NOT match the
     box RE and asserts NO planet-naming action fires.
   Both pins must fail if the respective prompt gate is removed.

**Falsifiable definition of done:**
`pytest tests/ -x` passes; grep confirms no `.search(text)` call on `_CLEAR_AVOIDS_RE` remains
unscoped (or a comment+test documents why it is safe); four new pin tests present and green
(SHOW_LOG, INACTIVITY/harmless-claim, OUTER_NAME prompt-gate, PLANET_NAME prompt-gate).

## Out of scope

- Explore HOLD bypass or any live-server connection
- Inventing new `screen_class` values
- Modifying classify.py, autoloop.py, or any non-login path
- Live third-party proves (hub will coordinate if needed)
- `_MODULE_ENTRY_MENU_RE` — already fixed at tip `84bbd65` (#23)

## Proof

STATUS + short SHA · output of `pytest tests/ -x` (all green) · grep confirming
`.search(text)` disposition on each of the four sites · four new pin-test names cited
(SHOW_LOG · INACTIVITY-harmless · OUTER_NAME-prompt-gate · PLANET_NAME-prompt-gate).

## Refs

- `tw2002_aiclient/session/login.py:109-140` — RE definitions
- `tw2002_aiclient/session/login.py:144-189` — `_option_block_above_prompt` helper + `_is_module_entry_menu`
- `tw2002_aiclient/session/login.py:547-556` — `_next_action_inner` decision path (four sites)
- `tw2002_aiclient/session/login.py:697` — `_PLANET_NAME` hybrid
- PR #23 (`a5cfdda`) — `MODULE_ENTRY` fix via `_option_block_above_prompt`
- `tw2002_aiclient/session/login.py:563` — `_OUTER_NAME_REJECTED_RE` gated under `_OUTER_NAME_PROMPT_RE.search(prompt)`
- `tw2002_aiclient/session/login.py:697` — `_PLANET_NAME_PROMPT_RE` gated under `_PLANET_NAME_BOX_RE.search(prompt)`
- `WO-MICRO-LOGIN-BLANK-REJECT` — bounded-retry pattern for blank-send risk (reference for Accept #4)
- impl-aiclient-cursor STATUS 2026-07-26T20:49:00Z (IDLE scout report)
- impl-claudecode-aiclient scout 2026-07-26T20:53:58Z (additions #4 + #5)
- hub seed 2026-07-26T20:49:50Z · hub fold 2026-07-26T20:55:00Z
