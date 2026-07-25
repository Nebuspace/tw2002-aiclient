# Helper & Script Pattern Findings (ClassicTW, Leg A)

Research pass mining ClassicTW's *Helpers & Scripts* (`f=15`) and *Manual*
(`f=7`) forums for prompt / menu / screen-state patterns useful to
`tw2002_aiclient/session/classify.py` and the settle layer.

**This is interoperability research, not a code import.** No helper code is
vendored. Quoted strings are short functional prompt literals — the minimum
text needed to *recognise a screen* — not reproductions of anyone's script,
documentation, or manual.

- **Corpus (gitignored):** `research/raw/helpers/` — forum index pages,
  selected topic pages, two publicly-linked attachments.
- **Fetched:** 2026-07-25. Forum reachable, HTTP 200. 1,763 topics / 36 pages
  in `f=15`; 66 topics sampled from `f=7`.
- **Sampled, not exhaustive:** index pages 1–5 of `f=15` (250 topics) plus 16
  targeted topic pages. Topic *titles* below are real; nothing is invented.

---

## Highest-value findings

### 1. The `-=-=-` block convention is a general screen-title anchor (P0)

TW2002 brackets system-generated report blocks with a consistent delimiter:

```
-=-=-        <Title>        -=-=-
...
-=-=-        End of <Title>        -=-=-
```

`classify.py` hardcodes exactly **one** instance of this convention —
`_CIM_REPORT_HEADER_RE` / `_CIM_REPORT_FOOTER_RE` for `Port Report (CIM)` /
`End of Report`. But our own captured fixtures already contain **fourteen**
distinct titles using the same shape, including `Docking Log`,
`Density & Holographic Scanners`, `Special Devices & Ordnance`,
`StarDock Shipyard - Cargo Hold Upgrade`, `StarDock Shipyard - Ship
Registration`, `TransWarp Drive Installation`, and four `End of … Listing`
footers.

Generalising the delimiter into a **block-title extractor** would yield ~10
screen identities we already have live captures for, and the exclusivity
discipline in `_is_genuine_cim_report` (nothing but blanks/command-echo around
the block) is reusable as-is.

**Nuance that will bite a naive implementation:** header and footer titles are
**not** always symmetric. `StarDock Shipyard - Cargo Hold Upgrade` closes with
`End of Cargo Hold Upgrade Quote`. A paired-title equality check would fail;
match the delimiter and treat the title as free text.

### 2. StarDock quantity prompts classify as `unknown` (P0)

Running `classify_screen()` over every fixture in `tests/fixtures/` (see
Verification below) shows `stardock_cargo_hold_quote.txt` — a **real captured
purchase screen** — resolving to `unknown`. Its prompt:

> `How many holds would you like to buy [0-20] ?`

No gate anchor and no content anchor matches. This is a **transaction prompt
with a bracketed range**, and it is exactly the hazard class `settle.py`'s own
module docstring records as bitten live three times (the `-75`-alignment
auto-taken colonist, the auto-given-away cargo). The bracketed `[0-20]` is a
*range hint*, not a default; other TW quantity prompts carry a bracketed
**default** (`[12]`) that Enter accepts — conflating the two is how an empty
Enter buys the wrong amount.

`tests/test_classify.py` currently has **no** StarDock coverage at all.

### 3. Community lore independently validates — and extends — our settle discipline (P0)

The TWX Proxy technical thread (`t=35604`, author reports decompiling the
released Delphi source) documents that TWX's two wait primitives are not
equivalent:

- `waitOn <text>` compiles down to `setTextTrigger` + `pause`.
- `waitFor <text>` is the raw blocking wait.

The stated consequence, twice in-thread and echoed onto the TWX wiki:

> *"You will get a valid `CURRENT_LINE` which doesn't seem to be true for
> `waitFor`."*

— alongside the community adage *"Never ever use 'waitfor', it's bad!"*

**Why this matters to us.** `classify.py` is scrupulous about the distinction:
gate anchors are matched against the **current prompt line**, content anchors
against the **whole screen**, precisely because pyte leaves stale cells the
server never overwrote. `settle.wait_for_settle()` has **no such discipline** —
`settle.py:81` matches `wait_prompt` against `session.render_text()`, the whole
rendered screen:

