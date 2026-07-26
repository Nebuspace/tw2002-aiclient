# Session / classify honesty audit — 2026-07-26

**WO:** `WO-SESSION-CLASSIFY-AUDIT-COVERAGE`  
**Seat:** `impl-aiclient-cursor`  
**Tree tip at audit:** `924cfaa` (`origin/main` / worktree `wo/SESSION-CLASSIFY-AUDIT`)  
**Mode:** READ-ONLY — no product invent in this tip  
**Surfaces:** `tw2002_aiclient/session/classify.py` end-to-end; companions named in findings
(`credentials` · `env` · `iac` · `terminal` · `player_bank`) scoped with honest gaps

---

## Verdict (do not inherit a false "session audited" claim)

| Claim people might inherit | Honest status at this tip |
|---|---|
| "`classify.py` is unaudited / only secret-prompt tests exist" | **STALE.** Module is ~991 lines with a large `tests/test_classify.py` (gates, game_select variants, CIM exclusivity, money_prompt / NEVER_AUTO_ACTION, fixtures, secret-prompt). The *prior* findings/MT-11 wording overstated the test gap. |
| "`classify.py` has been adversarial-audited for every consumer contract" | **FALSE.** Tests are strong; this report is the first dedicated honesty pass. Residual defects below are real. |
| "session/ is fully audited" | **FALSE.** Companions below are **not** end-to-end audited here — listed as scoped-next. |
| "NEVER_AUTO_ACTION is enforced everywhere that can send" | **PARTIAL.** Honoured by `menu/crawler.py` and `loops/player.py`. Guardian / graceful-quit use a `main_command`-only whitelist (fail-closed for money). Taught-rule / cockpit fire paths still need an explicit consumer pin check (suggested WO). |

**Bottom line:** classify is **test-rich but not audit-closed**. Companions remain **open**. Do not close SESSION-AUDIT-COVERAGE-GAP / MT-11 as "done" beyond "classify report exists + known residuals banked."

---

## `classify.py` — covered end-to-end

### Architecture (as shipped)

- **Gate anchors** (`_GATE_ANCHORS`, ~749–805): evaluated against the **current prompt line** in `classify_screen` (stale-body poison fix). Order is load-bearing (`computer` before `main_command`; `money_prompt` last among gates).
- **Content anchors** (`_CONTENT_ANCHORS`, ~807–824): full-screen; system-block titles first.
- **Special pre-passes:** `cim_report`, boxed/banner/`plain_timed_out` `game_select` (screen path).
- **Prohibition set:** `NEVER_AUTO_ACTION_CLASSES = {"money_prompt"}` with import-time subset assert (~857–862).
- **Separate fail-safe:** `is_probable_secret_prompt` (~871–909) — attach keystroke redaction only; deliberately broader than `login_password`.

### What is already in good shape

- Gate-vs-content split + docstring rationale match live stalls (pause leftover, warp_confirm, computer⊃main_command).
- Game-select structural checks (boxed / banner / timed-out) + adversarial bleed tests.
- CIM / StarDock block exclusivity discipline.
- Money-prompt last-among-gates + crawler/loop halt derivation from the frozenset (not a restated string).
- Secret-prompt residual honestly documented in-code (no-keyword / non-English prompts).

### Defects / honesty gaps (file:line · severity · suggested WO)

