"""The persisted rule library -- ``state/rules/*.json``, read strictly.

One admission gate
------------------
``_read_document`` is the ONLY place a stored rule becomes a
:class:`~tw2002_aiclient.rule_engine.Rule`, and it builds one by calling
:func:`~tw2002_aiclient.rule_engine.rule_from_dict` -- the same strict parser
the kernel's unit tests exercise. There is deliberately no second, lenient
path: the parser rejects unknown fields, a bool priority, and a non-bool
``approved`` precisely because *"a truthy string here is exactly how a draft
becomes live by accident"*, and a store that re-implemented admission would
make every one of those refusals unreachable on the only input that arrives
from outside the process. ``tests/test_rules_store.py`` pins that no module
in this package constructs a ``Rule`` any other way.

Absent, empty, and unreadable are three different facts
------------------------------------------------------
Mirrors :mod:`tw2002_aiclient.loops.store`, including its hard-won choice of
``os.listdir`` over ``Path.glob``: ``glob`` swallows a ``PermissionError`` on
the directory and yields nothing, which would make a store we were not
allowed to read indistinguishable from a store with no rules in it. For a
reflex layer that distinction is the whole safety story -- "no rule matched"
and "we could not see the rules" must never render as the same answer, since
one is a settled negative and the other is an unknown.

The ``cause`` vocabulary is **imported** from ``loops.store`` rather than
restated, for the reason ``classify.py`` gives about its own closed set: a
second copy holds only until someone edits one of them.

Approval is not filtered here
-----------------------------
:func:`read_rule_store` returns every rule it could parse, approved or not,
and the kernel's ``select_rule`` does the filtering. Two readers of one fact
is how they drift; the kernel already owns "a draft is absent, not
low-priority" and owns it alone.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from ..loops.store import (
    CAUSE_CORRUPT,
    CAUSE_DENIED,
    CAUSE_MALFORMED,
    CAUSE_UNUSABLE,
)
from ..rule_engine import Rule, RuleDocumentError, rule_from_dict

__all__ = [
    "DRAFTS_DIRNAME",
    "RULES_DIRNAME",
    "STATE_DIR",
    "STATUS_ABSENT",
    "STATUS_OK",
    "STATUS_PARTIAL",
    "STATUS_UNREADABLE",
    "drafts_dir",
    "legacy_flat_rules_dir",
    "migrate_flat_rules_to_world",
    "read_rule_store",
    "resolve_roots",
    "rules_dir",
]

RULES_DIRNAME = "rules"
DRAFTS_DIRNAME = "_drafts"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = _PROJECT_ROOT / "state"

#: No store has ever been written -- a genuine negative.
STATUS_ABSENT = "absent"
#: Every file in the store parsed.
STATUS_OK = "ok"
#: Some parsed, some did not. Callers that report a rule count MUST say so.
STATUS_PARTIAL = "partial"
#: We could not look. Never renderable as "there are no rules".
STATUS_UNREADABLE = "unreadable"


def rules_dir(state_dir=None, *, world_id=None) -> Path:
    """Blessed reflex library directory (pure path math — no I/O).

    * ``world_id`` set → ``state/world/<world_id>/rules`` (PWO-090 residual).
    * ``world_id`` omitted → legacy flat ``state/rules``.

    ``state_dir`` overrides the ``state/`` root (tests use ``tmp_path``).
    """
    base = Path(state_dir) if state_dir is not None else STATE_DIR
    if world_id is not None and str(world_id).strip():
        return base / "world" / str(world_id).strip() / RULES_DIRNAME
    return base / RULES_DIRNAME


def drafts_dir(state_dir=None, *, world_id=None) -> Path:
    """Drafts directory under the same scoping as :func:`rules_dir`.

    The blessed listing skips this directory for free rather than by a rule:
    it iterates names ending in ``.json``, and ``_drafts`` is a directory. That
    is worth stating because "the draft dir is excluded" reads like a filter
    somebody could remove; there is no filter to remove.

    Delegates to :func:`resolve_roots` rather than repeating ``rules_dir() /
    DRAFTS_DIRNAME``, so this convenience accessor cannot disagree with the
    resolution the reader and writer actually use.
    """
    return resolve_roots(state_dir=state_dir, world_id=world_id)[1]



def legacy_flat_rules_dir(state_dir=None) -> Path:
    """Explicit legacy flat ``state/rules`` (never world-scoped)."""
    from .migrate import legacy_flat_rules_dir as _legacy

    return _legacy(state_dir)


def migrate_flat_rules_to_world(world_id: str, *, state_dir=None) -> dict:
    """See :func:`tw2002_aiclient.rules.migrate.migrate_flat_rules_to_world`."""
    from .migrate import migrate_flat_rules_to_world as _migrate

    return _migrate(world_id, state_dir=state_dir)


def resolve_roots(*, state_dir=None, rules_path=None, drafts_path=None, world_id=None) -> tuple[Path, Path]:
    """``(blessed_dir, drafts_dir)`` from the three override knobs.

    **Every module in this package resolves those two directories here, and
    only here.** Reader and writer taking the same three arguments and each
    doing its own path math is a twin, and twins are equal only until someone
    edits one: the first version of this package had exactly that, and passing
    ``rules_path=tmp_path`` alone sent the reader to ``tmp_path/_drafts``
    while the writer went to the operator's real ``state/rules/_drafts``.
    Every test that overrode one root would have silently promoted and deleted
    live drafts. Pure path math -- touches no filesystem.

    ``drafts_path`` is derived from ``rules_path`` when only the latter is
    given, because ``_drafts`` is defined as *inside* the library rather than
    as a sibling of it; an override of the library must carry its drafts with
    it or it is not the same store.
    """
    blessed = (
        Path(rules_path)
        if rules_path is not None
        else rules_dir(state_dir, world_id=world_id)
    )
    if drafts_path is not None:
        return blessed, Path(drafts_path)
    return blessed, blessed / DRAFTS_DIRNAME


def _read_document(path: Path, *, draft: bool = False) -> tuple[Optional[Rule], Optional[str], Optional[str]]:
    """``(rule, None, None)`` on a usable rule document, ``(None, reason,
    cause)`` on one this reader refuses to present as a rule.

    ``OSError`` is caught alongside the decode errors for the reason
    ``loops.store`` records: a permission-denied file, or a directory named
    ``*.json``, otherwise escapes and takes the whole listing down instead of
    being reported as one unreadable file.

    :class:`~tw2002_aiclient.rule_engine.RuleDocumentError` is caught and
    coarsened to ``malformed`` rather than propagated. That is not leniency
    -- the document is still refused, and its message is carried verbatim
    into ``reason`` so an operator can fix the file. What it buys is that one
    bad rule cannot silence the rest of the library, which for a *safety*
    layer is the direction that fails closed: the alternative is a single
    typo disarming every guard in the store at once.
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
    if draft and document.get("approved") is True:
        # REFUSED, not silently coerced to False. A file's LOCATION is the
        # authority on whether it is blessed, so a draft claiming approval is
        # a contradiction -- and the loud reading is the safe one here.
        # Coercing would "repair" it into a valid draft and lose the fact that
        # something wrote `approved: true` into a directory that may not
        # contain it; the writer cannot do that, so it means a hand-edit or a
        # second author, and both are worth an operator's attention. This is
        # the file-level twin of `rule_from_dict`'s refusal of a truthy
        # non-bool `approved`, and for the same stated reason.
        return None, "a draft may not carry approved: true -- promote it instead", CAUSE_MALFORMED
    try:
        # THE admission gate. Every `Rule` this package produces is born here.
        return rule_from_dict(document), None, None
    except RuleDocumentError as exc:
        return None, str(exc), CAUSE_MALFORMED


