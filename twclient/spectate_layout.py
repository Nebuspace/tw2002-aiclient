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


def format_ticker_entry(
    event: dict,
    *,
    answered_prompt=None,
    answered_classification=None,
) -> str:
    """One LOG/ticker row.

    ``sent_input`` is the keystroke that *caused* this settle, but the
    event's own ``prompt`` / ``classification`` are the *landing* after
    that send. Pairing ``→sent`` with the landing prompt/class skews
    one-off in the LOG (WO-TUI-LOG-QA-SKEW / WO-TUI-LOG-QA-LABELS).

    When ``answered_prompt`` (and ideally ``answered_classification``)
    are supplied from the prior event — the question that was on screen
    when the send happened — the left class tag and the ``— prompt``
    both describe the prompt that *received* the answer. Landing is
    only an optional ``⇒ …`` suffix when it differs.
    """
    ts = event.get("ts", "")
    landing_cls = event.get("classification", "unknown")
    reason = event.get("settled_reason", "-")
    landing = (event.get("prompt") or "").strip()[:40]
    sent = event.get("sent_input")

    if sent and answered_prompt is not None:
        answered = (answered_prompt or "").strip()[:40]
        cls = answered_classification or "unknown"
        line = f"[{ts}] {cls} ({reason}) — {answered}  →{sent}"
        if landing and landing != answered:
            line = f"{line} ⇒ {landing}"
        return line

    if sent and answered_prompt is None:
        # Orphan TX (no prior event): never pretend the landing prompt
        # was what we answered — show send + landing without a false pair.
        line = f"[{ts}] ({reason})  →{sent}"
        if landing:
            line = f"{line} ⇒ {landing}"
        return line

    return f"[{ts}] {landing_cls} ({reason}) — {landing}"


def format_ticker_history(events) -> list:
    """Format LOG rows with sent_input paired to the prior prompt+class."""
    out = []
    prev = None
    for event in events or ():
        answered = answered_cls = None
        if event.get("sent_input") and prev is not None:
            answered = prev.get("prompt")
            answered_cls = prev.get("classification")
        out.append(
            format_ticker_entry(
                event,
                answered_prompt=answered,
                answered_classification=answered_cls,
            )
        )
        prev = event
    return out


def format_status_line(connected=False, subscriber_count=0, last_rx_age_s=None, daemon_pid=None, **_extra) -> str:
    # **_extra absorbs forward-compatible fields on the status dict (e.g.
    # spectate_app.fetch_status()'s "host"/"name"/"world_id") — WO-HUD-HOST-
    # VISIBLE surfaces host (and world_id when known) so a wrong-daemon
    # sock is obvious in --snapshot and plain status chrome, not only the
    # interactive header.
    conn = "CONNECTED" if connected else "DISCONNECTED"
    age = f"{last_rx_age_s:.1f}s ago" if last_rx_age_s is not None else "-"
    pid = daemon_pid if daemon_pid is not None else "-"
    host = _extra.get("host") or "-"
    wid = (_extra.get("world_id") or "").strip()
    identity = f"host: {host}" + (f" | world: {wid}" if wid else "")
    return f"{conn} | {identity} | subscribers: {subscriber_count} | last-rx: {age} | daemon pid: {pid}"


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
        "ticker": format_ticker_history(ticker_history[-TICKER_MAX:]),
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

