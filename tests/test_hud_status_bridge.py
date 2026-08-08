"""WO-HUD-STATUS-BRIDGE — the daemon side of the always-on Play HUD.

`cockpit/hud.py` has defined the wire contract since it was written and has
been painting honest `-` ever since, because **no producer emitted
`status["hud"]`**. This file is the producer's proof.

**The finding that shaped the work, stated up front because it inverts the
obvious reading of the WO.** Two TWGS dialects spell the command prompt's
`TL=` field differently and only one of them means turns by it:

    Command [TL=00753:0/0/0/850] (?=Help)? :      <- CLASSIC: a turn count
    Command [TL=00:00:00]:[21068] (?=Help)? :     <- this server: a CLOCK

`state_parser.py` says outright that "the live target server uses the
bracketed form" — the second one — and `canon/testing/cases/
test-state-parser.md` records it as observed fact ("this live server's MBBS
Gold build uses TL= for a HH:MM:SS countdown timer, not a turn count"). So a
prompt-line-only extractor answers `absent` on **every prompt this server
ever prints**, and a HUD wired to it alone would have stayed `-` forever
while the suite went green. The counted shape survives in this repo only in
fixtures stamped *constructed-pending-live-capture*.

The turn count this server actually prints is a BODY statement, and the one
genuine turn number in the whole corpus is on a live capture:
`tests/fixtures/port_trade_screen.txt` — "One turn deducted, 29990 turns
left." — whose own prompt is the countdown. Hence two readers, not one, and
`test_the_live_capture_is_what_fills_the_hud` is the test that would have
caught the cosmetically-green version.

**The forged zero.** Reading `TL=00:00:00` as an integer yields `0`, and `0`
here is not a harmless wrong number — it is the reading that says "you are
out of turns". The archive shipped exactly that and "silently reported
`turns_left=0`". The refusal is built as an ACCEPT-list over what a count
looks like rather than a blocklist over what a clock looks like, because a
blocklist only closes the spellings someone thought of;
`test_no_clock_shaped_body_can_ever_yield_a_number` sweeps ~2000 of them.

No network, no daemon, no real `config/`. The session tests run against the
**real `Session` class** (the `test_last_known_sector.py` convention — a
hand-built double would confirm what this file assumed rather than what the
daemon does), with only the render surface monkeypatched. The small harness
doubles are local to this module, per the convention
`test_ensure_login_error_redaction.py` states.
"""

import hashlib
import math
import re
from pathlib import Path

import pytest

from tw2002_aiclient.cockpit import goals, hud
from tw2002_aiclient.session import protocol
from tw2002_aiclient.session import state_parser as sp
from tw2002_aiclient.session.session import Session

# The two real prompt dialects, copied from captured fixtures rather than
# retyped: `stardock_shipyard_listing.txt` and `port_trade_screen.txt`.
CLASSIC_PROMPT = "Command [TL=00752:0/0/0/850] (?=Help)? :"
LIVE_PROMPT = "Command [TL=00:00:00]:[21068] (?=Help)? :"
# The WO's Accept-1 example. It welds the classic TL body onto the bracketed
# sector form, and `state_parser.py` says the classic shape "carries no
# [NNNN] bracket at all" — so this line exists on NEITHER server. Pinned
# anyway: the Accept names it, and the reader is deliberately indifferent to
# whether a sector bracket follows (that is the sector reader's business).
WO_ACCEPT_EXAMPLE = "Command [TL=00753:0/0/0/850]:[21068] (?=Help)? :"

LIVE_NARRATIVE = "One turn deducted, 29990 turns left."
SHIP_INFO_LABEL = "Turns left     : 850"

# WO-HUD-I-LIVE-FIXTURE: byte-identical #226 live `I` capture.
_SHIP_INFO_FIXTURE = Path("tests/fixtures/ship_info_screen.txt")
_SHIP_INFO_SHA256 = (
    "5fa6cfb3aaf7989e0c94c7fcb27d028366b9643f109ab7765c566c9f5ef9c867"
)


class _Server:
    """The three attributes `_status_response` reads off a server, all
    absent-shaped. Everything it reaches for is `getattr`-guarded, so this
    is enough to exercise the whole response."""

    watch_hub = None
    control_lock = None
    autoloop = None


@pytest.fixture
def session(tmp_path):
    """A real `Session`. `__init__` builds a `TelnetConnection` but does not
    connect — the `test_last_known_sector.py` fixture, verbatim in intent."""
    return Session("127.0.0.1", 65000, "probe", str(tmp_path))


def _wire(session, monkeypatch, *rows):
    """Point a REAL Session's render surface at a fixed screen."""
    rows = list(rows)
    monkeypatch.setattr(session, "render", lambda *a, **k: list(rows))
    monkeypatch.setattr(session, "render_with_color", lambda *a, **k: (list(rows), None))
    monkeypatch.setattr(session, "render_text", lambda r=None: "\n".join(r or rows))
    monkeypatch.setattr(session.conn, "connected", True, raising=False)
    return session


