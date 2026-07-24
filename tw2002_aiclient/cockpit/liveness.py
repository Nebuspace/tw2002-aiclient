"""Pure liveness composer for the trainer-cockpit control strip's "is it
frozen?" cluster (WO-P3-038, ``workorders/WO-P3-034-041-panels-PREP.md``).
Composes three independent liveness cues into one text line: the
always-breathing heartbeat glyph, the waiting spinner glyph, and the
``→ TX`` sent-keystroke readout.

No ``curses`` import here on purpose — mirrors ``tw2002_aiclient/cockpit/
hud.py`` / ``goals.py`` / ``focus.py`` / ``decisions.py``'s pure-composer
discipline: this module renders plain strings only, curses/attribute
handling belongs to the draw layer.

Canon grounding (`canon/surfaces/visual-language.md` glyph table + the
"Liveness-cue catalog"; `canon/surfaces/trainer-cockpit.md` "Liveness and
TX transparency" / "Liveness & motion"):

- **heartbeat** — ``●``/``○`` (ASCII ``*``/``.``), ``HEARTBEAT_PERIOD_S =
  0.8`` — "always breathing... so 'alive' reads even on a settled
  screen." ``heartbeat_glyph`` is a pure function of ``now`` alone, with
  **no calm override** — the archive's ``spectate_app.py`` additionally
  froze the heartbeat glyph during a fully-disconnected ``calm_idle``
  app state (steady, not breathing, to avoid a misleadingly "alive" look
  on a genuinely dead session); that app-level nuance is out of scope
  for this pure composer's agreed API (no calm/connected parameter) and
  is a caller decision — whether to even call this function during a
  known-dead session — not this module's. Canon's own framing ("always
  breathing") is the primary contract this module follows.
- **spinner** — braille ramp ``⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`` (ASCII ``|/-\\``) — "advances
  while connecting/between events; frozen at frame [0] when calm." The
  archive drove this from a stateful per-draw ``anim_tick`` counter owned
  by the app's render loop; this pure composer has no clock and no
  internal state, so the caller supplies the current frame number
  directly via ``frame`` — ``None`` (or anything that isn't a real,
  non-``bool`` ``int``) *is* the calm signal and freezes at ramp[0].
- **``→ TX``** — ``→ 158`` sent / ``→ -`` idle (`format_tx_readout`).
  ``→`` is **NO-SWAP** (`visual-language.md` glyph table, "sent-key / TX
  channel") — it never becomes an ASCII twin, unlike every other glyph
  in this module.

Upstream payload contract (WO-P3-038 dispatch — no wire bridge exists
yet; **this composer DEFINES the contract**, mirroring ``hud.py``'s own
in-module contract definition so the eventual wire bridge needs zero
composer rework)::

    status["tx"] = {"sent_count": <int|None>, "age_s": <float|None>}
    status["spinner_frame"] = <int|None>

``sent_count`` is a running tally of keystrokes sent this session — not
the last input's literal text (that stays out of this channel; see the
redaction note below). This is a deliberate translation of the archive's
``format_tx_readout(sent_input)`` (which rendered the last raw input
token, e.g. ``"158"``, treating any falsy value — ``None``, ``0``, an
empty string — as idle) into the JSON-wire dict shape the rest of this
codebase's composers use (mirroring ``hud.py``'s per-field
``{"value": ..., "age_s": ...}`` shape); the archive's own falsy-is-idle
policy is preserved verbatim: ``sent_count`` of ``0`` (or missing/``None``)
renders as idle ``→ -``, the same as the archive's ``if not sent_input``.
``age_s`` is accepted in the payload shape for forward-compat with a
future staleness treatment (mirroring HUD's ``age_s`` → freshness-stamp
story) but this module's frozen ``format_tx_readout(...) -> str``
signature has no staleness output to give it — **not consumed by this
WO's rendering**; a later WO may add a ``(text, stale)`` return the way
``hud.py``'s ``_field_cell`` does. ``spinner_frame`` is the app's own
per-draw tick counter (mirroring the archive's ``anim_tick``) — this
module never increments it itself; it only indexes the ramp with
whatever frame number it is handed.

**Redaction stance (verbatim per dispatch):** TX values arrive
pre-masked upstream from ``Session.send()`` — a ``--secret`` send is
already redacted before it ever reaches this module (see
[secrets-and-credentials](/doctrine/secrets-and-credentials.md)). This
module renders what it is handed and never unmasks, reconstructs, or
logs anything — and per current scope the readout renders only the
**count** (plus the heartbeat/spinner glyphs), never message content, so
no secret can transit this channel even if upstream masking failed.

Hardening family (matches ``hud.py``/``goals.py``/``focus.py``): every
public function is never-raises regardless of input shape. Non-finite/
negative/hostile ``now`` never raises — pinned to a deterministic
fallback: coercion failures and non-finite results collapse to ``0.0``,
and a negative-but-finite ``now`` clamps to ``0.0`` (mirroring
``hud.py``'s ``_safe_age`` clamp), which together naturally yield
heartbeat phase 0 rather than needing a separate special-cased branch.
A hostile ``status``/``tx`` per-field slot (one whose ``.get()`` raises)
is contained here, never escapes — the same per-item boundary
``hud.py``'s ``_field_cell`` draws around a hostile ``dict`` subclass;
the top-level ``status`` payload itself being a hostile ``dict``
subclass is out of contract, matching every sibling composer's own
top-level trust boundary. ``bool`` never silently renders as a number —
a ``sent_count`` of ``True``/``False`` degrades to idle ``→ -``
(mirroring ``hud.py``'s own bool-guard for numeric fields), and a
``bool`` ``frame`` is likewise treated as not-a-real-``int`` and freezes
the spinner at ramp[0] (the same defensive posture, applied here for
consistency even though the dispatch's explicit bool callout was for
``sent_count``). A huge ``sent_count`` or ``frame`` renders/indexes fine
(Python ints don't overflow); the composed cluster line is clipped only
by its own ``width`` clip, never a crash. Width coercion also catches
``OverflowError`` (not just ``TypeError``/``ValueError``) —
``int(float("inf"))`` raises ``OverflowError``, and JSON's bare
``Infinity`` literal decodes to exactly that float — a landmine this
module closes explicitly rather than inheriting.

D5: no ``ai_pilot``/imperative-mood text anywhere — this module renders
read-only liveness observations, never a command.
"""