def _read_root(directory: Path, *, draft: bool) -> dict[str, Any]:
    """Read one store directory. Never raises -- the failure IS the report."""
    root: dict[str, Any] = {
        "path": str(directory),
        "draft": draft,
        "status": STATUS_OK,
        "reason": None,
        "rules": [],
        "unreadable": [],
    }
    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        root["status"] = STATUS_ABSENT
        return root
    except NotADirectoryError:
        root["status"] = STATUS_UNREADABLE
        root["reason"] = "not a directory"
        return root
    except OSError as exc:
        # A failure to LOOK, reported as its own status precisely so no
        # caller downstream can render it as "empty".
        root["status"] = STATUS_UNREADABLE
        root["reason"] = exc.strerror or "could not be listed"
        return root

    # `_drafts` is a directory, so it is skipped by the `.json` filter without
    # a rule of its own -- see `drafts_dir`.
    for path in [directory / name for name in sorted(names) if name.endswith(".json")]:
        rule, reason, _cause = _read_document(path, draft=draft)
        if rule is None:
            # Named, never silently skipped -- the `continue` that drops a
            # file without recording it is what lets a store of entirely
            # unreadable rules report as an empty one.
            root["unreadable"].append({"path": str(path), "reason": reason})
            continue
        root["rules"].append(rule)

    if root["unreadable"]:
        root["status"] = STATUS_PARTIAL
    return root


