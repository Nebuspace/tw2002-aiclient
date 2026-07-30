# WO-AUTOLOOP-CYCLES — unlock N passes now that 4/4 rails exist

**Status:** DONE · origin `30c8e57` (#243) · Accept verified 2026-07-30
**Posted / seeded:** 2026-07-30T06:10Z · hub (after #242 hazard-halt → All four rails)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `1d81492` (4/4 rails; `cycles` still refused only by policy)  
**Refs:** `session/autoloop.py` follow-on note · `canon/doctrine/action-safety-guards.md` turn-budget hard cap · `#239` `scope: repeating` · `#235` reflex arm

## Goal

With stop-loss · novelty-halt · turn-budget · hazard-halt all built, unlock
**`cycles=N`** on AutoLoop as **N invocations of `replay_loop`** (per-cycle
start-anchor for free). Wire Play `V`→arm so a matched **`scope: repeating`**
rule requests a bounded multi-pass run — `one-shot` stays one pass.

## Scope

- Accept `cycles` on `autoloop_start` / runner: positive int only; refuse
  bool/float/≤0; **clamp to a hard ceiling** (name the constant; document
  in STATUS — canon: hard cap regardless of caller intent).
- Runner: N serial `replay_loop` passes of the same taught macro; stop early
  on any halt/refuse; each pass re-checks rails (floor / turn_budget /
  hazard / novelty).
- Update docstring: cycles accepted **because** 4/4 rails enforce; no
  smuggled `for` without rails.
- **Play / reflex:** when the confirmed proposal's rule has
  `scope: repeating`, launch with `cycles=<hard cap>` (or lower if an
  explicit safe arg exists). `one-shot` / missing scope → one pass (today).
  Do not invent a second player.
- Focused tests: clamp; early halt stops further passes; one-shot path
  unchanged; repeating path requests multi-pass; refuse invalid cycles.

## Constraints

- Hard ceiling is mandatory — never unbounded.
- `force` / `param` stay refused.
- `#218` frozen — smallest Play/`app.py` wire if needed.
- No §A.2 / new deps / tooling.
- Successful **live** multi-cycle arm still Max sacrificial GO — this WO
  live prove: `n/a` offline (or safe refusal half only).

## Accept

1. `autoloop_start` with valid `cycles` runs that many passes (or fewer on
   halt), each under the four rails.
2. Over-ceiling requests clamp (pin); invalid types refused.
3. Play `V`→`y` on a `repeating` rule requests multi-pass; `one-shot` stays
   single-pass.
4. Focused tests + suite green.
5. Live prove: `n/a` (offline unlock). Note #235 live arm still
   NOT-ATTEMPTED.

## Proof

```bash
pytest -q tests/test_autoloop.py tests/test_hazard_halt.py tests/test_play_reflex_arm.py  # + new cycles pins
pytest -q tests
```

STATUS names the hard ceiling constant and the repeating→cycles wiring.

## Follow-on

- Max sacrificial GO: live `V`→`y` multi-cycle diversity.
- Optional operator-visible cycle progress chrome.
