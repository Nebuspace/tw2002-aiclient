"""Pure semantic-tone module (WO-P3-040) — the single-source ``ok``/``warn``/
``danger``/``info``/``gain``/``loss``/``muted`` color vocabulary every
cockpit surface renders through.

No ``curses`` import here on purpose — this module maps semantic tone names
to plain ``(color_name, bold)`` pairs and classifies raw signals into tone
names, nothing more. It mirrors ``tw2002_aiclient/cockpit/goals.py`` /
``hud.py`` / ``focus.py`` / ``decisions.py`` / ``fold.py``'s pure-composer
discipline: any caller (curses draw layer, a future non-curses renderer, a
test) turns a ``(color_name, bold)`` pair into an actual attribute — that
translation is deliberately out of scope here, same division of labor
``hud.py`` keeps from its own curses host.

Canon (`canon/surfaces/visual-language.md` "Color semantics — the one
7-tone table", ~31-108) is the single-source authority for both the palette
and the two shared classifiers; this module is that canon table given a
concrete on-disk home. Archive precedent (reference only — canon wins on
divergence, see below): the palette is ``_SEMANTIC_COLORS``
(``archive/pre-rebirth-2026-07-23/code/twclient/spectate_app.py`` ~1098-1114)
and the classifiers are ``status_semantic``/``gauge_semantic``
(``archive/pre-rebirth-2026-07-23/code/twclient/spectate_layout.py``
~2678-2706).

Deliberate departures from the archive, all canon- or hardening-driven:

- ``SEMANTIC_COLORS`` here is a 2-tuple ``(fg_name, bold)``, not the
  archive's 3-tuple ``(fg, bg, bold)``. Canon's table documents only
  fg/attr per tone (bg is "default" for every single archived entry, so it
  carries no information); this module drops the constant bg slot rather
  than ship a field that never varies.
- ``warn``'s fg name is the plain string ``"yellow"``, not the archive's
  pyte-library color name ``"brown"``. The archive's dict is consumed by
  ``spectate_app.py``'s pyte-to-curses color-pair machinery, where
  ``"brown"`` is pyte's own ANSI-yellow name (a naming quirk of that
  library, not a design choice — canon's own table calls this out
  verbatim). This module has no pyte import and is not that translation
  layer, so it names the color the way canon's table itself does:
  ``"yellow"``. Any future curses-attribute resolver that consumes
  ``SEMANTIC_COLORS`` is responsible for its own pyte-name mapping, the
  same way ``spectate_app.py``'s ``_PYTE_TO_CURSES_COLOR`` already is.
- ``SEMANTIC_COLORS`` is a ``types.MappingProxyType``, not a plain ``dict``
  (WO-P3-040 REVISE, Mack-flagged hardening). Every curses-facing consumer
  across the cockpit imports and aliases this single module-level object —
  a plain mutable ``dict`` would let a stray write through *any* one of
  those aliases silently corrupt the shared palette process-wide. The real
  mutable backing dict stays module-private (``_SEMANTIC_COLORS_MUTABLE``);
  the exported name is read-only, so an accidental write raises
  ``TypeError`` at the write site instead of propagating.

D5: no ``ai_pilot``/imperative-mood text anywhere — this module authors no
user-facing text at all, only color/tone data and classification.
"""

from __future__ import annotations

import math
from types import MappingProxyType

# The one 7-tone semantic palette (`canon/surfaces/visual-language.md`
# "Color semantics — the one 7-tone table"). Every value is
# ``(curses_color_name, bold)`` — plain strings, never curses constants, so
# this module stays import-clean of ``curses`` and any caller (curses draw
# layer, tests, a future renderer) resolves the actual attribute itself.
# Kept private/mutable here only so the module has a single place to define
# the table; every external reference is the read-only ``SEMANTIC_COLORS``
# proxy below.
_SEMANTIC_COLORS_MUTABLE: dict[str, tuple[str, bool]] = {
    "ok": ("green", True),
    "warn": ("yellow", True),
    "danger": ("red", True),
    "info": ("cyan", False),
    "gain": ("green", True),
    "loss": ("red", True),
    "muted": ("default", False),
}

# Deliberately read-only (``MappingProxyType``, not a plain ``dict``):
# every curses-facing consumer across the cockpit imports and aliases this
# exact object, so a stray write through any one of those aliases would
# silently corrupt the shared palette process-wide — assignment raises
# ``TypeError`` instead (Mack-flagged hardening, WO-P3-040 REVISE).
SEMANTIC_COLORS: MappingProxyType[str, tuple[str, bool]] = MappingProxyType(
    _SEMANTIC_COLORS_MUTABLE
)

