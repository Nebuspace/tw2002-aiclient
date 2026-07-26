# WO-CLASSIFY-PASSWORD-LENGTH-UNKNOWN

**Status:** OPEN · BANKED · offline · not urgent (post C-02 residual)  
**Posted:** 2026-07-26 · CC framing 21:33:55Z + Cursor ACK 21:35:00Z  
**Depends:** `WO-CLASSIFY-LOGIN-PASSWORD-NARROW` on main (`7130871`)

## Goal

After C-02, screens like `How many characters in your password?` no longer classify as `login_password` (credential-leak closed). They currently land on **`money_prompt`** and halt via `NEVER_AUTO_ACTION_CLASSES` — **safe by accident**, not by vocabulary honesty.

Re-aim such prompts to an honest class (likely `unknown`, which also fail-closes) so safety does not depend on `money_prompt`'s breadth surviving a future tighten.

## Scope

- `session/classify.py` gate/content anchors + pins
- Audit note linking C-02 ↔ C-06 load-bearing pair
- **Out:** Explore HOLD · live · invent money/bank flows · weaken NEVER_AUTO

## Accept

1. Documented residual: post-C-02 `money_prompt` landing is incidental.
2. Chosen honest class for password-length / help-about-password chrome (prefer `unknown` unless evidence says otherwise).
3. Pin: that chrome is not `login_password` and not relying solely on money_prompt breadth for halt (or pin that `unknown`/chosen class still refuse-sends).
4. pytest green.

## Refs

CC 2026-07-26T21:33:55Z · Cursor ACK 21:35:00Z · C-02 / C-06
