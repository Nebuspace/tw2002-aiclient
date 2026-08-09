"""Menu-map inspector — pure tests on synthetic maps."""

from tw2002_aiclient.menu.map_view import (
    format_menu_map_lines,
    format_menu_map_report,
    menu_map_summary,
    menu_map_summary_from_store,
)


def _node(sig, label=None):
    return {"signature": sig, "label": label}


def _edge(frm, key, to, kind="nav"):
    return {
        "from_node": frm,
        "key": key,
        "to_node": to,
        "kind": kind,
        "desc": None,
    }


def test_empty_map_zero_state():
    s = menu_map_summary([], [])
    assert s["node_count"] == 0
    assert s["edge_count"] == 0
    assert s["current"] is None
    assert s["reachable_from_current"] == 0
    assert s["dead_ends"] == []
    assert s["orphans"] == []
    lines = format_menu_map_lines(s, cols=22)
    assert lines[0].startswith("MAP 0n")
    assert "off-map" in lines[1]


def test_linear_current_and_reachable():
    nodes = [_node("A", "Root"), _node("B", "Mid"), _node("C", "Leaf")]
    edges = [_edge("A", "1", "B"), _edge("B", "2", "C")]
    s = menu_map_summary(nodes, edges, current_sig="A")
    assert s["node_count"] == 3
    assert s["edge_count"] == 2
    assert s["current"]["label"] == "Root"
    assert s["current"]["star"] is True
    assert s["reachable_from_current"] == 3  # A,B,C
    assert s["dead_ends"] == ["C"]
    assert s["orphans"] == []  # root A has outgoing — not an island


def test_branching_and_cycle():
    nodes = [_node("A"), _node("B"), _node("C"), _node("D")]
    edges = [
        _edge("A", "1", "B"),
        _edge("A", "2", "C"),
        _edge("B", "x", "A"),  # cycle
        _edge("C", "3", "D"),
    ]
    s = menu_map_summary(nodes, edges, current_sig="A")
    assert s["reachable_from_current"] == 4
    assert "D" in s["dead_ends"]
    assert "A" not in s["orphans"]  # B→A gives A an incoming


def test_off_map_current_honest():
    nodes = [_node("A", "Known")]
    edges = []
    s = menu_map_summary(nodes, edges, current_sig="unknown")
    assert s["current"] is None
    assert s["reachable_from_current"] == 0
    lines = format_menu_map_lines(s, cols=22)
    assert lines[1] == "here off-map"


def test_orphan_node_is_isolated_island():
    nodes = [_node("A", "Linked"), _node("Z", "Orphan")]
    edges = [_edge("A", "1", "A")]  # self-loop: A has out + in
    s = menu_map_summary(nodes, edges, current_sig="A")
    assert s["orphans"] == ["Z"]  # no-in AND no-out
    assert s["reachable_from_current"] == 1


def test_root_with_outgoing_is_not_orphan():
    nodes = [_node("ROOT", "Entry"), _node("B", "Child")]
    edges = [_edge("ROOT", "1", "B")]
    s = menu_map_summary(nodes, edges, current_sig="ROOT")
    assert "ROOT" not in s["orphans"]
    assert s["orphans"] == []
    assert s["dead_ends"] == ["B"]


def test_render_clips_at_22_and_expands_at_40():
    s = menu_map_summary(
        [_node("A", "Shipyard"), _node("B", "Status")],
        [_edge("A", "S", "B")],
        current_sig="A",
    )
    narrow = format_menu_map_lines(s, cols=22)
    assert all(len(line) <= 22 for line in narrow)
    assert "★" in narrow[1]
    assert "Shipyard" in narrow[1]
    assert "orphans" not in narrow[2]

    wide = format_menu_map_lines(s, cols=40)
    assert all(len(line) <= 40 for line in wide)
    assert "orphans" in wide[2]


def test_from_store_wrapper(tmp_path):
    from tw2002_aiclient.menu import knowledge

    path = tmp_path / "game_knowledge.json"
    knowledge.upsert_menu_node(path, "sig-a", label="Computer")
    knowledge.upsert_menu_node(path, "sig-b", label="Ship")
    knowledge.upsert_menu_edge(path, "sig-a", "2", "sig-b", kind="nav")
    s = menu_map_summary_from_store(path, current_sig="sig-a")
    assert s["node_count"] == 2
    assert s["current"]["label"] == "Computer"
    assert s["reachable_from_current"] == 2


def test_format_menu_map_report_lists_coverage_and_orphans():
    """FA13 CLI surface — report lines match fixture coverage/orphans."""
    nodes = [_node("A", "Root"), _node("B", "Mid"), _node("Z", "Orphan")]
    edges = [_edge("A", "1", "B")]
    s = menu_map_summary(nodes, edges, current_sig="A")
    report = format_menu_map_report(s)
    joined = "\n".join(report)
    assert "MAP 3n" in report[0]
    assert "here ★ Root" in report[1]
    assert "2/3 reachable" in joined
    assert "orphans: Z" in joined
    assert "dead-ends: B" in joined


def test_summary_from_store_attaches_last_crawl(tmp_path):
    from tw2002_aiclient.menu import knowledge as menu_knowledge

    path = tmp_path / "gk.json"
    menu_knowledge.upsert_menu_node(path, "A", label="Root")
    assert menu_map_summary_from_store(path)["last_crawl"] is None
    menu_knowledge.record_crawl_status(
        path, status="truncated", reason="max_nodes", nodes_visited=2, frontier_remaining=1
    )
    crawl = menu_map_summary_from_store(path)["last_crawl"]
    assert crawl["status"] == "truncated"
    assert crawl["reason"] == "max_nodes"
    assert crawl["nodes_visited"] == 2
    assert crawl["frontier_remaining"] == 1


def test_report_includes_last_crawl_line_when_stamped():
    s = menu_map_summary([_node("A")], [])
    s["last_crawl"] = {
        "status": "aborted",
        "reason": "human took keyboard",
        "nodes_visited": 3,
        "frontier_remaining": 2,
        "ts": "2026-08-09T00:00:00Z",
    }
    report = "\n".join(format_menu_map_report(s))
    assert "last-crawl: aborted" in report
    assert "reason=human took keyboard" in report
    assert "visited=3" in report
    assert "frontier=2" in report


def test_report_omits_last_crawl_when_unstamped():
    s = menu_map_summary([_node("A")], [])
    s["last_crawl"] = None
    report = "\n".join(format_menu_map_report(s))
    assert "last-crawl:" not in report
