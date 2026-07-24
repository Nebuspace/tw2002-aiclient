# Findings (DOCS-WIN)

**Path choice:** `canon/findings.md` — inside the reborn OKF bundle. The legacy root `knowledge/` bundle is retired to `archive/knowledge/` (per WO-CANON-HYGIENE-KNOWLEDGE); `canon/` is the sole live OKF root.
**Nature:** documentation-only. This file **edits no code** and imports nothing from `archive/`.
**Updated:** 2026-07-23 (WO-P0-006).

Central ledger of known **canon ↔ (pre-rebirth / port-source) code** divergences. Under
greenfield rebuild, these are **targets to avoid / correct when reimplementing** — not an
inventory of live root defects (the packages named below lived under
`archive/pre-rebirth-2026-07-23/` and are not imported by the greenfield tree).

---

## Documented divergences (minimum four)

### 1. AI-pilot drive mode (no canon equivalent)

**Canon:** `canon/architecture/control-and-escalation.md` (Code Divergence) — also cross-cited
from `canon/architecture/session-engine.md`.

Pre-rebirth control-lock exposed `MODE_AI_PILOT` / `ai_pilot` as a mode in which "the AI drives."
Reborn north-star / control-and-escalation: live keyboard holders are `{app, human}` only; the AI
is a spectator-teacher that never live-drives. That drive mode has no canon equivalent and must
not return.

### 2. EV-every-tick picker vs stop-on-unknown run-loop

**Canon:** `canon/engine/priority-engine.md` (Code Divergence).

Pre-rebirth shape: `autopilot.select()` scored `run_chain` / `upgrade` / `explore` (etc.) from
scratch every tick — a **per-cycle EV** action-picker. Reborn model: taught-screen APP autopilot
runs known rules/macros and stops on the unknown for the human. Do not revive the EV-every-tick
driver as the live run-loop.

### 3. Legacy live-actor vocabulary vs reborn senders

**Canon:** `canon/architecture/session-engine.md` and `canon/engine/trace-ledger.md` (Code
Divergence sections).

Pre-rebirth `ledger.record_do()` declared actor among ai / trainer / human (default `"ai"`),
treating LLM-decided sends as a live `ai` value. Reborn send-time invariant: live senders are
`{app, human}` only; AI authorship is provenance of a *rule*, not a ledger live-actor value.

### 4. Founding auto-haggle money-path defect

**Canon:** `canon/engine/auto-haggle.md` (Code Divergence — founding auto-haggle finding).

The verified **78-turn**-autopilot money-path misfire is a real defect in the pre-rebirth
auto-haggle / autopilot money path. Reimplementation must treat that finding as a hard regression
target, not an acceptable behavior.

---

## REFERENCE-ONLY — `archive/pre-rebirth-2026-07-23/`

Port-source snapshot only. **Nothing under `archive/` is imported by the greenfield tree.**

Top-level (as of WO-P0-006):

| Path | Note |
|------|------|
| `code/` | Pre-rebirth product packages (`tw2002_aiclient/`, `twclient/`, tests, launchers) |
| `config/` | Pre-rebirth config / secrets layout reference |
| `docs/` | Pre-rebirth operator / design docs |
| `runtime/` | Pre-rebirth runtime artifacts reference |
| `tooling/` | Pre-rebirth tooling |
| `root-misc/` | Misc root leftovers |
| `README.md` | Archive index |

Use for field-shape / behavior reference when a WO explicitly allows it. Never restore to repo root;
never drive recommendations that contradict reborn `canon/`.

---

## Stale `twclient` test collection (WO-TEST-SUITE-REHAB)

**Symptom:** stale tests still `import twclient` (archive-only). Rehab buckets live in
`workorders/WO-TEST-SUITE-REHAB.md`. **Default honesty (WO-TEST-COLLECT-HYGIENE):** `pytest.ini`
`--ignore=`s every banked uncollectable file so `pytest --collect-only` / `pytest -q` run only the
greenfield suite (0 collection ERRORS). Remove an ignore line when that file is rewritten/Accepted.

**P2-025 control-lock (execute):** live `session/control_lock.py` modes `{app,human,spectate}`;
daemon owns lock + thin attach; ensure via `acquire_driver`. Collectable:
`test_control_lock` · `test_actor_attribution` · `test_tw04_toctou`. Attach rehab pair +
`test_clean_preempt` remain ignored (DEFER). See WO-P2-025 §Lane 3 EXECUTE.

**P2-026 settle (prep):** kernel already in `session/settle.py` + green `tests/test_settle.py`; execute
likely verify + case-mismatch unit — see `workorders/WO-P2-026-settle-detection-baseline.md` §PREP.

**P2-027 reconnect/replay (prep):** no live `guardian.py`; drop flag + `Session.reconnect` +
`run_login`/`secret=True` already match — execute ports supervisor + rewrite
`tests/test_guardian.py -k reconnect` (keepalive stays 028). See
`workorders/WO-P2-027-reconnect-login-replay.md` §PREP.

**P2-028 idle-keepalive (prep):** zero live D10; archive `_maybe_keepalive` matches mechanical
canon; execute tags `sender=app` + rewrite `test_guardian -k keepalive` (5). See
`workorders/WO-P2-028-idle-keepalive-off-on-unsafe.md` §PREP.

## Run-dir override (WO-P2-021)

**Canon:** `canon/architecture/session-engine.md` (Single-Connection Invariant).

The daemon's pidfile + socket home is the **project-rooted** `run/` directory
(`run/twd.pid`, `run/twd.sock`), resolved via `tw2002_aiclient.session.env.resolve_run_dir()`
regardless of caller CWD. The **sole documented override** is the environment variable
`TW_RUN_DIR` (absolute, or relative to the project root). There is no silent per-profile
`run/<profile>/` splinter under the default — one daemon, one `run/` home, matching the
single-connection invariant. A second process pointed at the same run-dir is refused by the
atomic pidfile claim; a different `TW_RUN_DIR` is an independent home (operator-chosen
isolation, not automatic).
