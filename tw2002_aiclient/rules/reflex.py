"""One live screen -> the kernel's answer. The product's reach into the reflex layer.

This is the wire :mod:`tw2002_aiclient.rule_engine` was built behind. It reads
the persisted library through :mod:`.store` (which admits documents only via
the kernel's strict parser), derives facts from the status payload the daemon
already produces, and returns the kernel's
:class:`~tw2002_aiclient.rule_engine.Decision` verbatim.

Two landings are deliberately inert
-----------------------------------
Both were ruled in scope-setting and are disclosed here so nobody reads a
macro name in a ``Decision`` as a thing that is about to happen:

1. **``NEVER_AUTO_ACTION_CLASSES`` stays unconditional.**
   ``loops/player.py`` refuses those screens at every boundary with no flag to
   waive it, so an *approved* rule proposing a macro that reaches a buy/sell
   prompt still halts on ``never_auto_action:*``. That is the rail holding,
   not a wire defect.
2. **A rule's approval does not reach the player.** A ``Loop`` from the loader
   carries no guard field and no arming field -- the schema has neither -- so
   the §A.2 exemption for "a human-armed autopilot with an explicit
   taught/guarded rule" cannot be honoured from here. Opening it is a separate,
   human-gated change.

Taken together: **selecting a macro changes nothing about what that macro is
permitted to do.** The taught run path is untouched, and arming is still the
human's ``y`` at arm-confirm.

An unreadable library is not an empty one
-----------------------------------------
``select_rule`` answers ``autopilot_no_candidates`` when nothing matched --
a *settled negative*, meaning "we looked at the whole library and none of it
applies". If the library could not be read, that sentence is false, and
returning it would report a searched-and-empty world we never searched. So
:func:`propose_macro` converts a non-readable store into its own
:data:`STOP_RULES_UNREADABLE` before the kernel is ever consulted. The two
answers look identical to a caller that only checks ``decision.macro is
None``, which is exactly why they must not share a reason code.

**A partly-read library is treated the same way, and the reason is not
symmetry.** It is tempting to let a ``partial`` store answer from the rules
that did parse -- the parsed ones are individually valid, after all. But the
kernel's answer is a *comparison* across the whole candidate set, and the
file that failed to parse could hold the rule that would have won: a
higher-priority rule, or a ``stop``-posture guard whose whole job is to
dominate a fireable one. Dropping it does not weaken some other rule's
guards; it removes a veto. So the error moves in the dangerous direction --
a library we could only partly read can turn a STOP into a fire, and it
cannot do the reverse. ``partial`` therefore authorises nothing, and the
cost of that strictness is currently zero, because every proposal in this
slice is inert anyway.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..halt_reasons import qualify
from ..rule_engine import Decision, select_rule
from .store import STATUS_ABSENT, STATUS_OK, read_rule_store

#: The only two store outcomes that may produce a rule decision.
#:
#: ``absent`` is here and ``partial`` is not, which reads backwards until you
#: ask what each one licenses. ``absent`` is a *complete* search of an empty
#: world -- there are no rules, so "no rule matched" is exactly true.
#: ``partial`` is an *incomplete* search, and the missing part may be the veto.
_AUTHORISING_STATUSES = (STATUS_OK, STATUS_ABSENT)

__all__ = [
    "ARGS_REFLEX_ARM",
    "PROPOSAL_IDENTITY",
    "STATUS_FACT_KEYS",
    "STOP_PROPOSAL_DRIFT",
    "STOP_RULES_UNREADABLE",
    "facts_from_status",
    "propose_macro",
    "proposal_drift",
]

#: The library could not be read. Distinct from ``autopilot_no_candidates``
#: (which claims a completed search) and never rendered as "no rule matched".
STOP_RULES_UNREADABLE = "autopilot_rules_unreadable"

#: The library no longer proposes what the human was shown and confirmed.
#:
#: Its own code, never folded into ``autopilot_no_candidates``: that one says
#: "we searched and nothing applies", which is a statement about the library.
#: This one says "something moved between the preview and your ``y``", which is
#: a statement about *time*, and the operator response differs -- look again,
#: rather than go teach a rule.
STOP_PROPOSAL_DRIFT = "autopilot_proposal_drift"

#: The three fields that identify a proposal to the human who confirms it,
#: checked in this order and reported by name when one drifts.
#:
#: All three, not just the macro. The macro is what *runs*, but a macro
#: reached via a different rule was selected by guards the human never saw,
#: and a macro selected for a different screen class is being launched at a
#: screen it was not chosen for. Either of those is a different act wearing
#: the confirmed act's name.
PROPOSAL_IDENTITY = ("rule_id", "macro", "classification")

#: Args the ``reflex_arm`` verb accepts -- exactly the identity, nothing else.
#:
#: Notably absent: any ``cycles``, ``force``, ``yes`` or ``floor``. This verb
#: launches through ``autoloop_start``, which owns those decisions; cycle
#: count for a repeating rule is derived from rule ``scope`` on the daemon
#: (WO-AUTOLOOP-CYCLES), never accepted as a client arg here.
ARGS_REFLEX_ARM = frozenset(PROPOSAL_IDENTITY)

#: Status fields promoted to guard facts, by their status key.
#:
#: Deliberately a short, literal allowlist rather than "everything in the
#: payload". A guard names a fact; if the name silently tracked whatever the
#: daemon happened to emit this release, a renamed status key would turn every
#: guard on it from a live check into an ``UNKNOWN`` -- and ``UNKNOWN`` fails
#: closed, so the rule would go quietly ineligible rather than loudly wrong.
#: An explicit list makes that rename a test failure instead.
#:
#: Game-world facts (credits, sector, turns) are **not** here: they have no
#: live producer in the status response today. Omitting them is the honest
#: choice -- an absent fact reaches the kernel as ``UNKNOWN`` and fails its
#: guard closed, whereas inventing a default would arm a rule on a number
#: nobody measured.
STATUS_FACT_KEYS = (
    "connected",
    "idle_ms",
    "subscribers",
)


def facts_from_status(status: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """Derive guard facts from a daemon status payload.

    **A missing key is omitted, never defaulted.** The kernel treats an absent
    fact as ``UNKNOWN`` and fails every guard on it closed; a default here
    would replace that refusal with a confident answer derived from nothing.
    ``None`` is dropped for the same reason -- the daemon uses it for "no
    value", which is an absence wearing a value's clothes.
    """
    if not isinstance(status, Mapping):
        return {}
    facts: dict[str, Any] = {}
    for key in STATUS_FACT_KEYS:
        value = status.get(key)
        if value is None:
            continue
        facts[key] = value
    return facts


def propose_macro(
    screen_class: Optional[str],
    facts: Optional[Mapping[str, Any]] = None,
    *,
    state_dir=None,
    rules_path=None,
) -> Decision:
    """Propose the macro the taught library says fits *screen_class*, or a typed STOP.

    A **proposal**. Nothing here sends, arms, or executes; see this module's
    docstring for the two landings that stay inert.

    ``screen_class`` is ``classify_screen``'s closed-vocabulary answer. A
    falsy or non-string class returns the unreadable-library stop's sibling
    -- ``autopilot_no_candidates`` qualified with ``unknown`` -- via the
    kernel, since a screen we cannot name genuinely matches no rule.
    """
    report = read_rule_store(state_dir=state_dir, rules_path=rules_path)
    status = report["status"]
    if status not in _AUTHORISING_STATUSES:
        # We could not read the whole library. Saying "nothing matched" would
        # claim a search we did not complete, and on `partial` the file we
        # could not read may be the one holding the veto.
        return Decision(stop_reason=qualify(STOP_RULES_UNREADABLE, str(status)))
    return select_rule(
        screen_class if isinstance(screen_class, str) and screen_class else "unknown",
        report["rules"],
        facts or {},
    )


def proposal_drift(
    claimed: Optional[Mapping[str, Any]],
    *,
    decision: Decision,
    classification: Optional[str],
) -> Optional[str]:
    """The first identity field that no longer matches, or ``None`` if all do.

    ``claimed`` is the identity a human was shown and confirmed; ``decision``
    and ``classification`` are what the library proposes for the screen *now*.
    ``None`` means the run about to launch is the run that was confirmed.

    **Every field must be a non-empty string on the claimed side, and that is
    the whole point rather than input hygiene.** ``rule_id`` is ``None`` on
    the kernel's document-level outcomes, and ``classification`` is ``None``
    for a screen the classifier could not name -- so a caller that omits a
    field would be compared ``None == None`` and *pass*, arming a run whose
    identity was never established. A confirmation has to be of something.
    An absent field is therefore reported as drift on that field: it does not
    match the proposal, because it does not name one.

    Checked in :data:`PROPOSAL_IDENTITY` order and reported one at a time. The
    caller gets the first mismatch rather than a set, because the operator
    response to any single one is identical -- look again -- and a combined
    reason would need parsing to act on.

    This is the only layer that compares identity; the daemon verb does not
    repeat it. Never raises: a ``claimed`` that is not a mapping at all drifts
    on the first field.
    """
    fresh = {
        "rule_id": decision.rule_id,
        "macro": decision.macro,
        "classification": classification,
    }
    given = claimed if isinstance(claimed, Mapping) else {}
    for field in PROPOSAL_IDENTITY:
        want = given.get(field)
        if not isinstance(want, str) or not want:
            return qualify(STOP_PROPOSAL_DRIFT, field)
        if fresh.get(field) != want:
            return qualify(STOP_PROPOSAL_DRIFT, field)
    return None
