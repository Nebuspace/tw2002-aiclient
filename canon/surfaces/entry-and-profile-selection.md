---
type: System
title: Entry Surface — Player Profile & Server Selection
description: The pre-cockpit launcher where the operator picks or creates a player and chooses the game server from the known catalog, establishing the world identity before the cockpit ever opens.
tags: [surface, entry, launcher, profile, server-catalog, world-identity, credentials, tui]
timestamp: 2026-07-23T20:55:20Z
---

Before there is a cockpit, a mode line, or a single keystroke sent to a game, there is a choice:
*who are you playing, and where?* The entry surface is that pre-cockpit launcher. It lists the
players the operator has already set up, offers to create a new one, and — for a new player — lets
the operator pick a server from a catalog of known TradeWars 2002 endpoints rather than typing a
hostname from memory. The single act of selecting a player-plus-server is what pins the **world
identity** the rest of the session keys everything off of, so this surface is small but
load-bearing: get the wrong character or the wrong game letter here and every durable store down the
line is scoped to the wrong galaxy.

This surface is deliberately narrow. It does not drive the game, it does not send input to a live
connection, and it never displays a password. It selects, it validates, and it hands a chosen
profile off to the cockpit.

# Schema

## What the surface is for

The entry surface answers exactly one question — *which world am I about to enter, as which
character* — and then gets out of the way. Its responsibilities:

1. **List existing players** so the operator picks a known character in one move.
2. **Create a new player**, including choosing the server from a preformatted catalog.
3. **Establish the world identity** (`host` + `game-letter` + `character`) from the selection — the
   one keying rule every durable store obeys.
4. **Surface the multi-player rotation touchpoint** — the credential bank that lets several
   *independent* characters be rotated to multiply the daily turn allotment — with its hard boundary
   shown, never hidden.
5. **Hand the chosen profile to the cockpit**, where it binds to the mode-line character strip.

It is a launcher, not a pilot. The reborn-vision invariant holds here trivially: nothing on this
surface sends a live keystroke to a game, so there is no "app vs human vs AI" driver question to
answer yet. That question belongs to the cockpit's mode line, not here.

## The player / profile picker

The picker lists the profiles the operator has already configured. Each row is a **profile** — a
named, non-secret shape describing one character on one server. The launcher's row data comes from
`credentials.list_profile_summaries()`, which yields, per profile: the profile `name`, the
character `handle`, a `server` display (the catalog key if the profile references one, otherwise the
bare host), the `game_letter`, and the `autopilot` flag. A profile that fails to parse still appears
as a row carrying an `error` string rather than vanishing — a broken profile is visible and
diagnosable, never silently dropped.

Two things a row **never** contains:

- **A password.** Profiles live in `config/profiles.toml`, which holds only the non-secret shape.
  The password lives elsewhere entirely (see below). The picker has no password field to render, so
  redaction here is structural, not a display filter.
- **Inferred login state.** The picker never guesses who is online from host/handle alone, and it
  never displays secrets.

### Active-profile presence (read-only overlay)

Profile **shape** still comes only from local config (`credentials.list_profile_summaries()` —
that half opens no socket). Separately, the launcher overlays a **read-only** presence column from
a bounded daemon `status` poll against the app's run directory:

- Mark a row **ONLINE** only when `status.connected is True` **and**
  `status.replay_arm.profile` **exact-matches** that row's profile `name`.
- At most one row is ONLINE (single active daemon / profile model).
- Connected false, daemon absent, unreachable status, missing/`None` profile, or a profile name
  that matches no configured row → **no** row is marked online. Unreachable status shows an honest
  unavailable note rather than inventing presence.

Presence is display-only: it does not attach, arm, send, or stop. Whole-app quit (`q`) is owned
by the app-exit confirm in [ADR-001](/ADR/001-one-tree-embedded-session.md) /
[trainer-cockpit](/surfaces/trainer-cockpit.md); Esc from Play back to this launcher still leaves
the daemon running.

Selecting an existing row means "enter this world as this character" and proceeds toward the
cockpit. The list is joined by a **Create New Player** action for the case where the character does
not exist yet.

## The new-player flow

