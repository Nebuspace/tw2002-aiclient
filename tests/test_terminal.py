"""pyte render + crop correctness tests — no network involved."""

from twclient.terminal import GLYPHS_ASCII, GLYPHS_UNICODE, TerminalScreen, glyph_set, init_locale


def test_raw_display_is_80x25():
    t = TerminalScreen()
    assert len(t.raw_display()) == 25
    assert all(len(row) == 80 for row in t.raw_display())


def test_empty_screen_crops_to_nothing():
    t = TerminalScreen()
    assert t.render_cropped() == []


def test_crop_trims_trailing_blank_rows_and_columns():
    t = TerminalScreen()
    t.feed(b"hello\r\n")
    cropped = t.render_cropped()
    # Only one row of content; cropped to that row's content width.
    assert cropped == ["hello"]


def test_crop_keeps_leading_blank_rows():
    t = TerminalScreen()
    # Move to row 3 (0-indexed) via a few newlines, then write.
    t.feed(b"\r\n\r\n\r\nhi\r\n")
    cropped = t.render_cropped()
    assert len(cropped) == 4
    # Leading blank rows are kept (not dropped) but padded to the shared
    # bounding-box width ("hi" = 2 cols wide), so they're spaces, not "".
    assert cropped[0] == "  "
    assert cropped[1] == "  "
    assert cropped[2] == "  "
    assert cropped[3] == "hi"


def test_crop_width_is_max_content_width_across_rows():
    t = TerminalScreen()
    t.feed(b"short\r\nmuch longer line\r\n")
    cropped = t.render_cropped()
    assert cropped[0] == "short" + " " * (len("much longer line") - len("short"))
    assert cropped[1] == "much longer line"


def test_cursor_reports_position():
    t = TerminalScreen()
    t.feed(b"hi")
    c = t.cursor()
    assert c == {"x": 2, "y": 0}


def test_cp437_box_drawing_bytes_decode_to_unicode():
    """TWGS is a DOS BBS door: high-byte art bytes are CP437, not UTF-8.
    Feeding them raw (pyte.ByteStream's UTF-8 default) renders mojibode;
    decoding as CP437 first (see TerminalScreen.feed) must render the
    correct Unicode box-drawing glyphs instead. Confirmed live against
    twgs.test.example's ANSI-art menus."""
    t = TerminalScreen()
    # 0xC9 0xCD 0xBB = CP437 double-line box-drawing: ╔ ═ ╗
    t.feed(bytes([0xC9, 0xCD, 0xBB]))
    cropped = t.render_cropped()
    assert cropped == ["╔═╗"]  # ╔═╗


def test_ansi_color_sequences_still_work_alongside_cp437_bytes():
    """ANSI/VT escape bytes are all <0x80 and decode identically under
    cp437 and ASCII -- the CP437 switch must not break color/cursor
    control sequences interleaved with high-byte art."""
    t = TerminalScreen()
    t.feed(b"\x1b[31m" + bytes([0xDB]) + b"\x1b[0mhi")  # red FG, full block, reset, "hi"
    cropped = t.render_cropped()
    assert cropped == ["█hi"]  # █hi


def test_color_map_empty_screen():
    t = TerminalScreen()
    assert t.color_map() == []


def test_color_map_single_run_for_uncolored_text():
    t = TerminalScreen()
    t.feed(b"hi")
    color = t.color_map()
    assert len(color) == 1  # one row
    assert color[0] == [{"start": 0, "end": 2, "fg": "default", "bg": "default", "bold": False}]


def test_color_map_splits_runs_at_attribute_changes():
    """SGR 31 (red fg) applied to one word, reset, then plain text --
    color_map() must report three runs (red / reset boundary / plain), not
    one flat run for the whole line."""
    t = TerminalScreen()
    t.feed(b"\x1b[31mRED\x1b[0m ok")
    color = t.color_map()
    assert len(color) == 1
    runs = color[0]
    assert runs[0] == {"start": 0, "end": 3, "fg": "red", "bg": "default", "bold": False}
    assert runs[1]["start"] == 3
    assert runs[1]["fg"] == "default"
    assert runs[-1]["end"] == len("RED ok")


def test_color_map_captures_bold_and_background():
    t = TerminalScreen()
    t.feed(b"\x1b[1;42mgo\x1b[0m")  # bold, green background
    color = t.color_map()
    assert color[0] == [{"start": 0, "end": 2, "fg": "default", "bg": "green", "bold": True}]


def test_color_map_aligned_with_render_cropped_bounding_box():
    """The color map must describe the EXACT same rows/columns as
    render_cropped() -- a spectator zips them together by row index, and
    any drift would color the wrong cells."""
    t = TerminalScreen()
    t.feed(b"\r\n\x1b[31mshort\x1b[0m\r\nmuch longer line\r\n")
    cropped = t.render_cropped()
    color = t.color_map()
    assert len(color) == len(cropped)
    # every row's runs collectively span the exact same width as the
    # cropped text row -- both are cropped to the same bounding box.
    for row_text, runs in zip(cropped, color):
        assert runs[-1]["end"] == len(row_text)


# -- glyph_set() / init_locale() -- chrome capability (TUI-POLISH-PLAN.md
# Phase 0/1/2: viewport/HUD borders, liveness spinner/heartbeat) ----------


def test_glyph_set_selects_unicode_or_ascii_table():
    assert glyph_set(True) is GLYPHS_UNICODE
    assert glyph_set(False) is GLYPHS_ASCII


def test_glyph_tables_expose_the_same_keys():
    """Every drawing helper indexes both tables by the same key set --
    a table missing a key the other has would only surface as a KeyError
    under whichever locale wasn't tested."""
    assert set(GLYPHS_UNICODE.keys()) == set(GLYPHS_ASCII.keys())


def test_glyph_tables_have_a_distinct_viewport_and_hud_border_weight():
    """Weight hierarchy (Phase 1): double-line viewport border, thin
    rounded HUD border -- the two must not be the same glyphs."""
    assert GLYPHS_UNICODE["viewport_tl"] != GLYPHS_UNICODE["hud_tl"]
    assert GLYPHS_UNICODE["viewport_h"] != GLYPHS_UNICODE["hud_h"]


def test_glyph_tables_spinner_and_heartbeat_are_nonempty_sequences():
    for glyphs in (GLYPHS_UNICODE, GLYPHS_ASCII):
        assert len(glyphs["spinner"]) >= 2
        assert len(glyphs["heartbeat"]) >= 2


def test_ascii_glyph_table_is_pure_ascii():
    """The whole point of the fallback table -- every glyph in it must be
    safely renderable on a non-UTF-8 terminal."""
    for value in GLYPHS_ASCII.values():
        chars = value if isinstance(value, tuple) else (value,)
        for ch in chars:
            ch.encode("ascii")  # raises UnicodeEncodeError if not pure ASCII


def test_init_locale_returns_a_bool_without_raising():
    # Real side effect (mutates the process locale) -- can't assert a
    # specific value portably across environments, only that it runs
    # clean and reports a real capability verdict.
    assert isinstance(init_locale(), bool)
