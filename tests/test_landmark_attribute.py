"""WO-LANDMARK-ATTRIBUTE-LAST-KNOWN — the first product landmark writer.

**What this wires.** `world_model.add_landmark()` is the product-facing write
path into `landmarks`; `sector_explore._attribute_landmark()` is the consumer
that decides *whether* to call it. Before this WO nothing in the product ever
wrote a landmark: the only product write path is `write_from_state`
(`sector_explore.py`), and it maps `warps`/`port`/`threats` only — so #165's
union semantics protected a field with no writer, and `find_landmark_sectors`
read one.

**The asymmetry these pins exist to protect.** `landmarks` UNIONS, and the
product has no removal path at all. A skipped write costs one re-read; a wrong
write is permanent. So every test here that proves a refusal is more important
than the one that proves a write, and `test_a_forgotten_sector_writes_NOTHING`
is the single most load-bearing assertion in the file.

**Known limitation, pinned rather than hidden.** Both StarDock classes are
menus, reached by sending, and every send invalidates the memory — so in
ordinary play `_attribute_landmark` refuses. `test_the_documented_limitation_
is_real` pins that as current behaviour so it cannot be quietly "fixed" by
loosening the guard, which is the one change that would make it dangerous.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from tw2002_aiclient import world_model
from tw2002_aiclient.session import sector_explore
from tw2002_aiclient.session.session import Session

WORLD_ID = "landmark-probe"
SECTOR = 158
OTHER = 4309
STARDOCK_CLASS = "stardock_shipyard_listing"


def _marks(tmp_path, sector=SECTOR):
    rec = world_model.get_sector(WORLD_ID, sector, state_dir=tmp_path)
    return list((rec or {}).get("landmarks") or [])


# ------------------------------------------------ the writer


def test_add_landmark_writes_one(tmp_path):
    world_model.add_landmark(WORLD_ID, SECTOR, "StarDock", state_dir=tmp_path)
    assert _marks(tmp_path) == ["StarDock"]


def test_add_landmark_UNIONS_rather_than_replacing(tmp_path):
    """Inherited from #165 P1, re-pinned at this layer: the guarantee only
    matters if the product's own writer actually gets it."""
    world_model.add_landmark(WORLD_ID, SECTOR, "StarDock", state_dir=tmp_path)
    world_model.add_landmark(WORLD_ID, SECTOR, "Federation HQ", state_dir=tmp_path)
    assert _marks(tmp_path) == ["StarDock", "Federation HQ"]


def test_a_second_write_of_the_same_landmark_does_not_duplicate(tmp_path):
    world_model.add_landmark(WORLD_ID, SECTOR, "StarDock", state_dir=tmp_path)
    world_model.add_landmark(WORLD_ID, SECTOR, "stardock", state_dir=tmp_path)
    assert _marks(tmp_path) == ["StarDock"], "casefold dedup regressed"


def test_other_sectors_are_untouched(tmp_path):
    world_model.add_landmark(WORLD_ID, SECTOR, "StarDock", state_dir=tmp_path)
    assert _marks(tmp_path, OTHER) == []


@pytest.mark.parametrize(
    "bad", [True, False, "158", 158.0, None, [158]],
    ids=["true", "false", "str", "float", "none", "list"],
)
def test_a_junk_sector_RAISES_rather_than_returning_None(tmp_path, bad):
    """Loud, not quiet, and the distinction is the point: a quiet `None` here
    would be indistinguishable from the caller's legitimate "we do not know
    where we are, do not write" — the one signal that has to stay readable."""
    with pytest.raises(world_model.WorldModelError):
        world_model.add_landmark(WORLD_ID, bad, "StarDock", state_dir=tmp_path)


@pytest.mark.parametrize("bad", ["", "   ", None, 7, b"StarDock"], ids=["empty", "blank", "none", "int", "bytes"])
def test_a_junk_name_RAISES(tmp_path, bad):
    with pytest.raises(world_model.WorldModelError):
        world_model.add_landmark(WORLD_ID, SECTOR, bad, state_dir=tmp_path)


def test_a_raised_junk_write_left_nothing_behind(tmp_path):
    """Negative control for the two RAISES tests: raising is only useful if it
    also declined to write. An implementation that wrote and *then* raised
    would satisfy both of them."""
    with pytest.raises(world_model.WorldModelError):
        world_model.add_landmark(WORLD_ID, SECTOR, "", state_dir=tmp_path)
    assert _marks(tmp_path) == []


# ------------------------------------------------ the consumer's decision


class _Memory:
    """Minimal stand-in for the ONE method the seam consults.

    Deliberately not a full Session here: this is testing the *decision*, and
    the decision reads exactly one thing. `test_the_real_session_still_carries_
    the_probe` is what keeps that from excusing a regression in the real class.
    """

    def __init__(self, sector):
        self._sector = sector

    def last_known_sector(self):
        return self._sector


