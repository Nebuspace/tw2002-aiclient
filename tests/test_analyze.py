"""TW-12 session-retro analyzer tests — no network, synthetic ledger only."""

from twclient.analyze import analyze_session, format_report, select_session_entries


def _entry(ts, prompt, inp, d_credits, d_turns=-1, capture=None, settled="main_command"):
    return {
        "ts": ts,
        "capture": capture,
        "prompt": prompt,
        "input": inp,
        "settled_class": settled,
        "reward": {"d_credits": d_credits, "d_turns": d_turns},
        "pre_state": {},
        "post_state": {},
        "screen_delta_summary": "unchanged",
    }


def _money_loop_entries(capture="pilot-loop"):
    """Two full buy→sell style cycles under one capture name."""
    # Four steps × 2 occurrences so window mining can see recurrence.
    steps = [
        ("How many holds?", "50", 0, "port_trade"),
        ("Your offer?", "100", 0, "port_trade"),
        ("How many holds?", "50", 0, "port_trade"),
        ("Your offer?", "100", 500, "main_command"),
    ]
    entries = []
    for cycle in range(2):
        for i, (prompt, inp, cr, cls) in enumerate(steps):
            entries.append(
                _entry(
                    f"2026-07-19T10:0{cycle}:{i:02d}Z",
                    prompt,
                    inp,
                    cr,
                    capture=capture,
                    settled=cls,
                )
            )
    return entries


def test_select_by_capture_name():
    entries = _money_loop_entries() + [_entry("2026-07-18T01:00:00Z", "x", "y", 1, capture="other")]
    sliced = select_session_entries(entries, "pilot-loop")
    assert len(sliced) == 8
    assert all(e["capture"] == "pilot-loop" for e in sliced)


def test_select_by_ts_prefix():
    entries = _money_loop_entries() + [_entry("2026-07-18T01:00:00Z", "x", "y", 1)]
    sliced = select_session_entries(entries, "2026-07-19")
    assert len(sliced) == 8


def test_select_all():
    entries = _money_loop_entries()
    assert len(select_session_entries(entries, "all")) == 8


def test_analyze_surfaces_profitable_candidates():
    report = analyze_session("pilot-loop", entries=_money_loop_entries(), min_support=2)
    assert report["entry_count"] == 8
    assert report["match"] == "capture"
    assert report["candidates"], "expected at least one profitable recurring pattern"
    top = report["candidates"][0]
    assert top["support"] >= 2
    assert (top.get("cr_per_turn") or 0) > 0 or (top.get("cr_per_action") or 0) > 0
    text = format_report(report)
    assert "candidates to codify" in text
    assert "pilot-loop" in text


def test_analyze_empty_session():
    report = analyze_session("no-such", entries=_money_loop_entries())
    assert report["entry_count"] == 0
    assert report["match"] == "none"
    assert report["candidates"] == []
    assert "no ledger entries matched" in format_report(report)
