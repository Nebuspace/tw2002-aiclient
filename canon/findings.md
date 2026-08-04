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

### 1. AI-pilot drive mode (no canon equivalent) — RETIRED on tip

**Canon:** `canon/architecture/control-and-escalation.md` (Code Divergence · resolved) — also
cross-cited from `canon/architecture/session-engine.md`.

Pre-rebirth control-lock exposed `MODE_AI_PILOT` / `ai_pilot` as a mode in which "the AI drives."
Reborn north-star / control-and-escalation: live keyboard holders are `{app, human}` only; the AI
is a spectator-teacher that never live-drives. **Tip status (2026-08-04):**
`tw2002_aiclient/session/control_lock.py` defines only `{app, human, spectate}` — the drive mode
is gone from product code. Remains a **do-not-revive** flag (not an open tip defect).
(`AUDIT-CANON-DRAFT-AI-PILOT-RETIREMENT-STALE`.)

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
Source tip at audit: `922739b`. Product fixes: F1 DONE `7e13b7d` · F2/F3/F4 in flight · **F5 Ruled (A)** · **F6 DONE `c21cd1c`** · F7/F8 BANK · **F9 DONE `879280f`** · CLI-ASCII write-choke BANK (Max ruling pending).

| ID | Gap | Tip reality |
|---|---|---|
| SESSION-F6-TRANSCRIPT-ORDER | `connection.py` / `session.py` / `_send_raw`+TX-IAC log-AFTER `sendall`; fail path type/phrase only | **DONE** origin `a33825a` (orphan preserve `c21cd1c` — do not rebuild) — scope includes `_send_raw`/TX-IAC, not only the two banked files |
| SESSION-F7-STATUS-DAEMON-RUNNING | `cli.py` `cmd_status` stamps `daemon_running: True` over failed round-trip (PID reuse) | **DONE** tip `b2ef693` · `WO-MT-03-STATUS-DAEMON-RUNNING` — `daemon_running` follows round-trip `ok`; failed RT sets `status_unreachable` + rc 1; pinned by `tests/test_cli_status_daemon_running_honesty.py` |
| SESSION-F8-WATCH-FRAME-GAP | `cli.py` `tw watch` swallows unparseable frames; `--frames N` counts only parsed | **DONE** tip `397f11d` · `WO-MT-04-WATCH-FRAME-SWALLOW` — stderr `ERROR: watch_frame_unparseable`; corrupt lines do not count toward `--frames N`; pinned in `test_cli_ops_verb_e2.py` |
| SESSION-AUDIT-COVERAGE-GAP | `classify.py` + companions (`credentials` · `env` · `iac` · `terminal` · `player_bank`) | **REPORT LANDED** — `audit/session-classify-audit-coverage-20260726.md` (classify end-to-end; companions scoped-next). Prior "634 lines / only secret-prompt tests" wording was **stale**. Residuals C-01…C-07 banked as suggested WOs. MT-11 restated. |
| SESSION-F5-INTERNAL-ERROR-STR | `daemon.py` widest catch `internal_error:{e}` vs type-name-only siblings | **Ruled (A)** Max `@ 14:28:33Z` — wire type-name-only + local traceback; **DONE** tip via `WO-AUDIT-F5-TYPE-NAME` |
| LOGIN-REDACTION-SUITE-NOT-RUNNING | `tests/test_login_redaction.py` still `import twclient` · pytest.ini `--ignore` | **BANKED → REHAB soon** Max #3 `@ 14:31:06Z` — `WO-AUDIT-LOGIN-REDACTION-REHAB` · MISSING-TESTS MT-02 |
| KEYS-ARGV-SHELL-HISTORY | `tw attach --keys` puts keystrokes on argv/process table/shell history; canon was silent; help/README lacked warn | **BANKED + docs warn** — README + Invariant 1 hazard; argparse help draft for product |
| SESSION-F1-ATTACH-SEND-KEY-BOOL | Interactive `tw attach` discarded `send_key` bool → silent ATTACHED black hole | **DONE** tip `7e13b7d` (was `4754dd4`) · `WO-AUDIT-ATTACH-SEND-KEY-BOOL` |
| SESSION-F1-MICRO-SETTLE-NUDGE | `cli.py` discarded post-spawn `send_request("read")` dict (was falsely banked as "benign settle-nudge") | **DONE** tip `61bdea2` · product now checks/retries settle `read` (WO-ENSURE-SPAWN-READINESS); prior "benign" claim reversed · MISSING-TESTS MT-09 amended |
| SESSION-F1-MICRO-DOCSTRING | `cli.py` module docstring claimed `tw watch` is **the** lifetime-stream exception | **DONE** tip `9110a95` · `WO-MT-12-WATCH-DOCSTRING` — tip now names both `tw watch` and `tw attach` as lifetime socket holds |
| P5-064-STALE-INTERVENTION-PATH | Canon / archive tests cite `twclient/intervention_labels.py` | **DONE** tip `af62889` catalog in `cockpit/stopbanner.py` · canon cites retargeted (`WO-TIP-STAMP-P5-064-STALE-INTERVENTION-PATH`); BANKED archive `test_intervention_labels.py` remains a separate ignore-list item |
| P5-064-SCREENS-BADGE-DOCSTRING | `screens.py` module docstring still says no dynamic App/Human mode badge | **FIXED** — docstring aligned to 060 `control_seat` chip · `WO-SCREENS-BADGE-DOCSTRING-STALE` |
| F9-COCKPIT-UTF8-GARBAGE-FORWARD | Cockpit `getch()` path forwarded each UTF-8 byte `<256` as its own `send_key` | **DONE** tip `879280f` — refuse multi-byte UTF-8 getch + ungetch truncated lead; `WO-AUDIT-COCKPIT-UTF8-GETCH` CLOSED |
| CLI-ASCII-WRITE-CHOKE | Non-UTF-8 stdout: `./tw --help` / `menumap` / `loops` crash mid-output on ★ / em-dash / … after attach-only ASCII banner fix `fec3ffe` | **BANKED** — docs do **not** close product. Reachable: `PYTHONIOENCODING=ascii\|latin-1` · `LC_ALL=en_US.ISO8859-1` · `LC_ALL=C` with UTF-8 mode **off** (bare `LC_ALL=C` does **not** crash — PEP 540). Product WO **STAGED** pending Max glyph ruling (A refuse / B NO-SWAP substitute / C other). MISSING-TESTS MT-05/06. Stub: `workorders/WO-AUDIT-CLI-ASCII-WRITE-CHOKE.md` |