from __future__ import annotations

import math

# Two parallel glyph tables, switched by a single unicode_ok flag — same
# discipline as the canon glyph table (`visual-language.md` "Two parallel
# glyph tables ... every chrome element ... degrades together, never
# per-glyph"). Ported verbatim from the archive's `terminal.py`
# GLYPHS_UNICODE/GLYPHS_ASCII "heartbeat"/"spinner" entries.
_HEARTBEAT_UNICODE: tuple[str, ...] = ("●", "○")
_HEARTBEAT_ASCII: tuple[str, ...] = ("*", ".")

_SPINNER_UNICODE: tuple[str, ...] = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_SPINNER_ASCII: tuple[str, ...] = ("|", "/", "-", "\\")

# Canon `trainer-cockpit.md` / `visual-language.md` — "always breathing
# ... HEARTBEAT_PERIOD_S = 0.8" — ported verbatim from the archive's
# `spectate_app.py` HEARTBEAT_PERIOD_S.
HEARTBEAT_PERIOD_S: float = 0.8

# The TX channel's idle text — the archive's `format_tx_readout`'s own
# `"→ -"` return for a falsy `sent_input`, ported verbatim. `→` is
# NO-SWAP (`visual-language.md` glyph table) so this constant is used
# unchanged regardless of `unicode_ok`.
_TX_IDLE = "→ -"


