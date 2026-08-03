"""Read-only reader over the taught-macro ("learned loop") store.

WO-P2-G3. Pure filesystem read: this module opens JSON files and reports
what it found. It never writes the store, never touches the session, and
cannot send a keystroke. Recording a macro (``tw record``) and mining a
draft (``tw mine``) are the writers, and neither exists in the reborn tree
yet -- so on a live checkout today this reader honestly reports an empty
store, because nothing has ever written one.

Canon
-----
* ``canon/engine/macros.md`` §Schema defines the document: ``name`` /
  ``start_anchor`` / ``source`` / ``created_ts`` / ``mined_stats``, and
  ``steps[]`` of ``{input, wait_prompt, expected_post_class}``.
* ``canon/architecture/cli-verbs.md §"The One-Round-Trip Contract"`` lists ``loops`` among the
  **daemon-free reads** -- "they read on-disk artifacts directly, so they
  work with the daemon stopped". So this is a direct store read with no
  protocol verb. The archive routed the same listing through the daemon
  (``protocol.py::_dispatch_list_skills``) purely to attach live
  ``loop_player`` progress; G3 has no player and canon prescribes against
  the round trip, so the daemon path is not carried. **Docs win.**
* ``canon/engine/candidate-mining.md §"What it reads, what it emits"`` and
  ``canon/engine/world-identity.md §"Code divergence"`` both name the on-disk home:
  ``state/skills/<name>.json`` blessed, ``state/skills/_drafts/<name>.json``
  drafts. A draft is **inert** -- approval is expressed by file location
  (``canon/engine/macros.md §"Findings — code divergences (docs win)"``), so this reader flags every draft row
  and lists them only on explicit opt-in.

World scoping (PWO-090 / DECISION-LOOPS-WORLD-MIGRATE-ON-READ)
-------------------------------------------------------------
Canon requires the macro library be world-scoped
(``canon/engine/world-identity.md``). Paths:

* **World-scoped (default when ``world_id`` is supplied):**
  ``state/world/<world_id>/skills/`` (+ ``_drafts/``).
* **Legacy flat:** ``state/skills/`` — still returned when ``world_id`` is
  omitted (tests / daemon-free callers without a profile).

On first world-scoped read/write, ``migrate_flat_loops_to_world`` copies
legacy flat JSON into the world path if the world store is empty and the
flat store has files (idempotent; never deletes flat). Silent empty-world
reads against a non-empty flat store are forbidden by that migrate step.

The honesty contract
--------------------
Three outcomes, never two. "There are no loops" and "the store could not be
read" are different facts and an operator can act on only one of them, so
they never render alike -- the same defect class a sibling lane just fixed in
``tw menumap``, where a failed lookup was indistinguishable from a genuine
off-map result.

* ``status="ok"``         -- every consulted root was read and every file in
  it parsed. Only this status has established a negative, so only this status
  entitles a caller to say "there are no loops".
* ``status="partial"``    -- some rows are real, but a root or a file could
  not be read, so the listing is incomplete. A count under this status is a
  floor, never a total.
* ``status="unreadable"`` -- no consulted root could be read at all. Nothing
  is known; no count may be reported.

Deliberate asymmetry with ``tw menumap``: that verb reads ONE file, so an
unreadable store is a total failure and it correctly aborts with an error
(``cli.py``'s ``cmd_menumap`` catch). This store is a DIRECTORY of mutually
independent documents, where one corrupt file among twenty leaves nineteen
real macros worth listing -- so the failure is reported *in band*, as
``status`` plus a named ``unreadable`` list, rather than thrown. Different
handling, same rule: the operator is never told a negative that was not
established.

Every row is READ. No field is defaulted into existence: an absent ``source``
stays ``None`` rather than becoming ``"recorded"`` (the archive's default,
which asserts human provenance no data supports, on an artifact that gets
pressed back into a live game), and profit metadata appears only when the
document actually carries a finite number for it.
"""

from __future__ import annotations

import json
import math
import shutil
import os
from pathlib import Path
from typing import Any, Mapping, Optional

# Canon's two provenance values (`canon/engine/macros.md §"What a macro is"`). Anything else
# -- absent, misspelled, or invented -- is unknown provenance, never coerced
# into one of these.
SOURCE_VALUES = frozenset({"recorded", "mined"})