def _status(session, monkeypatch, *rows):
    _wire(session, monkeypatch, *rows)
    return protocol._status_response(session, _Server())


# ===========================================================================
# The prompt-line reader — the CLASSIC dialect, and the forged zero
# ===========================================================================


def test_extracts_turns_left_from_command_prompt():
    """Canon test case (`canon/testing/cases/test-state-parser.md`), on the
    real captured classic line — which carries NO sector bracket."""
    read = sp.read_turns_left(CLASSIC_PROMPT)
    assert read.outcome == sp.OUTCOME_READ
    assert read.turns == 752
    assert read.source == sp.SOURCE_TURN_COUNT_PROMPT


def test_the_wo_accept_example_reads_even_though_no_server_prints_it():
    """The Accept-1 string is a chimera of the two dialects. The reader is
    indifferent to a trailing sector bracket, so it reads anyway — pinned so
    the Accept is demonstrably satisfied as written, not merely in spirit."""
    assert sp.read_turns_left(WO_ACCEPT_EXAMPLE).turns == 753


def test_tl_hhmmss_timer_shape_is_not_misread_as_zero_turns():
    """Canon test case, and the archive's actual live defect: this server's
    MBBS Gold build uses `TL=` for a countdown, and reading it as an integer
    "silently reported turns_left=0"."""
    read = sp.read_turns_left(LIVE_PROMPT)
    assert read.outcome == sp.OUTCOME_ABSENT
    assert read.turns is None
    # Said the other way round too. `absent`/`None` is the assertion above;
    # this one is the CONSEQUENCE that matters, and it is what a future
    # refactor toward `int(...) or 0` would break first.
    assert read.turns != 0


@pytest.mark.parametrize(
    "body",
    [
        "00:00:00",  # the live capture
        "06:45:36",  # a running clock
        "1:2:3",  # single-digit fields — NOT matched by \d{1,2}:\d{2}:\d{2}
        "00:00",  # truncated / half-painted clock
        "0:0",
        "00:00:00 ",  # trailing space
        " 00:00:00",
    ],
)
def test_no_clock_shaped_body_is_read_as_a_count(body):
    """Each of these escapes an HH:MM:SS *blocklist* in a different way, and
    every one of them would have yielded a small integer (usually `0`) from a
    leading-digit read. The accept-list refuses them all by default."""
    assert sp.read_turns_left(f"Command [TL={body}]:[9] :").outcome == sp.OUTCOME_ABSENT


def test_no_clock_shaped_body_can_ever_yield_a_number():
    """The sweep behind the parametrisation above.

    A blocklist is only as good as the spellings its author imagined, so
    this asserts the property over the whole clock space rather than over
    seven examples. `1:2:3` and `00:00` are the two that a naive
    `\\d{1,2}:\\d{2}:\\d{2}` refusal lets through — both were live holes in
    this file's own first draft, found by this sweep.
    """
    forged = []
    for h in range(0, 25):
        for m in (0, 5, 9, 30, 59):
            for s in (0, 8, 36, 59):
                for fmt in ("%d:%02d:%02d", "%02d:%02d:%02d", "%d:%d:%d"):
                    body = fmt % (h, m, s)
                    read = sp.read_turns_left(f"Command [TL={body}]:[9] :")
                    if read.outcome != sp.OUTCOME_ABSENT:
                        forged.append((body, read.outcome, read.turns))
    assert not forged, f"clock-shaped bodies read as turn counts: {forged[:10]}"


def test_the_sweep_can_actually_fail():
    """Positive control for the sweep above — an empty result from a broken
    loop is indistinguishable from a passing property. A genuine count is
    fed through the same expression the sweep uses, and must NOT be absent."""
    read = sp.read_turns_left("Command [TL=00753:0/0/0/850]:[9] :")
    assert read.outcome != sp.OUTCOME_ABSENT


@pytest.mark.parametrize("body,turns", [("1000", 1000), ("0", 0), ("00753", 753), (" 00753 ", 753)])
def test_a_bare_count_reads(body, turns):
    """A STATED zero is a real game state and reads as one. What must never
    happen is a zero nobody stated — the distinction the accept-list keeps."""
    assert sp.read_turns_left(f"Command [TL={body}] :").turns == turns


def test_an_unrecognised_body_is_absent_rather_than_a_digit_hunt():
    assert sp.read_turns_left("Command [TL=abc] :").outcome == sp.OUTCOME_ABSENT


def test_a_damaged_tl_bracket_is_unreadable_not_a_number():
    """A bracket that opened and never closed is a mid-paint render, not a
    count — and `unreadable` is a NON-write, so it ages the sticky value
    instead of replacing it."""
    read = sp.read_turns_left("Command [TL=00753:0/0/0/850 (?=Help)? :")
    assert read.outcome == sp.OUTCOME_UNREADABLE
    assert read.reason == sp.REASON_DAMAGED_COMMAND_PROMPT
    assert read.turns is None


