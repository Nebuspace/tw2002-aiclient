---
type: System
title: Menu Map & Read-Only Introspection Crawl
description: The per-world menu graph, the safety-critical read-only never-commit crawler that builds it, the read-only game-data introspector and zero-input probe that feed it, and deterministic menu navigation over the map — with every state-changing edge gated exactly like a taught rule.
tags: [engine, menu-map, read-only-crawl, never-commit, introspection, probe, deterministic-nav, per-world, human-invoked]
timestamp: 2026-07-23T20:01:52Z
---

This concept owns the **menu map** of a game world — a per-world directed graph of the
screens the app can navigate between — and the safety-critical, **read-only, never-commit**
machinery that discovers it: a supervised crawler, a text-only game-data introspector, and a
zero-input catalog probe. It also owns **deterministic navigation** over the finished map: given
a known start and a target node, compute a keystroke route and walk it. The map is pure recorded
observation; walking an *action* edge is never automatic — it is gated exactly like a taught rule.

In the reborn contract this is the app learning the *shape* of a world without ever *changing*
that world. Every mechanism here reads and records; none of it buys, sells, attacks, deploys,
confirms, or commits anything. The exploration is **human-invoked** — a supervised discovery run
the operator starts against a disposable character, or a teacher-assisted map-fill — never an
autonomous agent wandering a live account. What it produces is data other layers *read*: the
[Screen Understanding](/engine/screen-understanding.md) signature keys each node, the
[Game-Data Store](/engine/game-data-store.md) receives introspected rows, and a future navigator
localizes and routes over the graph.

# The Menu Map — Nodes, Edges, Per World

The map is a directed graph stored per world:

