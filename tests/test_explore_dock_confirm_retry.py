"""WO-FIX-EXPLORE-PORT-DOCK-CONFIRM-FAILED pins."""

from __future__ import annotations

import inspect

from tw2002_aiclient.session import sector_explore as sx


def test_live_ansi_qty_prompt_matches_after_strip():
    # From joes_tavern live buffer (SGR without ESC in log extract).
    raw = "How many holds of [1;36mFuel Ore[0;35m do you want to buy [[1;33m25[0;35m]? "
    plain = sx._plain_prompt(raw)
    assert sx._PORT_QUANTITY_PROMPT_RE.fullmatch(plain), plain


def test_send_dock_letter_retries_unstable_idle():
    src = inspect.getsource(sx.ExploreRunner._send_dock_letter)
    assert "retry_unstable_idle=True" in src