Creating a player collects the non-secret shape of a profile and, crucially, lets the operator
**pick the server from a catalog** instead of typing a raw hostname. The catalog is
`config/servers.toml` — a directory-listed inventory of known TW2002 endpoints (hostname, port,
transport, front-end kind, status), resolved for display by `tw servers list`
(`cli.py::cmd_servers_list` → `servers.list_servers()`). It performs **no live connections**; the
`status` column is directory-provenance, not a health probe.

A created profile is written to `config/profiles.toml` (via `credentials.create_profile()`), which
requires at minimum a `game_letter` and either a `server` catalog key or an explicit `host`+`port`.
A profile may reference the catalog by key and let the endpoint resolve at load time
(`load_profile()` calls `servers.resolve_endpoint()` when `host`/`port` are absent but a `server`
key is present), so the catalog stays the single source of truth for where a server actually lives.

`handle` (the character name) is normally required too — with one deliberate exception: a profile
that opts into automated new-character registration (`allow_register = true`) may omit `handle`, and
the login automaton draws a fresh handle per registration attempt. That is the "register me a new
character" shape; an ordinary profile names its character explicitly.

**No password is collected on this surface into any tracked or logged path.** When a new character
must be registered, the password is generated and persisted by the automaton (see
secrets-and-credentials), never typed into a field this surface then echoes.

**Tip module — `create_form_screen.py`.** The Create-New-Player TUI form (extracted from
`screens` · WO-SCREENS-CREATE-FORM-SPLIT) collects only non-secret fields: catalog
`server` picker, `game_letter`, and `handle`. Credentials/secrets are **never
collected or shown** on this surface — field kinds are server/text only; there is
no password widget. `validate_create_form` is UI-side refuse (empty letter,
unknown catalog key, duplicate handle) and does not write. Persist still goes
through `credentials.create_profile()` after the form accepts.

## World identity on entry

Selecting a player is the moment the **world identity** is fixed. A world is *not* just a server — it
is the tuple **`host` + `game_letter` + `character/handle`**, because registering a fresh character
produces a freshly generated galaxy even on the same host and the same game letter. Two characters
on the same nominal game are two different worlds whose maps, threats, and learned loops must never
bleed into each other.

The profile carries exactly those three components, and `world_identity.world_id_from_profile()`
derives the single filesystem-safe world slug that every per-world store (the world model, the
game-knowledge crawl store) keys its persisted state on. So the operator's one selection on this
surface is what scopes all durable knowledge for the whole session. This is the anti-galaxy-bleed
guarantee's origin point: choose the character here, and the keying rule does the rest. See
world-identity for the full derivation and why all three components are load-bearing.

## Multi-player rotation touchpoint

TradeWars metes out turns per character per day. The **credential bank** (TW-31) exists to multiply
the operator's *own* daily allotment by rotating across **several independent characters** — each a
distinct profile, each its own world. The entry surface is where that bank is visible as a rotation
touchpoint: `tw players list` (`players_cli.py::cmd_players_list`) shows the banked characters with
`last_played` / `turns_state` rotation bookkeeping. Tip LIVE bank verbs are
`{list,next,rotate}` only — there is **no** `tw players add` today; linking a new bank row to a
profile remains TARGET / cockpit Create-New-Player + credential-bank write paths, not a shipped
`tw` subcommand (see [CLI Verbs](/architecture/cli-verbs.md)).

The bank stores **metadata only** — name, handle, host, game-letter, rotation timestamps. It holds
**no password** (`player_bank.py` pulls fields from `credentials.Profile`, which has no password
field at all; the one free-form input, a `notes` dict, is filtered against a secret-shaped-key
denylist as defense-in-depth). Passwords stay in the chmod-600 secrets file, resolved at use-time by
the login path — never by the bank.

### The hard boundary — shown, never buried

Multi-accounting to multiply *your own* turns is the sanctioned use. What the surface must make
unambiguous is the line it stops at: **never collusion or resource-transfer between the operator's
own accounts.** The characters in the bank are independent players; the bank exists to give each its
own honest turn allotment, not to shuttle credits, cargo, or assets from one of the operator's
characters to another. That boundary is stated canonically in alignment-and-conduct and echoed in
secrets-and-credentials; this surface's job is to *display* it at the rotation touchpoint so the
capability is never presented without its limit. The credential bank is a turn-multiplier for
independent play, full stop.

## Hand-off to the cockpit

