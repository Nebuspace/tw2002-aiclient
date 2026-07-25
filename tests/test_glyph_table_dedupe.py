"""Proof lane for ``WO-AUDIT-GLYPH-TABLE-DEDUPE``: ``screens.py``'s launcher
thin-glyph tables (``_GLYPHS_UNICODE``/``_GLYPHS_ASCII``) used to byte-
duplicate ``cockpit.draw``'s ``THIN_UNICODE``/``THIN_ASCII`` for the six
box-drawing keys (``tl``/``tr``/``bl``/``br``/``h``/``v``) plus carry one
extra key (``sel``, the launcher's own row-picker triangle -- the cockpit
chrome has no selection-triangle concept). They now import-and-extend
``draw``'s tables instead of re-typing the glyphs, so the two tables cannot
drift. Four proof legs:

1. Byte-parity pin -- every shared key's value is identical to ``draw``'s
   table, and ``sel`` is present with the exact expected literal, in both
   variants.
2. Single-source pin -- the shared-key set is EXACTLY ``draw``'s key set
   plus ``sel`` (by construction, via dict-spread), so a future key added to
   ``draw``'s table flows through automatically and a divergent local key
   re-appearing would widen this set and fail loudly.
3. Render-parity smoke -- ``_glyph_set()`` (the launcher's selector) returns
   the expected literals under both ``TW2002_ASCII`` states, gated on the
   real ``_unicode_ok()`` selector (not re-implemented here).
4. Existing-suite sweep -- ``test_play_chrome_nav.py``, ``test_safe_addstr_
   choke.py``, and ``test_spectate_no_send.py`` all pass unchanged, proving
   the dedupe is render-identical (zero fixture updates expected).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tw2002_aiclient import screens
from tw2002_aiclient.cockpit import draw as cockpit_draw

REPO_ROOT = Path(__file__).resolve().parents[1]

_BOX_KEYS = ("tl", "tr", "bl", "br", "h", "v")


def test_shared_box_keys_are_byte_identical_to_draw_unicode() -> None:
    for key in _BOX_KEYS:
        assert screens._GLYPHS_UNICODE[key] == cockpit_draw.THIN_UNICODE[key]


def test_shared_box_keys_are_byte_identical_to_draw_ascii() -> None:
    for key in _BOX_KEYS:
        assert screens._GLYPHS_ASCII[key] == cockpit_draw.THIN_ASCII[key]


def test_sel_key_literals_unchanged() -> None:
    # The launcher's own addition -- not sourced from draw.py -- pinned
    # against literals since there is no upstream table to derive it from.
    assert screens._GLYPHS_UNICODE["sel"] == "▸"  # "▸"
    assert screens._GLYPHS_ASCII["sel"] == ">"


def test_unicode_table_key_set_is_draw_keys_plus_sel() -> None:
    # A future key added to draw.THIN_UNICODE flows through automatically; a
    # divergent local key re-appearing widens this set and fails loudly.
    assert set(screens._GLYPHS_UNICODE) == set(cockpit_draw.THIN_UNICODE) | {"sel"}


def test_ascii_table_key_set_is_draw_keys_plus_sel() -> None:
    assert set(screens._GLYPHS_ASCII) == set(cockpit_draw.THIN_ASCII) | {"sel"}


def test_glyph_set_selects_unicode_table_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TW2002_ASCII", raising=False)
    assert screens._unicode_ok() is True
    glyphs = screens._glyph_set()
    assert glyphs["tl"] == "╭"  # "╭"
    assert glyphs["sel"] == "▸"  # "▸"


def test_glyph_set_selects_ascii_table_under_tw2002_ascii(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TW2002_ASCII", "1")
    assert screens._unicode_ok() is False
    glyphs = screens._glyph_set()
    assert glyphs["tl"] == "+"
    assert glyphs["sel"] == ">"


@pytest.mark.parametrize(
    "test_path",
    [
        "tests/test_play_chrome_nav.py",
        "tests/test_safe_addstr_choke.py",
        "tests/test_spectate_no_send.py",
    ],
)
def test_existing_suite_sweep_unchanged(test_path: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_path, "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"{test_path} regressed under the glyph-table dedupe:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
