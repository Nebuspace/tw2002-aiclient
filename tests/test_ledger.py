"""Trace-Ledger tests (DESIGN-v2 §3 v2.1 item 11a, C1) -- no network,
tmp_path only, never touches the real state/ directory."""

import json

from twclient import ledger


def test_snapshot_state_merges_state_parser_plus_local_cargo_extraction():
    text = "Sector : 1234\nYou have 100,000 credits and 50 empty cargo holds."
    state = ledger.snapshot_state(text)
    assert state["sector"] == 1234
    assert state["credits"] == 100000
    assert state["cargo_holds_empty"] == 50


def test_snapshot_state_omits_cargo_when_absent():
    state = ledger.snapshot_state("Sector : 1234")
    assert "cargo_holds_empty" not in state


def test_snapshot_state_prefers_you_have_credits_over_a_stale_offer_mention():
    # Live-caught bug (this build's own money-loop proof): a leftover
    # "We'll sell them for 132 credits." sentence from the PRIOR trade
    # round can still be sitting in pyte's unclaimed screen buffer above
    # the CURRENT "You have N credits" balance line. state_parser's
    # first-match-wins scan grabs the stale 132; the ledger must not.
    text = (
        "We'll sell them for 132 credits.\n"
        "Your offer [132] ?\n"
        "You have 100,485 credits and 50 empty cargo holds."
    )
    assert ledger.snapshot_state(text)["credits"] == 100485


def test_snapshot_state_falls_back_to_state_parser_when_no_you_have_line():
    # No "you have" anchor present at all -- unchanged behavior, whatever
    # state_parser itself found (or didn't).
    text = "Credits: 5,000"
    assert ledger.snapshot_state(text)["credits"] == 5000


def test_snapshot_state_takes_the_last_you_have_credits_when_a_screen_shows_both():
    # Live-caught, round 2 of the same bug: a completed-transaction
    # screen prints "You have N credits" TWICE -- pre-transaction port
    # status context, then the actual post-transaction result at the
    # very end. The LAST one is current.
    text = (
        "You have 100,101 credits and 40 empty cargo holds.\n"
        "We'll buy them for 384 credits.\n"
        "Your offer [384] ? 384\n"
        "Very well, we'll buy them.\n"
        "You have 100,485 credits and 50 empty cargo holds."
    )
    assert ledger.snapshot_state(text)["credits"] == 100485


def test_snapshot_state_no_longer_locally_corrects_credits():
    # Regression guard for the §8 root-fix relocation: snapshot_state()
    # must now just be state_parser's own (already-corrected) reading
    # plus cargo -- no local credits override left behind. A screen
    # where the LAST 'you have' line is the true 100,485 balance proves
    # the correction is still happening, just upstream in state_parser.
    text = (
        "We'll sell them for 132 credits.\n"
        "You have 100,485 credits and 50 empty cargo holds."
    )
    from twclient.state_parser import parse_state

    assert ledger.snapshot_state(text)["credits"] == parse_state(text)["credits"] == 100485


# -- §10 human-readable log-trail: prompt capture + redaction --------------


def test_extract_prompt_returns_last_meaningful_line():
    pre_text = "Fuel Ore   Buying    2650    100%       0\n\nHow many holds of Fuel Ore [50]?"
    assert ledger.extract_prompt(pre_text) == "How many holds of Fuel Ore [50]?"


def test_extract_prompt_redacts_a_password_entry_line():
    pre_text = "Enter your handle: Kirk\nPassword:"
    assert ledger.extract_prompt(pre_text) == "<redacted>"


def test_extract_prompt_empty_when_pre_text_blank():
    assert ledger.extract_prompt("\n\n   \n") == ""


def test_record_do_captures_the_prompt_field(tmp_path):
    writer = ledger.LedgerWriter(path=tmp_path / "ledger.jsonl")
    entry = writer.record_do(
        pre_text="Sector : 100\nYour offer [158] ?",
        input_text="158",
        secret=False,
        post_text="Sector : 100\nVery well, we'll buy them.",
        settled_class="port_trade",
    )
    assert entry["prompt"] == "Your offer [158] ?"


def test_record_do_redacts_prompt_for_secret_input_even_without_the_word_password(tmp_path):
    # Belt-and-suspenders: a --secret dispatch redacts its prompt too,
    # even on a screen shape whose last line doesn't literally say
    # "password" -- the secret flag alone is enough to trigger it.
    writer = ledger.LedgerWriter(path=tmp_path / "ledger.jsonl")
    entry = writer.record_do(
        pre_text="Enter it again to confirm:",
        input_text="hunter2",
        secret=True,
        post_text="Command [TL=00753:0/0/0/850]",
        settled_class="main_command",
    )
    assert entry["prompt"] == "<redacted>"
    assert "hunter2" not in json.dumps(entry)


