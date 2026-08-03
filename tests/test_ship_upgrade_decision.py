"""TW-30 ship-upgrade decision engine — unit coverage for all five §24 learnings."""

from tw2002_aiclient.ship_upgrade_decision import (
    LoopEconomics,
    PlayerState,
    ShipSpec,
    choose_upgrade,
    evaluate_candidate,
    holds_per_turn,
    payback_turns,
    remaining_productive_turns,
)


def _merchant_man():
    return ShipSpec(
        name="Merchant Cruiser",
        cost=50_000,
        holds=75,
        turns_per_warp=3,
        fighters=100,
        shields=50,
        commissioned=True,
    )


def _imperial_galleon():
    return ShipSpec(
        name="Imperial Galleon",
        cost=200_000,
        holds=150,
        turns_per_warp=3,
        fighters=200,
        shields=100,
        commissioned=True,
    )


def _cargo_barge():
    """Same holds as galleon but worse warps — must rank lower."""
    return ShipSpec(
        name="Cargo Barge",
        cost=180_000,
        holds=150,
        turns_per_warp=6,
        fighters=50,
        shields=20,
        commissioned=True,
    )


def _ss_250():
    """Expensive huge-hold ship — fails ROI at 57 turns left."""
    return ShipSpec(
        name="Super Freighter 250",
        cost=400_000,
        holds=250,
        turns_per_warp=3,
        fighters=10,
        shields=10,
        commissioned=True,
    )


def _slaver_locked():
    return ShipSpec(
        name="Slaver",
        cost=100_000,
        holds=100,
        turns_per_warp=3,
        fighters=300,
        shields=50,
        alignment_req=1000,
        commissioned=False,
    )


def _glass_cannon():
    return ShipSpec(
        name="Glass Cannon",
        cost=80_000,
        holds=120,
        turns_per_warp=3,
        fighters=0,
        shields=0,
        commissioned=True,
    )


def _loop_fat():
    return LoopEconomics(
        margin_per_hold=200,
        turns_per_cycle=10,
        stock_capacity=300,
    )


def test_remaining_productive_turns_respects_reserve():
    state = PlayerState(turns_left=57, current_holds=40, turn_reserve=5)
    assert remaining_productive_turns(state) == 52


def test_roi_vs_budget_57_turns_rejects_250_hold():
    """§24 key fix: 57 turns left → do NOT recommend a 250-hold upgrade."""
    state = PlayerState(turns_left=57, current_holds=40, turn_reserve=0)
    loop = LoopEconomics(margin_per_hold=150, turns_per_cycle=12, stock_capacity=300)
    decision = evaluate_candidate(_ss_250(), state, loop, cost_per_hold=500)
    assert decision.recommend is False
    assert "roi_vs_budget" in decision.flags
    assert decision.projected_payback is not None
    assert decision.projected_payback > 57
    hold = choose_upgrade([_ss_250()], state, loop, cost_per_hold=500)
    assert hold.recommend is False
    assert "HOLD" in hold.rationale


def test_alignment_rank_filter_blocks_uncommissioned():
    state = PlayerState(turns_left=500, current_holds=40)
    loop = _loop_fat()
    decision = evaluate_candidate(_slaver_locked(), state, loop)
    assert decision.recommend is False
    assert "alignment_rank" in decision.flags


def test_holds_per_turn_ranks_galleon_above_barge():
    loop = _loop_fat()
    g = holds_per_turn(_imperial_galleon(), loop)
    b = holds_per_turn(_cargo_barge(), loop)
    assert g > b


def test_choose_upgrade_picks_better_warp_at_equal_holds():
    state = PlayerState(turns_left=800, current_holds=40)
    loop = LoopEconomics(margin_per_hold=200, turns_per_cycle=8, stock_capacity=300)
    decision = choose_upgrade(
        [_cargo_barge(), _imperial_galleon()],
        state,
        loop,
        cost_per_hold=100,
    )
    assert decision.recommend is True
    assert decision.ship is not None
    assert decision.ship.name == "Imperial Galleon"


def test_loop_stock_match_flags_needs_chains():
    state = PlayerState(turns_left=800, current_holds=40)
    loop = LoopEconomics(margin_per_hold=200, turns_per_cycle=8, stock_capacity=100)
    decision = evaluate_candidate(_imperial_galleon(), state, loop)  # 150 holds
    assert decision.recommend is False
    assert "needs_chains" in decision.flags
    assert "TW-21" in decision.rationale


