# The classify safety chain is load-bearing — read before narrowing anything

**Seat:** `impl-claudecode-aiclient` · **Written against:** `origin/main` `adb031d`
**Companion to:** `audit/session-classify-audit-coverage-20260726.md` (C-01, C-02, C-06)

Four work orders landed on 2026-07-26. They were **scoped as independent** and are **not**. This note exists so a future simplification cannot silently reopen a credential-leak shape.

---

## The chain

| # | WO | What it established |
|---|---|---|
| 1 | `WO-NEVER-AUTO-ACTION-CONSUMER-AUDIT` (C-06) | Every classification→send path refuses `NEVER_AUTO_ACTION_CLASSES`, pinned by 12 tests. The set has exactly one member: `money_prompt`. |
| 2 | `WO-CLASSIFY-LOGIN-PASSWORD-NARROW` (C-02) | Closed a **credential-leak** shape. Before it, `"How many characters in your password?"` classified as `login_password` — **the class that makes the automaton send the stored credential.** |
| 3 | `WO-CLASSIFY-API-PARITY-PLAIN-TIMEOUT` (C-01) | `classify()` is stale-blind on *every* gate anchor (no prompt line). Contract stated; AST guard blocks import, alias, submodule-alias and reflective `getattr` routes to it. |
| 4 | `WO-CLASSIFY-PASSWORD-LENGTH-UNKNOWN` | Re-aims that chrome off its incidental `money_prompt` landing. |

## Why they lean on each other

**C-02's fix did not choose where the screen landed.** Narrowing `login_password` moved `"How many characters in your password?"` onto `money_prompt` — a class that is also wrong for it, but which **halts**. The halt came entirely from `money_prompt` being the sole member of the set C-06 had pinned an hour earlier.

**So for the window between those WOs, the protection against sending a real password to a prompt merely *asking about* passwords was one regex's breadth plus one frozenset's membership.** Neither was chosen for that purpose.

## ⚠️ Do not narrow these without replacing the halt

1. **Do not remove or narrow `money_prompt` from `NEVER_AUTO_ACTION_CLASSES`.** It is not only about credits and holds. Until WO #4 is on `main`, it is what stops a password-length prompt from being actioned.
2. **Do not widen `login_password`'s gate back toward a bare `password` substring.** That anchor decides whether the automaton *sends a stored credential*. C-02's narrowing is a security control, not a tidiness fix — the audit's own MED rating undersells it.
3. **Do not route the live path through bare `classify()`.** It has no prompt line and is stale-blind on every gate anchor; `tests/test_classify_api_parity.py` enforces this and will fail loudly.

## Two different halts, both real — and the second is stronger than it looks

WO #4 re-aims the chrome to `unknown`. The halt mechanism changes with it, and the two are worth telling apart:

- **`money_prompt` halts by explicit refusal** at every consumer boundary — a denylist, asserted by twelve tests.
- **`unknown` halts because it is canon's escalate trigger.** Per `engine/screen-understanding.md` ("The Unknown Is First-Class"), an unrecognised screen is handed to the human by default.

**The second is not safety-by-omission**, which is what it looks like from outside. `tests/test_never_auto_action.py` states the load-bearing property directly: *every* consumer is **a positive match on a named class, or a denylist** — and **not one is of the form "act unless the class is unknown."** That shape is what makes adding a label unable to enable an action anywhere, and it is pinned, including a test guarding specifically against a future rewrite to `cls is not unknown` sneaking a money screen through as a ready session.

So both halts are pinned; they are pinned by different mechanisms. **`money_prompt` is a narrowing of what may be acted on. `unknown` is the default that acting must be positively justified against.**

`WO-UNKNOWN-CLASSIFY-SEND-REFUSE-PIN` later added `test_no_consumer_acts_on_unknown` — an **explicit assertion of the canonical property**, not the closing of a gap. It was requested on a mistaken premise (that `unknown` was unguarded) and kept on a correct one: a property stated in canon and implied by a consumer shape is worth asserting where a test will fail if it stops being true, rather than leaving a reader to reconstruct it from a module docstring.

**The thing to protect is the SHAPE, not just the set.** A refactor that turns any consumer's positive-match into "act unless unknown" would keep every existing test green in isolation while quietly making every future label actionable. That is the failure this chain is most exposed to, and it is why the consumer inventory pin matters as much as the frozenset.

## How this was found

Not by design review. Each WO was proved individually, and the dependency only became visible when the live before/after for C-02 showed the screen landing on `money_prompt` — a class nobody had chosen for it. **Independent Accept criteria can each be satisfied while the composition rests on a coincidence none of them names.** That is the general lesson, and it is why this note exists rather than a line in a commit message.
