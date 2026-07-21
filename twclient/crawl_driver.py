"""twclient/crawl_driver.py — TW-26 live-crawl driver: wires the
already-hardened menu crawler (`twclient/menu_crawler.py`, its own
multi-round safety gate) into a hub-supervised live run.

**The load-bearing safety leg lives HERE, not in menu_crawler.py**
(that module's own docstring is explicit about this — see its "THE
NEVER-COMMIT GUARANTEE LIVES OUTSIDE THIS MODULE" section): a live crawl
only ever runs under the A+C protocol — a disposable, zero-credit/
zero-asset character (**A**) plus a hub-supervisor able to **A**bort mid-
crawl (**C**) — and `Profile.crawl_sacrificial` (`credentials.py`) is
this module's CODE-ENFORCED half of that guarantee. `run_live_crawl()`
refuses outright, before opening a single connection or calling
`session_factory()` even once, on any profile that hasn't explicitly
opted in — structural, not a convention a caller could forget to check.

`menu_crawler.py` is used AS-IS, unmodified — this module never touches
its safety internals, only wraps the `session_factory` callable it
hands to `crawl_menus()`:

- **Abort, without a new menu_crawler parameter.** `crawl_menus()` calls
  `session_factory()` once per BFS node dequeued, AND once more per
  re-anchor after every successfully-emitted option (see that module's
  own `_replay`/Traversal docstring) — every fresh settled screen this
  crawl will ever observe passes through exactly one such call. Wrapping
  it to check `abort_check()` FIRST, before ever reaching the real
  factory, and raise `CrawlAborted` when it says stop, therefore lands
  the abort at the next screen boundary, never mid-send — and needs no
  cooperation from menu_crawler.py at all: `crawl_menus()` has no
  try/except around its own `session_factory()` calls, so the exception
  propagates straight out of it, and `run_live_crawl` is the one place
  that catches it.
- **A live, line-buffered JSONL log.** The same wrapped factory logs one
  `"screen"` event every time it hands back a fresh session — the
  honest granularity available without reaching into menu_crawler's
  internals (the richer per-option `send_log`/category detail only
  exists inside `crawl_menus()` itself, and is written back as one final
  `"summary"` event once — or if — it returns).

Nothing here ever calls `session.send()`, `settle.send_and_confirm()`,
or any other keystroke-emitting primitive directly: every candidate
keystroke this driver could ever cause to reach the wire still passes
through menu_crawler's own single chokepoint, `emit_key_if_safe()`.
"""

import datetime
import json
from pathlib import Path

from .menu_crawler import _DEFAULT_MAX_NODES, crawl_menus


class CrawlSafetyError(Exception):
    """Raised ONLY by the `crawl_sacrificial` startup gate, before any
    connection or crawl action is taken — see `run_live_crawl`'s
    docstring. Never raised for anything else in this module."""