STORE_DIRNAME = "skills"
DRAFTS_DIRNAME = "_drafts"

# Why something could not be read. Vocabulary and VALUES deliberately
# identical to `session/credentials.py`'s `CAUSE_*` (and `player_bank`'s
# before it) rather than a second dialect -- coarse enough to branch on,
# distinct where the operator's next action differs: fixing permissions,
# replacing a wrong path, and repairing a damaged document are three
# different jobs, and `reason` narrows each one further.
#
# Redefined here rather than imported because `loops/` deliberately imports
# nothing from `session/` -- that disjointness is what keeps this package
# structurally incapable of reaching the wire (see `loops/__init__.py`), and
# it is worth four duplicated string constants. Identical values mean a
# future unification is a re-export, never a translation table.
CAUSE_DENIED = "denied"  # we were not allowed to look
CAUSE_UNUSABLE = "unusable"  # the path is not a readable file (e.g. a directory)
CAUSE_CORRUPT = "corrupt"  # we looked, and the bytes are not a readable document
CAUSE_MALFORMED = "malformed"  # it parsed, and it is not the document we needed

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = _PROJECT_ROOT / "state"


def loops_dir(state_dir=None, *, world_id=None) -> Path:
    """Blessed macro library directory (pure path math — no I/O).

    * ``world_id`` set → ``state/world/<world_id>/skills`` (PWO-090).
    * ``world_id`` omitted → legacy flat ``state/skills``.

    ``state_dir`` overrides the ``state/`` root (tests use ``tmp_path``).
    """
    base = Path(state_dir) if state_dir is not None else STATE_DIR
    if world_id is not None and str(world_id).strip():
        return base / "world" / str(world_id).strip() / STORE_DIRNAME
    return base / STORE_DIRNAME


def drafts_dir(state_dir=None, *, world_id=None) -> Path:
    """Drafts directory under the same scoping as :func:`loops_dir`."""
    return loops_dir(state_dir, world_id=world_id) / DRAFTS_DIRNAME


def legacy_flat_loops_dir(state_dir=None) -> Path:
    """Explicit legacy flat ``state/skills`` (never world-scoped)."""
    base = Path(state_dir) if state_dir is not None else STATE_DIR
    return base / STORE_DIRNAME


def migrate_flat_loops_to_world(world_id: str, *, state_dir=None) -> dict:
    """Copy legacy flat skills into ``state/world/<world_id>/skills`` once.

    Policy (DECISION-LOOPS-WORLD-MIGRATE-ON-READ, hub GO 2026-08-03):

    * Fresh installs / empty flat → no-op (``migrated=False``, ``copied=0``).
    * World store already has ``*.json`` → no-op (already scoped).
    * Flat has ``*.json`` and world store empty → copy files (incl. ``_drafts/``).
    * Never deletes the flat tree (operator can remove manually later).

    Returns ``{"migrated": bool, "copied": int, "world_dir": str, "flat_dir": str}``.
    """
    if world_id is None or not str(world_id).strip():
        raise ValueError("world_id is required for migrate_flat_loops_to_world")
    wid = str(world_id).strip()
    flat = legacy_flat_loops_dir(state_dir)
    world = loops_dir(state_dir, world_id=wid)
    result = {
        "migrated": False,
        "copied": 0,
        "world_dir": str(world),
        "flat_dir": str(flat),
    }

    def _json_files(root: Path) -> list[Path]:
        # Open-and-classify, never Path.exists/is_file/is_dir — those collapse
        # permission-denied into "absent" (see test_the_loader_never_asks…).
        try:
            candidates = sorted(root.rglob("*.json"))
        except OSError:
            return []
        out: list[Path] = []
        for path in candidates:
            try:
                with path.open("rb"):
                    pass
            except OSError:
                continue
            out.append(path)
        return out

    if _json_files(world):
        return result
    flat_files = _json_files(flat)
    if not flat_files:
        return result

    world.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src in flat_files:
        rel = src.relative_to(flat)
        dest = world / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with dest.open("xb") as out_f, src.open("rb") as in_f:
                shutil.copyfileobj(in_f, out_f)
        except FileExistsError:
            continue
        except OSError:
            continue
        copied += 1
    result["migrated"] = copied > 0
    result["copied"] = copied
    return result


