---
type: Reference
title: World Identity — the Keying Rule for All Durable Knowledge
description: The single host + game-letter + character identity tuple that scopes every durable per-world store, so knowledge learned in one galaxy never bleeds into another.
tags: [world-identity, keying, per-world, isolation, invariant, cross-cutting]
timestamp: 2026-07-23T19:47:49Z
---

Everything the trainer learns is learned *about a specific world*: this sector has that port,
these warps lead there, this menu key does that, this taught macro flies this route. None of it is
universal. A map drawn in one galaxy is not just useless in another — replaying it there is a way
to send the human's ship somewhere it was never meant to go. So every durable store the app writes
must be scoped to exactly one world, and there must be exactly **one** rule for naming a world that
every store keys off of. That rule is the subject of this document.

# Schema

## What a world is — the identity tuple

A **world** is identified by three components, together:

1. **`host`** — the telnet server the game runs on. A different server is a different game
   universe.
2. **`game_letter`** — the in-game game slot on that host (TradeWars servers host multiple lettered
   games). A different letter on the same host is a different galaxy.
3. **`character` / registration handle** — the specific character the human plays as. **This is the
   part that is easy to get wrong, and it is load-bearing.** In TradeWars, registering a fresh
   character produces a **freshly generated galaxy** even on the same host and the same game letter.
   Two different characters on the same nominal game are two *different worlds*, with different
   sector layouts, different ports, and a different turn/asset allotment. Keying on host + game
   alone would let one character's map silently overwrite another's — the "galaxy bleed" this rule
   exists to prevent.

All three are required, and all three participate in the key. Drop any one and two genuinely
distinct worlds can collide onto the same key.

## The keying rule

The identity tuple resolves to a single **filesystem-safe world slug** that names the on-disk home
of every durable store for that world. The derivation is deterministic and does no I/O — the same
inputs always produce the same slug, from any process (CLI, daemon, or a test), without touching
disk.

Two normalization rules are part of the contract, not incidental:

- **`host` is lowercased before it is used.** Network hostnames are conventionally
  case-insensitive, so `Host.Example` and `host.example` must resolve to the **same** world.
- **`game_letter` and `character` are case-preserved.** Both are exact in-game identifiers, not
  free-form text, and case can be a real distinction there — folding it away could merge two
  distinct worlds.

Anything outside the filesystem-safe alphabet (letters, digits, dash, underscore) becomes an
underscore. This substitution is deliberately **not** collapsed or trimmed: two distinct raw inputs
must never sanitize down to the same slug (a character named `jon` and one named `jon!` stay
distinct — `jon` versus `jon_` — rather than both collapsing to `jon`).

A structurally unusable component — missing, null, or empty/whitespace-only host, game letter, or
character — is a hard error, never a silently-defaulted or blank key. An *unusual but present*
value (stray punctuation, mixed case) is sanitized, not rejected.

> A world does not exist until its character does. A profile set up to auto-register but that has
> not yet drawn a character handle has no character component yet, and therefore **cannot** be
> assigned a world identity — there is nothing to key on until the registration lands. Any store
> that needs a home before then must use a distinct, clearly-temporary per-profile fallback, never
> a half-formed world key. See the Code divergence note on handle-less profiles.

## One keying rule, many consumers

The whole point of a single rule is that **no store invents its own key.** Every durable per-world
store derives its location from the one world slug. The consumers, enumerated so the list is
closed:

| Consumer | What it stores per world | Cross-link |
|---|---|---|
| **World Model** | the sector database — warps, ports, threats, landmarks, formations | [world-model](/engine/world-model.md) |
| **Game-Data Store** | live per-server introspected DATA (ship stats, catalogs) | [game-data-store](/engine/game-data-store.md) |
| **Menu Map** | the per-world menu graph and its read-only-crawled structure | [menu-map-and-introspection](/engine/menu-map-and-introspection.md) |
| **Macro / Loop Library** | the taught keystroke sequences and repeating loops for this world | [macros](/engine/macros.md) |
| **Retro / Candidate Mining** | the ledger slices mined for this world's recurring patterns | [candidate-mining](/engine/candidate-mining.md) |

Each of these owns its own record schema and its own read/write discipline; what they **share** —
and must share — is this one rule for deciding which world a given record belongs to.

## Reset semantics — isolation is the guarantee

- **A new world is a clean slate.** Its map, its menu graph, its game-data rows, its macro library
  all start empty. Learning does not carry forward from a prior character or a prior galaxy, because
  it would be wrong there — the sectors, ports, and layout are freshly generated.