def test_a_bracket_damaged_after_a_good_one_does_not_read_the_stale_one():
    """Last-match applied to the DAMAGE check, not only to the value.

    An earlier bracket resolved cleanly and a later one is still painting.
    Reading the earlier number would be first-match-wins by the back door,
    and on this field it hands the HUD a count from before the spend. The
    body reader has the same pin; this is its prompt-line twin, added
    because a mutation pass found the prompt-line side unguarded.
    """
    line = "Command [TL=00752:0/0/0/850] : Command [TL=00753:0/0/0/"
    read = sp.read_turns_left(line)
    assert read.outcome == sp.OUTCOME_UNREADABLE
    assert read.reason == sp.REASON_DAMAGED_COMMAND_PROMPT
    assert read.turns is None


def test_last_match_wins_on_the_prompt_line():
    """Canon's hard rule. A stale bracket echoed earlier on the row must not
    beat the one the server most recently printed."""
    line = "Command [TL=00999:0/0/0/1] : Command [TL=00752:0/0/0/850] :"
    assert sp.read_turns_left(line).turns == 752


def test_a_non_string_is_unreadable():
    assert sp.read_turns_left(None).reason == sp.REASON_NOT_TEXT
    assert sp.read_turns_left(b"Command [TL=1] :").reason == sp.REASON_NOT_TEXT


# ===========================================================================
# The body reader — what this server actually prints, and the archive scar
# ===========================================================================


def test_extracts_turns_left_plain_phrasing():
    """Canon test case. The post-move narrative, verbatim from the live
    capture `tests/fixtures/port_trade_screen.txt`."""
    read = sp.read_turns_left_from_screen(f"Docking...\n{LIVE_NARRATIVE}\n")
    assert read.outcome == sp.OUTCOME_READ
    assert read.turns == 29990
    assert read.source == sp.SOURCE_TURNS_LEFT_NARRATIVE


def test_ship_info_turns_left_label_not_forged_from_sector_line():
    """Canon test case. The label-first ship-info (`I`) shape, with the
    forgery source the canon row names sitting directly above it: a sector
    id on the previous line must not become the turn count."""
    read = sp.read_turns_left_from_screen(f"Sector  : 21068\n{SHIP_INFO_LABEL}\n")
    assert read.outcome == sp.OUTCOME_READ
    assert read.turns == 850
    assert read.source == sp.SOURCE_TURNS_LEFT_LABEL


def test_the_archive_scar_a_newline_cannot_be_crossed():
    """THE regression. The archive's `_TURNS_LEFT_PLAIN_RE` used `\\s+`,
    which "crossed newlines and forged turns_left from the prior line's
    sector id". Here the number and the phrase are on different lines, so a
    `\\s`-based pattern reads 21068 turns; a `[ \\t]`-based one reads
    nothing."""
    read = sp.read_turns_left_from_screen("Sector  : 21068\nturns left\n")
    assert read.outcome == sp.OUTCOME_ABSENT
    assert read.turns is None


def test_the_scar_guard_is_structural_not_incidental():
    """The pattern itself, not just its behaviour on one fixture: no pattern
    this reader uses may contain a `\\s` class, because that is the single
    character-class difference between the archive's defect and this code."""
    import inspect

    src = inspect.getsource(sp)
    turns_patterns = re.findall(r"^_TURNS_[A-Z_]*RE = re\.compile\(\s*r?\"(.*?)\"", src, re.M)
    assert turns_patterns, "found no turns patterns to inspect — the check is vacuous"
    for pattern in turns_patterns:
        assert "\\s" not in pattern, f"a turns pattern reintroduced \\s: {pattern!r}"


def test_the_game_select_menu_turns_column_is_not_a_turn_count():
    """Real crossfire, from `tests/fixtures/game_select_menu.txt`: the game
    list advertises each game's turn allowance. It is not the pilot's
    remaining turns, and it fails to match rather than being filtered out
    afterwards — refusal by construction."""
    menu = " [D] Default Stock Game      -Sectors:1000  Turns:250  Time:60m\n"
    assert sp.read_turns_left_from_screen(menu).outcome == sp.OUTCOME_ABSENT


def test_a_fighter_count_is_not_a_turn_count():
    assert sp.read_turns_left_from_screen("You have 3 fighters\n").outcome == sp.OUTCOME_ABSENT


def test_body_last_match_wins_across_both_shapes():
    """Position-sorted across the two patterns, not per-pattern priority —
    otherwise "last match" silently means "last match of my favourite
    shape"."""
    screen = f"{LIVE_NARRATIVE}\n{SHIP_INFO_LABEL}\n"
    assert sp.read_turns_left_from_screen(screen).turns == 850
    screen = f"{SHIP_INFO_LABEL}\n{LIVE_NARRATIVE}\n"
    assert sp.read_turns_left_from_screen(screen).turns == 29990


def test_a_damaged_turns_label_is_unreadable_not_a_number():
    read = sp.read_turns_left_from_screen("Turns left     :\n")
    assert read.outcome == sp.OUTCOME_UNREADABLE
    assert read.reason == sp.REASON_DAMAGED_TURNS_LABEL