def test_a_known_sector_is_attributed(tmp_path):
    got = sector_explore._attribute_landmark(
        _Memory(SECTOR), WORLD_ID, STARDOCK_CLASS, state_dir=tmp_path
    )
    assert got == SECTOR
    assert _marks(tmp_path) == ["StarDock"]


def test_a_forgotten_sector_writes_NOTHING(tmp_path):
    """The load-bearing pin. `None` means we moved (or might have), and
    attributing anyway writes StarDock into a sector we are no longer in —
    permanently, since `landmarks` unions and nothing can remove it."""
    got = sector_explore._attribute_landmark(
        _Memory(None), WORLD_ID, STARDOCK_CLASS, state_dir=tmp_path
    )
    assert got is None
    assert _marks(tmp_path) == []
    assert _marks(tmp_path, OTHER) == []
    # and nothing was created anywhere in the world at all
    assert world_model.known_sector_count(WORLD_ID, state_dir=tmp_path) == 0


@pytest.mark.parametrize(
    "klass",
    ["main_command", "port_offer", "money_prompt", "game_select", "", "stardock", "stardock_equipment_listing"],
)
def test_a_non_stardock_screen_is_never_attributed(tmp_path, klass):
    """Includes `stardock_equipment_listing` on purpose — it LOOKS like a
    StarDock class and is not one (`classify._BLOCK_TITLE_SPECS` deliberately
    excludes it), so a prefix-matching implementation would adopt it."""
    got = sector_explore._attribute_landmark(
        _Memory(SECTOR), WORLD_ID, klass, state_dir=tmp_path
    )
    assert got is None
    assert world_model.known_sector_count(WORLD_ID, state_dir=tmp_path) == 0


#: Spelled out rather than read back from `sector_explore`. Iterating the
#: product's own set would make these tests a derived oracle: DELETING a class
#: from `STARDOCK_SCREEN_CLASSES` would shrink the loop, the assertions would
#: track the shrink, and the whole file would stay green while a real StarDock
#: screen silently stopped being attributed.
EXPECTED_STARDOCK_CLASSES = {"stardock_cargo_hold_quote", "stardock_shipyard_listing"}


def test_the_stardock_class_set_is_exactly_what_we_think_it_is():
    assert sector_explore.STARDOCK_SCREEN_CLASSES == EXPECTED_STARDOCK_CLASSES


@pytest.mark.parametrize("klass", sorted(EXPECTED_STARDOCK_CLASSES))
def test_each_stardock_class_attributes(tmp_path, klass):
    got = sector_explore._attribute_landmark(
        _Memory(SECTOR), WORLD_ID, klass, state_dir=tmp_path
    )
    assert got == SECTOR, f"{klass} did not attribute"
    assert _marks(tmp_path) == ["StarDock"]


def test_a_session_without_the_probe_is_tolerated(tmp_path):
    class _NoProbe:
        pass

    got = sector_explore._attribute_landmark(
        _NoProbe(), WORLD_ID, STARDOCK_CLASS, state_dir=tmp_path
    )
    assert got is None
    assert world_model.known_sector_count(WORLD_ID, state_dir=tmp_path) == 0


def test_the_real_session_still_carries_the_probe():
    """Closes the `getattr` hole the tolerance above opens: if `Session` lost
    `last_known_sector`, the seam would silently become a permanent no-op and
    every test in this file would still pass."""
    assert callable(getattr(Session, "last_known_sector", None))


# ------------------------------------------------ the gate returns the class


@pytest.mark.parametrize(
    "text,prompt",
    [("Command [TL=00:00:00]:[158] (?=Help)? :", "Command [TL=00:00:00]:[158] (?=Help)? :")],
)
def test_the_gate_hands_back_the_class_it_decided_on(text, prompt):
    """The seam depends on the gate's class, so the two must be one answer.
    Re-classifying at the call site would let them drift apart silently."""
    halt, klass = sector_explore._gate_screen(text, prompt)
    assert isinstance(klass, str) and klass
    assert halt is None or isinstance(halt, str)


def test_the_gate_still_halts_on_an_unrecognized_screen():
    halt, klass = sector_explore._gate_screen("<StarDock> Where to? (?=Help)", "<StarDock> Where to? (?=Help)")
    assert halt == sector_explore.HALT_UNRECOGNIZED_SCREEN
    assert klass != sector_explore.MOVEMENT_SCREEN_CLASS


# ------------------------------------------------ the closed side


