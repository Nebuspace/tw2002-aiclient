"""Thin menu-map knowledge store (WO-P2-OPS-VERB-G0).

Bounded subset of archive ``game_knowledge`` — menu_map nodes/edges only.
No world_identity / game_data / learned_rules (later WOs).
"""

from __future__ import annotations

import contextlib
import datetime
import fcntl
import json
import os
from collections import deque
from pathlib import Path

SCHEMA_VERSION = 1

# Canon's three-value enum, exactly -- `canon/engine/menu-map-and-introspection.md`
# is prescriptive: "The edge `kind` is a three-value enum -- nav | info | action".
# There is deliberately NO "unknown" kind: an option the crawler could not prove
# safe is recorded `kind="action"` with its real category folded into `desc`
# ("unknown: K----"), so the distinction rides in `desc` rather than widening
# this vocabulary. A fourth kind here would let that fold silently stop
# happening, which is the exact information-shape canon forbids.
#
# Gates WRITES only. `load_knowledge` never validates a stored edge's kind, so
# narrowing this set cannot make a previously-readable map unreadable --
# pinned by tests/test_menu_knowledge_edge_kinds.py.
MENU_EDGE_KINDS = frozenset({"nav", "info", "action"})
KNOWLEDGE_FILENAME = "game_knowledge.json"

# How a crawl ended. A map with NO recorded status is of UNKNOWN
# provenance -- which is honest, and deliberately not the same as
# "complete": nothing here ever lets a partial map read as a finished one.
CRAWL_STATUS_VALUES = frozenset({"complete", "truncated", "aborted", "error"})
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WORLD_STATE_DIR = _PROJECT_ROOT / "state" / "world"


class GameKnowledgeError(Exception):
    pass


def knowledge_path_for_world(world_id_slug, state_dir=None):
    """Join ``state/world/<slug>/game_knowledge.json`` (no world_identity).

    ``state_dir`` overrides the ``state/`` root (tests point at ``tmp_path``).
    Pure path math — does not call credentials or world_identity.
    """
    base = Path(state_dir) / "world" if state_dir is not None else WORLD_STATE_DIR
    return base / str(world_id_slug) / KNOWLEDGE_FILENAME


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_knowledge():
    return {
        "version": SCHEMA_VERSION,
        "menu_map": {"nodes": {}, "edges": []},
    }


def _lock_path(path):
    return path.with_suffix(path.suffix + ".lock")


@contextlib.contextmanager
def _knowledge_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(path)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def load_knowledge(path):
    path = Path(path)
    if not path.exists():
        return _new_knowledge()
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise GameKnowledgeError(
                f"game_knowledge file is corrupt (invalid JSON): {path} ({e})"
            ) from e
    if not isinstance(data, dict):
        raise GameKnowledgeError(
            f"game_knowledge file has an invalid top-level shape: {path}"
        )
    data.setdefault("version", SCHEMA_VERSION)
    if data["version"] != SCHEMA_VERSION:
        raise GameKnowledgeError(
            f"unsupported game_knowledge version {data['version']!r} in {path}"
        )
    data.setdefault("menu_map", {})
    data["menu_map"].setdefault("nodes", {})
    data["menu_map"].setdefault("edges", [])
    return data