# `status_semantic`'s liveness-staleness boundary (canon: "warn if
# last_rx_age_s >= 5.0"; archive `_STALE_RX_THRESHOLD_S`). Inclusive on the
# stale side, matching every other freshness boundary in this codebase
# (``hud.py``'s ``FRESHNESS_STALE_S`` is the same >= convention).
STALE_RX_THRESHOLD_S: float = 5.0

# `gauge_semantic`'s fill-fraction boundaries (canon: "ok >=0.5, warn
# >=0.2, else danger"; archive `_GAUGE_WARN_THRESHOLD`/
# `_GAUGE_DANGER_THRESHOLD`). Both inclusive on their named side.
_GAUGE_WARN_THRESHOLD: float = 0.5
_GAUGE_DANGER_THRESHOLD: float = 0.2


def _safe_connected(value: object) -> bool | None:
    """Best-effort truthiness for ``status_semantic``'s ``connected``
    argument. A real ``bool`` (or anything whose ``__bool__``/``__len__``
    resolves cleanly — an ``int``, a non-empty ``str``, ``None``, etc.)
    coerces via plain ``bool()`` and is returned as-is, ``True`` or
    ``False`` — this includes cleanly-falsy inputs like ``None``/``False``/
    ``0``, which mechanically mirror the archive's own
    ``if not connected: return "danger"`` branch (a real observed "not
    connected" state, not a coercion failure). Only when the object's own
    truthiness genuinely **cannot** be evaluated at all (a raising
    ``__bool__``/``__len__``) does this return ``None`` — the distinct
    "unevaluable" signal ``status_semantic`` maps to ``"warn"``, never
    ``"danger"``: see that function's docstring for the shared principle
    this shares with ``gauge_semantic``'s own hostile-fraction handling.
    Never raises."""
    try:
        return bool(value)
    except Exception:
        return None


def _safe_rx_age(value: object) -> float | None:
    """Best-effort seconds-age coercion for ``status_semantic``'s
    ``last_rx_age_s`` argument — mirrors ``hud.py``'s ``_safe_age`` verbatim
    (same family-standard hardening): ``None``, unparsable input, or a
    non-finite result (``Infinity``/``-Infinity``/``NaN`` — ``json.loads``
    accepts these by default) all become ``None``. A negative-but-finite
    age clamps to ``0.0`` (a real, just-skewed number, not an unknown one).
    The broad ``except Exception`` is the same never-raises backstop every
    sibling coercion helper in this codebase uses — a hostile ``__float__``
    that raises something unexpected still degrades honestly rather than
    escaping this module."""
    if value is None:
        return None
    try:
        age = float(value)
    except Exception:
        return None
    if not math.isfinite(age):
        return None
    return max(0.0, age)


def status_semantic(connected: object, last_rx_age_s: object) -> str:
    """Classify overall connection liveness into ``"danger"``/``"warn"``/
    ``"ok"`` (canon: "danger if disconnected; warn if last_rx_age_s >= 5.0;
    else ok"). Ported from the archive's ``status_semantic``
    (`spectate_layout.py` ~2681-2690).

    Policy split (load-bearing, do not re-derive): the "never claim danger
    without data" honest-unknown rule belongs to the *wire* — the daemon-
    side caller is documented to only invoke this with a real observed
    ``connected``/``last_rx_age_s`` pair, so it simply never calls this
    without real data in the first place. This function itself mechanically
    mirrors the archive's comparison semantics for whatever it's handed,
    hardened only against crashing:

    - A cleanly-evaluated ``connected`` (including cleanly-falsy ``None``/
      ``False``/``0`` — a real observed "not connected" state, not a
      coercion failure) follows the archive branch mechanically: falsy ->
      ``"danger"``, truthy -> continue to the age check.
    - An **unevaluable** ``connected`` (a raising ``__bool__``/``__len__`` —
      see ``_safe_connected``) degrades to ``"warn"``, **not**
      ``"danger"``. Shared principle with ``gauge_semantic`` (state it
      identically there): an unevaluable input degrades to warn —
      attention without claiming an observed state; the wire's
      honest-unknown rule means this path is defense-in-depth,
      unreachable when the wire honors its contract. Landing an
      unevaluable input on ``"danger"`` would be the exact same
      false-alarm-honesty mistake ``gauge_semantic`` explicitly rejects
      for its own hostile ``fraction`` — a classifier fed garbage must not
      claim a specific observed critical state either way.
    - A hostile/non-finite/unparsable ``last_rx_age_s`` counts as **not**
      stale (mirrors ``hud.py``'s own non-finite-``age_s`` policy: an
      unknown age is "we don't know how old this is", not "confidently very
      stale") -> falls through to ``"ok"`` when connected.
    - A negative-but-finite age clamps to ``0.0`` (a real, just-skewed
      number) rather than being treated as unknown.

    Never raises regardless of what either argument is."""
    is_connected = _safe_connected(connected)
    if is_connected is None:
        return "warn"
    if not is_connected:
        return "danger"
    age = _safe_rx_age(last_rx_age_s)
    if age is not None and age >= STALE_RX_THRESHOLD_S:
        return "warn"
    return "ok"