def test_render_keystroke_blank_input_is_never_invisible():
    assert ledger.render_keystroke("") == "«⏎ Enter (default)»"


def test_render_keystroke_control_byte_symbolic():
    assert ledger.render_keystroke("\x1d") == "«^]»"  # Ctrl-]


def test_render_keystroke_backspace_symbolic():
    assert ledger.render_keystroke("\x7f") == "«⌫»"
    assert ledger.render_keystroke("\x08") == "«⌫»"


def test_render_keystroke_redacted_input():
    assert ledger.render_keystroke("<redacted>") == "«<redacted>»"


def test_render_keystroke_highlights_normal_text():
    assert ledger.render_keystroke("158") == "«158»"


def test_render_trail_line_renders_question_keystroke_and_result():
    entry = {
        "ts": "2026-07-19T07:08:45Z",
        "settled_class": "port_trade",
        "prompt": "your offer [158]?",
        "input": "158",
        "pre_state": {"credits": 96553},
        "post_state": {"credits": 96783},
        "reward": {"d_credits": 230},
    }
    line = ledger.render_trail_line(entry)
    assert line.startswith("07:08:45 port_trade")
    assert 'Q ▸ "your offer [158]?"' in line
    assert "⌨ ▸ «158»" in line
    assert "+230cr (96,553→96,783)" in line


def test_render_trail_line_falls_back_to_screen_delta_when_no_reward():
    entry = {
        "ts": "2026-07-19T07:08:45Z",
        "settled_class": "sector_display",
        "prompt": "Command [TL=00753:0/0/0/850]:",
        "input": "M",
        "reward": {},
        "screen_delta_summary": "+4/-4/~0 lines",
    }
    assert "+4/-4/~0 lines" in ledger.render_trail_line(entry)


def test_compute_reward_computes_deltas_when_both_present():
    pre = {"credits": 1000, "turns_left": 850, "cargo_holds_empty": 50}
    post = {"credits": 1300, "turns_left": 848, "cargo_holds_empty": 45}
    reward = ledger.compute_reward(pre, post)
    assert reward == {"d_credits": 300, "d_turns": -2, "d_cargo": -5}


def test_compute_reward_omits_field_when_either_side_missing():
    pre = {"credits": 1000}
    post = {"turns_left": 848}  # credits missing on post, turns_left missing on pre
    reward = ledger.compute_reward(pre, post)
    assert reward == {}


def test_summarize_screen_delta_unchanged():
    assert ledger.summarize_screen_delta("same\ntext", "same\ntext") == "unchanged"


def test_summarize_screen_delta_reports_changed_lines():
    summary = ledger.summarize_screen_delta("line one\nline two", "line one\nline THREE")
    assert "unchanged" not in summary
    assert summary  # non-empty, bounded-length one-liner


def test_ledger_writer_append_and_read_roundtrip(tmp_path):
    path = tmp_path / "ledger.jsonl"
    writer = ledger.LedgerWriter(path=path)
    entry = writer.record_do(
        pre_text="Sector : 100\nYou have 1,000 credits.",
        input_text="M",
        secret=False,
        post_text="Sector : 200\nYou have 1,000 credits.",
        settled_class="sector_display",
        capture="my_run",
    )
    assert entry["capture"] == "my_run"
    assert entry["input"] == "M"
    assert entry["pre_state"]["sector"] == 100
    assert entry["post_state"]["sector"] == 200
    assert entry["reward"] == {"d_credits": 0}  # only credits present on both sides

    entries = ledger.read_entries(path=path)
    assert len(entries) == 1
    assert entries[0]["input"] == "M"
    assert entries[0]["settled_class"] == "sector_display"


def test_ledger_writer_redacts_secret_input_via_append(tmp_path):
    path = tmp_path / "ledger.jsonl"
    writer = ledger.LedgerWriter(path=path)
    entry = writer.record_do(
        pre_text="Password:",
        input_text="hunter2",
        secret=True,
        post_text="Command [TL=00753:0/0/0/850]",
        settled_class="main_command",
    )
    assert entry["input"] == "<redacted>"
    on_disk = ledger.read_entries(path=path)
    assert on_disk[0]["input"] == "<redacted>"
    assert "hunter2" not in path.read_text(encoding="utf-8")


def test_read_entries_skips_corrupt_trailing_line(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text(json.dumps({"input": "A"}) + "\n" + "{not valid json\n", encoding="utf-8")
    entries = ledger.read_entries(path=path)
    assert entries == [{"input": "A"}]


def test_read_entries_missing_file_returns_empty_list(tmp_path):
    assert ledger.read_entries(path=tmp_path / "nope.jsonl") == []