### Root markdown retirement (Max 2026-07-25)

Repo-root `DESIGN.md` and `priority_engine.md` are **deleted**. Content ownership:

- **DESIGN.md** → already prescribed by `/architecture/session-engine.md`, `cli-verbs.md`, `settle-detection.md`, north-star. Unique leftover: MCP-ready-by-construction note folded into session-engine. AI-live-driver framing remains superseded (Finding 1).
- **priority_engine.md** → already the source material for `/engine/priority-engine.md` (reborn ranker, not EV-every-tick driver — Finding 2). Citations retargeted; root file removed.

Do not grow new architecture dumps at repo root — sole docs root is `canon/`. Work order: `workorders/WO-ROOT-MD-INTO-CANON.md`.

### Screen-pattern research → OKF (Max 2026-07-25)

Useful patterns extracted to [`/research/tw2002-screen-patterns.md`](/research/tw2002-screen-patterns.md).
`research/*-FINDINGS.md` are redirects. Implementer brief: `workorders/BRIEF-OKF-SCREEN-PATTERNS.md`.

### Archive Port Patterns — research doc landed (2026-07-25 · Monk WO-ARCHIVE-PATTERNS-INTO-CANON)

**Canon addition:** `canon/research/archive-port-patterns.md` — 14 patterns (AP-01…AP-14) distilled from `archive/pre-rebirth-2026-07-23/code/twclient/`. No archive code restored to root; archive stays reference-only.

**Key do-not-revive flags recorded here (cross-reference to Documented divergences §1/§2):** `ai_pilot` mode, `autonomous` profile flag, `actor="trainer"` ledger enum, EV-every-tick live run-loop, `LoopPlayer` autonomous loop — all in the Negative Patterns section of the new concept.

**Cross-links added to:** `architecture/settle-detection.md` [7] · `architecture/login-automaton.md` [6] · `engine/world-model.md` (last bullet) · `strategy/trade-loops.md` (chains bullet). Implementer brief: `workorders/BRIEF-OKF-ARCHIVE-PORT-PATTERNS.md`.