def test_a_label_damaged_after_a_good_reading_does_not_read_the_stale_one():
    """Last-match applied to the DAMAGE check too — reading the earlier
    number would be first-match-wins by the back door, and on this field it
    would report a count from before the spend."""
    screen = f"{SHIP_INFO_LABEL}\nTurns left     :\n"
    assert sp.read_turns_left_from_screen(screen).outcome == sp.OUTCOME_UNREADABLE


# ===========================================================================
# The real captured screen — the test the cosmetic version fails
# ===========================================================================


def test_the_live_capture_is_what_fills_the_hud(tmp_path):
    """`port_trade_screen.txt` is the only fixture in the repo carrying a
    genuine turn count, and it is a LIVE capture. Its prompt is the
    countdown, so the prompt reader answers `absent` and the body reader is
    the one that produces 29990.

    This is the test a prompt-line-only implementation fails. Everything
    else in this file would still have been green.
    """
    text = (
        pytest.importorskip("pathlib").Path("tests/fixtures/port_trade_screen.txt")
        .read_text(encoding="utf-8", errors="replace")
    )
    prompt = [line.strip() for line in text.splitlines() if line.strip()][-1]

    assert prompt.startswith("Command [TL="), "fixture's last line is no longer the prompt"
    assert sp.read_turns_left(prompt).outcome == sp.OUTCOME_ABSENT
    assert sp.read_turns_left_from_screen(text).turns == 29990


