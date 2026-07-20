"""Pure layout/formatting for the spectator TUI (`tw spectate`).

No curses, no sockets, no I/O of any kind — every function here takes
plain data (an event dict shaped like protocol.build_response(), a
history list, a status dict) and returns plain strings. That's what makes
it unit-testable without a real terminal; spectate_app.py owns the
curses window management and calls these to get the text to draw.
"""

TICKER_MAX = 8
DEFAULT_EVENT = {"screen": [], "color": [], "prompt": "", "classification": "connecting...", "state": {}}

# Calm GAME-pane copy when the daemon has no live game/player link — so a
# leftover login prompt ("What's your name?") never contradicts status.
WAITING_SESSION_LINES = (
    "  No game session yet.",
    "",
    "  Spectate is attached to the local daemon, but the",
    "  game/player link is down — there is no live screen.",
    "",
    "  Start or reconnect a player, and this GAME pane",
    "  will show the world.",
    "",
    "  Status NO GAME LINK = daemon has no live telnet",
    "  session (spectate itself is fine; q quits viewer).",
)


def waiting_session_screen(game_h):
    """Placeholder lines for the GAME viewport when disconnected."""
    h = max(1, int(game_h or 1))
    lines = list(WAITING_SESSION_LINES)
    if len(lines) < h:
        lines.extend([""] * (h - len(lines)))
    return lines[:h]


def format_sidebar(event: dict) -> list[str]:
    state = event.get("state") or {}
    lines = [
        f"Classification: {event.get('classification', 'unknown')}",
        f"Settled:        {event.get('settled_reason', '-')}",
    ]
    if "sector" in state:
        lines.append(f"Sector:         {state['sector']}")
    if "credits" in state:
        lines.append(f"Credits:        {state['credits']:,}")
    if "turns_left" in state:
        lines.append(f"Turns left:     {state['turns_left']:,}")
    elif "turn_timer" in state:
        lines.append(f"Turn timer:     {state['turn_timer']}")
    if "warps" in state:
        lines.append(f"Warps:          {', '.join(str(w) for w in state['warps'])}")
    # Forward-compatible with a future confidence/novelty score (A5) —
    # rendered if present, silently skipped otherwise.
    if "confidence" in event:
        lines.append(f"Confidence:     {event['confidence']}")
    if "novelty" in event:
        lines.append(f"Novelty:        {event['novelty']}")
    port = state.get("port")
    if port and port.get("commodities"):
        lines.append("")
        lines.append("Port:")
        for c in port["commodities"]:
            lines.append(f"  {c['name']:<10} {c['status']:<7} {c['pct']:>3}%")
    return lines


def format_ticker_entry(event: dict) -> str:
    ts = event.get("ts", "")
    cls = event.get("classification", "unknown")
    reason = event.get("settled_reason", "-")
    prompt = (event.get("prompt") or "").strip()[:40]
    line = f"[{ts}] {cls} ({reason}) — {prompt}"
    # TX channel ("Core transparency", TUI-POLISH-PLAN.md): pair the send
    # that (likely) caused this settle with its outcome in one glance --
    # `sent_input` rides on every build_response() now (protocol.py), so
    # this is silently absent only for pre-TX-channel events (a bare
    # dispatch-harness test's synthetic event dict).
    sent = event.get("sent_input")
    if sent:
        line = f"{line}  →{sent}"
    return line


def format_status_line(connected=False, subscriber_count=0, last_rx_age_s=None, daemon_pid=None, **_extra) -> str:
    # **_extra absorbs forward-compatible fields on the status dict (e.g.
    # spectate_app.fetch_status()'s "host"/"name", added for the Phase 1
    # header) that this snapshot-only status line doesn't render -- same
    # "extend the dict, tolerate what you don't use" convention as
    # format_sidebar's confidence/novelty fields above.
    conn = "CONNECTED" if connected else "DISCONNECTED"
    age = f"{last_rx_age_s:.1f}s ago" if last_rx_age_s is not None else "-"
    pid = daemon_pid if daemon_pid is not None else "-"
    return f"{conn} | subscribers: {subscriber_count} | last-rx: {age} | daemon pid: {pid}"


def compose_dashboard(event: dict, ticker_history: list, status: dict) -> dict:
    """Compose the full dashboard as named text blocks — ready for either
    curses rendering (spectate_app.py) or flattening to plain stdout
    (render_plain(), used by `tw spectate --snapshot`).

    "main_color" (D13) rides alongside "main": a list of per-row color
    runs from the SAME event, so a curses renderer can zip them together
    by row index. render_plain() ignores it entirely — plain text has no
    use for it."""
    event = event or DEFAULT_EVENT
    return {
        "main": list(event.get("screen") or []),
        "main_color": event.get("color") or [],
        "sidebar": format_sidebar(event),
        "ticker": [format_ticker_entry(e) for e in ticker_history[-TICKER_MAX:]],
        "status": format_status_line(**status),
    }


# -- Bordered viewport + persistent HUD (TUI-POLISH-PLAN.md Phase 0/1/2) --
#
# Everything below is the reflow/HUD/liveness math for the INTERACTIVE
# curses path (spectate_app.py). It stays pure/curses-free -- same
# discipline as the dashboard functions above -- so the geometry and the
# HUD-accumulator behavior are unit-testable without a terminal.
# render_plain()/compose_dashboard() above are untouched and keep serving
# `tw spectate --snapshot`, which never exercises curses at all.

GAME_W, GAME_H = 80, 24
# The bordered viewport wraps the native grid with ZERO inner padding --
# border consumes exactly 1 row/col on every side, content starts
# immediately inside it. ANY extra inset here would shear the CP437
# box-art the game itself draws; see _content_inset() in spectate_app.py.
VIEWPORT_W, VIEWPORT_H = GAME_W + 2, GAME_H + 2  # 82 x 26

HUD_GUTTER_W = 26  # exactly VIEWPORT_W + HUD_GUTTER_W = 108, the right_gutter floor below
MINIMAL_HEADER_MIN_COLS = 82   # == VIEWPORT_W: the floor at which a bordered viewport fits at all
RIGHT_GUTTER_MIN_COLS = 108    # == VIEWPORT_W + HUD_GUTTER_W: viewport + one gutter, zero-margin fit
FULL_GUTTER_MIN_COLS = 132     # right_gutter's fit PLUS a comfortable centered margin (visual symmetry)
MIN_COLS = 60
MIN_LINES = 20
# TW-08: one-cell outer frame around the whole client. Layout math uses
# the INNER content size (cols/lines minus 2); thresholds above remain
# content floors — callers measuring a REAL terminal must add +2.
OUTER_FRAME_PAD = 1  # per side
# Titled LOG box needs ≥3 rows (border + 1 content + border).
LOG_BOX_MIN_H = 3


