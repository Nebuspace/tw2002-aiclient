---
type: Strategy
title: Toll and Defense Math
description: Decision framework for handling toll-sector NPC fighters and mine encounters — when to fight through, pay, or reroute, and how much defense is enough.
tags: [strategy, combat, defense, hypothesis]
timestamp: 2026-07-19T16:11:33Z
---

Applies specifically to NPC-controlled hazards (deployed corp fighters guarding a sector, mines)
encountered en route — not to player-vs-player combat, which this client treats as a separate,
human-directed concern (see [Paladin Ethos](/doctrine/paladin-ethos.md) for the no-grief
posture this strategy operates under).

**Verification status:** UNVERIFIED against the live game. The specific ratios and percentages
below (minimum-fighters formula, surrender-probability bands, missile-bypass rate, shield defense
floor) are carried over from third-party TW2002-variant strategy-guide research and must be
confirmed against direct in-game combat observation before being relied on operationally. Encode as
configurable coaching parameters, never hardcoded constants.

# What it is
A pre-combat decision: given a toll sector's known (or scanned) defender fighter count and combat
odds, decide whether to fight through, pay a toll if offered, or reroute around the sector
entirely.

# When it applies
- Any time a route (a planned trade loop or an exploration frontier push) crosses a sector known or
  suspected to hold defended NPC fighters.
- Also applies to mine encounters, which threaten cargo/ship loss on entry rather than requiring
  combat.

# Tradeoffs (hypothesis)
- **Minimum fighters to win** is hypothesized as `(defender fighters × defender odds) ÷ your odds`,
  with shields counting double their nominal value (2:1) toward your effective defense.
- **Surrender upside**, hypothesized by attack-strength ratio: overwhelming force (>10x) tends
  toward full/free surrender; a large edge (~5x) toward roughly even odds of a partial surrender; a
  moderate edge (~2x) toward a smaller chance. These are approximate bands, not guarantees.
- A small fraction of missile damage (hypothesized ~7%) is described as bypassing fighter defense
  directly, which is the argument for carrying some minimum shield reserve (hypothesized ~10% of
  fighter count) even when fighters alone look sufficient.
- **Reroute** (an extra hop or two around the hazard) is often cheaper in turns than fighting,
  especially when the fight would cost fighters/shields that then need turns/credits to replace —
  weigh reroute-turn-cost against expected combat losses; "we can win" does not automatically mean
  "we should fight."
- This strategy assumes purely NPC/environmental hazards. Any situation involving a real player is
  out of scope here — see [Paladin Ethos](/doctrine/paladin-ethos.md); the client's posture
  never autonomously initiates player combat regardless of the math above.

# Steps
1. Before entering a known-hazardous sector, retrieve its last-known defender count from the
   [World Model](/architecture/world-model.md), or take a fresh density-scan reading (see
   [Frontier Exploration](/strategies/exploration.md)) if the record is stale.
2. Compute the hypothesized minimum-fighters-to-win and compare against your current
   fighter/shield loadout.
3. If the reroute cost (extra turns) is lower than the expected cost of fighting (fighters/shields
   likely lost, replacement turns/credits), prefer reroute.
4. If fighting, ensure the minimum shield reserve is met before engaging, to blunt the
   bypass-damage risk.
5. Record the outcome (fighters/shields spent, sector, result) so the world-model's threat entry
   for that sector stays current for the next pass.

# Citations
[1] design history §16.2 — toll decision rule: minimum-fighters formula, surrender-ratio bands,
    missile-bypass rate, shield reserve
[2] design history §18 — alignment ethos: player-combat is human-directed/coached, never an
    autonomous trigger
