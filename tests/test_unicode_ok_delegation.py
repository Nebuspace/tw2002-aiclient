"""Proof lane for ``WO-AUDIT-UNICODE-OK-DOCSTRING``: ``screens._unicode_ok``
used to be a second, independent implementation of ``cockpit.draw``'s
``unicode_ok`` -- same ``TW2002_ASCII`` flag, separately typed -- and its
docstring had drifted to claim an "otherwise prefer UTF-8-capable locale"
fallback that neither copy ever performed. It is now a thin delegate, so the
two cannot split-brain on a future flag change. Three proof legs:

1. Delegation pin -- with ``draw.unicode_ok`` monkeypatched to return a
   sentinel object no boolean re-implementation could produce, the launcher's
   selector returns THAT sentinel and the patched target records the call. A
   re-typed local copy fails this leg.
2. Unconditional-delegation pin -- leg 1 holds under every ``TW2002_ASCII``
   state, so a "delegate, but short-circuit on the env var first" hybrid
   (which would re-open the drift) fails too.
3. Equivalence pin -- the flag's truth table itself, across the env grid that
   licensed the delegation: ONLY a value stripping to exactly ``"1"`` forces
   ASCII; unset/empty/``"0"``/``"01"``/``"true"``/``"1 1"`` all stay Unicode.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient import screens
from tw2002_aiclient.cockpit import draw as cockpit_draw

_SENTINEL = object()

# Only a value stripping to exactly "1" forces ASCII; ``None`` = unset.
_ENV_GRID = (
    (None, True),
    ("", True),
    ("1", False),
    (" 1 ", False),
    ("\t1\n", False),
    (" 1", False),
    ("1 ", False),
    ("0", True),
    ("2", True),
    ("01", True),
    ("1 1", True),
    ("true", True),
    ("TRUE", True),
    ("  ", True),
    ("\n", True),
)


def _set_flag(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv("TW2002_ASCII", raising=False)
    else:
        monkeypatch.setenv("TW2002_ASCII", value)


def test_unicode_ok_delegates_to_draw(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple] = []

    def fake_unicode_ok(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return _SENTINEL

    monkeypatch.setattr(cockpit_draw, "unicode_ok", fake_unicode_ok)
    # Identity, not equality: no independent bool-returning copy of the
    # predicate could hand back this object.
    assert screens._unicode_ok() is _SENTINEL
    assert calls == [((), {})]


@pytest.mark.parametrize("value", [None, "", "1", " 1 ", "0", "true"])
def test_delegation_is_unconditional_across_env(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    # Guards against a hybrid that delegates only on the Unicode branch and
    # keeps a local ASCII short-circuit -- that is the drift this WO closed.
    _set_flag(monkeypatch, value)
    monkeypatch.setattr(cockpit_draw, "unicode_ok", lambda: _SENTINEL)
    assert screens._unicode_ok() is _SENTINEL


@pytest.mark.parametrize("value,expected", _ENV_GRID)
def test_flag_truth_table(
    monkeypatch: pytest.MonkeyPatch, value: str | None, expected: bool
) -> None:
    _set_flag(monkeypatch, value)
    assert screens._unicode_ok() is expected
    assert cockpit_draw.unicode_ok() is expected