def test_the_classic_fixture_is_the_mirror_image():
    """`stardock_shipyard_listing.txt` is the other dialect: the prompt
    carries the count and the body says nothing. Both readers are load-
    bearing, on different servers."""
    from pathlib import Path

    text = Path("tests/fixtures/stardock_shipyard_listing.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    prompt = [line.strip() for line in text.splitlines() if line.strip()][-1]
    assert sp.read_turns_left(prompt).outcome == sp.OUTCOME_READ
    assert sp.read_turns_left_from_screen(text).outcome == sp.OUTCOME_ABSENT


# ===========================================================================
# WO-HUD-I-LIVE-FIXTURE — exact live `I` capture, not a hand-typed label
# ===========================================================================


def _ship_info_raw() -> bytes:
    return _SHIP_INFO_FIXTURE.read_bytes()


def _ship_info_rows() -> list[str]:
    """Exact capture lines (trailing spaces preserved)."""
    return _ship_info_raw().decode("utf-8").splitlines()


def test_ship_info_fixture_is_byte_identical_to_the_live_capture():
    """Provenance pin: the fixture is the #226 capture, not a redraw."""
    raw = _ship_info_raw()
    assert len(raw) == 1525
    assert hashlib.sha256(raw).hexdigest() == _SHIP_INFO_SHA256
    text = raw.decode("utf-8")
    assert "Turns left     : 25000" in text
    assert "Command [TL=07:57:48]:[15450]" in text
    assert "Current Sector : 15450" in text
    assert "Credits        : 100,000" in text


def test_ship_info_live_capture_fills_turns_from_the_label_not_the_countdown():
    """The load-bearing live dialect on the `I` screen: countdown prompt is
    absent (never a forged zero); the body label is SOURCE_TURNS_LEFT_LABEL."""
    rows = _ship_info_rows()
    text = "\n".join(rows)
    prompt = rows[-1].strip()
    assert prompt.startswith("Command [TL="), prompt

    prompt_read = sp.read_turns_left(prompt)
    assert prompt_read.outcome == sp.OUTCOME_ABSENT
    assert prompt_read.turns is None
    assert prompt_read.turns != 0

    body = sp.read_turns_left_from_screen(text)
    assert body.outcome == sp.OUTCOME_READ
    assert body.turns == 25000
    assert body.source == sp.SOURCE_TURNS_LEFT_LABEL


def test_ship_info_live_capture_fills_status_and_hud_through_real_session(
    session, monkeypatch
):
    """Same Session + `_status_response` path as the rest of this file —
    all five HUD cells come from the capture's positive statements plus the
    session-profit baseline."""
    rows = _ship_info_rows()
    resp = _status(session, monkeypatch, *rows)
    assert resp["turns_left"] == 25000
    assert resp["hud"]["turns"]["value"] == 25000
    assert math.isfinite(resp["hud"]["turns"]["age_s"])
    assert resp["hud"]["sector"]["value"] == 15450
    assert resp["hud"]["credits"]["value"] == 100000
    assert resp["hud"]["cargo"]["value"] == "60 empty / 60"
    assert resp["hud"]["profit"]["value"] == 0


# ===========================================================================
# The sticky stores, against the REAL Session class
# ===========================================================================


def test_the_real_session_class_carries_the_contract():
    """`protocol.py` reaches every one of these through `getattr(...)` so the
    scripted stand-ins handed to `build_response` cannot crash the daemon.
    That tolerance must never extend to the real thing — this is the pin
    that closes the `getattr` hole."""
    for name in ("observe_turns", "turns_snapshot", "observe_sector", "sector_snapshot"):
        assert callable(getattr(Session, name, None)), f"Session lost {name}()"


def test_nothing_observed_reports_absent_not_zero(session):
    """A store that has never seen a number must not be able to assert one.
    On this field that is the whole point: `absent` and `0` are different
    game states and the archive collapsed them."""
    snapshot = session.turns_snapshot()
    assert snapshot.outcome == sp.OUTCOME_ABSENT
    assert snapshot.turns is None


def test_precedence_the_prompt_line_wins_when_both_speak(session):
    """Specificity, not trust: the prompt line is one line the server just
    printed, while the body reader searches a grid that may still be showing
    an older screen."""
    session.observe_turns(f"{LIVE_NARRATIVE}\n{CLASSIC_PROMPT}", CLASSIC_PROMPT)
    assert session.turns_snapshot().turns == 752


def test_the_body_fills_turns_where_the_prompt_cannot(session):
    """The live dialect. The prompt says `absent`, so the body is what the
    HUD ends up showing — the fallback that makes this WO visible."""
    session.observe_turns(f"{LIVE_NARRATIVE}\n{LIVE_PROMPT}", LIVE_PROMPT)
    assert session.turns_snapshot().turns == 29990


def test_a_screen_stating_nothing_does_not_clobber(session):
    """Non-clobber, exactly like `observe_credits`. A reading that VANISHED
    and a count that reached zero must not look alike to the HUD."""
    session.observe_turns(f"{LIVE_NARRATIVE}\n{LIVE_PROMPT}", LIVE_PROMPT)
    session.observe_turns("A screen that mentions no turns at all\n", LIVE_PROMPT)
    assert session.turns_snapshot().turns == 29990


def test_a_damaged_claim_is_not_written(session):
    """"I could not finish reading it" is not a turn count."""
    session.observe_turns(f"{LIVE_NARRATIVE}\n{LIVE_PROMPT}", LIVE_PROMPT)
    session.observe_turns("Turns left     :\n", "Command [TL=00753:0/0/0/850 :")
    assert session.turns_snapshot().turns == 29990


def test_the_age_is_seconds_and_finite(session):
    session.observe_turns(f"{LIVE_NARRATIVE}\n{LIVE_PROMPT}", LIVE_PROMPT)
    age = session.turns_snapshot().age_s
    assert isinstance(age, float) and math.isfinite(age) and age >= 0.0


def test_the_sticky_sector_is_not_the_epoch_guarded_memory(session):
    """`last_known_sector()` is epoch-invalidated — it goes `None` the moment
    anything is sent, because a world-model write against a stale sector is
    the live incident it exists to prevent. A HUD cell built on it would
    blank on every keystroke, so the display gets its own store.

    Pinned by driving the epoch forward and asserting the two DISAGREE. If a
    later edit points `sector_snapshot` at the guarded memory to save a
    field, this is what reddens.
    """
    session.observe_sector(LIVE_PROMPT)
    session.note_sector(21068)
    assert session.last_known_sector() == 21068

    session._sector_epoch += 1  # what a send does

    assert session.last_known_sector() is None, "epoch guard is not doing its job"
    assert session.sector_snapshot().sector == 21068, "the HUD store followed the guard"


# ===========================================================================
# The wire — `status["hud"]` and the top-level `turns_left`
# ===========================================================================


def test_status_always_emits_all_five_hud_cells(session, monkeypatch):
    """Always present, like `replay_arm`: a missing key must not be how
    "nothing is known" is expressed, because the composer already has an
    honest unknown cell and a silent key is indistinguishable from a bridge
    that broke."""
    resp = _status(session, monkeypatch, "A screen with nothing on it", LIVE_PROMPT)
    assert set(resp["hud"]) == {"credits", "sector", "turns", "cargo", "profit"}
    for name, cell in resp["hud"].items():
        assert set(cell) == {"value", "age_s"}, name


def test_cargo_and_profit_are_honest_unknowns(session, monkeypatch):
    """No producer yet, emitted anyway so the payload's shape does not change
    the day they get one."""
    resp = _status(session, monkeypatch, LIVE_NARRATIVE, LIVE_PROMPT)
    assert resp["hud"]["cargo"] == {"value": None, "age_s": None}
    assert resp["hud"]["profit"] == {"value": None, "age_s": None}


def test_accept_1_classic_prompt_fills_turns_left_and_hud_turns(session, monkeypatch):
    """Accept 1. Both fields, from one reading, with a finite age."""
    resp = _status(session, monkeypatch, "StarDock listing", WO_ACCEPT_EXAMPLE)
    assert resp["turns_left"] == 753
    assert resp["hud"]["turns"]["value"] == 753
    assert math.isfinite(resp["hud"]["turns"]["age_s"])


def test_accept_1_sector_fills_from_the_bracketed_prompt(session, monkeypatch):
    resp = _status(session, monkeypatch, "Docking...", LIVE_PROMPT)
    assert resp["hud"]["sector"]["value"] == 21068
    assert math.isfinite(resp["hud"]["sector"]["age_s"])


def test_accept_2_countdown_emits_no_turns_left_key_and_no_forged_zero(session, monkeypatch):
    """Accept 2. The key is ABSENT, not `0` and not `None`."""
    resp = _status(session, monkeypatch, "A screen with no turn count", LIVE_PROMPT)
    assert "turns_left" not in resp
    assert resp["hud"]["turns"] == {"value": None, "age_s": None}


def test_turns_left_is_omitted_never_null(session, monkeypatch):
    """Omit-don't-null, the rule `sector_wire` states for its own fields. A
    `None` here would be this response's one field asserting a value it does
    not have."""
    resp = _status(session, monkeypatch, "nothing", LIVE_PROMPT)
    assert "turns_left" not in resp
    with pytest.raises(KeyError):
        resp["turns_left"]


def test_the_status_verb_is_the_one_that_observes(session, monkeypatch):
    """The wire, not just the store. `dispatch` routes `status` to
    `_status_response` directly — it does NOT pass through
    `build_response`, so the observation has to live on this path or the
    HUD's own poll would never fill anything.

    A producer nobody calls is indistinguishable from no producer at all.
    """
    _wire(session, monkeypatch, LIVE_NARRATIVE, LIVE_PROMPT)
    assert session.turns_snapshot().outcome == sp.OUTCOME_ABSENT
    resp = protocol.dispatch(session, "status", {}, _Server())
    assert session.turns_snapshot().turns == 29990
    assert resp["turns_left"] == 29990


def test_the_hud_persists_across_a_screen_that_omits_everything(session, monkeypatch):
    """Sticky. The operator walks onto a StarDock screen that states neither
    sector nor turns; the cells keep their last-known values and age."""
    first = _status(session, monkeypatch, LIVE_NARRATIVE, LIVE_PROMPT)
    assert first["hud"]["turns"]["value"] == 29990

    later = _status(session, monkeypatch, "<StarDock> Where to? (?=Help)")
    assert later["hud"]["turns"]["value"] == 29990
    assert later["hud"]["sector"]["value"] == 21068


def test_a_session_without_the_stores_does_not_crash_the_daemon(session, monkeypatch):
    """The `getattr` tolerance, exercised. A stand-in predating these stores
    reports unknown cells rather than raising — the same answer a store that
    had seen nothing would give."""

    class _Bare:
        pass

    assert protocol._hud_payload(_Bare()) == {
        name: {"value": None, "age_s": None}
        for name in ("credits", "sector", "turns", "cargo", "profit")
    }


# ===========================================================================
# The consumers — contract match with the composers this exists to feed
# ===========================================================================


def test_accept_3_the_composer_renders_the_payload_this_bridge_emits(session, monkeypatch):
    """Contract match, asserted by RENDERING rather than by comparing shapes:
    two dicts agreeing proves nothing if the composer reads a third key."""
    resp = _status(session, monkeypatch, LIVE_NARRATIVE, LIVE_PROMPT)
    lines = hud.compose_hud_cells(resp, width=40)
    assert len(lines) == 10
    rendered = "\n".join(text for text, _stale in lines)
    assert "29,990" in rendered or "29990" in rendered, rendered
    assert "21,068" in rendered or "21068" in rendered, rendered


def test_the_composer_still_paints_unknown_when_the_bridge_says_nothing(session, monkeypatch):
    """The control. Without it, a composer that ignored the payload entirely
    and always printed a number would pass the test above."""
    resp = _status(session, monkeypatch, "nothing at all")
    lines = hud.compose_hud_cells(resp, width=40)
    rendered = "\n".join(text for text, _stale in lines)
    assert hud.UNKNOWN_VALUE in rendered
    assert "29,990" not in rendered


def test_accept_4_goals_turns_row_consumes_the_top_level_field(session, monkeypatch):
    """Accept 4. The GOALS row reads `status["turns_left"]`, not the HUD
    cell and not the viewport paint — so the top-level field is load-bearing
    on its own and is not decoration beside `hud.turns`."""
    resp = _status(session, monkeypatch, LIVE_NARRATIVE, LIVE_PROMPT)
    rendered = "\n".join(goals.compose_goals_lines(resp, width=44))
    assert "29,990" in rendered, rendered


def test_the_goals_row_degrades_honestly_without_the_field(session, monkeypatch):
    """Control for the row above."""
    resp = _status(session, monkeypatch, "nothing at all", LIVE_PROMPT)
    rendered = "\n".join(goals.compose_goals_lines(resp, width=44))
    assert "29,990" not in rendered


# ===========================================================================
# Type contracts
# ===========================================================================


@pytest.mark.parametrize(
    "kwargs",
    [
        {"outcome": sp.OUTCOME_READ},  # read with no number
        {"outcome": sp.OUTCOME_ABSENT, "turns": 5, "source": sp.SOURCE_TURN_COUNT_PROMPT},
        {"outcome": sp.OUTCOME_READ, "turns": True, "source": sp.SOURCE_TURN_COUNT_PROMPT},
        {"outcome": sp.OUTCOME_READ, "turns": 5},  # no source
        {"outcome": sp.OUTCOME_UNREADABLE, "reason": "invented_reason"},
    ],
)
def test_turns_read_refuses_an_incoherent_verdict(kwargs):
    """`turns=True` is the one worth naming: `isinstance(True, int)` holds,
    so an unguarded check remembers one turn for `True`."""
    with pytest.raises(ValueError):
        sp.TurnsRead(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"outcome": sp.OUTCOME_READ, "turns": 5},  # no age
        {"outcome": sp.OUTCOME_READ, "turns": 5, "age_s": float("nan")},
        {"outcome": sp.OUTCOME_READ, "turns": 5, "age_s": -1.0},
        {"outcome": sp.OUTCOME_ABSENT, "turns": 0, "age_s": 1.0},
        {"outcome": sp.OUTCOME_UNREADABLE, "turns": 5, "age_s": 1.0},
    ],
)
def test_turns_snapshot_refuses_an_incoherent_pair(kwargs):
    """NaN is the dangerous one: `nan >= FRESHNESS_STALE_S` is False, so an
    unguarded freshness ladder reads a NaN age as perfectly fresh."""
    with pytest.raises(ValueError):
        sp.TurnsSnapshot(**kwargs)


