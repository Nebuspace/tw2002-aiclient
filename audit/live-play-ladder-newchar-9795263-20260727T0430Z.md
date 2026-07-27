# LIVE prove — Play ladder, NEW character on a random catalog server

**WO:** `WO-PLAY-LADDER-LIVE-PROVE` (NEW-char amendment) · **Seat:** `impl-claudecode-aiclient`
**Tip proved against:** `9795263` · **UTC:** 2026-07-27T04:24Z–04:33Z
**Mode:** LIVE — real public TWGS server, real registration, real daemon. No mocks, no
`127.0.0.1` harness, no reuse of the matrix bank or Max's bank.

---

## Verdict

| leg | result |
|---|---|
| NEW character created on a randomly-chosen catalog server | ✅ **PASS** |
| Live `ensure` → `main_command` via NEW registration | ✅ **PASS** |
| Play TUI: offer visible → `E` → `y` → explore ≥5 | ❌ **FAIL — and the failure is a real product defect, not a harness fault** |

**The Play ladder's explore offer is structurally invisible on a live session.** It renders
only when the LOGS band has no daemon transcript, which is never true once a session is
actually connected. Every unit and pty test passes because none of them has a daemon tail.

---

## What was proved live

Fresh isolated config (never the git tree), fresh run-dir:
```
TW_CONFIG_DIR=/tmp/play-ladder-newchar-20260727T0424Z    (secrets.json chmod 600)
TW_RUN_DIR   =/tmp/play-ladder-newchar-run-20260727T0424Z
```

**Server selection — RNG method recorded per the WO.** `secrets.SystemRandom()` (CSPRNG),
uniform `choice` over the 44 sorted `[servers.*]` keys in `config/servers.toml`.

| attempt | key | host:port | outcome |
|---|---|---|---|
| 1 | `roysdon_net` | `tw2002.roysdon.net:2002` | reachable, ensure did not settle |
| 2 | `error_404` | `error404bbs.ddns.net:24` | BBS front-end on a non-2002 port — needs door navigation this WO does not scope |
| 3 | **`polarwireless`** | **`polarwireless.ca:2002`** | ✅ **NEW character registered, reached `main_command`** |

Attempt 3's re-roll was filtered to port 2002 after attempt 2 taught that a non-2002 catalog
entry is a BBS front-end rather than a direct TWGS door. Filter recorded here rather than
left implicit — it narrowed the random draw.

Profile was hand-written with `allow_register = true` (`create_profile()` forces it false).
Handle `Proof79ba3d58`, game letter `A`, both generated per-run. Sacrificial ship/planet
names `ProofRunner` / `ProofRock`. **The generated password was written only to the
chmod-600 `secrets.json` in the isolated config — never echoed, never in argv, never in this
audit, never in coord.**

**Registration evidence** (the game's own words, on the live wire):
```
Blasting off from ProofRock
Sector  : 54 in Benkei (unexplored).
Ports   : Pogson, Class 8 (BBB)
Command [TL=00:00:00]:[54] (?=Help)? :
```
`ProofRock` is the planet name this run generated — proof the character is ours and new.

**Daemon status after ensure:** `connected=true` · `classification=main_command`.

---

## The defect this live prove found

`app.py` (L3) writes the explore offer to `play.status_line`:
```python
play.status_line = f"session ready — {result.classification}  ·  explore ×5 available — press E"
```

`screens.py:1555` renders that field **only when the LOGS band has nothing real to show**:
```python
has_real_tail = current_newest is not None          # :1538
...
if not has_real_tail and self.status_line and logs_inner_h > 0:   # :1555
    logs_lines = [self.status_line[:logs_inner_w]]
```

On this live session `has_real_tail` is **True** — the daemon reports a populated
`log_tail`:
```
log_tail: ['app> ', 'app> A', 'app> Proof79ba3d58', 'app> Y', 'app> T', 'app> N',
           'app> Y', '<<secret input redacted>>', ...]
```
(Incidentally: the redaction sink is working — the password send appears as
`<<secret input redacted>>`, never as content.)

So the offer text is written, and then never drawn. The operator sees the game transcript in
LOGS and **no indication that `E` does anything**. `E` still works if pressed blind — the
key path is live and correct — but nothing tells the human it exists.

**Why the whole suite missed it.** `status_line` is a *fallback* for an empty LOGS band. Every
unit and pty test drives a stubbed or absent daemon, so `has_real_tail` is False and the
fallback always renders. The tests assert the offer appears; on the only configuration that
matters — a connected session — it cannot. This is the same shape recorded in
`suite-green-is-not-coverage`: **a suite's coverage is bounded by the states its fixtures
drive**, and no fixture drove "LOGS has real content".

---

## Follow-on (banked, not built here — this WO is a prove, not a fix)

`WO-PLAY-OFFER-VISIBLE-ON-LIVE` — the explore offer needs a surface that survives a populated
LOGS band. Candidates for the hub to rule between: a dedicated affordance slot on the control
strip beside the teach band (where `A)nalyze R)ecord T)rigger` already live and are visible on
this very screenshot); or promoting the offer out of the `status_line` fallback into its own
row. **Not** "make status_line always win" — that would erase the daemon transcript, which is
the LOGS band's actual job.

A regression pin must drive a **populated** `log_tail`, or it will pass exactly as the current
ones do.

---

## Cleanup

`explore stop` + `tw stop` issued against the run-dir. The registered character is
sacrificial and abandoned in place — no further action taken against the host.

## Honesty statement

**Play keys driven: PARTIAL.** `Enter` (profile select) was typed into a real pty and the Play
shell rendered the live session. `E` and `y` were **not** typed, because the offer they
respond to never appeared on screen — the harness waits for `press E` and correctly refused to
send a keystroke for an affordance the operator could not see. Claiming a pass by sending `E`
blind would have proved the key handler while hiding the defect that makes the feature
unusable.