def heartbeat_glyph(now: object, *, unicode_ok: bool = True) -> str:
    """The always-breathing heartbeat glyph for a given clock reading.

    ``phase = int(now / HEARTBEAT_PERIOD_S) % 2`` — ported verbatim from
    the archive's ``spectate_app.py`` (``heartbeat_char = glyphs
    ["heartbeat"][int(now / HEARTBEAT_PERIOD_S) % len(glyphs
    ["heartbeat"])]``). Phase 0 is the filled dot (``●``/``*``), phase 1
    the hollow one (``○``/``.``) — a slow breathing pulse driven purely by
    ``now``, never by an internal clock or counter (this module never
    imports ``time``).

    Never raises: ``now`` that fails ``float()`` coercion (``None``, a
    string, a hostile object whose ``__float__`` raises), is non-finite
    (``inf``/``-inf``/``nan``), or is negative all degrade to a
    deterministic phase-0 reading — coercion failure and non-finite
    results collapse to ``0.0``, and a negative-but-finite value clamps
    to ``0.0`` (mirroring ``hud.py``'s ``_safe_age`` clamp), which
    naturally computes to phase 0 without a separate special case.
    """
    glyphs = _HEARTBEAT_UNICODE if unicode_ok else _HEARTBEAT_ASCII
    try:
        t = float(now)
    except Exception:
        t = 0.0
    if not math.isfinite(t):
        t = 0.0
    t = max(0.0, t)
    try:
        phase = int(t / HEARTBEAT_PERIOD_S) % len(glyphs)
    except Exception:
        phase = 0
    return glyphs[phase]


def spinner_glyph(frame: object = None, *, unicode_ok: bool = True) -> str:
    """The waiting-spinner glyph for a given frame number, or the calm
    (frozen) glyph when ``frame`` is ``None`` or anything else that isn't
    a real, non-``bool`` ``int``.

    ``frame`` is the caller's own per-draw tick counter (mirroring the
    archive's stateful ``anim_tick``, owned by the app's render loop, not
    this pure module) — a valid ``int`` indexes the ramp modulo its
    length (Python's ``%`` on a negative int yields a non-negative index,
    so a negative frame is still a valid, well-defined index, not an
    error). ``None``, a ``bool`` (``True``/``False`` must never silently
    act as ``1``/``0``), a ``float`` (even a whole-valued one — this
    module's frame contract is strictly ``int``, never a re-parsed
    numeric string or float), a string, or any other hostile/unexpected
    object all freeze at frame ``[0]`` — canon's "frozen at frame [0]
    when calm," extended here to cover every invalid input, not just the
    literal calm state.

    Never raises: a pathological ``int`` subclass whose ``__mod__``
    raises degrades to frame ``[0]`` rather than escaping.
    """
    glyphs = _SPINNER_UNICODE if unicode_ok else _SPINNER_ASCII
    if isinstance(frame, int) and not isinstance(frame, bool):
        try:
            return glyphs[frame % len(glyphs)]
        except Exception:
            return glyphs[0]
    return glyphs[0]