def _finite_number(value) -> Optional[float]:
    """A real, renderable number, or ``None``.

    Rejects three things that would otherwise render as a confident figure
    next to a macro that spends credits:

    * ``bool`` -- ``isinstance(True, int)`` is true in Python, so an
      unguarded numeric check turns ``"cr_per_turn": true`` into ``+1.0``.
    * ``NaN`` / ``±Inf`` -- Python's ``json`` accepts the bare ``NaN``,
      ``Infinity`` and ``-Infinity`` tokens by default, so a store file can
      carry them and they would format as ``nan``/``inf`` cr/turn.
    * anything non-numeric (a string, a dict, ``None``).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _read_document(path: Path) -> tuple[Optional[dict], Optional[str], Optional[str]]:
    """``(document, None, None)`` on a usable macro doc, ``(None, reason,
    cause)`` on one this reader refuses to present as a loop.

    The reasons are deliberately specific -- an operator who is told a file is
    unreadable can only act on it if they know what is wrong with it. The
    ``cause`` is the same detail coarsened into a value a CALLER can branch
    on without sniffing the reason string; ``loops/loader.py`` uses it to
    tell "I was not allowed to look" from "this is not a macro" when it has
    to decide whether a miss was honestly established.

    ``OSError`` is caught alongside the JSON errors on purpose: the archive
    reader caught only its own ``SkillError``, so a permission-denied file (or
    a directory named ``*.json``) escaped as an ``OSError`` and took the whole
    listing down instead of being reported as one unreadable file.

    This is the ONE document-admission gate in the package. The listing
    (`_read_root`) and the single-loop loader both come through it, so the
    minimum bar for "this is a macro at all" -- a usable identity and a step
    list -- cannot drift between what `tw loops` shows and what a player is
    allowed to load.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON ({exc.msg}, line {exc.lineno})", CAUSE_CORRUPT
    except UnicodeDecodeError:
        return None, "not valid UTF-8", CAUSE_CORRUPT
    except PermissionError as exc:
        return None, exc.strerror or "permission denied", CAUSE_DENIED
    except OSError as exc:
        return None, exc.strerror or "could not be opened", CAUSE_UNUSABLE

    if not isinstance(document, dict):
        return (
            None,
            f"top-level shape is {type(document).__name__}, expected an object",
            CAUSE_MALFORMED,
        )
    # `name` is the macro's identity -- what a human types to replay it. The
    # filename is NOT a substitute: the writer sanitizes names into stems, so
    # a stem is a lossy derivation, and adopting one would be inventing an
    # identity for a document that does not carry it.
    name = document.get("name")
    if not isinstance(name, str) or not name.strip():
        return None, "missing a usable 'name'", CAUSE_MALFORMED
    if not isinstance(document.get("steps"), list):
        return None, "missing a usable 'steps' list", CAUSE_MALFORMED
    return document, None, None


def _row(document: Mapping[str, Any], *, draft: bool) -> dict[str, Any]:
    """One listing row, every field read off ``document``.

    ``source`` stays ``None`` when the document does not carry one of canon's
    two values. The archive defaulted it to ``"recorded"``, which reads as
    "a human demonstrated this at the keyboard" -- the single strongest claim
    the schema can make about a macro (``canon/engine/macros.md`` invariant 1)
    -- asserted from an absent field.

    Profit is likewise read, never derived. The archive additionally computed
    a ``demo_profit`` by summing ledger rows tagged with the macro's capture
    name; the Trace-Ledger exists again (#353/#355) but this listing path
    still does not sum it, and an absent or failed ledger read summing to
    ``0`` would render as ``"+0cr demo"`` -- a definite economic claim
    manufactured from no data. Not carried.
    """
    source = document.get("source")
    row: dict[str, Any] = {
        "name": document["name"],
        "source": source if source in SOURCE_VALUES else None,
        "created_ts": document.get("created_ts"),
        "start_anchor": document.get("start_anchor"),
        "steps": len(document["steps"]),
        "draft": draft,
    }
    mined_stats = document.get("mined_stats")
    if isinstance(mined_stats, Mapping):
        for row_key, stat_key in (
            ("profit_per_turn", "cr_per_turn"),
            ("profit_per_action", "cr_per_action"),
            ("support", "support"),
        ):
            number = _finite_number(mined_stats.get(stat_key))
            if number is not None:
                row[row_key] = number
    return row


