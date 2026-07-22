"""Spectator dashboard layout tests — pure functions, no curses/terminal
involved. Feeds synthetic events and asserts each dashboard section
renders the expected values.
"""

from twclient.spectate_layout import (
    CREDIT_FLASH_DURATION_S,
    CREDIT_TWEEN_DURATION_S,
    CHAIN_PANEL_DWELL_S,
    CHAIN_PANEL_ROTATION_PERIOD_S,
    DECISIONS_MIN_H,
    FRESHNESS_STALE_S,
    FULL_GUTTER_MIN_COLS,
    LEFT_GUTTER_MIN_COLS,
    PRIORITIES_MIN_W,
    PRIORITIES_W,
    GAME_H,
    GAME_W,
    HUD_GUTTER_W,
    HUD_GUTTER_MIN_H,
    LOG_BOX_MIN_H,
    MINIMAL_HEADER_MIN_COLS,
    RIGHT_GUTTER_MIN_COLS,
    VIEWPORT_H,
    VIEWPORT_W,
    GoalsSnapshot,
    aggregate_world_metrics,
    chain_hop_count_and_unit,
    compose_autonomy_footer_box,
    compose_autonomy_headline,
    compose_dashboard,
    compose_decisions_placeholder,
    compose_hud_cells,
    compose_live_metrics,
    compose_phase2_side_panel,
    compose_port_panel,
    compose_primary_goals_lines,
    compose_priorities_lines,
    compose_priorities_panel,
    compute_autonomy_ratio,
    decisions_should_show_chain,
    format_autonomy_counts,
    format_autonomy_lines,
    format_autopilot_trace_lines,
    format_chain_summary,
    format_freshness,
    format_idle_age,
    format_sidebar,
    format_status_line,
    format_ticker_entry,
    format_ticker_history,
    format_trace_ev,
    PROVISIONAL_AUTOPILOT_TRACE,
    CHAIN_VIZ_H,
    compose_chain_bubbles,
    chain_bubble_sectors,
    frame_layout,
    gauge_semantic,
    is_recent,
    render_bar_meter,
    stamp_world_metrics,
    render_plain,
    render_sparkline,
    status_semantic,
    tick_down_timer,
    update_tracked_stats,
    seed_tracked_from_status,
    CONTROL_HINTS,
    compose_control_strip,
    format_loops_library_header,
    format_loops_library_row,
    format_longest_chain_banner,
    format_mode_badge,
    format_play_progress_or_hints,
    format_tx_readout,
    longest_chain_steps,
    sort_trade_loop_chains,
)


