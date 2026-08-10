"""WO-CLEANUP-PORT-ECONOMICS-LEDGER-FLIP — boot wires hypothesis-tag assert."""

from __future__ import annotations

import inspect

from tw2002_aiclient import app as app_mod
from tw2002_aiclient.port_economics import (
    all_hypothesis_params,
    assert_all_unverified_tagged,
)


def test_assert_all_unverified_tagged_green() -> None:
    assert_all_unverified_tagged()
    assert len(all_hypothesis_params()) >= 1


def test_app_main_wires_hypothesis_tag_assert() -> None:
    src = inspect.getsource(app_mod.main)
    assert "assert_all_unverified_tagged" in src
    assert "all_hypothesis_params" in src
