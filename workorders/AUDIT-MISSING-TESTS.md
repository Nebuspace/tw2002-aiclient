# AUDIT-MISSING-TESTS

**WO:** `WO-AUDIT-MISSING-TESTS` · report-only · tip base `a7e66c1`  
**Seat:** `impl-aiclient-cursor` · 2026-07-25  
**Nature:** create-list of tests we should have but do not. **Not** a DUP/POINTLESS re-litigation.  
**Exclude:** 0-CUT pins from `AUDIT-TEST-SUITE-DUP-POINTLESS.md`; inventing tests for RETIRED `tw spectate` ops.

---

## Method

1. Hub HANDOFF honesty classes + `canon/findings.md` BANKED rows (F7/F8 · LOGIN-REDACTION · ASCII residual).
2. `pytest --collect-only` vs live modules; keyword scan of `tests/` for each candidate.
3. Spot-read suites named in recent STATUS (attach-redaction · watch · status · login · keys-encoding · ascii-terminal · loops).
4. Cross-check DUP-POINTLESS "coverage holes" — some closed since that report (`--keys` unencodable now covered by `test_cli_attach_keys_encoding.py`).

---

## Headline

| Band | Count | Notes |
|---|---|---|
| **P0** | 3 | Redaction fail-blind · login return/exception redaction not collecting · status `--json` self-contradict |
| **P1** | 6 | Watch frame swallow · CLI ASCII write-choke · help glyph pin · settle-nudge · ensure leak surface · secrets fail-path |
| **P2** | 3 | Peercred · classify breadth · docstring honesty |
| **CLOSED since DUP** | 1 | Scripted `--keys` unencodable (see Non-gaps) |

Coverage is **not** thin overall (~150 test modules; attach/cockpit/loops dense). Gaps cluster on **failure-path honesty**, **BANKED session residuals**, and **uncollected REHAB**.

---

## Gaps (create-list)

