"""Game Knowledge Store -- TW-25 (design history §23.1/§23.3): the
per-world, persisted store of TWO independently-schemad knowledge
graphs that a future menu-crawler (TW-26) and introspector (TW-27) will
populate, and a future deterministic-nav pathfinder (TW-28) will read.
This module is the STORE + SCHEMA only -- it has no opinion about HOW a
menu signature or a game-data value gets discovered, only about how
such a discovery is persisted, upserted, and queried back.

**Two schemas, one file per world:**

1. **Menu-map graph** -- nodes are menu *signatures* (a stable
   hash/label of a menu screen's identifying text, computed by the
   caller -- this store never hashes screen text itself); edges are
   `{from_node, key, to_node, kind, desc}`, where `key` is the
   keystroke/option that gets from one menu to the next. Re-upserting
   the same signature/edge is idempotent (updates `last_seen_ts` in
   place) rather than accumulating duplicates, because the whole point
   of a menu-map is that the SAME signature recurs every time the
   crawler revisits that screen.
2. **Game-data tables** -- `ships` / `scanners` / `transwarp` / `items` /
   `cargo_holds`, each row keyed by a caller-supplied string key (a
   ship_name, scanner_type, etc. -- domain semantics this store has no
   opinion on; see `knowledge/reference/tw2002-ships-and-equipment.md`'s
   `# Schema` section for what each table's fields mean, and
   `game_data.py`'s `persist_cargo_hold_price` docstring for why
   `cargo_holds` is always keyed by one fixed singleton key rather than
   a per-item name) plus two fields every row carries regardless of
   table: `source` (how it was obtained) and `last_verified_ts`
   (stamped fresh on every upsert -- this store records when a value
   was last confirmed live, it never decides when that confirmation
   should happen; that's the introspector's job).

**Keying -- per world, via the pinned `world_identity.world_id()`
interface** (a sibling lane's module, imported here, never authored
here): two characters on the same host+game are two different worlds
with two different generated galaxies, so their menu-maps and game-data
rows must never bleed into each other -- collapsing the key to just
host+game would silently merge them. `knowledge_path()` below is the
ONE place this module calls into that interface; every other function
in this module takes an already-resolved `path` (mirroring
`player_bank.py`'s `bank_path=`/`ledger.py`'s `path=` convention --
identity resolution happens once, at the call site that has it, not
re-derived on every single store operation).

Concurrency/atomicity: `flock`-guarded load-mutate-save critical
sections and temp-then-rename atomic writes at 0600, verbatim from
`player_bank.py`'s cipher/mack-hardened pattern -- see that module's
docstring for the full rationale (a bank/knowledge file is local-only
metadata, never a secret, but still gets the same defense-in-depth
treatment as `credentials.py`'s secrets file rather than an
umask-default 0644).
"""

import contextlib
import datetime
import fcntl
import json
import os
from collections import deque
from pathlib import Path

from .world_identity import world_id

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = PROJECT_ROOT / "state"
WORLD_STATE_DIR = STATE_DIR / "world"
KNOWLEDGE_FILENAME = "game_knowledge.json"

SCHEMA_VERSION = 1

# The five game-data tables tw2002-ships-and-equipment.md's `# Schema`
# section defines (`cargo_holds` added by TW-27 P1-b -- a StarDock
# hold-upgrade price quote, not a doc-schema catalog table, but this
# store treats it identically to the other four: a validated table
# name plus opaque per-table fields). Table NAMES are validated here (a
# typo'd table should fail loudly, not silently create a sixth table);
# per-table FIELD names/types are the caller's business, not this
# store's -- see module docstring.
GAME_DATA_TABLES = ("ships", "scanners", "transwarp", "items", "cargo_holds")

# Menu-map edge kinds (per the TW-25 dispatch's pinned shape).
MENU_EDGE_KINDS = ("nav", "info", "action")


