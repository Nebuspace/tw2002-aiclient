# tw2002-aiclient

> **You fly TradeWars 2002. The app carries only the screens you've taught it. An AI teacher
> can help you teach — it never touches the keyboard itself.**

[TradeWars 2002](https://en.wikipedia.org/wiki/TradeWars_2002) is the cult-classic BBS
space-trading game — a raw telnet stream of ANSI art, cryptic menus, and haggling port
merchants. **tw2002-aiclient** is a trainer built on top of it: a persistent daemon holds your
one telnet connection open, and you fly from a curses cockpit. Any screen the app already knows
how to handle, it can carry for you. Anything it doesn't recognize, it stops and hands the
keyboard straight back — no guessing, ever.

## Install

```bash
git clone <this repo> && cd tw2002-aiclient
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # one dependency: pyte
```

`./tw2002-aiclient` finds its own venv by absolute path — run it from anywhere, no
`source .venv/bin/activate` needed.

## Play

```bash
./tw2002-aiclient
```

That's the one command. It opens a profile picker in your terminal (needs a real TTY, not a
pipe or a plain log):

- **No profiles yet?** The picker's only option is **Create New Player** — pick a server from
  the built-in catalog, a game letter, and your handle. It writes the profile for you; there's
  no password field here (see [Your credentials](#your-credentials) below).
- **Already have profiles?** ↑/↓ to pick one, **Enter** to fly it, **q** to quit.

Picking a profile connects, logs you in — registering a brand-new character and generating its
password if that's what you asked for — and drops you into the cockpit. If the connection ever
drops mid-session, a background guardian reconnects and logs back in on its own; you don't have
to babysit the socket.

## How the autopilot works

The app only ever does what you've taught it. It recognizes a screen, matches it against a rule
you (or the AI, with your approval) recorded earlier, and plays back the keystrokes. The moment
it meets a screen it doesn't recognize, **it stops and gives you the keyboard back** — that's
not a bug, that's the whole design.

When that happens, you have three moves:

1. **Just play it yourself** — the way you would with any BBS door game.
2. **Record it** as a macro, so the app handles this exact prompt itself next time.
3. **Ask the AI teacher to look at it afterward** — it reviews what happened and proposes a rule
   for you to approve.

Every one of those is a deposit into the app's growing repertoire. **The AI never drives live** —
not on its own initiative, and not even if you offer it the keyboard mid-session. It only ever
*proposes*, after the fact, and only when you ask.

The cockpit and the taught-screen library are both still growing session over session — don't
expect either to know everything on day one; an unrecognized screen handing control back to you
is the app being honest, not broken.

## Your credentials

Profiles (server, handle, game letter) live in `config/profiles.toml`, copied from
`config/profiles.toml.example` — gitignored, so it's yours alone. Passwords never live in that
file: they're resolved from a `TW2002_PASSWORD_<PROFILE>` environment variable first, or a
chmod-600 `config/secrets.json` otherwise (registering a new character writes its generated
password there for you). Either way, a password never appears in a log, an argument list, your
shell history, or this repo.

## Under the hood

One long-lived daemon (`twd`) owns your single telnet connection and a real terminal emulator; a
control lock makes sure exactly one thing — you, or the taught autopilot — is driving at any
instant. It's backed by a large, fully network-free test suite (fake clocks, scripted sessions,
real captured screen fixtures), so "taught" behavior stays taught as the app grows.

## For agents & automation

`./tw2002-aiclient` is the only executable a player needs. A second command, `./tw`, drives the
same daemon headlessly for scripts and AI agents (`ensure`, `status`, `do`, and friends) — run
`./tw --help` for the current list, and see [`CLAUDE.md`](CLAUDE.md) for how it fits into the
project. You won't need it to play.

## Going deeper

- [`canon/architecture/north-star.md`](canon/architecture/north-star.md) — the vision this
  trainer is built to: human sovereign, app taught-screen autopilot, AI teacher that never
  live-drives.
- [`canon/index.md`](canon/index.md) — the full design bundle.
- [`CLAUDE.md`](CLAUDE.md) — project setup, seat, and hard rules (mostly for contributors and
  agents).
- [`workorders/`](workorders/) — the ordered build queue this trainer is being rebuilt from.
