"""The live-crawl driver — where canon's never-commit guarantee actually lives.

Canon (``canon/doctrine/action-safety-guards.md``, "Read-only, never-commit
crawl gate (K3)") is explicit that the crawler's never-commit guarantee is
enforced **outside the crawler's own traversal logic, by this driver**, on
two structural legs. `menu.crawler` is used as-is and unmodified; this
module never touches its safety internals, only wraps the
``session_factory`` callable handed to `crawl_menus()`.

**Leg 1 — sacrificial-only startup gate.** `run_live_crawl()` refuses
outright — *before opening a single connection or invoking the session
factory even once* — on any profile not explicitly flagged
``crawl_sacrificial``. A crawl only ever runs under the disposable,
zero-credit / zero-asset character protocol, and the refusal is
code-enforced, not a convention a caller could forget: no branch below the
gate can reach a keystroke-emitting path, and the gate runs before the log
file is opened, so a refusal leaves no trace on disk at all.

The gate is **fail-closed twice over**. The flag is read with an explicit
``False`` default, so a profile object that has never heard of the field
refuses; and only a genuine ``True`` opens it — a truthy stand-in (the
string ``"false"``, a ``1``, an object with a custom ``__bool__``) is
*not* consent to crawl a live world. That is deliberately stricter than
the archived gate's ``if not getattr(...)`` and can only ever refuse more,
never allow more.

**Leg 2 — boundary-aligned abort.** `crawl_menus()` asks for a fresh
session once per BFS node dequeued and once more per re-anchor after every
successfully-emitted option — every fresh settled screen the crawl will
ever observe passes through exactly one such call, and never mid-send.
Wrapping that call to check the stop signals *first*, before the real
factory is ever touched, therefore lands the stop at the next screen
boundary and needs no cooperation from `menu.crawler` at all: it has no
``try``/``except`` around its own ``session_factory()`` calls, so
`CrawlAborted` propagates straight out and this module is the one place
that catches it. Two independent triggers land on the identical clean
path: a hub-supervisor ``abort_check``, and ``is_driver_fenced`` — a human
``tw attach`` taking the control lock out from under an in-flight crawl.

Nothing here calls ``session.send()``, ``settle.send_and_confirm()``, or
any other keystroke-emitting primitive: every candidate keystroke this
driver could cause to reach the wire still passes through
`menu.crawler.emit_key_if_safe`, the single chokepoint.
"""

import datetime
import json
from pathlib import Path

from .crawler import _DEFAULT_MAX_NODES, crawl_menus
from .knowledge import record_crawl_status

# The one value that means "yes, this is a disposable crawl character".
# Anything else -- absent, False, or merely truthy -- refuses.
_SACRIFICIAL_FLAG = "crawl_sacrificial"


class CrawlSafetyError(Exception):
    """Raised ONLY by the sacrificial-only startup gate, before any
    connection or crawl action is taken. Never raised for anything else in
    this module."""


