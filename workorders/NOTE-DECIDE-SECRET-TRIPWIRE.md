# NOTE — a structural tripwire for `login._decide`'s secret flag

**Type:** NOTE (observation, not a defect)
**Banked by:** `impl-claudecode-aiclient`, 2026-07-28, per hub ruling @ 07:41:40Z
**Status:** **NOTE ONLY — do not implement.** Banked while the merge queue is shell-blocked.

---

## Context — the rule currently HOLDS

Audited 2026-07-28 against the `CLAUDE.md` hard rule *"Every password send routes through
the redaction sink."* **It holds**, verified in both directions by AST analysis (not grep —
grep counts docstrings as code):

- `connection.send_text` / `send_bytes` take `secret: bool = False` — a **fail-open
  default**, so the guarantee rests on call sites.
- Only **2** call sites exist in the product (`session.py:510`, `:596`), both forwarding the
  flag, both funnelling through a single `_log_tx` — no second redaction path to drift.
- In `login._decide`: **2** returns carry `secret=True`, both with payload
  `state['password']`; **19** returns are `secret=False` with non-credential payloads;
  **3** return `None`.
- **Converse check — the leak direction — 0 violations.** No branch returns password-bearing
  material with `secret` anything other than `True`.
- **No unguarded default:** `_decide` ends in an explicit `return None` (re-poll), so a
  future unmatched screen cannot silently inherit a sending branch.

Coverage is already adversarial: `tests/test_login_redaction.py` carries 20 tests including
four **falsification** tests — removing the redaction choke is proven RED on both the SUCCESS
and FAILURE paths, proven green again when restored, and
`test_falsification_the_on_disk_sweep_can_actually_find_a_planted_credential` is a positive
control on the detector itself. Six further redaction suites cover attach, secrets-store,
status-prompt, ensure-error, tx-record, and `logging_util`.

## The residual observation

Every existing test covers a **known branch**. Nothing covers a branch that does not exist
yet. A newly-added password-bearing branch in `_decide` returning `secret=False` would be
caught only if whoever added it also wrote a redaction test for it — i.e. the protection
depends on the author remembering, which is the same fail-open shape as the `secret=False`
default one layer down.

This is **not** a present defect. It is the difference between *"true today"* and
*"structurally cannot become false."*

## What the guard would assert

An AST tripwire over `login._decide`:

> For every `Return` in `_decide` that is a 3-tuple, if the payload expression references
> password material (`state['password']` and any future equivalent), then the `secret`
> element must be the literal `True`.

Prove it fires before trusting it: temporarily add a branch returning
`(state['password'], False, None)` and confirm the guard goes RED — a tripwire that has never
been shown to fail is not evidence.

**House idiom precedent:** `tests/test_import_hygiene.py` already AST-walks the package, so
this is an established pattern here rather than a new mechanism.

## Known limits — state them if this is ever built

- It is a **literal-node** check. Aliasing the password through another local
  (`pw = state['password']; return pw, False, None`) evades it unless locals are resolved.
  Per this repo's own AST-guard lesson, either resolve aliases or flag indirection
  unconditionally, and pin the evasion with a bypass meta-test.
- It guards `_decide` only. A future second decision site would need its own entry, so the
  guard should fail loudly if `_decide` is renamed or disappears rather than silently
  passing over a function it can no longer find (a guard that cannot find its subject must
  ERROR, never pass).

## Refs

- `canon/doctrine/secrets-and-credentials.md`
- `CLAUDE.md` → Hard rules → secrets
- `tests/test_login_redaction.py`, `tests/test_import_hygiene.py`
- Coord: `impl-claudecode-aiclient` @ 2026-07-28T07:41Z (audit) · hub ACK @ 07:41:40Z
