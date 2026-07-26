# tw2002-aiclient

> **A human-piloted trainer for TradeWars 2002 — teach the App screens; invite an AI teacher when you want proposals. The AI never live-drives.**

[TradeWars 2002](https://en.wikipedia.org/wiki/TradeWars_2002) is the cult-classic
BBS space-trading game: a raw telnet stream of ANSI art, cryptic menus, and
haggling port merchants. It was never meant to be automated.

**tw2002-aiclient** is the reborn trainer for that world. A persistent daemon owns
the telnet connection and a real terminal emulator. **You** fly from the product
TUI (`./tw2002-aiclient`). The App carries only screens it has been *taught*
(deterministic macros / autopilot). An on-demand AI teacher may propose draft
rules when invited — every rule is human-approved before it can fire. Live
keystroke senders are `{app, human}` only.

### Product vs ops

| Surface | Role |
|---|---|
| `./tw2002-aiclient` | **Product TUI** — profile launcher, play shell / cockpit chrome. Human-facing client. |
| `./tw` | **Backend / ops CLI** — shipped verbs today: `status`, `ensure`, `screen`, `stop`, `do`, `send`, `read`, `history`, `watch`, `attach`, `menumap`, `loops`, `record` (table grows one WO at a time). |

Same daemon either way — one telnet connection. Prefer `./tw2002-aiclient` for day-to-day play; keep `./tw` for automation and ops. Further ops verbs (`spectate`, `autoloop`, …) are inventoried in [`workorders/WO-P2-OPS-VERB-SURFACE.md`](workorders/WO-P2-OPS-VERB-SURFACE.md) — not on `./tw --help` yet.


---

## What it does

**🕹️ You fly; the App carries taught screens.** The product surface is
`./tw2002-aiclient` — launcher → play shell / cockpit. The human is the sovereign
pilot. Deterministic App autopilot may run only on screens it has already been
taught; on an unrecognized screen it **stops and hands the keyboard back**.

**🔐 It logs itself in.** `tw ensure` is the one ops command for getting into the
game: it spawns the daemon if needed, then drives registration or login all the
way to the command prompt — picking the game, dismissing interstitials, even
registering a brand-new character and generating its password. Credentials live
in a chmod-600 local store (or an env var) and are redacted everywhere: your
password never appears in logs, argv, shell history, or any output. If the
connection drops, a background guardian reconnects and logs back in by itself.

**📺 Ops visibility today.** `tw status` / `tw screen` / `tw stop` / `tw do` /
`tw send` / `tw read` / `tw history` / `tw watch` / `tw attach` / `tw menumap` /
`tw loops` / `tw record` (plus `ensure`) are the shipped ops verbs. Most talk to
the daemon over a unix socket; `tw loops`, `tw record`, and (absent a live
localize) `tw menumap` read/write their own on-disk stores instead, so they
work with the daemon stopped.
Long-lived `tw spectate` and `tw state` (needs `state_parser`) are staged
in [`WO-P2-OPS-VERB-SURFACE.md`](workorders/WO-P2-OPS-VERB-SURFACE.md) — **not**
on `./tw --help` yet.

**🤖 AI is a spectator-teacher, not a live pilot.** When invited, a retrospective
AI teacher may propose draft rules or macros from history. Those drafts never
fire live until a human approves them. There is no "AI drives" mode.

**📈 Learning path (staged).** Trace ledger, macro record/replay, and loop mining
are part of the trainer vision; product cockpit chrome is landing panel-by-panel
under Phase-3 work orders. Do not expect `tw loops` / `tw autoloop` / a full
spectate dashboard on tip today.

**🧪 Built to be reliable.** Settle detection is the reliability core for any
future drive verb, and the stack — telnet negotiation, terminal emulation,
classification, login automaton, control lock, cockpit compose — is covered by a
large, fully network-free test suite driven by fake clocks and scripted sessions.

---

## How it fits together

One long-lived daemon, short-lived windows into it:

```
  you ──── ./tw2002-aiclient (play / cockpit) ──▶ ┌──────────────┐
                                                   │ twd (daemon) │ ── telnet ──▶ TW2002 server
  ops ─── tw ensure/status/…/attach/menumap/loops ▶│  the ONE     │
                                                   │  connection  │
  Coming: tw spectate · start · state · autoloop ─▶└──────────────┘
```

- **The daemon (`twd`)** owns the single telnet connection and a pyte terminal
  emulator, watches for settle edges when a drive verb needs them, and serves
  everything over a local unix socket. You never run it directly.
- **The CLI (`tw`)** is stateless: every verb connects, asks, prints, exits.
  Shipped today: `ensure`, `status`, `screen`, `stop`, `do`, `send`, `read`,
  `history`, `watch`, `attach`, `menumap`, `loops`, `record`. More verbs land
  one WO at a time — see the Verb reference and the ops WO. (`menumap`,
  `loops`, and `record` are daemon-free: they read/write their own on-disk
  stores, so they work with the daemon stopped.)
- **Product play** is `./tw2002-aiclient`, not `./tw`. Thin `tw attach` /
  `tw watch` / `tw menumap` / `tw loops` / `tw record` already ship on the
  same daemon; full-curses `tw spectate` (and `start` / `state` / `autoloop`)
  stay **Coming**.
- **A control lock** arbitrates the one connection: App (taught autopilot) or
  human at the keyboard — exactly one live driver at a time. The AI is never a
  live driver.

Deep architecture and rationale: see [`CLAUDE.md`](CLAUDE.md) and `canon/`
(north star: human sovereign · App taught-screen autopilot · AI teacher never
live-drives). Day-to-day cold-start (profiles, secrets, Mode chords, run-dir
isolation): [`canon/surfaces/operator-cold-start.md`](canon/surfaces/operator-cold-start.md).
Catalog / community directory sources:
[`canon/doctrine/server-catalog-sources.md`](canon/doctrine/server-catalog-sources.md).

---

## Quickstart

```bash
git clone <this repo> && cd tw2002-aiclient
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt     # one dependency: pyte
```

`./tw2002-aiclient` and `./tw` are self-locating — they run from anywhere by
absolute path, no venv activation needed.

**Product path** (launcher → create/select profile → play / cockpit):

```bash
./tw2002-aiclient --help    # title: tw2002-aiclient; points at ./tw for ops
./tw2002-aiclient           # curses product TUI (needs a real TTY)
```

**Ops / backend path** — get into the game (handles daemon spawn, login/registration,
credential storage) and check daemon health:

```bash
cp config/profiles.toml.example config/profiles.toml   # once; set host/game/handle
./tw ensure --profile default
./tw status
./tw screen            # current settled screen (read-only)
./tw do "d"            # send + wait for settle (App drive; control-lock gated)
# ./tw stop            # graceful daemon shutdown when you're done
```

Further ops verbs (`start`, `state`, `spectate`, `loops`, …) are **not
shipped yet** — see
[`workorders/WO-P2-OPS-VERB-SURFACE.md`](workorders/WO-P2-OPS-VERB-SURFACE.md).
Cold start without a separate `tw start`: use `tw ensure --profile …` (it spawns
the daemon when needed).

## Verb reference (shipped)

Everything takes `--json` for machine-parseable output where applicable.

| Verb | What it does |
|---|---|
| `tw ensure [target] --profile NAME` | **Auto-login.** Idempotent: spawn daemon if needed, register or log in, land at the command prompt. Covers cold start, mid-session, and post-drop recovery. |
| `tw status` | Daemon alive? Connected? Classification / idle-ms / run_dir. Always safe to run. |
| `tw screen [--raw] [--compact]` | Current settled screen (non-destructive; never sends). |
| `tw stop` | Graceful daemon shutdown (in-game QUIT when at main prompt; else disconnect). No-ops with a clear message if the daemon is already down. |
| `tw do "<input>"` | Send input, wait until settled, return the new screen + `settled_reason`. `--wait-prompt` is **case-sensitive**. Control-lock gated (`sender=app`). |
| `tw send "<input>"` | Raw send, no settle wait (rare / low-level). Control-lock gated. |
| `tw read` | Wait for settle and return the screen without sending. |
| `tw history [--n N]` | Recent verb/prompt entries from the live session history ring (secret inputs already redacted when recorded). |
| `tw watch [--frames N]` | Tail the settle-edge push-stream (read-only `subscribe`). Prints each event; `--frames N` exits after N events (else Ctrl-C). |
| `tw attach [--keys …]` | Take the control-lock and forward keystrokes (thin — no curses paint yet). TTY cbreak until Ctrl-]; `--keys` for scripted/non-TTY. **Warning:** `--keys` puts those bytes on **argv / process table / shell history** — never put a password or PIN there; use interactive attach (redacted) or env/`secrets.json` for credentials. |
| `tw menumap --path FILE` | Read-only menu-map inspector (coverage / dead-ends / orphans / you-are-here ★). Optional live localize via `screen` when daemon up; never sends. `--world-id` joins `state/world/<slug>/game_knowledge.json`. |
| `tw loops [--include-drafts]` | List the learned-loop (taught-macro) store in `state/skills/` — name, provenance, profit metadata, step count. Daemon-free; never sends. Drafts are inert until a human promotes them, so they list only on `--include-drafts` and are tagged `[DRAFT]`. An unreadable store never renders as an empty one: the report says so and the verb exits **1** (a partial read lists what it read, is marked INCOMPLETE, and exits 0). |
| `tw record MANIFEST [--draft]` | Write a taught macro from an already-captured demonstration manifest (assembled from real `tw do`/`tw screen --json` output) into `state/skills/`. Daemon-free; the recorder itself cannot send a keystroke. `expected_post_class` is always the live classifier's answer and `wait_prompt` is always escaped, never raw; a capture without a readable current sector is refused rather than saved without a `start_anchor`. Lands **blessed** by default (`--draft` writes to `state/skills/_drafts/` instead). See `loops/recorder.py` for the manifest shape and the live-attach follow-up this leaves on the table. |