def _event(**overrides):
    base = {
        "ok": True,
        "screen": ["Command [TL=00:00:00]:[22825] (?=Help)? :"],
        "prompt": "Command [TL=00:00:00]:[22825] (?=Help)? :",
        "classification": "main_command",
        "settled_reason": "idle",
        "state": {"sector": 22825, "turns_left": 29990, "credits": 100000},
        "ts": "2026-07-19T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_sidebar_includes_classification_and_settled_reason():
    lines = format_sidebar(_event())
    joined = "\n".join(lines)
    assert "main_command" in joined
    assert "idle" in joined


def test_sidebar_includes_parsed_state_fields():
    lines = format_sidebar(_event())
    joined = "\n".join(lines)
    assert "22825" in joined
    assert "29,990" in joined  # comma-formatted per the credits/turns convention
    assert "100,000" in joined


def test_sidebar_prefers_turns_left_over_turn_timer_when_both_absent_is_fine():
    lines = format_sidebar(_event(state={"turn_timer": "00:00:00"}))
    joined = "\n".join(lines)
    assert "00:00:00" in joined
    assert "Turns left" not in joined


def test_sidebar_renders_port_commodities():
    state = {"port": {"commodities": [{"name": "Fuel Ore", "status": "buying", "pct": 100, "amount": 2650}]}}
    lines = format_sidebar(_event(state=state))
    joined = "\n".join(lines)
    assert "Fuel Ore" in joined
    assert "buying" in joined
    assert "100%" in joined


def test_sidebar_omits_missing_fields_gracefully():
    lines = format_sidebar(_event(state={}))
    joined = "\n".join(lines)
    assert "Sector" not in joined
    assert "Credits" not in joined
    assert "Port" not in joined


def test_sidebar_renders_confidence_and_novelty_when_present():
    """Forward-compatible with a future A5 confidence/novelty score --
    must render if present, must not error/appear if absent (already
    covered by the omission test above)."""
    lines = format_sidebar(_event(confidence=0.92, novelty="new_screen_shape"))
    joined = "\n".join(lines)
    assert "0.92" in joined
    assert "new_screen_shape" in joined


def test_ticker_entry_format():
    entry = format_ticker_entry(_event())
    assert entry.startswith("[2026-07-19T00:00:00Z]")
    assert "main_command" in entry
    assert "idle" in entry


def test_ticker_entry_truncates_long_prompts():
    entry = format_ticker_entry(_event(prompt="x" * 100))
    assert len(entry) < 100


def test_ticker_entry_pairs_the_sent_input_when_present():
    # Orphan TX (no answered_prompt): must not attach →sent to landing prompt
    entry = format_ticker_entry(_event(sent_input="158", prompt="Command?"))
    assert "→158" in entry
    assert "— Command?  →158" not in entry
    assert "⇒ Command?" in entry


def test_ticker_entry_omits_tx_segment_when_absent():
    entry = format_ticker_entry(_event())
    assert "→" not in entry


def test_ticker_history_pairs_sent_with_prior_prompt_not_landing():
    """WO-TUI-LOG-QA-SKEW: answer attaches to the prompt it answered."""
    events = [
        _event(prompt="What is your name?", sent_input=None, classification="login"),
        _event(prompt="ANSI graphics?", sent_input="F", classification="login"),
        _event(prompt="Game? Tumbleweed", sent_input="Tumbleweed", classification="game_select"),
    ]
    lines = format_ticker_history(events)
    assert "— What is your name?  →F" in lines[1]
    assert "⇒ ANSI graphics?" in lines[1]
    assert "— ANSI graphics?  →Tumbleweed" in lines[2]
    assert "— ANSI graphics?  →F" not in lines[1]


def test_ticker_history_left_class_is_answered_not_landing():
    """WO-TUI-LOG-QA-LABELS: left class tag matches the prompt that got the answer."""
    events = [
        _event(prompt="What is your name?", sent_input=None, classification="name_prompt"),
        _event(prompt="Use ANSI graphics?", sent_input="Tumbleweed", classification="ansi_prompt"),
    ]
    lines = format_ticker_history(events)
    # Must read as name_prompt answering the name question — not ansi_prompt →Tumbleweed
    assert "name_prompt" in lines[1]
    assert "— What is your name?  →Tumbleweed" in lines[1]
    assert "⇒ Use ANSI graphics?" in lines[1]
    assert not lines[1].startswith("[") or "ansi_prompt" not in lines[1].split("—")[0]


def test_ticker_history_orphan_first_sent_does_not_false_pair():
    """First event with →sent and no prior must not claim landing was answered."""
    events = [
        _event(prompt="Use ANSI graphics?", sent_input="F", classification="ansi_prompt"),
    ]
    lines = format_ticker_history(events)
    assert "→F" in lines[0]
    assert "— Use ANSI graphics?  →F" not in lines[0]
    assert "ansi_prompt" not in lines[0].split("→")[0] or "— Use ANSI graphics?" not in lines[0]


def test_status_line_connected():
    line = format_status_line(
        connected=True, subscriber_count=2, last_rx_age_s=1.5, daemon_pid=4242,
        host="game.tw2002.net", world_id="game_tw2002_net__F__Ona",
    )
    assert "CONNECTED" in line
    assert "DISCONNECTED" not in line
    assert "subscribers: 2" in line
    assert "1.5s ago" in line
    assert "4242" in line
    assert "host: game.tw2002.net" in line
    assert "world: game_tw2002_net__F__Ona" in line


def test_status_line_disconnected_defaults():
    line = format_status_line()
    assert "DISCONNECTED" in line
    assert "subscribers: 0" in line
    assert "host: -" in line


def test_compose_dashboard_assembles_all_sections():
    dashboard = compose_dashboard(_event(), ticker_history=[_event()], status={"connected": True})
    assert dashboard["main"] == _event()["screen"]
    assert any("main_command" in line for line in dashboard["sidebar"])
    assert len(dashboard["ticker"]) == 1
    assert "CONNECTED" in dashboard["status"]


def test_compose_dashboard_caps_ticker_to_max_recent():
    history = [_event(ts=f"t{i}") for i in range(20)]
    dashboard = compose_dashboard(_event(), ticker_history=history, status={})
    assert len(dashboard["ticker"]) == 8  # TICKER_MAX
    assert "t19" in dashboard["ticker"][-1]  # most recent kept


def test_compose_dashboard_handles_no_event_yet():
    dashboard = compose_dashboard(None, ticker_history=[], status={})
    assert dashboard["main"] == []
    assert dashboard["ticker"] == []
    assert dashboard["main_color"] == []


def test_compose_dashboard_carries_color_map_alongside_main_text():
    """D13: main_color rides alongside main so a curses renderer can zip
    them together by row index -- render_plain() ignores it (plain text
    has no use for it), but it must still be present on the dashboard."""
    color = [[{"start": 0, "end": 3, "fg": "red", "bg": "default", "bold": True}]]
    dashboard = compose_dashboard(_event(color=color), ticker_history=[], status={})
    assert dashboard["main_color"] == color


def test_compose_dashboard_defaults_main_color_when_absent():
    dashboard = compose_dashboard(_event(), ticker_history=[], status={})
    assert dashboard["main_color"] == []


def test_render_plain_includes_all_sections_and_is_a_single_string():
    dashboard = compose_dashboard(_event(), ticker_history=[_event()], status={"connected": True})
    text = render_plain(dashboard)
    assert isinstance(text, str)
    assert "MAIN" in text
    assert "SIDEBAR" in text
    assert "EVENTS" in text
    assert "Command [TL=" in text
    assert "CONNECTED" in text


def test_render_plain_handles_empty_dashboard_without_crashing():
    dashboard = compose_dashboard(None, ticker_history=[], status={})
    text = render_plain(dashboard)
    assert "(no screen yet)" in text
    assert "(no events yet)" in text


# -- frame_layout() -- the pure reflow ladder (Phase 0/1) ------------------


def test_frame_layout_below_floor_is_too_small():
    regions = frame_layout(19, 200)
    assert regions["mode"] == "too_small"
    assert "19" in regions["message"] or "resize" in regions["message"].lower() or "Resize" in regions["message"]

    regions = frame_layout(40, 59)
    assert regions["mode"] == "too_small"


def test_frame_layout_no_border_tier_below_viewport_width():
    # Terminal 24x80 → inner 22x78 < VIEWPORT_W → no_border
    regions = frame_layout(24, 80)
    assert regions["mode"] == "no_border"
    assert regions["viewport"]["border"] is False
    assert regions["gutter"] is None
    assert regions["outer"] is not None
    # never stretched past the native grid, even unbordered
    assert regions["viewport"]["game_w"] <= GAME_W
    assert regions["viewport"]["game_h"] <= GAME_H


def test_frame_layout_minimal_tier_borders_and_centers_with_no_gutter():
    # +2 outer pad so INNER cols == 90
    regions = frame_layout(32, 92)
    assert regions["mode"] == "minimal"
    vp = regions["viewport"]
    assert vp["border"] is True
    assert vp["w"] == VIEWPORT_W
    assert vp["h"] == VIEWPORT_H
    assert vp["game_w"] == GAME_W  # native, zero-inset, never stretched
    assert vp["game_h"] == GAME_H
    assert regions["gutter"] is None
    assert regions["decisions"] is None
    # centered inside the outer inset: equal-ish margin on both sides
    left_margin = vp["x"] - 1  # subtract outer pad
    right_margin = 92 - 1 - (vp["x"] + vp["w"])
    assert abs(left_margin - right_margin) <= 1


def test_frame_layout_right_gutter_tier_left_anchors_viewport():
    # Terminal size = content floor + outer pad (1 per side)
    regions = frame_layout(36, RIGHT_GUTTER_MIN_COLS + 2)
    assert regions["mode"] == "right_gutter"
    vp = regions["viewport"]
    assert vp["border"] is True
    assert vp["x"] == 1  # left-anchored inside outer inset
    gutter = regions["gutter"]
    assert gutter is not None
    # viewport and gutter never overlap
    assert gutter["x"] >= vp["x"] + vp["w"]
    # Decisions lives in the right HUD column when a gutter exists.
    if regions["decisions"] is not None and regions["gutter"] is not None:
        dec = regions["decisions"]
        hud = regions["gutter"]
        assert dec["x"] == hud["x"]
        assert dec["w"] == HUD_GUTTER_W == hud["w"]
        assert dec["y"] == hud["y"] + hud["h"]
        assert dec["y"] + dec["h"] == vp["y"] + vp["h"]
        assert hud["h"] == vp["h"] - dec["h"]
    elif regions["decisions"] is not None and regions["ticker"] is not None:
        assert regions["decisions"]["y"] == regions["ticker"]["y"]
        assert regions["decisions"]["x"] >= regions["ticker"]["x"] + regions["ticker"]["w"]
    if regions.get("chain") is not None:
        # WO-TUI-CHAIN-BUBBLES: under viewport, centered on game window
        assert regions["chain"]["title"] is None
        assert regions["chain"]["border"] is False
        assert regions["chain"]["h"] == CHAIN_VIZ_H
        assert regions["chain"]["y"] == regions["viewport"]["y"] + regions["viewport"]["h"]
        assert regions["chain"]["x"] == regions["viewport"]["x"]
        assert regions["chain"]["w"] == regions["viewport"]["w"]


def test_frame_layout_full_tier_centers_viewport_with_right_gutter():
    regions = frame_layout(42, FULL_GUTTER_MIN_COLS + 2)
    assert regions["mode"] == "full"
    vp = regions["viewport"]
    gutter = regions["gutter"]
    assert gutter is not None
    assert gutter["x"] >= vp["x"] + vp["w"]
    assert vp["x"] > 1  # centered inside inset, not left-anchored like right_gutter
    assert regions["outer"] is not None
    assert regions["outer"]["w"] == FULL_GUTTER_MIN_COLS + 2
    # WO-TUI-CHAIN-BUBBLES: under-viewport chain + LOG|DECISIONS band
    # WO-TUI-PRIORITIES-LEFT: PRIORITIES is a tall left gutter (not bottom-band)
    assert regions["chain"] is not None
    assert regions["decisions"] is not None
    assert regions["priorities"] is not None
    assert regions["priorities"]["title"] == "PRIORITIES"
    assert regions["priorities"]["h"] == regions["viewport"]["h"]
    assert regions["priorities"]["x"] < regions["viewport"]["x"]
    assert regions["ticker"]["h"] >= 5
    assert regions["decisions"]["w"] == HUD_GUTTER_W
    assert regions["decisions"]["h"] >= DECISIONS_MIN_H
    assert (
        regions["decisions"]["y"] + regions["decisions"]["h"]
        == regions["viewport"]["y"] + regions["viewport"]["h"]
    )
    assert regions["ticker"]["w"] == FULL_GUTTER_MIN_COLS
    assert regions["chain"]["h"] == CHAIN_VIZ_H
    assert regions["chain"]["title"] is None
    assert regions["chain"]["y"] == regions["viewport"]["y"] + regions["viewport"]["h"]
    assert regions["chain"]["x"] == regions["viewport"]["x"]


def test_frame_layout_viewport_never_stretched_beyond_native_grid():
    for cols in (60, 82, 90, 108, 132, 200):
        regions = frame_layout(52, cols + 2)
        if regions["mode"] == "too_small":
            continue
        vp = regions["viewport"]
        assert vp["game_w"] <= GAME_W
        assert vp["game_h"] <= GAME_H


def test_frame_layout_status_bar_always_present_and_pinned_to_last_inner_row():
    for lines, cols in ((22, 62), (26, 82), (32, 92), (42, 142)):
        regions = frame_layout(lines, cols)
        assert regions["status"]["y"] == lines - 2  # above outer bottom border
        assert regions["status"]["h"] == 1
        assert regions["outer"] is not None


def test_frame_layout_drops_header_before_border_under_height_pressure():
    """Exactly enough body height for a bordered viewport and nothing
    else -- the header is the first thing to go (plan: "height ladder
    degrades by dropping header/border lines")."""
    # inner: status(1) + VIEWPORT_H → terminal +2 outer
    lines = VIEWPORT_H + 1 + 2
    regions = frame_layout(lines, MINIMAL_HEADER_MIN_COLS + 2)
    assert regions["viewport"]["border"] is True
    assert regions["header"] is None


def test_frame_layout_adds_header_once_there_is_a_spare_line():
    lines = VIEWPORT_H + 2 + 2
    regions = frame_layout(lines, MINIMAL_HEADER_MIN_COLS + 2)
    assert regions["viewport"]["border"] is True
    assert regions["header"] is not None


def test_frame_layout_too_small_has_no_control_region():
    regions = frame_layout(19, 200)
    assert regions["control"] is None
    assert regions["outer"] is None


def test_frame_layout_control_strip_sits_directly_above_status_when_present():
    regions = frame_layout(42, 142)  # plenty of leftover body height
    control = regions["control"]
    assert control is not None
    assert control["h"] == 1
    assert control["y"] == regions["status"]["y"] - 1
    assert control["w"] == 140  # inner cols


def test_frame_layout_control_strip_takes_priority_over_ticker_for_scarce_leftover():
    """Exactly one spare body row (not enough for BOTH control and a
    titled LOG box) -- the control strip wins (WO: "the control
    strip is the panel's primary interactive surface; the ticker is a
    nice-to-have event log"), and the ticker is dropped entirely rather
    than the two overlapping."""
    # Use a size with exactly 1 leftover row AFTER the header is placed.
    # inner leftover=1 → lines = VIEWPORT_H + 3 + 2 outer
    lines = VIEWPORT_H + 3 + 2
    regions = frame_layout(lines, MINIMAL_HEADER_MIN_COLS + 2)
    assert regions["header"] is not None
    assert regions["control"] is not None
    assert regions["ticker"] is None


def test_frame_layout_ticker_still_appears_with_enough_leftover_for_both():
    lines = VIEWPORT_H + 6 + 2
    regions = frame_layout(lines, MINIMAL_HEADER_MIN_COLS + 2)
    assert regions["control"] is not None
    assert regions["ticker"] is not None
    assert regions["ticker"].get("title") == "LOG"
    # control sits between the ticker and the status bar, never overlapping either.
    assert regions["ticker"]["y"] + regions["ticker"]["h"] <= regions["control"]["y"]
    assert regions["control"]["y"] + regions["control"]["h"] <= regions["status"]["y"]


def test_frame_layout_is_a_pure_function_of_its_inputs():
    a = frame_layout(42, 142)
    b = frame_layout(42, 142)
    assert a == b  # same inputs -> structurally equal dict every time


def test_frame_layout_tw08_regions_do_not_overlap_at_full_tier():
    """TW-08 geometry proof: outer / viewport / gutter / decisions /
    log / control / status rects are pairwise non-overlapping (outer
    is the wrap; inners must not collide with each other)."""
    regions = frame_layout(42, FULL_GUTTER_MIN_COLS + 2)
    assert regions["mode"] == "full"
    assert regions["outer"] is not None
    assert regions["decisions"] is not None
    assert regions["ticker"] is not None

    def _rect(r):
        return (r["y"], r["x"], r["y"] + r["h"], r["x"] + r["w"])

    def _overlap(a, b):
        ay0, ax0, ay1, ax1 = a
        by0, bx0, by1, bx1 = b
        return not (ay1 <= by0 or by1 <= ay0 or ax1 <= bx0 or bx1 <= ax0)

    panes = [
        regions["viewport"], regions["gutter"], regions["decisions"],
        regions["ticker"], regions["control"], regions["status"],
    ]
    if regions.get("priorities") is not None:
        panes.insert(3, regions["priorities"])
    if regions.get("chain") is not None:
        panes.insert(3, regions["chain"])
    if regions["header"] is not None:
        panes.insert(0, regions["header"])
    rects = [_rect(p) for p in panes]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            assert not _overlap(rects[i], rects[j]), (
                f"overlap between panes {i} and {j}: {rects[i]} vs {rects[j]}"
            )

# -- the persistent HUD accumulator (the operator's directive) --------------


def test_update_tracked_stats_persists_fields_across_events_lacking_them():
    """The exact bug this replaces: format_sidebar's `if "credits" in
    state` silently DROPPED credits on a credits-less screen. The
    accumulator must instead keep the last-known value."""
    tracked = {}
    tracked = update_tracked_stats(tracked, {"state": {"credits": 100000, "sector": 22825}}, now=10.0)
    assert tracked["credits"] == (100000, 10.0)
    assert tracked["sector"] == (22825, 10.0)

    # A later event with NO state at all (e.g. a combat prompt) --
    # previously-tracked fields must survive untouched.
    tracked = update_tracked_stats(tracked, {"state": {}}, now=15.0)
    assert tracked["credits"] == (100000, 10.0)
    assert tracked["sector"] == (22825, 10.0)


def test_update_tracked_stats_updates_only_fields_present_on_the_new_event():
    tracked = {"credits": (100, 1.0), "sector": (5, 1.0)}
    tracked = update_tracked_stats(tracked, {"state": {"sector": 6}}, now=2.0)
    assert tracked["sector"] == (6, 2.0)
    assert tracked["credits"] == (100, 1.0)  # untouched -- not in this event's state


def test_update_tracked_stats_prefers_turns_left_and_ignores_turn_timer():
    tracked = update_tracked_stats({}, {"state": {"turns_left": 29990}}, now=1.0)
    assert tracked["turns"] == (("count", 29990), 1.0)

    tracked = update_tracked_stats({}, {"state": {"turn_timer": "00:04:12"}}, now=1.0)
    assert "turns" not in tracked


def test_update_tracked_stats_count_survives_later_timer_only_screen():
    """WO-TUI-HUD-POLISH / WO-TUI-HUD-TURNS-COUNT: TL= must not clobber turns."""
    tracked = update_tracked_stats({}, {"state": {"turns_left": 4406}}, now=1.0)
    tracked = update_tracked_stats(tracked, {"state": {"turn_timer": "00:00:00", "sector": 4406}}, now=5.0)
    assert tracked["turns"] == (("count", 4406), 1.0)
    cells = compose_hud_cells(tracked, now=5.0)
    turns = [c for c in cells if c["label"] == "TURNS"][0]
    assert turns["value"] == "4,406"
    assert not any(c["label"] == "REGEN" for c in cells)


def test_update_tracked_stats_timer_alone_leaves_turns_blank():
    """WO-TUI-HUD-TURNS-COUNT: TURNS slot is count-only — never HH:MM:SS."""
    tracked = update_tracked_stats({}, {"state": {"turn_timer": "00:00:00", "sector": 1}}, now=1.0)
    assert "turns" not in tracked
    cells = compose_hud_cells(tracked, now=1.0)
    turns = [c for c in cells if c["label"] == "TURNS"][0]
    assert turns["value"] == "-"
    assert ":" not in turns["value"]


def test_update_tracked_stats_prefers_fa7a_credits_and_ignores_port_quote_state():
    """FA7a top-level balance wins; loose state credits must not replace it."""
    tracked = update_tracked_stats(
        {}, {"credits": 100000, "credits_age_ms": 0, "state": {}}, now=10.0,
    )
    assert tracked["credits"] == (100000, 10.0)
    tracked = update_tracked_stats(
        tracked,
        {"credits": 100000, "credits_age_ms": 3000, "state": {"credits": 42}},  # port quote
        now=13.0,
    )
    assert tracked["credits"][0] == 100000
    assert tracked["credits"][1] == 10.0  # age_ms=3000 → seen_ts=13-3
    cells = compose_hud_cells(tracked, now=13.0)
    assert [c for c in cells if c["label"] == "CREDITS"][0]["value"] == "100,000"


def test_compose_hud_cells_credits_persist_when_absent_from_later_screen():
    tracked = update_tracked_stats({}, {"state": {"credits": 87500}}, now=1.0)
    tracked = update_tracked_stats(tracked, {"state": {"sector": 250}}, now=4.0)
    cells = compose_hud_cells(tracked, now=4.0)
    assert [c for c in cells if c["label"] == "CREDITS"][0]["value"] == "87,500"


def test_hud_gutter_width_floor_fits_credits_freshness():
    """WO-TUI-HUD-POLISH: pin HUD_GUTTER_W ≥34 and tier floors stay coherent."""
    assert HUD_GUTTER_W >= 34
    assert RIGHT_GUTTER_MIN_COLS == VIEWPORT_W + HUD_GUTTER_W
    assert FULL_GUTTER_MIN_COLS == VIEWPORT_W + HUD_GUTTER_W + PRIORITIES_W
    assert LEFT_GUTTER_MIN_COLS == VIEWPORT_W + HUD_GUTTER_W + PRIORITIES_MIN_W
    assert FULL_GUTTER_MIN_COLS >= RIGHT_GUTTER_MIN_COLS
    regions = frame_layout(36, RIGHT_GUTTER_MIN_COLS + 2)
    assert regions["mode"] == "right_gutter"
    assert regions["gutter"]["w"] == HUD_GUTTER_W
    regions = frame_layout(42, FULL_GUTTER_MIN_COLS + 2)
    assert regions["mode"] == "full"
    assert regions["gutter"]["w"] == HUD_GUTTER_W


def test_update_tracked_stats_computes_profit_as_delta_from_first_seen_credits():
    tracked = update_tracked_stats({}, {"state": {"credits": 100000}}, now=1.0)
    assert "profit" not in tracked  # no baseline delta yet on the very first sighting

    tracked = update_tracked_stats(tracked, {"state": {"credits": 100230}}, now=2.0)
    assert tracked["profit"] == (230, 2.0)

    tracked = update_tracked_stats(tracked, {"state": {"credits": 99500}}, now=3.0)
    assert tracked["profit"] == (-500, 3.0)  # can go negative -- a real loss since session start


def test_seed_tracked_from_status_fills_fa7a_credits_on_cold_start():
    tracked = seed_tracked_from_status(
        {},
        {"credits": 250000, "credits_age_ms": 5000},
        now=100.0,
    )
    assert tracked["credits"] == (250000, 95.0)
    cells = compose_hud_cells(tracked, now=100.0)
    assert [c for c in cells if c["label"] == "CREDITS"][0]["value"] == "250,000"


def test_seed_tracked_from_status_backfills_missing_fields_without_clobbering():
    tracked = update_tracked_stats({}, {"state": {"sector": 4406, "turns_left": 1200}}, now=1.0)
    seeded = seed_tracked_from_status(
        tracked,
        {"credits": 99999, "credits_age_ms": 0},
        now=5.0,
        parsed_state={"sector": 9999, "turns_left": 1},
    )
    assert seeded["sector"] == (4406, 1.0)
    assert seeded["turns"] == (("count", 1200), 1.0)
    assert seeded["credits"] == (99999, 5.0)


def test_seed_tracked_from_status_uses_parsed_state_when_tracked_empty():
    tracked = seed_tracked_from_status(
        {},
        {"credits": None, "credits_age_ms": None},
        now=2.0,
        parsed_state={"sector": 22825, "turns_left": 4406, "cargo_holds_empty": 12},
    )
    assert tracked["sector"] == (22825, 2.0)
    assert tracked["turns"] == (("count", 4406), 2.0)
    assert tracked["cargo_holds_empty"] == (12, 2.0)


def test_seed_tracked_from_status_prefers_status_turns_left():
    """WO-HUD-CREDITS-TURNS-JOIN: sticky session turns via status beat a
    empty/missing parsed fighter-toll screen."""
    tracked = seed_tracked_from_status(
        {},
        {"credits": 300, "credits_age_ms": 0, "turns_left": 1622},
        now=10.0,
        parsed_state={"sector": 2594},
    )
    assert tracked["credits"] == (300, 10.0)
    assert tracked["turns"] == (("count", 1622), 10.0)
    assert tracked["sector"] == (2594, 10.0)


def test_update_tracked_stats_is_pure_returns_new_dict():
    tracked = {}
    out = update_tracked_stats(tracked, {"state": {"sector": 1}}, now=1.0)
    assert tracked == {}  # original untouched
    assert out is not tracked


def test_update_tracked_stats_handles_none_event():
    assert update_tracked_stats({}, None, now=1.0) == {}


# -- format_freshness / staleness -------------------------------------------


def test_format_freshness_shows_now_for_sub_second_age():
    assert format_freshness(0.4) == "✦ now"


def test_format_freshness_shows_seconds_ago():
    assert format_freshness(7.9) == "✦ 7s ago"


def test_format_freshness_accepts_an_ascii_mark():
    assert format_freshness(3.0, mark="*") == "* 3s ago"


# -- compose_hud_cells() -----------------------------------------------------


def test_compose_hud_cells_placeholder_shape_with_no_data_yet():
    cells = compose_hud_cells({}, now=100.0)
    labels = [c["label"] for c in cells]
    assert labels == ["CREDITS", "SECTOR", "TURNS", "CARGO", "PROFIT"]
    assert all(c["value"] == "-" for c in cells)
    assert all(c["freshness"] == "" for c in cells)
    assert all(c["stale"] is False for c in cells)


def test_compose_hud_cells_formats_values_and_freshness():
    tracked = update_tracked_stats({}, {"state": {"credits": 100000, "sector": 1027, "cargo_holds_empty": 50}}, now=100.0)
    cells = compose_hud_cells(tracked, now=102.0)
    by_label = {c["label"]: c for c in cells}
    assert by_label["CREDITS"]["value"] == "100,000"
    assert by_label["CREDITS"]["freshness"] == "✦ 2s ago"
    assert by_label["SECTOR"]["value"] == "1027"
    assert by_label["CARGO"]["value"] == "50"


def test_compose_hud_cells_dims_a_cell_past_the_staleness_threshold():
    tracked = update_tracked_stats({}, {"state": {"credits": 100000}}, now=0.0)
    fresh = compose_hud_cells(tracked, now=FRESHNESS_STALE_S - 1)
    stale = compose_hud_cells(tracked, now=FRESHNESS_STALE_S + 1)
    assert [c for c in fresh if c["label"] == "CREDITS"][0]["stale"] is False
    assert [c for c in stale if c["label"] == "CREDITS"][0]["stale"] is True


def test_compose_hud_cells_turns_cell_ignores_live_timer():
    tracked = update_tracked_stats({}, {"state": {"turn_timer": "00:00:10"}}, now=0.0)
    cells = compose_hud_cells(tracked, now=4.0)
    turns_cell = [c for c in cells if c["label"] == "TURNS"][0]
    assert turns_cell["value"] == "-"


def test_compose_hud_cells_turns_cell_shows_comma_formatted_count():
    tracked = update_tracked_stats({}, {"state": {"turns_left": 29990}}, now=0.0)
    cells = compose_hud_cells(tracked, now=1.0)
    turns_cell = [c for c in cells if c["label"] == "TURNS"][0]
    assert turns_cell["value"] == "29,990"


def test_compose_live_metrics_placeholder_shape():
    rows = compose_live_metrics({})
    assert [r["label"] for r in rows] == [
        "SECTORS", "STATIONS", "PLANETS", "FIGHTERS", "MINES", "PROBLEMS",
    ]
    assert all(r["value"] == "0" for r in rows)


def test_compose_live_metrics_reads_tracked_tuple_values():
    tracked = {
        "sectors_mapped": (100, 1.0),
        "stations_found": (12, 1.0),
        "planets_found": (3, 1.0),
        "fighters_seen": (40, 1.0),
        "mines_seen": (2, 1.0),
        "problem_sectors": (1, 1.0),
    }
    by_label = {r["label"]: r["value"] for r in compose_live_metrics(tracked)}
    assert by_label == {
        "SECTORS": "100", "STATIONS": "12", "PLANETS": "3", "FIGHTERS": "40",
        "MINES": "2", "PROBLEMS": "1",
    }


def test_aggregate_world_metrics_sectors_mapped_is_record_count():
    sectors = [
        {"sector_id": 1, "port": None, "threats": {}, "landmarks": [], "formation_membership": None},
        {"sector_id": 2, "port": None, "threats": {}, "landmarks": [], "formation_membership": None},
    ]
    assert aggregate_world_metrics(sectors)["sectors_mapped"] == 2
    assert aggregate_world_metrics([])["sectors_mapped"] == 0
    assert aggregate_world_metrics(None)["sectors_mapped"] == 0


def test_aggregate_world_metrics_counts_ports_threats_landmarks():
    sectors = [
        {"sector_id": 1, "port": {"class": 1}, "threats": {"mines": False, "fighters": None},
         "landmarks": [], "formation_membership": None},
        {"sector_id": 2, "port": None, "threats": {"mines": True, "fighters": 5},
         "landmarks": ["Own Planet"], "formation_membership": ["one-way"]},
        {"sector_id": 3, "port": {"class": 3}, "threats": {"mines": False, "fighters": None},
         "landmarks": ["StarDock"], "formation_membership": []},
    ]
    m = aggregate_world_metrics(sectors)
    assert m == {
        "sectors_mapped": 3,
        "stations_found": 2,
        "planets_found": 1,
        "fighters_seen": 1,
        "mines_seen": 1,
        "problem_sectors": 1,  # sector 2 only (mines + fighters + one-way)
    }


def test_stamp_world_metrics_feeds_compose_live_metrics():
    metrics = aggregate_world_metrics([
        {"sector_id": 1, "port": {"class": 1}, "threats": {"mines": False, "fighters": None},
         "landmarks": [], "formation_membership": None},
        {"sector_id": 2, "port": None, "threats": {"mines": True, "fighters": None},
         "landmarks": [], "formation_membership": None},
    ])
    tracked = stamp_world_metrics({}, metrics, now=9.0)
    by_label = {r["label"]: r["value"] for r in compose_live_metrics(tracked)}
    assert by_label["SECTORS"] == "2"
    assert by_label["STATIONS"] == "1"
    assert by_label["MINES"] == "1"
    assert by_label["PROBLEMS"] == "1"


def test_compute_autonomy_ratio_trainer_over_ai_plus_trainer():
    entries = [
        {"actor": "ai"},
        {"actor": "ai"},
        {"actor": "trainer"},
        {"actor": "human"},
        {"actor": "trainer"},
    ]
    data = compute_autonomy_ratio(entries)
    assert data["ai"] == 2
    assert data["trainer"] == 2
    assert data["human"] == 1
    assert data["ratio"] == 0.5
    assert data["pct_display"] == "50%"


def test_compute_autonomy_ratio_empty_and_window():
    assert compute_autonomy_ratio([])["pct_display"] == "—"
    assert compute_autonomy_ratio([])["ratio"] is None
    entries = [{"actor": "ai"}] * 10 + [{"actor": "trainer"}] * 10
    data = compute_autonomy_ratio(entries, window=5)
    assert data["ai"] == 0
    assert data["trainer"] == 5
    assert data["pct_display"] == "100%"


def test_format_autonomy_lines_ties_pct_to_app_ai_counts():
    # App/(App+AI) = 30/(30+10) = 75% — counts ARE the ratio.
    data = compute_autonomy_ratio(
        [{"actor": "trainer"}] * 30 + [{"actor": "ai"}] * 10 + [{"actor": "human"}] * 2
    )
    assert data["pct_display"] == "75%"
    lines = format_autonomy_lines(data)
    assert lines[0] == "AUTO 75%"
    assert lines[1] == "App 30 / AI 10 · Hum 2"
    assert "App 30" in format_autonomy_counts(data)
    assert "AI 10" in format_autonomy_counts(data)
    empty = format_autonomy_lines(compute_autonomy_ratio([]))
    assert empty[0] == "AUTO —"
    assert empty[1] == "App 0 / AI 0 · Hum 0"


def test_format_autopilot_trace_lines_chosen_gated_and_hold():
    lines = format_autopilot_trace_lines(PROVISIONAL_AUTOPILOT_TRACE, cols=40)
    assert lines[0].startswith("★ run_chain")
    assert "550" in lines[0]
    assert any(ln.startswith("★ run_chain") for ln in lines[1:])
    assert any(ln.startswith("· upgrade") for ln in lines)
    gated = [ln for ln in lines if ln.startswith("⊘")]
    assert gated and "explore" in gated[0]
    assert "turn-reserve" in gated[0] or "50" in gated[0]
    # HOLD when chosen is None
    hold = format_autopilot_trace_lines(
        {"chosen": None, "candidates": [
            {"kind": "explore", "ev_cr_per_turn": None, "gated": True, "gate_reason": "cash"},
        ]},
        cols=22,
    )
    assert hold[0] == "HOLD"
    assert "—" in hold[1]  # None EV → em-dash, never 0
    assert hold[1].startswith("⊘")
    # empty / malformed → "—", no crash
    assert format_autopilot_trace_lines(None) == ["—"]
    assert format_autopilot_trace_lines({}) == ["—"]
    assert format_autopilot_trace_lines("bogus") == ["—"]
    # non-str chosen must not leak a Python repr into the TUI
    assert format_autopilot_trace_lines(
        {"candidates": "notalist", "chosen": object()}
    ) == ["—"]
    assert format_trace_ev(None) == "—"
    # dual attr tolerance
    class _C:
        kind = "run_chain"
        ev_cr_per_turn = 100.0
        gated = False
        gate_reason = None

    class _T:
        chosen = "run_chain"
        candidates = [_C()]

    attr_lines = format_autopilot_trace_lines(_T(), cols=30)
    assert attr_lines[0].startswith("★ run_chain")
    assert all(len(ln) <= 30 for ln in attr_lines)


def test_compose_hud_cells_appends_autonomy_when_provided():
    # autonomy kwarg is accepted but does not grow the 5-cell ship HUD
    # (a 6th 3-row cell would clip PORT meters in the gutter).
    cells = compose_hud_cells({}, now=1.0, autonomy=compute_autonomy_ratio([{"actor": "trainer"}]))
    assert [c["label"] for c in cells] == [
        "CREDITS", "SECTOR", "TURNS", "CARGO", "PROFIT",
    ]
    assert compose_autonomy_headline(compute_autonomy_ratio([{"actor": "trainer"}]))["value"] == "100%"
    assert compose_autonomy_headline(None)["value"] == "—"


def test_compose_primary_goals_fighters_line():
    zero_lines = compose_primary_goals_lines(GoalsSnapshot(
        fighters_known=True, fighters_count=0,
    ), width=36)
    assert any("Fighters" in ln and "0 (need some)" in ln and "·" in ln for ln in zero_lines)

    ok_lines = compose_primary_goals_lines(GoalsSnapshot(
        fighters_known=True, fighters_count=30,
    ), width=36)
    assert any("Fighters" in ln and "30" in ln and "✓" in ln for ln in ok_lines)

    unknown_lines = compose_primary_goals_lines(GoalsSnapshot(
        fighters_known=False,
    ), width=36)
    assert any("Fighters" in ln and "unknown" in ln and "?" in ln for ln in unknown_lines)


def test_compose_primary_goals_ship_hold_prices_gated_without_stardock():
    blocked = compose_primary_goals_lines(GoalsSnapshot(
        stardock_found=False,
        ship_prices_count=0,
        upgrade_status="price?",
    ), width=36)
    # Parent: StarDock not found
    assert any("StarDock" in ln and "not found" in ln for ln in blocked)
    # Indented children appear immediately after the StarDock parent row
    dock_idx = next(i for i, ln in enumerate(blocked) if "StarDock" in ln and "not found" in ln)
    assert blocked[dock_idx + 1].startswith("  ") and "⊘" in blocked[dock_idx + 1] and "Ship prices" in blocked[dock_idx + 1]
    assert blocked[dock_idx + 2].startswith("  ") and "⊘" in blocked[dock_idx + 2] and "Hold upg" in blocked[dock_idx + 2]
    # The explanatory text is now implied by the parent row — not repeated on each child
    assert not any("need StarDock" in ln or "need dock" in ln for ln in blocked)
    # Short-label variant
    blocked_short = compose_primary_goals_lines(GoalsSnapshot(stardock_found=False), width=20)
    dock_idx_s = next(i for i, ln in enumerate(blocked_short) if "Dock" in ln and "not found" in ln)
    assert blocked_short[dock_idx_s + 1].startswith("  ") and "Ships" in blocked_short[dock_idx_s + 1]
    assert blocked_short[dock_idx_s + 2].startswith("  ") and "Hold" in blocked_short[dock_idx_s + 2]

    hunting = compose_primary_goals_lines(GoalsSnapshot(
        stardock_found=True, stardock_sectors=(100,),
        ship_prices_count=0,
        upgrade_status="price?",
    ), width=36)
    assert any("Ship prices" in ln and "price?" in ln and "·" in ln for ln in hunting)
    assert any("Hold upg" in ln and "price?" in ln for ln in hunting)
    assert not any("need StarDock" in ln for ln in hunting)

    known = compose_primary_goals_lines(GoalsSnapshot(
        stardock_found=True, stardock_sectors=(100,),
        ship_prices_count=4,
        upgrade_status="1500/h",
    ), width=36)
    assert any("Ship prices" in ln and "4 priced" in ln and "✓" in ln for ln in known)
    assert any("Hold upg" in ln and "1500/h" in ln and "✓" in ln for ln in known)


def test_update_tracked_stats_records_fighters_aboard():
    from twclient.spectate_layout import update_tracked_stats

    tracked = update_tracked_stats({}, {
        "state": {"fighters_aboard": 12},
    }, now=100.0)
    assert tracked["fighters"] == (12, 100.0)


def test_compose_primary_goals_and_chain_highlight():
    from twclient.chains import ProfitChain, TradeHop
    lines = compose_primary_goals_lines(GoalsSnapshot(
        turns_known=True, turns_count=220,
        credits_known=True, credits_amount=48000,
        stardock_found=True, stardock_sectors=(4223,), known_sectors=40,
        formations=2, longest_chain_hops=3, longest_chain_unit="hops",
        ship_prices_count=5, upgrade_status="1468/h",
        holds_status="85/125",
    ), width=36)
    assert any("Turns" in ln and "220" in ln and "✓" in ln for ln in lines)
    assert any("Credits" in ln and "48,000" in ln for ln in lines)
    assert any("StarDock" in ln and "4223" in ln for ln in lines)
    assert any("Formations" in ln and "2 found" in ln for ln in lines)
    assert any("Galaxy Exploration:" in ln and "40 Sectors" in ln for ln in lines)
    assert not any("40 known" in ln for ln in lines)
    assert any("3 hops" in ln for ln in lines)
    assert any("Ship prices" in ln and "5 priced" in ln for ln in lines)
    assert any("Hold upg" in ln and "1468/h" in ln for ln in lines)
    assert not any("form " in ln for ln in lines)
    chain = ProfitChain(
        sectors=(1, 2, 3, 1),
        hops=(
            TradeHop(1, 2, "A", 10, 1),
            TradeHop(2, 3, "B", 10, 1),
            TradeHop(3, 1, "C", 10, 1),
        ),
        overall_profit=30,
        turns=3,
        cr_per_turn=10.0,
        cr_per_execution=30.0,
    )
    in_chain = format_chain_summary(chain, current_sector=2, cols=40)
    assert any("★" in ln for ln in in_chain)
    assert any("here ★2" in ln for ln in in_chain)
    panel = compose_phase2_side_panel(
        GoalsSnapshot(known_sectors=5),
        {"sectors": [10, 11, 10], "steps": 2, "demo_profit": 50},
        current_sector=10,
        width=30,
    )
    assert "— GOALS —" in panel and "— CHAIN —" in panel
    assert "— PRIORITIES —" not in panel


# -- WO-TUI-PRIORITIES: ordered weigh list from autopilot_trace ------------


def test_compose_priorities_lines_orders_by_ev_with_readable_labels():
    """Engine ranks ungated chain first; upgrade gated without payback."""
    lines = compose_priorities_lines(PROVISIONAL_AUTOPILOT_TRACE, width=40)
    assert lines[0].startswith("1 ") and "Trade chain" in lines[0] and "550" in lines[0]
    assert lines[1].startswith("2 ") and "Upgrade" in lines[1]
    assert "⊘" in lines[1]  # no payback in trace → engine gates upgrade
    assert lines[2].startswith("3 ") and "Explore" in lines[2]
    assert "⊘" in lines[2]  # gated explore in fixture trace
    assert "run_chain" not in "\n".join(lines)


def test_compose_priorities_lines_engine_stay_vs_leave_demotes_upgrade():
    """RT stay-vs-leave gates upgrade below chain even when raw EV is higher."""
    from twclient.priority_engine import recommend_actions

    trace = {"context": {"turns_left": 500, "sector": 10}, "candidates": []}
    chain = {"sectors": [10, 20, 30, 40, 50, 10], "profit_per_turn": 550.0, "turns": 10, "steps": 5}
    rec = recommend_actions(
        chain_cr_per_turn=550.0,
        chain_cycle_turns=10,
        chain_link_count=5,
        at_chain_start=True,
        upgrade_extra_cr_per_turn=80.0,
        upgrade_payback=20.0,
        hops_to_stardock=10,
        hops_return_to_work=10,
        turns_per_warp=3,
        turns_left=500,
        turn_reserve=50,
        explore_available=False,
    )
    lines = compose_priorities_lines(trace, chain=chain, width=40, priority_rec=rec)
    assert lines[0].startswith("1 ") and "Trade chain" in lines[0] and "550" in lines[0]
    assert "Upgrade" in lines[1] and "⊘" in lines[1]
    assert "RT" in lines[1]


def test_compose_priorities_lines_empty_unknown_is_clear():
    assert compose_priorities_lines(None) == ["—"]
    assert compose_priorities_lines({}) == ["—"]
    assert compose_priorities_lines({"candidates": []}) == ["—"]
    assert compose_priorities_lines("bogus") == ["—"]


def test_compose_priorities_panel_folds_goals_and_weigh_list():
    """Left gutter: GOALS + FOCUS + autonomy footer box — never in DECISIONS."""
    panel = compose_priorities_panel(
        GoalsSnapshot(known_sectors=9),
        None,
        PROVISIONAL_AUTOPILOT_TRACE,
        autonomy_lines=["AUTO 75%", "App 30 / AI 10 · Hum 2"],
        width=36,
        include_chain=False,
    )
    assert "— GOALS —" in panel
    assert "— FOCUS —" in panel
    assert any("Trade chain" in ln for ln in panel)
    assert panel.index("— GOALS —") < panel.index("— FOCUS —")
    # Autonomy is a nested footer box under FOCUS, not a header row.
    assert panel[0] != "AUTO 75%"
    auto_idx = next(i for i, ln in enumerate(panel) if "AUTO 75%" in ln)
    assert auto_idx > panel.index("— FOCUS —")
    assert panel[auto_idx - 1].startswith("╭")
    assert panel[auto_idx + 1].startswith("│") and "App 30" in panel[auto_idx + 1]
    assert panel[auto_idx + 2].startswith("╰")
    # Centered: content is flanked by spaces inside the box.
    assert panel[auto_idx].startswith("│")
    assert panel[auto_idx].endswith("│")
    assert panel[auto_idx].index("AUTO 75%") > 1


def test_compose_autonomy_footer_box_centers_and_fits_width():
    box = compose_autonomy_footer_box(
        ["AUTO 100%", "App 5 / AI 0 · Hum 0"], width=28,
    )
    assert len(box) == 4
    assert box[0].startswith("╭") and box[0].endswith("╮")
    assert box[-1].startswith("╰") and box[-1].endswith("╯")
    assert all(len(ln) == 28 for ln in box)
    assert "AUTO 100%" in box[1]
    assert box[1].index("AUTO 100%") > 1


def test_compose_phase2_side_panel_does_not_fold_priorities():
    """PRIORITIES is its own TUI box — never a section inside GOALS."""
    panel = compose_phase2_side_panel(
        GoalsSnapshot(known_sectors=3),
        None,
        width=36,
        include_chain=False,
    )
    assert panel.count("— GOALS —") == 1
    assert "— PRIORITIES —" not in panel
    assert "Trade chain" not in "\n".join(panel)


def test_frame_layout_full_tier_priorities_matches_hud_width():
    """WO-TUI-PRIORITIES-LEFT: full tier PRIORITIES width == HUD_GUTTER_W."""
    assert PRIORITIES_W == HUD_GUTTER_W
    regions = frame_layout(42, FULL_GUTTER_MIN_COLS + 2)
    pri = regions["priorities"]
    vp = regions["viewport"]
    hud = regions["gutter"]
    assert pri is not None
    assert pri["title"] == "PRIORITIES"
    assert pri["border"] is True
    assert pri["w"] == PRIORITIES_W == HUD_GUTTER_W
    assert pri["h"] == vp["h"]
    assert hud["h"] + regions["decisions"]["h"] == vp["h"]
    assert pri["y"] == vp["y"] == hud["y"]
    assert pri["x"] + pri["w"] <= vp["x"]
    assert vp["x"] + vp["w"] <= hud["x"]
    dec = regions["decisions"]
    assert dec["x"] == hud["x"]
    assert dec["w"] == HUD_GUTTER_W
    assert dec["y"] == hud["y"] + hud["h"]
    assert dec["y"] + dec["h"] == vp["y"] + vp["h"]
    # Bottom band is LOG only — DECISIONS is in the right HUD column.
    assert regions["ticker"]["w"] == FULL_GUTTER_MIN_COLS


def test_frame_layout_decisions_hud_aligned_in_right_column():
    """WO-TUI-DECISIONS-HUD-ALIGN: DECISIONS width matches HUD; bottom aligns."""
    regions = frame_layout(42, FULL_GUTTER_MIN_COLS + 2)
    dec = regions["decisions"]
    hud = regions["gutter"]
    vp = regions["viewport"]
    assert dec is not None and hud is not None
    assert dec["w"] == HUD_GUTTER_W == hud["w"]
    assert dec["x"] == hud["x"]
    assert dec["y"] == hud["y"] + hud["h"]
    assert dec["y"] + dec["h"] == vp["y"] + vp["h"]
    assert dec["h"] == max(DECISIONS_MIN_H, vp["h"] - HUD_GUTTER_MIN_H)
    assert regions["ticker"]["w"] == FULL_GUTTER_MIN_COLS


def test_frame_layout_hud_keeps_room_for_metrics():
    """Decisions-in-HUD must not clip METRICS (HUD_GUTTER_MIN_H=10 regression)."""
    regions = frame_layout(42, FULL_GUTTER_MIN_COLS + 2)
    hud = regions["gutter"]
    dec = regions["decisions"]
    assert hud["h"] == HUD_GUTTER_MIN_H == VIEWPORT_H - DECISIONS_MIN_H
    assert dec["h"] == DECISIONS_MIN_H
    # 5 ship cells @ 2 rows from content row 2 → row 12; METRICS needs header+6.
    assert hud["h"] - 2 >= 5 * 2 + 1 + 6


def test_frame_layout_left_priorities_absent_below_left_gutter_floor():
    """Right HUD alone (118) — no left PRIORITIES until LEFT_GUTTER_MIN_COLS."""
    regions = frame_layout(42, RIGHT_GUTTER_MIN_COLS + 2)
    assert regions["mode"] == "right_gutter"
    assert regions["gutter"] is not None
    assert regions["priorities"] is None
    regions_left = frame_layout(42, LEFT_GUTTER_MIN_COLS + 2)
    assert regions_left["priorities"] is not None
    assert regions_left["priorities"]["w"] == PRIORITIES_MIN_W
    assert regions_left["priorities"]["h"] == regions_left["viewport"]["h"]


# -- WO-FA5a: hops (a real trade-loop chain) vs steps (a learned macro) ----
#
# protocol.py's list_skills / chains.chain_as_library_row() share ONE wire
# field ("steps") for two different concepts: a discovered ProfitChain's
# sector-hop count, and a recorded/mined skill's macro action count.
# chain_hop_count_and_unit()/_chain_unit_for_source() are the one place
# that decides which word display text should use.


def test_chain_hop_count_and_unit_object_chain_is_always_hops():
    from twclient.chains import ProfitChain, TradeHop
    chain = ProfitChain(
        sectors=(1, 2, 1),
        hops=(TradeHop(1, 2, "A", 10, 1), TradeHop(2, 1, "B", 10, 1)),
        overall_profit=20, turns=2, cr_per_turn=10.0, cr_per_execution=20.0,
    )
    assert chain_hop_count_and_unit(chain) == (2, "hops")


def test_chain_hop_count_and_unit_recorded_or_mined_dict_is_steps():
    assert chain_hop_count_and_unit({"source": "recorded", "steps": 4}) == (4, "steps")
    assert chain_hop_count_and_unit({"source": "mined", "steps": 6}) == (6, "steps")


def test_chain_hop_count_and_unit_discovered_dict_is_hops():
    assert chain_hop_count_and_unit({"source": "discovered", "steps": 5}) == (5, "hops")


def test_chain_hop_count_and_unit_none_chain():
    assert chain_hop_count_and_unit(None) == (None, "hops")


def test_chain_hop_count_and_unit_presence_seed_from_sectors():
    """Presence-seed viz has sectors but historically omitted steps — GOALS
    must still count hops so it matches the Trade Loop bubble panel."""
    assert chain_hop_count_and_unit(
        {"sectors": (123, 753, 8293, 123), "source": "presence_seed"}
    ) == (3, "hops")
    assert chain_hop_count_and_unit(
        {"sectors": (10, 20, 30, 40), "source": "presence_seed"}
    ) == (3, "hops")
    # Explicit steps still wins when present.
    assert chain_hop_count_and_unit(
        {"sectors": (1, 2, 3), "source": "presence_seed", "steps": 2}
    ) == (2, "hops")


def test_compose_primary_goals_presence_seed_not_none_yet():
    lines = compose_primary_goals_lines(GoalsSnapshot(
        longest_chain_hops=3, longest_chain_unit="hops",
    ), width=36)
    assert any("Chain" in ln and "3 hops" in ln for ln in lines)
    assert not any("none yet" in ln for ln in lines)


def test_compose_primary_goals_lines_labels_steps_vs_hops():
    steps_lines = compose_primary_goals_lines(GoalsSnapshot(
        longest_chain_hops=4, longest_chain_unit="steps",
    ), width=30)
    assert any("4 steps" in ln for ln in steps_lines)
    hops_lines = compose_primary_goals_lines(GoalsSnapshot(
        longest_chain_hops=4, longest_chain_unit="hops",
    ), width=30)
    assert any("4 hops" in ln for ln in hops_lines)


def test_format_chain_summary_dict_branch_labels_steps_vs_hops():
    steps_lines = format_chain_summary(
        {"sectors": [1, 2, 1], "steps": 2, "source": "recorded"}, cols=40,
    )
    assert any("2 steps" in ln for ln in steps_lines)
    assert not any("hops" in ln for ln in steps_lines)
    hops_lines = format_chain_summary(
        {"sectors": [1, 2, 1], "steps": 2, "source": "discovered"}, cols=40,
    )
    assert any("2 hops" in ln for ln in hops_lines)


def test_format_chain_summary_non_numeric_sector_does_not_crash_the_membership_check():
    """Pixel-caught defect (pre-existing, in a function this WO touched):
    the path-building loop already tolerates a non-numeric sid
    (`str(sid)`, `continue`), but the later "here ★N" membership check
    used to re-parse the SAME sectors with a bare `int(s)` and no guard
    -- ValueError on a real terminal, crashing the whole spectate render.
    A valid `current_sector` alongside a non-numeric sid must render
    cleanly instead."""
    lines = format_chain_summary(
        {"sectors": [1, "warp-gate", 2, 1], "steps": 3, "source": "discovered"},
        current_sector=2,
        cols=40,
    )
    assert any("warp-gate" in ln for ln in lines)
    assert any("here ★2" in ln for ln in lines)

    # The object-chain branch takes a different code path but the same
    # membership check -- prove it doesn't crash there either.
    class _FakeChain:
        sectors = (1, "warp-gate", 2, 1)
        hops = ()
        overall_profit = None
        cr_per_turn = None

    obj_lines = format_chain_summary(_FakeChain(), current_sector=2, cols=40)
    assert any("here ★2" in ln for ln in obj_lines)


# -- WO-FA5a: DECISIONS pane rotation (explore/trace must not PERMANENTLY
# preempt GOALS+CHAIN) ------------------------------------------------------


def test_decisions_should_show_chain_dwell_window_and_wraps():
    assert decisions_should_show_chain(0.0) is True
    assert decisions_should_show_chain(CHAIN_PANEL_DWELL_S - 0.01) is True
    assert decisions_should_show_chain(CHAIN_PANEL_DWELL_S) is False
    assert decisions_should_show_chain(CHAIN_PANEL_ROTATION_PERIOD_S - 0.01) is False
    # Wraps: the SAME phase repeats every ROTATION_PERIOD_S, forever --
    # explore/trace can never permanently keep GOALS+CHAIN off-screen.
    assert decisions_should_show_chain(CHAIN_PANEL_ROTATION_PERIOD_S) is True
    assert decisions_should_show_chain(3 * CHAIN_PANEL_ROTATION_PERIOD_S + 1.0) is True


# -- WO-FA5a: DECISIONS/GOALS+CHAIN geometry floor --------------------------


def test_frame_layout_decisions_absent_below_its_height_floor():
    """Just enough leftover for a bare LOG box (LOG_BOX_MIN_H) but short of
    DECISIONS_MIN_H -- LOG claims the whole band; a squeezed 1-2-content-row
    DECISIONS pane (the "collapsed to nothing" defect) never appears.
    inner leftover == LOG_BOX_MIN_H == 3 (mirrors
    test_frame_layout_ticker_still_appears_with_enough_leftover_for_both's
    same VIEWPORT_H + 6 + 2 size, which never asserted on `decisions`)."""
    lines = VIEWPORT_H + 6 + 2
    regions = frame_layout(lines, MINIMAL_HEADER_MIN_COLS + 2)
    assert regions["decisions"] is None
    assert regions["ticker"] is not None
    assert regions["ticker"]["w"] == MINIMAL_HEADER_MIN_COLS  # full leftover width, no split


def test_frame_layout_decisions_present_at_its_height_floor():
    # inner leftover == DECISIONS_MIN_H == 5 (two rows more than the case above).
    lines = VIEWPORT_H + 8 + 2
    regions = frame_layout(lines, MINIMAL_HEADER_MIN_COLS + 2)
    assert regions["decisions"] is not None
    assert regions["decisions"]["h"] == DECISIONS_MIN_H
    assert regions["ticker"] is not None
    # Leftover == DECISIONS_MIN_H is short of CHAIN_VIZ_H + LOG_BOX_MIN_H
    assert regions["chain"] is None


def test_frame_layout_band_grows_toward_double_height():
    """WO-TUI-CHAIN-BOX: band_h targets min(10, leftover) so LOG/DECISIONS
    content rows roughly double vs the old min(5, leftover) cap."""
    # Generous leftover well above BAND_H_MAX.
    lines = VIEWPORT_H + 20 + 2
    regions = frame_layout(lines, FULL_GUTTER_MIN_COLS + 2)
    assert regions["ticker"]["h"] == 10
    assert regions["decisions"]["h"] == max(DECISIONS_MIN_H, VIEWPORT_H - HUD_GUTTER_MIN_H)
    assert regions["decisions"]["w"] == HUD_GUTTER_W
    assert regions["chain"] is not None
    assert regions["chain"]["h"] == CHAIN_VIZ_H
    assert regions["chain"]["y"] == regions["viewport"]["y"] + regions["viewport"]["h"]
    assert regions["chain"]["x"] == regions["viewport"]["x"]
    assert regions["chain"]["w"] == regions["viewport"]["w"]
    # LOG spans full band; DECISIONS is in the right HUD column.
    assert regions["ticker"]["w"] == FULL_GUTTER_MIN_COLS
    assert (
        regions["decisions"]["y"] + regions["decisions"]["h"]
        == regions["viewport"]["y"] + regions["viewport"]["h"]
    )
    assert regions["priorities"] is not None
    assert regions["priorities"]["h"] == regions["viewport"]["h"]
    assert regions["priorities"]["x"] < regions["viewport"]["x"]


def test_render_plain_includes_phase2_sections():
    text = render_plain({
        "main": ["hi"],
        "sidebar": ["Sector: 1"],
        "ticker": [],
        "status": "STATUS ok",
        "metrics": [{"label": "STATIONS", "value": "3"}],
        "autonomy": {
            "pct_display": "75%",
            "trainer": 30,
            "ai": 10,
            "human": 2,
        },
        "decisions": format_autopilot_trace_lines(PROVISIONAL_AUTOPILOT_TRACE, cols=40),
        "priorities": [
            "AUTO 75%", "App 30 / AI 10 · Hum 2",
            "— GOALS —", "· Gal 9 known",
            "— FOCUS —", "1 Trade chain 550", "2 Upgrade 200",
        ],
    })
    assert "METRICS" in text and "STATIONS" in text
    assert "AUTONOMY" in text and "75%" in text
    assert "App 30" in text and "AI 10" in text and "Hum 2" in text
    assert "DECISIONS" in text and "run_chain" in text and "550" in text
    assert "PRIORITIES" in text and "— GOALS —" in text and "Trade chain" in text
    assert "GOALS / CHAIN" not in text
    # empty autonomy still renders cleanly
    empty = render_plain({
        "main": [], "sidebar": [], "ticker": [], "status": "ok",
        "autonomy": compute_autonomy_ratio([]),
    })
    assert "AUTONOMY" in empty and "—" in empty
    assert "App 0 / AI 0 · Hum 0" in empty


def test_compose_decisions_placeholder_is_nonempty_honest_idle():
    lines = compose_decisions_placeholder()
    assert len(lines) >= 1
    joined = " ".join(lines).lower()
    assert "tw-13" not in joined
    assert "trace" in joined or "autopilot" in joined or "explore" in joined


# -- tick_down_timer / format_idle_age / status_semantic --------------------


def test_tick_down_timer_counts_down_and_floors_at_zero():
    assert tick_down_timer("00:00:10", 4.0) == "00:00:06"
    assert tick_down_timer("00:00:10", 999.0) == "00:00:00"


def test_tick_down_timer_passes_through_unparseable_input():
    assert tick_down_timer("garbage", 4.0) == "garbage"
    assert tick_down_timer(None, 4.0) is None


def test_format_idle_age_seconds_then_minutes():
    assert format_idle_age(4.2) == "4.2s"
    assert format_idle_age(65) == "1m05s"


def test_status_semantic_disconnected_is_danger():
    assert status_semantic(False, None) == "danger"
    assert status_semantic(False, 0.1) == "danger"


def test_status_semantic_connected_and_fresh_is_ok():
    assert status_semantic(True, 0.5) == "ok"
    assert status_semantic(True, None) == "ok"


def test_status_semantic_connected_but_stale_rx_is_warn():
    assert status_semantic(True, 30.0) == "warn"


# -- is_recent() / render_bar_meter() / render_sparkline() / gauge_semantic() --


def test_is_recent_true_within_window_false_after_and_for_none():
    assert is_recent(10.0, now=10.5, duration=1.0) is True
    assert is_recent(10.0, now=11.5, duration=1.0) is False
    assert is_recent(None, now=11.5, duration=1.0) is False


def test_render_bar_meter_scales_and_clamps():
    assert render_bar_meter(0.0, 10) == "[" + "░" * 10 + "]"
    assert render_bar_meter(1.0, 10) == "[" + "█" * 10 + "]"
    assert render_bar_meter(0.5, 10) == "[" + "█" * 5 + "░" * 5 + "]"
    assert render_bar_meter(-1.0, 10) == "[" + "░" * 10 + "]"  # clamped, not garbled
    assert render_bar_meter(2.0, 10) == "[" + "█" * 10 + "]"


def test_render_bar_meter_accepts_ascii_fallback_chars():
    assert render_bar_meter(0.5, 4, full_char="#", empty_char=".") == "[##..]"


def test_render_sparkline_empty_series_is_empty_string():
    assert render_sparkline([]) == ""


def test_render_sparkline_flat_series_uses_middle_glyph():
    chars = "▁▂▃▄▅▆▇█"
    flat = render_sparkline([100, 100, 100], chars=chars)
    assert flat == chars[len(chars) // 2] * 3


def test_render_sparkline_scales_to_series_min_max():
    chars = ".-=#"
    line = render_sparkline([0, 50, 100], chars=chars)
    assert line[0] == "."   # the series minimum -> the ramp's lowest glyph
    assert line[-1] == "#"  # the series maximum -> the ramp's highest glyph
    assert len(line) == 3


def test_gauge_semantic_thresholds():
    assert gauge_semantic(1.0) == "ok"
    assert gauge_semantic(0.5) == "ok"
    assert gauge_semantic(0.3) == "warn"
    assert gauge_semantic(0.2) == "warn"
    assert gauge_semantic(0.1) == "danger"
    assert gauge_semantic(0.0) == "danger"


# -- update_tracked_stats()'s Phase 3/4 "something just happened" bookkeeping --


def test_update_tracked_stats_sets_ticker_flash_on_any_real_event():
    tracked = update_tracked_stats({}, {"state": {}}, now=5.0)
    assert tracked["_ticker_flash_ts"] == 5.0


def test_update_tracked_stats_does_not_set_ticker_flash_for_a_none_event():
    tracked = update_tracked_stats({}, None, now=5.0)
    assert "_ticker_flash_ts" not in tracked


def test_update_tracked_stats_pulses_on_classification_change_only():
    tracked = update_tracked_stats({}, {"classification": "main_command", "state": {}}, now=1.0)
    assert "_classification_pulse_ts" not in tracked  # first sighting -- nothing "changed" yet

    tracked = update_tracked_stats(tracked, {"classification": "main_command", "state": {}}, now=2.0)
    assert "_classification_pulse_ts" not in tracked  # same classification -- no pulse

    tracked = update_tracked_stats(tracked, {"classification": "port_menu", "state": {}}, now=3.0)
    assert tracked["_classification_pulse_ts"] == 3.0


def test_update_tracked_stats_flashes_and_tweens_on_a_real_credits_change():
    tracked = update_tracked_stats({}, {"state": {"credits": 100000}}, now=1.0)
    assert "_credits_flash" not in tracked  # first sighting -- no prior value to delta against
    assert "_credits_tween" not in tracked

    tracked = update_tracked_stats(tracked, {"state": {"credits": 100230}}, now=2.0)
    assert tracked["_credits_flash"] == (230, 2.0)
    assert tracked["_credits_tween"] == (100000, 100230, 2.0)


def test_update_tracked_stats_does_not_flash_when_credits_is_unchanged():
    tracked = update_tracked_stats({}, {"state": {"credits": 100000}}, now=1.0)
    tracked = update_tracked_stats(tracked, {"state": {"credits": 100000}}, now=2.0)
    assert "_credits_flash" not in tracked


def test_update_tracked_stats_builds_a_bounded_credit_series():
    tracked = {}
    for i in range(30):
        tracked = update_tracked_stats(tracked, {"state": {"credits": 100000 + i}}, now=float(i))
    assert len(tracked["_credit_series"]) == 20  # CREDIT_SPARK_WIDTH
    assert tracked["_credit_series"][-1] == 100029  # newest sample kept
    assert tracked["_credit_series"][0] == 100010   # oldest beyond the window dropped


def test_update_tracked_stats_turns_max_tracks_the_session_high():
    tracked = update_tracked_stats({}, {"state": {"turns_left": 1000}}, now=1.0)
    assert tracked["_turns_max"] == 1000
    tracked = update_tracked_stats(tracked, {"state": {"turns_left": 800}}, now=2.0)
    assert tracked["_turns_max"] == 1000  # spent turns don't lower the "full tank" mark
    tracked = update_tracked_stats(tracked, {"state": {"turns_left": 1200}}, now=3.0)
    assert tracked["_turns_max"] == 1200  # a real increase raises it


# -- compose_hud_cells()'s Phase 3/4 per-field extras -----------------------


def test_credits_cell_flashes_gain_with_a_chip_and_tweens_toward_the_target():
    tracked = update_tracked_stats({}, {"state": {"credits": 100000}}, now=0.0)
    tracked = update_tracked_stats(tracked, {"state": {"credits": 100230}}, now=10.0)

    # Mid-tween (well inside CREDIT_TWEEN_DURATION_S): value is BETWEEN
    # old and new, not yet the final number.
    mid_cells = compose_hud_cells(tracked, now=10.0 + CREDIT_TWEEN_DURATION_S / 2)
    credits_cell = [c for c in mid_cells if c["label"] == "CREDITS"][0]
    mid_value = int(credits_cell["value"].replace(",", ""))
    assert 100000 < mid_value < 100230

    # Tween finished, flash still fresh: final value + gain tone + chip.
    settled_cells = compose_hud_cells(tracked, now=10.0 + CREDIT_TWEEN_DURATION_S + 0.05)
    credits_cell = [c for c in settled_cells if c["label"] == "CREDITS"][0]
    assert credits_cell["value"] == "100,230"
    assert credits_cell["tone"] == "gain"
    assert "230" in credits_cell["chip"]

    # Flash long expired: back to neutral, no chip.
    late_cells = compose_hud_cells(tracked, now=10.0 + CREDIT_FLASH_DURATION_S + 1.0)
    credits_cell = [c for c in late_cells if c["label"] == "CREDITS"][0]
    assert credits_cell["tone"] is None
    assert credits_cell["chip"] == ""


def test_credits_cell_flashes_loss_on_a_decrease():
    tracked = update_tracked_stats({}, {"state": {"credits": 100000}}, now=0.0)
    tracked = update_tracked_stats(tracked, {"state": {"credits": 99500}}, now=1.0)
    cells = compose_hud_cells(tracked, now=1.1)
    credits_cell = [c for c in cells if c["label"] == "CREDITS"][0]
    assert credits_cell["tone"] == "loss"
    assert "-500" in credits_cell["chip"]


def test_credits_cell_no_flash_or_chip_on_first_sighting():
    tracked = update_tracked_stats({}, {"state": {"credits": 100000}}, now=0.0)
    cells = compose_hud_cells(tracked, now=0.1)
    credits_cell = [c for c in cells if c["label"] == "CREDITS"][0]
    assert credits_cell["tone"] is None
    assert credits_cell["chip"] == ""


def test_credits_cell_carries_a_sparkline_once_there_is_a_series():
    tracked = update_tracked_stats({}, {"state": {"credits": 100000}}, now=0.0)
    tracked = update_tracked_stats(tracked, {"state": {"credits": 100500}}, now=1.0)
    cells = compose_hud_cells(tracked, now=1.0)
    credits_cell = [c for c in cells if c["label"] == "CREDITS"][0]
    assert len(credits_cell["spark"]) == 2


def test_turns_cell_shows_a_gauge_and_tone_once_a_max_is_known():
    tracked = update_tracked_stats({}, {"state": {"turns_left": 1000}}, now=0.0)
    tracked = update_tracked_stats(tracked, {"state": {"turns_left": 100}}, now=1.0)  # 10% left
    cells = compose_hud_cells(tracked, now=1.0)
    turns_cell = [c for c in cells if c["label"] == "TURNS"][0]
    assert turns_cell["value"] == "100"  # plain value untouched by the gauge suffix
    assert turns_cell["gauge"].startswith("[") and turns_cell["gauge"].endswith("]")
    assert turns_cell["tone"] == "danger"  # 10% -> below the danger threshold


def test_turns_cell_legacy_timer_entry_renders_blank_not_hhmmss():
    """Pre-count-only tracked shape must not paint HH:MM:SS into TURNS."""
    tracked = {"turns": (("timer", "00:00:30"), 0.0)}
    cells = compose_hud_cells(tracked, now=0.0)
    turns_cell = [c for c in cells if c["label"] == "TURNS"][0]
    assert turns_cell["value"] == "-"
    assert turns_cell["gauge"] == ""
    assert turns_cell["tone"] is None


def test_non_credits_non_turns_cells_carry_neutral_extras():
    tracked = update_tracked_stats({}, {"state": {"sector": 1027, "cargo_holds_empty": 50}}, now=0.0)
    cells = compose_hud_cells(tracked, now=0.0)
    for label in ("SECTOR", "CARGO", "PROFIT"):
        cell = [c for c in cells if c["label"] == label][0]
        assert cell["tone"] is None
        assert cell["chip"] == ""


# -- compose_port_panel() ----------------------------------------------------


def test_compose_port_panel_empty_when_no_port_in_state():
    assert compose_port_panel({"state": {}}) == []
    assert compose_port_panel(None) == []


def test_compose_port_panel_renders_one_row_per_commodity_with_bar_and_tone():
    event = {
        "state": {
            "port": {
                "commodities": [
                    {"name": "Fuel Ore", "status": "buying", "pct": 100, "amount": 2650},
                    {"name": "Organics", "status": "selling", "pct": 40, "amount": 10},
                ]
            }
        }
    }
    rows = compose_port_panel(event)
    assert len(rows) == 2
    assert rows[0] == {"name": "Fuel Ore", "pct": 100, "bar": "[" + "█" * 10 + "]", "tone": "ok"}
    assert rows[1]["tone"] == "info"  # "selling" is not "buying"
    assert rows[1]["bar"] == "[" + "█" * 4 + "░" * 6 + "]"  # 40%


def test_compose_port_panel_does_not_persist_across_events():
    """Deliberate design choice (see compose_port_panel's docstring): a
    port's numbers are only shown while CURRENTLY at that port -- calling
    it against a later, port-less event must return nothing, not stale
    data from the earlier one."""
    at_port = {"state": {"port": {"commodities": [{"name": "Fuel Ore", "status": "buying", "pct": 100}]}}}
    assert compose_port_panel(at_port) != []
    left_port = {"state": {"sector": 1027}}
    assert compose_port_panel(left_port) == []


# -- Trainer Control Panel: mode badge / TX readout / control strip --------


def test_format_mode_badge_known_modes():
    label, tone = format_mode_badge("ai_pilot")
    assert label == "AI-PILOT" and tone == "info"
    label, tone = format_mode_badge("auto_loop")
    assert tone == "ok"
    label, tone = format_mode_badge("human")
    assert tone == "warn"
    label, tone = format_mode_badge("spectate")
    assert tone == "muted"


def test_format_mode_badge_unknown_mode_degrades_gracefully():
    label, tone = format_mode_badge("something_new")
    assert label == "SOMETHING_NEW"
    assert tone is None


def test_format_mode_badge_handles_falsy_mode():
    label, tone = format_mode_badge(None)
    assert label == "?"


def test_format_tx_readout_shows_dash_when_nothing_sent_yet():
    assert format_tx_readout(None) == "→ -"
    assert format_tx_readout("") == "→ -"


def test_format_tx_readout_shows_the_sent_text():
    assert format_tx_readout("158") == "→ 158"


def test_format_play_progress_or_hints_shows_hints_when_nothing_running():
    assert format_play_progress_or_hints(None) == CONTROL_HINTS
    assert format_play_progress_or_hints({"running": False}) == CONTROL_HINTS


def test_format_play_progress_or_hints_shows_a_live_bar_while_running():
    play = {"running": True, "paused": False, "name": "demo-loop", "cycle": 2, "cycles_total": 5}
    text = format_play_progress_or_hints(play)
    assert "Playing demo-loop" in text
    assert "2/5" in text
    assert "[" in text and "]" in text


def test_format_play_progress_or_hints_shows_paused_state():
    play = {"running": True, "paused": True, "name": "demo-loop", "cycle": 2, "cycles_total": 5}
    assert "PAUSED demo-loop" in format_play_progress_or_hints(play)


def test_format_play_progress_or_hints_guards_zero_cycles_total():
    play = {"running": True, "paused": False, "name": "demo-loop", "cycle": 0, "cycles_total": 0}
    text = format_play_progress_or_hints(play)  # must not raise (division by zero)
    assert "0/0" in text


def test_compose_control_strip_assembles_all_segments():
    strip = compose_control_strip("auto_loop", "158", {"running": True, "paused": False, "name": "d", "cycle": 1, "cycles_total": 3})
    assert strip["badge"] == " AUTO-LOOP "
    assert strip["badge_tone"] == "ok"
    assert strip["tx"] == "→ 158"
    assert "Playing d" in strip["right"]


def test_compose_control_strip_shows_hints_when_idle():
    strip = compose_control_strip("ai_pilot", None, None)
    assert strip["right"] == CONTROL_HINTS
    assert strip["tx"] == "→ -"


def test_control_hints_points_to_tw_attach_for_human_takeover():
    """Human-reported discoverability gap: `M` only cycles ai_pilot<->
    spectate (by design -- `tw attach` is the only door into
    MODE_HUMAN); the legend must say so via the real `A` keybinding
    (WO-FA5c), and the addition must not blow the "minimal" tier's
    control-strip width budget (82 inner cols)."""
    assert "A)ttach" in CONTROL_HINTS
    # Every pre-existing token must still be intact -- an addition that
    # SILENTLY replaced/shortened one would be its own regression.
    for token in ("M)ode", "L)chains", "E)xplore", "Spc pause", "X stop", "P panic"):
        assert token in CONTROL_HINTS
    # 82 == MINIMAL_HEADER_MIN_COLS -- the narrowest bordered-viewport tier
    # the control strip still spans at full inner width; the shortest
    # realistic badge+tx (ai_pilot/spectate/auto_loop, not the long
    # MANUAL badge -- see the pty test's docstring) leaves ~14 cols of
    # left margin before the right-aligned hints text starts.
    assert len(CONTROL_HINTS) <= 82 - 14


# -- Trainer Control Panel: Trade Loop Chains overlay (TW-07) ---------------


def test_format_loops_library_row_mined_shows_three_metrics():
    loop = {
        "name": "mined-loop", "source": "mined",
        "profit_per_turn": 12.5, "profit_per_action": 40.0,
        "steps": 3, "draft": True,
    }
    row = format_loops_library_row(loop, selected=False, cols=100)
    assert "mined-loop" in row
    assert "+12.5/t" in row
    assert "+40" in row
    assert "DRAFT" in row
    # WO-FA5a: a mined SKILL's "steps" is a macro action count, not a
    # trade-loop hop count -- must never be labeled "hops".
    assert "3 steps" in row
    assert "hops" not in row


def test_format_loops_library_row_recorded_shows_overall_and_exec():
    loop = {"name": "recorded-loop", "source": "recorded", "demo_profit": 230, "steps": 5, "draft": False}
    row = format_loops_library_row(loop, selected=False, cols=100)
    assert "+230" in row
    assert "5 steps" in row
    assert "hops" not in row
    assert "DRAFT" not in row


def test_format_loops_library_row_no_profit_data_shows_dash():
    loop = {"name": "unknown-loop", "source": "recorded", "steps": 1, "draft": False}
    row = format_loops_library_row(loop, selected=False, cols=100)
    assert "1 steps" in row
    assert row.count("-") >= 1


def test_format_loops_library_row_discovered_shows_hops():
    """A genuine discovered trade-loop chain (chains.chain_as_library_row's
    "discovered" tag) really does count sector hops -- the one `source`
    that keeps the old "hops" wording."""
    loop = {"name": "1→2→3", "source": "discovered", "demo_profit": 30, "steps": 3, "draft": False}
    row = format_loops_library_row(loop, selected=False, cols=100)
    assert "3 hops" in row
    assert "steps" not in row


def test_format_loops_library_row_selected_gets_a_marker():
    loop = {"name": "x", "source": "recorded", "demo_profit": 1, "steps": 1, "draft": False}
    selected_row = format_loops_library_row(loop, selected=True, cols=80)
    unselected_row = format_loops_library_row(loop, selected=False, cols=80)
    assert selected_row.startswith("▸")
    assert not unselected_row.startswith("▸")


def test_format_loops_library_row_longest_gets_star():
    loop = {"name": "long", "source": "recorded", "demo_profit": 1, "steps": 9, "draft": False}
    row = format_loops_library_row(loop, selected=False, cols=80, longest=True)
    assert row.startswith("★")


def test_format_loops_library_row_truncates_to_cols():
    loop = {"name": "a-very-long-loop-name-that-would-overflow", "source": "recorded", "demo_profit": 1, "steps": 1, "draft": False}
    row = format_loops_library_row(loop, selected=False, cols=20)
    assert len(row) <= 19


def test_format_loops_library_header_shows_count_and_tw07_title():
    header = format_loops_library_header(3)
    assert "TRADE LOOP CHAINS" in header
    assert "3 chain(s)" in header
    assert "Enter arms" in header
    assert "Enter run" not in header


def test_sort_trade_loop_chains_profit_desc():
    loops = [
        {"name": "low", "source": "recorded", "demo_profit": 10, "steps": 2},
        {"name": "high", "source": "recorded", "demo_profit": 500, "steps": 1},
        {"name": "mid", "source": "mined", "profit_per_turn": 50.0, "steps": 4},
    ]
    sorted_loops = sort_trade_loop_chains(loops)
    assert [loop["name"] for loop in sorted_loops] == ["high", "mid", "low"]


def test_longest_chain_steps_and_banner():
    loops = [
        {"name": "short", "source": "recorded", "steps": 2, "demo_profit": 100},
        {"name": "long", "source": "recorded", "steps": 7, "demo_profit": 1},
    ]
    assert longest_chain_steps(loops) == 7
    banner = format_longest_chain_banner(loops[1], cols=60)
    assert "LONGEST CHAIN" in banner
    assert "long" in banner
    # WO-FA5a: a recorded skill's "steps" is a macro action count, not a
    # trade-loop hop count -- must never be labeled "hops".
    assert "7 steps" in banner
    assert "hops" not in banner


def test_longest_chain_banner_discovered_shows_hops():
    loop = {"name": "1→2→3", "source": "discovered", "steps": 3, "demo_profit": 30}
    banner = format_longest_chain_banner(loop, cols=60)
    assert "3 hops" in banner
    assert "steps" not in banner


# -- WO-TUI-CHAIN-BUBBLES: pure ASCII bubble-chain --------------------------


def test_compose_chain_bubbles_empty_is_quiet_placeholder():
    lines = compose_chain_bubbles(None, width=40)
    assert len(lines) == CHAIN_VIZ_H
    joined = "\n".join(lines)
    assert "no trade loop yet" in joined
    assert "╭" not in joined


def test_compose_chain_bubbles_two_hop_accept_contract():
    """Hub Accept visual contract (2-hop, ship at 100, classes known)."""
    chain = {"sectors": (100, 200, 100)}  # closed cycle — drop repeat
    assert chain_bubble_sectors(chain) == [100, 200]
    lines = compose_chain_bubbles(
        chain,
        current_sector=100,
        port_classes={100: "BSB", 200: "SSB"},
        width=82,
    )
    assert len(lines) == CHAIN_VIZ_H
    body = "\n".join(lines)
    assert "100" in body and "200" in body
    assert "BSB" in body and "SSB" in body
    assert "═════" in body
    assert "★" in body
    # ★ under the active (100) bubble — left of the 200 sector id on mid row
    mid = next(ln for ln in lines if "100" in ln and "200" in ln)
    star_row = lines[-1]
    assert star_row.index("★") < mid.index("200")


def test_compose_chain_bubbles_grows_with_hop_count():
    two = "".join(compose_chain_bubbles({"sectors": (1, 2)}, width=82))
    three = "".join(compose_chain_bubbles({"sectors": (1, 2, 3)}, width=82))
    assert two.count("═════") == 1
    assert three.count("═════") == 2


def test_longest_contiguous_port_run_splits_at_non_port():
    from twclient.spectate_layout import longest_contiguous_port_run

    # Non-port breaks — do not bridge 10↔20 across 50.
    assert longest_contiguous_port_run([10, 50, 20, 50], {10, 20}) == [10]
    assert longest_contiguous_port_run([10, 20], None) == [10, 20]
    # A(port)-B(no)-C(port)-D(port) → longest run is C,D (length beats prefer_sector).
    assert longest_contiguous_port_run([1, 2, 3, 4], {1, 3, 4}) == [3, 4]
    assert longest_contiguous_port_run(
        [1, 2, 3, 4], {1, 3, 4}, prefer_sector=1,
    ) == [3, 4]
    assert longest_contiguous_port_run(
        [1, 2, 3], {1, 3}, prefer_sector=1,
    ) == [1]
    # Four contiguous ports → length 4.
    assert longest_contiguous_port_run([10, 20, 30, 40], {10, 20, 30, 40}) == [
        10, 20, 30, 40,
    ]


def test_compose_chain_bubbles_contiguous_port_run_only():
    """Non-port breaks chain; bubbles never bridge across empty warps."""
    from twclient.spectate_layout import compose_chain_bubbles, chain_bubble_sectors

    raw = {"sectors": (1, 2, 3, 4), "source": "presence_seed"}
    assert chain_bubble_sectors(raw) == [1, 2, 3, 4]
    joined = "\n".join(
        compose_chain_bubbles(
            raw,
            port_classes={1: "BSB", 3: "SBB", 4: "BBB"},
            known_ports={1, 3, 4},
            width=82,
        )
    )
    assert "3" in joined and "4" in joined
    assert "1" not in joined
    assert "2" not in joined


def test_compose_chain_bubbles_unknown_class_is_question_mark():
    lines = compose_chain_bubbles({"sectors": (7, 8)}, port_classes={7: "BSB"}, width=40)
    joined = "\n".join(lines)
    assert "BSB" in joined
    assert "?" in joined
