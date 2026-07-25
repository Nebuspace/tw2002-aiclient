"""The edge-kind vocabulary — canon's three, and nothing wider.

`canon/engine/menu-map-and-introspection.md` is prescriptive here: the edge
`kind` is a **three-value enum** -- `nav | info | action` -- and "the store's
schema has no `unknown` kind, so the crawler folds the real category into the
edge's `desc`". The store had drifted to a five-value set (`escape` /
`unknown` besides the three); `crawler.py` had never written the extra two and
said so in its own comments. These tests pin the narrowed vocabulary so the
drift cannot quietly return.

The last test is the load-bearing one. Narrowing a *validated* vocabulary is
only safe because validation is **write-only**: `load_knowledge` and every
reader below it pass an edge's stored `kind` through verbatim and never
consult `MENU_EDGE_KINDS`. That is what makes this a code-alignment change
rather than a store-breaking one, and it is pinned here so a later WO cannot
turn the narrowing into a reader that rejects a map it used to be able to
read.
"""

import json

import pytest

from tw2002_aiclient.menu import map_view, nav
from tw2002_aiclient.menu.knowledge import (
    MENU_EDGE_KINDS,
    GameKnowledgeError,
    find_menu_path,
    list_menu_edges,
    load_knowledge,
    upsert_menu_edge,
)
from tw2002_aiclient.menu.sig import menu_signature

CANON_THREE = frozenset({"nav", "info", "action"})

# The two kinds the store used to accept and canon never defined.
RETIRED_KINDS = ("escape", "unknown")


def test_menu_edge_kinds_is_exactly_canon_three():
    """The constant IS canon's enum -- not a superset of it."""
    assert MENU_EDGE_KINDS == CANON_THREE


@pytest.mark.parametrize("kind", sorted(CANON_THREE))
def test_canon_kinds_are_accepted(tmp_path, kind):
    """The narrowing must not cost a legitimate kind."""
    path = tmp_path / "game_knowledge.json"
    edge = upsert_menu_edge(path, "sig-a", "X", "sig-b", kind=kind)
    assert edge["kind"] == kind


@pytest.mark.parametrize("kind", RETIRED_KINDS)
def test_retired_kinds_are_refused(tmp_path, kind):
    """`escape` and `unknown` were code drift; writing one is now an error.

    Before the narrowing these were silently ACCEPTED -- a crawler bug that
    wrote `kind="unknown"` would have been persisted as a real edge kind
    instead of folded into `desc`, which is precisely the information-shape
    canon forbids.
    """
    path = tmp_path / "game_knowledge.json"
    with pytest.raises(GameKnowledgeError, match="invalid menu edge kind"):
        upsert_menu_edge(path, "sig-a", "X", "sig-b", kind=kind)


@pytest.mark.parametrize("kind", RETIRED_KINDS)
def test_refusing_a_retired_kind_writes_nothing(tmp_path, kind):
    """The refusal is a rejection, not a half-write.

    Validation happens before the lock/load/save block, so a refused edge
    must leave no file and no partial edge behind.
    """
    path = tmp_path / "game_knowledge.json"
    with pytest.raises(GameKnowledgeError):
        upsert_menu_edge(path, "sig-a", "X", "sig-b", kind=kind)
    assert not path.exists()


@pytest.mark.parametrize("kind", RETIRED_KINDS)
def test_a_stored_retired_kind_is_still_READABLE(tmp_path, kind):
    """The legacy-data guarantee: narrowing gates WRITES, never READS.

    A map written by an older build (or hand-edited) that holds a retired
    kind must still load, list, path-find, plan, and summarize -- passing the
    stored kind through verbatim. If this ever goes red, the narrowing has
    become a store-breaking change and needs a migration, not a constant.
    """
    path = tmp_path / "game_knowledge.json"
    screen = "Legacy Root Menu"
    sig_a = menu_signature(screen)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "menu_map": {
                    "nodes": {
                        sig_a: {"signature": sig_a, "label": "Legacy Root Menu",
                                "first_seen_ts": "t", "last_seen_ts": "t"},
                        "sig-b": {"signature": "sig-b", "label": "B",
                                  "first_seen_ts": "t", "last_seen_ts": "t"},
                    },
                    "edges": [
                        {"from_node": sig_a, "key": "1", "to_node": "sig-b",
                         "kind": kind, "desc": f"legacy {kind} edge",
                         "last_seen_ts": "t"},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    # load / list: the stored kind survives verbatim, un-coerced and un-dropped.
    assert load_knowledge(path)["menu_map"]["edges"][0]["kind"] == kind
    assert [e["kind"] for e in list_menu_edges(path)] == [kind]

    # pathfinding still crosses it.
    assert [e["key"] for e in find_menu_path(path, sig_a, "sig-b")] == ["1"]

    # the planner reports it verbatim to its caller.
    plan = nav.plan_nav(screen, "sig-b", path)
    assert plan["ok"] is True
    assert [s["kind"] for s in plan["steps"]] == [kind]

    # the map-view summary counts it like any other edge.
    summary = map_view.menu_map_summary_from_store(path)
    assert summary["edge_count"] == 1


@pytest.mark.parametrize("kind", RETIRED_KINDS)
def test_a_stored_retired_kind_can_be_REWRITTEN_to_a_canon_kind(tmp_path, kind):
    """Re-observing a legacy edge heals it rather than tripping on it.

    `upsert_menu_edge` validates the kind it is HANDED, never the kind already
    on disk -- so a re-crawl over a legacy map upgrades the stale edge in
    place instead of failing.
    """
    path = tmp_path / "game_knowledge.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "menu_map": {
                    "nodes": {},
                    "edges": [
                        {"from_node": "sig-a", "key": "1", "to_node": "sig-b",
                         "kind": kind, "desc": "legacy", "last_seen_ts": "t"},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    edge = upsert_menu_edge(path, "sig-a", "1", "sig-b", kind="nav", desc="healed")
    assert edge["kind"] == "nav"
    assert [e["kind"] for e in list_menu_edges(path)] == ["nav"]


def test_the_error_message_names_the_accepted_set(tmp_path):
    """An operator who hits this must be told what IS allowed."""
    path = tmp_path / "game_knowledge.json"
    with pytest.raises(GameKnowledgeError) as excinfo:
        upsert_menu_edge(path, "sig-a", "X", "sig-b", kind="escape")
    message = str(excinfo.value)
    assert "'escape'" in message
    for kind in sorted(CANON_THREE):
        assert kind in message
    # ...and must not advertise a kind the store no longer takes.
    assert "unknown" not in message