### Coming (not on `./tw --help` yet)

Remaining classic ops verbs (`start`, `state`,
`autoloop`, …) are staged in
[`WO-P2-OPS-VERB-SURFACE.md`](workorders/WO-P2-OPS-VERB-SURFACE.md)
(A–C + E2 `watch` + F1 `attach` + G1 `menumap` + G3 `loops` shipped; ops
`tw spectate` **RETIRED / WONTBUILD**; **G2 EXECUTING** · G4 staged behind
G3 — see
[`WO-P2-OPS-VERB-G-PREP.md`](workorders/WO-P2-OPS-VERB-G-PREP.md)).

Notes worth knowing up front:

- The daemon is single-connection, single-session; its socket and pidfile live
  under the project directory (or `TW_RUN_DIR`) regardless of where you invoke `tw` from.
- Plain CLI output is deliberately color-stripped (token-efficient for agents).
- Product play / cockpit chrome is `./tw2002-aiclient`, not `./tw`.


## Spectator / attach

`tw attach` is **shipped** (thin): control-lock + keystroke forward; no live
screen paint yet — pair with `tw watch`. Secret keystrokes at password/PIN
prompts are redacted in the transcript log and `last_sent` via
`Session.send_raw` (ledger/`record_attach_keystroke` still cut).

