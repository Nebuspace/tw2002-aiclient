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

## Cell state on `a5cfdda`

| Host | Letter | NEW | RETURNING | Notes |
|---|---|---|---|---|
| `roguetw.net:2002` | A | **PASS** `main_command` | **PASS** `main_command` | Proven on `7e43af6`. **Not re-run on `a5cfdda`** — see regression gate below. |
| `twgs.microblaster.net:2002` | B | **PASS** `main_command` | **not yet run** | NEW proven post-merge. RETURNING is newly possible — a credential now exists where none did this morning. |
| `game.a-net-online.lol:2002` | A | **PASS** `main_command` | **not yet run** | Letter **A**. Bank profile is configured **C**, which is a **closed game** — see below. |
| xeno / `twgs.exiled.org:2002` | — | **N-A** honest halt | **N-A** | Untaught square-bracket door, fingerprinted. Phase-2 is Max-gated. **A halt is a result, not a gap.** |

**≥3-host bar:** met — rogue, micro and a-net each reach `main_command`, with xeno a documented halt.

---

## Open items, stated rather than smoothed

### 1. a-net's letter: offered is not the same as playable — **resolved**

The a-net profile was configured with letter **C**. The door does offer `<C>`, but the game behind it is **closed**, so `ensure` now fails loudly with `game_closed` instead of wedging — the correct behaviour, and the fix working rather than a regression.

**The profile has since been repointed to letter `A`, which passes.** Bank-side edit, outside this repo; no product change was implied or made.

Recorded because the distinction cost real time and is easy to repeat: *the config has C*, *the door offers C*, and *the C game is playable* are three different claims, and only the third settles whether the letter is the problem. Checking the first two and stopping produces a confident wrong answer — it did here.

### 2. `a5cfdda` has not been re-proved on the hosts that were already green

rogue and micro were proven on **earlier tips**. `WO-ANET-GAME-SELECT-LETTER-STEP12` changed `login.py`'s menu branch, which **every host traverses**.

**The confirming wave should run rogue and micro first, as regression gates, before a-net.** They are the only cells that can show whether the shared-path change was safe, and they were green before it landed. Running a-net alone would confirm the fix while leaving a break in the working hosts invisible.

### 3. Record classification **and** step, never a bare PASS/FAIL

`menu`@5 → `game_select`@12 was the single most useful datum of the day: it showed the banner fix had *worked* and moved the wall, which a bare FAIL would have hidden. A cell that records only PASS/FAIL cannot distinguish "no progress" from "progress, new door".

### 4. micro RETURNING and a-net RETURNING are first runs

Neither has ever been executed. They are not expected failures — they are **unknowns**, and should be reported as whatever they turn out to be rather than assumed to mirror NEW. Registration inserts screens a returning login never sees; the reverse also holds.

---

## Suggested order for the confirming wave

1. **rogue** NEW + RETURNING — regression gate
2. **micro** NEW + RETURNING — regression gate, and RETURNING is a first run
3. **a-net** NEW + RETURNING on letter **A** — last, and after cool-off: the host refused connections following a probe burst earlier today
4. **xeno** — no live attempt; the halt stands on the existing fingerprint

Cool-off before a-net is not a formality. A host that has just refused connections will produce a failure that looks like a product defect and is not.
