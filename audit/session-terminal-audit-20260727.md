# Honesty audit — `tw2002_aiclient/session/terminal.py`

**Seat:** `impl-aiclient-cursor` · **Tip audited:** `wo/AUDIT-SESSION-TERMINAL` `f96d68b` · **Mode:** READ-ONLY, no product change
**WO:** `WO-AUDIT-SESSION-TERMINAL` · **Companion to:** `audit/session-iac-audit-20260727.md`, `audit/session-env-audit-20260726.md`
**Method:** read `terminal.py` end-to-end; grep callers/tests; **execute** decode/locale/glyph probes against the live module (CPython 3.14.6 · `sys.flags.utf8_mode == 1`). Where a probe found nothing, that is stated too.

---

## Summary

`terminal.py` is 161 lines and does two jobs that have **diverged in honesty**:

1. **Game-byte decode (`TerminalScreen.feed`)** — the CP437 claim is **true** and pinned. Codec claimed == codec applied. No `errors='replace'|'ignore'`. Clean under every WO category that touches the wire→pyte path.
2. **Chrome locale / glyph switch (`init_locale` / `glyph_set` / `GLYPHS_*`)** — the **docstring story is stale relative to the live TUI**. Canon and this module still present `init_locale()` → `unicode_ok` → `glyph_set()` as the single chrome switch. Product chrome does **not** call either function; it uses `cockpit.draw.unicode_ok()` (`TW2002_ASCII=1` only). The locale probe that remains would also return `True` under a bare `C` locale whenever PEP 540 UTF-8 mode is on — so even if rewired, it would not answer "can this terminal draw Unicode?"

| # | Surface | Severity | Status |
|---|---|---|---|
| T-01 | `init_locale` / `glyph_set` / `GLYPHS_*` are orphaned chrome; live `unicode_ok` ignores locale | **MED** | defect (cross-module + canon drift) |
| T-02 | `init_locale`'s preferred-encoding probe is blind under PEP 540 UTF-8 mode | **MED** (latent — only bites if T-01 is "fixed" by rewiring to `init_locale`) | defect |
| T-03 | Canon still names `terminal.py` as the glyph / `glyph_set()` source of truth | **LOW** | docs↔code |
| T-04 | UTF-8 multibyte bytes fed to `feed()` become silent CP437 mojibake (no validation) | **LOW** | contract gap / latent |
| — | Encoding claim (`cp437`) vs applied codec | — | **probed, clean** |
| — | Silent `errors='replace'|'ignore'` inside `terminal.py` | — | **none found** |
| — | `GLYPHS_ASCII` pure-ASCII / `glyph_set` table switch | — | **probed, clean** (API itself) |
| — | CP437 box-drawing + ANSI colour coexistence | — | **probed, clean** (tests + re-run) |

---

## Category coverage (Accept #2)

| Category | Verdict |
|---|---|
| 1. Encoding / decoding contracts | **Clean** on the live path — see §Encoding. Claimed `cp437` is what `feed` applies. |
| 2. Glyph / control-character handling | **Mixed** — game-art glyphs correct; chrome glyph tables in this file are orphaned (T-01/T-03). C0 controls follow pyte VT semantics (expected; not documented as chrome). |
| 3. Locale / LANG assumptions | **Findings T-01, T-02** — module *has* a locale probe, but nothing product-side calls it; the probe itself is UTF-8-mode-blind. |
| 4. Unicode-ok assertions / flags | **Finding T-01** — `glyph_set(unicode_ok)` is correct *if* the flag is honest; the live flag source is not this module. |
| 5. Silent lossy paths (`errors='replace'|'ignore'`) | **None found** in `terminal.py`. Related latent: T-04 (always-succeeds CP437, not `errors=`). |

---

## T-01 · MED · chrome `unicode_ok` story in this file is orphaned — live TUI never calls `init_locale` / `glyph_set`

`init_locale` (`terminal.py:101-113`) documents:

> Returns True when the resulting locale's preferred encoding is UTF-8 … callers fall back to the plain-ASCII glyph set …

Comment at `:118` and `glyph_set` (`:156-161`) present a single `unicode_ok` flag from `init_locale()` as the chrome switch.

**Measured callers of `init_locale` / `glyph_set` in product code (`tw2002_aiclient/`):**

| Symbol | Product callers | Test / archive-only callers |
|---|---|---|
| `init_locale` | **none** | `tests/test_terminal.py`, `tests/test_pty_helpers_smoke.py`, `tests/test_spectate_app.py` (still imports `twclient`) |
| `glyph_set` | **none** | `tests/test_terminal.py` only |
| `TerminalScreen` | `session/session.py:34,76,235` (live) | many |