- **Node** = a menu screen, keyed by its **menu signature** — the short, stable SHA-256 over the
  screen's identifying text (leading/trailing blank lines and trailing per-line whitespace
  normalized away) produced by `menu_sig.menu_signature()`. The signature primitive is owned by
  [Screen Understanding](/engine/screen-understanding.md); this concept owns the graph it keys.
  A node carries its `signature`, a human-readable `label` (the screen's first non-blank line),
  and `first_seen_ts` / `last_seen_ts` stamps. Re-observing a screen stamps a fresh `last_seen_ts`
  and never duplicates the node.
- **Edge** = a keystroke transition `(from_node, key) → to_node`, carrying a `kind` and a `desc`.
  Edges are keyed by the `(from_node, key)` pair: within one world a given key on a given screen
  leads somewhere deterministic, so re-observing that transition updates the existing edge in
  place rather than appending a duplicate.

The edge `kind` is a **three-value enum** — `nav | info | action` — and it is the load-bearing
distinction of the whole map:

- **`nav`** — literal menu navigation that changes *where you are* without changing *game state*
  (back / previous).
- **`info`** — reading content without moving (view / help / list / display / examine).
- **`action`** — every state-changing or unrecognized transition. This is the catch-all: a named
  state-changing verb (buy/sell/purchase/attack/deploy/genesis/…), *and* any option the crawler
  could not affirmatively prove safe, are both recorded with `kind="action"`. The store's schema
  has no `"unknown"` kind, so the crawler folds the real category into the edge's `desc`
  (`"buy: Buy New Ship"` vs `"unknown: K----"`) — the distinction is never lost, it just rides in
  `desc` rather than in `kind`. An `action` edge is **recorded-not-pressed**: the crawler notes
  that the transition exists and where it starts, but never presses it to find out where it leads,
  so its `to_node` is the sentinel `<unexplored>`.

**Per-world keying is an invariant.** A world is `host + in-game game-letter + character/handle`,
not merely host+game — two different characters on the same host and game are two different
worlds, because a fresh character sees a different map state. The store resolves every node/edge
under `world/<world_id>/game_knowledge.json` via the pinned identity from
[World Identity](/engine/world-identity.md). One map never bleeds across characters.

# The Read-Only Never-Commit Crawler Contract

The crawler enumerates a world's menu map by walking it, and its entire reason for existing safely
is that **it can never commit an action.** The contract has a specific, deliberately-layered
shape, and one part of it is easy to get wrong: *where the guarantee actually lives.*

## The guarantee lives in the supervised run, not the word-list

The bounding guarantee is the **A+C protocol**: a live crawl must only ever run under a disposable,
**zero-credit / zero-asset character (A)** plus a **hub-supervisor able to abort mid-crawl (C)**.
That is what would bound the worst case to *nothing* — not the crawler's lexical label
classification.

**Tip has no live crawl driver today — intentionally parked, not orphan-dead.**
`menu/crawl_driver.py` — the module that held the code-enforced half of this
(`run_live_crawl()`, which refused outright before opening a single
connection unless the profile was explicitly flagged `crawl_sacrificial`) — was
retired (WO-CLEANUP-DEAD-SYMBOLS-BATCH-2026-08-05) because the daemon's
`crawl_start` protocol verb has never been wired to a driver
(`tests/test_crawl_start_protocol.py` stays BANKED/ignored for exactly that
reason). The read-only discovery machinery this concept describes
(`menu/crawler.py` / `crawl_menus()`, below) is live, real, and test-proven;
*driving* it against a live connection waits on Max's scope ruling in
[PENDING-MENU-CRAWL-LIVE-DRIVER-REBUILD](/DECISIONS.md#PENDING-MENU-CRAWL-LIVE-DRIVER-REBUILD)
(queue visibility: `WO-GATED-MENU-CRAWL-DRIVER-REBUILD`). Cleanup-removal
audits must not delete the never-commit suite or half-wire `tw crawl` ahead of
that gate. `credentials.is_crawl_sacrificial()` — the fail-closed
`crawl_sacrificial` flag reader — is still live, but today it only backs the
unrelated `dev`-sender exception (`canon/doctrine/dev-drive-exception.md`), not
a live crawl. A genuine sacrificial profile is still expected to set both
`crawl_sacrificial = true` and `allow_register = true`
whenever a live driver is (re)built — the requirement below is the contract that rebuild must
satisfy, not a description of code that exists today.

The abort leg was equally structural, in the retired module: the crawler asks its
`session_factory` for a fresh settled screen at every node boundary (it traverses by *replay from
start*, never by stateful backtracking); the driver wrapped that factory so a hub abort check —
and an independent `is_driver_fenced()` signal (still live, `session/control_lock.py`), raised the
instant a human `tw attach` takes the control lock out from under an in-flight crawl — were checked
*before* the real factory was ever touched. Either trigger was meant to land the stop at the next
screen boundary, **never mid-send**, needing no cooperation from the crawler's own internals. A
rebuilt driver must reinstate this, not merely the sacrificial-flag check above.

## The lexical layers are best-effort defense-in-depth

Under that frame, the crawler's own classification is a genuine, tightly-kept **defense-in-depth**
belt whose job is to *minimize how often the crawl even brushes up against* a commit action — not
to be a completeness proof (an unbounded natural-language label space cannot be lexically
classified with proven completeness, and chasing that was deliberately abandoned once A+C made it
unnecessary). Three layers:

1. **Per-option label gate** (`classify_option_label`). Every discovered `(key, label)` pair is
   judged from its rendered **text label**, never the bare keystroke — the same physical key means
   different things on different screens (`B` is "Buy" on one menu, "Back" on another), so the
   label is the only safe thing to judge. It is **deny-by-default**: a key is emittable only on an
   affirmative match to a small **safe allowlist** (view / help / list / display / examine / back /
   previous). Anything else — a named state-changing verb, a **compound label** naming more than
   one clause (`"View & Repair Ship"` reads safe by its first clause but commits its second), or
   any unrecognized label — classifies `"unknown"` and is recorded-not-pressed.
2. **Per-screen safety classification** (`screen_state`), evaluated *before* any option on the
   current screen is even enumerated. A screen that looks like a commit / confirm / purchase /
   combat gate — by keyword anywhere on screen, *or* structurally by the shape of its **active
   prompt line** (a trailing square-bracket default-answer token `"…? [Y]:"`, a free-input
   solicitation `"Enter … :"` / `"How many … :"`), *or* by matching one of Screen Understanding's
   own login/pause/game-select/char-create/cim gate anchors — is **never enumerated at all**. Not
   even its options' labels are read. This is what "back out to a safe menu without answering"
   means in practice: the crawl simply never sends anything from an unsafe frontier and moves on.
3. **No bare Enter, ever.** A bare vertical confirm like `"(Y)es\n(N)o"` (or `"(A)ccept\n(D)ecline"`)
   has an ordinary bracket-option line as its last line and slips past both layers above. Rather
   than chase it with another heuristic, a synthetic bare-Enter option is still *discovered* (so
   the graph notes an Enter transition exists) but is **never** in the safe allowlist — it is
   unconditionally recorded-not-pressed. "Quit" is likewise deliberately never emittable: the
   replay-from-start traversal never needs to press quit/back to navigate, so a quit option — an
   innocent parent-menu quit or a genuine session exit alike — is always recorded-not-pressed.

Every candidate keystroke the crawler could ever send passes through exactly **one chokepoint**,
`emit_key_if_safe()`, which reaches an actual `session.send()` (via `settle.send_and_confirm`)
only when the resolved category is in the safe allowlist. There is no other send path in the
module. The allowlist and the deny set are held provably disjoint by a module-load assertion.

## Accepted residuals — by design, not oversight

The lexical layer knowingly leaks a bounded set of shapes, each bounded to **zero real-world
impact** by the A+C protocol: prefix-affixed forms of a deny verb (`"Repurchase"` dodging `buy`);
agent-nouns and derived nouns sharing a verb stem (`"Buyer"`, `"Vendor"`, `"Ejection"`,
`"Confirmation"`, `"Redemption"` — the deny patterns are deliberately bounded to *active verb
conjugations only*, never bare prefixes, precisely so these read as ordinary informational nouns);
the `"board"` homograph (the common UI noun "Notice Board" vs the rare piracy verb — only the
unambiguous `"boarding"` is denied); and a genuinely novel/synonym/mislabeled commit action
sharing no vocabulary with anything denied. None is a completeness gap the module claims to close;
the sacrificial-character + hub-abort protocol is what makes closing it unnecessary.

# The Reborn Recast — Human-Invoked, Not Autonomous

In v1 framing this crawl was described as "AI-driven." In the reborn contract it is a
**human-invoked, supervised discovery run**: the operator starts it against a sacrificial
character with the hub watching, or the teacher assists a targeted map-fill after an escalation.
There is no autonomous agent exploring a live, asset-bearing account. Map extension is the
escalation moment recast — when the app meets an unrecognized menu (the `unknown` stop-on-unknown
trigger owned by [Control & Escalation](/architecture/control-and-escalation.md)), the human is
the one who decides to explore it, and the crawl records what is found for a future navigator. The
knowledge store is *read* by guards, the navigator, and the teacher; it never reads itself to
drive.

## Crawl-status provenance (`record_crawl_status` / `get_crawl_status`)

Each crawl stamps a sidecar on the on-disk menu map via `menu/knowledge.record_crawl_status`
(writer — called from `menu/crawler.py` at crawl end/abort/error) and reads it back with
`get_crawl_status` (reader). The stamp carries `status` (`complete` / `aborted` / `error` /
`truncated`), optional `reason`, and frontier counters (`nodes_visited`, `frontier_remaining`).
`menu/map_view.menu_map_summary_from_store` attaches that blob as `last_crawl`; `format_menu_map_report`
(`tw menumap`) appends one provenance line when present so a partial map is not silently readable
as complete — absent stamp omits the line (unknown provenance is not invented as "never crawled").
Shipped PR #636.

# The Game-Data Introspector — Read, Parse, Store as VIEW

Alongside the menu-graph crawl sits a pure **game-data introspector** (`introspector.py`): it
turns a captured StarDock / shipyard / scanner / TransWarp / item **listing screen** into
structured rows for the [Game-Data Store](/engine/game-data-store.md). It is the **read side** of
the two-layer rule this bundle enforces everywhere — portable *semantics* are authored in canon
and carry no per-server numbers; concrete per-server *values* are introspected live from a real
screen, never hardcoded. `introspector.py` is exactly that live-value reader: pure text-in /
rows-out, no I/O, no daemon touch, regexes over an already-rendered buffer, precisely like
`state_parser.parse_port_report()`.

Its discipline is conservative by design, because a wrong introspected stat poisons the data store
that upgrade decisions read:

- A field the listing does not actually show is **omitted or left `None`** — never a guessed
  default. An unparseable line is **silently skipped** — never a garbage row.
- Ship rows carry `alignment_requirement` / `rank_requirement` because a ship the player cannot
  yet legally commission is not a real acquisition candidate no matter how good its stats look.
- It anchors to the **LAST** closed listing block, not the first — the same stale-scrollback
  discipline the rest of the read layer obeys: an older, already-closed listing can sit above a
  fresher one in pyte's unclaimed grid, and first-match would parse the stale one. A listing still
  printing (no footer yet) is treated as not confidently closed and skipped.
- It carries **no clock**: stamping `last_verified_ts` is the persist layer's job, keeping this
  module pure.

Every introspected row is stored as a **VIEW-only** observation — recorded because a screen was
*read*, never because anything was purchased to reveal it. The `source` field tags each row's
provenance (`"introspected: stardock_shipyard"`, etc.).

# `tw probe` — The Zero-Input Read-Only Catalog Probe (L0)

`probe.py` / `tw probe` is the **zero-input entry point** into this whole read-only contract — the
gentlest possible touch of a server. At its default **L0** level it does a TCP connect and replies
to IAC telnet negotiation **only** — never a byte of user input — and classifies the front end
from the opening banner alone (`twgs-direct` / `bbs` / `protocol-fail` / `unreachable`). A polite
envelope bounds it: a 7-second connect/read budget, sequential, no retries, one connection per
endpoint per run, no credentials.

An optional **L1** (`--menu`, default **off**) is structurally incapable of answering any prompt
but one: it may emit **at most one bare carriage return**, and only when the cleaned banner
already contains the exact TWGS outer `(ENTER for none)` name prompt — then it disconnects. On any
other prompt (BBS or unknown) it refuses to send the CR at all. Probe never rewrites a catalog's
`front_end`; it only surgically patches `status` / `last_checked_at` for the keys it probed. It is
the smallest, safest instance of the never-commit posture the crawler scales up.

# Deterministic Navigation Over the Map

Once the map exists, navigation is deterministic and pure: match a live screen to a known node
(**localize**, `menu_nav.localize` — compute the signature the crawler stored and look it up;
return `None`, meaning "off-map, escalate — do not navigate blind," rather than ever guessing a
nearby node), then compute a **route** — the shortest edge path from here to a target node
(`game_knowledge.find_menu_path`, plain BFS over the edge list) — and hand back an ordered
keystroke sequence. The menu-map inspector (`menu_map_view.py` / `tw menumap`) renders the graph
for the human: you-are-here (★ or off-map), reachable coverage, dead-ends, orphans — pure summary,
no sends.

The safety rule governing *execution* of a route is the same one that governs the map's own edge
kinds: **a `nav` or `info` edge is free to walk; an `action`-class edge is gated exactly like a
taught rule** — human-approved, never fired blind. Pathfinding may *route through* only the safe
edge kinds; a route that would need to cross an `action` edge is not silently executed on the
human's behalf. This mirrors the [Rule–Macro Engine](/architecture/rule-macro-engine.md)'s gate on
any fireable action and defers to the runtime stop-on-unknown owned by
[The App Autopilot Model](/architecture/app-autopilot-model.md): the moment localization returns
off-map, or a route needs an action edge, the app stops and the human decides.

# Scanner + TransWarp Acquisition (K6) — Evaluated From the DB, Acquired by the Human

Acquiring a scanner or a TransWarp drive is a concrete downstream use of the introspected
game-data. The evaluation is deterministic and reads the **game-data store**, never a live screen
guess: given the introspected catalog rows (cost, requirements) plus the player's state and loop
economics, the upgrade evaluator (`ship_upgrade_decision.py`) ranks eligible **commissioned**
candidates against its gates — an un-commissionable ship (alignment/rank not met) is filtered out
before its stats ever count. But **acquisition itself is a human-approved behavior**: the app may
*recommend* "this scanner pays back in N turns," it does not autonomously buy it. The purchase is a
state-changing action, so it lives on the far side of the same rule-gate every `action` edge sits
behind — surfaced as a suggestion, executed only on the human's say-so. This keeps a clean seam:
the DB and the evaluator are read-only reasoning; the credit-spending keystroke is a taught,
approved move.

# Code divergence

The read-only machinery is broadly faithful to the reborn target — the crawler cannot commit, the
introspector cannot guess, the probe cannot type. The divergences worth recording are about
*framing* and *un-wired reach*, not unsafe behavior:

- **"AI-driven crawl" language — tip-closed (WO-CANON-DRAFT-MENU-CRAWLER-AI-DRIVEN-TERMINOLOGY).**
  Tip `menu/crawler.py` docstring is **human-invoked, supervised discovery — never an autonomous
  agent** (archived "AI-driven" framing named as retired). `menu/knowledge.py` has no AI-driven
  claim. Live paths are `menu/crawler.py` + `menu/knowledge.py` (not archived `menu_crawler.py` /
  `game_knowledge.py`). Behavior already matched the reborn A+C gate; naming now matches tip.
- **Deterministic-nav execution — kernel LIVE (`menu_nav_exec.run_nav`);
  CLI consumer LIVE (`tw menumap --to … --exec --arm`).**
  `plan_nav` keeps the dry CLI path (`tw menumap --to`, never sends).
  The send half lives **outside** the crawl `menu/` package (so
  `emit_key_if_safe` remains the sole crawl send chokepoint):
  `run_nav(session, plan, path, should_abort=, is_armed=)` — unarmed → zero
  sends (`not_armed`); ``action`` edges → `action_edge_requires_rule` without
  sending; re-checks arm/abort each step; off-map / localization mismatch →
  halt. Concrete session contract (`send` + `rendered_text`), no getattr
  duck-typing. Product CLI: `--exec` without `--arm` refuses with zero
  sends; together they drive a daemon `do`/`screen` adapter through
  `run_nav`.
- **No live-captured StarDock/shipyard screen yet.** `introspector.py`'s row grammar (the columnar
  ship table; the Name/Cost equipment tables; the per-hold cargo-price line) is **constructed**
  from the documented TW2002 listing convention plus this project's own real-capture divider
  style — it is *not* a byte-for-byte real capture. Its output is **HYPOTHESIS / UNVERIFIED**
  until the daemon sees a real StarDock screen; consumers (the game-data store, the upgrade
  evaluator) must treat introspected values as provisional. See Verification status.
- **Scanner/TransWarp acquisition has no send path.** `ship_upgrade_decision.py` *evaluates*
  candidates from the DB, but there is no autonomous acquisition executor — consistent with the
  reborn target (acquisition is human-approved). Recorded as intended-not-missing: the seam is
  correct; only a human-gated suggestion surface, not an auto-buyer, should ever be built on it.
- **`find_menu_path` kind filter — CLOSED (WO-FIX-MENU-PATH-KIND-FILTER).** Earlier tip BFS walked
  every stored edge; safety was emergent from action→`<unexplored>` sinks (scout
  WO-FIND-MENU-PATH-KIND-FILTER-SCOUT). Tip now filters hops to `SAFE_MENU_WALK_KINDS` (`nav|info`)
  so an action edge to a real node cannot be walked. The unexplored-sink assert remains
  belt-and-suspenders.

# Verification status

- **VERIFIED (live-behaviour / tested):** the crawler's chokepoint and layered safety gates, the
  menu-signature keying shared with the navigator, the `nav|info|action` edge schema, and
  `tw probe`'s L0 IAC-only / L1 single-CR envelope are exercised by the test suite and the
  read-only-by-construction design. The `crawl_sacrificial` *flag reader*
  (`credentials.is_crawl_sacrificial`) is live-tested; the live-crawl refusal gate and
  abort/fence stop-at-boundary behavior that used to consume it are **retired, not live** — see
  "The guarantee lives in the supervised run" above.
- **HYPOTHESIS (constructed, not yet live-captured):** every concrete introspected value grammar in
  `introspector.py` (ship/scanner/TransWarp/item listing shapes, the cargo-hold per-unit price
  line). This bundle authors the portable *semantics* of these catalogs; the per-server *values*
  are introspected live and remain provisional until a real StarDock screen is captured. No
  per-server stat number is asserted in this canon.

# Examples

The two edge kinds a crawler emits for the same screen — one walked, one recorded-not-pressed:

```
Menu screen (settled):
  StarDock Main
    (V)iew Ship Registry
    (B)uy New Ship
    (Q)uit to Sector
  Enter your choice:

classify_option_label("V", "View Ship Registry") -> "view"   (safe allowlist)
  => emitted; edge recorded  kind="info"   desc="View Ship Registry"  to_node=<real sig>

classify_option_label("B", "Buy New Ship")       -> "buy"    (state-changing)
  => NEVER pressed; edge recorded  kind="action"  desc="buy: Buy New Ship"  to_node=<unexplored>

"(Q)uit"  -> recorded-not-pressed (quit is never emittable); traversal replays from start instead
```

A commit-shaped screen is never enumerated at all:

```
Screen (settled), active prompt line = "Purchase 40 holds for 58,720 credits? [Y]:"

screen_state(...) -> "unsafe"     (trailing square-bracket default-answer shape)
  => the crawl reads NONE of this screen's options; it backs out to the next queued frontier
```

Navigation localizes or honestly reports off-map:

```
localize(live_screen, path) -> node        => find_menu_path -> [edge, edge, ...]  (walk nav/info)
localize(live_screen, path) -> None        => off-map: STOP, escalate — never navigate blind
```

# Citations

[1] `tw2002_aiclient/menu/crawler.py` — the read-only crawler: deny-by-default
    `classify_option_label`, `screen_state` per-screen gate, the single `emit_key_if_safe`
    chokepoint, BFS-via-replay traversal, the `nav|info|action` edge folding, and the
    accepted-residual analysis. (Archive port-source: `twclient/menu_crawler.py`.)
[2] Archive `twclient/crawl_driver.py` / retired tip `menu/crawl_driver.py` — the load-bearing
    safety leg: the `crawl_sacrificial` startup refusal (A+C protocol) and the abort /
    driver-fence stop-at-boundary wrapper. Retired 2026-08-05 (zero product callers,
    `crawl_start` never wired to a driver) — see "The guarantee lives in the supervised run"
    above. No live tip module implements this citation today.
[3] `tw2002_aiclient/introspector.py` — the pure text-in/rows-out game-data introspector,
    last-match block anchoring, conservative omit-never-guess discipline, and the
    constructed-grammar provenance caveat. (Archive port-source: `twclient/introspector.py`.)
[4] Tip probe/IAC split (archive `twclient/probe.py` was a single L0/L1 peek module):
    `tw2002_aiclient/session/iac.py` (IAC negotiation / polite envelope) +
    `tw2002_aiclient/catalog_cli.py` (`tw probe` — TCP catalog liveness sidecar; not a
    TWGS-outer-prompt typer). Do not read tip `tw probe` as a revival of archive L0 banner
    classification.
[5] `tw2002_aiclient/menu/nav.py`, `tw2002_aiclient/menu/knowledge.py`,
    `tw2002_aiclient/menu/map_view.py` — localize / `find_menu_path` route composition, the
    per-world-keyed node/edge store (`MENU_EDGE_KINDS`, `upsert_menu_node`/`upsert_menu_edge`,
    `knowledge_path`), and the read-only menu-map inspector.
[6] `tw2002_aiclient/menu/sig.py` — the shared menu-signature primitive keying every node
    (owned by Screen Understanding).
[7] `tw2002_aiclient/ship_upgrade_decision.py` — the read-only upgrade evaluator behind K6
    scanner/TransWarp acquisition; the `commissioned` (alignment/rank) gate.
[8] `tw2002_aiclient/world_identity.py` — `world_id(host, game_letter, handle)`, the per-world
    keying invariant the map is stored under.
[9] CLAUDE.md "Architecture map" + "Hard rules" — the read-only crawl gate, `state_parser`
    last-match invariant, single-connection daemon, and secrets discipline.
[10] `.samantha/plans/okf-final-vision-map.md` — `engine/menu-map-and-introspection.md` spec
    (must-cover, cross-links, REIMAGINE disposition, findings).