Once a profile is chosen (existing row) or created (new-player flow), the entry surface's work is
done: it binds the selected profile to the cockpit and closes. The chosen character becomes the
**character strip on the mode line** — the App/Human dual mode line the cockpit renders (there is no
third "AI drives" position; AI appears only as a teach-overlay indicator). The world identity fixed
here is what the cockpit, the guards, and the retrospective teacher all read.

The transition is one-directional in normal flow: pick here, pilot there. Returning to the launcher
means ending the current session's binding, not switching worlds under a live connection.

This hand-off has a bookend at the other end of the session: when the operator exits the cockpit, a
confirm popup asks whether to stop the daemon along with the client, rather than silently leaving a
reattachable game session either orphaned or force-killed
*(— per [ADR-001](/ADR/001-one-tree-embedded-session.md) (Accepted 2026-07-24))*. See
[the Trainer Cockpit](/surfaces/trainer-cockpit.md)'s "Exit flow" section for the full statement;
this surface only launches the app the exit flow later closes.

## Boundaries this surface holds

- **No live send.** Listing, creating, and selecting touch local config and the catalog file only.
  No socket to a game is opened by this surface.
- **No password on screen, in argv, in logs, or in the repo.** Redaction reaches the UI by
  construction — there is no password field to leak.
- **No autopilot arming here.** Whether a profile *may* run Autopilot is a stored `autopilot` flag
  shown in the row, but arming a run and launching it is a confirm-gated action that happens in the
  cockpit, never as a side effect of selecting a player. There is never one keystroke from this
  surface to live money.
- **Catalog is directory data, not truth-on-the-wire.** A `status = "online"` in the catalog is
  provenance, not a probe; the operator learns a server is actually reachable only once the cockpit
  connects.

# Visual design & polish

This surface is, by design, the **plainest** in the bundle — and its look-and-polish spec has to be
read against a hard split between *what is built* and *what is aspirational*. Today the entry surface
is not a curses screen at all: it is a set of composed CLI verbs (`tw servers list`,
`tw players list` / `next` / `rotate`, plus profile creation via `credentials.create_profile()` /
Create-New-Player TUI) that print **plain, uncolored, columnar text**
to the terminal. The consolidated visual picker+create flow this document specifies — a focused
curses launcher rendered by the same engine as the cockpit — is the target; where a look detail
depends on that unbuilt picker it is marked `[ASPIRATIONAL]` and inherits the shared vocabulary
rather than inventing a local one. The one dimension that is fully *built and load-bearing* here is
**spacing/alignment** (the CLI column layout) and the structural **password-never-shown** affordance.

The shared color/glyph/border/fold vocabulary this surface would inherit lives in
[the shared visual language](/surfaces/visual-language.md) (tip — authoritative dictionary for the
7-tone semantic palette, Unicode/ASCII glyph twin-tables, two-weight border hierarchy, and
responsive fold ladder). This section specifies only what is
*surface-specific* to the launcher and points at that dictionary for the rest.

## Spacing / alignment / hierarchy — the one built dimension

The current CLI verbs already commit to a **fixed-width, left-aligned columnar** convention, and the
consolidated picker should inherit it verbatim so the two never drift. Grounded in `cli.py`:

- **Server catalog** (`cmd_servers_list`, cli.py:394-397): header + rows on the exact format
  `{KEY:<28} {HOST:<36} {PORT:>5} {FE:<7} {STATUS}` — text columns left-aligned, the **numeric
  `PORT` right-aligned** (`:>5`) so port numbers align on their ones digit. A single space is the
  gutter between every column.
- **Player / rotation list** (`cmd_players_list`, cli.py:458-459):
  `{name:<16} {handle:<16} {host:<24} {game_letter:<3} {last_played:<21} {turns_state}` — the same
  left-aligned-text convention; `game_letter` gets a tight 3-col field, `last_played` a wide 21-col
  field to hold a full ISO date.
- **Probe/catalog variant** (cli.py:424-428): `{KEY:<28} {CLASS:<14} {STATUS:<10} {HOST:PORT}`.

**Hierarchy / what draws the eye:** the operator is choosing *a character on a world*, so the
identity columns lead — `name` / `handle` first, the server context (`host`, `game_letter`) next, and
the rotation bookkeeping (`last_played`, `turns_state`) trailing as secondary metadata. The **game
letter** is the smallest field but the most load-bearing single character (it partly keys the world
identity), so `[ASPIRATIONAL]` the consolidated picker should emphasize it — bold, or set off from
the host — rather than let its 3-col field bury it.