**`--keys` hazard:** scripted keystrokes are ordinary CLI argv. They land in
shell history and the process table. Do **not** pass passwords/PINs via
`--keys` — that path is for non-secret automation only. Interactive attach
keeps secret prompts on the redaction sink (Invariant 1 in
[`canon/doctrine/secrets-and-credentials.md`](canon/doctrine/secrets-and-credentials.md)).

Ops `tw spectate` is **RETIRED / WONTBUILD** (Max `@ 13:13:55Z`) — in-cockpit
Spectate is LIVE via PWO-055; see
[`WO-P2-OPS-VERB-F-PREP.md`](workorders/WO-P2-OPS-VERB-F-PREP.md).


## Tests

```bash
.venv/bin/python -m pytest          # parallel by default (-n auto)
.venv/bin/python -m pytest -n0      # serial / single-process debug
```

The suite is entirely network-free: telnet negotiation (including commands split
across packet boundaries), terminal rendering, prompt classification against
real captured fixtures, settle timing on a fake clock, the login automaton's
registration and recovery branches, the control lock's one-driver guarantees,
and cockpit / play-shell compose against FakeClient and scripted sessions.

## Known limitations

- Live `./tw` verbs today are **`status` / `ensure` / `screen` / `stop` / `do` /
  `send` / `read` / `history` / `watch` / `attach` / `menumap` / `loops`**;
  `tw state` waits on a
  `state_parser` port; `tw start` / `tw spectate` intentionally not wired yet.
  Remaining slices in
  [`WO-P2-OPS-VERB-SURFACE.md`](workorders/WO-P2-OPS-VERB-SURFACE.md) land one WO at a time.
- `state` parsing (when wired) is a best-effort skeleton under `tw2002_aiclient.session`
  — extend anchors as new screen shapes turn up.
- `tw stop` attempts in-game QUIT from the main command prompt when possible;
  elsewhere the daemon disconnects and exits.
- Opening blurb / architecture prose used to narrate a live AI-pilot product;
  this README follows reborn canon (`canon/architecture/north-star.md`).


## Going deeper

- [`canon/`](canon/) — reborn OKF (start at [`canon/index.md`](canon/index.md) /
  [`canon/architecture/north-star.md`](canon/architecture/north-star.md)).
- [`CLAUDE.md`](CLAUDE.md) — seat, hard rules, setup.
- [`workorders/`](workorders/) — ordered rebuild queue (WO-00…WO-17 + Phase-2/3 WOs).