# ===========================================================================
# WO-STATUS-FIGHTERS-ABOARD — top-level status["fighters_aboard"]
# ===========================================================================


def test_accept_fighters_aboard_from_ship_info_fixture(session, monkeypatch):
    """Accept 1. Live I-capture ship-info line → top-level int."""
    text = _SHIP_INFO_FIXTURE.read_text(encoding="utf-8")
    resp = _status(session, monkeypatch, text)
    assert resp["fighters_aboard"] == 150


def test_fighters_aboard_omitted_when_never_observed(session, monkeypatch):
    """Accept 2. Never invent 0 from absence — coach at_shipyard must stay silent."""
    resp = _status(session, monkeypatch, "A screen with no fighters line", LIVE_PROMPT)
    assert "fighters_aboard" not in resp
    with pytest.raises(KeyError):
        resp["fighters_aboard"]


def test_encounter_toll_fighters_line_does_not_emit_fighters_aboard(
    session, monkeypatch
):
    """Other people's grid fighters must not become aboard count."""
    resp = _status(
        session,
        monkeypatch,
        "Fighters: 4 (Somecorp) [Toll]\nOption? (A,D,I,R,P,S,?):?",
        LIVE_PROMPT,
    )
    assert "fighters_aboard" not in resp


def test_fighter_encounter_status_emits_toll_ev(session, monkeypatch):
    """WO-WIRE-REROUTE-EV-TO-PRIORITY-COACH: product call site on status."""
    resp = _status(
        session,
        monkeypatch,
        "Commander Rax is here.\nYour fighters: 500 vs. theirs: 1\n"
        "Option? (A,D,I,R,S,?):?",
    )
    assert resp["classification"] == "fighter_encounter"
    assert "toll_ev" in resp
    assert resp["toll_ev"]["preferred"] in ("reroute", "fight", "unknown")
    assert "prompt" not in resp