def read_rule_store(
    *,
    include_drafts: bool = False,
    state_dir=None,
    rules_path=None,
    drafts_path=None,
    world_id=None,
) -> dict[str, Any]:
    """Read the rule library and report what is actually in it.

    Returns ``path``, ``status``, ``reason``, ``rules`` (**blessed only**),
    ``drafts`` (populated only when ``include_drafts``), ``roots``
    (per-directory outcome), ``unreadable``, and ``include_drafts``.

    **``rules`` never contains a draft, in any configuration.** Drafts come
    back in their own list rather than in ``rules`` with a ``draft: True``
    flag -- the shape ``loops/store.py`` uses. The difference matters here
    because the consumer is a selector rather than a listing: a flag on a row
    is safe only while every reader remembers to check it, and forgetting is
    silent. Two lists make mixing an **explicit concatenation** somebody has
    to write, which is the property worth having on the path that decides
    what the app would do.

    ``include_drafts`` defaults to **False**, and `rules/reflex.py` stays on
    that default. A draft is a proposal awaiting a human; selection must not
    see one.

    **Branch on ``status`` before saying anything about how many rules
    exist.** An empty list is true for an empty store, an absent store, and a
    store of entirely corrupt files -- three different things to tell an
    operator. Never raises: the failure is data in the result, because a
    reader that dies on a corrupt file tells the operator less than one that
    names it.
    """
    if rules_path is None and world_id is not None and str(world_id).strip():
        migrate_flat_rules_to_world(str(world_id).strip(), state_dir=state_dir)
    blessed, drafts = resolve_roots(
        state_dir=state_dir,
        rules_path=rules_path,
        drafts_path=drafts_path,
        world_id=world_id,
    )
    roots = [_read_root(blessed, draft=False)]
    if include_drafts:
        roots.append(_read_root(drafts, draft=True))

    unreadable = [u for r in roots for u in r["unreadable"]]
    # An ABSENT draft directory is the normal state on a fresh install and
    # must not drag the whole report to `partial`; only a directory we were
    # not allowed to LOOK at is a failure to see.
    blind = [r for r in roots if r["status"] == STATUS_UNREADABLE]
    if blind and len(blind) == len(roots):
        status = STATUS_UNREADABLE
    elif blind or unreadable:
        status = STATUS_PARTIAL
    elif all(r["status"] == STATUS_ABSENT for r in roots):
        status = STATUS_ABSENT
    else:
        status = STATUS_OK

    return {
        "path": str(blessed),
        "status": status,
        "reason": roots[0]["reason"],
        "rules": list(roots[0]["rules"]),
        "drafts": list(roots[1]["rules"]) if include_drafts else [],
        "roots": roots,
        "unreadable": unreadable,
        "include_drafts": bool(include_drafts),
    }