def test_defense_floor_on_hostile_server():
    state = PlayerState(
        turns_left=800,
        current_holds=40,
        hostile_or_pvp=True,
        current_fighters=50,
    )
    loop = _loop_fat()
    decision = evaluate_candidate(_glass_cannon(), state, loop)
    assert decision.recommend is False
    assert "defense_floor" in decision.flags


def test_defense_floor_ignored_on_peaceful():
    state = PlayerState(turns_left=800, current_holds=40, hostile_or_pvp=False)
    loop = LoopEconomics(margin_per_hold=300, turns_per_cycle=6, stock_capacity=300)
    # Cheap relative to fat margin → should recommend despite 0 fighters when peaceful
    cheap = ShipSpec(
        name="Peace Scout",
        cost=10_000,
        holds=90,
        turns_per_warp=3,
        fighters=0,
        shields=0,
        commissioned=True,
    )
    decision = evaluate_candidate(cheap, state, loop, cost_per_hold=50)
    assert decision.recommend is True


def test_choose_upgrade_prefers_affordable_commissioned_over_slaver():
    state = PlayerState(turns_left=800, current_holds=40)
    loop = LoopEconomics(margin_per_hold=250, turns_per_cycle=8, stock_capacity=300)
    decision = choose_upgrade(
        [_slaver_locked(), _merchant_man()],
        state,
        loop,
        cost_per_hold=100,
    )
    assert decision.recommend is True
    assert decision.ship.name == "Merchant Cruiser"


def test_payback_turns_positive_for_upgrade():
    state = PlayerState(turns_left=800, current_holds=40)
    loop = LoopEconomics(margin_per_hold=200, turns_per_cycle=10, stock_capacity=300)
    pb = payback_turns(_merchant_man(), state, loop, cost_per_hold=100)
    assert pb is not None
    assert pb > 0


def test_compose_upgrade_decision_lines_recommend_and_hold():
    from tw2002_aiclient.ship_upgrade_decision import (
        UpgradeDecision,
        compose_upgrade_decision_lines,
    )

    yes = UpgradeDecision(
        recommend=True,
        ship=_merchant_man(),
        rationale="Merchant Cruiser: payback ok",
        projected_payback=10.0,
        flags=(),
    )
    lines = compose_upgrade_decision_lines(yes, width=40)
    assert lines[0].startswith("Upgrade: Merchant")
    assert "payback" in lines[1].lower() or "Merchant" in lines[1]

    hold = UpgradeDecision(
        recommend=False,
        ship=None,
        rationale="HOLD — ROI",
        projected_payback=None,
        flags=("roi_vs_budget",),
    )
    hlines = compose_upgrade_decision_lines(hold, width=40)
    assert hlines[0] == "Upgrade: HOLD"


def test_upgrade_decision_from_status_catalog_path():
    from tw2002_aiclient.ship_upgrade_decision import upgrade_decision_from_status

    status = {
        "upgrade_catalog": [
            {
                "name": "Merchant Cruiser",
                "cost": 50_000,
                "holds": 75,
                "turns_per_warp": 3,
                "fighters": 100,
                "shields": 50,
                "commissioned": True,
            }
        ],
        "upgrade_player": {"turns_left": 800, "current_holds": 40},
        "upgrade_loop": {
            "margin_per_hold": 250,
            "turns_per_cycle": 8,
            "stock_capacity": 300,
        },
        "upgrade_cost_per_hold": 100,
    }
    decision = upgrade_decision_from_status(status)
    assert decision is not None
    assert decision.recommend is True
    assert decision.ship is not None
    assert decision.ship.name == "Merchant Cruiser"


def test_decisions_panel_surfaces_upgrade_decision():
    from tw2002_aiclient.cockpit.decisions import compose_decisions_lines

    status = {
        "upgrade_decision": {
            "recommend": True,
            "rationale": "Merchant Cruiser: payback 12.0 within productive 800",
            "ship": {"name": "Merchant Cruiser", "cost": 1, "holds": 75,
                     "turns_per_warp": 3, "fighters": 1, "shields": 1},
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert any("Upgrade" in line for line in lines)
    assert any("Merchant" in line or "payback" in line.lower() for line in lines)