def test_calm_screen_omits_toll_ev(session, monkeypatch):
    resp = _status(session, monkeypatch, "Command [TL=00:00:00]:[1] (?=Help)? :")
    assert resp.get("classification") != "fighter_encounter"
    assert "toll_ev" not in resp


def test_fighters_aboard_zero_is_emitted_not_omitted(session, monkeypatch):
    """A real reading of 0 is a fact (shipyard arm); omit is only for unknown."""
    resp = _status(session, monkeypatch, "Fighters       : 0\n", LIVE_PROMPT)
    assert resp["fighters_aboard"] == 0


def test_the_status_verb_observes_fighters(session, monkeypatch):
    """Observation lives on the status path (same pin as turns)."""
    _wire(session, monkeypatch, "Fighters       : 12\n")
    assert session.fighters_snapshot().outcome == sp.OUTCOME_ABSENT
    resp = protocol.dispatch(session, "status", {}, _Server())
    assert session.fighters_snapshot().fighters == 12
    assert resp["fighters_aboard"] == 12


def test_goals_fighters_row_reads_status_fighters_aboard(session, monkeypatch):
    """Consumer proof: GOALS paints the count once the wire supplies it."""
    resp = _status(session, monkeypatch, "Fighters       : 7\n", LIVE_PROMPT)
    lines = goals.compose_goals_lines(resp, width=40)
    joined = "\n".join(lines)
    assert "7" in joined
    assert "Fighters" in joined or "fighters" in joined.lower()


# ===========================================================================
# WO-STATUS-CREDITS — top-level status["credits"]
# ===========================================================================


