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
MENU_EDGE_KINDS = frozenset({"nav", "info", "action", "escape", "unknown"})


class GameKnowledgeError(Exception):
    pass


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