```python
if prompt_re is not None and prompt_re.search(session.render_text()):
    return "prompt", elapsed
```

`send_and_confirm()` mitigates with a "genuinely new bytes since send"
(`rx_count`) guard — good, and deliberate per its docstring. But **new bytes
arriving does not prove the match is on the new content.** A stale copy of the
target text sitting in an unclaimed grid region satisfies the search regardless
of where the new bytes landed, so a mid-arrival screen can confirm against the
stale copy. That is the same failure TWX's community reached by a different
road twenty years earlier.

The plumbing to fix it already exists: `session.current_prompt_line()`
(`session.py:236`).

### 4. Server config can suppress prompts the client waits for (P1)

From `t=35875`, on why bots send invisible keepalive characters:

> *"a server could have interactive sub-prompts turned off. This in some cases
> would disallow the timeout prompt from being seen."*

A per-server toggle changes **whether a prompt is emitted at all**. Any settle
path whose only stop condition is a `wait_prompt` match will hang to full
timeout on such a server rather than fail meaningfully. Relevant to the
`Timed out…` handling already present in `_selection_prompt_context`.

Related: `t=35202` notes that toggling ANSI in the in-game Computer menu
changes trigger behaviour — i.e. a *player-controllable* setting alters the
byte stream our classifier reads.

### 5. Mombot's prompt taxonomy — our missing screen classes (P1)

The Mombot command list (`t=34704`) enumerates the prompt classes a mature TW
bot distinguishes, as its documented "Start Prompts":

| Community prompt class | Our anchor | Status |
|---|---|---|
| Command Prompt | `main_command` | ✅ handled |
| Computer Prompt | `computer` | ✅ handled (correctly ordered before `main_command`) |
| Port Prompt | `port_trade` | ⚠️ present but masked — see below |
| Planet/Citadel Prompt(s) | — | ❌ absent from `classify.py` |
| StarDock Prompt | — | ❌ absent |
| Tavern prompt | — | ❌ absent |

`Planet command` exists as a *step* regex inside `login.py`, but not as a
classification anchor — the login automaton can recognise a screen the
classifier cannot name.

### 6. `port_trade` is masked on the screen it was written for (P1)

`port_trade` is a **content** anchor, and content anchors run only after gate
anchors have failed against the prompt line. A docked-port screen ends in
`Command [TL=…]`, so `main_command` wins first. Empirically:
`port_trade_screen.txt` → `main_command`, and
`port_commerce_report_gorram_primus.txt` → `main_command`.

`port_trade` is not dead — it fires on mid-trade prompts like *"How many holds
of Fuel Ore do you want to buy"* — but it never fires on the port display
itself. If anything consumes `port_trade` expecting "I am docked", that
assumption is wrong today.

### 7. `been_on_today` split-brain (P2)

`been_on_today_reenter_screen.txt` → `unknown`, yet `login.py:98` carries
`you\s+have\s+been\s+on\s+(?:the\s+game\s+)?today`. Same split-brain as §5: a
screen the automaton handles that the classifier cannot name.

### 8. SWATH's event vocabulary (P2)

`t=35202` documents SWATH's built-in event names — a mature taxonomy of
game events worth recognising, useful as a checklist for future anchors:
`ProbeDestroyed`, `ProbeSelfdestructs`, `ProbeEnteredSector`,
`YouDestroyedProbe`. In-thread caution: SWATH's *text-string* triggers reject
punctuation, so the on-screen text `Probe Destroyed!` had to be matched without
the `!` — a reminder that other tools' anchors may be *punctuation-stripped*
versions of the real screen text, and should not be copied verbatim as ours.

---

## Prioritized table