def test_accept_credits_from_ship_info_fixture(session, monkeypatch):
    """Accept 1. Live I-capture credits line → top-level int."""
    text = _SHIP_INFO_FIXTURE.read_text(encoding="utf-8")
    resp = _status(session, monkeypatch, text)
    assert resp["credits"] == 100000
    # Distinct from the HUD cell the bridge already supplied.
    assert resp["hud"]["credits"]["value"] == 100000


def test_credits_omitted_when_never_observed(session, monkeypatch):
    """Accept 2. Never invent 0 from absence — GOALS Credits must stay `?`."""
    resp = _status(session, monkeypatch, "A screen with no credits line", LIVE_PROMPT)
    assert "credits" not in resp
    with pytest.raises(KeyError):
        resp["credits"]


def test_price_quote_credits_mention_does_not_emit_top_level_credits(
    session, monkeypatch
):
    """AP-13: a hold-price quote must not become the cash balance."""
    resp = _status(
        session,
        monkeypatch,
        "Holds cost 1,468 credits each, for a total of 29,360 credits "
        "to fill them all.\n",
        LIVE_PROMPT,
    )
    assert "credits" not in resp


def test_credits_zero_is_emitted_not_omitted(session, monkeypatch):
    """A real reading of 0 is a fact; omit is only for unknown."""
    resp = _status(session, monkeypatch, "Credits        : 0\n", LIVE_PROMPT)
    assert resp["credits"] == 0


def test_the_status_verb_already_observes_credits(session, monkeypatch):
    """Observation already lives on the status path — do not re-plumb."""
    _wire(session, monkeypatch, "Credits        : 42\n")
    assert session.credits_snapshot().outcome == sp.OUTCOME_ABSENT
    resp = protocol.dispatch(session, "status", {}, _Server())
    assert session.credits_snapshot().balance == 42
    assert resp["credits"] == 42


def test_goals_credits_row_reads_status_credits(session, monkeypatch):
    """Consumer proof: GOALS paints the balance once the wire supplies it."""
    resp = _status(session, monkeypatch, "Credits        : 987654\n", LIVE_PROMPT)
    lines = goals.compose_goals_lines(resp, width=40)
    joined = "\n".join(lines)
    assert "987,654" in joined or "987654" in joined
    assert "Credits" in joined or "Cr" in joined


# ===========================================================================
# WO-COACH-EXPLORE-MODE — top-level status["explore_mode"]
# ===========================================================================


class _ExploreStub:
    """Minimal runner: snapshot() is what observe_explore calls."""

    def __init__(self, snapshot):
        self._snapshot = snapshot

    def snapshot(self):
        return self._snapshot


class _ExploreServer(_Server):
    def __init__(self, runner):
        self.sector_explore = runner


def test_explore_mode_emitted_when_running_with_report(session, monkeypatch):
    """Accept 1. Mid-run explore → top-level intent string."""
    from tw2002_aiclient.session import sector_explore as sx

    report = sx.ExploreReport(
        world_id="w", started_at="t", min_sectors=1, intent="map_fill"
    )
    snap = sx.ExploreSnapshot(running=True, report=report)
    _wire(session, monkeypatch, "Command prompt\n", LIVE_PROMPT)
    resp = protocol._status_response(session, _ExploreServer(_ExploreStub(snap)))
    assert resp["explore_mode"] == "map_fill"


def test_explore_mode_omitted_when_idle(session, monkeypatch):
    """Accept 2. Idle / no runner → key omitted; coach card stays silent."""
    from tw2002_aiclient.session import sector_explore as sx

    snap = sx.ExploreSnapshot(running=False, report=None)
    _wire(session, monkeypatch, "Command prompt\n", LIVE_PROMPT)
    resp = protocol._status_response(session, _ExploreServer(_ExploreStub(snap)))
    assert "explore_mode" not in resp
    # Default _Server has no runner — same omit.
    assert "explore_mode" not in _status(session, monkeypatch, "idle\n", LIVE_PROMPT)


def test_explore_mode_omitted_when_running_without_report(session, monkeypatch):
    """Running-but-no-report must not invent a mode."""
    from tw2002_aiclient.session import sector_explore as sx

    snap = sx.ExploreSnapshot(running=True, report=None)
    _wire(session, monkeypatch, "Command prompt\n", LIVE_PROMPT)
    resp = protocol._status_response(session, _ExploreServer(_ExploreStub(snap)))
    assert "explore_mode" not in resp


def test_decisions_reads_status_explore_mode(session, monkeypatch):
    """Consumer proof: decisions surfaces exploring_frontier from the wire."""
    from tw2002_aiclient.cockpit.decisions import compose_decisions_lines
    from tw2002_aiclient.session import sector_explore as sx

    report = sx.ExploreReport(
        world_id="w", started_at="t", min_sectors=1, intent="find_stardock"
    )
    snap = sx.ExploreSnapshot(running=True, report=report)
    _wire(session, monkeypatch, "Command prompt\n", LIVE_PROMPT)
    resp = protocol._status_response(session, _ExploreServer(_ExploreStub(snap)))
    joined = "\n".join(compose_decisions_lines(resp, width=60))
    assert "Density-scan before stepping" in joined
