"""Pre-cockpit launcher + create-profile form (WO-P1-010…012).

Credentials/secrets are never collected or shown on these surfaces.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from typing import Callable, Sequence

import curses

from tw2002_aiclient.cockpit import decisions as cockpit_decisions
from tw2002_aiclient.cockpit import draw as cockpit_draw
from tw2002_aiclient.cockpit import focus as cockpit_focus
from tw2002_aiclient.cockpit import fold as cockpit_fold
from tw2002_aiclient.cockpit import goals as cockpit_goals
from tw2002_aiclient.cockpit import hud as cockpit_hud
from tw2002_aiclient.cockpit import liveness as cockpit_liveness
from tw2002_aiclient.cockpit import logsband as cockpit_logsband
from tw2002_aiclient.cockpit import tones as cockpit_tones
from tw2002_aiclient.cockpit.layout import frame_layout
from tw2002_aiclient.cockpit.strip import compose_profile_strip_from_row
from tw2002_aiclient.session import credentials


@dataclass(frozen=True)
class ProfileRow:
    """Non-secret profile summary for the picker (world-identity columns)."""

    name: str
    handle: str
    server: str  # catalog key or bare host label
    game_letter: str = ""
    host: str = ""  # resolved host for world-identity display
    autopilot: bool = False  # capability flag shown (ok tint) — not an armed run
    error: str | None = None  # parse failure — row stays visible (never dropped)


TITLE = " TW2002 AICLIENT "
SUBTITLE = " SELECT PROFILE "
CREATE_CTA = "Create New Player"
CREATE_TITLE = " CREATE NEW PLAYER "

# Shared 7-tone table -- SOURCED FROM cockpit.tones.SEMANTIC_COLORS (WO-P3-040
# single source of truth). screens.py used to fork its own literal copy of
# this table; every curses-facing consumer here (LauncherScreen's
# _TonePalette, PlayShellScreen's chrome/viewport-border colors) now resolves
# tone names off cockpit.tones directly, so a tone-table edit there needs no
# echo here. Values stay the pure (curses_fg_name, bold) shape tones.py
# defines; "muted" = terminal default, non-bold.
_SEMANTIC_COLORS: dict[str, tuple[str, bool]] = cockpit_tones.SEMANTIC_COLORS

_COLOR_NAME_TO_CURSES = {
    "green": curses.COLOR_GREEN,
    "yellow": curses.COLOR_YELLOW,
    "red": curses.COLOR_RED,
    "cyan": curses.COLOR_CYAN,
    "default": -1,
}


class _SharedPairs:
    """Process-lifetime curses color-pair allocator -- the ONLY place
    ``curses.init_pair``/``curses.start_color`` are called anywhere in this
    module (WO-P3-040 REVISE, Mack CRITICAL finding).

    ``curses`` color-pair NUMBERS are global to the whole terminal session,
    not scoped per class or per screen instance. Before this fix, every
    screen in this file hardcoded its OWN pair numbers with DIFFERENT
    colors: ``_TonePalette`` (the launcher's 7-tone palette) allocated
    pairs 1-7 sequentially at construction; ``PlayShellScreen``,
    ``BankViewScreen``, and ``CreateFormScreen`` each separately called
    ``curses.init_pair(1, ...)``/``curses.init_pair(2, ...)`` with their own
    colors. Constructing a SECOND screen mid-session silently
    **re-painted** whatever pair number(s) it happened to reuse -- and a
    curses attr int returned by ``curses.color_pair(n)`` only encodes the
    pair NUMBER, resolved to an actual color by the terminal at RENDER
    time, never at the moment the attr int was computed. So a
    previously-constructed screen's ALREADY-CACHED attr ints (e.g.
    ``LauncherScreen``'s ``self._ok``/``self._warn``, set once in
    ``__init__``) silently changed color out from under it the instant any
    other screen reused that pair number for something else. Reproduced:
    a launcher -> play -> Esc -> back round trip permanently repainted the
    SAME launcher instance's warn row red and its ok row cyan for the rest
    of the process (Mack's PoC) -- because ``PlayShellScreen`` happened to
    reuse pairs 1/2 for its own info/danger colors.

    The fix: exactly ONE process-lifetime allocator (this class, and the
    module-level ``_shared_pairs`` instance below). It allocates a pair
    number PER DISTINCT COLOR NAME on first request, caches it forever, and
    every later request for that same name returns the SAME pair number --
    so no two screens can ever collide, no matter how many are constructed
    across the app's lifetime, and no matter which order. Two tones that
    happen to share an fg name (``"ok"``/``"gain"`` both ``"green"``,
    ``"danger"``/``"loss"`` both ``"red"``) now legitimately share ONE
    underlying pair too -- a pure allocation-count optimization, not a
    behavior change, since callers still apply their own bold flag on top
    of the returned base attr.
    """

    def __init__(self) -> None:
        self._pair_for_name: dict[str, int] = {}
        self._next_pair = 1
        self._started = False

    def attr_for(self, color_name: str) -> int:
        """Base (non-bold) curses attr for ``color_name``. ``"default"``
        (or any name absent from ``_COLOR_NAME_TO_CURSES``) resolves to
        ``curses.A_NORMAL`` without ever consuming a pair number -- there
        is nothing to allocate for "no color". Never raises: a
        ``curses.error`` from ``init_pair`` (e.g. the pair table is
        exhausted) degrades that one call to ``curses.A_NORMAL`` rather
        than crashing the draw pass, the same honesty-over-crash
        convention every other curses-facing call in this module already
        follows."""
        if not curses.has_colors():
            return curses.A_NORMAL
        fg = _COLOR_NAME_TO_CURSES.get(color_name, -1)
        if fg == -1:
            return curses.A_NORMAL
        cached = self._pair_for_name.get(color_name)
        if cached is not None:
            return curses.color_pair(cached)
        if not self._started:
            curses.start_color()
            try:
                curses.use_default_colors()
            except curses.error:
                pass
            self._started = True
        pair_n = self._next_pair
        try:
            curses.init_pair(pair_n, fg, -1)
        except curses.error:
            return curses.A_NORMAL
        self._next_pair += 1
        self._pair_for_name[color_name] = pair_n
        return curses.color_pair(pair_n)


# One process-lifetime allocator shared by every screen in this module --
# see _SharedPairs' own docstring for why a per-class allocator corrupted
# other screens' already-cached colors.
_shared_pairs = _SharedPairs()

# Thin-rounded HUD chrome (launcher has no live viewport — never double-line).
_GLYPHS_UNICODE = {
    "tl": "╭",
    "tr": "╮",
    "bl": "╰",
    "br": "╯",
    "h": "─",
    "v": "│",
    "sel": "▸",
}
_GLYPHS_ASCII = {
    "tl": "+",
    "tr": "+",
    "bl": "+",
    "br": "+",
    "h": "-",
    "v": "|",
    "sel": ">",
}


def _unicode_ok() -> bool:
    """ASCII force via ``TW2002_ASCII=1``; otherwise prefer UTF-8-capable locale."""
    import os

    if os.environ.get("TW2002_ASCII", "").strip() == "1":
        return False
    return True


def _glyph_set() -> dict[str, str]:
    return _GLYPHS_UNICODE if _unicode_ok() else _GLYPHS_ASCII


def _safe_addstr(win: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    try:
        max_y, max_x = win.getmaxyx()
        if y < 0 or y >= max_y or x >= max_x:
            return
        clipped = text[: max(0, max_x - x - 1)]
        if clipped:
            win.addstr(y, x, clipped, attr)
    except curses.error:
        pass


def _draw_chrome_box(win: curses.window, attr: int) -> None:
    """Thin-rounded (or ASCII twin) chrome box — cyan is chrome, never data."""
    glyphs = _glyph_set()
    try:
        max_y, max_x = win.getmaxyx()
    except curses.error:
        return
    if max_y < 2 or max_x < 2:
        return
    h, v = glyphs["h"], glyphs["v"]
    _safe_addstr(win, 0, 0, glyphs["tl"] + h * (max_x - 2) + glyphs["tr"], attr)
    for y in range(1, max_y - 1):
        _safe_addstr(win, y, 0, v, attr)
        _safe_addstr(win, y, max_x - 1, v, attr)
    _safe_addstr(win, max_y - 1, 0, glyphs["bl"] + h * (max_x - 2) + glyphs["br"], attr)


class _TonePalette:
    """Resolve `_SEMANTIC_COLORS` tones to curses attrs (one table for the launcher)."""

    def __init__(self) -> None:
        self._attrs: dict[str, int] = {}
        self._init()

    def _init(self) -> None:
        if not curses.has_colors():
            # Monochrome: bold ≈ attention; underline ≈ warn; reverse still selection.
            self._attrs = {
                "ok": curses.A_BOLD,
                "warn": curses.A_BOLD | curses.A_UNDERLINE,
                "danger": curses.A_BOLD,
                "info": curses.A_BOLD,
                "gain": curses.A_BOLD,
                "loss": curses.A_BOLD,
                "muted": curses.A_NORMAL,
            }
            return
        # Colors resolve through the ONE shared process-lifetime allocator
        # (WO-P3-040 REVISE, Mack CRITICAL) -- no init_pair call here
        # anymore. See _SharedPairs' own docstring for why a per-class
        # allocator corrupted other screens' already-cached colors.
        for tone, (fg_name, bold) in _SEMANTIC_COLORS.items():
            attr = _shared_pairs.attr_for(fg_name)
            if bold:
                attr |= curses.A_BOLD
            self._attrs[tone] = attr

    def attr(self, tone: str) -> int:
        return self._attrs.get(tone, curses.A_NORMAL)

class LauncherScreen:
    """Branded profile picker: titled list, ↑/↓ selection, ``q`` to quit.

    Always ends with a **Create New Player** CTA. Empty picker = CTA only (cold join).
    Broken profiles keep their ``error`` inline and use a warn tint when color is available.
    """

    def __init__(self, stdscr: curses.window, profiles: Sequence[ProfileRow] | None = None) -> None:
        self.stdscr = stdscr
        self.profiles: list[ProfileRow] = list(profiles or ())
        self.selected = 0  # index into selectable items (profiles + trailing CTA)
        self._palette = _TonePalette()
        self._chrome = self._palette.attr("info")
        self._warn = self._palette.attr("warn")
        self._ok = self._palette.attr("ok")
        self._muted = self._palette.attr("muted")

    def set_profiles(self, profiles: Sequence[ProfileRow]) -> None:
        self.profiles = list(profiles or ())
        self.selected = min(self.selected, max(0, self._n_items - 1))

    @property
    def _n_items(self) -> int:
        # profiles (0..n) + Create CTA as last selectable
        return len(self.profiles) + 1

    def _is_cta(self, index: int) -> bool:
        return index == len(self.profiles)

    def _row_base_attr(self, row: ProfileRow) -> int:
        if row.error:
            return self._warn
        if row.autopilot:
            return self._ok
        return self._muted

    def draw(self) -> None:
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        glyphs = _glyph_set()
        if max_y >= 3 and max_x >= 10:
            _draw_chrome_box(self.stdscr, self._chrome)
            _safe_addstr(self.stdscr, 0, 2, TITLE, self._chrome | curses.A_BOLD)
            _safe_addstr(self.stdscr, 1, 2, SUBTITLE, self._chrome)

        list_top = 3
        y = list_top

        # Column header when any healthy profile is present (chrome, not data).
        if self.profiles and any(not p.error for p in self.profiles) and y < max_y - 2:
            _safe_addstr(
                self.stdscr,
                y,
                5,
                f"{'name':<14} {'handle':<14} {'host':<22} game",
                self._chrome,
            )
            y += 1

        # Profile rows (including broken — never silently dropped).
        for i, row in enumerate(self.profiles):
            if y >= max_y - 2:
                break
            selected = i == self.selected
            prefix = f"{glyphs['sel']} " if selected else "  "
            base = self._row_base_attr(row)
            # A_REVERSE is the one selection convention — never a second scheme.
            attr = (base | curses.A_REVERSE) if selected else base
            if row.error:
                label = f"{row.name}  ·  ERROR: {row.error}"
                _safe_addstr(self.stdscr, y, 3, prefix + label, attr)
            else:
                host = row.host or row.server or "?"
                letter = (row.game_letter or "—")[:1]
                left = f"{row.name:<14} {row.handle:<14} {host:<22} "
                letter_attr = (attr | curses.A_BOLD) if selected else (base | curses.A_BOLD)
                x = 3
                _safe_addstr(self.stdscr, y, x, prefix + left, attr)
                x += len(prefix + left)
                _safe_addstr(self.stdscr, y, x, f"[{letter}]", letter_attr)
            y += 1

        # Create New Player CTA — sole content when the picker is empty.
        if y < max_y - 2:
            cta_index = len(self.profiles)
            selected = self.selected == cta_index
            attr = curses.A_REVERSE if selected else curses.A_BOLD
            prefix = f"{glyphs['sel']} " if selected else "  "
            _safe_addstr(self.stdscr, y, 3, prefix + CREATE_CTA, attr)

        _safe_addstr(
            self.stdscr,
            max_y - 2,
            3,
            "↑/↓ select   Enter play/create   b bank   q quit",
            self._chrome,
        )
        self.stdscr.refresh()

    def handle_key(self, key: int) -> str | None:
        """Return ``quit`` / ``create`` / ``play`` / ``bank`` / ``None``."""
        if key in (ord("q"), ord("Q")):
            return "quit"
        if key in (ord("b"), ord("B")):
            return "bank"
        n = self._n_items
        if key in (curses.KEY_UP, ord("k")):
            self.selected = (self.selected - 1) % n
        elif key in (curses.KEY_DOWN, ord("j")):
            self.selected = (self.selected + 1) % n
        elif key in (curses.KEY_ENTER, 10, 13):
            if self._is_cta(self.selected):
                return "create"
            row = self.profiles[self.selected]
            if row.error:
                return None  # broken row stays on launcher
            return "play"
        return None

    def selected_profile(self) -> ProfileRow | None:
        if self._is_cta(self.selected) or not self.profiles:
            return None
        return self.profiles[self.selected]


PLAY_TITLE = " PLAY SHELL "
# Retained for import compatibility (tests/test_play_chrome_nav.py imports
# this name at module level) -- the chrome itself no longer draws this flat
# placeholder line; the GAME panel itself now draws an honest blank grid
# (PWO-051) rather than any placeholder text (PWO-031/033).
PLAY_SUBTITLE = " (placeholder — cockpit chrome is a later WO) "
BANK_TITLE = " PLAYER BANK "

# A raising composer (bad input surviving to a status field, a future
# panel's own bug, ...) must never take the whole cockpit down with it --
# same honesty-over-crash fallback as an unreachable/raising status_provider
# (Mack finding: the provider call was already guarded, the compose call
# wasn't). One honest-unknown line per panel, reusing the established
# em-dash glyph rather than inventing a second "something broke" vocabulary.
_GOALS_COMPOSE_FAILED = ["—"]
_FOCUS_COMPOSE_FAILED = ["—"]
# DECISIONS' own composer already defines its honest-empty state as
# ``["—", "Exploring…"]`` (canon `trainer-cockpit.md` "Panel states":
# `DECISIONS shows ["—", "Exploring…"]`) -- the raising-composer fallback
# mirrors that same two-line shape rather than the other panels' bare
# em-dash, so a compose-time crash still reads as "known-nothing, not a
# bug" instead of visibly regressing to a shorter, differently-shaped panel.
_DECISIONS_COMPOSE_FAILED = ["—", "Exploring…"]
# The responsive-fold composer (WO-P3-039, ``cockpit.fold.
# compose_folded_decisions_lines``) defines its own all-empty state as the
# same two-line ``["—", "Exploring…"]`` shape as unfolded DECISIONS (the
# fold relocates GOALS+FOCUS content INTO the DECISIONS pane; it does not
# invent a third empty-state vocabulary). A raising fold composer falls
# back to the single em-dash line GOALS/FOCUS already use, not the two-line
# shape -- a compose-time crash on the folded path is closer in spirit to
# "one of several stacked sections failed" than "the whole panel is
# honestly idle", so it reuses the plainer single-line fallback rather than
# claiming the two-line honest-empty state that the real composer reserves
# for "no data was folded in at all".
_FOLD_COMPOSE_FAILED = ["—"]
# HUD's own composer (PWO-037, ``cockpit.hud.compose_hud_cells``) already
# defines its own honest-empty state -- every cell sticky ``"-"`` with no
# freshness stamp, per-CELL rather than per-panel (canon
# `trainer-cockpit.md` "The always-on HUD and its freshness": a cold cell
# persists "-", never blank). The raising-composer fallback below is HUD's
# own ``(text, stale)`` cell shape, not the plain string list GOALS/FOCUS/
# DECISIONS use -- one honest-unknown, never-stale cell, reusing that same
# plain-hyphen vocabulary rather than the other panels' em-dash (HUD's
# sticky-unknown glyph is "-", not "—" -- ``cockpit.hud``'s own convention,
# distinct on purpose).
_HUD_COMPOSE_FAILED = [("-", False)]
# CONTROL_STRIP's own composer (WO-P3-038, ``cockpit.liveness.
# compose_liveness_cluster``) has no honest-empty convention of its own to
# borrow -- it is a bare motion cluster, not a panel with an empty state --
# so a raising composer falls back to the empty string (renders as a blank
# row this tick) rather than any invented placeholder text.
_CONTROL_STRIP_COMPOSE_FAILED = ""
# LOGS' own composer (WO-P3-041, ``cockpit.logsband.compose_logs_lines``)
# already defines its own single-line honest-empty state
# (``cockpit_logsband.LOGS_EMPTY``) -- a raising composer reuses that exact
# text rather than the other panels' em-dash, since LOGS never had an
# em-dash "unknown" vocabulary to begin with (its own honest-empty already
# reads as "known-nothing, not a bug"). Sliced to whatever height actually
# fits at draw time -- see ``draw()``'s own LOGS block.
_LOGS_COMPOSE_FAILED = [cockpit_logsband.LOGS_EMPTY]


def _resolve_last_rx_age_s(status: dict) -> float:
    """``status["idle_ms"]`` (the real wire field,
    ``tw2002_aiclient/session/protocol.py``'s ``status`` verb --
    ``resp["idle_ms"] = int((time.monotonic() - session.last_rx) * 1000)``)
    -> the ``last_rx_age_s`` seconds argument ``cockpit.tones.
    status_semantic`` expects. Defensive, never raises: a missing/
    non-numeric/non-finite/negative ``idle_ms`` all resolve to ``0.0``
    (freshest-possible, never fabricated staleness) -- this mirrors
    ``cockpit.tones``'s own ``_safe_rx_age`` policy of treating an unknown
    age as "we don't know how old this is", not "confidently very stale".
    Only reached once the caller has already confirmed a real, definite
    ``connected`` bool is present (see ``PlayShellScreen.
    _viewport_border_attr``'s honest-unknown gate) -- a missing/invalid
    ``idle_ms`` on an otherwise-real status payload still degrades to
    ``0.0`` rather than blocking the whole classification, since
    ``status_semantic`` only escalates past "ok" on staleness while
    ``connected`` is already ``True``."""
    idle_ms = status.get("idle_ms")
    try:
        idle_ms = float(idle_ms)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(idle_ms) or idle_ms < 0:
        return 0.0
    return idle_ms / 1000.0


BOUNDARY_LINE_1 = (
    "Rotation multiplies YOUR own daily turns across INDEPENDENT characters."
)
BOUNDARY_LINE_2 = (
    "Hard line: never transfer credits/cargo/assets between them."
)


class PlayShellScreen:
    """Trainer-cockpit frame bound to one launcher profile (WO-P1-016,
    PWO-031/033).

    Renders the two-weight bordered chrome from
    ``cockpit.layout.frame_layout``: a cyan-bold double-line outer frame
    titled ``PLAY SHELL``, the row-1 character/profile strip
    (``cockpit.strip.compose_profile_strip_from_row``), a three-column body
    (left gutter stacked GOALS above thin-rounded FOCUS | double-line
    GAME viewport | right gutter stacked thin-rounded HUD above thin-rounded
    DECISIONS, PWO-036), and the bottom thin-rounded LOGS band carrying the
    daemon's advancing session transcript tail (WO-P3-041, ``cockpit.
    logsband.compose_logs_lines``, falling back to the ensure-session
    ``status_line`` only while no real tail exists yet -- see the LOGS
    paragraph below). The live game viewport render itself is a later WO
    (PWO-052) -- GAME shows an honest blank 80x24 grid inside its
    double-line border today, zero inset, never placeholder text or fake
    content (PWO-051).
    Below the fold floor (``mode == "too_small"``) only the layout's
    refusal message is drawn. The left-gutter FOCUS box is the
    ``left_gutter`` region internally (unchanged region key -- only its
    drawn title and content are PWO-035; ``cockpit.layout``'s
    PRIORITIES_W/PRIORITIES_MIN_W geometry constants are untouched). The
    right-gutter HUD box is likewise still the ``right_gutter`` region
    internally (unchanged key, pre-dating the split); DECISIONS is the new
    ``decisions`` region below it.

    Responsive fold (WO-P3-039, canon `trainer-cockpit.md` "Responsive
    fold"): below ``layout.LEFT_GUTTER_MIN_COLS`` (138) the left gutter is
    absent entirely (``regions["goals"] is None``) while the DECISIONS host
    still survives -- GOALS and FOCUS relocate INTO the idle DECISIONS pane
    rather than disappearing, via ``cockpit.fold.
    compose_folded_decisions_lines`` in place of ``cockpit.decisions.
    compose_decisions_lines`` for that one draw call. The DECISIONS box
    title stays ``"DECISIONS"`` either way; only its content composer
    switches, gated on ``goals is None`` (the exact fold-active condition --
    see the DECISIONS draw call below). At >=138 cols nothing changes; below
    ``RIGHT_GUTTER_MIN_COLS`` (118) ``decisions`` itself drops to ``None``
    first, so there is no host left to fold into.

    ``status_provider`` (PWO-034/035/036/037, WO-P3-038) is the shared data
    seam for every panel that reads live daemon state -- GOALS and FOCUS in
    the left gutter, HUD and DECISIONS in the right, and now the
    ``control_strip`` liveness cluster (``cockpit.liveness.
    compose_liveness_cluster``) at the bottom: a no-arg callable returning a
    ``status`` dict (the daemon ``status`` verb shape) or ``None``.
    Defaults to ``None`` -- with no provider set, ``cockpit.goals.
    compose_goals_lines`` renders every row honestly unknown,
    ``cockpit.focus.compose_focus_lines`` renders its own honest-empty,
    ``cockpit.decisions.compose_decisions_lines`` renders its own
    ``["—", "Exploring…"]`` honest-empty, ``cockpit.hud.
    compose_hud_cells`` renders every cell sticky ``"-"`` with no freshness
    stamp, and ``compose_liveness_cluster`` renders its own idle ``→ -`` TX
    read, rather than any panel going blank or inventing content. Every
    panel reads the SAME single ``status_provider()`` snapshot per draw --
    one poll per tick, polled whenever ANY status-consuming region is
    present this tier (``goals``, ``decisions``, ``right_gutter``/HUD, OR
    ``control_strip`` -- never tied to any single one of them alone, so a
    fold that drops some of the four can never silently starve whichever
    one survives). ``app.py`` is the one place that assigns a real
    provider; a raising provider never crashes the draw pass (``draw()``
    catches around the call and falls back to ``None``, same
    honesty-over-crash convention as ``adapters.ensure_session``). HUD's
    own freshness dimming (``curses.A_DIM`` on stale value rows only, per
    ``cockpit.hud.FRESHNESS_STALE_S``) is drawn through
    ``cockpit_draw.draw_lines_attrs`` -- the per-line-attr sibling of
    ``draw_lines`` -- rather than ``draw_lines`` itself, since HUD is the
    one panel where some lines in the same box need a different attr than
    others (every other panel here still uses ``draw_lines``'s single flat
    attr).

    ``now_fn`` (WO-P3-038, extended by WO-P3-041) is a clock seam shared by
    the ``control_strip`` liveness cluster AND the LOGS newest-row flash
    below -- a no-arg callable returning a ``time.monotonic()``-shaped
    float, resolved ONCE per ``draw()`` call (not construction time) to the
    real ``time.monotonic`` when unset, and reused for both consumers
    rather than queried twice. Tests inject a scripted clock so the
    heartbeat phase (and, per this WO, the flash decision) is
    deterministic; the real refresh cadence (``app.py``'s 1 Hz
    ``stdscr.timeout(1000)``) is unchanged by this seam.

    LOGS (WO-P3-041, ``cockpit.logsband``): the SAME shared ``status``
    snapshot's ``log_tail`` field composes the box's advancing transcript
    (``compose_logs_lines``, newest-last, clipped to the box's one content
    row today). While ``cockpit_logsband.newest_tail_entry(status)`` is
    ``None`` -- no real daemon tail yet -- the box falls back to
    ``self.status_line`` (the local ensure-session progress/error string
    app.py sets) rather than the composer's own generic honest-empty
    marker, so the pre-tail ensure-session feedback (notably a failure
    reason) is never silently lost; once a real tail exists it supersedes
    the fallback entirely. The newest row renders ``curses.A_BOLD`` for
    ``cockpit_logsband.TICKER_FLASH_DURATION_S`` (1.0s, canon's LOGS/ticker
    flash duration -- distinct from the CREDITS delta-chip's own 1.5s) after
    a genuinely NEW newest entry is observed -- tracked as this instance's
    own content-identity state (``_logs_last_newest`` /
    ``_logs_newest_arrival_s``), since ``cockpit_logsband`` is a pure,
    stateless composer with no draw-to-draw memory of its own. The
    ``status_line`` fallback line never flashes (it is not real tail
    content).

    Every box border/title here renders in the ``"info"`` chrome tone
    (cyan, non-bold) sourced from ``cockpit.tones.SEMANTIC_COLORS`` -- the
    single source of truth (WO-P3-040) -- except the outer frame's own
    bold exception and the GAME viewport border's own STATE flip: cyan
    chrome by default, red non-bold the instant the same shared ``status``
    snapshot carries a real, definite ``connected: False`` (see
    ``_viewport_border_attr``). No mode badges and no gauge surface render
    here -- both are out of scope for this WO (mode badges belong to the
    N5 mode-line-and-teach-controls WO; ``gauge_semantic`` ships
    classifier-only, with no wired consumer yet).

    Esc ends the binding and returns to the launcher — clean close, not a suspend.
    """

    def __init__(
        self,
        stdscr: curses.window,
        profile: ProfileRow,
        *,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        self.stdscr = stdscr
        self.profile = profile
        self.status_line = ""  # set by app.py after the ensure_session() call
        self.status_provider: Callable[[], dict | None] | None = None  # set by app.py (PWO-034)
        self._now_fn = now_fn  # WO-P3-038 -- resolved to time.monotonic at draw() time when unset
        # LOGS newest-row flash (WO-P3-041): content-identity tracking across
        # draw() calls -- cockpit.logsband is a pure, stateless composer (no
        # clock, no draw-to-draw memory), so this instance is the only place
        # "did a NEW line just arrive" can live. See draw()'s own LOGS block.
        self._logs_last_newest: str | None = None
        self._logs_newest_arrival_s: float | None = None
        self._outer_attr = curses.A_NORMAL
        self._chrome_attr = curses.A_NORMAL
        self._viewport_danger_attr = curses.A_NORMAL  # WO-P3-040 -- set for real below
        self._init_colors()

    def _init_colors(self) -> None:
        # Tone-table fg names -- sourced from cockpit.tones via the
        # module-level _SEMANTIC_COLORS alias (WO-P3-040 single source of
        # truth), never a hardcoded curses.COLOR_* literal. The table's own
        # bold flags are deliberately NOT used below -- this class has its
        # own bold policy (outer frame bold, everything else non-bold,
        # including the viewport-border danger flip, which stays non-bold
        # even though the table's "danger" entry is bold=True elsewhere).
        info_fg_name, _unused_info_bold = _SEMANTIC_COLORS.get("info", ("cyan", False))
        danger_fg_name, _unused_danger_bold = _SEMANTIC_COLORS.get("danger", ("red", True))
        if not curses.has_colors():
            # Monochrome: bold marks the outer frame apart from the thin
            # instrument chrome, same as the launcher's monochrome fallback.
            # The viewport-border danger flip has no color to lean on here,
            # so it gets its own non-bold underline -- distinct from both the
            # bold-only outer frame and the plain chrome default, and never
            # A_REVERSE (reserved as the one selection/badge signal,
            # visual-language.md "load-bearing color rules").
            self._outer_attr = curses.A_BOLD
            self._chrome_attr = curses.A_NORMAL
            self._viewport_danger_attr = curses.A_UNDERLINE
            return
        # Colors resolve through the ONE shared process-lifetime allocator
        # (WO-P3-040 REVISE, Mack CRITICAL) -- no init_pair call here
        # anymore. See _SharedPairs' own docstring for why a per-class
        # allocator corrupted other screens' already-cached colors (this
        # class's own former init_pair(1, ...)/init_pair(2, ...) calls were
        # the reproduced culprit -- they silently repainted the launcher's
        # already-cached pairs 1/2 the instant a PlayShellScreen was
        # constructed mid-session).
        # Cyan is chrome, never data (visual-language.md); the outer frame is
        # the one bold exception -- every other border/title stays non-bold
        # "info" tone so the eye lands on the game viewport, not the frame.
        self._chrome_attr = _shared_pairs.attr_for(info_fg_name)
        self._outer_attr = self._chrome_attr | curses.A_BOLD
        # The viewport border's own STATE flip (visual-language.md "the
        # viewport border is a STATE surface"): red, deliberately NON-bold
        # per canon's own wording -- distinct from both the bold-cyan outer
        # frame and the non-bold-cyan default chrome, never the tone table's
        # own (red, bold=True) "danger" attr.
        self._viewport_danger_attr = _shared_pairs.attr_for(danger_fg_name)

    def _viewport_border_attr(self, status: dict | None) -> int:
        """The GAME viewport border's own STATE flip (WO-P3-040, canon
        `visual-language.md` "the viewport border is a STATE surface"):
        cyan chrome by default, ``self._viewport_danger_attr`` (red,
        non-bold) the instant the real daemon status verb reports
        ``connected: False``.

        HONEST-UNKNOWN RULE: ``cockpit.tones.status_semantic`` is only ever
        called below with a genuinely real, definite ``connected`` bool read
        straight off the wire (``tw2002_aiclient/session/protocol.py``'s
        ``status`` dispatch -- ``resp["connected"] = session.conn.
        connected``, always a real bool on an ``ok`` response). A non-dict
        ``status`` (no provider set, or the provider returned/raised
        nothing usable -- see ``draw()``'s own guard around the
        ``status_provider()`` call), or a dict that lacks a real ``bool``
        ``connected`` field (a malformed/partial payload), both leave the
        border at its default chrome cyan -- this method never claims
        danger without real data, matching every other panel's own
        honest-unknown convention in this file.

        Only the ``"danger"`` tone flips the border; ``"warn"``/``"ok"``
        both render as the unchanged default chrome (canon's own wording
        describes a strict connected/disconnected flip, not a three-way
        gauge -- no gauge/badge surface is in scope for this WO)."""
        if not isinstance(status, dict):
            return self._chrome_attr
        connected = status.get("connected")
        if not isinstance(connected, bool):
            return self._chrome_attr
        last_rx_age_s = _resolve_last_rx_age_s(status)
        tone = cockpit_tones.status_semantic(connected, last_rx_age_s)
        if tone == "danger":
            return self._viewport_danger_attr
        return self._chrome_attr

    def draw(self) -> None:
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        regions = frame_layout(max_y, max_x)
        if regions["mode"] == "too_small":
            cockpit_draw.draw_refuse_message(self.stdscr, regions["message"], self._outer_attr)
            self.stdscr.refresh()
            return

        uok = cockpit_draw.unicode_ok()

        # Outer frame -- double-line, cyan+bold, titled on its own top-border
        # row (row 1 below it is fully claimed by the character/profile strip).
        cockpit_draw.draw_box(
            self.stdscr, regions["outer"], weight="double", attr=self._outer_attr,
            title=PLAY_TITLE.strip(), title_attr=self._outer_attr, uok=uok,
        )

        strip_region = regions["strip"]
        strip_text = compose_profile_strip_from_row(
            self.profile, width=strip_region["w"] if strip_region else 0, unicode_ok=uok
        )
        # Strip content is profile identity -- DATA, not chrome. Canon
        # doctrine ("cyan is chrome, never data", visual-language.md) reads
        # as an interim ruling here pending hub ratification of this
        # concept's own promotion out of staged status; A_NORMAL (default
        # fg, non-bold) keeps the row itself un-tinted while the outer
        # frame's own border stays cyan around it.
        cockpit_draw.draw_lines(self.stdscr, strip_region, [strip_text], curses.A_NORMAL, boxed=False)

        goals = regions["goals"]
        cockpit_draw.draw_box(
            self.stdscr, goals, weight="thin", attr=self._chrome_attr,
            title="GOALS", title_attr=self._chrome_attr, uok=uok,
        )
        decisions = regions["decisions"]
        # One status_provider() snapshot per draw, shared by every panel
        # that reads it -- GOALS/FOCUS in the left gutter, HUD/DECISIONS in
        # the right. Polled whenever ANY of `goals`, `decisions`, OR
        # `right_gutter` (HUD) is present this tier -- they fold
        # independently (`goals` gates on the left gutter's own pri_w > 0
        # check, `decisions` on the right gutter's own height contention
        # against HUD_BOX_MIN_H, `right_gutter` on has_right_gutter alone),
        # so the poll must never stay tied to any single one of them.
        # `right_gutter` was added here (PWO-037) as the same class of gap
        # that starved DECISIONS pre-036: layout.py's own stacked-gutter
        # comment documents DECISIONS shrinking then dropping (`None`) once
        # HUD alone consumes the right gutter's slot, which would leave
        # `right_gutter` as the tier's ONLY live status consumer with both
        # `goals` and `decisions` `None`. (A `frame_layout` probe across
        # every reachable `(lines, cols)` at the CURRENT `MIN_LINES=20` /
        # `HUD_BOX_MIN_H=12` constants found no tier where that actually
        # happens -- `column_h` never falls below 14 at the MIN_LINES
        # floor, 2 rows clear of HUD_BOX_MIN_H, so `decisions` always
        # accompanies `right_gutter` today. This term is therefore
        # defensive, not a live-bug fix -- same "latent guard" shape
        # layout.py's own LOGS_MIN_H clamp already documents for a future
        # floor change -- never a second `status_provider()` call per
        # panel regardless.)
        #
        # `control_strip` was added here (WO-P3-038) as a FOURTH consumer
        # class -- and unlike `right_gutter` above, this one is LIVE, not
        # defensive: `control_strip` is present at every reachable
        # non-`too_small` tier today (layout.py's own CONTROL_STRIP_H
        # comment), INCLUDING the `minimal` tier (82..117 inner cols) where
        # `goals`/`decisions`/`right_gutter` are ALL `None` together (no
        # side gutters at all). Before this term, that tier polled zero
        # times per tick (see the now-updated
        # `tests/test_cockpit_hud_pty.py::
        # test_poll_guard_zero_calls_at_minimal_tier_with_no_status_consumer`,
        # which the WO-P3-038 dispatch flags as a disclosed 5th-file touch);
        # with `control_strip` present, that same real tier now needs
        # exactly one poll so the liveness cluster's `→ TX` read is live
        # rather than permanently idle-stub. Pinned by
        # `tests/test_cockpit_liveness_pty.py`'s own poll-guard test.
        #
        # Responsive fold (WO-P3-039) needs no FIFTH term here -- verified,
        # not assumed. The fold-active condition below (`goals is None`
        # while `decisions is not None`) is a strict subset of the existing
        # `decisions is not None` term: fold-active can only ever be true
        # when `decisions` is already present, so every fold-active tier
        # was already polling. No new gap, structurally -- not merely
        # unobserved at today's constants (unlike the `right_gutter` term
        # above, which IS a defensive/latent addition).
        #
        # The GAME viewport's own border-state flip (WO-P3-040,
        # `_viewport_border_attr` below) is a SIXTH consumer of this same
        # snapshot -- and, like the fold, needs no new term here either.
        # `layout.py`'s own CONTROL_STRIP comment establishes `control_strip`
        # is present at every reachable non-`too_small` size today,
        # independent of fold `mode` (explicitly including the `no_border`
        # tier where `center["border"]` is `False` and this new consumer
        # never even runs). So every tier where `center["border"]` could be
        # `True` already has `control_strip is not None` true and was
        # already polling -- structurally, not merely unobserved.
        #
        # LOGS (WO-P3-041, `cockpit.logsband.compose_logs_lines`) is a
        # SEVENTH consumer of this same snapshot -- and, like the fold and
        # the viewport-border flip above, needs no new term here either.
        # `logs` (unlike `right_gutter`/`decisions`/`goals`) has no `None`
        # branch of its own anywhere in `layout.py`'s non-`too_small` path
        # -- `logs_h_actual` is computed unconditionally and is always
        # >= 1 (LOGS claims its floor FIRST, before CONTROL_STRIP's own
        # carve). So `logs` is present at every reachable non-`too_small`
        # tier, the exact same footprint `control_strip` already has (see
        # `layout.py`'s own CONTROL_STRIP_H comment) -- `regions
        # ["control_strip"] is not None` in the guard below is therefore
        # already true at every tier where LOGS itself is drawn, and
        # LOGS's own status read (`status.get("log_tail")`,
        # `cockpit_logsband.newest_tail_entry`) shares this SAME polled
        # `status`, never a second `status_provider()` call.
        if (
            goals is not None
            or decisions is not None
            or regions["right_gutter"] is not None
            or regions["control_strip"] is not None
        ):
            try:
                status = self.status_provider() if self.status_provider is not None else None
            except Exception:  # noqa: BLE001 -- a raising provider must not crash the draw pass
                status = None
        else:
            status = None

        if goals is not None:
            goals_inner_w = max(0, goals["w"] - 2)
            try:
                goals_lines = cockpit_goals.compose_goals_lines(status, width=goals_inner_w)
            except Exception:  # noqa: BLE001 -- operator keeps control over panel-render failures
                goals_lines = _GOALS_COMPOSE_FAILED
        else:
            goals_lines = []
        cockpit_draw.draw_lines(self.stdscr, goals, goals_lines, curses.A_NORMAL)

        left = regions["left_gutter"]
        cockpit_draw.draw_box(
            self.stdscr, left, weight="thin", attr=self._chrome_attr,
            title="FOCUS", title_attr=self._chrome_attr, uok=uok,
        )
        if left is not None:
            left_inner_w = max(0, left["w"] - 2)
            try:
                focus_lines = cockpit_focus.compose_focus_lines(status, width=left_inner_w)
            except Exception:  # noqa: BLE001 -- a raising panel must not crash the draw pass
                focus_lines = _FOCUS_COMPOSE_FAILED
        else:
            focus_lines = []
        cockpit_draw.draw_lines(self.stdscr, left, focus_lines, curses.A_NORMAL)

        # GAME viewport (PWO-051): an honest blank grid -- zero content is
        # drawn into the interior on purpose (no placeholder text, no fake
        # data; the live pyte/settle paint itself is PWO-052). At the
        # bordered tiers only the double-line frame + title render, leaving
        # the interior cells whatever `erase()` already left them (blank);
        # at the `no_border` tier (`center["border"]` False) nothing is
        # drawn at all -- the region stays reserved by `frame_layout`, same
        # "reserved but unpainted" convention the tall-terminal gap band
        # already uses elsewhere in this frame.
        center = regions["center"]
        if center is not None and center["border"]:
            # WO-P3-040: the viewport border's own STATE flip -- cyan
            # chrome by default, red non-bold the instant a real,
            # definite `connected: False` reaches us (honest-unknown
            # otherwise; see `_viewport_border_attr`'s own docstring).
            border_attr = self._viewport_border_attr(status)
            cockpit_draw.draw_box(
                self.stdscr, center, weight="double", attr=border_attr,
                title="GAME", title_attr=border_attr, uok=uok,
            )

        right = regions["right_gutter"]
        cockpit_draw.draw_box(
            self.stdscr, right, weight="thin", attr=self._chrome_attr,
            title="HUD", title_attr=self._chrome_attr, uok=uok,
        )
        if right is not None:
            hud_inner_w = max(0, right["w"] - 2)
            try:
                hud_cells = cockpit_hud.compose_hud_cells(
                    status, width=hud_inner_w, unicode_ok=uok
                )
            except Exception:  # noqa: BLE001 -- a raising panel must not crash the draw pass
                hud_cells = _HUD_COMPOSE_FAILED
        else:
            hud_cells = []
        # HUD dims only STALE VALUE rows (content stays data-tone, never a
        # color swap -- "cyan is chrome, never data") -- the one panel
        # needing draw_lines_attrs' per-line attr rather than draw_lines'
        # single flat one.
        hud_lines_attrs = [
            (text, curses.A_DIM if stale else curses.A_NORMAL) for text, stale in hud_cells
        ]
        cockpit_draw.draw_lines_attrs(self.stdscr, right, hud_lines_attrs)

        cockpit_draw.draw_box(
            self.stdscr, decisions, weight="thin", attr=self._chrome_attr,
            title="DECISIONS", title_attr=self._chrome_attr, uok=uok,
        )
        if decisions is not None:
            decisions_inner_w = max(0, decisions["w"] - 2)
            # Responsive fold (WO-P3-039, canon `trainer-cockpit.md`
            # "Responsive fold"): below `LEFT_GUTTER_MIN_COLS` (138) the
            # left gutter is absent entirely (`goals is None`) while the
            # right gutter/DECISIONS host still survives -- GOALS+FOCUS
            # relocate INTO the idle DECISIONS pane rather than
            # disappearing. `goals is None` (checked here, inside the
            # already-established `decisions is not None` guard) is
            # therefore the exact fold-active condition: at >=138 `goals`
            # is present and this stays the unfolded path; below 118
            # `decisions` itself drops to `None` first (no host to fold
            # into -- nothing to wire, per canon's own ladder), so this
            # branch is only ever reached at a genuine narrow-right tier.
            if goals is None:
                try:
                    decisions_lines = cockpit_fold.compose_folded_decisions_lines(
                        status, width=decisions_inner_w
                    )
                except Exception:  # noqa: BLE001 -- a raising panel must not crash the draw pass
                    decisions_lines = _FOLD_COMPOSE_FAILED
            else:
                try:
                    decisions_lines = cockpit_decisions.compose_decisions_lines(
                        status, width=decisions_inner_w
                    )
                except Exception:  # noqa: BLE001 -- a raising panel must not crash the draw pass
                    decisions_lines = _DECISIONS_COMPOSE_FAILED
        else:
            decisions_lines = []
        cockpit_draw.draw_lines(self.stdscr, decisions, decisions_lines, curses.A_NORMAL)

        # `now_fn` (WO-P3-038, extended WO-P3-041): resolved ONCE per draw,
        # here -- `logs` is unconditionally present at every reachable
        # non-`too_small` tier (see the poll-guard comment above), so
        # hoisting this ahead of the LOGS block lets its own newest-row
        # flash and CONTROL_STRIP's heartbeat below share the identical
        # reading rather than each querying the clock separately.
        try:
            now_val = (self._now_fn or time.monotonic)()
        except Exception:  # noqa: BLE001 -- a raising now_fn must not crash the draw pass
            # Fall back to the REAL clock, not a frozen 0.0: the
            # heartbeat's whole job is proving the draw loop is still
            # running (canon "always breathing... so 'alive' reads even
            # on a settled screen") -- the loop IS running (we got this
            # far), so the true signal should survive a broken injected
            # clock rather than lying still.
            now_val = time.monotonic()

        logs = regions["logs"]
        cockpit_draw.draw_box(
            self.stdscr, logs, weight="thin", attr=self._chrome_attr,
            title="LOGS", title_attr=self._chrome_attr, uok=uok,
        )
        logs_inner_w = max(0, logs["w"] - 2)
        logs_inner_h = max(0, logs["h"] - 2)
        try:
            current_newest = cockpit_logsband.newest_tail_entry(status)
        except Exception:  # noqa: BLE001 -- a raising panel must not crash the draw pass
            current_newest = None
        has_real_tail = current_newest is not None
        try:
            logs_lines = cockpit_logsband.compose_logs_lines(
                status, width=logs_inner_w, height=logs_inner_h
            )
        except Exception:  # noqa: BLE001 -- a raising panel must not crash the draw pass
            logs_lines = _LOGS_COMPOSE_FAILED[:logs_inner_h]
            has_real_tail = False  # a raising composer can't be trusted to carry real content
        # `status_line` fallback (WO-P3-041): while there is no real daemon
        # tail (`has_real_tail` False -- honest-empty OR a raising
        # composer), surface app.py's own ensure-session progress/error
        # text instead of the composer's generic marker, so that feedback
        # (notably a failure reason) is never silently lost. Keyed off
        # `has_real_tail` (derived from `newest_tail_entry`, independent of
        # any width-driven truncation `compose_logs_lines` may have already
        # applied to its OWN honest-empty text) rather than a fragile
        # string comparison against the (possibly-clipped) composed line.
        if not has_real_tail and self.status_line and logs_inner_h > 0:
            logs_lines = [self.status_line[:logs_inner_w]] if logs_inner_w > 0 else [""]

        # Newest-row flash (WO-P3-041, canon "the newest LOGS/ticker row
        # flashes on arrival"): content-identity tracking is THIS
        # instance's own state -- `cockpit_logsband` is a pure, stateless
        # composer with no draw-to-draw memory. A changed `current_newest`
        # (including a transition to/from `None`) is a fresh arrival;
        # an unchanged one leaves the prior arrival timestamp untouched.
        # Known limitation (accepted): a consecutive genuinely-new arrival
        # with IDENTICAL text to the tracked newest does not re-flash
        # (realistic under per-keystroke attach, repeated identical keys);
        # ring churn at TAIL_MAX makes length-based detection equally
        # blind. Canon's "just-arrived" wording doesn't promise per-
        # duplicate flashes. Fix: session-side arrival counter (follow-on).
        if current_newest != self._logs_last_newest:
            self._logs_last_newest = current_newest
            self._logs_newest_arrival_s = now_val if current_newest is not None else None
        try:
            logs_newest_flashing = cockpit_logsband.flash_active(
                self._logs_newest_arrival_s, now=now_val
            )
        except Exception:  # noqa: BLE001 -- a raising helper must not crash the draw pass
            logs_newest_flashing = False

        logs_attrs = [(line, curses.A_NORMAL) for line in logs_lines]
        if has_real_tail and logs_newest_flashing and logs_attrs:
            # Only the bottom (newest) line ever flashes, and only when it
            # is genuine tail content -- the `status_line` fallback line
            # above never flashes (it is not a transcript arrival).
            last_text, _ = logs_attrs[-1]
            logs_attrs[-1] = (last_text, curses.A_BOLD)
        cockpit_draw.draw_lines_attrs(self.stdscr, logs, logs_attrs)

        # CONTROL_STRIP (WO-P3-038): the frame's own bottom-most interior
        # row, a bare content row (no box -- same `boxed=False` shape as the
        # row-1 profile strip) carrying ONLY the liveness cluster, right-
        # aligned. Everything else the canon mock shows on this row (mode
        # badge, A/R/T teach keys, run/record/panic cluster) belongs to the
        # N5 mode-line-and-teach-controls WO -- left deliberately blank here.
        control_strip = regions["control_strip"]
        if control_strip is not None:
            cs_w = control_strip["w"]
            try:
                liveness_text = cockpit_liveness.compose_liveness_cluster(
                    status, now=now_val, width=cs_w, unicode_ok=uok
                )
            except Exception:  # noqa: BLE001 -- a raising composer must not crash the draw pass
                liveness_text = _CONTROL_STRIP_COMPOSE_FAILED
            control_strip_lines = [liveness_text.rjust(cs_w)] if cs_w > 0 else [""]
        else:
            control_strip_lines = []
        cockpit_draw.draw_lines(
            self.stdscr, control_strip, control_strip_lines, curses.A_NORMAL, boxed=False
        )

        self.stdscr.refresh()

    def handle_key(self, key: int) -> str | None:
        """Return ``back`` / ``quit`` / ``None``."""
        if key == 27:  # Esc — end binding, return to launcher
            return "back"
        if key in (ord("q"), ord("Q")):
            return "quit"
        return None


class BankViewScreen:
    """Credential-bank rotation touchpoint — metadata only (WO-P1-015)."""

    def __init__(
        self,
        stdscr: curses.window,
        entries: Sequence[dict[str, str]] | None = None,
    ) -> None:
        self.stdscr = stdscr
        self.entries = list(entries or ())
        self._chrome = curses.A_NORMAL
        self._warn = curses.A_BOLD
        self._init_colors()

    def _init_colors(self) -> None:
        # Reuses _TonePalette (WO-P3-040 REVISE, Mack single-source MEDIUM +
        # CRITICAL pair-collision fix) instead of this screen's own former
        # curses.init_pair(1, ...)/init_pair(2, ...) calls -- "chrome"/"warn"
        # here mean exactly the tone table's "info"/"warn" tones (cyan
        # non-bold / yellow bold), and _TonePalette's own monochrome
        # fallback (bold "info", bold+underline "warn") is already
        # byte-identical to this class's prior standalone mono fallback, so
        # reusing it changes zero visible behavior while routing every pair
        # allocation through the one shared, collision-free mechanism.
        palette = _TonePalette()
        self._chrome = palette.attr("info")
        self._warn = palette.attr("warn")

    def draw(self) -> None:
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        if max_y >= 3 and max_x >= 10:
            try:
                self.stdscr.attron(self._chrome)
                self.stdscr.box()
                self.stdscr.attroff(self._chrome)
            except curses.error:
                pass
            _safe_addstr(self.stdscr, 0, 2, TITLE, self._chrome | curses.A_BOLD)
            _safe_addstr(self.stdscr, 1, 2, BANK_TITLE, self._chrome)

        # Boundary shown at the touchpoint — never buried.
        _safe_addstr(self.stdscr, 2, 3, BOUNDARY_LINE_1, self._warn)
        _safe_addstr(self.stdscr, 3, 3, BOUNDARY_LINE_2, self._warn)

        y = 5
        header = (
            f"{'name':<16} {'handle':<16} {'host':<24} "
            f"{'game':<3} {'last_played':<21} turns"
        )
        _safe_addstr(self.stdscr, y, 3, header, self._chrome)
        y += 1
        if not self.entries:
            _safe_addstr(
                self.stdscr,
                y,
                3,
                "(bank empty — add profiles; rotation history shows never / -)",
                curses.A_DIM,
            )
        else:
            for entry in self.entries:
                if y >= max_y - 2:
                    break
                line = (
                    f"{entry.get('name', '?'):<16} "
                    f"{entry.get('handle', '?'):<16} "
                    f"{entry.get('host', '?'):<24} "
                    f"{entry.get('game_letter', '?'):<3} "
                    f"{entry.get('last_played', 'never'):<21} "
                    f"{entry.get('turns_state', '-')}"
                )
                _safe_addstr(self.stdscr, y, 3, line, curses.A_NORMAL)
                y += 1

        _safe_addstr(
            self.stdscr,
            max_y - 2,
            3,
            "Esc return to launcher",
            self._chrome,
        )
        self.stdscr.refresh()

    def handle_key(self, key: int) -> str | None:
        if key == 27:
            return "back"
        if key in (ord("q"), ord("Q")):
            return "quit"
        return None


# Field kinds on the create form (server picker + two text fields). No secret fields.
_FORM_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("server", "Server", "server"),
    ("game_letter", "Game letter", "text"),
    ("handle", "Handle", "text"),
)


def validate_create_form(
    *,
    server: str,
    game_letter: str,
    handle: str,
    catalog_keys: Sequence[str] | None = None,
    existing_names: Sequence[str] | None = None,
) -> str | None:
    """UI-side create-form checks. Return an error string, or ``None`` if ok.

    Does not write. Rejects empty game letter, unknown catalog server keys, and
    duplicate profile section names (derived from handle when name is omitted).
    """
    game = (game_letter or "").strip()
    if not game:
        return "game letter required"
    handle_s = (handle or "").strip()
    if not handle_s:
        return "handle required"
    key = (server or "").strip()
    if not key:
        return "server catalog key required"
    keys = set(catalog_keys) if catalog_keys is not None else {
        str(s["key"]) for s in credentials.list_servers()
    }
    if key not in keys:
        return f"unknown server catalog key: {key!r}"
    section = re.sub(r"[^a-z0-9]+", "_", handle_s.lower()).strip("_") or "profile"
    names = (
        set(existing_names)
        if existing_names is not None
        else {str(r["name"]) for r in credentials.list_profile_summaries()}
    )
    if section in names:
        return f"profile already exists: {section}"
    return None


class CreateFormScreen:
    """Catalog server + game_letter + handle → non-secret ``create_profile`` write."""

    def __init__(self, stdscr: curses.window) -> None:
        self.stdscr = stdscr
        self.servers = credentials.list_servers()
        self.server_idx = 0
        self.values = {
            "game_letter": "B",
            "handle": "",
        }
        self.focus = 0
        self.editing = False
        self.edit_buf = ""
        self.error = ""
        self._chrome = curses.A_NORMAL
        self._warn = curses.A_BOLD
        self._init_colors()

    def _init_colors(self) -> None:
        # Reuses _TonePalette -- see BankViewScreen._init_colors' own
        # comment (WO-P3-040 REVISE, Mack single-source MEDIUM + CRITICAL
        # pair-collision fix); identical "chrome"/"warn" mapping and
        # byte-identical monochrome fallback, zero visible behavior change.
        palette = _TonePalette()
        self._chrome = palette.attr("info")
        self._warn = palette.attr("warn")

    def _server_key(self) -> str:
        if not self.servers:
            return ""
        return str(self.servers[self.server_idx]["key"])

    def _server_label(self) -> str:
        if not self.servers:
            return "(no servers in catalog)"
        row = self.servers[self.server_idx]
        return f"{row['key']}  ·  {row['name']}"

    def draw(self) -> None:
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        if max_y >= 3 and max_x >= 10:
            try:
                self.stdscr.attron(self._chrome)
                self.stdscr.box()
                self.stdscr.attroff(self._chrome)
            except curses.error:
                pass
            _safe_addstr(self.stdscr, 0, 2, TITLE, self._chrome | curses.A_BOLD)
            _safe_addstr(self.stdscr, 1, 2, CREATE_TITLE, self._chrome)

        if self.error:
            _safe_addstr(self.stdscr, 2, 3, f"! {self.error}", self._warn)

        for i, (key, label, kind) in enumerate(_FORM_FIELDS):
            y = 4 + i
            if y >= max_y - 2:
                break
            selected = i == self.focus
            attr = curses.A_REVERSE if selected and not self.editing else curses.A_NORMAL
            if kind == "server":
                shown = self._server_label()
            else:
                shown = self.values[key]
                if self.editing and selected:
                    shown = self.edit_buf + "_"
            line = f"{label:<14} {shown}"
            prefix = "▸ " if selected else "  "
            _safe_addstr(self.stdscr, y, 3, prefix + line, attr)

        _safe_addstr(
            self.stdscr,
            max_y - 2,
            3,
            "↑/↓ field  ←/→ server  e/Enter edit  s save  Esc cancel",
            self._chrome,
        )
        self.stdscr.refresh()

    def handle_key(self, key: int) -> str | None:
        """Return ``saved`` / ``cancel`` / ``None``."""
        field_key, _label, kind = _FORM_FIELDS[self.focus]

        if self.editing:
            if key == 27:  # Esc
                self.editing = False
                try:
                    curses.curs_set(0)
                except curses.error:
                    pass
            elif key in (curses.KEY_ENTER, 10, 13):
                value = self.edit_buf.strip()
                if field_key == "game_letter":
                    value = value.upper()[:1]
                self.values[field_key] = value
                self.editing = False
                try:
                    curses.curs_set(0)
                except curses.error:
                    pass
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                self.edit_buf = self.edit_buf[:-1]
            elif 32 <= key < 127:
                self.edit_buf += chr(key)
            return None

        if key in (27, ord("q"), ord("Q")):
            return "cancel"
        if key in (curses.KEY_UP, ord("k")):
            self.focus = (self.focus - 1) % len(_FORM_FIELDS)
        elif key in (curses.KEY_DOWN, ord("j")):
            self.focus = (self.focus + 1) % len(_FORM_FIELDS)
        elif key == ord("s"):
            return self._try_save()
        elif kind == "server" and key in (curses.KEY_LEFT, ord("h")):
            if self.servers:
                self.server_idx = (self.server_idx - 1) % len(self.servers)
        elif kind == "server" and key in (
            curses.KEY_RIGHT,
            ord("l"),
            curses.KEY_ENTER,
            10,
            13,
            ord(" "),
        ):
            if self.servers:
                self.server_idx = (self.server_idx + 1) % len(self.servers)
        elif kind == "text" and key in (ord("e"), curses.KEY_ENTER, 10, 13):
            self.editing = True
            self.edit_buf = self.values[field_key]
            try:
                curses.curs_set(1)
            except curses.error:
                pass
        return None

    def _try_save(self) -> str | None:
        # Snapshot field values first — a reject must leave them intact for correction.
        server = self._server_key()
        game_letter = self.values["game_letter"]
        handle = self.values["handle"]
        catalog_keys = [str(s["key"]) for s in self.servers]
        err = validate_create_form(
            server=server,
            game_letter=game_letter,
            handle=handle,
            catalog_keys=catalog_keys,
        )
        if err:
            self.error = err
            # Values untouched — operator corrects the bad field only.
            return None
        try:
            credentials.create_profile(
                server=server,
                game_letter=game_letter,
                handle=handle,
            )
        except Exception as exc:  # noqa: BLE001 — surface in TUI; values preserved
            self.error = str(exc)
            return None
        return "saved"