class CrawlAborted(Exception):
    """Raised internally by the abort-wrapped session factory the instant a
    stop signal first fires — caught inside `run_live_crawl` and turned
    into a clean ``aborted=True`` result. Never expected to escape this
    module."""


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _open_log(log_path):
    """Line-buffered, append-only, so a supervisor tailing this file sees
    each event the instant it is written and a re-run against the same
    path accumulates rather than clobbers a prior crawl's trail."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    return open(log_path, "a", buffering=1, encoding="utf-8")


def _log_event(fh, event, **fields):
    fh.write(json.dumps({"ts": _utc_now(), "event": event, **fields}) + "\n")


def _wrap_session_factory(session_factory, abort_check, is_driver_fenced, log_fh, checkpoint_every, counter):
    """Return a zero-arg callable `crawl_menus()` can use in place of the
    caller's real `session_factory` — identical contract (a fresh session
    already sitting at the world's stable start context), plus three side
    effects on every call:

    1. **the stop check, evaluated BEFORE the real factory is ever
       touched.** `abort_check` (an external hub-supervisor stop) and
       `is_driver_fenced` (a ``tw attach`` took the control lock out from
       under this in-flight crawl) are two independent triggers for the
       exact same clean stop, checked in the same place: `crawl_menus()`
       asks for a fresh session only at a screen boundary, never mid-send,
       so this is always the next boundary after either signal fires;
    2. a live ``"screen"`` log line on every successful call, tagging the
       very first one ``"registered"``/``"crawl_start"`` too — the first
       settled screen a crawl sees IS the moment login/registration is
       confirmed complete and the walk is about to begin;
    3. a periodic ``"checkpoint"`` line every `checkpoint_every` screens,
       so a supervisor tailing a long crawl sees liveness between the
       coarser phase boundaries.

    `counter` is a single-element list used as a mutable int cell so the
    caller can still read the running total after the crawl ends."""

    def _factory():
        if abort_check is not None and abort_check():
            raise CrawlAborted("abort_check requested a stop")
        if is_driver_fenced is not None and is_driver_fenced():
            raise CrawlAborted("driver fenced by a human attach")
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
    """Drive one supervised live crawl of `profile`'s world via
    `menu.crawler.crawl_menus()`, used unmodified, writing every discovered
    menu node/edge into the knowledge store at `path` (an already-resolved
    path — resolving world identity is the caller's job).

    **Leg 1, the sacrificial-only gate, is the first thing this function
    does, before ANY connection, crawl action, or file write:** raises
    `CrawlSafetyError` unless ``profile.crawl_sacrificial`` is exactly
    ``True``. Structural — no branch below can reach `session_factory()` or
    `crawl_menus()` if it fails, and no `log_path` is created. A genuine
    sacrificial-crawl profile is expected to ALSO set ``allow_register``;
    that pairing is a caller/config convention, this gate enforces the
    crawl half.

    The gate reads the flag off whatever object it is handed, with an
    explicit ``False`` default: it deliberately does not import or require
    a particular profile type, so a profile representation that has never
    grown the field refuses rather than being trusted by omission.

    `log_path`: a line-buffered JSONL file this call appends to (never
    truncates). One line per live event — ``"phase"``
    (connect / registered / crawl_start / done / aborted / error),
    ``"screen"`` (one per fresh session obtained), ``"checkpoint"``, and a
    final ``"summary"`` carrying the crawler's richer per-option
    ``send_log``/``emitted_keys``/``nodes_visited`` once the crawl returns.

    `abort_check` / `is_driver_fenced`: optional zero-arg callables,
    checked before every fresh session the crawl asks for — the next screen
    boundary after either first returns True, never mid-send. Either raises
    the same internal `CrawlAborted` and lands on the identical clean-stop
    path; ``"aborted_reason"`` names which fired. On an abort `crawl_menus()`
    never returns at all (it has no partial-result return path), so
    ``"nodes_visited"`` is ``None`` and ``"emitted_keys"``/``"send_log"``
    are empty — only what was live-logged up to that point
    (``"screens_seen"``) is genuinely known.

    **Honest map on every terminal path.** A crawl that stops early still
    persisted whatever it discovered before stopping, so the outcome is
    stamped into the store (`record_crawl_status`) on the aborted and error
    paths, exactly as `crawl_menus()` stamps its own complete/truncated
    outcome — a partial map can never be mistaken for a finished one. Note
    that an abort on the very first screen therefore creates a store file
    holding an ``"aborted"`` stamp and no nodes: that is the honest record
    of a crawl that ran and stopped, and it happens only past the gate.

    Returns ``{"aborted": bool, "aborted_reason": str|None, "screens_seen":
    int, "nodes_visited": int|None, "truncated": bool, "frontier_remaining":
    int|None, "emitted_keys": [...], "send_log": [...]}``. Only
    `CrawlSafetyError` (the startup gate) and whatever `crawl_menus()` or
    `session_factory()` raise for a genuine structural failure (logged as
    ``"phase":"error"`` first, then re-raised — never swallowed) escape
    this function; an ordinary abort is the expected clean-stop path, not
    an error."""
    # Leg 1. Read with an explicit False default (fail-closed by
    # omission), then require exactly True (fail-closed against a merely
    # truthy stand-in). `is True` also never invokes a custom __bool__, so
    # a hostile profile object cannot raise its way past the gate either.
    if getattr(profile, _SACRIFICIAL_FLAG, False) is not True:
        raise CrawlSafetyError(
            f"refusing to crawl: profile {getattr(profile, 'name', None)!r} "
            f"is not flagged {_SACRIFICIAL_FLAG}"
        )

    log_fh = _open_log(log_path)
    try:
        _log_event(log_fh, "phase", phase="connect", max_nodes=max_nodes)
        screens_seen = [0]
        wrapped_factory = _wrap_session_factory(
            session_factory, abort_check, is_driver_fenced, log_fh, checkpoint_every, screens_seen
        )

        try:
            result = crawl_menus(wrapped_factory, path, max_nodes=max_nodes, step_timeout=step_timeout)
        except CrawlAborted as exc:
            record_crawl_status(
                path,
                status="aborted",
                reason=str(exc),
                nodes_visited=None,
                frontier_remaining=None,
            )
            _log_event(log_fh, "phase", phase="aborted", screens_seen=screens_seen[0], reason=str(exc))
            return {
                "aborted": True,
                "aborted_reason": str(exc),
                "screens_seen": screens_seen[0],
                "nodes_visited": None,
                "truncated": False,
                "frontier_remaining": None,
                "emitted_keys": [],
                "send_log": [],
            }
        except Exception as exc:  # observed + stamped + logged, then re-raised, never swallowed
            record_crawl_status(
                path,
                status="error",
                reason=repr(exc),
                nodes_visited=None,
                frontier_remaining=None,
            )
            _log_event(log_fh, "phase", phase="error", screens_seen=screens_seen[0], error=repr(exc))
            raise

        _log_event(log_fh, "summary", screens_seen=screens_seen[0], **result)
        _log_event(log_fh, "phase", phase="done", nodes_visited=result["nodes_visited"])
        return {"aborted": False, "aborted_reason": None, "screens_seen": screens_seen[0], **result}
    finally:
        log_fh.close()
