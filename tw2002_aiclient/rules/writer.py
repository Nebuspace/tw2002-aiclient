"""The only module in ``rules/`` that writes rule JSON to disk.

Mirrors ``loops/recorder.py``'s ownership: one writer, so "what can create a
rule" is a question with a single answer rather than a survey.

It cannot bless
---------------
:func:`write_draft` hard-codes ``approved: False`` **after** validation, and
there is deliberately no parameter through which a caller could ask for
``True``. That is the difference between a rule and a guard: a guard refuses a
request that was expressible, and this makes the request inexpressible. Canon
is unambiguous -- *"Nothing the AI writes ... without human approval"* -- and an
`approved=` keyword would put the whole guarantee one careless caller away,
including a future AI author, which is precisely the caller canon is about.

Blessing lives in :func:`promote_draft`, reached only from the explicit
``tw rule approve`` operator command. Two functions, two files' worth of
distance, one of them named for what it does.

It validates before it writes
-----------------------------
Every document goes through the kernel's :func:`rule_from_dict` before it
reaches the disk, so a draft that could never load is refused at the moment
the operator can still fix it rather than discovered later by a reader. Same
parser as the store and the kernel's own tests -- no second, lenient path.

Writes are atomic
-----------------
Write to a temporary file in the destination directory, then ``os.replace``.
A half-written JSON file in a store that a selector reads is a corrupt rule
that appears and disappears depending on when someone looked, and the store
would honestly report it as unreadable -- which is the *right* report of the
*wrong* situation. ``os.replace`` is atomic on POSIX within a filesystem, and
staging in the destination directory is what keeps it within one.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping

from ..rule_engine import RuleDocumentError, rule_from_dict, rule_to_dict
from .store import resolve_roots

__all__ = [
    "RuleWriteError",
    "promote_draft",
    "safe_stem",
    "write_draft",
]

# Conservative: letters, digits, dash, underscore. Everything else becomes a
# dash. A rule_id is operator-supplied and becomes a FILENAME, so this is the
# boundary where `../../etc/passwd` and a leading dot stop being possible.
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")


class RuleWriteError(ValueError):
    """A document was refused before anything reached the disk."""


def safe_stem(rule_id: str) -> str:
    """A filesystem-safe stem for *rule_id*.

    Lossy on purpose, and therefore **never** read back as an identity: the
    document's own ``rule_id`` is the identity, exactly as ``loops/store.py``
    says about macro names ("the filename is NOT a substitute ... adopting one
    would be inventing an identity for a document that does not carry it").

    Leading dots are stripped so a rule cannot write a hidden file, and the
    result is refused rather than defaulted if nothing survives -- a rule_id of
    ``"..."`` has no honest stem, and inventing one would put a document
    somewhere its author cannot predict.
    """
    stem = _UNSAFE.sub("-", str(rule_id)).strip("-.")
    if not stem:
        raise RuleWriteError(
            f"rule_id {rule_id!r} has no filesystem-safe form; give it letters or digits"
        )
    return stem


def _refuse_stem_collision(path: Path, rule_id: str) -> None:
    """Refuse to overwrite a file that holds a *different* rule.

    :func:`safe_stem` is lossy, so ``"dock/safe"`` and ``"dock-safe"`` land on
    one filename. Re-writing the same rule_id is a legitimate update; landing
    on a neighbour's file is silent deletion of a rule an operator approved,
    and it would show up later only as a reflex that stopped existing. An
    unreadable or absent file is not a collision -- the store already reports
    the first as unreadable, and refusing here would make a corrupt file
    unfixable by rewriting it.
    """
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(existing, dict) and existing.get("rule_id") not in (None, rule_id):
        raise RuleWriteError(
            f"rule_id {rule_id!r} maps to {path.name}, which already holds "
            f"{existing['rule_id']!r} -- rename one of them"
        )


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        # Leave no ".tmp-*" behind for the store to trip over. It would be
        # skipped by the `.json` filter today, but relying on that would make
        # this correct by a coincidence in another module.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_draft(
    document: Mapping[str, Any], *, state_dir=None, rules_path=None, drafts_path=None
) -> Path:
    """Persist *document* as an inert draft. Returns the path written.

    **Always ``approved: False``.** There is no parameter to ask otherwise;
    a document arriving with ``approved: True`` is refused rather than
    silently downgraded, because silently downgrading would let an author
    believe it had blessed something. Refusing says so.
    """
    if not isinstance(document, Mapping):
        raise RuleWriteError(f"a rule document must be a mapping, got {type(document).__name__}")
    if document.get("approved") is True:
        raise RuleWriteError(
            "a draft may not be written with approved: true -- drafts are inert by "
            "definition; use the explicit promote/approve command instead"
        )
    try:
        # Validate through THE parser before anything reaches the disk.
        rule = rule_from_dict({**document, "approved": False})
    except RuleDocumentError as exc:
        raise RuleWriteError(str(exc)) from None

    payload = rule_to_dict(rule)
    # Belt and braces: `rule_to_dict` round-trips what the parser produced,
    # and the parser was handed False, so this is already False. Asserting it
    # here means a future change to either function cannot quietly bless a
    # draft without this line becoming visibly wrong.
    payload["approved"] = False

    _, directory = resolve_roots(
        state_dir=state_dir, rules_path=rules_path, drafts_path=drafts_path
    )
    path = directory / f"{safe_stem(rule.rule_id)}.json"
    _refuse_stem_collision(path, rule.rule_id)
    _atomic_write_json(path, payload)
    return path


def promote_draft(
    rule_id: str,
    *,
    state_dir=None,
    rules_path=None,
    drafts_path=None,
    remove_draft: bool = True,
) -> Path:
    """Bless one draft into the live library. **The only path to ``approved: True``.**

    Reached only from the explicit ``tw rule approve`` operator command. It is
    not called by :func:`write_draft`, not called by `rules/reflex.py`, and
    takes the ``rule_id`` positionally so it cannot be invoked by accident
    with a default.

    The document is re-validated through the parser on the way out: a draft
    can sit on disk for a long time, and hand-editing between writing and
    promoting is exactly when a malformed one appears. Approving is the last
    moment the refusal is still cheap.
    """
    blessed, drafts = resolve_roots(
        state_dir=state_dir, rules_path=rules_path, drafts_path=drafts_path
    )
    stem = safe_stem(rule_id)
    src = drafts / f"{stem}.json"
    try:
        document = json.loads(src.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RuleWriteError(f"no draft named {rule_id!r} at {src}") from None
    except (OSError, ValueError) as exc:
        raise RuleWriteError(f"draft {rule_id!r} could not be read: {exc}") from None
    if not isinstance(document, dict):
        raise RuleWriteError(f"draft {rule_id!r} is not a rule document")
    try:
        rule = rule_from_dict({**document, "approved": True})
    except RuleDocumentError as exc:
        raise RuleWriteError(f"draft {rule_id!r} is not promotable: {exc}") from None

    payload = rule_to_dict(rule)
    payload["approved"] = True
    dest = blessed / f"{stem}.json"
    _refuse_stem_collision(dest, rule.rule_id)
    _atomic_write_json(dest, payload)
    if remove_draft:
        # Only after the blessed copy is durably in place. The reverse order
        # loses the rule entirely if the write fails, and a moment where the
        # rule exists in both places is harmless -- the selector reads only
        # the blessed tree.
        try:
            src.unlink()
        except OSError:
            pass
    return dest
