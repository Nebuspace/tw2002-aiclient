"""tw — the one-shot CLI. Talks to `twd` over its unix socket.

Every verb is a single connect -> send JSON -> read JSON line -> disconnect
round trip, so a Bash-driving agent never has to hold a socket open
(DESIGN.md §3).
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = PROJECT_ROOT / "run"
LOG_DIR = PROJECT_ROOT / "logs"
SOCK_PATH = RUN_DIR / "twd.sock"
PID_PATH = RUN_DIR / "twd.pid"
DAEMON_SCRIPT = PROJECT_ROOT / "twd"


def send_request(verb, args, timeout=15):
    if not SOCK_PATH.exists():
        return {"ok": False, "error": "daemon_not_running"}
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(SOCK_PATH))
        payload = json.dumps({"verb": verb, "args": args}) + "\n"
        s.sendall(payload.encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    except OSError as e:
        return {"ok": False, "error": f"connect_failed:{e}"}
    finally:
        s.close()
    if not buf:
        return {"ok": False, "error": "empty_response"}
    try:
        return json.loads(buf.decode("utf-8"))
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"bad_response:{e}"}


def daemon_alive():
    if not PID_PATH.exists():
        return False
    try:
        pid = int(PID_PATH.read_text().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


# -- output -------------------------------------------------------------

def print_response(resp, args):
    if getattr(args, "json", False):
        print(json.dumps(resp))
        return
    if not resp.get("ok"):
        print(f"ERROR: {resp.get('error')}")
        return
    if "screen" in resp:
        for row in resp["screen"]:
            print(row)
        if not getattr(args, "compact", False):
            bits = []
            if resp.get("prompt"):
                bits.append(f"prompt: {resp['prompt']}")
            if resp.get("classification"):
                bits.append(f"class: {resp['classification']}")
            if resp.get("settled_reason"):
                bits.append(f"settled: {resp['settled_reason']}")
            if bits:
                print("--- " + " | ".join(bits))
    elif "history" in resp:
        for h in resp["history"]:
            print(f"[{h['ts']}] {h['verb']} {h.get('args')} -> {h['classification']} ({h['settled_reason']})")
    else:
        print(json.dumps(resp, indent=2))


# -- verb implementations -------------------------------------------------

def cmd_start(args):
    RUN_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)

    if daemon_alive() and SOCK_PATH.exists():
        status = send_request("status", {})
        if status.get("ok"):
            print("(daemon already running)")
            print_response(send_request("screen", {}), args)
            return

    from . import env
    try:
        host, port = env.resolve_host_port(args.host, args.port)
    except env.EnvResolutionError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    daemon_log = open(RUN_DIR / "twd.stderr.log", "ab")
    cmd = [
        str(DAEMON_SCRIPT),
        "--host", host,
        "--port", str(port),
        "--run-dir", str(RUN_DIR),
        "--log-dir", str(LOG_DIR),
    ]
    if args.name:
        cmd += ["--name", args.name]
    subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=daemon_log,
        stderr=daemon_log,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.time() + 10
    while time.time() < deadline and not SOCK_PATH.exists():
        time.sleep(0.1)
    if not SOCK_PATH.exists():
        print("ERROR: daemon failed to start (no socket after 10s) — see run/twd.stderr.log")
        sys.exit(1)

    resp = send_request("read", {"timeout": args.timeout}, timeout=args.timeout + 5)
    print_response(resp, args)


def cmd_screen(args):
    resp = send_request("screen", {"raw": args.raw})
    if args.compact and resp.get("ok"):
        resp.pop("state", None)
    print_response(resp, args)


def cmd_do(args):
    resp = send_request(
        "do",
        {
            "input": args.input,
            "enter": args.enter,
            "secret": args.secret,
            "wait_prompt": args.wait_prompt,
            "timeout": args.timeout,
        },
        timeout=args.timeout + 5,
    )
    print_response(resp, args)


def cmd_send(args):
    resp = send_request("send", {"input": args.input, "enter": args.enter, "secret": args.secret})
    print_response(resp, args)


def cmd_read(args):
    resp = send_request(
        "read", {"wait_prompt": args.wait_prompt, "timeout": args.timeout}, timeout=args.timeout + 5
    )
    print_response(resp, args)


def cmd_state(args):
    print_response(send_request("state", {}), args)


def cmd_history(args):
    print_response(send_request("history", {"n": args.n}), args)


def cmd_log(args):
    """§10 human-readable trail: Q -> keystroke -> result, per action.
    Reads `state/ledger.jsonl` directly rather than round-tripping the
    daemon (ledger.py owns the on-disk shape) -- works even with the
    daemon stopped, and needs no protocol.py change."""
    from . import ledger

    entries = ledger.read_entries()
    if args.n:
        entries = entries[-args.n:]
    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "entries": entries}))
        return
    if not entries:
        print("(ledger empty -- no do/send actions recorded yet)")
        return
    for entry in entries:
        print(ledger.render_trail_line(entry))


def cmd_analyze(args):
    """TW-12 / §15.6 session-retro: group ledger decisions by pattern and
    rank profitable recurrers as candidates to codify. Reads the ledger
    directly (daemon optional). Session key is a capture name, ISO-ts
    prefix, or `all` until TW-05 adds real session_id."""
    from . import analyze

    report = analyze.analyze_session(
        args.session,
        min_support=args.min_support,
        top_k=args.top,
    )
    if getattr(args, "json", False):
        print(json.dumps({"ok": True, **report}))
        return
    print(analyze.format_report(report))


def cmd_servers_list(args):
    """WO-MS-1: print the config/servers.toml catalog (no live connections)."""
    from . import servers as servers_mod

    rows = servers_mod.list_servers()
    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "servers": rows, "count": len(rows)}))
        return
    print(f"{'KEY':<28} {'HOST':<36} {'PORT':>5} {'FE':<7} {'STATUS'}")
    for r in rows:
        print(
            f"{r['key']:<28} {r['hostname']:<36} {r['port']:>5} "
            f"{r['front_end']:<7} {r['status']}"
        )
    print(f"({len(rows)} servers)")


def cmd_players_list(args):
    """TW-31 CLI wiring (v1): list the multi-character rotation bank.
    Pure client-side, direct `state/player_bank.json` read -- no daemon
    socket round trip, same pattern as `cmd_log` reading
    `state/ledger.jsonl` directly. `player_bank.load_bank()` never
    creates the file on a miss (just returns an empty in-memory bank),
    so an absent bank shows the hint below without ever touching disk."""
    from . import player_bank

    bank = player_bank.load_bank()
    players = bank["players"]
    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "players": players}))
        return
    if not players:
        print("(player bank empty -- add a character with `tw players add <profile-name>`)")
        return
    for p in players:
        last_played = p.get("last_played") or "never"
        print(
            f"{p['name']:<16} {p['handle']:<16} {p['host']:<24} "
            f"{p['game_letter']:<3} {last_played:<21} {p.get('turns_state', '')}"
        )


def cmd_players_add(args):
    """Add a character from an EXISTING `config/profiles.toml` profile.
    Only ever takes a profile NAME -- `player_bank.add_player` pulls
    handle/host/port/game_letter from the profile itself via
    `credentials.load_profile`, so a bank entry can never drift from
    the profile actually used to connect. No password anywhere near
    this path: `credentials.Profile` has no password field at all."""
    from . import credentials, player_bank

    notes = _parse_params(args.note, flag="--note") if args.note else None
    try:
        entry = player_bank.add_player(args.profile, notes=notes)
    except (player_bank.PlayerBankError, credentials.CredentialError) as e:
        # add_player calls credentials.load_profile() internally (an
        # unknown/incomplete profile raises CredentialError, not
        # PlayerBankError) -- both are the same "clean error, exit 1"
        # case from this verb's point of view.
        print(f"ERROR: {e}")
        sys.exit(1)
    print(f"added {entry['name']} ({entry['handle']})")


def cmd_players_next(args):
    """Pure rotation-order query (`player_bank.next_player`) -- reads
    the bank but decides and writes nothing; the daemon-side rotation
    driver that actually acts on this is a later, separate wave."""
    from . import player_bank

    bank = player_bank.load_bank()
    name = player_bank.next_player(bank, current=args.current)
    if name is None:
        print("none: all players exhausted")
    else:
        print(name)


def cmd_status(args):
    if not daemon_alive():
        resp = {"ok": True, "daemon_running": False, "connected": False}
        print_response(resp, args)
        return
    resp = send_request("status", {})
    resp["daemon_running"] = True
    print_response(resp, args)


def cmd_stop(args):
    if not daemon_alive():
        print("daemon not running")
        return
    resp = send_request("stop", {})
    print_response(resp, args)


def cmd_ensure(args):
    """B4: the ONE command the LLM calls for auto-login. Classifies the
    current screen; if already at `target`, no-ops. Else drives the
    login automaton (B1/B3) using the profile's stored/generated
    credential (B2) all the way to `target`, spawning the daemon first
    (D9's CLI-level reconnect path) if none is running -- so this single
    verb covers cold-start, mid-session, AND post-drop recovery."""
    from . import credentials

    RUN_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)

    try:
        profile = credentials.load_profile(args.profile)
    except credentials.CredentialError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    if not (daemon_alive() and SOCK_PATH.exists()):
        daemon_log = open(RUN_DIR / "twd.stderr.log", "ab")
        cmd = [
            str(DAEMON_SCRIPT),
            "--host", profile.host,
            "--port", str(profile.port),
            "--run-dir", str(RUN_DIR),
            "--log-dir", str(LOG_DIR),
        ]
        subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=daemon_log,
            stderr=daemon_log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = time.time() + 10
        while time.time() < deadline and not SOCK_PATH.exists():
            time.sleep(0.1)
        if not SOCK_PATH.exists():
            print("ERROR: daemon failed to start (no socket after 10s) — see run/twd.stderr.log")
            sys.exit(1)
        # Let the fresh connection produce its first settled screen
        # before driving it — mirrors `tw start`.
        send_request("read", {"timeout": args.timeout}, timeout=args.timeout + 5)

    resp = send_request(
        "ensure",
        {"target": args.target, "profile": args.profile},
        timeout=args.timeout + 5,
    )
    print_response(resp, args)
    if not resp.get("ok"):
        sys.exit(1)


def _parse_params(pairs, flag="--param"):
    """`--param k=v` (repeatable) -> {"k": "v", ...} for skill template
    substitution (twclient.skills._apply_params). Also reused by `tw
    players add --note k=v` (flag="--note") -- identical k=v shape,
    just a different caller-facing flag name in the error message."""
    params = {}
    for pair in pairs:
        if "=" not in pair:
            print(f"ERROR: {flag} must be k=v, got {pair!r}")
            sys.exit(1)
        k, v = pair.split("=", 1)
        params[k] = v
    return params


def cmd_record(args):
    """v2.1 item 11b (C3): `tw record start [name]` opens a named skill
    capture -- every `do` sent while it's open becomes a step; `tw
    record stop` saves the accumulated steps as a replayable skill at
    state/skills/<name>.json."""
    if args.action == "start":
        resp = send_request("record_start", {"name": args.name})
    else:
        resp = send_request("record_stop", {})
    print_response(resp, args)
    if not resp.get("ok"):
        sys.exit(1)


def cmd_replay(args):
    """v2.1 item 11b: re-issue a saved skill's steps, validating each
    one's actual post-classification against what was recorded/mined --
    halts on the first divergence rather than pressing on blind."""
    params = _parse_params(args.param)
    resp = send_request(
        "replay",
        {"name": args.name, "params": params, "step_timeout": args.step_timeout, "force": args.force},
        timeout=args.timeout + 5,
    )
    print_response(resp, args)
    if not resp.get("ok"):
        sys.exit(1)


def cmd_mine(args):
    """v2.1 item 11c (C10): mine the Trace-Ledger for recurring
    profitable input-subsequences, proposing the top ones as draft
    skills at state/skills/_drafts/ for an AI/human to bless."""
    resp = send_request("mine", {"min_support": args.min_support}, timeout=30)
    if not getattr(args, "json", False) and resp.get("ok"):
        patterns = resp.get("patterns", [])
        if not patterns:
            print("(no recurring patterns found -- ledger may be too short yet)")
        for p in patterns[:10]:
            cr_t = p["cr_per_turn"]
            cr_t_str = f"{cr_t:.1f}" if cr_t is not None else "n/a"
            print(
                f"pre={p['pre_class']} inputs={p['inputs']} -> post={p['post_class']} "
                f"support={p['support']} cr/turn={cr_t_str} cr/action={p['cr_per_action']:.1f}"
            )
        for d in resp.get("drafts", []):
            print(f"DRAFT skill saved: {d['name']} -> {d['path']}")
        return
    print_response(resp, args)


def cmd_play(args):
    """v2.1 item 11d: run a learned skill autonomously for --cycles
    rounds, halting on the first surprise (post-class divergence, or an
    unmodeled/`unknown` screen) or a rail (--cycles cap / --floor
    stop-loss). Watch it happen live in a separate terminal with `tw
    watch` / `tw spectate` -- this dispatch runs the whole loop and
    returns the full per-cycle trace, the same shape as `ensure`."""
    params = _parse_params(args.param)
    resp = send_request(
        "play",
        {
            "name": args.name,
            "cycles": args.cycles,
            "floor": args.floor,
            "params": params,
            "step_timeout": args.step_timeout,
            "force": args.force,
        },
        timeout=args.timeout + 5,
    )
    if not getattr(args, "json", False) and resp.get("ok"):
        print(f"halted: {resp.get('halted')} after {resp.get('cycles_completed')} cycle(s)")
        for c in resp.get("trace", []):
            for s in c["steps"]:
                print(f"  cycle {c['cycle']} step {s['step']}: {s['input']!r} -> {s['actual']} (expected {s['expected']})")
        divergence = resp.get("divergence")
        if divergence:
            print(
                f"  DIVERGENCE at step {divergence['step_i']}: "
                f"expected {divergence['expected']!r} got {divergence['actual']!r}"
            )
        return
    print_response(resp, args)
    if not resp.get("ok"):
        sys.exit(1)


def cmd_haggle(args):
    """DESIGN-v2.md §9: deterministic auto-haggle, NO LLM -- negotiates
    the OFFER sub-dialogue the session must already be sitting at (drive
    the quantity/commodity selection with ordinary `do` calls first, the
    same as any other port-trade step). Prints the outcome, round count,
    and final price; the settled screen follows the same shape as `tw
    do`/`tw screen`."""
    resp = send_request(
        "haggle",
        {
            "fair_value": args.fair_value,
            "accept_threshold_pct": args.accept_threshold_pct,
            "open_aggression_pct": args.open_aggression_pct,
            "round_cap": args.round_cap,
            "step_timeout": args.step_timeout,
        },
        timeout=args.step_timeout * args.round_cap + 10,
    )
    if not getattr(args, "json", False) and resp.get("ok"):
        h = resp.get("haggle", {})
        print(
            f"haggle: {h.get('outcome')} (resolved={h.get('resolved')}, rounds={h.get('rounds')}, "
            f"direction={h.get('direction')}, fair_value={h.get('fair_value')}, final_price={h.get('final_price')})"
        )
    print_response(resp, args)
    if not resp.get("ok"):
        sys.exit(1)


def cmd_loops(args):
    """Trainer Control Panel (TUI-POLISH-PLAN.md): list every learned
    loop (recorded +, with --include-drafts, miner-drafted skills) with
    browsable metadata -- the CLI-scriptable twin of `tw spectate`'s
    in-TUI Learned-Loops Library (`L`)."""
    resp = send_request("list_skills", {"include_drafts": args.include_drafts})
    if not getattr(args, "json", False) and resp.get("ok"):
        loops = resp.get("loops", [])
        if not loops:
            print("(no learned loops yet -- `tw record`/`tw mine` first)")
        for loop in loops:
            profit = loop.get("profit_per_turn")
            if profit is not None:
                profit_text = f"{profit:+.1f}cr/turn"
            elif loop.get("demo_profit") is not None:
                profit_text = f"{loop['demo_profit']:+,}cr demo"
            else:
                profit_text = "-"
            tag = "[DRAFT] " if loop.get("draft") else ""
            print(f"{tag}{loop['name']:<28} {loop['source']:<9} {profit_text:>14} {loop['steps']:>3} steps")
        return
    print_response(resp, args)
    if not resp.get("ok"):
        sys.exit(1)


def cmd_autoloop(args):
    """Trainer Control Panel: start/stop/pause/resume the daemon's
    background AUTO-LOOP driver (loop_player.py) -- the CLI-scriptable
    twin of the in-TUI control strip's run controls. Unlike `tw play`
    (synchronous -- blocks the calling connection until the whole run
    completes), `start` returns immediately once armed; watch progress
    live with `tw spectate` (the control strip's own progress bar) or
    `tw watch` (raw "play_progress" events)."""
    if args.action == "start":
        params = _parse_params(args.param)
        resp = send_request(
            "play_start",
            {
                "name": args.name,
                "cycles": args.cycles,
                "floor": args.floor,
                "params": params,
                "step_timeout": args.step_timeout,
            },
        )
    elif args.action == "stop":
        resp = send_request("play_stop", {})
    elif args.action == "pause":
        resp = send_request("play_pause", {})
    else:
        resp = send_request("play_resume", {})
    print_response(resp, args)
    if not resp.get("ok"):
        sys.exit(1)


def cmd_spectate(args):
    from . import spectate_app

    if not SOCK_PATH.exists():
        print("ERROR: daemon_not_running — start it first with `tw start`")
        sys.exit(1)
    if args.snapshot:
        code = spectate_app.run_snapshot(SOCK_PATH, PID_PATH, frames=args.frames)
    else:
        if not sys.stdout.isatty():
            print("ERROR: tw spectate needs a real terminal (not a TTY) — use --snapshot for scripted/Bash use")
            sys.exit(1)
        code = spectate_app.run_interactive(SOCK_PATH, PID_PATH)
    sys.exit(code)


def cmd_attach(args):
    """Interactive live console (companion to `tw spectate`, which stays
    read-only): take the keyboard and drive the daemon's single game
    connection directly, in real color, until Ctrl-] hands control back
    to the AI. Rejected up front (before curses starts) if another
    human session is already attached -- see interactive_app.py's
    control-lock handshake."""
    from . import interactive_app

    if not SOCK_PATH.exists():
        print("ERROR: daemon_not_running — start it first with `tw start`")
        sys.exit(1)
    if not sys.stdout.isatty():
        print("ERROR: tw attach needs a real terminal (not a TTY) — this verb is interactive-only")
        sys.exit(1)
    code = interactive_app.run_interactive_attach(SOCK_PATH, PID_PATH)
    sys.exit(code)


def cmd_watch(args):
    """Tail the settle-edge push-stream (A1). Read-only — subscribing
    never sends input to the game. `--frames N` exits after N events so
    this is capturable in a Bash transcript; with no --frames it runs
    until Ctrl-C (SIGINT cleanly closes the socket, detaching without
    touching the daemon or the game session)."""
    if not SOCK_PATH.exists():
        print("ERROR: daemon_not_running")
        sys.exit(1)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(str(SOCK_PATH))
        s.sendall((json.dumps({"verb": "subscribe", "args": {}}) + "\n").encode("utf-8"))
    except OSError as e:
        print(f"ERROR: connect_failed:{e}")
        sys.exit(1)
    f = s.makefile("rb")
    count = 0
    try:
        while True:
            line = f.readline()
            if not line:
                break
            try:
                event = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            print_response(event, args)
            count += 1
            if args.frames is not None and count >= args.frames:
                break
    except KeyboardInterrupt:
        pass
    finally:
        s.close()


# -- argparse wiring -------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="tw")
    sub = p.add_subparsers(dest="verb", required=True)

    def add_json(sp):
        sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")

    def add_enter(sp):
        sp.add_argument("--enter", action="store_true", default=True, help="append \\r\\n (default)")
        sp.add_argument("--no-enter", dest="enter", action="store_false")

    sp = sub.add_parser("start", help="spawn the daemon, connect, return the first settled screen")
    sp.add_argument("--host", default=None, help="defaults via TW2002_HOST / .env / profiles.toml -- see twclient/env.py")
    sp.add_argument("--port", type=int, default=None, help="defaults via TW2002_PORT / .env / profiles.toml -- see twclient/env.py")
    sp.add_argument("--name", default=None)
    sp.add_argument("--timeout", type=float, default=10.0)
    add_json(sp)
    sp.set_defaults(func=cmd_start)

    sp = sub.add_parser("screen", help="current settled screen (non-destructive)")
    sp.add_argument("--compact", action="store_true")
    sp.add_argument("--raw", action="store_true", help="uncropped 80x25 grid")
    add_json(sp)
    sp.set_defaults(func=cmd_screen)

    sp = sub.add_parser("do", help="send input, wait for settle, return the new screen")
    sp.add_argument("input")
    add_enter(sp)
    sp.add_argument("--secret", action="store_true", help="password entry — never persisted to the transcript log")
    sp.add_argument("--wait-prompt", default=None)
    sp.add_argument("--timeout", type=float, default=8.0)
    add_json(sp)
    sp.set_defaults(func=cmd_do)

    sp = sub.add_parser("send", help="raw send, no wait (rare/low-level)")
    sp.add_argument("input")
    sp.add_argument("--secret", action="store_true", help="password entry — never persisted to the transcript log")
    add_enter(sp)
    add_json(sp)
    sp.set_defaults(func=cmd_send)

    sp = sub.add_parser("read", help="wait-and-return without sending")
    sp.add_argument("--wait-prompt", default=None)
    sp.add_argument("--timeout", type=float, default=8.0)
    add_json(sp)
    sp.set_defaults(func=cmd_read)

    sp = sub.add_parser("state", help="parsed structured game-state only")
    add_json(sp)
    sp.set_defaults(func=cmd_state)

    sp = sub.add_parser("history", help="recent screens/commands")
    sp.add_argument("--n", type=int, default=20)
    add_json(sp)
    sp.set_defaults(func=cmd_history)

    sp = sub.add_parser(
        "log",
        aliases=["trail"],
        help=(
            "human-readable trace log -- per action: the game's QUESTION, the highlighted "
            "KEYSTROKE, the RESULT (reads state/ledger.jsonl directly; no daemon required)"
        ),
    )
    sp.add_argument("--n", type=int, default=20, help="most recent N entries (default: 20)")
    add_json(sp)
    sp.set_defaults(func=cmd_log)

    sp = sub.add_parser("status", help="daemon alive? connected? idle-ms? classification?")
    add_json(sp)
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("stop", help="graceful in-game QUIT, disconnect, daemon exit")
    add_json(sp)
    sp.set_defaults(func=cmd_stop)

    sp = sub.add_parser(
        "ensure",
        help=(
            "idempotent auto-login (B4) — the ONE command an LLM calls: classifies the "
            "current screen, no-ops if already there, else drives registration/login (B1/B3) "
            "using the profile's stored/generated credential (B2), spawning the daemon first "
            "if needed (covers cold-start and post-drop recovery alike)"
        ),
    )
    sp.add_argument("target", nargs="?", default="main_command", help="target classification (default: main_command)")
    sp.add_argument("--profile", required=True, help="profile name in config/profiles.toml")
    sp.add_argument("--timeout", type=float, default=180.0, help="overall budget for the login automaton")
    add_json(sp)
    sp.set_defaults(func=cmd_ensure)

    sp = sub.add_parser(
        "record",
        help="bracket a named skill capture (C3): `tw record start [name]` ... play ... `tw record stop`",
    )
    sp.add_argument("action", choices=["start", "stop"])
    sp.add_argument("name", nargs="?", default=None, help="capture name (start only; auto-generated if omitted)")
    add_json(sp)
    sp.set_defaults(func=cmd_record)

    sp = sub.add_parser(
        "replay",
        help="re-issue a saved skill's steps, halting on divergence from what was recorded/mined",
    )
    sp.add_argument("name", help="skill name saved via `tw record` or blessed from a mined draft")
    sp.add_argument("--param", action="append", default=[], metavar="k=v", help="template substitution (repeatable)")
    sp.add_argument("--step-timeout", type=float, default=8.0, help="per-step settle timeout")
    sp.add_argument("--timeout", type=float, default=60.0, help="overall client-socket budget")
    sp.add_argument(
        "--force", action="store_true",
        help="TW-03: waive a missing/legacy start_anchor (never bypasses a DETECTED sector mismatch)",
    )
    add_json(sp)
    sp.set_defaults(func=cmd_replay)

    sp = sub.add_parser(
        "mine",
        aliases=["patterns"],
        help="mine the Trace-Ledger (C10) for recurring profitable input-subsequences; proposes drafts",
    )
    sp.add_argument("--min-support", type=int, default=2, help="minimum recurrence count to surface a pattern")
    add_json(sp)
    sp.set_defaults(func=cmd_mine)

    sp = sub.add_parser(
        "analyze",
        help=(
            "session-retro (TW-12 / §15.6): read a ledger slice, group recurring decisions, "
            "rank profitable ones as candidates to codify — <session> is a capture name, "
            "ISO-ts prefix, or 'all' (real session_id arrives with TW-05)"
        ),
    )
    sp.add_argument(
        "session",
        help="capture name, timestamp prefix (e.g. 2026-07-19), or 'all'",
    )
    sp.add_argument("--min-support", type=int, default=2, help="minimum recurrence to surface a pattern")
    sp.add_argument("--top", type=int, default=20, help="max candidates to print")
    add_json(sp)
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser(
        "players",
        help=(
            "multi-character rotation bank (TW-31): list (default) / add / next -- pure "
            "client-side, reads/writes state/player_bank.json directly, no daemon involved"
        ),
    )
    add_json(sp)
    sp.set_defaults(func=cmd_players_list, players_action=None)
    # Nested subparsers (rather than a single flat verb) because add/next
    # take genuinely different arguments -- a positional profile name +
    # repeatable --note vs. an optional --current -- unlike record/autoloop's
    # action choices, which all share one option set.
    players_sub = sp.add_subparsers(dest="players_action")

    sp_add = players_sub.add_parser(
        "add", help="add a player from an existing config/profiles.toml profile"
    )
    sp_add.add_argument("profile", help="profile name in config/profiles.toml")
    sp_add.add_argument(
        "--note", action="append", default=[], metavar="k=v",
        help="scalar note, repeatable (password-shaped keys are refused)",
    )
    sp_add.set_defaults(func=cmd_players_add)

    sp_next = players_sub.add_parser(
        "next",
        help="who's up next in rotation order (least-recently-played among non-exhausted players)",
    )
    sp_next.add_argument(
        "--current", default=None,
        help="rotate away from this player if they're the single most-overdue",
    )
    sp_next.set_defaults(func=cmd_players_next)

    sp = sub.add_parser(
        "play",
        help="run a learned skill autonomously for N cycles; halts on surprise or a rail (--cycles/--floor)",
    )
    sp.add_argument("name", help="skill name to play")
    sp.add_argument("--cycles", type=int, default=1, help="hard cap on repetitions (rails, capped at 50)")
    sp.add_argument(
        "--floor", type=float, default=None, help="stop-loss: halt before any cycle that would start at/below this credits balance"
    )
    sp.add_argument("--param", action="append", default=[], metavar="k=v", help="template substitution (repeatable)")
    sp.add_argument("--step-timeout", type=float, default=8.0, help="per-step settle timeout")
    sp.add_argument("--timeout", type=float, default=600.0, help="overall client-socket budget")
    sp.add_argument(
        "--force", action="store_true",
        help="TW-03: waive a missing/legacy start_anchor (never bypasses a DETECTED sector mismatch)",
    )
    add_json(sp)
    sp.set_defaults(func=cmd_play)

    sp = sub.add_parser(
        "haggle",
        help=(
            "deterministic auto-haggle (DESIGN-v2 §9), NO LLM -- negotiates the OFFER "
            "sub-dialogue the session must already be sitting at (drive quantity/commodity "
            "selection with `tw do` first)"
        ),
    )
    sp.add_argument("--fair-value", dest="fair_value", type=float, default=None, help="override the port's own baseline as the reference price")
    sp.add_argument("--accept-threshold-pct", type=float, default=5.0, help="accept once the port's quote is within this %% of fair value")
    sp.add_argument("--open-aggression-pct", type=float, default=15.0, help="how far off fair value the opening counter-offer starts")
    sp.add_argument("--round-cap", type=int, default=4, help="max negotiation rounds before the safe accept-default fallback")
    sp.add_argument("--step-timeout", type=float, default=8.0, help="per-round settle timeout")
    add_json(sp)
    sp.set_defaults(func=cmd_haggle)

    sp = sub.add_parser(
        "loops",
        help="list every learned loop (recorded/mined skills) with profit metadata -- the CLI twin of the in-TUI Learned-Loops Library",
    )
    sp.add_argument("--include-drafts", action="store_true", help="also list miner-drafted (unblessed) skills")
    add_json(sp)
    sp.set_defaults(func=cmd_loops)

    sp = sub.add_parser(
        "autoloop",
        help="start/stop/pause/resume the background AUTO-LOOP driver (Trainer Control Panel) -- unlike `tw play`, `start` returns immediately",
    )
    sp.add_argument("action", choices=["start", "stop", "pause", "resume"])
    sp.add_argument("name", nargs="?", default=None, help="skill name to run (start only)")
    sp.add_argument("--cycles", type=int, default=1, help="hard cap on repetitions (start only; rails, capped at 50)")
    sp.add_argument(
        "--floor", type=float, default=None,
        help="stop-loss: halt before any cycle that would start at/below this credits balance (start only)",
    )
    sp.add_argument("--param", action="append", default=[], metavar="k=v", help="template substitution (start only, repeatable)")
    sp.add_argument("--step-timeout", type=float, default=8.0, help="per-step settle timeout (start only)")
    add_json(sp)
    sp.set_defaults(func=cmd_autoloop)

    sp = sub.add_parser("watch", help="tail the settle-edge push-stream (read-only spectator feed)")
    sp.add_argument("--frames", type=int, default=None, help="exit after N events (default: until Ctrl-C)")
    add_json(sp)
    sp.set_defaults(func=cmd_watch)

    sp = sub.add_parser(
        "spectate",
        help=(
            "standalone spectator dashboard — run in your OWN terminal any time after "
            "`tw start`; attaches to the running daemon and watches live, decoupled from "
            "whoever/whatever is driving, zero coordination needed"
        ),
    )
    sp.add_argument(
        "--snapshot",
        action="store_true",
        help="proof/scripting variant: print dashboard frame(s) to stdout, no curses (the interactive "
        "dashboard with no flags is the real deliverable)",
    )
    sp.add_argument("--frames", type=int, default=1, help="with --snapshot, how many frames to print")
    sp.set_defaults(func=cmd_spectate)

    sp = sub.add_parser(
        "attach",
        help=(
            "interactive live console — take the keyboard and play as the player yourself, "
            "in real color, over the daemon's single game connection; Ctrl-] hands control "
            "back to the AI. `tw spectate` stays the read-only view; this is the driving seat."
        ),
    )
    sp.set_defaults(func=cmd_attach)

    # WO-MS-1 — server catalog (announce-first shared cli.py edit)
    servers_p = sub.add_parser("servers", help="list / inspect the config/servers.toml catalog")
    servers_sub = servers_p.add_subparsers(dest="servers_cmd", required=True)
    sp_list = servers_sub.add_parser("list", help="list all cataloged servers")
    sp_list.set_defaults(func=cmd_servers_list)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