# WO-TUI-HUD-POLISH: wide enough for CREDITS value + freshness (+ spark)
# on one line without wrap/truncate at full/right_gutter tiers.
HUD_GUTTER_W = 36  # exactly VIEWPORT_W + HUD_GUTTER_W = 118, the right_gutter floor below
# WO-TUI-PRIORITIES-LEFT: tall left gutter mirroring HUD width (not bottom-band).
# Full tier matches HUD_GUTTER_W; narrow fold keeps PRIORITIES_MIN_W.
PRIORITIES_W = HUD_GUTTER_W
PRIORITIES_MIN_W = 20
MINIMAL_HEADER_MIN_COLS = 82   # == VIEWPORT_W: the floor at which a bordered viewport fits at all
RIGHT_GUTTER_MIN_COLS = 118    # == VIEWPORT_W + HUD_GUTTER_W: viewport + right HUD, zero-margin fit
# full = viewport + both side gutters (PRIORITIES left + HUD right), zero-margin fit
FULL_GUTTER_MIN_COLS = VIEWPORT_W + HUD_GUTTER_W + PRIORITIES_W  # 154
# left PRIORITIES appears once both side gutters + viewport fit (may shrink pri_w)
LEFT_GUTTER_MIN_COLS = VIEWPORT_W + HUD_GUTTER_W + PRIORITIES_MIN_W  # 138
MIN_COLS = 60
MIN_LINES = 20
# TW-08: one-cell outer frame around the whole client. Layout math uses
# the INNER content size (cols/lines minus 2); thresholds above remain
# content floors — callers measuring a REAL terminal must add +2.
OUTER_FRAME_PAD = 1  # per side
# Titled LOG box needs ≥3 rows (border + 1 content + border).
LOG_BOX_MIN_H = 3
# WO-TUI-CHAIN-BUBBLES: ASCII bubble-chain sits directly under the
# viewport (not a bottom-band CHAIN column). 4 box rows + ★ marker row.
CHAIN_VIZ_H = 5
# DECISIONS/GOALS needs more room than LOG's bare floor before splitting
# off is worth it -- AUTO/App-AI-Hum + GOALS reads as collapsed-to-nothing
# at a squeezed 1-2-content-row band. `band_h` is capped at 10 (~2× the
# old cap of 5); this floor is the minimum leftover before DECISIONS
# splits from LOG — below it, LOG claims the whole leftover band
# (one legible pane beats two illegible ones).
DECISIONS_MIN_H = 5
BAND_H_MAX = 10
# WO-TUI-DECISIONS-HUD-ALIGN: when a right HUD gutter exists, DECISIONS
# shares that column (HUD width, bottom aligned with the column base).
# Prefer HUD: DECISIONS stays at DECISIONS_MIN_H so ship cells + METRICS
# still fit (HUD_GUTTER_MIN_H=10 clipped METRICS — human 2026-07-22).
HUD_GUTTER_MIN_H = VIEWPORT_H - DECISIONS_MIN_H  # 21


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
      >=142  "full"          -- PRIORITIES | centered game | HUD (both side gutters)
      >=118  "right_gutter"  -- bordered viewport (left-anchored) + right HUD;
                               left PRIORITIES when cols >= LEFT_GUTTER_MIN_COLS (138)
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

    When leftover height allows, a bubble-chain region sits directly under
    the viewport (WO-TUI-CHAIN-BUBBLES), centered on the game window; the
    remaining leftover band below splits into titled LOG + DECISIONS when
    width allows (no right HUD gutter). With a right HUD gutter,
    DECISIONS shares that column at HUD width with its bottom aligned to
    the column base (WO-TUI-DECISIONS-HUD-ALIGN). PRIORITIES is a tall
    left gutter (WO-TUI-PRIORITIES-LEFT), not a bottom-band column. The
    bottom log ("ticker") is always a titled "LOG" box when present.
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
            "priorities": None,
            "chain": None,
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
    has_right_gutter = i_cols >= RIGHT_GUTTER_MIN_COLS

    control = None
    if leftover >= 1:
        control = {"y": status["y"] - 1, "x": ox, "w": i_cols, "h": 1}
        leftover -= 1

    # Prefer bubble-chain under the viewport when both chain + a LOG
    # band fit; otherwise keep LOG|DECISIONS and skip chain (never clip
    # the game grid). Steal from the leftover band first.
    chain = None
    want_chain = leftover >= CHAIN_VIZ_H + LOG_BOX_MIN_H
    if want_chain:
        leftover -= CHAIN_VIZ_H

    ticker = None
    decisions = None
    # TW-08: leftover band hosts titled LOG; when tall/wide enough, split
    # side-by-side with DECISIONS. Side gutters (PRIORITIES left / HUD right)
    # stay full viewport height. PRIORITIES is never folded into GOALS and
    # never preempted by the DECISIONS slot rotation.
    if leftover >= LOG_BOX_MIN_H:
        band_h = min(BAND_H_MAX, leftover)
        band_y = status["y"] - (1 if control else 0) - band_h
        if (
            not has_right_gutter
            and i_cols >= 60
            and leftover >= DECISIONS_MIN_H
        ):
            # Wider DECISIONS (~2× old content rows via BAND_H_MAX); keep LOG
            # wide enough that settle/TX suffixes remain readable. When a
            # right HUD gutter exists, DECISIONS moves into that column instead
            # (WO-TUI-DECISIONS-HUD-ALIGN).
            dec_w = min(32, max(20, i_cols // 4))
            log_floor = 36
            if i_cols - dec_w < log_floor:
                dec_w = max(20, min(dec_w, i_cols - log_floor))
            log_w = i_cols - dec_w
            ticker = {
                "y": band_y, "x": ox, "w": log_w, "h": band_h,
                "title": "LOG", "border": True,
            }
            decisions = {
                "y": band_y, "x": ox + log_w, "w": dec_w, "h": band_h,
                "title": "DECISIONS", "border": True,
            }
        else:
            ticker = {
                "y": band_y, "x": ox, "w": i_cols, "h": band_h,
                "title": "LOG", "border": True,
            }

    # Side gutters: PRIORITIES (left) | game | HUD (right). Never crush
    # the native viewport — left PRIORITIES only when both gutters fit.
    priorities = None
    pri_w = 0
    if i_cols >= FULL_GUTTER_MIN_COLS:
        mode = "full"
        pri_w = PRIORITIES_W
        gutter = {"y": body_top, "x": ox + i_cols - HUD_GUTTER_W, "w": HUD_GUTTER_W, "h": viewport_h}
        middle = i_cols - pri_w - HUD_GUTTER_W
        viewport_x = ox + pri_w + max(0, (middle - viewport_w) // 2)
    elif i_cols >= LEFT_GUTTER_MIN_COLS:
        mode = "right_gutter"
        pri_w = PRIORITIES_MIN_W
        gutter = {"y": body_top, "x": ox + i_cols - HUD_GUTTER_W, "w": HUD_GUTTER_W, "h": viewport_h}
        viewport_x = ox + pri_w  # left-anchored after PRIORITIES
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

    if pri_w > 0:
        priorities = {
            "y": body_top, "x": ox, "w": pri_w, "h": viewport_h,
            "title": "PRIORITIES", "border": True,
        }

    if gutter is not None:
        dec_h = max(DECISIONS_MIN_H, viewport_h - HUD_GUTTER_MIN_H)
        gutter["h"] = viewport_h - dec_h
        decisions = {
            "y": body_top + gutter["h"],
            "x": gutter["x"],
            "w": HUD_GUTTER_W,
            "h": dec_h,
            "title": "DECISIONS",
            "border": True,
        }

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

    if want_chain:
        # Centered on the game window (viewport), directly beneath it.
        chain = {
            "y": body_top + viewport_h,
            "x": viewport_x,
            "w": viewport_w,
            "h": CHAIN_VIZ_H,
            "title": None,
            "border": False,
        }

    return {
        "mode": mode,
        "message": None,
        "outer": outer,
        "header": header,
        "viewport": viewport,
        "gutter": gutter,
        "decisions": decisions,
        "priorities": priorities,
        "chain": chain,
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

    if "fighters_aboard" in state:
        out["fighters"] = (state["fighters_aboard"], now)

    if "turns_left" in state:
        new_turns = state["turns_left"]
        prev_max = out.get("_turns_max")
        out["_turns_max"] = new_turns if prev_max is None else max(prev_max, new_turns)
        out["turns"] = (("count", new_turns), now)
    # turn_timer (TL=HH:MM:SS regen countdown) must NEVER fill the TURNS
    # HUD slot — that slot is turn COUNT only (sticky last-known). Showing
    # the timer there read as turns=00:00:00 (WO-TUI-HUD-TURNS-COUNT).

    # Prefer FA7a top-level strict balance (session.credits_snapshot /
    # "you have N credits") over parse_state's looser state["credits"],
    # which a port price quote satisfies just as well. When FA7a is
    # present, use credits_age_ms so freshness tracks the daemon's
    # last real observe — not every settle-edge rebroadcast.
    fa7a_credits = event.get("credits")
    if fa7a_credits is not None:
        age_ms = event.get("credits_age_ms")
        seen_ts = now - (age_ms / 1000.0) if isinstance(age_ms, (int, float)) else now
        new_credits = fa7a_credits
        prev_entry = tracked.get("credits")
        baseline = out.get("_credits_baseline")
        if baseline is None:
            out["_credits_baseline"] = (new_credits, seen_ts)
        else:
            out["profit"] = (new_credits - baseline[0], seen_ts)
        if prev_entry is not None and prev_entry[0] != new_credits:
            out["_credits_flash"] = (new_credits - prev_entry[0], now)
            out["_credits_tween"] = (prev_entry[0], new_credits, now)
        if prev_entry is None or prev_entry[0] != new_credits:
            series = list(out.get("_credit_series") or [])
            series.append(new_credits)
            out["_credit_series"] = series[-CREDIT_SPARK_WIDTH:]
        out["credits"] = (new_credits, seen_ts)
        out["_credits_from_fa7a"] = True
    elif "credits" in state and not out.get("_credits_from_fa7a"):
        # Cold / pre-FA7a path (tests + never-docked): allow state credits.
        # Once FA7a has supplied a balance, ignore loose state credits so
        # a port quote cannot replace the HUD.
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


def seed_tracked_from_status(tracked: dict, status: dict, now: float, *, parsed_state: dict | None = None) -> dict:
    """Backfill the HUD accumulator from daemon session truth on spectate
    connect (and on each status poll for FA7a credits freshness).

    `fetch_status()` already serves FA7a `credits`/`credits_age_ms`; watch
    events from subscribe do NOT carry those top-level fields — only
    `update_tracked_stats()` on the event stream left cold-start HUD cells
    blank until a credits-bearing settle edge. This synthesizes the same
    FA7a-shaped event `update_tracked_stats()` already understands.

    Non-credit HUD fields (`sector`, `turns`, `cargo_holds_empty`) are filled
    ONLY while still absent this spectate session — from optional
    `parsed_state` (a one-shot `state` verb on connect) merged with any
    `status["state"]` the daemon may serve later. Never clobbers values
    events have already established."""
    if not status:
        return dict(tracked)
    synthetic: dict = {}
    credits = status.get("credits")
    if credits is not None:
        synthetic["credits"] = credits
        age_ms = status.get("credits_age_ms")
        if age_ms is not None:
            synthetic["credits_age_ms"] = age_ms

    merged = dict(parsed_state or {})
    merged.update(status.get("state") or {})
    state: dict = {}
    if "sector" not in tracked and "sector" in merged:
        state["sector"] = merged["sector"]
    if "turns" not in tracked:
        # Prefer sticky status turns_left (session.observe_turns) over a
        # one-shot parsed_state that may be a fighter-toll screen with none.
        if status.get("turns_left") is not None:
            state["turns_left"] = status["turns_left"]
        elif "turns_left" in merged:
            state["turns_left"] = merged["turns_left"]
        # Never seed TURNS from turn_timer (TL=HH:MM:SS ≠ turn count).
    if "cargo_holds_empty" not in tracked and "cargo_holds_empty" in merged:
        state["cargo_holds_empty"] = merged["cargo_holds_empty"]
    if "fighters" not in tracked and status.get("fighters_aboard") is not None:
        state["fighters_aboard"] = status["fighters_aboard"]
    if state:
        synthetic["state"] = state
    if not synthetic:
        return dict(tracked)
    return update_tracked_stats(tracked, synthetic, now)


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
    # Legacy timer entries (pre-WO-TUI-HUD-TURNS-COUNT) → blank, not HH:MM:SS.
    if kind != "count":
        return {"label": "TURNS", "value": "-", "freshness": "", "stale": False, "tone": None, "chip": "", "gauge": ""}
    age = max(0.0, now - ts)
    tone, gauge = None, ""
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
# Fixed display order the operator named: Sectors mapped / Stations / Planets /
# Fighters / Mines / Problem-sectors. Always emit a full shape so the HUD never jumps.
_LIVE_METRIC_SPECS = (
    ("sectors_mapped", "SECTORS"),
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
    sectors_mapped = len(sectors or ())
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
        "sectors_mapped": sectors_mapped,
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
    """Metric terms: App = trainer, AI = llm-pilot; Hum = human attach (ratio-excluded)."""
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

# --snapshot / unit-test demo fixture (render proof surface). Live TUI trusts
# status["autopilot_trace"] only — null → GOALS/"—", never this mock.
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


# -- WO-TUI-PRIORITIES: ordered weigh list (dedicated PRIORITIES box)

# Readable labels for autopilot candidate kinds — never dump raw enums alone.
PRIORITY_KIND_LABELS = {
    "run_chain": "Trade chain",
    "upgrade": "Upgrade",
    "explore": "Explore",
}


def priority_kind_label(kind) -> str:
    """Human label for a planner/autopilot effort kind."""
    if not kind or not isinstance(kind, str):
        return "?"
    return PRIORITY_KIND_LABELS.get(kind, kind.replace("_", " ").title())


def _priority_ev_sort_key(candidate) -> tuple:
    """Legacy trace-only weigh order: highest known EV first; unknown EV last."""
    ev = _trace_field(candidate, "ev_cr_per_turn")
    try:
        ev_f = float(ev) if ev is not None else None
    except (TypeError, ValueError):
        ev_f = None
    if ev_f is None or ev_f != ev_f:  # None or NaN
        return (1, 0.0)
    return (0, -ev_f)


def _chain_start_sector(chain) -> int | None:
    """Normalized cycle start for return-path math."""
    if chain is None:
        return None
    sectors = list(getattr(chain, "sectors", None) or ())
    if not sectors and isinstance(chain, dict):
        sectors = list(chain.get("sectors") or ())
    if not sectors:
        return None
    try:
        return int(sectors[0])
    except (TypeError, ValueError):
        return None


def _chain_engine_metrics(chain, *, current_sector=None):
    """(cr_per_turn, cycle_turns, at_chain_start, link_count) from a chain-like value."""
    if chain is None:
        return None, None, False, None
    chain_cr = None
    chain_cycle = None
    link_count = None
    if hasattr(chain, "cr_per_turn"):
        try:
            chain_cr = float(chain.cr_per_turn) if chain.cr_per_turn is not None else None
        except (TypeError, ValueError):
            chain_cr = None
        chain_cycle = getattr(chain, "turns", None)
        hops = getattr(chain, "hops", None)
        if hops is not None:
            try:
                link_count = len(hops)
            except TypeError:
                link_count = None
        elif getattr(chain, "sectors", None) is not None:
            try:
                secs = chain.sectors
                link_count = max(0, len(secs) - 1)
            except TypeError:
                link_count = None
    elif isinstance(chain, dict):
        ppt = chain.get("profit_per_turn")
        if ppt is not None:
            try:
                chain_cr = float(ppt)
            except (TypeError, ValueError):
                chain_cr = None
        chain_cycle = chain.get("turns")
        if chain.get("steps") is not None:
            try:
                link_count = int(chain["steps"])
            except (TypeError, ValueError):
                link_count = None
        elif chain.get("sectors") is not None:
            try:
                link_count = max(0, len(chain["sectors"]) - 1)
            except TypeError:
                link_count = None
    start = _chain_start_sector(chain)
    at_start = False
    if start is not None and current_sector is not None:
        try:
            at_start = int(current_sector) == start
        except (TypeError, ValueError):
            at_start = False
    return chain_cr, chain_cycle, at_start, link_count


def _has_priority_inputs(trace, chain) -> bool:
    """True when trace or chain can feed the priority engine."""
    if chain is not None:
        return True
    if trace is None:
        return False
    if isinstance(trace, dict) and not trace:
        return False
    if not isinstance(trace, dict) and not hasattr(trace, "candidates"):
        return False
    candidates = _trace_field(trace, "candidates")
    if isinstance(candidates, (list, tuple)) and candidates:
        return True
    ctx = _trace_field(trace, "context") or {}
    return bool(ctx)


def _trace_candidate(trace, kind: str):
    """First autopilot_trace candidate entry for ``kind``."""
    if not trace:
        return None
    for c in _trace_field(trace, "candidates") or ():
        if _trace_field(c, "kind") == kind:
            return c
    return None


def build_priority_engine_inputs(
    trace,
    chain=None,
    *,
    current_sector=None,
    stardock_route=None,
    graph=None,
    turn_reserve: int = 0,
    turns_per_warp: int = 1,
    explore_available=None,
) -> dict:
    """Adapter: spectate-visible data → ``recommend_actions()`` kwargs.

    Pulls turns/sector from trace context, chain economics from the panel
    chain object (fallback: ungated trace EV), and optional world-model
    travel legs (StarDock route + return-to-chain-start).
    """
    from .priority_engine import compute_return_path, hops_of_path

    ctx = (_trace_field(trace, "context") or {}) if trace else {}
    turns_left = ctx.get("turns_left")
    if turns_left is not None:
        try:
            turns_left = int(turns_left)
        except (TypeError, ValueError):
            turns_left = None

    sector = current_sector
    if sector is None and ctx.get("sector") is not None:
        try:
            sector = int(ctx["sector"])
        except (TypeError, ValueError):
            sector = None

    chain_cr, chain_cycle, at_start, link_count = _chain_engine_metrics(
        chain, current_sector=sector
    )
    if chain_cr is None:
        run_c = _trace_candidate(trace, "run_chain")
        if run_c is not None and not bool(_trace_field(run_c, "gated")):
            ev = _trace_field(run_c, "ev_cr_per_turn")
            if ev is not None:
                try:
                    chain_cr = float(ev)
                except (TypeError, ValueError):
                    pass
            if link_count is None:
                steps = _trace_field(run_c, "steps")
                ch = _trace_field(run_c, "chain")
                if steps is None and isinstance(ch, dict):
                    steps = ch.get("steps")
                if steps is not None:
                    try:
                        link_count = int(steps)
                    except (TypeError, ValueError):
                        pass

    upgrade_ev = None
    upgrade_payback = None
    upgrade_name = None
    up_c = _trace_candidate(trace, "upgrade")
    if up_c is not None:
        ev = _trace_field(up_c, "ev_cr_per_turn")
        if ev is not None and not bool(_trace_field(up_c, "gated")):
            try:
                upgrade_ev = float(ev)
            except (TypeError, ValueError):
                pass

    hops_to_stardock = hops_of_path(stardock_route) if stardock_route is not None else None

    hops_return = None
    chain_start = _chain_start_sector(chain)
    if graph and stardock_route and chain_start is not None and len(stardock_route) >= 1:
        dock_sector = stardock_route[-1]
        ret_path = compute_return_path(graph, dock_sector, chain_start)
        hops_return = hops_of_path(ret_path)

    if explore_available is None:
        explore_available = False
        ex_c = _trace_candidate(trace, "explore")
        if ex_c is not None:
            explore_available = not bool(_trace_field(ex_c, "gated"))

    return {
        "chain_cr_per_turn": chain_cr,
        "chain_cycle_turns": chain_cycle,
        "chain_link_count": link_count,
        "at_chain_start": at_start,
        "upgrade_extra_cr_per_turn": upgrade_ev,
        "upgrade_payback": upgrade_payback,
        "upgrade_ship_name": upgrade_name,
        "hops_to_stardock": hops_to_stardock,
        "hops_return_to_work": hops_return,
        "turns_per_warp": turns_per_warp,
        "turns_left": turns_left,
        "turn_reserve": turn_reserve,
        "explore_available": explore_available,
    }


def recommend_priority_actions(trace, chain=None, **engine_kwargs):
    """Run ``priority_engine.recommend_actions`` on spectate adapter inputs."""
    from .priority_engine import recommend_actions

    inputs = build_priority_engine_inputs(trace, chain, **engine_kwargs)
    return recommend_actions(**inputs)


def _compose_priorities_from_engine(rec, *, width: int) -> list[str]:
    """Render engine-ranked ``PriorityScore`` rows for the weigh list."""
    width = max(8, int(width))
    lines = []
    for i, score in enumerate(rec.ranked, start=1):
        label = priority_kind_label(score.kind)
        mark = "⊘ " if score.gated else ""
        ev_s = format_trace_ev(score.ev_per_turn)
        rt_hint = ""
        if score.travel_cost_rt is not None and width >= 24:
            rt_hint = f" RT{score.travel_cost_rt}t"
        body = f"{i} {mark}{label} {ev_s}{rt_hint}"
        lines.append(body[:width])
    return lines or ["—"]


def compose_priorities_lines(
    trace,
    *,
    width: int = 22,
    chain=None,
    priority_rec=None,
    **engine_kwargs,
) -> list[str]:
    """Ordered effort list (1…N) from the priority engine.

    Uses ``recommend_actions()`` (RT travel + stay-vs-leave) when trace or
    chain inputs exist; falls back to legacy trace-only EV sort only when
    the engine cannot run. Gated rows carry ``⊘``; upgrade rows may show
    ``RTNt`` when width allows.
    """
    width = max(8, int(width))
    if trace is None and chain is None and priority_rec is None:
        return ["—"]

    if priority_rec is None and _has_priority_inputs(trace, chain):
        priority_rec = recommend_priority_actions(trace, chain, **engine_kwargs)

    if priority_rec is not None and priority_rec.ranked:
        return _compose_priorities_from_engine(priority_rec, width=width)

    # Legacy trace-only fallback (malformed trace with no chain context).
    if trace is None:
        return ["—"]
    if isinstance(trace, dict) and not trace:
        return ["—"]
    if not isinstance(trace, dict) and not hasattr(trace, "candidates"):
        return ["—"]

    candidates = _trace_field(trace, "candidates") or ()
    if not isinstance(candidates, (list, tuple)) or not candidates:
        return ["—"]

    ranked = sorted(candidates, key=_priority_ev_sort_key)
    lines = []
    for i, c in enumerate(ranked, start=1):
        kind = _trace_field(c, "kind")
        label = priority_kind_label(kind)
        gated = bool(_trace_field(c, "gated"))
        ev_s = format_trace_ev(_trace_field(c, "ev_cr_per_turn"))
        mark = "⊘ " if gated else ""
        body = f"{i} {mark}{label} {ev_s}"
        lines.append(body[:width])
    return lines or ["—"]


def compose_priorities_panel(
    goals_snap,
    chain,
    trace,
    *,
    autonomy_lines=None,
    current_sector=None,
    width: int = 22,
    include_chain: bool = True,
    **priority_engine_kwargs,
) -> list[str]:
    """Left-gutter PRIORITIES box: autonomy + GOALS (+ optional CHAIN) + FOCUS list.

    The outer TUI region stays titled PRIORITIES; inside, GOALS (strategic
    prerequisites) and FOCUS (this-tick action ranking) are separate sections.
    DECISIONS owns trace/explore only; this panel always shows strategy context
    beside the game viewport (WO-TUI-PRIORITIES-LEFT / human 2026-07-22).
    FOCUS order comes from ``priority_engine.recommend_actions()`` when
    trace/chain/travel hints are available (``priority_engine_kwargs``).
    """
    lines = list(autonomy_lines or [])
    lines.extend(
        compose_phase2_side_panel(
            goals_snap,
            chain,
            current_sector=current_sector,
            width=width,
            include_chain=include_chain,
        )
    )
    if lines and lines[-1]:
        lines.append("")
    focus_hdr = "— FOCUS —" if width >= 18 else "— NOW —"
    lines.append(focus_hdr)
    lines.extend(
        compose_priorities_lines(
            trace,
            width=width,
            chain=chain,
            **priority_engine_kwargs,
        )
    )
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


def _chain_unit_for_source(source) -> str:
    """'hops' for a genuine discovered trade-loop chain (a real sector
    path -- chains.chain_as_library_row()'s "discovered" tag) and for
    presence-seed port paths; 'steps' for recorded/mined skill macros.
    Both share the SAME "steps" wire field (protocol.py's list_skills /
    chains.chain_as_library_row) -- this is the one place that decides
    which word it actually means, so display text never conflates a
    learned macro's step count with a trade-loop's hop count (WO-FA5a)."""
    return "hops" if source in ("discovered", "presence_seed") else "steps"


def _hop_count_from_sectors(sectors) -> int | None:
    """Edge count along a sector path (closed cycle keeps the return hop)."""
    try:
        secs = [int(s) for s in (sectors or ())]
    except (TypeError, ValueError):
        return None
    if len(secs) < 2:
        return None
    # Closed cycle (a…a): edges == len(path) - 1. Open path: same formula.
    return len(secs) - 1


def chain_hop_count_and_unit(chain):
    """(count, unit) for a chain-like value headed for the GOALS panel --
    `chain` is either a genuine ProfitChain-like object (real `.hops`),
    a "discovered" library-row dict (also real hops, just re-shaped by
    chain_as_library_row), a presence-seed port path (``sectors``, no
    commodities yet), or a recorded/mined skill's library-row dict
    (macro STEPS, not hops -- see _chain_unit_for_source). `count` is
    None when there's nothing to show; `unit` falls back to "hops" when
    there's no dict to read a `source` off (an object chain, or none).

    Presence seeds omit ``steps`` but still render in the Trade Loop
    panel — derive hop count from ``sectors`` so GOALS never says
    "none yet" while bubbles show a path.
    """
    if chain is None:
        return None, "hops"
    if hasattr(chain, "hops") and chain.hops is not None:
        try:
            return len(chain.hops), "hops"
        except TypeError:
            pass
    if isinstance(chain, dict):
        unit = _chain_unit_for_source(chain.get("source"))
        if chain.get("steps") is not None:
            try:
                count = int(chain["steps"]) or None
            except (TypeError, ValueError):
                count = None
            if count is not None:
                return count, unit
        count = _hop_count_from_sectors(chain.get("sectors"))
        return count, unit if count is not None else "hops"
    if hasattr(chain, "sectors"):
        return _hop_count_from_sectors(getattr(chain, "sectors", None)), "hops"
    return None, "hops"

class GoalsSnapshot:
    """Frozen-enough goals view for compose_primary_goals_lines (plain dict OK too)."""

    __slots__ = (
        "turns_known", "turns_count", "credits_known", "credits_amount",
        "stardock_found", "stardock_sectors", "known_sectors", "galaxy_size",
        "formations",
        "genesis_candidates", "longest_chain_hops", "longest_chain_unit",
        "ship_prices_count", "upgrade_status", "holds_status",
        "fighters_known", "fighters_count",
    )

    def __init__(
        self,
        *,
        turns_known: bool = False,
        turns_count=None,
        credits_known: bool = False,
        credits_amount=None,
        stardock_found: bool = False,
        stardock_sectors=(),
        known_sectors: int = 0,
        galaxy_size=None,
        formations: int = 0,
        genesis_candidates: int = 0,
        longest_chain_hops=None,
        longest_chain_unit: str = "hops",
        ship_prices_count: int = 0,
        upgrade_status: str = "—",
        holds_status: str = "—",
        fighters_known: bool = False,
        fighters_count=None,
    ):
        self.turns_known = bool(turns_known)
        self.turns_count = turns_count
        self.credits_known = bool(credits_known)
        self.credits_amount = credits_amount
        self.stardock_found = bool(stardock_found)
        self.stardock_sectors = tuple(stardock_sectors or ())
        self.known_sectors = int(known_sectors)
        self.galaxy_size = int(galaxy_size) if galaxy_size else None
        self.formations = int(formations)
        self.genesis_candidates = int(genesis_candidates)
        self.longest_chain_hops = longest_chain_hops
        self.longest_chain_unit = longest_chain_unit or "hops"
        self.ship_prices_count = int(ship_prices_count)
        self.upgrade_status = upgrade_status or "—"
        self.holds_status = holds_status or "—"
        self.fighters_known = bool(fighters_known)
        self.fighters_count = fighters_count


def _goal_row(*, glyph: str, label: str, detail: str, width: int) -> str:
    """One GOALS line: status glyph + readable label + detail."""
    text = f"{glyph} {label} {detail}".strip()
    return text[:width]


def _goals_use_short_labels(width: int) -> bool:
    return width < 26


def compose_primary_goals_lines(snap, *, width: int = 22) -> list[str]:
    """Primary-goals panel lines (WO-P2-b).

    Readable strategic prerequisites — not action ranking. Glyphs: ✓ met/known,
    · in progress / partial, ? unknown, ⊘ blocked (prerequisite unmet).
    """
    width = max(12, int(width))
    if not isinstance(snap, GoalsSnapshot):
        snap = GoalsSnapshot(**(snap or {}))
    short = _goals_use_short_labels(width)
    lines: list[str] = []

    if snap.turns_known and snap.turns_count is not None:
        turns_detail = f"{int(snap.turns_count):,}"
        turns_glyph = "✓"
    else:
        turns_detail = "unknown"
        turns_glyph = "?"
    lines.append(_goal_row(
        glyph=turns_glyph,
        label="Turns" if not short else "Trn",
        detail=turns_detail,
        width=width,
    ))

    if snap.credits_known and snap.credits_amount is not None:
        credits_detail = f"{int(snap.credits_amount):,}"
        credits_glyph = "✓"
    else:
        credits_detail = "unknown"
        credits_glyph = "?"
    lines.append(_goal_row(
        glyph=credits_glyph,
        label="Credits" if not short else "Cr",
        detail=credits_detail,
        width=width,
    ))

    if snap.stardock_found and snap.stardock_sectors:
        dock_detail = f"@{','.join(str(s) for s in snap.stardock_sectors[:3])}"
        dock_glyph = "✓"
    elif snap.stardock_found:
        dock_detail = "found"
        dock_glyph = "✓"
    else:
        dock_detail = "not found"
        dock_glyph = "·"
    lines.append(_goal_row(
        glyph=dock_glyph,
        label="StarDock" if not short else "Dock",
        detail=dock_detail,
        width=width,
    ))

    # Known sector count is exploration progress (galaxy size often unknown).
    if snap.galaxy_size and snap.galaxy_size > 0:
        pct = min(100, int(100 * snap.known_sectors / snap.galaxy_size))
        map_detail = (
            f"{snap.known_sectors}/{snap.galaxy_size} ({pct}%)"
            if not short
            else f"{snap.known_sectors}/{snap.galaxy_size}"
        )
        map_glyph = "✓" if snap.known_sectors >= snap.galaxy_size else "·"
    else:
        map_detail = (
            f"{snap.known_sectors}"
            if short
            else f"{snap.known_sectors} Sectors"
        )
        map_glyph = "·"
    lines.append(_goal_row(
        glyph=map_glyph,
        label="Galaxy Exploration:" if not short else "Gal Exp:",
        detail=map_detail,
        width=width,
    ))

    form_label = "Formations" if not short else "Form"
    form_detail = f"{snap.formations} found"
    lines.append(_goal_row(
        glyph="·" if snap.formations else "?",
        label=form_label,
        detail=form_detail,
        width=width,
    ))

    if snap.genesis_candidates:
        gen_label = "Genesis" if not short else "Gen"
        gen_detail = (
            f"{snap.genesis_candidates} cand"
            if short
            else f"{snap.genesis_candidates} candidates"
        )
        lines.append(_goal_row(
            glyph="·", label=gen_label, detail=gen_detail, width=width,
        ))

    unit = snap.longest_chain_unit or "hops"
    if snap.longest_chain_hops:
        chain_glyph = "✓"
        chain_detail = (
            f"{snap.longest_chain_hops} {unit[:1]}"
            if short
            else f"{snap.longest_chain_hops} {unit}"
        )
    else:
        chain_glyph = "·"
        chain_detail = "none yet"
    lines.append(_goal_row(
        glyph=chain_glyph,
        label="Chain" if not short else "Chain",
        detail=chain_detail,
        width=width,
    ))

    ships_label = "Ship prices" if not short else "Ships"
    if not snap.stardock_found:
        ships_glyph = "⊘"
        ships_detail = "need StarDock" if not short else "need dock"
    elif snap.ship_prices_count > 0:
        ships_glyph = "✓"
        ships_detail = (
            f"{snap.ship_prices_count} priced"
            if not short
            else f"{snap.ship_prices_count} ok"
        )
    else:
        ships_glyph = "·"
        ships_detail = "price?"
    lines.append(_goal_row(
        glyph=ships_glyph, label=ships_label, detail=ships_detail, width=width,
    ))

    hold_label = "Hold upg" if not short else "Hold"
    hold_quote = snap.upgrade_status
    if not snap.stardock_found:
        hold_glyph = "⊘"
        hold_detail = "need StarDock" if not short else "need dock"
    elif hold_quote and hold_quote not in ("—", "price?"):
        hold_glyph = "✓"
        hold_detail = hold_quote
    else:
        hold_glyph = "·"
        hold_detail = "price?"
    lines.append(_goal_row(
        glyph=hold_glyph, label=hold_label, detail=hold_detail, width=width,
    ))

    ftr_label = "Fighters" if not short else "Ftr"
    if snap.fighters_known and snap.fighters_count is not None:
        n = int(snap.fighters_count)
        if n > 0:
            ftr_glyph = "✓"
            ftr_detail = str(n)
        else:
            ftr_glyph = "·"
            ftr_detail = "0 (need some)"
    else:
        ftr_glyph = "?"
        ftr_detail = "unknown"
    lines.append(_goal_row(
        glyph=ftr_glyph, label=ftr_label, detail=ftr_detail, width=width,
    ))

    return lines


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
        unit = "hops"
    else:
        sectors = list(chain.get("sectors") or ())
        overall = chain.get("demo_profit")
        cr_turn = chain.get("profit_per_turn")
        hops = int(chain.get("steps") or max(0, len(sectors) - 1))
        unit = _chain_unit_for_source(chain.get("source"))

    if not sectors:
        return ["(no chain yet)", "explore / mine first"]

    parts = []
    numeric_sids = set()  # only the sids that actually parsed as int (see loop below)
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
        numeric_sids.add(sid_i)
        if cur is not None and sid_i == cur:
            parts.append(f"★{sid_i}")
        else:
            parts.append(str(sid_i))
    path = "→".join(parts)
    lines = [path[:cols], f"{hops} {unit}"]
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
    # Reuses numeric_sids from the loop above -- a non-numeric sid (already
    # tolerated there via str(sid)) must never re-crash a bare int(s) here.
    if cur is not None and cur in numeric_sids:
        lines.append(f"here ★{cur}"[:cols])
    elif cur is not None:
        lines.append(f"here {cur} (off)"[:cols])
    return lines


def compose_longest_chain_panel(chain, *, current_sector=None, cols: int = 24) -> list[str]:
    """Alias used by the app — same body as format_chain_summary."""
    return format_chain_summary(chain, current_sector=current_sector, cols=cols)


# -- WO-TUI-CHAIN-BUBBLES: literal bubble-chain under the viewport ---------
#
# Highlight contract: ★ centered under the active bubble (ship sector
# match and/or active run_chain hop). Curses may ALSO reverse-video the
# active bubble body; the pure composer only emits the ★ marker row.
# Closed ProfitChain cycles drop the repeated closing = opening sector.

_CHAIN_CONNECTOR = "═════"
_CHAIN_EMPTY_PLACEHOLDER = "○ ○  no trade loop yet"


def chain_bubble_sectors(chain) -> list:
    """Unique hop-order sectors for bubble art (drop closed-cycle repeat)."""
    if chain is None:
        return []
    if hasattr(chain, "sectors"):
        sectors = list(chain.sectors or ())
    elif isinstance(chain, dict):
        sectors = list(chain.get("sectors") or ())
    else:
        return []
    if len(sectors) >= 2 and sectors[0] == sectors[-1]:
        sectors = sectors[:-1]
    out = []
    for sid in sectors:
        try:
            out.append(int(sid))
        except (TypeError, ValueError):
            continue
    return out


def filter_port_only_sectors(sectors, known_ports) -> list:
    """Deprecated alias — use :func:`longest_contiguous_port_run`."""
    return longest_contiguous_port_run(sectors, known_ports)


def longest_contiguous_port_run(
    sectors,
    known_ports,
    *,
    prefer_sector=None,
) -> list:
    """Longest contiguous subsequence where every sector is a known port.

    A non-port (or unknown) sector is a **break** — it never appears in
    the result and splits candidates. When two runs tie on length, prefer
    the run containing ``prefer_sector`` (live ship sector).
    """
    if known_ports is None:
        return list(sectors)
    allow = set()
    for p in known_ports:
        try:
            allow.add(int(p))
        except (TypeError, ValueError):
            continue
    try:
        cur = int(prefer_sector) if prefer_sector is not None else None
    except (TypeError, ValueError):
        cur = None

    best: list[int] = []
    run: list[int] = []
    for sid in sectors:
        try:
            sid = int(sid)
        except (TypeError, ValueError):
            run = []
            continue
        if sid in allow:
            run.append(sid)
            if len(run) > len(best):
                best = run[:]
            elif (
                len(run) == len(best)
                and cur is not None
                and cur in run
                and cur not in best
            ):
                best = run[:]
        else:
            run = []
    return best


def _bubble_inner_w(sectors: list) -> int:
    """Inner width between │ │ — enough for the widest sector id (min 4)."""
    widest = max((len(str(s)) for s in sectors), default=3)
    return max(4, widest)


def _pad_center(text: str, width: int) -> str:
    text = str(text)[:width]
    pad = width - len(text)
    left = pad // 2
    return (" " * left) + text + (" " * (pad - left))


def _center_block(lines: list[str], width: int, height: int) -> list[str]:
    width = max(1, int(width))
    height = max(1, int(height))
    trimmed = [(ln or "")[:width] for ln in lines]
    while len(trimmed) < height:
        trimmed.append("")
    trimmed = trimmed[:height]
    out = []
    for ln in trimmed:
        pad = max(0, width - len(ln))
        left = pad // 2
        out.append((" " * left) + ln + (" " * (pad - left)))
    return out


def compose_chain_bubbles(
    chain,
    *,
    current_sector=None,
    port_classes=None,
    width: int = 82,
    active_sector=None,
    known_ports=None,
) -> list[str]:
    """Pure ASCII bubble-chain (WO-TUI-CHAIN-BUBBLES).

    Returns exactly ``CHAIN_VIZ_H`` lines, centered in ``width``. Empty
    state is a quiet placeholder (no heavy box). Truncates left→right with
    an ``… Nh`` suffix when the full chain exceeds ``width``.

    ``port_classes`` maps sector_id → class string (e.g. ``BSB``); unknown
    sectors render ``?`` — never invent commodities.

    ``known_ports`` (WO-TUI-CHAIN-PORT-ONLY): when provided, bubbles
    show the **longest contiguous run** of sector ids that are all known
    ports — a non-port sector is a break, never bridged.
    """
    width = max(8, int(width))
    port_classes = port_classes or {}
    sectors = longest_contiguous_port_run(
        chain_bubble_sectors(chain),
        known_ports,
        prefer_sector=current_sector if current_sector is not None else active_sector,
    )
    if not sectors:
        return _center_block([_CHAIN_EMPTY_PLACEHOLDER], width, CHAIN_VIZ_H)

    try:
        cur = int(current_sector) if current_sector is not None else None
    except (TypeError, ValueError):
        cur = None
    if active_sector is not None and cur is None:
        try:
            cur = int(active_sector)
        except (TypeError, ValueError):
            cur = None

    inner = _bubble_inner_w(sectors)
    bubble_w = inner + 2  # │ + content + │
    conn = _CHAIN_CONNECTOR
    conn_w = len(conn)

    def _one_bubble(sid: int) -> tuple[str, str, str, str]:
        cls = port_classes.get(sid)
        if cls is None or cls == "":
            cls = "?"
        cls = str(cls)[:inner]
        top = "╭" + ("─" * inner) + "╮"
        mid_sec = "│" + _pad_center(str(sid), inner) + "│"
        mid_cls = "│" + _pad_center(cls, inner) + "│"
        bot = "╰" + ("─" * inner) + "╯"
        return top, mid_sec, mid_cls, bot

    def _fit_count(n: int, truncated: bool) -> int:
        """Width needed for n bubbles (+ optional … Nh suffix)."""
        art = n * bubble_w + max(0, n - 1) * conn_w
        if truncated:
            # " … 12h" after the last shown bubble
            art += 1 + len(f"… {len(sectors)}h")
        return art

    show_n = len(sectors)
    truncated = False
    while show_n > 1 and _fit_count(show_n, truncated=True) > width:
        show_n -= 1
        truncated = True
    if show_n < len(sectors):
        truncated = True
    # If even one bubble + suffix won't fit, shrink to one bubble bare.
    if _fit_count(show_n, truncated=truncated) > width:
        show_n = 1
        truncated = len(sectors) > 1

    shown = sectors[:show_n]
    tops, mids_s, mids_c, bots, stars = [], [], [], [], []
    for i, sid in enumerate(shown):
        t, ms, mc, b = _one_bubble(sid)
        if i:
            tops.append(" " * conn_w)
            mids_s.append(conn)
            mids_c.append(" " * conn_w)
            bots.append(" " * conn_w)
            stars.append(" " * conn_w)
        tops.append(t)
        mids_s.append(ms)
        mids_c.append(mc)
        bots.append(b)
        stars.append(_pad_center("★" if cur is not None and sid == cur else " ", bubble_w))

    top_ln = "".join(tops)
    mid_s_ln = "".join(mids_s)
    mid_c_ln = "".join(mids_c)
    bot_ln = "".join(bots)
    star_ln = "".join(stars)
    if truncated:
        suffix = f" … {len(sectors)}h"
        mid_s_ln = mid_s_ln + suffix
        # Keep other rows length-aligned for centering.
        pad = len(suffix)
        top_ln = top_ln + (" " * pad)
        mid_c_ln = mid_c_ln + (" " * pad)
        bot_ln = bot_ln + (" " * pad)
        star_ln = star_ln + (" " * pad)

    return _center_block([top_ln, mid_s_ln, mid_c_ln, bot_ln, star_ln], width, CHAIN_VIZ_H)


def compose_phase2_side_panel(
    goals_snap,
    chain,
    *,
    current_sector=None,
    width: int = 22,
    include_chain: bool = True,
) -> list[str]:
    """Combine GOALS (+ optional CHAIN) for the Decisions-band panel.

    When a dedicated CHAIN region exists (WO-TUI-CHAIN-BOX), callers pass
    ``include_chain=False`` so DECISIONS keeps GOALS/autonomy only.

    PRIORITIES lives in its own titled left-gutter box (``regions["priorities"]``) —
    never folded here (human 2026-07-22 / WO-TUI-PRIORITIES-LEFT).
    """
    lines = ["— GOALS —"]
    lines.extend(compose_primary_goals_lines(goals_snap, width=width))
    if include_chain:
        lines.append("— CHAIN —")
        lines.extend(
            format_chain_summary(chain, current_sector=current_sector, cols=width)
        )
    return lines


# -- WO-FA5a: DECISIONS pane rotation --------------------------------------
#
# The DECISIONS pane is ONE fixed region shared by three producers
# (explore-mode ticks, a live autopilot trace, and this Phase-2
# GOALS+CHAIN panel) -- whichever one is "active" used to win the pane
# FOREVER: explore stays on until the operator cycles it back to off, and
# a live trace keeps arriving on every status poll. GOALS+CHAIN has no
# keybinding of its own to reclaim the pane, so it needs a standing
# guarantee instead -- every ROTATION_PERIOD_S seconds it gets DWELL_S
# seconds of the pane back, regardless of what's preempting it. Pure
# function of wall-clock `now` -- no state to thread through the render
# loop, no drift, trivially unit-testable without a terminal.
#
# 5s/12s (pixel's UX ruling): a shorter dwell read as too rushed to scan
# a 5-7 line GOALS+CHAIN panel; this split gives trace ~58% of the cycle
# (still dominant) and goals+chain ~42% -- a glance-at-strategy rhythm,
# not a rushed flash.
CHAIN_PANEL_ROTATION_PERIOD_S = 12.0
CHAIN_PANEL_DWELL_S = 5.0


def decisions_should_show_chain(now: float) -> bool:
    """True during GOALS+CHAIN's periodic dwell window in the shared
    DECISIONS pane's rotation cycle. Only meaningful while something
    else (explore/trace) is actively preempting -- with nothing
    preempting, GOALS+CHAIN already owns the pane outright and callers
    don't need this at all."""
    return (now % CHAIN_PANEL_ROTATION_PERIOD_S) < CHAIN_PANEL_DWELL_S


def compose_decisions_placeholder() -> list[str]:
    """Idle DECISIONS copy when no live autopilot_trace is on status.

    Honest empty state — not a TW-13 "coming soon" stub
    (WO-TUI-PRIORITIES-DECISIONS-REGRESS).
    """
    return [
        "no live trace",
        "(start autopilot",
        " or explore: E)",
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

CONTROL_HINTS = "M)ode  L)chains  E)xplore  Spc pause  X stop  P panic  A)ttach"
# WO-FA5a fold (human-reported, live-witnessed 2026-07-21): pressing `M`
# here only cycles ai_pilot<->spectate BY DESIGN (`tw attach` is the only
# door into MODE_HUMAN -- control_lock.py's module docstring) -- but the
# legend never told the operator that, so `M` looked broken/dead-ended.
# WO-FA5c upgrade: `A` is now a REAL keybinding THIS screen consumes
# (spectate_app._suspend_and_run_attach() suspends curses and launches
# `tw attach` as a subprocess, resuming on return) -- the interim
# "attach:drive" pointer (a discoverability-only token that deliberately
# didn't follow the "KEY)verb" shape, since it wasn't a keystroke this
# screen consumed) is superseded by the same "KEY)verb" token every
# other hint uses. Still fits the "minimal" reflow tier's control strip
# (82 inner cols) without truncating the existing tokens -- see
# test_control_strip_shows_the_attach_takeover_hint_under_a_fake_pty.
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
    count = int(loop.get("steps") or 0)
    unit = _chain_unit_for_source(loop.get("source"))
    row = (
        f"{marker} {tag}{loop['name']:<22} {loop.get('source', '?'):<9} "
        f"{overall:>10} {cr_turn:>8} {cr_exec:>10} {count:>3} {unit}"
    )
    return row[: max(0, cols - 1)]


def format_loops_library_header(count: int) -> str:
    # TW-07 rename + TW-20 Enter wording (arms, does not fire).
    return (
        f"TRADE LOOP CHAINS — {count} chain(s) — "
        f"↑/↓ select · 1-9 cycles · Enter arms · Esc/L close"
    )


def format_longest_chain_banner(loop: dict, cols: int) -> str:
    """Centerpiece callout for the longest chain (TW-07 §22.2) -- "hops"
    for a genuine discovered trade-loop chain, "steps" for a recorded/
    mined skill's macro (see _chain_unit_for_source)."""
    count = int(loop.get("steps") or 0)
    unit = _chain_unit_for_source(loop.get("source"))
    text = f"★ LONGEST CHAIN · {loop.get('name', '?')} · {count} {unit}"
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
    if dashboard.get("priorities"):
        lines.append("-" * 80)
        lines.append(" PRIORITIES — goals + focus list")
        lines.append("-" * 80)
        lines.extend(dashboard["priorities"])
    lines.append("-" * 80)
    lines.append(" EVENTS")
    lines.append("-" * 80)
    lines.extend(dashboard["ticker"] or ["(no events yet)"])
    lines.append("-" * 80)
    lines.append(dashboard["status"])
    return "\n".join(lines)