def _read_root(directory: Path, *, draft: bool) -> dict[str, Any]:
    """List one store directory. Never raises -- the failure is the report."""
    root: dict[str, Any] = {
        "path": str(directory),
        "draft": draft,
        "status": "ok",
        "reason": None,
        "loops": [],
        "unreadable": [],
    }
    # `os.listdir`, NOT `Path.glob`. `glob` swallows a PermissionError on the
    # directory and returns an empty iterator (verified on this tree's Python
    # 3.14), which would make an unreadable store indistinguishable from an
    # empty one at the only place that distinction can still be made -- the
    # precise collapse this module exists to prevent. `listdir` raises, so
    # the failure survives to the report.
    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        # No store has ever been written. A genuine negative -- there are no
        # loops -- and a different fact from an empty directory, which is the
        # one that explains itself to an operator who expected rows.
        root["status"] = "absent"
        return root
    except NotADirectoryError:
        root["status"] = "unreadable"
        root["reason"] = "not a directory"
        return root
    except OSError as exc:
        # A failure to LOOK. Reported as its own status precisely so that no
        # caller downstream can render it as "empty".
        root["status"] = "unreadable"
        root["reason"] = exc.strerror or "could not be listed"
        return root
    for path in [directory / name for name in sorted(names) if name.endswith(".json")]:
        # `cause` is for the single-loop loader's honest-miss decision; the
        # listing renders `reason`, which is strictly more specific.
        document, reason, _cause = _read_document(path)
        if document is None:
            # Named, never silently skipped. The archive's `continue` here is
            # what let a store of entirely corrupt files report as an empty
            # one.
            root["unreadable"].append({"path": str(path), "reason": reason})
            continue
        root["loops"].append(_row(document, draft=draft))
    return root


def read_loop_store(
    *,
    include_drafts: bool = False,
    state_dir=None,
    skills_dir=None,
    drafts_path=None,
    world_id=None,
) -> dict[str, Any]:
    """Read the taught-macro store and report what is actually in it.

    Returns a dict with ``loops`` (real rows only, blessed before drafts),
    ``roots`` (per-directory outcome), ``unreadable`` (every file that could
    not be read, each with its path and reason), and ``status`` -- one of
    ``"ok"`` / ``"partial"`` / ``"unreadable"``, defined in this module's
    docstring. ``status`` is the field a caller must branch on before saying
    anything about how many loops exist.

    Drafts are inert proposals awaiting human approval, so they are consulted
    only when ``include_drafts`` is set; every draft row carries
    ``draft: True`` so it can never be mistaken for a blessed macro.

    Never raises on a bad store: an unreadable directory or file is data in
    the result, because a reader that dies on a corrupt file tells the
    operator less than one that names it.
    """
    if skills_dir is None and world_id is not None and str(world_id).strip():
        migrate_flat_loops_to_world(str(world_id).strip(), state_dir=state_dir)
    blessed = (
        Path(skills_dir)
        if skills_dir is not None
        else loops_dir(state_dir, world_id=world_id)
    )
    roots = [_read_root(blessed, draft=False)]
    if include_drafts:
        drafts = (
            Path(drafts_path)
            if drafts_path is not None
            else (
                blessed / DRAFTS_DIRNAME
                if skills_dir is not None
                else drafts_dir(state_dir, world_id=world_id)
            )
        )
        roots.append(_read_root(drafts, draft=True))

    loops: list[dict[str, Any]] = []
    unreadable: list[dict[str, Any]] = []
    for root in roots:
        loops.extend(root["loops"])
        unreadable.extend(root["unreadable"])

    # "absent" is a read that succeeded and found nothing -- a real negative.
    # "unreadable" is a read that failed. Only the latter costs us knowledge.
    looked = [root for root in roots if root["status"] != "unreadable"]
    if not looked:
        status = "unreadable"
    elif len(looked) != len(roots) or unreadable:
        status = "partial"
    else:
        status = "ok"

    return {
        "loops": loops,
        "roots": roots,
        "unreadable": unreadable,
        "status": status,
        "include_drafts": bool(include_drafts),
    }