def _coerce_sent_count(value: object) -> int | None:
    """Best-effort ``sent_count`` coercion for the TX readout. Returns a
    positive ``int`` count, or ``None`` when the slot should render as
    idle (``→ -``): missing/``None``, a falsy ``0`` (mirrors the
    archive's own ``if not sent_input`` idle check, translated to the new
    dict shape), a ``bool`` (must never silently render as a number), a
    non-finite or fractional ``float``, a negative count, a ``str``, or
    any other hostile/unexpected value. A whole-valued ``float`` (e.g.
    ``158.0``) is accepted and converted to ``int`` — mirroring
    ``hud.py``'s own whole-valued-float handling — but a fractional one
    (e.g. ``158.5``) is not, since a fractional keystroke count is
    nonsensical wire data, not a legitimate count that merely arrived as
    a float.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        count = value
    elif isinstance(value, float):
        try:
            if not math.isfinite(value) or not value.is_integer():
                return None
            count = int(value)
        except Exception:
            return None
    else:
        return None
    if count <= 0:
        return None
    return count


def format_tx_readout(status: dict | None, *, unicode_ok: bool = True) -> str:
    """The ``→ TX`` sent-keystroke readout: ``→ {N}`` when a positive
    ``sent_count`` is known, ``→ -`` (``_TX_IDLE``) otherwise — a missing/
    non-``dict`` ``status``, a missing/non-``dict`` ``status["tx"]``, a
    missing/``None``/zero/negative/``bool``/non-finite/fractional
    ``sent_count``, or a hostile per-field slot all degrade to idle. See
    the module docstring's payload-contract section for the full
    ``status["tx"]`` shape and the redaction stance.

    ``unicode_ok`` is accepted for API uniformity with every sibling
    composer in this package but is never actually branched on here —
    ``→`` is **NO-SWAP** per the canon glyph table
    (`visual-language.md`), so this function renders the identical arrow
    in both Unicode and ASCII modes.

    Never raises regardless of ``status``'s shape or content — a hostile
    ``dict`` subclass planted at ``status["tx"]`` (one whose ``.get()``
    raises) is contained here, the same per-item boundary
    ``hud.py``'s ``_field_cell`` draws around a hostile per-field slot;
    the top-level ``status`` payload itself being a hostile ``dict``
    subclass is out of contract, matching every sibling composer's own
    top-level trust boundary.
    """
    status = status if isinstance(status, dict) else {}
    tx = status.get("tx")
    if not isinstance(tx, dict):
        return _TX_IDLE
    try:
        raw = tx.get("sent_count")
    except Exception:
        return _TX_IDLE
    count = _coerce_sent_count(raw)
    if count is None:
        return _TX_IDLE
    return f"→ {count}"


def _clip(text: str, *, width: int) -> str:
    if width <= 0:
        return ""
    return text[:width]


def compose_liveness_cluster(
    status: dict | None, *, now: object, width: int, unicode_ok: bool = True
) -> str:
    """Compose the control strip's liveness cluster: the heartbeat glyph,
    the spinner glyph, and the ``→ TX`` readout, space-separated in that
    fixed order (``"{heartbeat} {spinner} {tx}"``) — the archive never
    combined all three cues into a single line (its heartbeat/spinner
    lived on the status bar, its TX readout on a separate control-strip
    segment), so this ordering is this WO's own choice per the dispatch's
    fallback instruction, not a direct port.

    ``now`` drives the heartbeat (see ``heartbeat_glyph``); the spinner's
    frame and the TX ``sent_count``/``age_s`` both come from ``status``
    (``status["spinner_frame"]``, ``status["tx"]`` — see the module
    docstring's payload contract). A non-``dict`` ``status`` (including
    ``None``) degrades every field independently: heartbeat still
    computes from ``now`` alone (it has no dependency on ``status``), the
    spinner freezes calm at ramp[0], and TX reads idle ``→ -`` — never a
    partial crash.

    ``width`` clips the composed line to that many code points
    (``width <= 0``, or a value that can't coerce to ``int`` — including
    ``OverflowError``-raising inputs like ``float("inf")`` — empties the
    line to ``""``), mirroring ``goals.py``/``focus.py``/``decisions.py``/
    ``hud.py``'s own width-clip convention. The three glyph/readout
    functions this composes are never independently clipped — only the
    joined cluster line is.

    Never raises regardless of ``status``'s shape/content, ``now``'s
    type, or ``width``'s type.
    """
    try:
        width = int(width)
    except Exception:
        width = 0

    status = status if isinstance(status, dict) else {}
    frame = status.get("spinner_frame")

    heartbeat = heartbeat_glyph(now, unicode_ok=unicode_ok)
    spinner = spinner_glyph(frame, unicode_ok=unicode_ok)
    tx = format_tx_readout(status, unicode_ok=unicode_ok)
    line = f"{heartbeat} {spinner} {tx}"
    return _clip(line, width=width)
