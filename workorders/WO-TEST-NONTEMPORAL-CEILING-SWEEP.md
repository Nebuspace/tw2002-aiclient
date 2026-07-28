# WO-TEST-NONTEMPORAL-CEILING-SWEEP

**Goal:** Mirror of #188 for **ceilings** (`<=` / `<`): find count/size/ratio bounds so *generous* that growth (or the bad direction) cannot cross them — vacuous ceilings rather than vacuous floors.

**Context:** #188 measured 57 non-temporal floors; ceilings were enumerated but not individually measured. Same instrument defects to avoid (token-boundary exclusions; purge `__pycache__` + `.pytest_cache` per mutation; md5-restore).

**Deliverable:** Sweep report (STATUS and/or appendix on this WO) with measured quantity per ceiling site, disposition KEEP / BANK-FIX / FIXED-inline-if-trivial. Bank fix WOs for real defects. **No product code** unless a one-line test fix is Accept-complete.

**Accept:**
1. Report covering non-temporal ceilings in `tests/`.
2. Each suspect: measured value, bound, what silent growth/miss looks like, disposition.
3. live-prove `n/a` (docs/test measurement).

**Refs:** #188 appendix · CC CLAIM 20:10:20Z.

---

## Findings — ceilings sweep (impl-claudecode-aiclient, 2026-07-28)

**19 ceiling sites** measured by the #188 method inverted: mutate the bound to an
unreachable **negative** value (`-1e9`), run that test alone, read the real quantity
out of the failure. **All 19 reddened** (no dead sites), **all restored md5-identical**,
throwaway copy — the lane was never mutated. Caches purged per run, per #188's lesson.

**The ceilings axis is materially cleaner than the floors axis, and the reason is
structural:** a ceiling in this suite almost always encodes a *contract* — a terminal
width, a frame edge, an ASCII range — and a contract is correct at any actual value
below it. A floor, by contrast, is often a *proxy* for "the process ran", and a proxy
must be sized to its population. Headroom is therefore expected on ceilings and is not
evidence of anything by itself.

| bound | actual | site | disposition |
|---|---|---|---|
| `<= 80` | 32 / 32 / 9 / 13 | `test_cockpit_strip.py:33/50/97/150` | **KEEP** — 80 is the *terminal-width contract*; output growing to 79 is legal, not a regression |
| `<= 3` | 3 | `test_coach_engine.py:263` | KEEP (exact) |
| `<= 1` | 0 / 1 | `test_cockpit_spectate.py:830/928` | KEEP — the XOR "App and MANUAL never co-render" |
| `<= 5` | 5 | `test_cockpit_strip.py:229` | KEEP (exact) |
| `<= 1` | 1 | `test_secrets_store_redaction.py:485` | KEEP (exact) |
| `< 200` | **78 worst case** | `test_secrets_store_redaction.py:483` | **BANK-FIX (low)** — below |

Nine sites are domain/geometry constants whose value the harness could not auto-extract
and which were read by hand: `<= 159` / `<= 39` (the 160×40 frame's inner inset),
`< 128` (ASCII by definition), `< 758` (the haggle sell-side baseline, the mirror of the
`> 2214` buy-side floor), `<= 22` / `<= 40` (menu-map view widths), `< 500` (trade qty
cap), `<= 1` (`result.steps`), `<= 12` (coach line width). Each is the requirement
itself. **KEEP, all nine.**

### The one finding — `tests/test_secrets_store_redaction.py:483` · BANK-FIX (low)

`assert len(rendered) < 200, f"str() grew a window: {rendered!r}"`

*Intent:* a **backstop**. The load-bearing assert is the line above it
(`SENTINEL not in rendered`); this one exists to catch a future Python that renders a
*window* of the offending buffer rather than a single byte.

*Measured across all 16 parametrizations* (8 damage kinds × 2 arrangements): the worst
real rendering is **78 chars**. The bound is **200** — **2.6× the worst real value**,
122 characters of headroom.

*What that costs:* the largest buffer under test is 42 bytes, so a future Python
rendering the **entire buffer** as a window would produce roughly 78 + 42 = **120
chars — comfortably under 200**. The ceiling cannot fire on total disclosure.

*Why this is LOW and not a leak:* that same total-disclosure case **is** caught, by the
sentinel identity assert on the line above — a full-buffer window necessarily contains
the sentinel. The ceiling's *unique* contribution is confined to windows that exclude
the sentinel, which by construction disclose no sentinel. So the guard is redundant
where it works and blind where it would have been novel.

*Fix to bank:* size the bound against the measured worst case (78) with a modest
margin — ~120 — so the backstop can actually fire on a rendered window. Do **not**
remove it: sized correctly it is cheap insurance on a secrets surface, and #185's rule
cuts both ways — a bound that cannot fire is the same defect as one that fires wrongly.
Note the third arrangement (damage *inside* the sentinel) is deliberately excluded by
the test's own docstring, so a **split** sentinel is not covered by the identity assert
either — which is precisely the case a correctly-sized length backstop would cover.
