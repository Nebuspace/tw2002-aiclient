# Live ensure matrix — state on tip `a5cfdda` (redacted)

**Seat:** `impl-claudecode-aiclient` · **Tip under test:** `origin/main` `a5cfdda`
**Supersedes:** `live-ensure-matrix-reprove-20260726.md` (written against `7e43af6`, before micro and a-net landed)
**Isolated config:** bank dir outside the tree, `chmod 700` — never committed, never named with values here
**Isolated run-dir:** required whenever `TW_CONFIG_DIR` is set (`ensure` fails closed without `--run-dir` / `TW_RUN_DIR`)

No credentials, handles, or screen dumps in this file. Public game hostnames only.

---

## What changed since the `7e43af6` wave

Three product fixes landed, each proven live rather than by fixture:

| Landed | Effect on the matrix |
|---|---|
| `WO-MICRO-LOGIN-BLANK-REJECT` | micro's outer gate no longer wedges on a refused blank name — micro NEW went from `unknown`@6 to `main_command` |
| `WO-ANET-STEP5-LIVE-BYTES` | a-net's live door classifies — `menu`@5 became `game_select`@12 |
| `WO-ANET-GAME-SELECT-LETTER-STEP12` | the false `T` at a post-door menu is gone — a-net letter **A** reaches `main_command` |

---

## Cell state — confirming wave `confirm-195540Z`, this lineage

Four cells were run. All four reached `main_command`.

| Cell | Profile | Letter | Classification | Steps |
|---|---|---|---|---|
| rogue NEW | `proof_rogue_new` | A | `main_command` | 9 |
| rogue RETURNING | `proof_rogue` | A | `main_command` | 9 |
| micro NEW | `proof_micro` | B | `main_command` | 9 |
| a-net NEW | `proof_anet` | A | `main_command` | 10 |

**"4/4" means these four cells — not four hosts.** xeno was not among them; it did not run and correctly halts (below).

### Not run, and honestly unknown

| Cell | Status |
|---|---|
| micro RETURNING | **Never executed.** Newly possible — a credential exists where none did before this date. |
| a-net RETURNING | **Never executed.** |
| xeno / `twgs.exiled.org:2002` | **N-A — honest halt.** Untaught square-bracket door, fingerprinted. Phase-2 is Max-gated. **A halt is a result, not a gap.** |

These are unknowns rather than expected passes. Registration inserts screens a returning login never sees, and the reverse holds too — neither direction may be assumed from the other.

**≥3-host bar:** met — rogue, micro and a-net each reach `main_command`, with xeno a documented halt.

---

## Open items, stated rather than smoothed

### 1. a-net's letter: offered is not the same as playable — **resolved**

The a-net profile was configured with letter **C**. The door does offer `<C>`, but the game behind it is **closed**, so `ensure` now fails loudly with `game_closed` instead of wedging — the correct behaviour, and the fix working rather than a regression.

**The profile has since been repointed to letter `A`, which passes.** Bank-side edit, outside this repo; no product change was implied or made.

Recorded because the distinction cost real time and is easy to repeat: *the config has C*, *the door offers C*, and *the C game is playable* are three different claims, and only the third settles whether the letter is the problem. Checking the first two and stopping produces a confident wrong answer — it did here.

### 2. The regression gate — asked, then answered

rogue and micro had been proven on **earlier tips**, and `WO-ANET-GAME-SELECT-LETTER-STEP12` changed `login.py`'s menu branch, which **every host traverses**. They were the only cells that could show whether that shared-path change was safe, so the wave was ordered to run them *first* — a-net alone would have confirmed its own fix while leaving a break in the working hosts invisible.

**Answered: both re-proved on this lineage — rogue NEW and RETURNING and micro NEW all `main_command`@9.** The shared-path change did not regress the hosts that were already green.

The question is kept rather than deleted, because the answer is only meaningful with it.

### 3. Record classification **and** step, never a bare PASS/FAIL

`menu`@5 → `game_select`@12 was the single most useful datum of the day: it showed the banner fix had *worked* and moved the wall, which a bare FAIL would have hidden. A cell that records only PASS/FAIL cannot distinguish "no progress" from "progress, new door".

### 4. The remaining cells are first runs, not formalities

micro RETURNING and a-net RETURNING are tabled above as never-executed. When they are run they should be reported as whatever they turn out to be — a NEW pass is not evidence for a RETURNING pass in either direction.

---

## The confirming wave — order used, and what remains

1. **rogue** NEW + RETURNING — regression gate · **run, both `main_command`@9**
2. **micro** NEW — regression gate · **run, `main_command`@9**. RETURNING **still outstanding**
3. **a-net** NEW on letter **A** — last, after cool-off · **run, `main_command`@10**. RETURNING **still outstanding**
4. **xeno** — no live attempt; the halt stands on the existing fingerprint

Cool-off before a-net is not a formality. A host that has just refused connections will produce a failure that looks like a product defect and is not.

---

## Provenance

Cells for the confirming wave above were run by the hub at **2026-07-26T19:55:40Z** on tip `a5cfdda`, under the isolated bank with per-cell run-dirs beneath `reprove/confirm-195540Z/`. Raw `ensure` JSON stays in the bank, outside this repo.