def frame_layout(lines: int, cols: int) -> dict:
    """Pure reflow: given the terminal's current (lines, cols), decide
    which chrome fits and return named regions ({"y","x","w","h", ...})
    for spectate_app's curses renderer to build windows from. No
    curses/terminal involved -- unit-testable directly, matching this
    module's existing pure-layout split.

    TW-08 wraps the entire client in an OUTER bordered frame. All other
    regions are laid out in the 1-cell inset; thresholds below are
    measured against that INNER content size.

    Ladder (cols-driven; height degrades by dropping header/ticker, then
    the control strip, then the viewport's own border, before ever
    falling to "too_small"):
      >=132  "full"          -- bordered viewport, CENTERED, + a right HUD gutter
      >=108  "right_gutter"  -- bordered viewport (left-anchored) + a right HUD gutter
      >=82   "minimal"       -- bordered viewport, centered, no side gutter
      >=60   "no_border"     -- viewport border dropped, game full-bleed/clipped
      else   "too_small"     -- refuse to render, existing message

    "control" (Trainer Control Panel, TUI-POLISH-PLAN.md) is an
    ADDITIVE region, folded in below the existing ladder rather than
    reshuffling it: one row, directly above "status", claiming leftover
    body space BEFORE "ticker" does (the control strip is the panel's
    primary interactive surface; the ticker is a nice-to-have event
    log) -- so a narrow-but-tall terminal shows mode/TX/hints even when
    there's no room left for the ticker underneath it.

    When a right HUD gutter is present and tall enough, its BOTTOM is
    split off into a titled "DECISIONS" box (placeholder content until
    TW-13). The bottom log ("ticker") is always a titled "LOG" box when
    present.
    """
    if lines < MIN_LINES or cols < MIN_COLS:
        return {
            "mode": "too_small",
            "message": (
                f"Terminal too small ({cols}x{lines}) — need at least "
                f"{MIN_COLS}x{MIN_LINES}. Resize to continue."
            ),
            "outer": None,
            "header": None,
            "viewport": None,
            "gutter": None,
            "decisions": None,
            "ticker": None,
            "control": None,
            "status": None,
        }

    outer = {"y": 0, "x": 0, "w": cols, "h": lines}
    ox = oy = OUTER_FRAME_PAD
    i_cols = cols - 2 * OUTER_FRAME_PAD
    i_lines = lines - 2 * OUTER_FRAME_PAD

    # The status bar (liveness lives there, Phase 2) is always reserved
    # once past the floor above — pinned to the last INNER row.
    status = {"y": oy + i_lines - 1, "x": ox, "w": i_cols, "h": 1}
    body_lines = i_lines - 1

    can_border = i_cols >= MINIMAL_HEADER_MIN_COLS and body_lines >= VIEWPORT_H
    if can_border:
        viewport_h, border = VIEWPORT_H, True
    else:
        viewport_h, border = min(GAME_H, body_lines), False
    viewport_w = VIEWPORT_W if border else min(GAME_W, i_cols)

    body_top = oy
    header = None
    if body_lines - viewport_h >= 1:
        header = {"y": oy, "x": ox, "w": i_cols, "h": 1}
        body_top = oy + 1

    leftover = body_lines - viewport_h - (1 if header else 0)

    control = None
    if leftover >= 1:
        control = {"y": status["y"] - 1, "x": ox, "w": i_cols, "h": 1}
        leftover -= 1

    ticker = None
    decisions = None
    # TW-08: leftover band hosts a titled LOG box; when wide enough, split
    # the same band side-by-side with DECISIONS so the HUD gutter stays
    # full-height for ship stats + live-metrics + port meters.
    if leftover >= LOG_BOX_MIN_H:
        band_h = min(5, leftover)
        band_y = status["y"] - (1 if control else 0) - band_h
        if i_cols >= 60:
            # Decisions is a short placeholder panel; keep LOG wide enough
            # that settle+TX suffixes remain readable.
            dec_w = min(24, max(16, i_cols // 5))
            log_w = i_cols - dec_w
            decisions = {
                "y": band_y, "x": ox + log_w, "w": dec_w, "h": band_h,
                "title": "DECISIONS", "border": True,
            }
            ticker = {
                "y": band_y, "x": ox, "w": log_w, "h": band_h,
                "title": "LOG", "border": True,
            }
        else:
            ticker = {
                "y": band_y, "x": ox, "w": i_cols, "h": band_h,
                "title": "LOG", "border": True,
            }

    if i_cols >= FULL_GUTTER_MIN_COLS:
        mode = "full"
        gutter = {"y": body_top, "x": ox + i_cols - HUD_GUTTER_W, "w": HUD_GUTTER_W, "h": viewport_h}
        viewport_x = ox + max(0, (i_cols - viewport_w - HUD_GUTTER_W) // 2)
    elif i_cols >= RIGHT_GUTTER_MIN_COLS:
        mode = "right_gutter"
        gutter = {"y": body_top, "x": ox + i_cols - HUD_GUTTER_W, "w": HUD_GUTTER_W, "h": viewport_h}
        viewport_x = ox
    elif i_cols >= MINIMAL_HEADER_MIN_COLS:
        mode = "minimal"
        gutter = None
        viewport_x = ox + max(0, (i_cols - viewport_w) // 2)
    else:
        mode = "no_border"
        gutter = None
        viewport_x = ox

    viewport = {
        "y": body_top,
        "x": viewport_x,
        "w": viewport_w,
        "h": viewport_h,
        "border": border,
        # The content area is ALWAYS <= the native 80x24 grid -- never
        # stretched to fill whatever's left over, only clipped when a
        # tier truly has no room for the full native size.
        "game_w": min(GAME_W, viewport_w - (2 if border else 0)),
        "game_h": min(GAME_H, viewport_h - (2 if border else 0)),
    }

    return {
        "mode": mode,
        "message": None,
        "outer": outer,
        "header": header,
        "viewport": viewport,
        "gutter": gutter,
        "decisions": decisions,
        "ticker": ticker,
        "control": control,
        "status": status,
    }


# -- The persistent HUD accumulator (the operator's directive) ------------
#
# `tracked` is an opaque dict of field -> (value, last_seen_monotonic_ts),
# threaded through spectate_app's main loop. update_tracked_stats() is
# pure (given `now`) so it's testable without a clock or a terminal:
# feed it a sequence of synthetic events and assert what's kept vs. what
# ages out.

FRESHNESS_STALE_S = 20.0  # a persisted cell dims past this many seconds untouched

_HUD_FIELD_SPECS = (
    ("credits", "CREDITS", lambda v: f"{v:,}"),
    ("sector", "SECTOR", lambda v: f"{v}"),
    ("cargo_holds_empty", "CARGO", lambda v: f"{v}"),
    ("profit", "PROFIT", lambda v: f"{v:+,}"),
)


CREDIT_TWEEN_DURATION_S = 0.3    # motion B2: count-up/down "slot machine tick" span
CREDIT_FLASH_DURATION_S = 1.5    # motion B1: how long the delta-flash/chip stays visible
TICKER_FLASH_DURATION_S = 1.0    # motion B3: newest-ticker-row flash-on-arrival span
CLASSIFICATION_PULSE_DURATION_S = 1.0  # motion B4: classification-change pulse span
CREDIT_SPARK_WIDTH = 20           # motion C1: how many recent credit samples the sparkline shows
TURNS_GAUGE_WIDTH = 10            # motion C5: turns-left fuel-gauge bar width
PORT_BAR_WIDTH = 10               # motion C4: port commodity %-meter bar width


def update_tracked_stats(tracked: dict, event: dict, now: float) -> dict:
    """Merge a new watch event into the persistent HUD accumulator.

    A field is updated ONLY when the event actually carries it -- the
    fix for the live bug this replaces: format_sidebar's old `if "credits"
    in state` check silently DROPPED credits on a credits-less screen
    (a submenu, a combat prompt) instead of keeping the last-known value.
    Values are read verbatim off the watch event's already-parsed
    `state` -- no local parser correction here (that's state_parser.py's
    job, out of this lane).

    `profit` is derived, not read off state directly: the delta between
    the CURRENT credits and the first credits value ever seen this
    spectate session (a simple, ledger-independent running total).

    This is also the single home for "something just happened, animate
    it" bookkeeping (Phase 3/4): `_ticker_flash_ts` (a new event arrived
    -- the ticker's newest row flashes), `_classification_pulse_ts` (the
    classification changed -- the header badge pulses), `_credits_flash`
    / `_credits_tween` (credits changed value -- the HUD cell flashes
    green/red with a floating delta chip and tweens the displayed number
    over CREDIT_TWEEN_DURATION_S), `_credit_series` (a bounded rolling
    window of recent credit samples for the sparkline -- built
    incrementally here, O(1) per event, rather than re-scanning the
    unbounded `ticker_history` list every render tick), `_turns_max` (the
    highest turns_left ever seen this session -- the fuel gauge's "full
    tank" denominator). One accumulator, not a second one.

    Returns a NEW dict (pure) -- the caller re-assigns its `tracked`.
    """
    if not event:
        return dict(tracked)
    state = event.get("state") or {}
    out = dict(tracked)
    out["_ticker_flash_ts"] = now

    classification = event.get("classification")
    if classification is not None:
        prev_cls = out.get("_prev_classification")
        if prev_cls is not None and prev_cls != classification:
            out["_classification_pulse_ts"] = now
        out["_prev_classification"] = classification

    for field, _label, _fmt in _HUD_FIELD_SPECS:
        if field in ("profit", "credits"):
            continue  # handled below (profit is derived; credits needs delta bookkeeping)
        if field in state:
            out[field] = (state[field], now)

    if "turns_left" in state:
        new_turns = state["turns_left"]
        prev_max = out.get("_turns_max")
        out["_turns_max"] = new_turns if prev_max is None else max(prev_max, new_turns)
        out["turns"] = (("count", new_turns), now)
    elif "turn_timer" in state:
        out["turns"] = (("timer", state["turn_timer"]), now)

    if "credits" in state:
        new_credits = state["credits"]
        prev_entry = tracked.get("credits")
        baseline = out.get("_credits_baseline")
        if baseline is None:
            out["_credits_baseline"] = (new_credits, now)
        else:
            out["profit"] = (new_credits - baseline[0], now)
        if prev_entry is not None and prev_entry[0] != new_credits:
            out["_credits_flash"] = (new_credits - prev_entry[0], now)
            out["_credits_tween"] = (prev_entry[0], new_credits, now)
        series = list(out.get("_credit_series") or [])
        series.append(new_credits)
        out["_credit_series"] = series[-CREDIT_SPARK_WIDTH:]
        out["credits"] = (new_credits, now)
    return out


def format_freshness(age_s: float, mark: str = "✦") -> str:
    """`✦ Ns ago` (or the ASCII fallback mark) -- NON-NEGOTIABLE per the
    plan: an always-on value without freshness reads as silently-current,
    and a confident HUD showing a stale balance is worse than no HUD."""
    age_s = max(0.0, age_s)
    if age_s < 1:
        return f"{mark} now"
    return f"{mark} {int(age_s)}s ago"


def is_recent(ts, now: float, duration: float) -> bool:
    """True while a recorded timestamp is still within its animation
    window -- the shared test every transient Phase 3 effect (ticker
    flash, classification pulse, credit flash/tween) uses to decide
    whether it's still active. `ts=None` (never happened) is never
    recent."""
    return ts is not None and (now - ts) < duration


def render_bar_meter(fraction: float, width: int, full_char: str = "█", empty_char: str = "░") -> str:
    """A `[███████░░]`-style bar meter (Phase 4) -- `fraction` clamped to
    [0, 1] first so an out-of-range input degrades to a full/empty bar
    instead of a garbled one."""
    fraction = max(0.0, min(1.0, fraction))
    filled = int(round(fraction * width))
    return "[" + full_char * filled + empty_char * (width - filled) + "]"


def render_sparkline(values: list, chars: str = "▁▂▃▄▅▆▇█") -> str:
    """One glyph per value from `chars`' low->high ramp, scaled to the
    series' own min/max (Phase 4 motion C1) -- NOT an absolute scale, so
    a session that only ever gains a little still shows visible texture.
    A flat series (every value equal, including a single sample) renders
    as the ramp's middle glyph throughout -- "no variance yet", not
    "all-time low"."""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        return chars[len(chars) // 2] * len(values)
    span = hi - lo
    out = []
    for v in values:
        frac = (v - lo) / span
        idx = min(len(chars) - 1, int(frac * len(chars)))
        out.append(chars[idx])
    return "".join(out)


_GAIN_LOSS_ARROWS = {"gain": "▲", "loss": "▼"}


def _credits_cell(tracked: dict, now: float, mark: str, delta_up: str, delta_down: str) -> dict:
    entry = tracked.get("credits")
    if entry is None:
        return {"label": "CREDITS", "value": "-", "freshness": "", "stale": False, "tone": None, "chip": "", "spark": ""}
    raw_value, ts = entry
    age = max(0.0, now - ts)

    display_value = raw_value
    tween = tracked.get("_credits_tween")
    if tween is not None and is_recent(tween[2], now, CREDIT_TWEEN_DURATION_S):
        from_v, to_v, start_ts = tween
        frac = max(0.0, (now - start_ts) / CREDIT_TWEEN_DURATION_S)
        display_value = int(round(from_v + (to_v - from_v) * frac))

    tone, chip = None, ""
    flash = tracked.get("_credits_flash")
    if flash is not None:
        delta, flash_ts = flash
        if is_recent(flash_ts, now, CREDIT_FLASH_DURATION_S):
            tone = "gain" if delta > 0 else "loss"
            arrow = delta_up if delta > 0 else delta_down
            chip = f"{delta:+,} {arrow}"

    spark = render_sparkline(tracked.get("_credit_series") or [])

    return {
        "label": "CREDITS",
        "value": f"{display_value:,}",
        "freshness": format_freshness(age, mark),
        "stale": age >= FRESHNESS_STALE_S,
        "tone": tone,
        "chip": chip,
        "spark": spark,
    }


def _turns_cell(tracked: dict, now: float, mark: str, bar_full: str, bar_empty: str) -> dict:
    entry = tracked.get("turns")
    if entry is None:
        return {"label": "TURNS", "value": "-", "freshness": "", "stale": False, "tone": None, "chip": "", "gauge": ""}
    (kind, value), ts = entry
    age = max(0.0, now - ts)
    tone, gauge = None, ""
    if kind == "timer":
        display = tick_down_timer(value, age)
    else:
        display = f"{value:,}"
        turns_max = tracked.get("_turns_max")
        if turns_max:  # 0/None -> no gauge, division-by-zero guard
            fraction = value / turns_max
            gauge = render_bar_meter(fraction, TURNS_GAUGE_WIDTH, bar_full, bar_empty)
            tone = gauge_semantic(fraction)
    return {
        "label": "TURNS",
        "value": display,
        "freshness": format_freshness(age, mark),
        "stale": age >= FRESHNESS_STALE_S,
        "tone": tone,
        "chip": "",
        "gauge": gauge,
    }


def _hud_cell(entry, label, fmt, now, mark):
    if entry is None:
        return {"label": label, "value": "-", "freshness": "", "stale": False, "tone": None, "chip": "", "spark": ""}
    value, ts = entry
    age = max(0.0, now - ts)
    return {
        "label": label,
        "value": fmt(value),
        "freshness": format_freshness(age, mark),
        "stale": age >= FRESHNESS_STALE_S,
        "tone": None,
        "chip": "",
        "spark": "",
    }


def compose_hud_cells(
    tracked: dict, now: float, mark: str = "✦",
    delta_up: str = "▲", delta_down: str = "▼",
    bar_full: str = "█", bar_empty: str = "░",
    autonomy: dict | None = None,
) -> list[dict]:
    """One cell per HUD stat, in the operator's fixed display order (CREDITS ·
    SECTOR · TURNS · CARGO · PROFIT) -- ready for either a vertical
    gutter panel or a horizontal header strip to lay out. A field with
    no data yet still gets a placeholder cell (value='-') so the HUD's
    shape never jumps around as fields arrive -- only their content
    fills in, same forward-compatible spirit as format_sidebar's
    confidence/novelty fields above.

    Every cell carries `tone` (None/"ok"/"warn"/"danger"/"gain"/"loss" --
    the SAME semantic vocabulary status_semantic()/gauge_semantic() use,
    so one color table serves the whole UI) for the renderer to color the
    value with, plus the Phase 3/4 per-field extras where they apply:
    CREDITS gets `chip` (a floating delta chip while a change is fresh)
    and `spark` (a rolling sparkline); TURNS gets `gauge` (a fuel-meter
    bar once a max is known). Cells that don't use an extra field still
    carry it as "" -- a uniform shape, not an inconsistent one, so a
    renderer never needs a per-cell isinstance/hasattr check.

    Optional `autonomy` is accepted for API compatibility but ignored here —
    a 6th 3-row HUD cell clips the PORT meters. Callers should prepend
    compose_autonomy_headline() into the METRICS list (one line) instead."""
    cells = [_credits_cell(tracked, now, mark, delta_up, delta_down)]
    cells.append(_hud_cell(tracked.get("sector"), "SECTOR", _HUD_FIELD_SPECS[1][2], now, mark))
    cells.append(_turns_cell(tracked, now, mark, bar_full, bar_empty))
    cells.append(_hud_cell(tracked.get("cargo_holds_empty"), "CARGO", _HUD_FIELD_SPECS[2][2], now, mark))
    cells.append(_hud_cell(tracked.get("profit"), "PROFIT", _HUD_FIELD_SPECS[3][2], now, mark))
    # Autonomy is NOT appended here — a 6th 3-row HUD cell clips PORT meters
    # in the gutter. Spectate_app injects it as a one-line METRICS row instead.
    return cells


# TW-08 live-metrics array (structure now; values from world-model later via TW-06).
# Fixed display order the operator named: Stations / Planets / Fighters /
# Mines / Problem-sectors. Always emit a full shape so the HUD never jumps.
_LIVE_METRIC_SPECS = (
    ("stations_found", "STATIONS"),
    ("planets_found", "PLANETS"),
    ("fighters_seen", "FIGHTERS"),
    ("mines_seen", "MINES"),
    ("problem_sectors", "PROBLEMS"),
)


def compose_live_metrics(tracked: dict | None = None) -> list[dict]:
    """HUD live-metrics rows (TW-08). Each key is live-trackable once the
    world-model fills `tracked`; until then every value is the placeholder
    `0` so the structure ships visible and stable."""
    tracked = tracked or {}
    rows = []
    for key, label in _LIVE_METRIC_SPECS:
        entry = tracked.get(key)
        if isinstance(entry, tuple) and len(entry) >= 1:
            value = entry[0]
        elif entry is None:
            value = 0
        else:
            value = entry
        rows.append({"label": label, "value": f"{int(value):,}" if isinstance(value, int) else str(value)})
    return rows


_PROBLEM_FORMATION_KINDS = frozenset({"one-way", "warp-sink"})
_PLANET_LANDMARK_TAGS = frozenset({"planet", "own_planet"})


def aggregate_world_metrics(sectors) -> dict:
    """Derive TW-08 metric counts from world-model sector records (read-only).

    Heuristic until canon tightens PROBLEM definitions: a sector counts as
    a problem when it has mines, any fighters sighting, or a one-way /
    warp-sink formation membership tag.
    """
    stations = planets = fighters = mines = problems = 0
    for sec in sectors or ():
        threats = sec.get("threats") or {}
        has_port = sec.get("port") is not None
        has_mines = threats.get("mines") is True
        has_fighters = threats.get("fighters") is not None
        landmarks = sec.get("landmarks") or []
        has_planet = False
        for lm in landmarks:
            lm_key = str(lm).casefold()
            if lm_key in _PLANET_LANDMARK_TAGS or "planet" in lm_key:
                has_planet = True
                break
        membership = sec.get("formation_membership") or []
        if isinstance(membership, str):
            membership = [membership]
        has_problem_formation = bool(
            _PROBLEM_FORMATION_KINDS.intersection(str(t).casefold() for t in membership)
        )
        if has_port:
            stations += 1
        if has_planet:
            planets += 1
        if has_fighters:
            fighters += 1
        if has_mines:
            mines += 1
        if has_mines or has_fighters or has_problem_formation:
            problems += 1
    return {
        "stations_found": stations,
        "planets_found": planets,
        "fighters_seen": fighters,
        "mines_seen": mines,
        "problem_sectors": problems,
    }


def stamp_world_metrics(tracked: dict, metrics: dict, now: float) -> dict:
    """Merge aggregate_world_metrics counts into tracked as (value, ts) tuples."""
    out = dict(tracked or {})
    for key, _label in _LIVE_METRIC_SPECS:
        if key in metrics:
            out[key] = (int(metrics[key]), now)
    return out


def compute_autonomy_ratio(entries, *, window: int = 500, session_id=None) -> dict:
    """§15.1 graduation gauge: trainer / (ai + trainer).

    Human actions are counted for display but excluded from the ratio
    denominator. Unknown/missing actor fields are ignored for ratio math.
    """
    rows = list(entries or ())
    if session_id is not None:
        rows = [e for e in rows if e.get("session_id") == session_id]
    if window is not None and window >= 0:
        rows = rows[-window:]
    trainer = ai = human = 0
    for e in rows:
        actor = e.get("actor")
        if actor == "trainer":
            trainer += 1
        elif actor == "ai":
            ai += 1
        elif actor == "human":
            human += 1
    denom = ai + trainer
    ratio = (trainer / denom) if denom else None
    if ratio is None:
        pct_display = "—"
    else:
        pct_display = f"{int(round(ratio * 100))}%"
    return {
        "ratio": ratio,
        "trainer": trainer,
        "ai": ai,
        "human": human,
        "pct_display": pct_display,
    }


def format_autonomy_counts(ratio_data: dict | None = None) -> str:
    """Max terms: App = trainer, AI = llm-pilot; Hum = human attach (ratio-excluded)."""
    data = ratio_data or {}
    app = int(data.get("trainer") or 0)
    ai = int(data.get("ai") or 0)
    human = int(data.get("human") or 0)
    return f"App {app} / AI {ai} · Hum {human}"


def format_autonomy_lines(ratio_data: dict | None = None) -> list[str]:
    """GOALS-band lines: AUTO % plus the counts that define it (App/(App+AI)).

    Kept out of the HUD METRICS gutter so PORT commodity meters stay unclipped.
    Empty ledger → "—" for % and zero counts (no crash).
    """
    data = ratio_data or {}
    pct = data.get("pct_display") or "—"
    return [f"AUTO {pct}", format_autonomy_counts(data)]


# -- WO-P2c Autopilot dry-run decision-trace (pure layout) -----------------

# Provisional mock until Impl #1's revised autopilot SHA relays real field
# names + transport. Hub negotiates; defensive .get() tolerates churn.
PROVISIONAL_AUTOPILOT_TRACE = {
    "tick": 3,
    "context": {"turns_left": 220, "cash": 48000, "sector": 42},
    "candidates": [
        {
            "kind": "run_chain",
            "ev_cr_per_turn": 550.0,
            "rationale": "loop @1↔3 margin 55/hold",
            "gated": False,
            "gate_reason": None,
        },
        {
            "kind": "upgrade",
            "ev_cr_per_turn": 200.0,
            "rationale": "Δ40 holds / 12t cycle",
            "gated": False,
            "gate_reason": None,
        },
        {
            "kind": "explore",
            "ev_cr_per_turn": 10.0,
            "rationale": "3 unmapped adj",
            "gated": True,
            "gate_reason": "turn-reserve<50",
        },
    ],
    "chosen": "run_chain",
}


def _trace_field(obj, key, default=None):
    """Dict-or-attr getter — same dual tolerance as format_chain_summary."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def format_trace_ev(value) -> str:
    """None-safe EV formatter — never guess/zero a missing value."""
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if v != v:  # NaN
        return "—"
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.1f}"


def format_autopilot_trace_lines(trace, *, cols: int = 22) -> list[str]:
    """Decisions-box lines for a Phase-1 autopilot dry-run decision trace.

    Header = chosen action + EV (`★ run_chain 550 cr/t`) or `HOLD`.
    Per candidate: `★` chosen / `·` other / `⊘` gated. Clipped to `cols`.
    Empty / None / malformed → `["—"]` (never crash).
    """
    cols = max(8, int(cols))
    if trace is None:
        return ["—"]
    if isinstance(trace, dict) and not trace:
        return ["—"]
    if not isinstance(trace, dict) and not (
        hasattr(trace, "chosen") or hasattr(trace, "candidates")
    ):
        return ["—"]

    candidates = _trace_field(trace, "candidates") or ()
    if not isinstance(candidates, (list, tuple)):
        candidates = ()
    # Explicit key missing on empty-ish objects → treat as malformed empty
    if isinstance(trace, dict) and "chosen" not in trace and not candidates:
        return ["—"]

    chosen_kind = _trace_field(trace, "chosen")
    # Non-str chosen (enum/dict/object) = malformed — fail-safe to "—"
    # so a provisional→real schema reconcile can't leak a Python repr.
    if chosen_kind is not None and not isinstance(chosen_kind, str):
        return ["—"]
    chosen_ev = None
    if chosen_kind is not None:
        for c in candidates:
            if _trace_field(c, "kind") == chosen_kind:
                chosen_ev = _trace_field(c, "ev_cr_per_turn")
                break

    if chosen_kind is None:
        header = "HOLD"
    else:
        header = f"★ {chosen_kind} {format_trace_ev(chosen_ev)} cr/t"
    lines = [header[:cols]]

    for c in candidates:
        kind = _trace_field(c, "kind") or "?"
        gated = bool(_trace_field(c, "gated"))
        gate_reason = _trace_field(c, "gate_reason")
        ev_s = format_trace_ev(_trace_field(c, "ev_cr_per_turn"))
        if gated:
            glyph = "⊘"
        elif chosen_kind is not None and kind == chosen_kind:
            glyph = "★"
        else:
            glyph = "·"
        body = f"{glyph} {kind} {ev_s}"
        if gated and gate_reason:
            rem = cols - len(body) - 1
            if rem > 2:
                body = f"{body} {str(gate_reason)[:rem]}"
        lines.append(body[:cols])
    return lines


def compose_autonomy_headline(ratio_data: dict | None = None) -> dict:
    """One HUD-shaped cell for the autonomy gauge (uniform with compose_hud_cells)."""
    data = ratio_data or {}
    value = data.get("pct_display") or "—"
    ratio = data.get("ratio")
    tone = None
    if isinstance(ratio, (int, float)):
        if ratio >= 0.5:
            tone = "ok"
        elif ratio > 0:
            tone = "warn"
    return {
        "label": "AUTONOMY",
        "value": value,
        "freshness": "",
        "stale": False,
        "tone": tone,
        "chip": "",
        "spark": "",
        "gauge": "",
    }


# -- WO-P2 Primary Goals + Longest-Chain panels (pure layout) --------------


class GoalsSnapshot:
    """Frozen-enough goals view for compose_primary_goals_lines (plain dict OK too)."""

    __slots__ = (
        "stardock_found", "stardock_sectors", "known_sectors", "formations",
        "genesis_candidates", "longest_chain_hops", "upgrade_status", "holds_status",
    )

    def __init__(
        self,
        *,
        stardock_found: bool = False,
        stardock_sectors=(),
        known_sectors: int = 0,
        formations: int = 0,
        genesis_candidates: int = 0,
        longest_chain_hops=None,
        upgrade_status: str = "—",
        holds_status: str = "—",
    ):
        self.stardock_found = bool(stardock_found)
        self.stardock_sectors = tuple(stardock_sectors or ())
        self.known_sectors = int(known_sectors)
        self.formations = int(formations)
        self.genesis_candidates = int(genesis_candidates)
        self.longest_chain_hops = longest_chain_hops
        self.upgrade_status = upgrade_status or "—"
        self.holds_status = holds_status or "—"


def compose_primary_goals_lines(snap, *, width: int = 22) -> list[str]:
    """Primary-goals panel lines (WO-P2-b). Status glyphs: ✓ / · / —."""
    width = max(12, int(width))
    if not isinstance(snap, GoalsSnapshot):
        snap = GoalsSnapshot(**(snap or {}))
    dock = "✓" if snap.stardock_found else "·"
    dock_detail = (
        f"@{','.join(str(s) for s in snap.stardock_sectors[:3])}"
        if snap.stardock_sectors else ""
    )
    chain = (
        f"✓ {snap.longest_chain_hops}h"
        if snap.longest_chain_hops
        else "·"
    )
    lines = [
        f"{dock} StarDock {dock_detail}".rstrip(),
        f"· map {snap.known_sectors}s · form {snap.formations}",
        f"{chain} longest chain",
        f"· upgrade {snap.upgrade_status}"[:width],
        f"· holds {snap.holds_status}"[:width],
    ]
    if snap.genesis_candidates:
        lines.append(f"· genesis {snap.genesis_candidates}")
    return [ln[:width] for ln in lines]


def format_chain_summary(
    chain,
    *,
    current_sector=None,
    cols: int = 24,
) -> list[str]:
    """Longest-chain panel lines (WO-P2-c). Highlights current sector with ★.

    Accepts a ProfitChain-like object (`.sectors`, `.overall_profit`, …)
    or a library-row dict (`sectors`/`steps`/`demo_profit`/…).
    """
    cols = max(12, int(cols))
    if chain is None:
        return ["(no chain yet)", "explore / mine first"]

    if hasattr(chain, "sectors"):
        sectors = list(chain.sectors or ())
        overall = getattr(chain, "overall_profit", None)
        cr_turn = getattr(chain, "cr_per_turn", None)
        hops = len(getattr(chain, "hops", ()) or ())
        if not hops and sectors:
            hops = max(0, len(sectors) - 1)
    else:
        sectors = list(chain.get("sectors") or ())
        overall = chain.get("demo_profit")
        cr_turn = chain.get("profit_per_turn")
        hops = int(chain.get("steps") or max(0, len(sectors) - 1))

    if not sectors:
        return ["(no chain yet)", "explore / mine first"]

    parts = []
    try:
        cur = int(current_sector) if current_sector is not None else None
    except (TypeError, ValueError):
        cur = None
    for sid in sectors:
        try:
            sid_i = int(sid)
        except (TypeError, ValueError):
            parts.append(str(sid))
            continue
        if cur is not None and sid_i == cur:
            parts.append(f"★{sid_i}")
        else:
            parts.append(str(sid_i))
    path = "→".join(parts)
    lines = [path[:cols], f"{hops} hops"]
    metrics = []
    if overall is not None:
        try:
            metrics.append(f"+{int(overall)}cr")
        except (TypeError, ValueError):
            metrics.append(f"+{overall}cr")
    if cr_turn is not None:
        try:
            metrics.append(f"{float(cr_turn):.0f}/t")
        except (TypeError, ValueError):
            pass
    if metrics:
        lines.append(" ".join(metrics)[:cols])
    if cur is not None and cur in {int(s) for s in sectors}:
        lines.append(f"here ★{cur}"[:cols])
    elif cur is not None:
        lines.append(f"here {cur} (off)"[:cols])
    return lines


def compose_longest_chain_panel(chain, *, current_sector=None, cols: int = 24) -> list[str]:
    """Alias used by the app — same body as format_chain_summary."""
    return format_chain_summary(chain, current_sector=current_sector, cols=cols)


def compose_phase2_side_panel(
    goals_snap,
    chain,
    *,
    current_sector=None,
    width: int = 22,
) -> list[str]:
    """Combine GOALS + CHAIN for the Decisions-band panel (clipped by draw)."""
    lines = ["— GOALS —"]
    lines.extend(compose_primary_goals_lines(goals_snap, width=width))
    lines.append("— CHAIN —")
    lines.extend(
        format_chain_summary(chain, current_sector=current_sector, cols=width)
    )
    return lines


def compose_decisions_placeholder() -> list[str]:
    """Decisions box content until TW-13 coaches land. Fixed copy so the
    titled box proves the region is wired without inventing advice."""
    return [
        "(coach pending)",
        "TW-13 fills this",
    ]


def compose_port_panel(event: dict, bar_full: str = "█", bar_empty: str = "░") -> list[dict]:
    """Port commodity %-bar-meters (Phase 4 motion C4) -- sourced
    straight off the CURRENT event's state, deliberately NOT persisted
    in the tracked accumulator like credits/sector/turns are: a port's
    prices are meaningless once you've undocked, so showing a stale
    port's numbers after leaving would be actively misleading, not just
    outdated (unlike the operator-directive stats, which are genuinely
    persistent facts about the ship/account). Empty list when the
    current screen isn't a port (or has no commodity table)."""
    state = (event or {}).get("state") or {}
    port = state.get("port") or {}
    commodities = port.get("commodities") or []
    rows = []
    for c in commodities:
        pct = c.get("pct", 0)
        status = c.get("status", "")
        rows.append({
            "name": c.get("name", "?"),
            "pct": pct,
            "bar": render_bar_meter(pct / 100.0, PORT_BAR_WIDTH, bar_full, bar_empty),
            "tone": "ok" if status == "buying" else "info",
        })
    return rows


def tick_down_timer(hhmmss: str, elapsed_s: float) -> str:
    """Locally interpolate a HH:MM:SS turn-timer countdown between polls
    (motion A5) -- the watch stream only reports a snapshot at each
    settle-edge; this keeps the displayed countdown ticking down in
    between instead of sitting frozen for up to a full poll interval.
    Floors at 00:00:00 -- never negative, never wraps. Any unparseable
    input is returned unchanged (defensive -- state_parser's shape could
    evolve)."""
    try:
        h, m, s = (int(x) for x in hhmmss.split(":"))
    except (ValueError, AttributeError):
        return hhmmss
    total = max(0, h * 3600 + m * 60 + s - int(elapsed_s))
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def format_idle_age(age_s: float) -> str:
    """Human-scale idle-age readout for the status bar (motion A3):
    seconds while short, minutes+seconds once it's been a while."""
    age_s = max(0.0, age_s)
    if age_s < 60:
        return f"{age_s:.1f}s"
    minutes, seconds = divmod(int(age_s), 60)
    return f"{minutes}m{seconds:02d}s"


_STALE_RX_THRESHOLD_S = 5.0


def status_semantic(connected: bool, last_rx_age_s) -> str:
    """Classify the status bar's overall liveness for semantic coloring
    (visual B2 + motion B8): "danger" (disconnected), "warn" (connected
    but the game hasn't sent anything in a while -- could be a hung
    session, could just be a quiet screen), or "ok"."""
    if not connected:
        return "danger"
    if last_rx_age_s is not None and last_rx_age_s >= _STALE_RX_THRESHOLD_S:
        return "warn"
    return "ok"


_GAUGE_WARN_THRESHOLD = 0.5
_GAUGE_DANGER_THRESHOLD = 0.2


def gauge_semantic(fraction: float) -> str:
    """Classify a depleting gauge's fill fraction into the SAME
    ok/warn/danger vocabulary status_semantic() uses (Phase 4 motion C5:
    the turns-left fuel gauge, green->amber->red as it depletes) -- one
    color table serves both, rather than a second bespoke one."""
    if fraction >= _GAUGE_WARN_THRESHOLD:
        return "ok"
    if fraction >= _GAUGE_DANGER_THRESHOLD:
        return "warn"
    return "danger"


# -- Trainer Control Panel (TUI-POLISH-PLAN.md) -- control strip + Trade
# Loop Chains overlay (TW-07 rename of the Learned-Loops Library). Same
# discipline as everything above: pure text/tuples, no curses --
# spectate_app.py owns the actual drawing + key handling.

# (label, tone) per control-lock mode -- tone is the SAME ok/warn/danger/
# info vocabulary status_semantic()/gauge_semantic() already use, plus
# "muted" for the deliberately-idle SPECTATE state (parked, not a warning).
_MODE_BADGES = {
    "ai_pilot": ("AI-PILOT", "info"),
    "auto_loop": ("AUTO-LOOP", "ok"),
    "human": ("MANUAL — YOU HAVE CONTROL", "warn"),
    "spectate": ("SPECTATE", "muted"),
}

CONTROL_HINTS = "M)ode  L)chains  E)xplore  Spc pause  X stop  P panic"
PLAY_PROGRESS_BAR_WIDTH = 12


def format_mode_badge(mode: str) -> tuple:
    """(label, tone) for the control strip's mode badge -- an unrecognized
    mode string (forward-compat: a future mode this build doesn't know
    the display name for) still renders SOMETHING sane rather than
    crashing or going blank."""
    return _MODE_BADGES.get(mode, (mode.upper() if mode else "?", None))


def format_tx_readout(sent_input) -> str:
    """The live "→ SENT" indicator (Core transparency) -- `sent_input` is
    protocol.build_response()'s own field, already redacted upstream
    (Session.send()) for a --secret send, so this never needs its own
    redaction logic."""
    if not sent_input:
        return "→ -"
    return f"→ {sent_input}"


def format_play_progress_or_hints(play: dict | None) -> str:
    """The control strip's right-hand segment: a live AUTO-LOOP
    cycle-progress bar while a loop is actually running/paused (the operator's
    "watch it learn & replay" payoff), else the keybinding hint legend
    -- never both, there's only room for one at this width. `play` is
    protocol.py status's own shape (running/paused/name/cycle/
    cycles_total/last_result) -- None (no loop_player at all, a bare
    dispatch-harness test) degrades to the hints, same as "not running"."""
    if not play or not play.get("running"):
        return CONTROL_HINTS
    state = "PAUSED" if play.get("paused") else "Playing"
    total = play.get("cycles_total") or 0
    fraction = (play.get("cycle") or 0) / total if total else 0.0
    bar = render_bar_meter(fraction, PLAY_PROGRESS_BAR_WIDTH)
    return f"{state} {play.get('name')} ▸ {play.get('cycle', 0)}/{total} {bar}"


def compose_control_strip(mode: str, sent_input, play: dict | None) -> dict:
    """Everything the control-strip row needs, pre-composed:
    {"badge": text, "badge_tone": tone, "tx": text, "right": text} --
    spectate_app.py lays these out left-to-right, coloring only the
    badge by tone (tx/hints/progress stay the strip's normal attribute)."""
    label, tone = format_mode_badge(mode)
    return {
        "badge": f" {label} ",
        "badge_tone": tone,
        "tx": format_tx_readout(sent_input),
        "right": format_play_progress_or_hints(play),
    }


def chain_overall_profit(loop: dict):
    """Overall profit for ranking/display. Recorded skills carry a summed
    demo-run credits delta; mined skills do not get a fabricated overall
    from rate × hops — return None and show an em-dash."""
    if loop.get("demo_profit") is not None:
        return float(loop["demo_profit"])
    return None


def chain_cr_per_turn(loop: dict):
    v = loop.get("profit_per_turn")
    return float(v) if v is not None else None


def chain_cr_per_execution(loop: dict):
    """One-way chain-execution credits: mined `profit_per_action` when
    present; recorded `demo_profit` (one demo ≈ one traverse)."""
    if loop.get("profit_per_action") is not None:
        return float(loop["profit_per_action"])
    if loop.get("demo_profit") is not None:
        return float(loop["demo_profit"])
    return None


def _chain_sort_key(loop: dict) -> float:
    overall = chain_overall_profit(loop)
    if overall is not None:
        return overall
    cr_turn = chain_cr_per_turn(loop)
    if cr_turn is not None:
        return cr_turn
    return float("-inf")


def sort_trade_loop_chains(loops: list) -> list:
    """Client-side profit-desc sort (TW-07). Does not mutate the input."""
    return sorted(loops or [], key=_chain_sort_key, reverse=True)


def longest_chain_steps(loops: list) -> int:
    """Hop count of the longest chain in `loops` (0 if empty)."""
    if not loops:
        return 0
    return max(int(loop.get("steps") or 0) for loop in loops)


def format_chain_metric(value, kind: str) -> str:
    """Compact three-metric display helpers. `kind` is overall|turn|exec."""
    if value is None:
        return "-"
    if kind == "turn":
        return f"{value:+.1f}/t"
    if isinstance(value, float) and not value.is_integer():
        return f"{value:+.1f}"
    return f"{int(value):+,}"


def format_loops_library_row(
    loop: dict, selected: bool, cols: int, *, longest: bool = False,
) -> str:
    """One row of the Trade Loop Chains overlay (`L`) -- name · source ·
    THREE metrics (overall profit · avg cr/turn · cr/chain-execution) ·
    hop count. `longest` marks the celebrated longest-hop chain (TW-07);
    `selected` only changes the leading marker -- spectate_app.py applies
    the highlight attribute separately."""
    overall = format_chain_metric(chain_overall_profit(loop), "overall")
    cr_turn = format_chain_metric(chain_cr_per_turn(loop), "turn")
    cr_exec = format_chain_metric(chain_cr_per_execution(loop), "exec")
    if longest:
        marker = "★"
    elif selected:
        marker = "▸"
    else:
        marker = " "
    tag = "DRAFT " if loop.get("draft") else ""
    hops = int(loop.get("steps") or 0)
    row = (
        f"{marker} {tag}{loop['name']:<22} {loop.get('source', '?'):<9} "
        f"{overall:>10} {cr_turn:>8} {cr_exec:>10} {hops:>3} hops"
    )
    return row[: max(0, cols - 1)]


def format_loops_library_header(count: int) -> str:
    # TW-07 rename + TW-20 Enter wording (arms, does not fire).
    return (
        f"TRADE LOOP CHAINS — {count} chain(s) — "
        f"↑/↓ select · 1-9 cycles · Enter arms · Esc/L close"
    )


def format_longest_chain_banner(loop: dict, cols: int) -> str:
    """Centerpiece callout for the longest-hop chain (TW-07 §22.2)."""
    hops = int(loop.get("steps") or 0)
    text = f"★ LONGEST CHAIN · {loop.get('name', '?')} · {hops} hops"
    return text[: max(0, cols - 1)]


def render_plain(dashboard: dict) -> str:
    """Flatten a composed dashboard into plain text — the --snapshot /
    non-curses path, and what a Bash transcript actually captures."""
    lines = []
    lines.append("=" * 80)
    lines.append(" MAIN — live screen")
    lines.append("=" * 80)
    lines.extend(dashboard["main"] or ["(no screen yet)"])
    lines.append("-" * 80)
    lines.append(" SIDEBAR — parsed state")
    lines.append("-" * 80)
    lines.extend(dashboard["sidebar"])
    if dashboard.get("metrics"):
        lines.append("-" * 80)
        lines.append(" METRICS")
        lines.append("-" * 80)
        for row in dashboard["metrics"]:
            lines.append(f"{row['label']:<10}{row['value']}")
    if dashboard.get("autonomy"):
        auto = dashboard["autonomy"]
        pct = auto.get("pct_display", "—")
        lines.append("-" * 80)
        lines.append(f" AUTONOMY  {pct}  {format_autonomy_counts(auto)}")
    if dashboard.get("decisions"):
        lines.append("-" * 80)
        lines.append(" DECISIONS — autopilot dry-run")
        lines.append("-" * 80)
        lines.extend(dashboard["decisions"])
    if dashboard.get("goals_chain"):
        lines.append("-" * 80)
        lines.append(" GOALS / CHAIN")
        lines.append("-" * 80)
        lines.extend(dashboard["goals_chain"])
    lines.append("-" * 80)
    lines.append(" EVENTS")
    lines.append("-" * 80)
    lines.extend(dashboard["ticker"] or ["(no events yet)"])
    lines.append("-" * 80)
    lines.append(dashboard["status"])
    return "\n".join(lines)