| ID | Location | Severity | Finding | Suggested WO title |
|---|---|---|---|---|
| C-01 | `classify.py:912–943` vs `:946–990` | **MED** | `classify()` (whole-text) does **not** call `_is_plain_timed_out_game_select`; `classify_screen` does. Live path uses `Session.classify()` → `classify_screen`, but any caller of bare `classify()` (tests / one-offs / future) can diverge on Timed Out + Select-a-game shapes. | `WO-CLASSIFY-API-PARITY-PLAIN-TIMEOUT` |
| C-02 | `classify.py:751` | **MED** | `login_password` gate is bare `password` substring. Drives login automaton decisions (unlike `is_probable_secret_prompt`). Help/utility prompt lines containing the word can steal the class if they are the active prompt. | `WO-CLASSIFY-LOGIN-PASSWORD-NARROW` |
| C-03 | `classify.py:750` | **LOW** | `pause_key` includes `press\s+.*\bkey\b` — broad; risk of claiming unrelated "press … key" chrome as a gate when it is the prompt line. | `WO-CLASSIFY-PAUSE-KEY-NARROW` (bank; only if live false positive) |
| C-04 | `classify.py:818–822` | **LOW** | `port_trade` keyword OR (`fuel ore` / `organics` / `equipment` / …) is loose content identity — acceptable for teachable labeling but easy over-claim vs `unknown`. | `WO-CLASSIFY-PORT-TRADE-TIGHTEN` (evidence-gated) |
| C-05 | `classify.py:714–722` | **INFO** | Deliberate non-claim of `Your offer [N]?` (auto-haggle ownership). Collision is documented, not resolved — keep escalated in DECISIONS, do not "fix" by claiming here. | (none — preserve) |
| C-06 | Consumers of `NEVER_AUTO_ACTION_CLASSES` | **MED** | Pin enforced in `menu/crawler.py` (~400) and `loops/player.py` (~782). No import in cockpit taught-rule / arm fire path under this skim. Guardian (`guardian.py:192–194`) and quit (`daemon.py:371`) are `main_command`-only (safe for money by omission). **Missing:** an assert/test that every app sender that keys off classification either whitelists `main_command` or intersects `NEVER_AUTO_ACTION_CLASSES`. | `WO-NEVER-AUTO-ACTION-CONSUMER-AUDIT` |
| C-07 | Findings / MT-11 prose | **MED (meta)** | Row still says "`classify.py` (634 lines) unaudited except secret-prompt regex" — line count and test claim are both stale. Closing the *coverage* finding without updating the *wording* would re-poison the next reader. | this WO (stamp below) |

### Test-map honesty (MT-11 correction)

`AUDIT-MISSING-TESTS.md` MT-11 said only the secret-prompt regex was heavily exercised. At this tip that is **wrong**: `tests/test_classify.py` covers the returnable vocabulary extensively. MT-11 should be restated as **"adversarial audit + companion coverage open; classify unit suite already large"** — not "add mass classify tests this wave."

---

## Companions — scoped next (honest gaps)

Read enough to know what each owns; **not** a Cipher/Mack pass.

| Module | Role (skim) | Gap / risk | Suggested follow-on |
|---|---|---|---|
| `credentials.py` (~786 lines) | Profile/server TOML + `secrets.json` / env password resolution; never writes passwords | Security-sensitive: path overrides (`TW_CONFIG_DIR`), store failure taxonomy, env-first password | `WO-AUDIT-SESSION-CREDENTIALS` (Cipher-led) |
| `env.py` (~424+ lines) | dotenv load, host/port resolution, run-dir / socket / pid paths | Config injection / override precedence; DotenvUnreadable honesty | `WO-AUDIT-SESSION-ENV` |
| `iac.py` (~154 lines) | Hand-rolled telnet IAC state machine (py3.13+ no telnetlib) | Split-packet IAC, option negotiation completeness vs TWGS | `WO-AUDIT-SESSION-IAC` (+ fuzz if warranted) |
| `terminal.py` | `TerminalScreen` (pyte), locale init, glyph set | Encoding / glyph / locale edge cases (related to CLI ASCII choke banked elsewhere) | `WO-AUDIT-SESSION-TERMINAL` |
| `player_bank.py` | Metadata-only rotation bank; `BankUnreadable` honesty contract already in-module | Prior WO-AUDIT-PLAYER-BANK-STORE-HONESTY landed the failure taxonomy; still not a full threat audit | Spot-check only unless new bank features land |

---

## Suggested WO queue (priority)

1. **P1** `WO-NEVER-AUTO-ACTION-CONSUMER-AUDIT` — prove every send path that uses classification refuses `money_prompt` (whitelist or frozenset).
2. **P2** `WO-CLASSIFY-API-PARITY-PLAIN-TIMEOUT` — align `classify()` pre-pass with `classify_screen` or document + lint "live path must use classify_screen."
3. **P2** `WO-CLASSIFY-LOGIN-PASSWORD-NARROW` — tighten gate without breaking login automaton fixtures.
4. **P2** `WO-AUDIT-SESSION-CREDENTIALS` — Cipher.
5. **P3** env / iac / terminal companion audits as capacity allows.

---

## Out of scope (per WO)

- Implementing any of the above fixes in this tip  
- Inventing classify vocabulary / screen_class expansions  
- CC TUI / `suite.yml` / pytest.ini
