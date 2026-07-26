---
type: Reference
title: TW2002 Screen Patterns — Classifier & Settle Evidence
description: Extracted interoperability patterns for classify and settle — block titles, quantity prompts, prompt-line settle scope, missing gate classes, and what not to mine — required reading before building those lanes.
tags: [research, classify, settle, screen-patterns, interop, evidence, required-reading]
timestamp: 2026-07-25T21:40:00Z
---

This concept is the **prescriptive pattern extract** from the 2026-07-25 ClassicTW helper
pass and TWGS-binary mining pass. It is **not** a code import and not a dump of forum or
installer text. Quoted strings are short functional literals — the minimum needed to
recognise a screen shape.

Implementers building [Screen Understanding](/engine/screen-understanding.md),
[Settle Detection](/architecture/settle-detection.md), or classify/settle product tips
**must read this before coding**. Product Accept bars still live in those owning concepts;
this document is the evidence catalog and hazard list they must not rediscover cold.

Corpus (binaries, forum HTML) stays gitignored under `research/raw/` — never commit it.
Method notes and dead ends are retired; only **useful patterns** remain here.

# Schema

## Pattern catalog (priority order)

| ID | Pattern | Lane | Priority | Status vs tree (2026-07-25) |
|---|---|---|---|---|
| P-BLOCK | `-=-=- <Title> -=-=-` / `End of …` report-block delimiter | classify | P0 | Only CIM Port Report hardcoded; ≥14 titles in fixtures |
| P-QTY | Quantity prompts with bracketed **range** vs **default** | classify + safety | P0 | StarDock holds → `unknown`; no StarDock classify tests |
| P-SETTLE-LINE | `wait_prompt` must scope to **current prompt line**, not whole screen | settle | P0 | Gate classify already prompt-line; settle still whole-screen `render_text()` |
| P-SUPPRESS | Server may disable interactive sub-prompts | settle | P1 | Document; timeout-only waits hang meaninglessly |
| P-GATES | Planet / Citadel / StarDock / Tavern gate classes | classify | P1 | Absent as `screen_class` gates (Planet step exists only in login) |
| P-PORT-MASK | `port_trade` never wins on docked-port **display** | classify | P1 | Content anchor loses to `main_command` on prompt line |
| P-BANNER | TWGS edition tiers may differ; banner conjunction is brittle | classify | P1 | Hypothesis — do **not** widen regex without live banner capture |
| P-BEEN | `been_on_today` known to login, `unknown` to classify | classify | P2 | Split-brain |
| P-EVENTS | Probe/event vocabulary checklist; do not copy punctuation-stripped triggers | classify | P2 | Future anchors |
| P-ANSI | In-game ANSI toggle changes the byte stream | classify | P2 | Player-controllable classifier input |

## P-BLOCK — general `-=-=-` block-title anchor

TW2002 brackets system-generated report blocks:

```
-=-=-        <Title>        -=-=-
...
-=-=-        End of <Title>        -=-=-
```

**Do:** generalise the CIM-only header/footer regexes into a **block-title extractor**;
reuse the exclusivity discipline (nothing but blanks/command-echo around the block —
same idea as genuine CIM report trust).

**Do not:** require header title == footer title. Example asymmetry already in fixtures:
`StarDock Shipyard - Cargo Hold Upgrade` closes with `End of Cargo Hold Upgrade Quote`.
Match the delimiter; treat the title as free text.

Fixture titles already present include Docking Log, Density & Holographic Scanners,
Special Devices & Ordnance, StarDock Shipyard cargo/ship registration, TransWarp Drive
Installation, and multiple `End of … Listing` footers.

## P-QTY — quantity prompts (range hint ≠ Enter default)

Real captured purchase screen `stardock_cargo_hold_quote.txt` classifies as `unknown`:

> `How many holds would you like to buy [0-20] ?`

