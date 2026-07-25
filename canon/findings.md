# Findings (DOCS-WIN)

**Path choice:** `canon/findings.md` — inside the reborn OKF bundle. The legacy root `knowledge/` bundle is retired to `archive/knowledge/` (per WO-CANON-HYGIENE-KNOWLEDGE); `canon/` is the sole live OKF root.
**Nature:** documentation-only. This file **edits no code** and imports nothing from `archive/`.
**Updated:** 2026-07-24 (WO-OKF-STATUS-TRUTH) — tip packages live under `tw2002_aiclient/` /
`tw2002_aiclient/session/` (ADR-001 relocate DONE). Pre-rebirth divergences below remain
**port-source caution** (do not revive); they are not an inventory of missing tip modules.

Central ledger of known **canon ↔ (pre-rebirth / port-source) code** divergences. Under
greenfield rebuild, these are **targets to avoid / correct when reimplementing** — not an
inventory of live root defects (the packages named in older rows lived under
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

**P2-027 reconnect/replay (execute):** live `session/guardian.py` (D9 poll+reconnect+`run_login`;
D10 keepalive stubbed for 028). Daemon DI start/stop. Collectable `test_guardian` — reconnect
green; keepalive skipped until 028. See WO-P2-027.

**P3 harness rehab (D1 execute):** shared `tests/fake_client.py` + `tests/pty_helpers.py`
(tw2002_aiclient-only; no `twclient`). Smoke collect green. Named Layer-B suites
(`test_spectate_*` / `test_interactive_app` / `test_aiclient_play_panels`) stay ignored until
owning PWO lifts them onto these helpers.

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

---

## Pending DOC-GAPs (Phase 4–5 · unsigned)

Logged at tip `bba53d4` (OKF-STATUS-TRUTH-056-057); Spectate reverse-vs-plain banked from CC PWO-060 mid-wave (hub @ 04:14:11Z); 061 Human→App + Ctrl-]@App-hold from kernel STATUS. **Pending** hub/Max canon — do not treat as signed prose.

### Ruled Max stamp (2026-07-25 · Batch-1 + **1b CLOSED** · Pending signed canon prose)
Hub relay `@ 09:12:51Z` + `@ 09:17:56Z`:
1. **Mode chord = Ctrl-A** (TTY; not Ctrl-M/⌘M). Toggles App↔Human both directions once App can hold the seat.
2. **While Human attached, bare `M` = TW Move** — passthrough to the game.
3. **Principle:** no **single printable** may be Mode (same collision class as `M` / game alphabet).
4. Batch-1 shape (not B′/C) closed earlier; **Batch 1b CLOSED** — HOLD lifts for 061-entry product under this contract. Spectate→Human bare `M` (056) should migrate to Ctrl-A (same WO or follow-on) so printable Mode does not remain. Ctrl-] detach unchanged. Cursor docs-only note; no signed north-star invent.
5. **Operator hazard (banked, not a second Mode key):** Ctrl-A is GNU `screen`'s default command prefix (and a common `tmux` rebind). Inside that multiplexer, Mode never reaches the app — use the mux escape (e.g. `Ctrl-A a`) or rebind. Unknown whether TradeWars itself consumes Ctrl-A.

### Ruled Max stamp (2026-07-25 · **Batch 2/3 CLOSED** · Pending FEATURES prose where noted)
Hub relay `@ 09:25:55Z`:
1. **Chip spelling = `APP`** (not Title-case App) — docs-win; match shipped `APP_LABEL="APP"`; no product rename.
2. **Spectate is not a Mode.** Default client run = autopilot (App). Spectate is observation chrome, not a third dual seat. **Ctrl-] from App-hold = deliberate no-op stay App** (do not invent Spectate transition).
3. **`log_note` → RETIRE** — product delete is CC (`WO-AUDIT-LOG-NOTE-RETIRE`); docs note only here.
4. **North-star SIGNED** — current `canon/architecture/north-star.md` (+ AI on-demand-only in teacher concepts) is Max-accepted; invent-HOLD lifts for *aligning* to it; do not invent new one-cockpit prose beyond signed text without a new Max ask.
5. **Archive `secrets.json` were never live** — no rotate required; close that gate.
6. CC product-TUI model = Opus (product seat; noted for paper trail).

