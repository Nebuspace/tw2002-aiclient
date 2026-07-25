"""The knowledge store's crawl-status stamp — an honest write path.

A crawl that half-completes persists every node and edge it discovered
before stopping. Without a record of HOW it ended, that partial map is
indistinguishable from a finished one: an unvisited frontier node looks
exactly like a genuine dead-end to `menu_map_summary`, and a navigator
reading it would conclude the world has no route where one simply was
never walked. These tests pin the stamp, and pin the one property that
makes it honest rather than decorative — an unstamped map reads as
*unknown provenance*, never as complete.
"""

import pytest

from tw2002_aiclient.menu import crawler
from tw2002_aiclient.menu.knowledge import (
    CRAWL_STATUS_VALUES,
    GameKnowledgeError,
    get_crawl_status,
    list_menu_edges,
    list_menu_nodes,
    record_crawl_status,
    upsert_menu_node,
)


class _WideMenuSession:
    """A root menu whose safe options each lead to another menu, so the
    frontier queue genuinely outlives a small `max_nodes` rail."""

    SCREENS = {
        "root": "(V)iew Alpha\n(D)isplay Beta\n(L)ist Gamma",
        "alpha": "(V)iew Alpha Detail\n(B)ack to Root",
        "beta": "(V)iew Beta Detail\n(B)ack to Root",
        "gamma": "(V)iew Gamma Detail\n(B)ack to Root",
    }
    TRANSITIONS = {
        ("root", "V"): "alpha",
        ("root", "D"): "beta",
        ("root", "L"): "gamma",
    }

    def __init__(self):
        self.t = 0.0
        self.rx_count = 1
        self.last_rx = -1.0
        self._id = "root"
        self.sent = []
        self._pending = None

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self._pending is not None:
            key, self._pending = self._pending, None
            self._id = self.TRANSITIONS.get((self._id, key), self._id)
            self.rx_count += 1
            self.last_rx = self.t

    def render(self):
        return self.SCREENS[self._id].split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self.SCREENS[self._id]

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))
        self._pending = text


# -- the store primitive -------------------------------------------------------


def test_an_unstamped_map_reports_unknown_provenance_not_completeness(tmp_path):
    """The load-bearing honesty property. `None` means "no crawl ever said
    how this ended" — a caller asking "is this finished?" has to find an
    explicit "complete", and cannot get one by default."""
    path = tmp_path / "game_knowledge.json"
    upsert_menu_node(path, "sig-a", label="Some Menu")

    assert get_crawl_status(path) is None


def test_status_round_trips_with_its_context(tmp_path):
    path = tmp_path / "game_knowledge.json"
    record_crawl_status(
        path, status="truncated", reason="max_nodes rail", nodes_visited=7, frontier_remaining=3
    )

    status = get_crawl_status(path)
    assert status["status"] == "truncated"
    assert status["reason"] == "max_nodes rail"
    assert status["nodes_visited"] == 7
    assert status["frontier_remaining"] == 3
    assert status["ts"]


def test_a_later_crawl_replaces_the_earlier_stamp(tmp_path):
    """The map describes one world; the most recent crawl is the one whose
    coverage the current node/edge set reflects. A stale "complete" left
    sitting beside an aborted re-crawl would be the exact dishonesty this
    record exists to prevent."""
    path = tmp_path / "game_knowledge.json"
    record_crawl_status(path, status="complete", nodes_visited=9, frontier_remaining=0)
    record_crawl_status(path, status="aborted", reason="a human took the keyboard")

    assert get_crawl_status(path)["status"] == "aborted"


def test_an_unrecognized_status_is_refused(tmp_path):
    path = tmp_path / "game_knowledge.json"
    with pytest.raises(GameKnowledgeError):
        record_crawl_status(path, status="probably_fine")


def test_the_recognized_statuses_are_exactly_the_four_outcomes():
    assert CRAWL_STATUS_VALUES == frozenset({"complete", "truncated", "aborted", "error"})


def test_the_stamp_does_not_disturb_the_menu_map(tmp_path):
    """Additive: stamping must not touch the nodes/edges a consumer
    reads."""
    path = tmp_path / "game_knowledge.json"
    upsert_menu_node(path, "sig-a", label="Some Menu")
    before_nodes = list_menu_nodes(path)
    before_edges = list_menu_edges(path)

    record_crawl_status(path, status="complete", nodes_visited=1, frontier_remaining=0)

    assert list_menu_nodes(path) == before_nodes
    assert list_menu_edges(path) == before_edges


def test_a_stamped_store_still_loads_cleanly_afterwards(tmp_path):
    """The record rides inside `menu_map`; a later load must not trip the
    schema checks."""
    path = tmp_path / "game_knowledge.json"
    record_crawl_status(path, status="error", reason="boom")
    upsert_menu_node(path, "sig-b", label="Later Menu")

    assert [n["signature"] for n in list_menu_nodes(path)] == ["sig-b"]
    assert get_crawl_status(path)["status"] == "error"


# -- what the crawler itself stamps --------------------------------------------


def test_a_drained_crawl_stamps_complete(tmp_path):
    path = tmp_path / "game_knowledge.json"
    result = crawler.crawl_menus(_WideMenuSession, path, max_nodes=50)

    assert result["truncated"] is False
    assert result["frontier_remaining"] == 0
    status = get_crawl_status(path)
    assert status["status"] == "complete"
    assert status["nodes_visited"] == result["nodes_visited"]


def test_a_rail_stopped_crawl_stamps_truncated_and_says_how_much_is_left(tmp_path):
    """Non-vacuous: the rail really did stop a walk that had more to do —
    frontier_remaining is positive, and the map is smaller than the drained
    one above."""
    path = tmp_path / "game_knowledge.json"
    result = crawler.crawl_menus(_WideMenuSession, path, max_nodes=1)

    assert result["nodes_visited"] == 1
    assert result["truncated"] is True
    assert result["frontier_remaining"] > 0

    status = get_crawl_status(path)
    assert status["status"] == "truncated"
    assert status["frontier_remaining"] == result["frontier_remaining"]
    assert "max_nodes" in status["reason"]


def test_the_truncated_map_would_otherwise_look_finished(tmp_path):
    """Why the stamp matters, demonstrated rather than asserted: the
    rail-stopped map contains nodes with no outgoing edges that are NOT
    dead-ends — they were simply never visited. Only the stamp tells them
    apart."""
    path = tmp_path / "game_knowledge.json"
    crawler.crawl_menus(_WideMenuSession, path, max_nodes=1)

    edges = list_menu_edges(path)
    explored_from = {e["from_node"] for e in edges}
    discovered = {n["signature"] for n in list_menu_nodes(path)}
    unwalked = discovered - explored_from

    assert unwalked, "fixture no longer leaves an unvisited frontier node"
    assert get_crawl_status(path)["status"] == "truncated"


def test_record_status_can_be_declined_by_a_caller_that_owns_the_stamp(tmp_path):
    """The driver stamps abort/error itself; a caller composing its own
    outcome can suppress the crawler's stamp rather than write two."""
    path = tmp_path / "game_knowledge.json"
    crawler.crawl_menus(_WideMenuSession, path, max_nodes=50, record_status=False)

    assert get_crawl_status(path) is None
    assert list_menu_nodes(path)  # the map itself was still written