| # | Pattern | Where seen | Suggested client touch | Priority |
|---|---|---|---|---|
| 1 | `-=-=- <Title> -=-=-` / `End of …` block convention, 14 titles | our own `tests/fixtures/`; corroborated by forum screen talk | `classify.py` — generalise `_CIM_REPORT_*_RE` into a block-title extractor; reuse `_is_genuine_cim_report` exclusivity | **P0** |
| 2 | `How many holds would you like to buy [0-20] ?` → `unknown` | `stardock_cargo_hold_quote.txt` | `classify.py` — quantity-prompt anchor; distinguish range-hint `[0-20]` from default `[12]`. Trainer must refuse to auto-answer | **P0** |
| 3 | `waitFor` vs `waitOn` — no valid `CURRENT_LINE` | `t=35604`, TWX wiki | settle layer — prompt-line-scoped `wait_prompt` via `session.current_prompt_line()` | **P0** |
| 4 | Interactive sub-prompts can be disabled server-side | `t=35875` | canon (settle-detection) + settle — document that prompt-absence is a legitimate server state | **P1** |
| 5 | Citadel / Planet / StarDock / Tavern prompt classes | `t=34704` | `classify.py` — four new gate anchors | **P1** |
| 6 | `port_trade` never fires on the docked-port display | fixture probe | `classify.py` — decide whether port display deserves its own gate anchor | **P1** |
| 7 | `been_on_today` known to `login.py`, `unknown` to classifier | fixture probe | `classify.py` — promote the existing `login.py` regex to an anchor | **P2** |
| 8 | SWATH event taxonomy; punctuation-stripped triggers | `t=35202` | canon — checklist for future anchors; do not copy stripped forms | **P2** |
| 9 | In-game ANSI toggle changes the byte stream | `t=35202` | canon — note as a player-controllable classifier input | **P2** |

---

## What is *not* useful (noise we can skip)

- **TWX/SWATH internals** — `openMenu TWX_DATABASE_SELECT` (`t=35627`), TWX
  version-numbering, script-compiler `ECHO` quoting rules, SWATH registration
  tooling. These describe *those tools'* UIs, not TW2002 screens.
- **TWX system variables** (`LogANSICodes`, `ListeningPort`, `AutoRunScript`,
  `MaxBubbleSize`, …) — proxy configuration, not game text.
- **`f=7` Manual forum** — strategy prose, glossaries, ship/planet type
  primers. Good for *domain vocabulary*, but it explains the game to humans
  rather than transcribing prompts; low yield for anchors. The linked
  `TWGS_References.PDF` is a site/link directory, not prompt documentation.

---

## Deliberately not included

- **`0_Login.cts`** (topic `t=35331`) is the most prompt-dense artifact found —
  a long-maintained login script whose string constants are TW2002's own login
  prompts. It ships **deliberately obfuscated**, and its author sells the
  source. The obfuscation is trivial to reverse. **I did not reverse it and
  have not documented the method.** Interoperability does not require defeating
  a third party's commercial protection, and the same anchors are obtainable
  from unobfuscated sources (the GPL TWX script pack, the public TWX wiki, and
  plain-text forum posts). Flagging the tension rather than resolving it
  unilaterally — if the anchors are wanted, the clean route is the GPL pack.
- **Bulk script/manual text.** No script bodies, no manual sections, no
  glossary reproduced. Only short prompt literals.
- **Attachment sweep.** ~1,763 topics carry many attachments; only two were
  downloaded (the two on topics already selected for prompt value). A full
  sweep is a separate, larger WO and mostly script packs rather than prompt
  documentation.

---

## Verification

Fixture probe — `classify_screen()` over every `tests/fixtures/*.txt`, prompt
line taken as the last non-blank line. Gaps reproduced:

| Fixture | Result |
|---|---|
| `stardock_cargo_hold_quote.txt` | `unknown` |
| `been_on_today_reenter_screen.txt` | `unknown` |
| `port_trade_screen.txt` | `main_command` (not `port_trade`) |
| `stardock_equipment_listing.txt` | `main_command` |
| `stardock_shipyard_listing.txt` | `main_command` |

Anchor probe — quantity-prompt shapes against the full `_ANCHORS` list:

| Prompt | Anchors matched |
|---|---|
| `How many holds would you like to buy [0-20] ?` | none |
| `Enter the number of fighters to deploy [100]?` | none |
| `How many holds of Fuel Ore do you want to buy [12]?` | `port_trade` |

No product code was modified by this research pass.
