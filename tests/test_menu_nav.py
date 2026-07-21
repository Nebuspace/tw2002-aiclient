"""TW-28 menu_nav localize + plan_nav — pure tests on synthetic maps."""

from twclient import game_knowledge
from twclient.menu_nav import localize, plan_nav
from twclient.menu_sig import menu_signature

SCREEN_A = "=== Computer ===\n(1) Status\n(2) Ship\n"
SCREEN_B = "=== Ship Status ===\nHolds: 50\n(Q) Quit\n"
SCREEN_OFF = "=== Totally Unknown Prompt ===\n(Z) Zap\n"


def _seed_map(path, screen_text, label, *edge_specs):
    """Upsert node for screen_text; optional edges as (from_sig, key, to_sig, kind)."""
    sig = menu_signature(screen_text)
    game_knowledge.upsert_menu_node(path, sig, label=label)
    for frm, key, to, kind in edge_specs:
        game_knowledge.upsert_menu_edge(path, frm, key, to, kind=kind)
    return sig


def test_localize_hit(tmp_path):
    path = tmp_path / "game_knowledge.json"
    sig = _seed_map(path, SCREEN_A, "Computer")
    node = localize(SCREEN_A, path)
    assert node is not None
    assert node["signature"] == sig
    assert node["label"] == "Computer"


def test_localize_whitespace_normalized_same_as_crawler(tmp_path):
    path = tmp_path / "game_knowledge.json"
    sig = _seed_map(path, SCREEN_A, "Computer")
    # trailing padding / blank lines must not miss
    padded = SCREEN_A.rstrip() + "   \n\n"
    node = localize(padded, path)
    assert node is not None
    assert node["signature"] == sig


def test_localize_miss_off_map(tmp_path):
    path = tmp_path / "game_knowledge.json"
    _seed_map(path, SCREEN_A, "Computer")
    assert localize(SCREEN_OFF, path) is None


def test_localize_empty_store_off_map(tmp_path):
    path = tmp_path / "game_knowledge.json"
    assert localize(SCREEN_A, path) is None


def test_plan_nav_end_to_end(tmp_path):
    path = tmp_path / "game_knowledge.json"
    sig_a = _seed_map(path, SCREEN_A, "Computer")
    sig_b = _seed_map(path, SCREEN_B, "Ship")
    game_knowledge.upsert_menu_edge(path, sig_a, "2", sig_b, kind="nav", desc="Ship")

    result = plan_nav(SCREEN_A, sig_b, path)
    assert result["ok"] is True
    assert result["reason"] is None
    assert result["from_sig"] == sig_a
    assert [s["key"] for s in result["steps"]] == ["2"]
    assert result["steps"][0]["to_node"] == sig_b
    assert result["steps"][0]["kind"] == "nav"


def test_plan_nav_already_there(tmp_path):
    path = tmp_path / "game_knowledge.json"
    sig_a = _seed_map(path, SCREEN_A, "Computer")
    result = plan_nav(SCREEN_A, sig_a, path)
    assert result["ok"] is True
    assert result["steps"] == []


def test_plan_nav_off_map(tmp_path):
    path = tmp_path / "game_knowledge.json"
    sig_a = _seed_map(path, SCREEN_A, "Computer")
    result = plan_nav(SCREEN_OFF, sig_a, path)
    assert result["ok"] is False
    assert result["reason"] == "off_map"
    assert result["steps"] is None


def test_plan_nav_unreachable(tmp_path):
    path = tmp_path / "game_knowledge.json"
    sig_a = _seed_map(path, SCREEN_A, "Computer")
    sig_b = _seed_map(path, SCREEN_B, "Ship")
    # no edges between them
    result = plan_nav(SCREEN_A, sig_b, path)
    assert result["ok"] is False
    assert result["reason"] == "unreachable"
    assert result["from_sig"] == sig_a
    assert result["steps"] is None


def test_plan_nav_shortest_of_branch(tmp_path):
    path = tmp_path / "game_knowledge.json"
    sig_a = _seed_map(path, SCREEN_A, "A")
    mid1 = "mid1sig____________"[:16]
    mid2 = "mid2sig____________"[:16]
    short = "shortsig___________"[:16]
    z = "zsig________________"[:16]
    for s, lab in [(mid1, "m1"), (mid2, "m2"), (short, "s"), (z, "z")]:
        game_knowledge.upsert_menu_node(path, s, label=lab)
    game_knowledge.upsert_menu_edge(path, sig_a, "1", mid1, kind="nav")
    game_knowledge.upsert_menu_edge(path, mid1, "2", mid2, kind="nav")
    game_knowledge.upsert_menu_edge(path, mid2, "3", z, kind="nav")
    game_knowledge.upsert_menu_edge(path, sig_a, "9", short, kind="nav")
    game_knowledge.upsert_menu_edge(path, short, "8", z, kind="info")

    result = plan_nav(SCREEN_A, z, path)
    assert result["ok"] is True
    assert [s["key"] for s in result["steps"]] == ["9", "8"]