def test_the_classifier_has_no_stardock_class_this_module_has_not_been_taught():
    """Tripwire for [[enumerate-the-closed-side]].

    `STARDOCK_SCREEN_CLASSES` is an explicit set, not a `stardock_` prefix
    rule, precisely so a new classifier class cannot be adopted by accident —
    adopting one wrongly writes a permanent landmark. But an explicit set rots
    the other way: a genuinely new StarDock screen would be silently ignored.
    This fails in that case and makes it a decision instead of a shrug.
    """
    src = pathlib.Path(sector_explore.classify_screen.__module__.replace(".", "/") + ".py")
    if not src.exists():  # resolved from the installed package instead
        import tw2002_aiclient.session.classify as _c

        src = pathlib.Path(_c.__file__)
    tree = ast.parse(src.read_text())
    literals = {
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and n.value.startswith("stardock")
        and "\n" not in n.value
    }
    unknown = literals - sector_explore.STARDOCK_SCREEN_CLASSES
    assert not unknown, (
        f"classify.py names StarDock screen class(es) {sorted(unknown)} that "
        f"sector_explore.STARDOCK_SCREEN_CLASSES does not list. Decide whether "
        f"each should attribute a landmark — do not just add it."
    )
    # positive control: the scan can actually see the two we DO know about
    assert sector_explore.STARDOCK_SCREEN_CLASSES <= literals, (
        "the AST scan found none of the known classes — the scan itself is broken, "
        "so its empty 'unknown' set proves nothing"
    )


# ------------------------------------------------ the documented limitation


def _live(tmp_path, monkeypatch):
    """A real `Session` with both wire halves stubbed. Real class throughout:
    the carry, the epoch and the memory interact, and a double would let this
    file confirm its own model of that interaction instead of the daemon's."""
    s = Session("127.0.0.1", 65000, "probe", str(tmp_path))
    monkeypatch.setattr(s.conn, "send_text", lambda *a, **k: None)
    monkeypatch.setattr(s.conn, "send_bytes", lambda *a, **k: None)
    return s


def test_landing_on_stardock_after_an_app_send_attributes(tmp_path, monkeypatch):
    """The whole point of the landing-screen rule.

    Read sector 158, send to dock, land on StarDock. The memory is correctly
    silent — but landing on a StarDock screen *proves* the send did not warp
    us, because a warp lands on a sector display. So the pre-send carry is
    safe to attribute here, and only here.
    """
    session = _live(tmp_path, monkeypatch)
    session.note_sector(SECTOR)
    session.send("D")
    assert session.last_known_sector() is None, "memory must still expire on a send"

    got = sector_explore._attribute_landmark(
        session, WORLD_ID, STARDOCK_CLASS, state_dir=tmp_path
    )
    assert got == SECTOR
    assert _marks(tmp_path) == ["StarDock"]


def test_the_carry_does_not_widen_last_known_sector(tmp_path, monkeypatch):
    """The carry must stay INERT. If it leaked into `last_known_sector()` it
    would hand every other consumer the stale value #169 exists to refuse."""
    session = _live(tmp_path, monkeypatch)
    session.note_sector(SECTOR)
    session.send("D")
    assert session.last_known_sector() is None
    assert session.sector_before_last_send() == SECTOR


def test_landing_on_stardock_after_a_HUMAN_send_does_not_attribute(tmp_path, monkeypatch):
    """`send_raw` files no carry. A human's keystrokes are opaque to us, so
    the app declines to reason about what they did — even though the landing
    screen would technically prove it. Fail-closed on the path we do not own."""
    session = _live(tmp_path, monkeypatch)
    session.note_sector(SECTOR)
    try:
        session.send_raw(b"D\r")
    except Exception:
        pass
    got = sector_explore._attribute_landmark(
        session, WORLD_ID, STARDOCK_CLASS, state_dir=tmp_path
    )
    assert got is None
    assert world_model.known_sector_count(WORLD_ID, state_dir=tmp_path) == 0


def test_a_reconnect_with_a_LIVE_memory_files_no_carry(tmp_path, monkeypatch):
    """The case the first version of this file missed, found by falsification.

    Injecting `carry=True` into `reconnect` did NOT turn the test below red,
    because that test sends first — which kills the memory, so the carry
    condition is already false by the time reconnect runs and the bug is
    masked. The dangerous sequence is a reconnect while the memory is still
    LIVE: a carry filed there would let a StarDock landing attribute to a
    sector from *before the connection dropped*, which is precisely the
    permanent wrong write this whole design exists to prevent.

    Reconnect must never file a carry, because a fresh connection is the one
    event that proves nothing about where we are.
    """
    session = _live(tmp_path, monkeypatch)
    session.note_sector(SECTOR)
    assert session.last_known_sector() == SECTOR, "memory must be LIVE for this to test anything"
    monkeypatch.setattr(session.conn, "close", lambda *a, **k: None)
    monkeypatch.setattr(session, "connect", lambda *a, **k: None, raising=False)
    try:
        session.reconnect()
    except Exception:
        pass
    assert session.sector_before_last_send() is None, "reconnect filed a carry from a live memory"
    assert session.last_known_sector() is None
    got = sector_explore._attribute_landmark(
        session, WORLD_ID, STARDOCK_CLASS, state_dir=tmp_path
    )
    assert got is None
    assert world_model.known_sector_count(WORLD_ID, state_dir=tmp_path) == 0


