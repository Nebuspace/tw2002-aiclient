"""WO-WIRE-IMPERATIVE-DENYLIST-RUNTIME-CHECK — startup + assert pin."""

from __future__ import annotations

import inspect

from tw2002_aiclient import app as app_mod
from tw2002_aiclient.cockpit.decisions import assert_authored_imperative_denylist


def test_assert_authored_imperative_denylist_green() -> None:
    assert_authored_imperative_denylist()


def test_app_main_wires_imperative_denylist_assert() -> None:
    src = inspect.getsource(app_mod.main)
    assert "assert_authored_imperative_denylist" in src