def save_knowledge(knowledge, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(knowledge, f, indent=2)
            f.write("\n")
        os.chmod(tmp_path, 0o600)
        os.replace(str(tmp_path), str(path))
        os.chmod(path, 0o600)
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


def upsert_menu_node(path, signature, label=None):
    if not signature or not str(signature).strip():
        raise GameKnowledgeError("menu node signature must be non-empty")
    path = Path(path)
    with _knowledge_lock(path):
        data = load_knowledge(path)
        nodes = data["menu_map"]["nodes"]
        now = _now_iso()
        existing = nodes.get(signature)
        if existing is not None:
            existing["last_seen_ts"] = now
            if label is not None:
                existing["label"] = label
            node = existing
        else:
            node = {
                "signature": signature,
                "label": label,
                "first_seen_ts": now,
                "last_seen_ts": now,
            }
            nodes[signature] = node
        save_knowledge(data, path)
        return dict(node)


def get_menu_node(path, signature):
    node = load_knowledge(path)["menu_map"]["nodes"].get(signature)
    return dict(node) if node is not None else None


def list_menu_nodes(path):
    return [dict(n) for n in load_knowledge(path)["menu_map"]["nodes"].values()]


def upsert_menu_edge(path, from_node, key, to_node, kind="nav", desc=None):
    if kind not in MENU_EDGE_KINDS:
        raise GameKnowledgeError(
            f"invalid menu edge kind {kind!r} (expected one of {sorted(MENU_EDGE_KINDS)})"
        )
    if not from_node or not key or not to_node:
        raise GameKnowledgeError(
            "menu edge requires non-empty from_node, key, and to_node"
        )
    path = Path(path)
    with _knowledge_lock(path):
        data = load_knowledge(path)
        edges = data["menu_map"]["edges"]
        now = _now_iso()
        for edge in edges:
            if edge["from_node"] == from_node and edge["key"] == key:
                edge["to_node"] = to_node
                edge["kind"] = kind
                edge["desc"] = desc
                edge["last_seen_ts"] = now
                save_knowledge(data, path)
                return dict(edge)
        edge = {
            "from_node": from_node,
            "key": key,
            "to_node": to_node,
            "kind": kind,
            "desc": desc,
            "last_seen_ts": now,
        }
        edges.append(edge)
        save_knowledge(data, path)
        return dict(edge)


def list_menu_edges(path):
    return [dict(e) for e in load_knowledge(path)["menu_map"]["edges"]]


def record_crawl_status(
    path,
    *,
    status,
    reason=None,
    nodes_visited=None,
    frontier_remaining=None,
):
    """Stamp the menu map with the outcome of the crawl that produced it.

    A crawl that half-completes -- aborted at a screen boundary, stopped
    by the ``max_nodes`` rail, or failed structurally -- persists every
    node and edge it discovered before stopping. Without this stamp a
    consumer cannot tell that partial map apart from a finished one: an
    unvisited frontier node looks exactly like a genuine dead-end. The
    stamp is what keeps the write path honest.

    Replaces any previous stamp -- the map describes one world, and the
    most recent crawl is the one whose coverage the current node/edge set
    reflects.
    """
    if status not in CRAWL_STATUS_VALUES:
        raise GameKnowledgeError(
            f"invalid crawl status {status!r} (expected one of {sorted(CRAWL_STATUS_VALUES)})"
        )
    path = Path(path)
    with _knowledge_lock(path):
        data = load_knowledge(path)
        record = {
            "status": status,
            "reason": reason,
            "nodes_visited": nodes_visited,
            "frontier_remaining": frontier_remaining,
            "ts": _now_iso(),
        }
        data["menu_map"]["last_crawl"] = record
        save_knowledge(data, path)
        return dict(record)


def get_crawl_status(path):
    """The last recorded crawl outcome, or ``None`` when the map's
    provenance is unknown (no crawl ever stamped it).

    ``None`` means exactly that -- unknown. It is never a completeness
    claim; a caller that needs "is this map finished?" must check for an
    explicit ``"complete"`` status.
    """
    record = load_knowledge(path)["menu_map"].get("last_crawl")
    return dict(record) if isinstance(record, dict) else None


def find_menu_path(path, from_signature, to_signature):
    if from_signature == to_signature:
        return []
    edges = list_menu_edges(path)
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge["from_node"], []).append(edge)
    visited = {from_signature}
    queue = deque([(from_signature, [])])
    while queue:
        node, path_so_far = queue.popleft()
        for edge in adjacency.get(node, []):
            nxt = edge["to_node"]
            if nxt in visited:
                continue
            new_path = path_so_far + [edge]
            if nxt == to_signature:
                return new_path
            visited.add(nxt)
            queue.append((nxt, new_path))
    return None
