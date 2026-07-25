# AUDIT — Test suite duplicate / pointless triage

> Seat: `impl-aiclient-cursor` · WO: `WO-AUDIT-TEST-SUITE-DUP-POINTLESS` · Max @ 10:24 ET  
> Tip base: origin `ae95271` · UTC: 2026-07-25T14:35Z  
> Nature: **read-only report** — no deletions · no consolidations · no `pytest.ini` edits · no product `.py`  
> Evidence sources: OKF catalog `canon/testing/test-case-catalog.md` (tip `4882045` / blur `ae95271`) · `pytest.ini` ignore list · CC PROCESS-NOTE `@ 14:25:51Z` (incorporated, not re-derived) · focused file reads · one subsystem scout (cli/session)

---

## Exec summary

| Metric | Count | Notes |
|---|---:|---|
| Catalog snapshot (OKF) | **2271** cases · **129** modules | 83 active / 1263 · 46 BANKED / 1008 — **stale vs tip** |
| Tip filesystem now | **94** active `test_*.py` · **44** BANKED ignores | Catalog lag: ≥9 active modules have **no** case file |
| Examined (this WO) | Catalog inventory + CC hand-overs + ~22 cli/session files + cockpit Layer-A/B pattern + crawl_sacrificial family + banked archive twins | Not a line-by-line re-read of all 2271 |
| Suspect true DUP (cuttable twins) | **0** | No identical-assertion pairs recommended CUT |
| Suspect POINTLESS (no teeth) | **0 confirmed** | Several *look* tautological; all CC-proven KEEP or environment-coupled |
| NEAR-DUP-KEEP | **many** (pattern) + **named rows below** | Layer-A composer vs Layer-B pty · unit vs wire |
| REHAB / BANK / HOLE | **named below** | login-redaction · attach-redaction failure-blind · `--keys` unencodable hole · catalog gaps |

