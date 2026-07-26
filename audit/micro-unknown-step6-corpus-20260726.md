# micro `unknown`@login step6 — redacted corpus + analysis

**WO:** `WO-MICRO-UNKNOWN-STEP6-CORPUS`  
**Seat:** `impl-aiclient-cursor` · branch `wo/MICRO-UNKNOWN-STEP6` @ tip base `d3c01ef`  
**Date:** 2026-07-26  
**Ruling:** corpus + analysis only — **no `screen_class` invent** · **no `classify.py` edit**

No passwords, handles, or full live screen dumps in this file.

---

## Matrix cell (opened)

| Host | Profile key | NEW | Class@step | Attribution |
|---|---|---|---|---|
| `twgs.microblaster.net:2002` | `proof_micro` | **FAIL** | `unknown`@step6 | remote · blank-name reject → silent reject line |

Source: `audit/live-ensure-matrix-20260726.md` (micro NEW row) · durable fail shape
`login_failed:automaton_stuck:classification='unknown':step=6`.

---

## Redacted frame shape (prior capture — Result 1)

**Source:** `audit/live-ensure-stall-diagnosis-20260726.md` Result 1 (tip then `f6432a1`; mechanism unchanged at `d3c01ef`).  
**Settle discriminator:** frames A == B == C, byte-identical; `settled_reason=timeout` after 10s idle → **stable dead-end, not mid-paint**.

**Structural transcript** (host text only; no operator identity):

```
Please enter your name (ENTER for none):
A login name is required.
Please enter your name (ENTER for none):
A login name is required.
Please enter your name (ENTER for none):
A login name is required.
```

**Automaton behavior (canon-correct so far):** `_OUTER_NAME_PROMPT_RE` matches `(ENTER for none)` → blank+CRLF (documented in `login-automaton.md`). Four blank answers. First three: reject + re-ask. **Fourth:** reject with **no re-ask** — host goes silent. Last non-blank line = `A login name is required.`

**Safety:** stall is **upstream of handle and password** — neither is sent on this path.

**Ephemeral frame JSON** (paths only, under `/tmp` bank run-dir; not in-tree): prior capture referenced as `/tmp/…/micro-frame-A.json`. Not re-fetched this tip (see Live recapture below).

---

## Step6 prompt shapes vs existing `classify` vocab

| On-screen shape | Existing class that *would* match | What actually classifies |
|---|---|---|
| `Please enter your name (ENTER for none):` | `login_name` (gate regex: `enter\s+your\s+name` …) | Matches while re-ask is last line |
| `A login name is required.` (alone, after silent host) | **none** — no gate/content anchor for this reject line | `unknown` |
| TWGS / game-select banners | `game_select` / `menu` (a-net path — different WO) | N/A on this micro frame |

**Conclusion for classify:** this is **not** a missing `screen_class` invent. The reject-only end state correctly falls through to `unknown`. Inventing a class for `"A login name is required."` would paper over a **login-automaton policy gap** (host advertises blank-ok, then refuses blank) — product follow-on already banked as `WO-MICRO-LOGIN-BLANK-REJECT` (`session/login.py` fallback on *explicit* rejection; still no classify invent).

---

## Escalation note (same family, different roots)

Per WO escalation line: micro `unknown`@6 · a-net `menu`@5 · xeno `unknown`@5 share a **login-flow coverage** theme, but micro’s root here is **automaton blank-reject**, not the a-net game-select mislabel (closed by `WO-ANET-BANNER-LAYOUT` / follow-on diagnosis). Do not collapse them into one classify widen.

---

## Live recapture this tip

**Not run from this seat.** Cursor Shell no-exit blocks `tw ensure` / `tw screen`. Bank path known (coord only): `TW_CONFIG_DIR=/tmp/tw2002-live-ensure-matrix-20260726T0801Z` key `proof_micro` + isolated `TW_RUN_DIR`. Prior Result 1 capture remains Accept-sufficient under this WO (redacted artifact from opened diagnosis). Hub/Max may optional N-of-M re-prove; not required to invent a class.

---

## Accept claim

- Redacted corpus + analysis committed under `audit/micro-unknown-step6-corpus-20260726.md`
- Cites matrix cell + tip base `d3c01ef`
- **No new `screen_class` names**
- Follow-on product WO already exists (`WO-MICRO-LOGIN-BLANK-REJECT`); hub decides whether to dispatch — **not** a classify invent WO