Live chrome switches on `cockpit.draw.unicode_ok()` (`draw.py:124-127`) — env flag only:

```python
return os.environ.get("TW2002_ASCII", "").strip() != "1"
```

`screens._unicode_ok` is an explicit thin delegate onto that (`screens.py:239-249`), after **WO-AUDIT-UNICODE-OK-DOCSTRING** retired a *false* locale claim there. The locale probe was not moved to draw — it was abandoned for the live path, and **left behind** in `terminal.py` with docs that still speak as if callers exist.

`session.py` imports **only** `TerminalScreen` — not `init_locale`, not `glyph_set`.

**Why MED:** an operator (or a future WO author) reading this module + `canon/surfaces/visual-language.md` will believe locale gates chrome. On a bare ASCII/`C` locale **without** `TW2002_ASCII=1`, the live cockpit still selects Unicode box-drawing / braille spinner glyphs. That is the exact "implicit UTF-8 that breaks on ASCII locale" failure mode this WO names — and the failure lives in the **disconnect**, not in `feed()`.

**Suggested follow-on:** `WO-TERMINAL-CHROME-ORPHAN-RETIRE` — either (a) delete/relocate `init_locale`+`glyph_set`+`GLYPHS_*` out of the session emulator module and point canon at `cockpit.draw` / liveness/hud tables, or (b) make the live TUI call one real probe *and* keep env override. Do not "fix" by wiring `init_locale` alone without T-02.

---

## T-02 · MED (latent) · `init_locale` returns True under `C` when PEP 540 UTF-8 mode is on — `terminal.py:111-113`

```python
locale.setlocale(locale.LC_ALL, "")
encoding = locale.getpreferredencoding().lower()
return "utf-8" in encoding or "utf8" in encoding
```

Probed on the audit host (CPython 3.14.6, `sys.flags.utf8_mode == 1`):

```
locale.setlocale(LC_ALL, "C")
locale.getpreferredencoding(False)  ->  'utf-8'
# ⇒ init_locale body would return True
```

Monkeypatch confirms the substring check itself:

```
preferred='ANSI_X3.4-1968' -> False
preferred='UTF-8' / 'utf8'   -> True
preferred='ISO8859-1'        -> False
```

So the function is **internally consistent** with its docstring, and **wrong as a capability probe** on modern CPython defaults: UTF-8 mode makes `getpreferredencoding()` report UTF-8 even when the process locale is `C`. Same shape already banked for CLI stdout as `CLI-ASCII-WRITE-CHOKE` / `WO-AUDIT-CLI-ASCII-WRITE-CHOKE` in `canon/findings.md`.

**Severity is MED-latent:** today nothing product-side calls this. It becomes load-bearing the moment T-01 option (b) rewires chrome to `init_locale`.

**Suggested follow-on:** fold into `WO-TERMINAL-CHROME-ORPHAN-RETIRE` — if a locale probe is kept, it must not trust `getpreferredencoding()` alone under UTF-8 mode (e.g. require explicit `TW2002_ASCII`, or probe an actual encode of a chrome glyph against the curses/stdout encoding). Cross-link the CLI ASCII choke WO; do not invent a second divergent policy.

---

## T-03 · LOW · canon still attributes the glyph tables to `terminal.py`

`canon/surfaces/visual-language.md:132-161`:

> Two parallel glyph tables — `GLYPHS_UNICODE` / `GLYPHS_ASCII` (`terminal.py`) — switch on a single `unicode_ok` flag via `glyph_set()` …

> `terminal.py` defines a deliberate **two-weight** border system …

Live borders / thin glyphs are drawn from `cockpit.draw.DOUBLE_*` / `THIN_*` (`draw.py:103-121`); spinner/heartbeat live in `cockpit/liveness.py:110-119` (comment admits "ported verbatim from the archive's `terminal.py`"). `terminal.py`'s tables remain, tested, and **unreferenced by product drawers**.

**Docs win:** this is a canon↔code divergence. Default presumption: update canon (and/or retire the dead tables) rather than silently accepting dual sources.

**Suggested follow-on:** same `WO-TERMINAL-CHROME-ORPHAN-RETIRE` (docs half), or a docs-only slice `WO-CANON-GLYPH-SOURCE-OF-TRUTH` if product retire is deferred.

---

## T-04 · LOW · always-succeeds CP437 means wrong-charset input is silent mojibake — `terminal.py:28`

```python
self.stream.feed(data.decode("cp437"))
```

CP437 maps every byte `0x00–0xFF` to exactly one code point. Probed: all 256 values decode under **strict** (no `errors=` needed, none present).

