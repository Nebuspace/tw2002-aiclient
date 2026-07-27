"""pyte render + crop correctness tests — no network involved."""

from tw2002_aiclient.session.terminal import TerminalScreen


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
    assert cropped == ["hello"]


def test_crop_keeps_leading_blank_rows():
    t = TerminalScreen()
    t.feed(b"\r\n\r\n\r\nhi\r\n")
    cropped = t.render_cropped()
    assert len(cropped) == 4
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
    t = TerminalScreen()
    # 0xC9 0xCD 0xBB = CP437 double-line box-drawing: ╔ ═ ╗
    t.feed(bytes([0xC9, 0xCD, 0xBB]))
    cropped = t.render_cropped()
    assert cropped == ["╔═╗"]


def test_ansi_color_sequences_still_work_alongside_cp437_bytes():
    t = TerminalScreen()
    t.feed(b"\x1b[31m" + bytes([0xDB]) + b"\x1b[0mhi")
    cropped = t.render_cropped()
    assert cropped == ["█hi"]


def test_color_map_empty_screen():
    t = TerminalScreen()
    assert t.color_map() == []


def test_color_map_single_run_for_uncolored_text():
    t = TerminalScreen()
    t.feed(b"hi")
    color = t.color_map()
    assert len(color) == 1
    assert color[0] == [{"start": 0, "end": 2, "fg": "default", "bg": "default", "bold": False}]


def test_color_map_splits_runs_at_attribute_changes():
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
    t.feed(b"\x1b[1;42mgo\x1b[0m")
    color = t.color_map()
    assert color[0] == [{"start": 0, "end": 2, "fg": "default", "bg": "green", "bold": True}]


def test_color_map_aligned_with_render_cropped_bounding_box():
    t = TerminalScreen()
    t.feed(b"\r\n\x1b[31mshort\x1b[0m\r\nmuch longer line\r\n")
    cropped = t.render_cropped()
    color = t.color_map()
    assert len(color) == len(cropped)
    for row_text, runs in zip(cropped, color):
        assert runs[-1]["end"] == len(row_text)
