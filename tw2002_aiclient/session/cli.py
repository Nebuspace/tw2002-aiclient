"""``tw`` — the backend/ops CLI. Talks to ``twd`` over its unix socket.

Most verbs are a single connect -> send JSON -> read JSON line -> disconnect
round trip. ``tw watch`` is the exception: a lifetime ``subscribe`` stream
(NDJSON settle-edge events) until ``--frames N`` or Ctrl-C (see canon
`architecture/session-engine.md`). Verb table grows one WO at a time;
``ensure``/``status`` land under WO-P2-020 -- APPEND new verbs to
``build_parser()``, never rewrite an already-landed one.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import argparse

from . import credentials, env


class ProfileResolutionError(Exception):
    """Raised when a profile name cannot be resolved to a connectable
    (host, port) -- missing section, missing host/port, or an unknown
    `server` catalog key."""


def _resolve_run_dir(run_dir_arg: str | None) -> Path:
    """Layer a per-invocation `--run-dir` CLI override on top of
    `env.resolve_run_dir()`'s `TW_RUN_DIR`-env-var default (e.g.
    `--run-dir run/ona` for an isolated daemon socket)."""
    if run_dir_arg is None:
        return env.resolve_run_dir()
    p = Path(run_dir_arg)
    return p if p.is_absolute() else (env.PROJECT_ROOT / p)


def _resolve_profile_connection(profile_name: str) -> tuple[str, int]:
    """Resolve `profile_name`'s (host, port) via the ONE shared resolver,
    `credentials.resolve_profile_host_port` (OPEN-003-A) -- replacing this
    function's own local catalog/host-port read, a divergent copy of the
    same logic `credentials.py`'s own docstring flags as superseded.
    Re-raised as this module's own `ProfileResolutionError` so
    `ensure_raw`'s existing `except ProfileResolutionError` catch (and any
    caller monkeypatching this function directly) keeps working unchanged.

    Precedence note (OPEN-003-A, no partial merge): a profile with a
    `server` catalog key AND only one of `host`/`port` set no longer
    merges the two -- the shared resolver treats explicit `host=`+`port=`
    as an all-or-nothing override and otherwise resolves fully off the
    catalog. Only affects a profile that mixes both forms, which was
    never a documented/supported shape.
    """
    try:
        return credentials.resolve_profile_host_port(profile_name)
    except credentials.ProfileConnectionError as e:
        raise ProfileResolutionError(str(e)) from e


# -- daemon transport -----------------------------------------------------

def send_request(verb, args_payload, *, timeout=15.0, run_dir=None):
    """One connect -> send one JSON line -> read one JSON line -> close
    round trip against `env.socket_path(run_dir)`. Never raises for an
    expected failure mode -- always returns a dict, `{"ok": False,
    "error": ...}` on any transport problem."""
    sock_path = env.socket_path(run_dir)
    if not sock_path.exists():
        return {"ok": False, "error": "daemon_not_running"}
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(sock_path))
        payload = json.dumps({"verb": verb, "args": args_payload}) + "\n"
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


def daemon_alive(run_dir=None):
    pid_path = env.pid_path(run_dir)
    if not pid_path.exists():
        return False
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


# -- output -----------------------------------------------------------------

def print_response(resp, args):
    if getattr(args, "json", False):
        print(json.dumps(resp))
        return
    if not resp.get("ok"):
        print(f"ERROR: {resp.get('error')}")
        if resp.get("detail"):
            print(f"  detail: {resp['detail']}")
        return
    if "screen" in resp:
        for row in resp["screen"]:
            print(row)
        if not getattr(args, "compact", False):
            bits = []
            if resp.get("prompt"):
                bits.append(f"prompt: {resp['prompt']}")
            if resp.get("classification") or resp.get("class"):
                bits.append(f"class: {resp.get('classification') or resp.get('class')}")
            if resp.get("settled_reason"):
                bits.append(f"settled: {resp['settled_reason']}")
            if bits:
                print("--- " + " | ".join(bits))
    else:
        print(json.dumps(resp, indent=2))


# -- verb implementations ----------------------------------------------------

def cmd_status(args):
    run_dir = _resolve_run_dir(args.run_dir)
    if not daemon_alive(run_dir):
        resp = {
            "ok": True,
            "daemon_running": False,
            "connected": False,
            # always echo which sock dir this invocation targets (default
            # run/ vs --run-dir), mirrors the archive's status shape.
            "run_dir": str(run_dir),
        }
        print_response(resp, args)
        return 0
    # SESSION-F7 / MT-03: pidfile-alive is not the same as a successful
    # status round-trip (PID reuse / dead sock). Only claim daemon_running
    # when the request itself succeeded.
    resp = send_request("status", {}, run_dir=run_dir)
    ok = bool(resp.get("ok"))
    resp["daemon_running"] = ok
    if not ok:
        resp.setdefault("status_unreachable", True)
    resp["run_dir"] = str(run_dir)
    print_response(resp, args)
    return 0 if ok else 1


def ensure_raw(profile, *, target="main_command", timeout=180.0, no_auto_arm=False, run_dir=None):
    """Core `ensure` implementation shared by `cmd_ensure` (the `tw
    ensure` CLI verb) and `adapters.ensure_session()` (the play-shell's
    Python entry point) -- both need the *same* spawn-then-round-trip
    logic, not two copies that could drift. Returns the daemon's raw
    response dict, or a locally-synthesized `{"ok": False, "error": ...,
    "detail": ...}` dict for a profile/spawn/budget failure that never
    reached the daemon. Never raises for an expected failure mode.

    Bounded by `timeout`: the whole call -- profile resolution, daemon
    spawn-wait, AND the login round trip -- budgets against one monotonic
    deadline, so a daemon that never comes up (or never settles) cannot
    hang the caller past `timeout` seconds. This is the mechanism behind
    canon's "play does not hang past a bounded timeout" contract
    (`canon/architecture/cli-verbs.md`).
    """
    run_dir = run_dir or env.resolve_run_dir()
    run_dir.mkdir(parents=True, exist_ok=True)
    env.LOG_DIR.mkdir(parents=True, exist_ok=True)

    deadline = time.monotonic() + timeout

    try:
        host, port = _resolve_profile_connection(profile)
    except ProfileResolutionError as e:
        return {"ok": False, "error": "profile_invalid", "detail": str(e)}

    sock_path = env.socket_path(run_dir)

    if not (daemon_alive(run_dir) and sock_path.exists()):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"ok": False, "error": "timeout", "detail": "budget exhausted before daemon spawn"}

        daemon_log_path = run_dir / "twd.stderr.log"
        try:
            daemon_log = open(daemon_log_path, "ab")
        except OSError as e:
            return {"ok": False, "error": "spawn_failed", "detail": f"cannot open {daemon_log_path}: {e}"}

        # WO-P2-020 daemon-spawn idiom: module invocation (there is no
        # `twd` launcher script in the one-tree layout yet -- ADR-001).
        # Confirmed against Monk-D's landed daemon: `twd`'s argv is ONLY
        # `--host/--port/--name` -- it does NOT reimplement run-dir/log-dir
        # flags (WO-P2-021 design: the daemon resolves its run-dir the same
        # way every other module does, via `env.resolve_run_dir()`/
        # `TW_RUN_DIR`, never a CLI override). So the run-dir this spawn
        # must land the daemon's socket in is passed through the
        # subprocess **environment**, not argv -- the same `TW_RUN_DIR`
        # override `env.py` already honors for every caller.
        cmd = [
            sys.executable, "-m", "tw2002_aiclient.session.daemon",
            "--host", host,
            "--port", str(port),
        ]
        spawn_env = {**os.environ, env.RUN_DIR_VAR: str(run_dir)}
        try:
            subprocess.Popen(
                cmd,
                cwd=str(env.PROJECT_ROOT),
                env=spawn_env,
                stdout=daemon_log,
                stderr=daemon_log,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as e:
            daemon_log.close()
            return {"ok": False, "error": "spawn_failed", "detail": str(e)}
        daemon_log.close()

        spawn_deadline = deadline  # never wait past the overall budget
        while time.monotonic() < spawn_deadline and not sock_path.exists():
            time.sleep(0.1)
        if not sock_path.exists():
            return {
                "ok": False,
                "error": "spawn_failed",
                "detail": f"daemon failed to start (no socket after {timeout:.0f}s) -- see {daemon_log_path}",
            }

        # Let the fresh connection produce its first settled screen
        # before driving it -- mirrors `tw start`'s post-spawn read.
        # Cap the settle window so a slow/idle first screen cannot burn
        # the whole ensure budget (WO-P2-OPS-VERB-B: `read` is live now;
        # previously unknown_verb returned instantly and hid this hazard).
        remaining = deadline - time.monotonic()
        settle_budget = min(remaining, 5.0)
        if settle_budget > 0:
            send_request(
                "read",
                {"timeout": settle_budget},
                timeout=settle_budget + 5,
                run_dir=run_dir,
            )

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return {"ok": False, "error": "timeout", "detail": "budget exhausted before ensure round trip"}

    return send_request(
        "ensure",
        {"target": target, "profile": profile, "no_auto_arm": bool(no_auto_arm)},
        timeout=remaining + 5,
        run_dir=run_dir,
    )


def cmd_ensure(args):
    run_dir = _resolve_run_dir(args.run_dir)
    resp = ensure_raw(
        args.profile,
        target=args.target,
        timeout=args.timeout,
        no_auto_arm=args.no_auto_arm,
        run_dir=run_dir,
    )
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_screen(args):
    """WO-P2-OPS-VERB-A: current settled screen (read-only; never sends)."""
    run_dir = _resolve_run_dir(args.run_dir)
    resp = send_request("screen", {"raw": bool(args.raw)}, run_dir=run_dir)
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_stop(args):
    """WO-P2-OPS-VERB-A: ask the daemon to shut down (protocol already present)."""
    run_dir = _resolve_run_dir(args.run_dir)
    if not daemon_alive(run_dir):
        if getattr(args, "json", False):
            print(json.dumps({"ok": True, "daemon_running": False, "run_dir": str(run_dir)}))
        else:
            print("daemon not running")
        return 0
    resp = send_request("stop", {}, run_dir=run_dir)
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_do(args):
    """WO-P2-OPS-VERB-B: send input, wait for settle, return the new screen."""
    run_dir = _resolve_run_dir(args.run_dir)
    timeout = float(args.timeout)
    resp = send_request(
        "do",
        {
            "input": args.input,
            "enter": args.enter,
            "secret": bool(args.secret),
            "wait_prompt": args.wait_prompt,
            "timeout": timeout,
        },
        timeout=timeout + 5,
        run_dir=run_dir,
    )
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_send(args):
    """WO-P2-OPS-VERB-B: raw send, no settle wait."""
    run_dir = _resolve_run_dir(args.run_dir)
    resp = send_request(
        "send",
        {
            "input": args.input,
            "enter": args.enter,
            "secret": bool(args.secret),
        },
        run_dir=run_dir,
    )
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_read(args):
    """WO-P2-OPS-VERB-B: wait-and-return without sending."""
    run_dir = _resolve_run_dir(args.run_dir)
    timeout = float(args.timeout)
    resp = send_request(
        "read",
        {
            "wait_prompt": args.wait_prompt,
            "timeout": timeout,
        },
        timeout=timeout + 5,
        run_dir=run_dir,
    )
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_history(args):
    """WO-P2-OPS-VERB-C: recent verb/prompt history from the live session ring."""
    run_dir = _resolve_run_dir(args.run_dir)
    resp = send_request("history", {"n": int(args.n)}, run_dir=run_dir)
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_watch(args):
    """WO-P2-OPS-VERB-E2: tail the settle-edge push-stream (read-only).

    Opens a lifetime ``subscribe`` connection — never sends game input.
    ``--frames N`` exits after N *parsed* events (transcript-friendly);
    unparseable lines are reported and do not count toward N. Otherwise
    runs until Ctrl-C / disconnect. SIGINT closes the socket cleanly.
    """
    run_dir = _resolve_run_dir(args.run_dir)
    sock_path = env.socket_path(run_dir)
    if not sock_path.exists():
        print("ERROR: daemon_not_running")
        return 1
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(str(sock_path))
        s.sendall((json.dumps({"verb": "subscribe", "args": {}}) + "\n").encode("utf-8"))
    except OSError as e:
        print(f"ERROR: connect_failed:{e}")
        s.close()
        return 1
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
                # SESSION-F8 / MT-04: do not silently swallow corruption —
                # operator-visible tell; --frames still counts only parsed.
                print("ERROR: watch_frame_unparseable", file=sys.stderr)
                continue
            print_response(event, args)
            count += 1
            if args.frames is not None and count >= args.frames:
                break
    except KeyboardInterrupt:
        pass
    finally:
        try:
            f.close()
        except OSError:
            pass
        s.close()
    return 0


def cmd_menumap(args):
    """WO-P2-OPS-VERB-G1: read-only menu-map inspector (coverage / orphans /
    you-are-here). Never sends. Localizes the live screen when a daemon is up.

    The you-are-here line has THREE states, not two, because "we looked and
    you are not on the map" and "we never managed to look" are different
    facts and the operator can act on only one of them:

    * ``here ★ <label>`` -- localized.
    * ``here off-map``   -- ``localize()`` ran and returned None. Canon's
      escalate-don't-navigate-blind signal, and the ONLY case entitled to
      this line.
    * ``here ? <reason>`` -- the lookup never happened: no daemon, an
      unusable ``screen`` response, a blank screen, or a raised lookup.

    The exit code stays 0 for all three: the map report itself succeeded
    (counts, coverage, dead-ends, orphans are all real), and only the
    you-are-here marker is unavailable. A scripted caller that needs to
    branch on it reads ``here_unknown`` from ``--json``.
    """
    from tw2002_aiclient.menu import knowledge as menu_knowledge
    from tw2002_aiclient.menu.map_view import (
        format_menu_map_report,
        menu_map_summary_from_store,
    )
    from tw2002_aiclient.menu.nav import localize

    path = args.path
    if not path and getattr(args, "world_id", None):
        path = str(menu_knowledge.knowledge_path_for_world(args.world_id))
    if not path:
        print("ERROR: need --path or --world-id")
        return 1

    run_dir = _resolve_run_dir(getattr(args, "run_dir", None))
    current_sig = None
    # Why we could not localize, or None once localize actually answered.
    # Every branch below that leaves `current_sig` unset names itself here:
    # four separate ways of FAILING TO LOOK used to render byte-for-byte
    # identically to a genuine "you are off the map", which is a claim about
    # the player's position that none of them established. Canon reserves
    # off-map for localize's own None -- "STOP, escalate, never navigate
    # blind" (canon/engine/menu-map-and-introspection.md:298-302) -- so the
    # other four get `here ? <reason>` instead.
    here_unknown = None
    if not daemon_alive(run_dir):
        here_unknown = "no daemon (store only)"
    else:
        resp = send_request("screen", {}, run_dir=run_dir)
        if not resp.get("ok"):
            here_unknown = f"screen unavailable: {resp.get('error') or 'unknown error'}"
        else:
            screen_text = "\n".join(resp.get("screen") or [])
            if not screen_text.strip():
                # The 4th path, undocumented before this WO: daemon up, the
                # `screen` verb ok, but nothing on the screen to localize --
                # `localize` is never called, so it never said off-map.
                here_unknown = "screen is blank"
            else:
                try:
                    node = localize(screen_text, path)
                except (OSError, ValueError, TypeError, KeyError) as e:
                    here_unknown = f"lookup failed: {type(e).__name__}"
                else:
                    if node:
                        current_sig = node.get("signature")
                    # else: localize really did answer None. That IS off-map,
                    # the one case that has always been entitled to say so --
                    # `here_unknown` stays None.

    try:
        summary = menu_map_summary_from_store(
            path, current_sig=current_sig, here_unknown=here_unknown
        )
    except (OSError, ValueError, TypeError, KeyError, menu_knowledge.GameKnowledgeError) as e:
        print(f"ERROR: {e}")
        return 1

    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "path": path, **summary}))
        return 0
    for line in format_menu_map_report(summary):
        print(line)
    return 0


def cmd_loops(args):
    """WO-P2-G3: read-only listing of the taught-macro ("learned loop") store.

    Daemon-free by canon -- ``canon/architecture/cli-verbs.md:36-38`` lists
    ``loops`` among the reads that "read on-disk artifacts directly, so they
    work with the daemon stopped". So there is no socket round trip here and
    no ``--run-dir``: nothing this verb reports comes from the session, and a
    run-dir flag would imply the listing depends on which daemon is up.

    Deliberately thin. ``loops/store.read_loop_store`` decides what is TRUE
    and ``loops/list_view.format_loops_report`` decides how it READS; this
    function chooses only the exit code. No store logic lives here -- a
    second opinion about what an empty store means is exactly the drift the
    engine-first split exists to prevent, and the in-TUI Learned-Loops
    Library is meant to share the same composer.

    Exit code -- the one decision this wire makes, and it follows the
    reader's ``status``, never the row count:

    * ``unreadable`` -> **1**. Nothing was established, so a scripted caller
      must never be able to read "no loops" out of a store nobody could
      read; ``tw loops || echo none`` is the shape that would otherwise lie
      silently.
    * ``partial``    -> **0**. The listing genuinely succeeded for the
      documents it could read: the rows are real, and the report already
      carries INCOMPLETE plus a named reason per failure -- strictly more
      than an exit code can carry.
    * ``ok`` (populated, empty, or never-written) -> **0**.

    Canon does not rule on that mapping (``cli-verbs.md``'s catalog stops at
    args and actor-class), so it is an evaluator UX call, recorded here so a
    later canon ruling has something explicit to overturn. It matches
    ``cmd_menumap``'s shape: non-zero when the report itself failed, zero
    when only a part of it is unavailable AND says so on the surface.

    Drafts are inert until a human promotes them
    (``canon/engine/candidate-mining.md``), so they are consulted only on
    explicit ``--include-drafts``, and the composer prefixes every draft row
    ``[DRAFT]`` so an inert proposal can never read as an armed macro.
    """
    from tw2002_aiclient.loops.list_view import format_loops_report
    from tw2002_aiclient.loops.store import read_loop_store

    result = read_loop_store(include_drafts=bool(getattr(args, "include_drafts", False)))

    if getattr(args, "json", False):
        # The reader's result verbatim. No ``ok: True`` is synthesized over
        # it: ``cmd_menumap`` can carry that flag because its report either
        # builds or errors out, but here a success flag sitting next to
        # ``status: partial``/``unreadable`` is the exact claim the verb did
        # not earn. ``status`` is the field a caller branches on -- and it
        # has to, because ``loops: []`` is structurally identical for an
        # empty store and an unreadable one.
        print(json.dumps(result))
    else:
        for line in format_loops_report(result):
            print(line)
    return 1 if result.get("status") == "unreadable" else 0


def _arm_lossless_stdin():
    """Make ``sys.stdin`` park an undecodable byte as a PEP 383 surrogate
    instead of raising, and report whether stdin is now lossless.

    ``cmd_attach`` forwards the operator's keystrokes to an **8-bit** game
    wire, so every byte the terminal delivers is potentially meaningful --
    but ``sys.stdin`` decodes to ``str`` first, under whatever codec the
    ambient locale picked, and a *strict* handler turns a byte it cannot
    decode into a ``UnicodeDecodeError``. Measured, not assumed: that error
    also discards the rest of the chunk the wrapper had already read, so a
    ``0xFF`` typed just before ``Q`` loses BOTH -- catching the exception and
    continuing would silently eat keystrokes, which is the exact class of
    harm this whole verb keeps being fixed for. Preventing the error is the
    only honest option, so we ask for ``surrogateescape`` up front.

    ``reconfigure()`` is only legal before the stream's first read, which is
    why this is called before the cbreak loop and nowhere else. It is a
    no-op when stdin already decodes with ``surrogateescape`` (the default
    on a UTF-8 or coerced-C locale), and it returns False rather than
    raising for a stdin that cannot be reconfigured at all -- a test double,
    or a stream something upstream already read. ``io.UnsupportedOperation``
    subclasses both ``ValueError`` and ``OSError``, so it needs no import
    here; ``TypeError`` covers a double with an incompatible signature.
    """
    stream = sys.stdin
    if getattr(stream, "errors", None) == "surrogateescape":
        return True
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return False
    try:
        reconfigure(errors="surrogateescape")
    except (TypeError, ValueError, OSError):
        return False
    return getattr(stream, "errors", None) == "surrogateescape"


def cmd_attach(args):
    """WO-P2-OPS-VERB-F1: take control_lock and forward keystrokes (thin).

    No curses screen paint yet (F2 spectate). Interactive mode needs a TTY
    (cbreak until Ctrl-], EOF, or a failed send). ``--keys`` sends latin-1
    bytes then detaches -- for FakeDaemon / scripted proof without a TTY.

    The exit code is honest about delivery on BOTH paths: a ``send_key()``
    returning False ends the session and returns 1 rather than continuing
    to swallow the pilot's keystrokes behind an ``ATTACHED`` banner
    (interactive: WO-AUDIT-ATTACH-SEND-KEY-BOOL; scripted ``--keys``:
    WO-AUDIT-CLI-KEYS-IGNORE-RETURN).

    Non-delivery is therefore reported in TWO different registers, because
    there are two different conditions and only one of them is fatal:

    * **transport failure** (``send_key()`` -> False) -- the wire is dead,
      nothing further will get through: report and END the session, rc 1.
    * **unencodable key** (interactive only) -- the wire is fine, but that
      character has no 8-bit encoding for the game: report and KEEP GOING,
      rc still 0 on a clean detach. Nothing is put on the wire for it.

    So on the interactive path rc 0 means "nothing was dropped by the
    transport", not "every key you pressed reached the game" -- an
    unencodable key is reported inline, at the moment it happens, which is
    the only surface the operator has here (thin attach paints no screen).

    ``--keys`` takes the FIRST register, not the second: an unencodable key
    there is rc 1, because there is no live session to protect and a script
    must be able to detect non-arrival. Nothing is sent at all in that case
    -- a partial send would put DIFFERENT bytes on the wire than were asked
    for, which is worse than sending none.

    Two properties this function holds deliberately, both easy to break by
    accident and both pinned by test:

    * **Every operator-facing string here is pure ASCII.** This is the one
      code path whose whole subject is a terminal that cannot represent
      some character, and it is reached on exactly the 8-bit and ascii
      terminals where a non-ASCII byte in our OWN output raises
      ``UnicodeEncodeError`` and kills the verb. The banner used to carry
      an em-dash and did precisely that on a latin-1 or ascii stdout: the
      operator lost attach before they could press a key, while the
      carefully-ASCII refusal notice thirty lines below never got to fire.
      An ASCII-only rule for the whole function is the property; a
      hand-checked line is not.
    * **A byte the terminal could not decode is still delivered.** See
      ``_arm_lossless_stdin`` and the surrogate branch in the loop.
    """
    from .attach_client import DETACH_KEY, AttachInputConn

    run_dir = _resolve_run_dir(args.run_dir)
    sock_path = env.socket_path(run_dir)
    if not sock_path.exists():
        print("ERROR: daemon_not_running")
        return 1

    keys = getattr(args, "keys", None)
    if keys is None and not sys.stdin.isatty():
        print("ERROR: tw attach needs a real terminal (or pass --keys for scripted use)")
        return 1

    conn = AttachInputConn(sock_path)
    if not conn.connect():
        print(f"ERROR: {conn.error or 'attach_failed'}")
        return 1

    try:
        if keys is not None:
            # Scripted: interpret escapes lightly -- \r \n \xNN and raw chars
            # (the contract README.md documents for this flag).
            #
            # THE ROOT DEFECT WAS NOT A DROP, IT WAS A DOUBLE ENCODE. The old
            # chain began `keys.encode("utf-8")`, and `unicode_escape` is a
            # LATIN-1-based codec: it decodes each BYTE to one codepoint. So a
            # UTF-8 multi-byte sequence came back as one character per byte,
            # every one of them latin-1-representable, and the final encode
            # shipped them all. `errors="ignore"` therefore almost never
            # fired -- the branch was not dropping non-ASCII input, it was
            # MANGLING it, silently, with rc 0:
            #
            #     --keys with a raw U+00FF  ->  wire b"\xc3\xbf"   (two bytes)
            #     the same key interactively ->  wire b"\xff"     (one byte)
            #
            # One character asked for, two bytes delivered, and the two halves
            # of the same verb disagreeing about a byte class an 8-bit
            # TradeWars wire is made of. Fixing only the visible drops would
            # have left every non-ASCII `--keys` value still going out as
            # mojibake -- a fix that passes its own tests while the real bug
            # runs on.
            #
            # So the FIRST encode is `latin-1`, not `utf-8`: encode the
            # operator's characters to the 8-bit bytes the game wire actually
            # takes, and hand `unicode_escape` the operator's OWN bytes
            # instead of a UTF-8 re-encoding of them. `unicode_escape` stays,
            # because the documented `\r` / `\n` / `\xNN` forms are its whole
            # job -- and it is now correct rather than incidentally lossy,
            # since latin-1 is exactly the code page it decodes back with.
            # The round trip is now an identity on every character the wire
            # can carry.
            #
            # Its `surrogateescape` handler covers the other half: argv
            # reaches Python already decoded by the OS-encoding codec with
            # PEP 383, so a raw 8-bit byte on the command line
            # (`--keys $'\xff'`) arrives as the lone surrogate U+DCFF, and
            # this maps it straight back to its byte. Strict raised
            # UnicodeEncodeError there and killed the verb with an uncaught
            # traceback. Identical recovery to the interactive loop below.
            #
            # The LAST encode is STRICT (it was `errors="ignore"`), which is
            # what makes a genuinely unencodable key visible instead of
            # silent. Both surviving failure shapes exited 0 before:
            #   full drop     `--keys '\u2192'`  -> sent nothing, rc 0,
            #                                       indistinguishable from
            #                                       `--keys ""`
            #   partial drop  `--keys 'a\u2192b'` -> sent b"ab", rc 0 -- not
            #                                       nothing, but DIFFERENT
            #                                       bytes than asked for
            #
            # ONE `except UnicodeEncodeError` covers both encodes deliberately,
            # because they are the same question asked of two populations:
            #   * first encode  -- a RAW character the wire cannot carry
            #                      (`--keys '\u2192'`), which used to be mangled
            #                      into its UTF-8 bytes. `e.start` indexes argv.
            #   * last encode   -- a character an ESCAPE produced. There are
            #                      FOUR such forms, not two (brute-forced, not
            #                      reasoned):
            #                        \uXXXX      -> up to U+FFFF
            #                        \UXXXXXXXX  -> up to U+10FFFF
            #                        \N{NAME}    -> any named codepoint
            #                        \400-\777   -> U+0100-U+01FF  (octal
            #                                      escape overflow)
            #                      `e.start` indexes the escape-DECODED keys.
            # Both hand us the offending index and codepoint for free, which
            # the length comparison originally specified could not have done.
            #
            # A useful consequence of encoding latin-1 FIRST: a backslash
            # immediately before an unencodable character (`--keys 'a\\u2192b'`)
            # is refused at the first encode rather than becoming ambiguous.
            # Nothing here ever manufactures escape text, so nothing can be
            # re-read as an escape the operator did not write.
            #
            # UnicodeDecodeError is the other half, and a different failure:
            # an escape that cannot be decoded AT ALL -- a trailing backslash,
            # or a truncated \x \u \U \N -- which was also an uncaught
            # traceback. Reported in the same register; nothing is sent.
            try:
                data = (
                    keys.encode("latin-1", errors="surrogateescape")
                    .decode("unicode_escape")
                    .encode("latin-1")
                )
            except UnicodeEncodeError as e:
                # Codepoint, never the glyph: same rule and same reasons as
                # the interactive notice below.
                print(
                    f"ERROR: key U+{ord(e.object[e.start]):04X} at index "
                    f"{e.start} has no 8-bit encoding for this game "
                    "connection; nothing was sent"
                )
                return 1
            except UnicodeDecodeError as e:
                # `e.start` here is a BYTE offset into the encoded argv, a
                # different unit from the branch above; named as such rather
                # than blurred into one word for both.
                #
                # `e.reason` and `e.start` ONLY -- never `str(e)` and never
                # `e.object`. Both `UnicodeDecodeError.object` and the
                # analogous `JSONDecodeError.doc` hold the ENTIRE input that
                # failed to parse, and neither is rendered by `str(e)`, so
                # reaching for the whole exception here would quietly widen a
                # one-line diagnostic into an echo of the operator's full
                # `--keys` argument. `e.reason` is a short fixed codec string
                # ("\\ at end of string", "truncated \\uXXXX escape").
                print(
                    f"ERROR: --keys could not be decoded ({e.reason}) at byte "
                    f"index {e.start}; nothing was sent"
                )
                return 1
            # `if data:` is now ONLY the deliberate `--keys ""` pin (032bc12):
            # "you asked for nothing" stays distinguishable from "everything
            # you asked for was thrown away", which is no longer reachable --
            # a dropped character raises above instead of arriving here as an
            # empty payload. Do not "simplify" this away.
            if data:
                if not conn.send_key(data):
                    print("ERROR: send_failed")
                    return 1
            return 0

        import termios
        import tty

        # Before the first read, and before the banner: see
        # `_arm_lossless_stdin`. Its result is deliberately not branched on --
        # a stdin that refuses to become lossless still attaches, and the
        # `UnicodeDecodeError` backstop in the loop below is what covers it.
        _arm_lossless_stdin()

        # PURE ASCII, and it has to stay that way -- this line used to carry
        # an em-dash and killed `tw attach` outright on a latin-1 or ascii
        # stdout, before the operator could press a single key. See the
        # ASCII property in this function's docstring.
        print("ATTACHED -- Ctrl-] detach (thin attach: no live screen paint yet; use tw watch)", flush=True)
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        send_failed = False
        undecodable_stdin = None
        try:
            tty.setcbreak(fd)
            while True:
                try:
                    ch = sys.stdin.read(1)
                except UnicodeDecodeError as e:
                    # BACKSTOP, not the live path: `_arm_lossless_stdin`
                    # above normally makes this unreachable by parking an
                    # undecodable byte as a surrogate instead of raising.
                    # Reached only when stdin could not be reconfigured.
                    #
                    # It ENDS the session rather than continuing, and that is
                    # the honest choice even though a lone bad key is
                    # survivable elsewhere in this loop: measured, a strict
                    # decode error also discards the rest of the chunk the
                    # wrapper had already read, so "report and keep going"
                    # would silently swallow keystrokes the operator had
                    # already typed. Continuing would recreate the exact
                    # defect this verb keeps being fixed for.
                    undecodable_stdin = e
                    break
                if not ch:
                    break
                code = ord(ch)
                if code == DETACH_KEY:
                    break
                if ch in ("\n", "\r"):
                    payload = b"\r\n"
                elif 0xDC80 <= code <= 0xDCFF:
                    # A byte stdin's decoder could NOT decode, parked as a
                    # lone PEP 383 surrogate: U+DC80-U+DCFF *is* byte
                    # 0x80-0xFF, by that PEP's definition. Recover it and
                    # SEND it -- it is deliverable, and it is precisely the
                    # byte class an 8-bit TradeWars wire is made of (an
                    # 8-bit Meta terminal, a latin-1 host, a pasted latin-1
                    # blob). The refusal below used to catch these and name
                    # them "U+DCFF", a codepoint that exists on no keyboard
                    # and that the operator never pressed: wrong twice, once
                    # for refusing a deliverable key and once for the name.
                    #
                    # Unambiguous: a lone surrogate cannot arrive from a
                    # terminal any other way (it has no UTF-8 form), so this
                    # branch cannot capture a character the operator meant
                    # literally. Surrogates outside DC80-DCFF are not
                    # PEP 383 escapes and fall through to the refusal below.
                    payload = bytes([code - 0xDC00])
                else:
                    try:
                        payload = ch.encode("latin-1")
                    except UnicodeEncodeError:
                        # A GENUINE character the game's 8-bit wire cannot
                        # carry (a curly quote, an em-dash, an emoji --
                        # typically pasted, not typed), as opposed to the
                        # undecodable BYTE handled by the branch above, which
                        # is deliverable and is sent.
                        # `errors="ignore"` used to turn it into b"",
                        # which the daemon answered `{"ok": true}`: the
                        # keystroke vanished with every surface reporting
                        # success. Decided HERE, before the wire, because the
                        # client already knows the character is unencodable.
                        #
                        # NOT the `send_failed` path below, deliberately: that
                        # one means the wire is broken and nothing will ever
                        # get through, so ending attach is right. This one
                        # means the wire is FINE and one character cannot be
                        # represented -- ending the session over a pasted
                        # em-dash would be a worse harm than the silent drop,
                        # and the human is the sovereign pilot here
                        # (canon/architecture/north-star.md). So: tell them,
                        # send nothing, keep the keyboard.
                        #
                        # The codepoint is named, never the glyph. cbreak has
                        # ECHO off and this session may be sitting on a game
                        # password prompt, so the keystroke itself may be part
                        # of a secret.
                        #
                        # CITATION CORRECTED: this used to cite canon's "a
                        # refused key is never echoed verbatim". That clause is
                        # real but is about something else entirely -- it lives
                        # in "The Credential Bank -- metadata only (TW-31)" and
                        # governs a rejected notes-dict KEY NAME, not a
                        # keystroke. The clauses that actually govern here are
                        # in the same doctrine (canon/doctrine/secrets-and-
                        # credentials.md): the section "Redaction: the send
                        # path, and its one honest boundary", which extends the
                        # redaction contract to "a raw human keystroke typed
                        # into an interactive attach session that happens to
                        # land on a password prompt"; its Schema row for the TX
                        # raw-byte send channel ("interactive attach
                        # keystroke", redacted, decided fresh at send time);
                        # and the worked Example "A password typed into a live
                        # attach session". The reasoning never changed -- only
                        # the clause it points at, which was wrong.
                        #
                        # Naming the CODEPOINT is safe and stays: any character
                        # reaching this branch is by construction not
                        # latin-1-representable, so it cannot be a byte of a
                        # working password on an 8-bit telnet game. Echoing the
                        # raw glyph back into a raw-mode terminal would be an
                        # independent hazard anyway (combining marks, bidi
                        # overrides).
                        #
                        # ASCII-only, like every other operator string in this
                        # function now is (see the docstring's ASCII property).
                        # This message carries the rule's sharpest case -- it
                        # fires BECAUSE something could not be represented, so
                        # it must not itself depend on the terminal rendering a
                        # non-ASCII character. It also makes "the glyph was not
                        # echoed" a checkable property of the line rather than
                        # a claim.
                        print(
                            f"NOT SENT: key U+{ord(ch):04X} has no 8-bit "
                            "encoding for this game connection (still attached)",
                            flush=True,
                        )
                        continue
                sent_ok = conn.send_key(payload)
                if not sent_ok:
                    # Both send sites feed this ONE check deliberately:
                    # fixing either alone is what left this loop dropping
                    # the pilot's keystrokes while still showing ATTACHED
                    # and exiting 0. Reported below rather than here so
                    # the `finally:` has provably restored the terminal
                    # before the operator reads the line (and so the outer
                    # `finally: conn.close()` still releases the wire).
                    send_failed = True
                    break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if send_failed:
            print("ERROR: send_failed -- keystrokes are NOT reaching the game; attach ended")
            return 1
        if undecodable_stdin is not None:
            # Same "report after the terminal is restored" discipline as
            # send_failed above. Reports the terminal's own codec by name,
            # because that is the thing the operator has to change.
            print(
                f"ERROR: this terminal's input encoding "
                f"({undecodable_stdin.encoding}, strict) cannot carry an "
                "8-bit key; attach ended"
            )
            return 1
    except KeyboardInterrupt:
        pass
    finally:
        conn.close()
    return 0


# -- parser -------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tw",
        description="tw2002-aiclient backend/ops CLI (verb table grows one WO at a time).",
    )
    sub = parser.add_subparsers(dest="verb")

    sp = sub.add_parser(
        "status",
        help="daemon alive? connected? idle-ms? classification? (includes run_dir)",
    )
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser(
        "ensure",
        help=(
            "idempotent auto-login -- the ONE verb a Bash-driving caller invokes: "
            "classifies the current screen, no-ops if already at target, else logs "
            "in using the profile's stored credential, spawning the daemon first "
            "if none is running"
        ),
    )
    sp.add_argument("target", nargs="?", default="main_command",
                     help="target classification (default: main_command)")
    sp.add_argument("--profile", required=True, help="profile name in config/profiles.toml")
    sp.add_argument("--timeout", type=float, default=180.0, help="overall budget for the login automaton")
    sp.add_argument("--no-auto-arm", action="store_true", dest="no_auto_arm",
                     help="accepted no-op: ensure never auto-arms; flag confirms non-arming (symmetry with any future default-arm proposal)")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_ensure)

    sp = sub.add_parser(
        "screen",
        help="current settled screen (non-destructive; never sends)",
    )
    sp.add_argument("--raw", action="store_true", help="uncropped pyte grid (session.render_raw)")
    sp.add_argument("--compact", action="store_true",
                     help="omit prompt/class footer after the screen rows")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_screen)

    sp = sub.add_parser(
        "stop",
        help="graceful daemon shutdown (in-game QUIT when at main prompt; else disconnect)",
    )
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_stop)

    sp = sub.add_parser(
        "do",
        help="send input, wait for settle, return the new screen",
    )
    sp.add_argument("input", help="text to send (CRLF appended unless --no-enter)")
    sp.add_argument("--no-enter", action="store_false", dest="enter",
                     help="do not append CRLF after input")
    sp.set_defaults(enter=True)
    sp.add_argument("--secret", action="store_true",
                     help="password entry — never persisted to the transcript log")
    sp.add_argument("--wait-prompt", default=None, dest="wait_prompt",
                     help="case-sensitive regex; settle waits until prompt matches")
    sp.add_argument("--timeout", type=float, default=8.0, help="settle timeout seconds")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_do)

    sp = sub.add_parser(
        "send",
        help="raw send, no settle wait (rare / low-level)",
    )
    sp.add_argument("input", help="text to send (CRLF appended unless --no-enter)")
    sp.add_argument("--no-enter", action="store_false", dest="enter",
                     help="do not append CRLF after input")
    sp.set_defaults(enter=True)
    sp.add_argument("--secret", action="store_true",
                     help="password entry — never persisted to the transcript log")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_send)

    sp = sub.add_parser(
        "read",
        help="wait for settle and return the screen without sending",
    )
    sp.add_argument("--wait-prompt", default=None, dest="wait_prompt",
                     help="case-sensitive regex; settle waits until prompt matches")
    sp.add_argument("--timeout", type=float, default=8.0, help="settle timeout seconds")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_read)

    sp = sub.add_parser(
        "history",
        help="recent screens/commands from the live session history ring",
    )
    sp.add_argument("--n", type=int, default=20, help="max entries to return (default 20)")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_history)

    sp = sub.add_parser(
        "watch",
        help="tail the settle-edge push-stream (read-only spectator feed)",
    )
    sp.add_argument(
        "--frames",
        type=int,
        default=None,
        metavar="N",
        help="exit after N events (default: run until Ctrl-C)",
    )
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.add_argument("--compact", action="store_true",
                     help="screen only — omit prompt/class/settled footer")
    sp.set_defaults(func=cmd_watch)

    sp = sub.add_parser(
        "attach",
        # ASCII, for the same reason cmd_attach's own strings are: `tw attach
        # --help` and `tw --help` both print this line, and on the ascii or
        # latin-1 terminal where attach's encoding behaviour actually matters
        # a non-ASCII glyph here crashes the help output instead. (The other
        # verbs' help strings in this parser still carry em-dashes and have
        # the same exposure -- out of this WO's scope, reported not fixed.)
        help="take the keyboard (control-lock); thin attach -- no curses paint yet",
    )
    sp.add_argument(
        "--keys",
        default=None,
        metavar="BYTES",
        help="scripted keystroke(s) then detach (unicode-escape; no TTY required)",
    )
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.set_defaults(func=cmd_attach)

    sp = sub.add_parser(
        "menumap",
        help=(
            "read-only menu-map inspector: coverage, dead-ends, orphans, "
            "and you-are-here ★ / off-map — never sends"
        ),
    )
    sp.add_argument(
        "--path",
        default=None,
        help="game_knowledge.json path (primary; required unless --world-id)",
    )
    sp.add_argument(
        "--world-id",
        dest="world_id",
        default=None,
        help="world_id slug under state/world/ (joins …/game_knowledge.json)",
    )
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_menumap)

    sp = sub.add_parser(
        "loops",
        # ASCII, deliberately. `tw --help` prints every verb's help line
        # through the terminal's own codec, so one non-ASCII glyph here
        # raises UnicodeEncodeError instead of printing help on an ascii or
        # latin-1 terminal -- the exposure `attach`'s help comment above
        # records for the em-dashed verbs that shipped before it. Not
        # widened here.
        help=(
            "list the learned-loop (taught-macro) store -- names, provenance, "
            "profit metadata; reads state/skills directly, never sends"
        ),
    )
    sp.add_argument(
        "--include-drafts",
        action="store_true",
        dest="include_drafts",
        help="also list mined drafts, tagged [DRAFT] (inert until a human promotes them)",
    )
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_loops)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if getattr(args, "func", None) is None:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