`[ASPIRATIONAL]` The consolidated picker renders these same columns inside a **thin-rounded titled
box** (chrome weight, cyan) — e.g. a `" PLAYERS "` box and a `" SERVERS "` box, titles at col 2 —
per the two-weight border hierarchy (`cockpit/draw.py` `DOUBLE_*` / `THIN_*`; see the shared visual
language). There is **no double-line viewport** on this surface: the double-line weight is reserved
for a live CP437 game screen, and the launcher has none — it opens no socket. The launcher is all
thin-rounded instrument chrome, no game frame.

## Color semantics for the launcher

`[ASPIRATIONAL]` The current CLI output is **entirely uncolored** — plain terminal text, no curses
pairs allocated. When the consolidated picker is built it inherits the shared 7-tone semantic table
(see the shared visual language) but exercises only its *calm* end, because nothing on a launcher is
hostile or critical:

- **`info` (cyan)** for the box chrome and titles — *cyan is chrome, never data*, the same rule as
  every other surface.
- **`muted` (default)** for ordinary, resolvable rows — the launcher's steady state is quiet.
- **`ok` (green)** `[ASPIRATIONAL]` for a row whose `autopilot` flag is set, signalling a
  fully-armed profile — but note this is a *stored capability flag shown*, never an armed run;
  arming still happens confirm-gated in the cockpit.
- **`warn` (yellow)** `[ASPIRATIONAL]` for a **broken-profile row** carrying an `error` string, so a
  parse failure is visibly attention-flagged rather than blending in (see Panel states below).
- **`danger` (red)** has essentially **no home on this surface** — there is no live connection to
  drop, no turns gauge to redline. Its deliberate absence is itself the signal that this is a safe,
  pre-flight surface.

**Selection = reverse-video**, the single selection/active signal shared across the whole UI: the
`[ASPIRATIONAL]` currently-highlighted player or server row is drawn `A_REVERSE`, exactly as the
cockpit's Loops/Chains selected row and mode badge are (see the shared visual language). One
selection attr, everywhere.

## The password-never-shown affordance — structural, not styled

The most important "visual" fact about this surface is a **non-appearance**: there is no password
field, no masked `••••` echo, no redaction filter running over a value that briefly existed. A
profile row has **no password to render** — `credentials.Profile` carries no password field, and the
credential bank stores metadata only (`player_bank.py`). Redaction here is **structural**: the UI
cannot leak a secret because the secret is never in the row model in the first place. The polish
implication is that the launcher must **never grow a password input** — not even a masked one — on
this surface; the sole place a password enters the system is the login automaton at connect-time
(and, for `allow_register` profiles, it is *generated and persisted* by the automaton, never typed
here). The correct visual for "where is the password?" on this surface is **nothing at all** —
absence is the affordance.

## Panel states — active / empty / broken

- **Active / selected** `[ASPIRATIONAL]` — reverse-video row, as above.
- **Empty picker (no profiles yet)** — the list is empty and only the **Create New Player** action
  remains; the cold state points the operator straight at profile creation rather than showing a
  bare empty box. This is the launcher's "cold-join": there is no world to resume, so the surface
  offers the one move that makes sense.
- **Empty rotation bank** — a never-rotated character shows the literal `never` / `-` sentinels
  (grounded in the `tw players list` example: `scout-b … B  never  -`), an honest "no rotation
  history yet" rather than a fabricated timestamp.
- **Broken-profile row (built, load-bearing)** — a profile that fails to parse **still appears as a
  row carrying an `error` string** rather than vanishing (from `list_profile_summaries`). This is the
  surface's core "error state": a broken profile is *visible and diagnosable*, never silently
  dropped. `[ASPIRATIONAL]` the consolidated picker tints that row `warn` (yellow) and marks it so
  the operator's eye is pulled to the one row that needs attention — the launcher's small echo of the
  cockpit's "calm-until-it-needs-you" escalation.
- **Alert / escalation** — genuinely **N/A** here. There is no live runtime to halt, no
  intervention strip, no STOP banner. The launcher has nothing to escalate because it drives nothing.

## Liveness & motion — deliberately still