| ID | Gap | Why it matters | Suggested nodeid / module | P | Depends-on | Draft Accept |
|---|---|---|---|---|---|---|
| MT-01 | **Attach redaction failure-path blind** — `tests/test_attach_redaction.py` only drives success `_StubSocket.sendall` (pass). No inject where `sendall` raises mid-secret; F6-class leak can stay green. | Suite-green ≠ coverage (DUP lesson). Secret can leak on fail-log path while 8/8 stay green. | `tests/test_attach_redaction.py::test_*_failpath_*` (extend) | **P0** | none (product tip already on origin) | Inject `sendall` raise under Password: prompt; assert sentinel absent from transcript + `last_sent` + status JSON **and** a falsification that removing the fail-path gate lets it leak. |
| MT-02 | **Login password never in return / `LoginError` / ledger — suite not collecting** — `tests/test_login_redaction.py` still `import twclient`; `pytest.ini:54` `--ignore`. Live `test_login.py` only proves transcript absence, not sink (c)/(d) from the BANKED suite. | `login.py:58` invariant ("NEVER touches return values, exceptions") has **no collecting test**. | Port as `tests/test_login_redaction.py` (greenfield) or `tests/test_login_password_sinks.py` | **P0** | **CC `WO-AUDIT-LOGIN-REDACTION-REHAB`** (queued behind credentials) | Collecting suite: sentinel absent from `run_login` return · raised `LoginError` text · ledger; plus inject-leak proves the suite catches a regression. |
| MT-03 | **`tw status --json` stamps `daemon_running: True` over a failed round-trip** — `cli.py` `cmd_status` sets `resp["daemon_running"] = True` after `daemon_alive` even when `send_request` returns `ok: False` / connect failure shape (SESSION-F7). Existing tests only assert `daemon_running is False` when daemon down. | Exit code can be honest while JSON self-contradicts (PID reuse / dead sock). | `tests/test_cli_status_daemon_running_honesty.py` | **P0** | product tip for F7 (BANKED — may need product WO first) | With pidfile alive + status round-trip failing: `--json` must **not** claim `daemon_running: True` (or must pair with explicit `status_unreachable`); rc stays non-zero. |
| MT-04 | **`tw watch` swallows unparseable frames** — `cli.py:393-394` `except JSONDecodeError: continue`; `--frames N` counts only parsed events. `test_cli_ops_verb_e2.py` only feeds clean NDJSON. | Corruption looks like a short stream; operators cannot tell frames were dropped (SESSION-F8). | `tests/test_cli_ops_verb_e2.py::test_unparseable_frame_*` | **P1** | product tip for F8 (BANKED) | Interleave one corrupt line between two valid events; either surface a counted skip/error **or** document+pin current swallow with an explicit "gap acknowledged" assert hub Accepts — prefer product tell. |
| MT-05 | **CLI stdout write-choke on non-UTF-8** — attach banner ASCII-fixed (`fec3ffe`); `tw --help` / `menumap` / `loops` still die mid-output on ★ / em-dash / …. Reachable: `PYTHONIOENCODING=ascii\|latin-1` · `LC_ALL=en_US.ISO8859-1` · `LC_ALL=C` **with UTF-8 mode off** (bare `LC_ALL=C` does **not** crash — PEP 540). | Operator help/list verbs crash after partial print. | `tests/test_cli_ascii_write_choke.py` (name TBD post-ruling) | **P1** | **Max glyph ruling** (A refuse / B substitute / C other) + product WO | After ruling: under `PYTHONIOENCODING=ascii`, `./tw --help` and `./tw menumap` / `./tw loops` either exit with ASCII-only error **or** complete without `UnicodeEncodeError` per ruled policy. |
| MT-06 | **Global help glyph inventory pin** — `test_cli_attach_ascii_terminal` pins attach help ASCII; `test_cli_loops` pins **loops** help ASCII and *documents* that `./tw --help` already dies on menumap ★ — but no collecting test fails when a new non-ASCII `help=` lands on other verbs. | Regression magnet for the ASCII crash surface until MT-05 ships. | `tests/test_cli_help_ascii_inventory.py` | **P1** | none (docs/pin only; or fold into MT-05) | Every `add_parser(..., help=)` / epilog string reachable from `build_parser().format_help()` is `.isascii()` **OR** (post-ruling) the write-choke test supersedes this pin. |
| MT-07 | **Login/ensure JSON error surface can carry password** — live login tests never assert sentinel absent from `ensure` / protocol error dict folded to CLI JSON (BANKED suite sink (c) via `twclient`). | Spectators/status consumers see daemon JSON; transcript-only proof is insufficient. | Fold into MT-02 or `tests/test_ensure_login_error_redaction.py` | **P1** | credentials-landed tip + LOGIN-REHAB | Force `returning_password_rejected` / malformed secrets through `ensure_raw` / dispatch; sentinel absent from returned dict + printed JSON. |
| MT-08 | **Secrets-store failure paths for login (not launcher profiles)** — `test_credentials_store_honesty` covers launcher profiles/servers; `test_credentials.py` BANKED (`pytest.ini`). Hub LOGIN-REHAB brief wants: rejected password · malformed secrets · non-UTF-8 secrets bytes · unreadable secrets with sentinel absent. | Distinct from launcher crash WO; password path still thin on secrets fail. | Part of MT-02 / LOGIN-REHAB create-wave | **P1** | CC LOGIN-REHAB | Each secrets failure mode: no crash with cleartext in stderr/return; sentinel absent. |
| MT-09 | **Settle-nudge `send_request("read")` result discarded** — SESSION-F1-MICRO-SETTLE-NUDGE. Prior row claimed **"Benign today; silent if nudge starts mattering"** — that claim is **stale and was wrong**. Live post-stop re-ensure (`twgs.microblaster.net`) proved the discarded not-ready (`empty_response`) preceded the same failure on the real `ensure` call. Product **reversed** at `61bdea2` (WO-ENSURE-SPAWN-READINESS): settle `read` is checked/retried, not discarded. | Was silent misreport of a local startup race as remote connect failure; **closed in product** at `61bdea2`. | `tests/test_ensure_spawn_readiness.py` + `tests/test_cli_attach_settle_nudge.py` (corrected; no longer claims discard is inconsequential) | **DONE** (docs amend) | — | Pins: one transient nudge hiccup still reaches successful ensure; never-ready spawn reports `spawn_failed`, not `empty_response`. |
| MT-10 | **Socket peer-cred / uid gate absent** — `test_daemon_socket_mode.py` explicitly defers `SO_PEERCRED` / `getpeereid` (mode-only WO). Mode 0600 ≠ "only this uid may drive". | Shared-host residual after mode fix. | Future `tests/test_daemon_socket_peercred.py` | **P2** | platform fork + product WO (not invented here) | On supporting platform: foreign-uid connect refused; owner connect ok. |
| MT-11 | **`classify.py` adversarial audit + companions open** — unit suite is already large; do not invent mass classify tests this wave. Report: `audit/session-classify-audit-coverage-20260726.md`. | False "session audited" claim / leftover MT wording. | Targeted WOs from report (C-01…C-06); companion audits | **P2** | `WO-SESSION-CLASSIFY-AUDIT-COVERAGE` (report) → follow-ons | Prior "only secret-prompt tested" claim **retracted**. |
| MT-12 | **`cli.py` module docstring claims `tw watch` is the sole lifetime-stream exception** — SESSION-F1-MICRO-DOCSTRING; attach also holds a socket. No test (docs). | Operator/docs drift. | Docs tip (not pytest) | **P2** | docs-only | One-line docstring fix on origin; no product behavior. |