def _safe_fraction(value: object) -> float | None:
    """Best-effort ``[0.0, 1.0]``-clamped fraction coercion for
    ``gauge_semantic``'s ``fraction`` argument. ``None``, ``bool``,
    non-numeric, or non-finite (``Infinity``/``-Infinity``/``NaN``) input
    all become ``None`` (uncoercible); a real finite ``int``/``float`` is
    clamped into ``[0.0, 1.0]``.

    ``bool`` is deliberately excluded from numeric coercion even though
    ``isinstance(True, int)`` is ``True`` in Python — mirrors ``hud.py``'s
    ``_format_value`` bool-exclusion (same family-standard hardening): a
    JSON boolean is a legal-but-nonsensical gauge fraction and must never
    silently read as numeric ``1.0``/``0.0``.

    Clamping real numbers is a documentation/future-proofing choice, not a
    behavior-changing one under the current monotonic ``>=``/``>=``/else
    threshold ladder: an out-of-range value like ``1.5`` or ``-0.3``
    classifies identically whether or not it's clamped first (both land in
    the same tier the unclamped comparison already would). It's still
    applied explicitly so the pinned contract stays correct if the
    threshold ladder ever stops being monotonic, and so a caller reading
    this function in isolation never has to re-derive that equivalence."""
    if isinstance(value, bool):
        return None
    try:
        fraction = float(value)
    except Exception:
        return None
    if not math.isfinite(fraction):
        return None
    return max(0.0, min(1.0, fraction))


def gauge_semantic(fraction: object) -> str:
    """Classify a depleting gauge's fill fraction into ``"ok"``/``"warn"``/
    ``"danger"`` (canon: "ok >=0.5, warn >=0.2, else danger"). Ported from
    the archive's ``gauge_semantic`` (`spectate_layout.py` ~2697-2706).

    **Intentional scaffolding** (WO-CANON-DRAFT-GAUGE-SEMANTIC-WIRE-CONSUMER):
    no product caller on tip. The archive only invoked this from
    ``_turns_cell`` once ``tracked["_turns_max"]`` was known; the reborn
    tree has no ``turns_max`` accumulator, and ``cockpit/hud.py`` banks the
    turns fuel-gauge as a motion follow-on outside the freshness composer.
    Parked here (test-covered) until that follow-on lands — do not invent a
    no-op caller.

    The archive never hardened this function against a non-numeric
    ``fraction`` — with no wire-facing callers there is no archived
    precedent for the hostile-input branch. This module pins one
    deliberately, following the same "never claim more than the data
    supports" spirit ``status_semantic``'s honest-unknown framing and
    ``hud.py``'s non-finite-age policy already establish elsewhere in this
    codebase:

    - Uncoercible/``NaN``/``bool`` input maps to ``"warn"`` — **not**
      ``"danger"`` and **not** ``"ok"``. Shared principle with
      ``status_semantic`` (stated identically there): an unevaluable input
      degrades to warn — attention without claiming an observed state; the
      wire's honest-unknown rule means this path is defense-in-depth,
      unreachable when the wire honors its contract. ``"danger"`` would be
      WRONG-honesty: it asserts a critical, near-empty gauge from data that
      doesn't exist (and note that without an explicit finiteness check,
      Python's own ``nan >= 0.5`` and ``nan >= 0.2`` both evaluate
      ``False``, so an unguarded port of the archive's bare ladder would
      silently fall through to ``"danger"`` on ``NaN`` by accident — this
      function's ``_safe_fraction`` finiteness check exists specifically to
      intercept that trap). ``"ok"`` would be dishonestly reassuring for
      the same reason. ``"warn"`` is the one tone in the palette whose own
      canon meaning is literally "attention-needed" (canon: "warning ·
      stale · attention-needed") rather than a confident verdict in either
      direction — the honest register for "this gauge's fill level cannot
      currently be determined".
    - A real, finite (non-``bool``) number clamps into ``[0.0, 1.0]`` and
      then walks the normal ladder — see ``_safe_fraction``.

    Never raises regardless of what ``fraction`` is."""
    value = _safe_fraction(fraction)
    if value is None:
        return "warn"
    if value >= _GAUGE_WARN_THRESHOLD:
        return "ok"
    if value >= _GAUGE_DANGER_THRESHOLD:
        return "warn"
    return "danger"