This surface is **static by design** and its polish is the *absence* of the cockpit's liveness
machinery: **no spinner, no heartbeat, no sparkline, no fuel-gauge, no delta-flash, no `→ TX`
readout, no `✦ Ns ago` freshness stamp.** It opens no socket, so there is nothing to be "frozen"
about — the "is it frozen?" problem the cockpit's liveness cues solve does not exist on a surface
that never streams. The nearest thing to a freshness signal is the **`last_played` date** in the
rotation list, but it is a plain stored value, not a live-dimming stamp. `[ASPIRATIONAL]` if the
consolidated picker ever shows freshness on `last_played`, it should reuse the shared `✦`/dim
convention rather than invent a new one — but the honest default is a still, quiet launcher.

## Glyph / status-marker vocabulary

Today the launcher's "markers" are **literal string values, not styled glyphs**: `online` / `ok` in
the `STATUS` column, `never` / `-` for empty rotation fields. These are **data, not chrome** — and in
particular a catalog `status = "online"` is **directory provenance, not a health probe** (the surface
opens no connection to verify it; see Boundaries). `[ASPIRATIONAL]` the consolidated picker adopts
the shared marker vocabulary (see the shared visual language) at its rotation/selection touchpoints:
`★` for a selected or you-are-here server row, `⊘` for a catalog entry known to be non-connectable,
`—` (em-dash) for an unknown/empty value in place of the bare `-`. Until then, the values above are
plain text and should be read as such.

## Responsive fold

`[ASPIRATIONAL]` The current CLI output relies on the terminal's own wrapping and a ~80-col
assumption for its columnar tables to line up; it has no adaptive layout. The consolidated picker
inherits the shared fold ladder (see the shared visual language) but exercises only its gentle end —
a launcher is a list, not a three-gutter cockpit, so on a narrow terminal the columns **collapse to a
single-column stacked row** (name/handle on top, server/game/rotation beneath) rather than scrolling
sideways. As everywhere in the bundle, **the body never scrolls horizontally** — a too-narrow field
truncates, it does not overflow.

## Feel

The plainest surface in the bundle, on purpose. It **selects, validates, hands off, and gets out of
the way** — deferring every ounce of richness (color, motion, escalation, the CP437 viewport) to the
cockpit it launches. Its aesthetic virtue is *quiet correctness*: aligned columns, honest empty and
broken states, and a password affordance that is a deliberate blank. A builder should resist
decorating it; the launcher earns its keep by being boring, legible, and impossible to leak a secret
through.

# Examples

## Picking an existing player

```
$ tw servers list          # (optional) browse the known-server catalog first
KEY                          HOST                                 PORT  FE      STATUS
a_net_online_lol             game.a-net-online.lol                2002  direct  online
briancmoses_com              tw2002.briancmoses.com                 23  direct  online
...

# Launcher rows come from list_profile_summaries():
#   name              handle            server                 game  autopilot
#   paladin-main      PaladinPrime      briancmoses_com        A     false
```

Selecting `paladin-main` fixes the world identity to
`world_id("tw2002.briancmoses.com", "A", "PaladinPrime")` and hands that profile to the cockpit.

## Creating a new player from the catalog

```
# Create New Player →
#   1. choose a server from the catalog  (server = "a_net_online_lol")
#   2. choose the game letter            (game_letter = "B")
#   3. name the character                (handle = "NewPilot")
# → credentials.create_profile(name="scout-b", server="a_net_online_lol",
#                              game_letter="B", handle="NewPilot", autopilot=False)
```

The endpoint is not copied into the profile — the profile references the catalog `server` key and
resolves `host`/`port` from `config/servers.toml` at load time, so the catalog stays the single
source of truth.

## The rotation bank with its boundary

```
$ tw players list
scout-b          NewPilot         game.a-net-online.lol    B   never          -
paladin-main     PaladinPrime     tw2002.briancmoses.com   A   2026-07-23     ok
# Rotation multiplies the operator's OWN daily turns across INDEPENDENT characters.
# Hard line (shown at this touchpoint): never transfer credits/cargo/assets between them.
```

# Code divergence