---

## Non-gaps / closed since DUP-POINTLESS

| Was hole | Reality at `a7e66c1` / `879280f` |
|---|---|
| Scripted `tw attach --keys <unencodable>` | **CLOSED** — `test_cli_attach_keys_encoding.py::test_a_raw_character_the_wire_cannot_carry_is_refused_not_mangled` (+ surrogate recovery). Interactive suite still `keys=None` by design. |
| UTF-8 cockpit getch truncated-lead / ungetch | **CLOSED** — `test_cockpit_utf8_getch.py` 7/7 on origin `879280f`. |
| G3 loops empty-vs-unreadable | **Covered** — `test_cli_loops.py` + `test_loops_store.py` (do not re-open). |
| Player-bank unreadable≠empty | **Covered** — `test_player_bank.py` honesty cases. |
| F5 type-name-only wire | **Covered** — `test_daemon_internal_error_typename.py`. |
| Daemon socket mode 0600 | **Covered** — `test_daemon_socket_mode.py` (peercred remains MT-10). |
| Attach interactive send-bool / keydrop | **Covered** — dedicated honesty suites; keep pins. |

---

## Suggested create-wave order (after hub triage)

1. **MT-01** attach-redaction fail-path (this seat · already HANDOFF'd as attach-redaction-fail)  
2. **MT-03 + MT-04** status/watch honesty (product tips if still BANKED → then tests)  
3. **MT-06** help ASCII inventory (cheap pin while Max rules MT-05)  
4. **MT-02 / MT-07 / MT-08** → CC LOGIN-REHAB wave (Cursor does not steal)  
5. **MT-05** after Max ruling  
6. Catalog catch-up remains docs-parallel (not a missing-*test* gap)

---

## Accept / Proof (this WO)

- Report path: `workorders/AUDIT-MISSING-TESTS.md`
- ≥10 concrete gaps with falsifiable P0 Accepts (MT-01..03)
- Zero mass test adds this WO · zero `pytest.ini` change
- Push waits Accept · hub triage → create HANDOFFs

## Refs

- HANDOFF `@ 2026-07-25T15:27:10Z`
- `workorders/AUDIT-TEST-SUITE-DUP-POINTLESS.md` (context only)
- `canon/findings.md` SESSION-F7/F8 · LOGIN-REDACTION · ASCII residual (banked this tip)
- Origin tip at audit: `a7e66c1` · UTF-8 CLOSED `879280f`