**Headline for hub triage:** nothing to delete this WO. Actionable follow-ons are catalog catch-up, a `--keys` unencodable coverage WO, login-redaction REHAB (Max #3 still open), and attach-redaction failure-path REHAB (F6 lesson).

---

## Do-not-touch (safety-critical pins)

Even if verbose / low-drama / parametrized-looking:

| Pin | Why KEEP |
|---|---|
| `tests/test_cli_attach_keys_exit_code.py::test_cmd_attach_keys_empty_string_sends_nothing_and_returns_zero` | **`032bc12` honesty pin** — empty ≠ full-drop. Looks tautological; currently void in practice until SURROGATE/F3 lands; pin makes that fix provable (CC `@ 14:25:51Z`) |
| `tests/test_spectate_no_send.py` | Security canary — fires if cockpit entry default gains a send path without legitimized gate |
| `tests/test_crawl_driver.py` Leg-1 refuse family (incl. string `"false"`) | **Not clones** — pins refuse on `"false"` where archive `getattr(..., False)` would accept |
| Redaction suites (`test_attach_redaction.py` success path) + control-lock (`test_control_lock.py` / actor attribution / TW-04) | Safety list — KEEP even when verbose |
| Attach honesty (`test_cli_attach_interactive_send_failure.py`, keydrop honesty, send-key bool) | Wire/rc honesty — KEEP |
| Crawl sacrificial + chokepoint adversarial refuse | Canon K3 structural legs — KEEP whole family |

**Method note (CC):** inject-defect / shadow-tree red-check is valid; separate **preservation pins** (must stay green on both sides) from **new-behavior pins** (must go red on pre-fix) before any CUT. This report recommends **zero CUTs**.

---

## ACTIVE findings

| nodeid(s) / module | category | evidence | recommendation | risk if cut |
|---|---|---|---|---|
| `test_cli_attach_keys_exit_code.py::…_empty_string…` | NEAR-DUP-KEEP (looks POINTLESS) | Docstring + CC: deliberate empty≠drop pin (`032bc12`); verified green | **KEEP** | Loses SURROGATE/F3 acceptance criterion |
| `test_spectate_no_send.py` (module) | NEAR-DUP-KEEP | Security canary; fired + re-justified this wave | **KEEP** | Silent send regression possible |
| `test_crawl_driver.py::test_leg1_only_an_explicit_true_opens_the_gate` (+ refuse family) | NEAR-DUP-KEEP | Param over `False/None/0/""/"false"/"true"/…` — `"false"` is the load-bearing case | **KEEP** (whole family) | Re-opens archive getattr hazard |
| `test_attach_redaction.py` (8 tests) | NEAR-DUP-KEEP / REHAB | Good falsification on **success** path; CC inject of fail-path payload stayed **8/8 green** | **KEEP** + **REHAB** (add fail-path) | Cutting loses success-path teeth |
| `test_cli_attach_unencodable_key.py` (all cases `keys=None`) | coverage **HOLE** (not DUP) | Zero `--keys` unencodable coverage; scripted branch untested | **KEEP** module · add `--keys` cases in keys-exit suite (**don't** touch empty pin) | N/A — hole, not cut |
| Layer-A `test_cockpit_*.py` vs Layer-B `*_pty.py` pairs | NEAR-DUP-KEEP | Composer purity vs real curses/pty wire — different failure modes | **KEEP** both | Cutting pty loses paint/attr regressions |
| `test_cockpit_arm.py` / `_wiring` / `_pty` | NEAR-DUP-KEEP | Pure indicator · wiring · pty Accept #4 — layered on purpose (062) | **KEEP** | Weakens arm≠seat / no-silent-arm proofs |
| `test_cockpit_stopbanner.py` vs `_wiring.py` | NEAR-DUP-KEEP | Catalog compose vs screens paint | **KEEP** | Banner height/paint regressions |
| `test_cli_attach_interactive_send_failure.py` vs `test_cli_attach_unencodable_key.py` | NEAR-DUP-KEEP | Explicit split: dead-wire fatal vs unencodable keep-alive | **KEEP** both | Merging would collapse opposite DoDs |
| `test_safe_addstr_choke.py` · `test_glyph_table_dedupe.py` | environment-coupled (not POINTLESS) | `git show <sha>:<path>` blob loaders — fail in rsync/worktree without `.git` | **KEEP** · flag harness class | Cutting loses choke/dedupe regression |
| Structural: `_FakeAttachConn` / `terminal_mode` / `tty_fd` fixtures 2–3× across attach files | STRUCT-DUP (helpers) | Scout: duplicated harness helpers | **MERGE** at next edit (not this WO) | Low — only churn risk |
| Uncatalogued active: `test_attach_keydrop_honesty` · `test_tx_record_honesty` · `test_cli_menumap_lookup_honesty` · `test_cli_attach_unencodable_{key,pty}` · `test_loops_store` · `test_menu_crawl_*` · `test_menu_map_view_here_unknown` · … | CATALOG-GAP | Tip has modules; OKF case files missing | **KEEP** tests · **docs** catalog catch-up | N/A |

---

## BANKED findings

| nodeid(s) / module | category | evidence | recommendation | risk if cut |
|---|---|---|---|---|
| `tests/test_login_redaction.py` (BANKED · `pytest.ini:54`) | REHAB (not CUT) | `import twclient` → uncollectable; holds full redaction + **falsification**; **LOGIN password path proof not running** (only attach live) | **REHAB** when Max #3 / login stabilises — port to greenfield | Cutting destroys unique settle/ledger/error-text coverage |
| `tests/test_intervention_labels.py` | BANKED archive twin | Imports `twclient.intervention_labels`; live catalog is `cockpit/stopbanner.py` (`af62889`) | **BANK** / eventual REHAB or CUT-after-stopbanner coverage proven | Premature CUT if stopbanner suite gaps remain |
| `tests/test_spectate_app.py` · `test_spectate_layout.py` | BANKED archive | `import twclient` + AI-PILOT era; product spectate is `test_cockpit_spectate.py` | **BANK** — do not CUT until cockpit suite owns every archive property still wanted | Silent loss of archive-only geometry pins |
| `tests/test_aiclient_play_panels.py` · `test_control_panel.py` · `test_interactive_app.py` | BANKED archive | Pre-rebirth UI; rehab via owning PWO | **BANK** / REHAB per `WO-TEST-SUITE-REHAB` | Same |
| `tests/test_ledger.py` · many Phase-6/world BANKED | BANKED | Product modules not ported | **BANK** — not DUP of live suite | Cutting loses port-source acceptance seeds |
| BANKED suites that *look* like LIVE twins | NEAR-DUP vs LIVE | Often archive path + different asserts; treat as REHAB candidates not CUT | **BANK** until property-mapped | False "green by accident" if LIVE doesn't cover archive property |

---

## Coverage holes (not duplicates)

| Hole | Evidence | Follow-on |
|---|---|---|
| Scripted `tw attach --keys <unencodable>` | Unencodable suite uses `keys=None` only | Add cases beside keys-exit suite; preserve empty-keys pin |
| Attach redaction **failure** path | F6 inject stayed green on `test_attach_redaction` | Extend suite when F6 tip on origin |
| Login password redaction | BANKED `test_login_redaction` uncollected | Max #3 + REHAB WO |
| Catalog lag (≥9 active modules) | Filesystem 94 active vs catalog 83 | Docs tip: regenerate/append case files |

---

## Explicit non-findings

- **No CUT recommendations** in this report.
- Cockpit Layer-A vs Layer-B volume is intentional D1 harness law — not pointless duplication.
- Parametrized crawl-gate matrix is intentional adversarial allowlist proof — not clone spam.

---

## Accept / Proof (this WO)

- Report path: `workorders/AUDIT-TEST-SUITE-DUP-POINTLESS.md`
- Zero product behavior change · zero `pytest.ini` change
- Push waits Accept

## Refs

- Max HANDOFF `@ 2026-07-25T14:24:58Z`
- CC evidence relay hub `@ 14:26:12Z` / CC `@ 14:25:51Z`
- OKF catalog tip `4882045` · blur `ae95271`
- Suite-green≠coverage PROCESS-NOTE (F6 / attach-redaction)