- **Launcher UI is CLI-verb-composed, not a single dedicated screen (yet).** The reborn "entry
  surface" is described here as one launcher; in current code its pieces are separate CLI verbs —
  `tw servers list` (`catalog_cli.cmd_servers_list`), `tw players {list,next,rotate}`
  (`players_cli`) — **no** `tw players add` — and profile creation via
  `credentials.create_profile()` / Create-New-Player TUI. The product cockpit entry is
  `./tw2002-aiclient` / `python -m tw2002_aiclient` (`app.py`) — **not** a `tw aiclient`
  subcommand (there is no `cmd_aiclient`; see [CLI Verbs](/architecture/cli-verbs.md)). The
  consolidated visual picker+create flow this document specifies is the target; the underlying
  data functions (`list_profile_summaries`, `create_profile`, `list_servers`, `player_bank`)
  already exist and are what a single surface would compose. Recorded, not silently conformed.

- **`tw players next` rotation selection and the rotation *driver* are both LIVE.**
  `player_bank.next_player` + `tw players next` (`players_cli.py`) pick a read-only next
  profile under a default 24h cooldown window. `player_bank.advance_rotation` + `tw players
  rotate` (WO-BUILD-PLAYER-BANK-ROTATION-DRIVER) wrap that same selector to report who's due
  as a first-class decision (`RotationDecision(name, reason)`) — still decide-and-report only,
  never a write: no `last_played` write path exists anywhere in this codebase today, so the
  driver never fabricates a play session. Neither logs in / auto-switches. The daemon-side
  consumer that would actually *act* on a driver decision (auto-login/auto-switch) remains a
  separate future wave.

- **`tw players list` is LIVE (WO-BUILD-TW-PLAYERS-LIST).** Prints the same
  `BOUNDARY_LINE_1` / `BOUNDARY_LINE_2` no-collusion lines as `BankViewScreen`, then
  metadata rows from `player_bank.list_players` (never logs in). Broken profiles are
  marked with `!` + an `error:` follow-up line on both CLI and TUI
  (`BankViewScreen` — WO-FIX-BANKVIEW-BROKEN-PROFILE-ERROR).

- **The no-collusion boundary is shown on the launcher bank view and on `tw players list`.**
  Doctrine + review still own enforcement (no code path can stop in-game manual transfers).

# Citations

- **Cross-links:**
  - /doctrine/secrets-and-credentials.md — the credential store, resolution precedence, redaction,
    and the credential-bank metadata-only discipline this surface relies on.
  - /engine/world-identity.md — the `host` + `game-letter` + `character` keying rule the selection
    establishes, and why all three are load-bearing.
  - /surfaces/trainer-cockpit.md — the destination this surface hands the chosen profile to; where
    the character binds to the App/Human mode-line strip.
  - /architecture/login-automaton.md — the classification-driven auto-login / new-character
    registration path that actually connects and (for `allow_register` profiles) generates and
    persists the password.
  - /doctrine/alignment-and-conduct.md — the canonical statement of the no-collusion /
    no-resource-transfer boundary shown at the rotation touchpoint.
  - /surfaces/mode-line-and-teach-controls.md — the App/Human dual mode line (no AI-drives slot) the
    chosen character strip appears on.

- **Design history:** DESIGN-v2.md (B1 profile/credential store, the launcher sketch); the
  `aiclient_ui.md` USERDOCS sketch (player/profile listing + known-server selection), re-rooted here
  in the reborn human-piloted vision; TW-31 credential-bank multi-player rotation; the WO-MS-1 server
  catalog and WO-MS-3/L0 probe work that built the known-server directory.

- **Code modules:** `credentials.py` (`list_profile_summaries`, `create_profile`, `load_profile`,
  `Profile`, env-first password resolution); `create_form_screen.py` (Create-New-Player TUI —
  server/game_letter/handle only; no secret fields); `world_identity.py` (`world_id`,
  `world_id_from_profile`); `catalog_cli.py` (`cmd_servers_list` / `tw servers list`);
  `players_cli.py` (`cmd_players_list` / `next` / `rotate` — no `add`); product entry
  `./tw2002-aiclient` / `python -m tw2002_aiclient` (`app.py` / `__main__.py` — not a `tw`
  subcommand); `session/player_bank.py` (metadata-only bank, secret-shaped-key notes filter);
  `config/servers.toml` (the tracked server catalog); `config/profiles.toml.example` (the tracked
  profile shape). Per CLAUDE.md's Architecture map and Hard rules: secrets never touch logs/argv/repo;
  `config/`, `run/`, `state/`, `logs/` are gitignored, with only `profiles.toml.example` and
  `servers.toml` tracked.