def test_a_reconnect_clears_the_carry(tmp_path, monkeypatch):
    """A fresh connection loses position entirely — the carry must not survive
    it and re-attribute against a world we may no longer be in."""
    session = _live(tmp_path, monkeypatch)
    session.note_sector(SECTOR)
    session.send("D")
    assert session.sector_before_last_send() == SECTOR
    monkeypatch.setattr(session.conn, "close", lambda *a, **k: None)
    monkeypatch.setattr(session, "connect", lambda *a, **k: None, raising=False)
    try:
        session.reconnect()
    except Exception:
        pass
    assert session.sector_before_last_send() is None
    got = sector_explore._attribute_landmark(
        session, WORLD_ID, STARDOCK_CLASS, state_dir=tmp_path
    )
    assert got is None
    assert world_model.known_sector_count(WORLD_ID, state_dir=tmp_path) == 0


def test_a_non_stardock_landing_leaves_the_world_untouched(tmp_path, monkeypatch):
    """The fail-closed direction, driven through the real Session rather than
    a double: an ordinary send whose landing screen we cannot vouch for must
    attribute nothing, even though a carry exists."""
    session = _live(tmp_path, monkeypatch)
    session.note_sector(SECTOR)
    session.send("1")  # a warp
    assert session.sector_before_last_send() == SECTOR  # carry exists...
    got = sector_explore._attribute_landmark(
        session, WORLD_ID, "main_command", state_dir=tmp_path
    )
    assert got is None, "a sector display landing must never attribute"
    assert world_model.known_sector_count(WORLD_ID, state_dir=tmp_path) == 0


def test_two_sends_without_a_stardock_landing_discard_the_carry(tmp_path, monkeypatch):
    """The carry is ONE slot and is only filled from a currently-valid memory.
    After a second send the memory was already dead, so nothing is carried —
    the chain breaks by itself rather than dragging a two-hops-old sector."""
    session = _live(tmp_path, monkeypatch)
    session.note_sector(SECTOR)
    session.send("1")
    session.send("2")
    assert session.sector_before_last_send() is None
    got = sector_explore._attribute_landmark(
        session, WORLD_ID, STARDOCK_CLASS, state_dir=tmp_path
    )
    assert got is None
    assert world_model.known_sector_count(WORLD_ID, state_dir=tmp_path) == 0


def test_multi_step_menu_navigation_carries_forward(tmp_path, monkeypatch):
    """Attribution re-notes the proven sector, so a second StarDock screen one
    send later still attributes — without any special case for menu depth."""
    session = _live(tmp_path, monkeypatch)
    session.note_sector(SECTOR)
    session.send("D")
    assert sector_explore._attribute_landmark(
        session, WORLD_ID, STARDOCK_CLASS, state_dir=tmp_path
    ) == SECTOR
    assert session.last_known_sector() == SECTOR, "proof of position must re-establish the memory"

    session.send("S")  # deeper into the menus
    assert sector_explore._attribute_landmark(
        session, WORLD_ID, "stardock_cargo_hold_quote", state_dir=tmp_path
    ) == SECTOR
    assert _marks(tmp_path) == ["StarDock"]


def test_a_wrong_turn_out_of_the_menus_stops_the_chain(tmp_path, monkeypatch):
    """Negative control for the carry-forward above: once a screen we cannot
    vouch for appears, the next StarDock landing must NOT resurrect the chain
    from a sector two sends stale."""
    session = _live(tmp_path, monkeypatch)
    session.note_sector(SECTOR)
    session.send("D")
    sector_explore._attribute_landmark(session, WORLD_ID, STARDOCK_CLASS, state_dir=tmp_path)
    session.send("Q")            # left the menus; landing is a sector display
    sector_explore._attribute_landmark(session, WORLD_ID, "main_command", state_dir=tmp_path)
    session.send("9")            # then warped somewhere
    got = sector_explore._attribute_landmark(
        session, WORLD_ID, STARDOCK_CLASS, state_dir=tmp_path
    )
    assert got is None, "the chain resurrected a stale sector after leaving the menus"