class CrawlAborted(Exception):
    """Raised internally by the abort-wrapped session_factory the
    instant `abort_check()` first returns True — caught inside
    `run_live_crawl` and turned into a clean `aborted=True` result; this
    exception is never expected to escape this module."""


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _open_log(log_path):
    """Line-buffered (`buffering=1`), append-only — same convention as
    `logging_util.TranscriptLogger`'s own log handle — so a hub-operator
    tailing this file sees each event the instant it's written, and a
    re-run against the same path accumulates rather than clobbers a
    prior crawl's trail."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    return open(log_path, "a", buffering=1, encoding="utf-8")


def _log_event(fh, event, **fields):
    fh.write(json.dumps({"ts": _utc_now(), "event": event, **fields}) + "\n")


def _wrap_session_factory(session_factory, abort_check, is_driver_fenced, log_fh, checkpoint_every, counter):
    """Returns a zero-arg callable `crawl_menus()` can use in place of
    the caller's real `session_factory` — identical contract (a fresh
    session already sitting at the world's stable start context), plus
    three side effects on every call:

    1. the abort check, evaluated BEFORE the real factory is ever
       touched (see module docstring's Abort section) -- `abort_check`
       (an external hub-supervisor stop) and `is_driver_fenced`
       (WO-CLEANPREEMPT: a `tw attach` took control_lock's MODE_HUMAN out
       from under this in-flight crawl dispatch -- see control_lock.py's
       `take_human()`/`is_driver_fenced()`) are two INDEPENDENT triggers
       for the exact same clean stop, checked in the same place, for the
       same reason `_wrap_session_factory`'s Abort section already
       documents: `crawl_menus()` asks for a fresh session at every node
       boundary, never mid-send, so this is always the next screen
       boundary after either signal first fires, never mid-send;
    2. a live `"screen"` log line on every successful call, tagging the
       very FIRST one `"registered"`/`"crawl_start"` too — the first
       settled screen this crawl ever sees IS the moment a sacrificial
       character's registration/login is confirmed complete and
       menu_crawler.py is about to start walking the graph from it;
    3. a periodic `"checkpoint"` line every `checkpoint_every` screens,
       purely so a hub-operator tailing a long crawl sees liveness
       between the coarser phase boundaries.

    `counter` is a single-element list used as a mutable int cell so the
    caller can still read the running total after the crawl ends
    (`crawl_menus()` itself never exposes partial progress mid-run — see
    `run_live_crawl`'s docstring on why an abort's result has no
    `nodes_visited`)."""

    def _factory():
        if abort_check is not None and abort_check():
            raise CrawlAborted("abort_check requested a stop")
        if is_driver_fenced is not None and is_driver_fenced():
            raise CrawlAborted("driver fenced by a human attach (WO-CLEANPREEMPT)")
        session = session_factory()
        counter[0] += 1
        if counter[0] == 1:
            _log_event(log_fh, "phase", phase="registered")
            _log_event(log_fh, "phase", phase="crawl_start")
        _log_event(log_fh, "screen", screens_seen=counter[0])
        if checkpoint_every and counter[0] % checkpoint_every == 0:
            _log_event(log_fh, "checkpoint", screens_seen=counter[0])
        return session

    return _factory


def run_live_crawl(
    profile,
    session_factory,
    *,
    path,
    log_path,
    abort_check=None,
    is_driver_fenced=None,
    max_nodes=_DEFAULT_MAX_NODES,
    step_timeout=8.0,
    checkpoint_every=10,
):
    """Drive one hub-supervised live crawl of `profile`'s world via
    `menu_crawler.crawl_menus()`, used unmodified, writing every
    discovered menu node/edge into the `game_knowledge` store at `path`
    (an already-resolved path — see `game_knowledge.knowledge_path()` —
    resolving world identity is the caller's job, mirroring that
    module's own convention; this function has no opinion about it).

    **`crawl_sacrificial` startup gate — the first thing this function
    does, before ANY connection or crawl action:** raises
    `CrawlSafetyError` unless `profile.crawl_sacrificial` is `True`.
    Structural: no branch below this check can reach `session_factory()`
    or `crawl_menus()` at all if it fails. A genuine sacrificial-crawl
    profile is expected to ALSO set `allow_register=True` (WO-MS-4) —
    that pairing is a caller/config convention, this gate only enforces
    the crawl half (the register half is credentials.py/login.py's own
    `allow_register` gate, at the character-creation choke point).

    `session_factory`/`path`/`max_nodes`/`step_timeout` are forwarded to
    `crawl_menus()` unchanged, wrapped only as described in this
    module's docstring (abort + live log).

    `log_path`: a line-buffered JSONL file this call appends to (never
    truncates). One line per live event — `"phase"`
    (`connect`/`registered`/`crawl_start`/`done`/`aborted`/`error`),
    `"screen"` (one per fresh session obtained — see
    `_wrap_session_factory`'s docstring for exactly what this counts),
    `"checkpoint"` (every `checkpoint_every` screens), and a final
    `"summary"` line carrying menu_crawler's own richer per-option
    `send_log`/`emitted_keys`/`nodes_visited` once the crawl actually
    returns.

    `abort_check`: an optional zero-arg callable, checked before every
    fresh session `crawl_menus()` asks for (see `_wrap_session_factory`)
    — the next screen boundary after it first returns True, never
    mid-send. `is_driver_fenced` (WO-CLEANPREEMPT): a second, independent
    zero-arg callable checked in the exact same place — protocol.py's
    `_dispatch_crawl_start` passes `_driver_was_fenced(server)`, so a `tw
    attach` racing in mid-crawl (this dispatch reserves the driver slot
    for the crawl's ENTIRE duration, same as replay/play) stops the crawl
    at the next node boundary instead of continuing to emit keystrokes
    under a human's nose. Either trigger raises the same internal
    `CrawlAborted` and lands on the identical clean-stop path below —
    `"aborted_reason"` in the returned dict (and the logged `"aborted"`
    phase event) names WHICH one fired. On an abort, `crawl_menus()`
    never returns at all (it has no partial-result return path — its own
    `nodes_visited`/`emitted_keys`/`send_log` locals are simply discarded
    when the exception unwinds through it), so this function's own
    returned `"nodes_visited"` is `None` and `"emitted_keys"`/`"send_log"`
    are empty on the aborted path — only what was live-logged up to that
    point (`"screens_seen"`) is genuinely known.

    Returns `{"aborted": bool, "aborted_reason": str|None, "screens_seen":
    int, "nodes_visited": int|None, "emitted_keys": [...], "send_log":
    [...]}` (`"aborted_reason"` is `None` on a normal, non-aborted
    completion). Only `CrawlSafetyError` (the startup gate) and whatever
    `crawl_menus()`/`session_factory()` themselves raise for a genuine
    structural failure (logged as `"phase":"error"` first, then
    re-raised — never swallowed) escape this function; an ordinary abort
    is the expected clean-stop path, not an error."""
    if not getattr(profile, "crawl_sacrificial", False):
        raise CrawlSafetyError(
            f"refusing to crawl: profile {profile.name!r} is not flagged crawl_sacrificial"
        )

    log_fh = _open_log(log_path)
    try:
        _log_event(log_fh, "phase", phase="connect", profile=profile.name, max_nodes=max_nodes)
        screens_seen = [0]
        wrapped_factory = _wrap_session_factory(
            session_factory, abort_check, is_driver_fenced, log_fh, checkpoint_every, screens_seen
        )

        try:
            result = crawl_menus(wrapped_factory, path, max_nodes=max_nodes, step_timeout=step_timeout)
        except CrawlAborted as exc:
            _log_event(log_fh, "phase", phase="aborted", screens_seen=screens_seen[0], reason=str(exc))
            return {
                "aborted": True,
                "aborted_reason": str(exc),
                "screens_seen": screens_seen[0],
                "nodes_visited": None,
                "emitted_keys": [],
                "send_log": [],
            }
        except Exception as exc:  # noqa: BLE001 -- observed live, then re-raised, never swallowed
            _log_event(log_fh, "phase", phase="error", screens_seen=screens_seen[0], error=repr(exc))
            raise

        _log_event(log_fh, "summary", screens_seen=screens_seen[0], **result)
        _log_event(log_fh, "phase", phase="done", nodes_visited=result["nodes_visited"])
        return {"aborted": False, "aborted_reason": None, "screens_seen": screens_seen[0], **result}
    finally:
        log_fh.close()