- Bracketed **`[0-20]`** is a **range hint**, not a default Enter accepts.
- Other quantity prompts use bracketed **defaults** (`[12]`, `[100]`) that Enter accepts.
- Conflating the two is how empty Enter buys the wrong amount (same hazard class as
  settle's documented auto-taken colonist / auto-given cargo scars).

**Do:** recognise quantity-prompt shapes; distinguish range vs default in any parser or UI.

**Do not:** auto-answer quantity / money screens from the app. Refuse / escalate —
trainer sovereignty. Vocab labels for new `screen_class` values remain Max-gated when
the closed vocabulary must expand (see [screen-understanding](/engine/screen-understanding.md)).

Anchor probe (research day): holds `[0-20]` and fighters deploy `[100]?` matched **no**
anchors; Fuel Ore buy `[12]?` matched `port_trade` only.

## P-SETTLE-LINE — prompt-line-scoped settle (TWX lesson)

Community TWX lore: `waitOn` yields a valid current line; raw `waitFor` does not —
stale buffer matches are the classic failure.

Our classify layer already matches **gate** anchors against the current prompt line
because pyte leaves stale cells. Settle's `wait_prompt` historically searched
`session.render_text()` (whole screen). **New bytes since send do not prove the match
is on new content** — a stale copy of the target text elsewhere on the grid still hits.

**Do:** scope prompt-settle matches through `session.current_prompt_line()` (or equivalent
prompt-line API). Keep `rx_count` / freshness guards; they are necessary but not sufficient.

**Do not:** treat whole-screen regex success as proof the *live* prompt matched.

**Ruled (Max carte blanche → hub 2026-07-26):** settle-detection owns readiness / default
`match_scope` for drive verbs; screen-understanding owns identity only. See `DECISIONS.md`
§D under "Max carte blanche parked gates."

## P-SUPPRESS — missing prompts are a legitimate server state

A server can turn interactive sub-prompts off. Paths that **only** stop on `wait_prompt`
will hang to full timeout instead of failing meaningfully. Combine with idle/timeout
reasons; document prompt-absence as expected on some hosts.

## P-GATES — missing mature bot prompt classes

Mature community bots distinguish (among others) Planet/Citadel, StarDock, and Tavern
prompts. We handle Command and Computer; Port is present but masked (P-PORT-MASK).
Planet command exists as a **login step** regex but not as a classifier gate — split-brain.

**Do:** when adding gates, follow gate-vs-content discipline (prompt line only).

**Do not:** invent closed-vocab `screen_class` labels without Max GO when the vocabulary
is fixed in screen-understanding.

## P-PORT-MASK — docked port display ≠ `port_trade`

`port_trade` is a **content** anchor and runs only after gates fail. Docked-port screens
end in `Command [TL=…]`, so `main_command` wins. Empirically `port_trade_screen.txt` →
`main_command`. `port_trade` still fires on mid-trade quantity lines (e.g. Fuel Ore buy).

**Do not** assume `port_trade` means "I am docked at a port display."

## P-BANNER — TWGS edition names (hypothesis only)

Installer product strings name three editions (full / Lite / Unregistered). Our
`game_select` banner check is a hard multi-signal conjunction; title regex may not
tolerate `2002` between "Wars" and "Game".

**Honest framing:** those strings are Windows product/registry names, **not** observed
telnet banners. Only captured banner `TradeWars Game Server` is proven.

**Do:** capture banners empirically from small listed servers before widening regexes.

**Do not:** loosen exclusivity/conjunction on installer inference alone — that conjunction
defends against stale-scrollback misfires.

## P-BEEN / P-EVENTS / P-ANSI (P2 checklist)

- Promote `been_on_today` login regex to a classify gate when scheduled (P2).
- Probe event names (`ProbeDestroyed`, …) are a **checklist**; other tools strip
  punctuation — do not copy their stripped forms as our anchors.
- In-game Computer-menu ANSI toggle changes the byte stream — treat as
  player-controllable classifier input.

# Negative results (do not waste cycles)

1. **TWGS 2.20b downloadable `.EXE` / Tools zip are installers**, not game-text carriers.
   Player-visible prompts are inside compressed InstallShield payloads. String dumps of
   readable installer binaries yield **no** TW domain prompts. **Do not re-mine these
   installers.**
2. Host-admin / registry / InstallShield chrome is **never** player-visible — not
   classifier input.
3. Reaching installed `TWGS.EXE` game modules needs Windows + its own WO; live capture of
   *rendered* screens is higher value for classify than mining format strings.

# Explicit non-patterns (noise)

Skip as classifier/settle work: TWX/SWATH *tool* UIs and system variables; Manual-forum
strategy prose (low prompt yield); reversing commercially obfuscated helper scripts —
use unobfuscated/public sources and live captures instead.

# Examples

| Fixture / prompt | Observed class | Pattern |
|---|---|---|
| `stardock_cargo_hold_quote.txt` | `unknown` | P-QTY |
| `been_on_today_reenter_screen.txt` | `unknown` | P-BEEN |
| `port_trade_screen.txt` | `main_command` | P-PORT-MASK |
| `stardock_equipment_listing.txt` | `main_command` | (listing under command) |
| `How many holds of Fuel Ore… [12]?` | `port_trade` | P-QTY default shape |

# Citations

- Source extracts: ClassicTW Helpers & Scripts / Manual forum sample (2026-07-25);
  TWGS 2.20b installer string mining (negative result).
- Owning product concepts: [screen-understanding](/engine/screen-understanding.md),
  [settle-detection](/architecture/settle-detection.md),
  [login-automaton](/architecture/login-automaton.md),
  [action-safety-guards](/doctrine/action-safety-guards.md).
- Related parked product: `WO-CLASSIFY-BLOCK-TITLES` (P-BLOCK / P-QTY vocab + money-screen Max gates).
