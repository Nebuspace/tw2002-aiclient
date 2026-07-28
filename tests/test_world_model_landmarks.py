"""WO-WM-LANDMARKS-WRITE P1 — `landmarks` unions rather than replaces.

**What the union is defending against, concretely.** A landmark is recorded when
a screen identifies one. Nothing the trainer can read ever says "there is
positively no landmark here" — a sector display that does not mention StarDock is
*silence*, not a denial. Under this module's ordinary replace semantics, the very
next ordinary write carrying `landmarks` would erase what an earlier observation
found, and the erasure is indistinguishable from never having found it: the
lookup returns `[]` either way, and every test that supplies its own landmarks
stays green. Canon states the requirement ("a plain visit never clears them");
until now it was a rule a writer had to remember, and this makes it structural.

The tests below are written so that **replacing the union with a plain assignment
turns them red** — that mutation is the whole point of the file, not a hypothetical.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient import world_model
from tw2002_aiclient.explore import find_landmark_sectors

WORLD = "w-landmarks"


def _put(tmp_path, sector_id, **fields):
    return world_model.upsert_sector(
        WORLD, {"sector_id": sector_id, **fields}, state_dir=tmp_path
    )


def _marks(tmp_path, sector_id):
    return world_model.get_sector(WORLD, sector_id, state_dir=tmp_path)["landmarks"]


# ------------------------------------------------------- the load-bearing rule


def test_a_later_write_cannot_clear_a_landmark(tmp_path):
    """THE test. A plain visit carrying an empty list must not erase StarDock."""
    _put(tmp_path, 1, landmarks=["stardock"])
    _put(tmp_path, 1, landmarks=[])
    assert _marks(tmp_path, 1) == ["stardock"]


def test_a_later_write_with_a_different_landmark_keeps_both(tmp_path):
    _put(tmp_path, 1, landmarks=["stardock"])
    _put(tmp_path, 1, landmarks=["class_zero"])
    assert _marks(tmp_path, 1) == ["stardock", "class_zero"]


def test_an_absent_landmarks_key_still_leaves_them_untouched(tmp_path):
    """The pre-existing "additive" half, pinned here because the union must not
    be what accidentally provides it — a warps-only write touches nothing."""
    _put(tmp_path, 1, landmarks=["stardock"])
    _put(tmp_path, 1, warps=[2, 3])
    assert _marks(tmp_path, 1) == ["stardock"]


def test_the_reader_finds_it_after_an_erasing_write(tmp_path):
    """End to end through the real consumer: `find_landmark_sectors` is what
    the GOALS stardock surface calls, so its answer is the one that matters."""
    _put(tmp_path, 41, landmarks=["stardock"])
    _put(tmp_path, 41, landmarks=[])
    assert find_landmark_sectors(WORLD, "StarDock", state_dir=tmp_path) == [41]


# ------------------------------------------------------- dedup and hygiene


def test_dedup_is_casefold_because_the_reader_casefolds(tmp_path):
    """`find_landmark_sectors` casefolds both sides, so `StarDock` and
    `stardock` are ONE landmark to the reader. Storing both would make the
    record disagree with every lookup made against it."""
    _put(tmp_path, 1, landmarks=["stardock"])
    _put(tmp_path, 1, landmarks=["StarDock", "STARDOCK"])
    assert _marks(tmp_path, 1) == ["stardock"]


def test_existing_order_is_stable_and_new_tokens_append(tmp_path):
    _put(tmp_path, 1, landmarks=["stardock", "class_zero"])
    _put(tmp_path, 1, landmarks=["class_zero", "ferrengi", "stardock"])
    assert _marks(tmp_path, 1) == ["stardock", "class_zero", "ferrengi"]


@pytest.mark.parametrize(
    "junk", [None, 0, 1.5, object(), {}, [""], [None, "stardock"]],
    ids=["none", "int", "float", "obj", "dict", "empty-str", "none-in-list"],
)
def test_junk_never_corrupts_the_set(tmp_path, junk):
    """A landmarks list is a list of names; anything else could only ever fail
    to match a lookup, so it is dropped rather than stored."""
    _put(tmp_path, 1, landmarks=["stardock"])
    _put(tmp_path, 1, landmarks=junk)
    assert "stardock" in _marks(tmp_path, 1)
    assert all(isinstance(m, str) and m for m in _marks(tmp_path, 1))


def test_a_bare_string_is_refused_not_shredded_per_character(tmp_path):
    """A string is iterable. Iterating it would store one landmark per
    CHARACTER — `['s','t','a',...]` — which no lookup could ever match and
    which would look like data corruption rather than a caller's type error."""
    _put(tmp_path, 1, landmarks="stardock")
    assert _marks(tmp_path, 1) == []


def test_the_first_write_still_records(tmp_path):
    """Negative control for the whole file: a union that returned the existing
    set unchanged would pass every "cannot clear" test above and record nothing."""
    _put(tmp_path, 7, landmarks=["stardock"])
    assert _marks(tmp_path, 7) == ["stardock"]
    assert find_landmark_sectors(WORLD, "stardock", state_dir=tmp_path) == [7]


def test_other_fields_still_REPLACE(tmp_path):
    """The union is scoped to `landmarks` alone. If it leaked into `warps`,
    stale warps would accumulate forever and routing would plan hops that do
    not exist — a far worse failure than the one being fixed."""
    _put(tmp_path, 1, warps=[2, 3])
    _put(tmp_path, 1, warps=[4])
    assert world_model.get_sector(WORLD, 1, state_dir=tmp_path)["warps"] == [4]


def test_write_from_state_still_refuses_landmarks(tmp_path):
    """The refusal is deliberate and canon-cited, and this WO does NOT widen it:
    the raw per-visit state read must stay unable to touch landmarks, so the
    union is a second line of defence rather than the only one."""
    world_model.write_from_state(
        WORLD, {"sector": 1, "landmarks": ["stardock"]}, state_dir=tmp_path
    )
    rec = world_model.get_sector(WORLD, 1, state_dir=tmp_path)
    assert rec["landmarks"] == []