class GameKnowledgeError(Exception):
    """Store-level errors: corrupt file, unknown table, an empty/blank
    key where one is required, an invalid edge kind, etc."""


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_knowledge():
    return {
        "version": SCHEMA_VERSION,
        "menu_map": {"nodes": {}, "edges": []},
        "game_data": {table: {} for table in GAME_DATA_TABLES},
        # Phase-3 try-then-verify rules (additive; SCHEMA_VERSION stays 1).
        "learned_rules": {},
    }


def knowledge_path(host, game_letter, handle, state_dir=None):
    """Resolve `<state_dir or state/>/world/<world_id>/game_knowledge.json`
    via the pinned `world_identity.world_id(host, game_letter, handle)`
    slug -- the ONLY place this module calls into that sibling lane's
    interface. `state_dir` overrides the `state/` root (tests point it
    at `tmp_path` so the real gitignored `state/` tree is never
    touched); everything else about the module takes the resulting
    `Path` directly rather than re-resolving identity per call."""
    slug = world_id(host, game_letter, handle)
    return knowledge_path_for_world(slug, state_dir=state_dir)


def knowledge_path_for_world(world_id_slug, state_dir=None):
    """Same `<state_dir or state/>/world/<slug>/game_knowledge.json` path
    join `knowledge_path()` does, but for a caller that already holds an
    opaque, ALREADY-RESOLVED `world_id` slug (e.g. `game_data.py`'s
    per-world game-data writer/query API, pinned to a `world_id`-first
    signature the same way `world_model.py`'s public API is) rather
    than a raw host/game_letter/handle triple. Never calls into
    `world_identity` itself -- `knowledge_path()` above remains the ONE
    call site of that interface; this is purely the path-join half,
    factored out so it isn't duplicated per caller."""
    base = Path(state_dir) / "world" if state_dir is not None else WORLD_STATE_DIR
    return base / str(world_id_slug) / KNOWLEDGE_FILENAME


def _lock_path(path):
    return path.with_suffix(path.suffix + ".lock")


@contextlib.contextmanager
def _knowledge_lock(path):
    """Exclusive `fcntl.flock`, held across a mutator's FULL
    load-mutate-save critical section -- verbatim
    `player_bank._bank_lock`'s pattern (see that module's docstring for
    the full lost-update rationale). Locks a sibling `<path>.lock`
    file, never the knowledge file itself, so lock-free readers
    (`load_knowledge`, the `get_*`/`list_*`/`find_*` query functions)
    are never blocked by a held write lock."""
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
    """Load the knowledge file at `path`, or return a fresh empty
    structure if it doesn't exist yet -- that's the expected
    pre-first-write state for a brand-new world, never an error. A
    corrupt/truncated/empty file or an unsupported `version` is fatal
    structural corruption -- `GameKnowledgeError`, naming the file,
    NEVER a silent reset to an empty store (mirrors
    `player_bank.load_bank`'s contract exactly)."""
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
            f"game_knowledge file has an invalid top-level shape (expected an object): {path}"
        )
    data.setdefault("version", SCHEMA_VERSION)
    if data["version"] != SCHEMA_VERSION:
        raise GameKnowledgeError(
            f"unsupported game_knowledge version {data['version']!r} in {path} "
            f"(expected {SCHEMA_VERSION})"
        )
    data.setdefault("menu_map", {})
    data["menu_map"].setdefault("nodes", {})
    data["menu_map"].setdefault("edges", [])
    data.setdefault("game_data", {})
    for table in GAME_DATA_TABLES:
        data["game_data"].setdefault(table, {})
    data.setdefault("learned_rules", {})
    return data


def save_knowledge(knowledge, path):
    """Atomic write: temp-then-rename, chmod 0600 -- verbatim
    `player_bank.save_bank`'s pattern, including its on-any-failure
    orphaned-tmp-file cleanup (see that module's docstring)."""
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


# -- menu-map graph -----------------------------------------------------------