Consequence: if UTF-8 multibyte ever reached `feed()`, there is **no exception** — only wrong glyphs:

```
"╔".encode("utf-8") == bytes([0xE2, 0x95, 0x94])
feed(those bytes) -> render_cropped() == ['Γòö']   # CP437 reading of UTF-8
```

The module docstring correctly states the **intended** contract (IAC-stripped DOS/TWGS bytes). `connection.py` feeds IAC-clean socket bytes into `terminal.feed` — that path matches. This finding is only that the function does not *defend* the contract; a mistaken UTF-8 producer would look "successful."

**No follow-on required unless** a second producer of `TerminalScreen.feed` appears that might speak UTF-8. Optional pin: document "caller must not pass UTF-8 multibyte" next to the decode line (docs-only).

---

## Encoding — probed, clean (category 1)

| Claim (`feed` docstring `:15-26`) | Applied (`:28`) | Probe |
|---|---|---|
| Decode as CP437, not UTF-8 | `data.decode("cp437")` | box bytes `C9 CD BB` → `╔═╗` |
| Avoid `pyte.ByteStream` UTF-8 default | constructs `pyte.Stream` (`:13`), feeds **str** | `ByteStream.__init__` still installs `utf-8` incremental decoder with `"replace"` — we do **not** use it |
| Single-byte → safe per-chunk | CP437 length == byte length | chunk-boundary claim holds |
| ANSI/VT `<0x80` identical under cp437/ASCII | decode identity for `0x00–0x7F` | true for *decode*; display of C0 is pyte's job (BEL dropped, BS backspaces — probed) |

Canon `session-engine.md:116-118` matches this path.

Pins: `tests/test_terminal.py` (`test_cp437_box_drawing_bytes_decode_to_unicode`, `test_ansi_color_sequences_still_work_alongside_cp437_bytes`); 19/19 green on this tip.

Outbound TX encoding is **out of scope** for this file but noted for contrast: `connection.send_text` uses `text.encode("utf-8")` **strict** (`connection.py:311-314`) — never silent-replace. Good neighbor, different direction.

---

## Glyph / control-character — category 2 detail

**Game art (in scope of `feed`):** high bytes `0xB0–0xDF` etc. decode to the intended Unicode box/shade glyphs (probed `B0/B1/B2/DB/C4/CD`). **Clean.**

**C0 / DEL:** `NUL`/`DEL`/`BEL` do not appear as printable cells; `BS` moves cursor (pyte). Docstring talks about decode identity for control bytes, not display — not a lie, but a reader looking for "control-character handling" will not find a chrome-level policy here. Cockpit write-path neutralization lives in `cockpit.draw._sanitize_controls` (out of this WO's product-edit scope).

**Chrome tables in this file:** key-parity and ASCII purity are pinned (`test_glyph_tables_expose_the_same_keys`, `test_ascii_glyph_table_is_pure_ascii`). The API is fine; the **wiring** is the defect (T-01).

---

## Silent lossy `errors=` — category 5 · none found

AST walk of `terminal.py`: **zero** `errors=` keyword arguments. Substrings `errors='replace'` / `errors='ignore'` are absent.

The only nearby `"replace"` in the dependency surface is **pyte's unused** `ByteStream` UTF-8 decoder (`codecs.getincrementaldecoder("utf-8")("replace")`) — relevant as justification for *not* using `ByteStream`, not as a live lossy path.

---

## Banked follow-on WOs (recommended stubs — not created as files this turn)

| WO id | Target | From |
|---|---|---|
| `WO-TERMINAL-CHROME-ORPHAN-RETIRE` | Retire or rewire `init_locale`/`glyph_set`/`GLYPHS_*`; update `visual-language.md` source-of-truth; decide single `unicode_ok` policy with `draw.unicode_ok` / `TW2002_ASCII` | T-01, T-03, T-02 |
| `WO-CANON-GLYPH-SOURCE-OF-TRUTH` | Docs-only alternative if product retire slips — stop naming `terminal.py` as the live glyph switch | T-03 |
| *(existing)* `WO-AUDIT-CLI-ASCII-WRITE-CHOKE` | Cross-link only — same PEP 540 / ASCII-locale family on CLI stdout | T-02 |

No product fix in this WO. No new test infrastructure.

---

## Note on method

Encoding and locale claims were **executed** (full 256-byte CP437 sweep, box-drawing feed, UTF-8-as-CP437 mojibake, `C` locale preferred-encoding, monkeypatched `init_locale` truth table, `ByteStream` source inspection). Caller orphanhood was produced by ripgrep over `tw2002_aiclient/` plus import audit of `session.py`. A surface marked clean means a probe ran and matched the claim — not that the file "looked fine."
