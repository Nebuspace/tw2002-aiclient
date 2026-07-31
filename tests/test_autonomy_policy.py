"""Pins for the confirm-only early-game autonomy offer policy."""

from __future__ import annotations

import inspect

from tw2002_aiclient import autonomy_policy
from tw2002_aiclient.autonomy_policy import choose_offer


def _status(*candidates, stardock_found=False):
    return {
        "stardock_found": stardock_found,
        "focus": {"candidates": list(candidates)},
    }


def test_preference_order_is_explore_then_chain_then_upgrade():
    explore = choose_offer(
        _status(
            {"kind": "run_chain", "gated": True, "gate_reason": "route unavailable"},
            {"kind": "upgrade", "gated": False},
        )
    )
    chain = choose_offer(
        _status(
            {"kind": "run_chain", "gated": False, "ev_per_turn": 80.0},
            {"kind": "upgrade", "gated": False},
            stardock_found=True,
        )
    )
    upgrade = choose_offer(
        _status({"kind": "upgrade", "gated": False}, stardock_found=True)
    )

    assert (explore.kind, explore.gated) == ("explore", False)
    assert chain.kind == "run_chain"
    assert upgrade.kind == "upgrade"


def test_incomplete_or_hostile_focus_idles_honestly():
    assert choose_offer({}).kind == "idle"
    assert "unavailable" in choose_offer({"focus": {"candidates": [None]}}).reason
    assert choose_offer({"focus": {"candidates": [{"kind": "unknown", "gated": False}]}}).kind == "idle"


def test_gated_upgrade_remains_an_offer_when_stardock_is_known():
    offer = choose_offer(
        _status(
            {
                "kind": "upgrade",
                "gated": True,
                "gate_reason": "empty holds unknown",
            },
            stardock_found=True,
        )
    )

    assert (offer.kind, offer.gated, offer.reason) == (
        "upgrade",
        True,
        "empty holds unknown",
    )


def test_hold_arm_absence_omits_upgrade_offers():
    offer = choose_offer(
        _status({"kind": "upgrade", "gated": False}, stardock_found=True),
        has_hold_arm=False,
    )

    assert offer.kind == "idle"


def test_policy_has_no_adapter_or_arm_boundary():
    source = inspect.getsource(autonomy_policy)
    assert "adapters" not in source
    assert "_start(" not in source
    assert "_arm(" not in source
