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
    "RULES_DIRNAME",
    "STATE_DIR",
    "STATUS_ABSENT",
    "STATUS_OK",
    "STATUS_PARTIAL",
    "STATUS_UNREADABLE",
    "read_rule_store",
    "rules_dir",
]

RULES_DIRNAME = "rules"

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


def rules_dir(state_dir=None) -> Path:
    """``state/rules`` -- the human-approved reflex library.

    ``state_dir`` overrides the ``state/`` root (tests point at ``tmp_path``).
    Pure path math -- touches no filesystem.
    """
    base = Path(state_dir) if state_dir is not None else STATE_DIR
    return base / RULES_DIRNAME


def _read_document(path: Path) -> tuple[Optional[Rule], Optional[str], Optional[str]]:
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
    try:
        # THE admission gate. Every `Rule` this package produces is born here.
        return rule_from_dict(document), None, None
    except RuleDocumentError as exc:
        return None, str(exc), CAUSE_MALFORMED


def read_rule_store(*, state_dir=None, rules_path=None) -> dict[str, Any]:
    """Read the rule library and report what is actually in it.

    Returns ``path``, ``status`` (one of the four module constants),
    ``reason``, ``rules`` (parsed :class:`Rule` objects, approved and draft
    alike), and ``unreadable`` (every file that could not be read, each with
    its path and reason). Never raises -- the failure IS the report.

    **Branch on ``status`` before saying anything about how many rules
    exist.** ``rules == []`` is true for an empty store, an absent store, and
    a store of entirely corrupt files, and those are three different things
    to tell an operator.
    """
    directory = Path(rules_path) if rules_path is not None else rules_dir(state_dir)
    report: dict[str, Any] = {
        "path": str(directory),
        "status": STATUS_OK,
        "reason": None,
        "rules": [],
        "unreadable": [],
    }
    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        report["status"] = STATUS_ABSENT
        return report
    except NotADirectoryError:
        report["status"] = STATUS_UNREADABLE
        report["reason"] = "not a directory"
        return report
    except OSError as exc:
        # A failure to LOOK, reported as its own status precisely so no
        # caller downstream can render it as "empty".
        report["status"] = STATUS_UNREADABLE
        report["reason"] = exc.strerror or "could not be listed"
        return report

    for path in [directory / name for name in sorted(names) if name.endswith(".json")]:
        rule, reason, _cause = _read_document(path)
        if rule is None:
            # Named, never silently skipped -- the `continue` that drops a
            # file without recording it is what lets a store of entirely
            # unreadable rules report as an empty one.
            report["unreadable"].append({"path": str(path), "reason": reason})
            continue
        report["rules"].append(rule)

    if report["unreadable"]:
        report["status"] = STATUS_PARTIAL
    return report