def upsert_menu_node(path, signature, label=None):
    """Upsert a menu-map node keyed by `signature` -- a stable
    hash/label of a menu screen's identifying text, computed by the
    caller (the future TW-26 crawler), never by this store. Idempotent:
    re-upserting the same signature stamps a fresh `last_seen_ts` (and
    updates `label` if a non-None one is given) rather than creating a
    duplicate node; `first_seen_ts` is stamped once, on first insert,
    and never overwritten afterward."""
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
    """A single node by signature, or `None` if never seen. A copy --
    mutating the returned dict never touches the live store."""
    node = load_knowledge(path)["menu_map"]["nodes"].get(signature)
    return dict(node) if node is not None else None


def list_menu_nodes(path):
    """Every known node, as copies, in insertion order."""
    return [dict(n) for n in load_knowledge(path)["menu_map"]["nodes"].values()]


def upsert_menu_edge(path, from_node, key, to_node, kind="nav", desc=None):
    """Upsert an edge keyed by the `(from_node, key)` pair -- a given
    menu keystroke is expected to lead somewhere deterministic within
    one world, so re-upserting the same `(from_node, key)` updates
    `to_node`/`kind`/`desc`/`last_seen_ts` on the existing edge in place
    rather than appending a duplicate. `from_node`/`to_node` are
    signatures (need not already exist as upserted nodes -- the crawler
    may discover an edge before it has separately upserted both
    endpoints; that ordering is the crawler's business, not this
    store's)."""
    if kind not in MENU_EDGE_KINDS:
        raise GameKnowledgeError(
            f"invalid menu edge kind {kind!r} (expected one of {MENU_EDGE_KINDS})"
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
    """Every known edge, as copies, in insertion order."""
    return [dict(e) for e in load_knowledge(path)["menu_map"]["edges"]]


def get_edges_from(path, signature):
    """Adjacency query: every edge whose `from_node` is `signature`."""
    return [e for e in list_menu_edges(path) if e["from_node"] == signature]


def find_menu_path(path, from_signature, to_signature):
    """Shortest path (fewest edges) from `from_signature` to
    `to_signature`, as an ordered list of edge dicts a TW-28
    deterministic-nav pathfinder can walk keystroke-by-keystroke (each
    edge's `key`). Returns `[]` if the two signatures are identical
    (already there), or `None` if `to_signature` is unreachable from
    `from_signature` over the currently-known graph. Plain BFS over the
    edge list -- pure read, no lock needed."""
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


# -- game-data tables ----------------------------------------------------------

def upsert_game_data_row(path, table, key, fields, source):
    """Upsert one row in `table` (one of `GAME_DATA_TABLES`) keyed by
    `key` -- a caller-supplied string (a ship_name/scanner_type/
    item_name/etc.; this store has no opinion on which field a given
    table treats as its natural name, only that SOME string key is
    given). `fields` is the caller-supplied dict of that table's domain
    values, per tw2002-ships-and-equipment.md's `# Schema` (e.g.
    `max_holds`, `special_abilities` -- lists are valid field values,
    per that schema's `special_abilities` column, so `fields` is
    intentionally NOT restricted to scalars the way `player_bank`'s
    unrelated secrets-guarded `notes` dict is).

    `source` is required (how this row was obtained -- e.g.
    `"introspected: shipyard listing"`) and `last_verified_ts` is
    stamped fresh on every upsert; both are stored under the row itself
    alongside a `key` field (so a row read back via `list_game_data_rows`
    is self-describing without a caller having to separately track
    which key it came from). This module never authors/decides field
    VALUES -- that is the future TW-27 introspector's job, never
    hardcoded here."""
    if table not in GAME_DATA_TABLES:
        raise GameKnowledgeError(
            f"unknown game_data table {table!r} (expected one of {GAME_DATA_TABLES})"
        )
    if not key or not str(key).strip():
        raise GameKnowledgeError("game_data row key must be non-empty")
    if not source or not str(source).strip():
        raise GameKnowledgeError("game_data row source must be non-empty")
    if not isinstance(fields, dict):
        raise GameKnowledgeError("game_data row fields must be a dict")
    path = Path(path)
    with _knowledge_lock(path):
        data = load_knowledge(path)
        rows = data["game_data"][table]
        row = dict(fields)
        row["key"] = key
        row["source"] = source
        row["last_verified_ts"] = _now_iso()
        rows[key] = row
        save_knowledge(data, path)
        return dict(row)


def get_game_data_row(path, table, key):
    """A single row by key, or `None` if never seen."""
    if table not in GAME_DATA_TABLES:
        raise GameKnowledgeError(
            f"unknown game_data table {table!r} (expected one of {GAME_DATA_TABLES})"
        )
    row = load_knowledge(path)["game_data"][table].get(key)
    return dict(row) if row is not None else None


def list_game_data_rows(path, table):
    """Every known row in `table`, as copies, in insertion order."""
    if table not in GAME_DATA_TABLES:
        raise GameKnowledgeError(
            f"unknown game_data table {table!r} (expected one of {GAME_DATA_TABLES})"
        )
    return [dict(r) for r in load_knowledge(path)["game_data"][table].values()]


# -- learned rules (Phase-3 try-then-verify) ------------------------------------

def _learned_rule_id(state_signature, tried_action):
    return f"{state_signature}|{tried_action}"


def upsert_learned_rule(path, state_signature, tried_action, observed_transition, confidence):
    """Upsert a learned-rule record keyed by ``state_signature|tried_action``.

    Idempotent: re-upserting the same pair updates ``observed_transition``,
    ``confidence``, and ``last_seen_ts``; ``first_seen_ts`` is stamped once.
    ``state_signature`` is a caller-supplied menu_sig hash (this store never
    hashes screen text). ``confidence`` must be in ``[0, 1]``.
    """
    if not state_signature or not str(state_signature).strip():
        raise GameKnowledgeError("learned rule state_signature must be non-empty")
    if not tried_action or not str(tried_action).strip():
        raise GameKnowledgeError("learned rule tried_action must be non-empty")
    if not observed_transition or not str(observed_transition).strip():
        raise GameKnowledgeError("learned rule observed_transition must be non-empty")
    try:
        conf = float(confidence)
    except (TypeError, ValueError) as e:
        raise GameKnowledgeError(
            f"learned rule confidence must be a number in [0, 1], got {confidence!r}"
        ) from e
    if conf < 0.0 or conf > 1.0:
        raise GameKnowledgeError(
            f"learned rule confidence must be in [0, 1], got {conf!r}"
        )
    path = Path(path)
    rule_id = _learned_rule_id(state_signature, tried_action)
    with _knowledge_lock(path):
        data = load_knowledge(path)
        rules = data["learned_rules"]
        now = _now_iso()
        existing = rules.get(rule_id)
        if existing is not None:
            existing["observed_transition"] = observed_transition
            existing["confidence"] = conf
            existing["last_seen_ts"] = now
            rule = existing
        else:
            rule = {
                "state_signature": state_signature,
                "tried_action": tried_action,
                "observed_transition": observed_transition,
                "confidence": conf,
                "first_seen_ts": now,
                "last_seen_ts": now,
            }
            rules[rule_id] = rule
        save_knowledge(data, path)
        return dict(rule)


def get_learned_rule(path, state_signature, tried_action):
    """A single learned rule by (state, action), or ``None``."""
    rule_id = _learned_rule_id(state_signature, tried_action)
    rule = load_knowledge(path)["learned_rules"].get(rule_id)
    return dict(rule) if rule is not None else None


def list_learned_rules(path):
    """Every learned rule, as copies, in insertion order."""
    return [dict(r) for r in load_knowledge(path)["learned_rules"].values()]


def list_learned_rules_for_state(path, state_signature):
    """Learned rules whose ``state_signature`` matches, as copies."""
    return [
        r for r in list_learned_rules(path)
        if r.get("state_signature") == state_signature
    ]