- **Knowledge never bleeds across worlds.** Because two worlds resolve to two different slugs, their
  stores live in two different directories and *structurally* cannot overwrite each other. Isolation
  is not enforced by a runtime check that could be forgotten; it falls out of the keying itself.
- **A reset is scoped to its own world.** Abandoning or re-rolling a character resets that world's
  library and map only. Every other world the human has taught is untouched.

## Invariant status

Per-world scoping via this one keying rule is a **hard, cross-cutting invariant**, stated here once
so the individual store concepts don't each re-derive it:

> **Every durable store the app writes is keyed by the world identity tuple (host + game-letter +
> character). No store may key on a subset of it, and no store may invent its own scheme.**

This sits alongside the trainer's other load-bearing invariants (senders of live keystrokes are
`{app, human}` only; secrets never touch logs/argv/repo). It is the one that keeps a galaxy's worth
of learned knowledge from leaking into a galaxy where it is false.

# Examples

**Same character, host case differs → one world.** `TelnetHost.Example / game A / <character>` and
`telnethost.example / game A / <character>` lowercase the host to the same value and therefore key
to the *same* world — the human reconnecting with a differently-cased host string keeps their map.

**Same host + game, different character → two worlds.** `host / game A / <character-one>` and
`host / game A / <character-two>` key to two different slugs. Each fresh registration got a fresh
galaxy; their maps, threats, and taught loops stay completely separate. This is the anti-bleed case
the rule exists for.

**Same character, different game letter → two worlds.** `host / game A / <character>` and
`host / game B / <character>` are two different galaxies on the same server and key separately.

**No character yet → no world.** A profile that opted into auto-registration but has not drawn a
handle has no character component and cannot be keyed — there is no world until the character
exists.

# Code divergence

The reborn keying rule is implemented and matches this doc for the map-shaped stores, but two
consumers enumerated above are **not yet world-keyed** in the current code. These are recorded as
divergences (DOCS WIN): the target is that every durable store keys on the world identity; where the
code has not caught up, the doc is the prescription, not the description.

- **Macro / loop library world-scoping (PWO-090).** When a `world_id` is supplied, the macro store
  reads/writes `state/world/<world_id>/skills/` (+ `_drafts/`), matching map / game-data / menu-map.
  Legacy flat `state/skills/` remains for callers that omit `world_id`, and
  `migrate_flat_loops_to_world` copies flat → world on first world-scoped read/write when the world
  store is empty (DECISION-LOOPS-WORLD-MIGRATE-ON-READ). Callers that never pass `world_id` still
  see the flat tree — product cockpit / autoloop (profile-derived) / CLI `--world-id` are the
  world-scoped paths. (Start-anchor / send-and-confirm guards remain the replay backstop.)

- **The trace ledger is a single global sink.** The ledger appends every session's rows to one
  shared file (`state/ledger.jsonl`) rather than a per-world store. Each row does carry a
  `session_id` (and actor attribution), so a retro pass *can* slice by session — but it cannot
  cleanly slice by world without correlating sessions to worlds out of band. The prescription is
  that retro/candidate-mining reads a **world-scoped** view; whether that is achieved by a per-world
  ledger path or by stamping each row with the world slug and filtering is an implementation choice
  the ledger and candidate-mining concepts should settle, but the current global-sink shape does not
  yet honor the per-world keying rule.

- **Handle-less registration profiles fall back to a per-profile path, by design.** Because the
  keying rule (correctly) refuses to derive a world slug from a profile with no character handle, a
  not-yet-registered auto-register profile has no world identity, and the CLI routes such a profile
  to a plain per-profile fallback path instead. This is consistent with "a world does not exist
  until its character does" above and is recorded as expected behavior, not a defect — but it is the
  one path where a durable store is *not* under a world slug, and it must resolve to a real world
  slug the moment the character registration lands.

# Citations

- Reborn vision (fixed constraints): the human is the sovereign pilot; the app plays back only
  taught, per-world knowledge and stops on anything unrecognized. Per-world isolation is what makes
  "taught knowledge" safe to replay.
- Internal design history — the world-model World Identity section (the host + game-letter +
  character rule and the fresh-galaxy-per-registration rationale) and the TW-06 world-model /
  TW-25 game-knowledge lanes that pin the shared keying signature.
- Project canon — the North Star three-actor model and the hard-rules invariant set (single-session
  daemon, secrets never touch logs/argv/repo) this keying invariant sits alongside.