### Ruled Max stamp (2026-07-25 · **entry chip = APP** · **CLOSED** tip `7c0e882`)
Hub relay `@ 09:33:23Z`: on cockpit **entry**, chip must show **`APP`** to match daemon `MODE_APP` — not SPECTATE. Product tip **`7c0e882`** (CC `WO-ENTRY-APP-CHIP`, rebased from `0537298`). Docs stamp `WO-AUDIT-ENTRY-APP-CHIP`.

| ID | Gap | Tip reality |
|---|---|---|
| DOC-GAP-M-FROM-SPECTATE | Canon frames `M` as App↔Human; silent on Spectate→Human | **CLOSED / SUPERSEDED** (ADR-002 · Batch 1b + 2/3): Mode=Ctrl-A; attached `M`=Move; Spectate≠Mode |
| DOC-GAP-POST-DETACH-COPY | Canon silent on post-detach status copy | Shipped `"detached — spectating"` (dispatch-decided) |
| DOC-GAP-SPECTATE-REVERSE-VS-PLAIN | `mode-line-and-teach-controls.md:196-198` says Spectate chip reverse-video like every badge; `spectate-and-attach.md:262` (+ PWO-060 constraint) say muted/**plain** | **055 shipped plain**; 060 keeps Spectate plain; dual App/Human get reverse+tone. Do not resolve in 060. |
| DOC-GAP-CTRL-RBRACKET-FROM-APP-HOLD | Ctrl-] from App-hold is a no-op today | **Ruled** Batch 2/3: deliberate **no-op stay App** (CC pins product; no Spectate invent) |
| DOC-GAP-APP-CHIP-SPELLING | Canon short **App** vs shipped `APP` | **Ruled** Batch 2/3: chip text **`APP`**; actor prose may still say App |
| DOC-GAP-ENTRY-CHIP-SPECTATE | Fresh cockpit entry showed SPECTATE while daemon MODE_APP | **DONE** tip `7c0e882` — App-hold entry; chip **APP** (match daemon) |
| HARDEN-ATTACH-SOCKET-TIMEOUT | Unbounded `AttachInputConn` socket read | **DONE** tip `88004d8` (`settimeout(5.0)` + OSError containment) · out of Phase-5 PREP |
| LOG-NOTE-RETIRE | Dead `log_note` helper | **Ruled RETIRE** — CC product delete; no silent keep |
| SECRETS-ARCHIVE-NEVER-LIVE | Rotate gate on archive secrets | **CLOSED** — Max: archive `secrets.json` never live; no rotate |

### Banked · session/ honesty audit (2026-07-25 · CC READ-ONLY · hub adjudicated `@ 12:15:44Z`)
Source tip at audit: `922739b`. Product fixes: F1 CUT (CC ∥ 064) · F2 after F1 · F3/F4 staged · **F5 🧑‍⚖️ Max** (no patch) · **F6–F8 BANK** (this stamp).

| ID | Gap | Tip reality |
|---|---|---|
| SESSION-F6-TRANSCRIPT-ORDER | `connection.py` logs payload *before* `sendall`; `session.py` appends after — broken pipe ⇒ records disagree | **BANKED** — no WO this wave |
| SESSION-F7-STATUS-DAEMON-RUNNING | `cli.py` `cmd_status` stamps `daemon_running: True` over failed round-trip (PID reuse) | **BANKED** — exit code stays honest; `--json` self-contradicts |
| SESSION-F8-WATCH-FRAME-GAP | `cli.py` `tw watch` swallows unparseable frames; `--frames N` counts only parsed | **BANKED** — invisible gap on corruption |
| SESSION-AUDIT-COVERAGE-GAP | `classify.py` (634 lines) unaudited except secret-prompt regex; also unread: `credentials` · `env` · `iac` · `terminal` · `player_bank` | **BANKED** — future audit WO must not inherit false coverage |
| SESSION-F5-INTERNAL-ERROR-STR | `daemon.py:76-77` widest catch returns `internal_error:{e}` (siblings type-name-only) | **🧑‍⚖️ Max** — DECISION-NEEDED; secrets leak UNVERIFIED; path disclosure VERIFIED |

