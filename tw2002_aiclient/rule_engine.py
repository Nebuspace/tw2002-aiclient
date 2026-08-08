"""The guarded rule–macro reflex kernel: one settled screen → one macro or one typed STOP.

Canon: `canon/architecture/rule-macro-engine.md` (the reflex layer). This module
is the single-cycle decision only. The multi-cycle run-loop that repeats it, the
macro replay mechanics, and the STOP→keyboard handoff all live elsewhere and are
deliberately not touched here (WO-GUARDED-RULE-KERNEL).

**Dependency-neutral by construction.** Nothing here imports curses, a socket,
the daemon, the control lock, the macro player, or the filesystem. The one
sibling import is `halt_reasons`, which is itself neutral by construction and
exists precisely so the `<code>:<detail>` shape is not re-derived per site.

That neutrality is why the canonical STOP codes below are *literals* rather than
imports. The live catalog is `cockpit.stopbanner.INTERVENTION_REASON_LABELS`, but
that module imports `session.control_lock`, and a control-lock edge is exactly
what this kernel must not have. `tests/test_rule_engine.py` imports the catalog
and asserts every code emitted here is a member, so the codes stay pinned to the
real catalog without the kernel ever reaching for it.

**Zero reasoning per cycle.** Every step is a lookup, a boolean filter, or an
integer comparison. No model call, no expected-value scoring, no ranking of
competing goals. Canon calls this property load-bearing; the AI is a
retrospective author of rules, never a participant in a live cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence

from tw2002_aiclient.halt_reasons import qualify

__all__ = [
    "UNKNOWN",
    "Guard",
    "Rule",
    "Decision",
    "RuleDocumentError",
    "STOP_NO_CANDIDATES",
    "STOP_AMBIGUOUS",
    "GUARD_OPERATORS",
    "POSTURE_INELIGIBLE",
    "POSTURE_STOP",
    "SCOPE_ONE_SHOT",
    "SCOPE_REPEATING",
    "ORIGIN_HUMAN",
    "ORIGIN_AI_APPROVED",
    "VALID_ORIGINS",
    "select_rule",
    "rule_to_dict",
    "rule_from_dict",
    "document_to_dicts",
    "document_from_dicts",
]


# ── typed STOP codes ────────────────────────────────────────────────────────
#
# Canon `control-and-escalation.md` §"Escalation reason-code catalog" names the
# first two. They are NOT invented here.

#: No approved rule's `screen_match` matched the settled screen -- canon:
#: "no rule matched the current screen; nothing to play, so hand off". Also the
#: outcome when every matching rule was filtered out as ineligible: canon's
#: reflex loop routes "no survivors at all" to the same escalate-on-unknown.
STOP_NO_CANDIDATES = "autopilot_no_candidates"

#: Two or more eligible rules tie at the top priority. Canon fixes `priority` as
#: an integer total order and is SILENT on equal priority, so this code is new.
#: The catalog is "open by construction" (Max ruling 1A): an unlabelled code
#: renders as its own raw text until a label row is added, which is a disclosed
#: DOC-GAP rather than a breakage. Resolving a tie by rule id instead was
#: rejected -- it would invent an ordering the rule author never expressed and
#: fire a macro on the strength of an alphabetical accident.
STOP_AMBIGUOUS = "autopilot_ambiguous_rules"

POSTURE_INELIGIBLE = "ineligible"
POSTURE_STOP = "stop"

SCOPE_ONE_SHOT = "one-shot"
SCOPE_REPEATING = "repeating"

# Teaching-provenance axis (canon/engine/coverage-metrics.md). Authorship of a
# guarded rule — never a live-sender value. Absent on pre-field documents.
ORIGIN_HUMAN = "human"
ORIGIN_AI_APPROVED = "ai-approved"
VALID_ORIGINS = (ORIGIN_HUMAN, ORIGIN_AI_APPROVED)

_SCOPES = (SCOPE_ONE_SHOT, SCOPE_REPEATING)
_POSTURES = (POSTURE_INELIGIBLE, POSTURE_STOP)


class RuleDocumentError(ValueError):
    """A rule document is malformed.

    Raised on strict parse. A `ValueError` subclass so a caller that already
    contains value errors keeps working, but its own type so a caller that needs
    to tell "bad document" from "bad arithmetic" can.
    """


class _Unknown:
    """The unknown-fact sentinel.

    Canon: "Unknown is a first-class guard input ... the fact is *unknown*, not
    zero and not a guess." A distinct singleton rather than `None` so a fact
    store can carry an explicit unknown that is indistinguishable, to every
    guard, from a fact it never held.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging affordance
        return "UNKNOWN"

    def __bool__(self) -> bool:
        # An unknown must never be usable as a truth value. Anything that tries
        # `if facts[...]` on it is asking a question with no honest answer, and
        # a silent False there is precisely the fabricated value canon forbids.
        raise TypeError("UNKNOWN has no truth value -- guards must fail closed on it")


UNKNOWN = _Unknown()


# ── guard operators ─────────────────────────────────────────────────────────
#
# Each returns True (passed), False (failed), or None (UNDECIDABLE -- the
# comparison is not meaningful for these operand types). Undecidable is treated
# exactly like a failure, never like a pass: a guard that cannot be evaluated has
# not been satisfied.
#
# `bool` is a subclass of `int` in Python, so `True < 5` is a legal comparison
# that silently reads True as 1. Every numeric operator below excludes bool
# explicitly -- a fighters count of `True` is a broken fact, not the number one.


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _numeric(op):
    def run(actual: Any, expected: Any) -> Optional[bool]:
        if not (_is_number(actual) and _is_number(expected)):
            return None
        return op(actual, expected)

    return run


def _op_eq(actual: Any, expected: Any) -> Optional[bool]:
    # Deliberately total: `5 == "5"` is a decidable False, not undecidable. An
    # equality guard asks "is the fact this exact value", and a type mismatch is
    # a clear no rather than an unanswerable question.
    return actual == expected


def _op_ne(actual: Any, expected: Any) -> Optional[bool]:
    return actual != expected


def _op_is_true(actual: Any, _expected: Any) -> Optional[bool]:
    # Identity on the literal, not truthiness. `bool(1)` and `bool("no")` are
    # both True, and a guard that accepts them is asserting something the fact
    # never said. Same discipline as the App-chip's `value is False` gate.
    if not isinstance(actual, bool):
        return None
    return actual is True


def _op_is_false(actual: Any, _expected: Any) -> Optional[bool]:
    if not isinstance(actual, bool):
        return None
    return actual is False


#: operator name -> (callable, takes_value)
GUARD_OPERATORS: Mapping[str, tuple] = {
    "eq": (_op_eq, True),
    "ne": (_op_ne, True),
    "lt": (_numeric(lambda a, b: a < b), True),
    "le": (_numeric(lambda a, b: a <= b), True),
    "gt": (_numeric(lambda a, b: a > b), True),
    "ge": (_numeric(lambda a, b: a >= b), True),
    "is_true": (_op_is_true, False),
    "is_false": (_op_is_false, False),
}


# ── schema ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Guard:
    """One typed predicate over a supplied fact.

    `posture` decides what a failure means: `ineligible` removes the rule from
    contention; `stop` escalates and outranks any fireable rule. `stop_reason` is
    required for `stop` and forbidden otherwise -- a STOP with no typed reason
    would be a free-text halt, which canon does not permit.
    """

    fact: str
    op: str
    value: Any = None
    posture: str = POSTURE_INELIGIBLE
    stop_reason: Optional[str] = None


@dataclass(frozen=True)
class Rule:
    """`when(screen_match + guards) → do(macro)`, carrying priority and scope."""

    rule_id: str
    screen_match: str
    do: str
    priority: int
    scope: str = SCOPE_ONE_SHOT
    approved: bool = False
    guards: tuple = ()
    # Teaching provenance: ``human`` | ``ai-approved`` | None (legacy / unknown).
    # Never silently defaulted to either real origin when the field is absent.
    origin: Optional[str] = None


@dataclass(frozen=True)
class Decision:
    """The single-cycle outcome: exactly one of `macro` or `stop_reason` is set.

    `rule_id` names the rule responsible -- the winner when a macro fires, the
    STOPping rule when a guard refused, and `None` for document-level outcomes
    (no candidates, ambiguity) which no single rule owns.

    `scope` is the winning rule's ``one-shot`` / ``repeating`` when a macro
    fires (WO-AUTOLOOP-CYCLES); ``None`` on every STOP / document-level
    outcome, because those have no run to bound.
    """

    macro: Optional[str] = None
    rule_id: Optional[str] = None
    stop_reason: Optional[str] = None
    scope: Optional[str] = None

    @property
    def fired(self) -> bool:
        return self.macro is not None


# ── guard + rule evaluation ─────────────────────────────────────────────────

_PASS = "pass"
_INELIGIBLE = "ineligible"
_STOP = "stop"


def _fact(facts: Mapping[str, Any], name: str) -> Any:
    """The fact, or UNKNOWN.

    Absent, explicitly UNKNOWN, and `None` all read as unknown. `None` is folded
    in deliberately: a fact store that could not read a value has no way to say
    so other than absence or a null, and treating a null as a real value is the
    coercion canon forbids.
    """
    if name not in facts:
        return UNKNOWN
    value = facts[name]
    if value is None or isinstance(value, _Unknown):
        return UNKNOWN
    return value


def _evaluate_guard(guard: Guard, facts: Mapping[str, Any]) -> bool:
    """True iff the guard is satisfied. Unknown and undecidable both fail."""
    actual = _fact(facts, guard.fact)
    if isinstance(actual, _Unknown):
        return False
    fn, _takes_value = GUARD_OPERATORS[guard.op]
    outcome = fn(actual, guard.value)
    return outcome is True


def _evaluate_rule(rule: Rule, facts: Mapping[str, Any]) -> tuple:
    """`(_PASS|_INELIGIBLE|_STOP, reason_or_None)`.

    STOP dominates within a rule as well as across rules: if any `stop`-posture
    guard fails, the rule STOPs even when an `ineligible` guard also failed.
    The reported reason is the first failing `stop` guard **in the rule's own
    declared order** -- that order is authored content, not an accident of how
    the caller happened to assemble the document, so this stays deterministic
    without pretending guard order is meaningless.
    """
    stopped = None
    ineligible = False
    for guard in rule.guards:
        if _evaluate_guard(guard, facts):
            continue
        if guard.posture == POSTURE_STOP:
            if stopped is None:
                stopped = qualify(str(guard.stop_reason), guard.fact)
        else:
            ineligible = True
    if stopped is not None:
        return (_STOP, stopped)
    if ineligible:
        return (_INELIGIBLE, None)
    return (_PASS, None)


# ── selection ───────────────────────────────────────────────────────────────


def select_rule(
    screen_class: str,
    rules: Iterable[Rule],
    facts: Optional[Mapping[str, Any]] = None,
) -> Decision:
    """One settled screen class → one macro or one typed STOP.

    Canon's reflex loop, with one clarification the canon prose needs (banked as
    a DOC-GAP): `rule-macro-engine.md:81` says "drop any rule with a failing
    guard" and `:82` then asks whether a *survivor* has a guard that says STOP.
    Read literally, line 81 removes every STOP guard before line 82 can see one,
    making STOP-dominance unreachable and contradicting the same document's own
    outcome table. Only `ineligible` failures drop; `stop` failures escalate.

    A STOP outranks a fireable rule **regardless of priority** -- priority
    chooses between rules that may fire, and a rule that says "do not act" is
    not competing for that slot.
    """
    facts = facts or {}
    # Drafts are filtered here, before anything else looks at them: canon says an
    # unapproved rule "is not in the set the collect step draws from", so it has
    # no priority standing, cannot win a tie, and -- importantly -- cannot STOP
    # either. An inert draft that could halt the app would still be firing.
    candidates = [
        rule
        for rule in rules
        if rule.approved and rule.screen_match == screen_class
    ]

    stops: list = []
    eligible: list = []
    for rule in candidates:
        verdict, reason = _evaluate_rule(rule, facts)
        if verdict == _STOP:
            stops.append((rule, reason))
        elif verdict == _PASS:
            eligible.append(rule)

    if stops:
        # Which STOP to report must not depend on input order. Highest priority
        # first, then rule id -- both intrinsic to the rules, so any permutation
        # of the same document reports the same reason.
        rule, reason = min(stops, key=lambda pair: (-pair[0].priority, pair[0].rule_id))
        return Decision(macro=None, rule_id=rule.rule_id, stop_reason=reason)

    if not eligible:
        return Decision(stop_reason=qualify(STOP_NO_CANDIDATES, screen_class))

    top = max(rule.priority for rule in eligible)
    winners = [rule for rule in eligible if rule.priority == top]
    if len(winners) > 1:
        # Ambiguity is resolved at SELECTION time, not by rejecting the document
        # at parse time: two rules sharing a priority on *different* screens
        # never compete, and refusing that document would reject a legal rule set.
        return Decision(stop_reason=qualify(STOP_AMBIGUOUS, str(top)))

    winner = winners[0]
    return Decision(macro=winner.do, rule_id=winner.rule_id, scope=winner.scope)


# ── strict serialization ────────────────────────────────────────────────────

_GUARD_REQUIRED = ("fact", "op")
_GUARD_OPTIONAL = ("value", "posture", "stop_reason")
_RULE_REQUIRED = ("rule_id", "screen_match", "do", "priority")
_RULE_OPTIONAL = ("scope", "approved", "guards", "origin")


def _require_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuleDocumentError(f"{field} must be a non-empty string, got {value!r}")
    return value


def _check_keys(payload: Any, required: Sequence[str], optional: Sequence[str], what: str) -> None:
    if not isinstance(payload, Mapping):
        raise RuleDocumentError(f"{what} must be a mapping, got {type(payload).__name__}")
    keys = set(payload)
    missing = [k for k in required if k not in keys]
    if missing:
        raise RuleDocumentError(f"{what} missing required field(s): {sorted(missing)}")
    # Unknown keys are REJECTED rather than ignored. Ignoring them is what makes
    # a round-trip lose data silently -- the field survives the first parse in
    # nobody's hands and is simply absent from the re-serialized document.
    extra = sorted(keys - set(required) - set(optional))
    if extra:
        raise RuleDocumentError(f"{what} has unknown field(s): {extra}")


def guard_from_dict(payload: Any) -> Guard:
    _check_keys(payload, _GUARD_REQUIRED, _GUARD_OPTIONAL, "guard")
    op = _require_str(payload["op"], "guard.op")
    if op not in GUARD_OPERATORS:
        raise RuleDocumentError(f"guard.op {op!r} is not one of {sorted(GUARD_OPERATORS)}")
    posture = payload.get("posture", POSTURE_INELIGIBLE)
    if posture not in _POSTURES:
        raise RuleDocumentError(f"guard.posture {posture!r} is not one of {list(_POSTURES)}")
    stop_reason = payload.get("stop_reason")
    if posture == POSTURE_STOP:
        _require_str(stop_reason, "guard.stop_reason")
    elif stop_reason is not None:
        raise RuleDocumentError(
            "guard.stop_reason is only meaningful when posture is 'stop'; "
            "a reason on an 'ineligible' guard would never be emitted"
        )
    _fn, takes_value = GUARD_OPERATORS[op]
    has_value = "value" in payload
    if takes_value and not has_value:
        raise RuleDocumentError(f"guard.op {op!r} requires a 'value'")
    if not takes_value and has_value:
        raise RuleDocumentError(f"guard.op {op!r} takes no 'value'")
    return Guard(
        fact=_require_str(payload["fact"], "guard.fact"),
        op=op,
        value=payload.get("value"),
        posture=posture,
        stop_reason=stop_reason,
    )


def guard_to_dict(guard: Guard) -> dict:
    out: dict = {"fact": guard.fact, "op": guard.op}
    _fn, takes_value = GUARD_OPERATORS[guard.op]
    if takes_value:
        out["value"] = guard.value
    out["posture"] = guard.posture
    if guard.posture == POSTURE_STOP:
        out["stop_reason"] = guard.stop_reason
    return out


def rule_from_dict(payload: Any) -> Rule:
    _check_keys(payload, _RULE_REQUIRED, _RULE_OPTIONAL, "rule")
    priority = payload["priority"]
    if not isinstance(priority, int) or isinstance(priority, bool):
        raise RuleDocumentError(f"rule.priority must be an int, got {priority!r}")
    scope = payload.get("scope", SCOPE_ONE_SHOT)
    if scope not in _SCOPES:
        raise RuleDocumentError(f"rule.scope {scope!r} is not one of {list(_SCOPES)}")
    approved = payload.get("approved", False)
    if not isinstance(approved, bool):
        # A truthy string here is exactly how a draft becomes live by accident.
        raise RuleDocumentError(f"rule.approved must be a bool, got {approved!r}")
    # Absent ``origin`` stays None (legacy/unknown bucket). Never invent human
    # or ai-approved for a pre-field document.
    if "origin" in payload:
        origin = payload["origin"]
        if origin not in VALID_ORIGINS:
            raise RuleDocumentError(
                f"rule.origin {origin!r} is not one of {list(VALID_ORIGINS)}"
            )
    else:
        origin = None
    raw_guards = payload.get("guards", ())
    if isinstance(raw_guards, (str, bytes, Mapping)) or not isinstance(raw_guards, Iterable):
        raise RuleDocumentError("rule.guards must be a list of guard mappings")
    return Rule(
        rule_id=_require_str(payload["rule_id"], "rule.rule_id"),
        screen_match=_require_str(payload["screen_match"], "rule.screen_match"),
        do=_require_str(payload["do"], "rule.do"),
        priority=priority,
        scope=scope,
        approved=approved,
        guards=tuple(guard_from_dict(g) for g in raw_guards),
        origin=origin,
    )


def rule_to_dict(rule: Rule) -> dict:
    out = {
        "rule_id": rule.rule_id,
        "screen_match": rule.screen_match,
        "do": rule.do,
        "priority": rule.priority,
        "scope": rule.scope,
        "approved": rule.approved,
        "guards": [guard_to_dict(g) for g in rule.guards],
    }
    # Omit when unset so a legacy document round-trips without inventing the
    # field — coverage then buckets it as unknown/legacy.
    if rule.origin is not None:
        out["origin"] = rule.origin
    return out


def document_from_dicts(payload: Any) -> tuple:
    if isinstance(payload, (str, bytes, Mapping)) or not isinstance(payload, Iterable):
        raise RuleDocumentError("a rule document must be a list of rule mappings")
    rules = tuple(rule_from_dict(item) for item in payload)
    seen: set = set()
    for rule in rules:
        if rule.rule_id in seen:
            # Duplicate ids break the STOP tie-break's determinism and make
            # "which rule fired" unanswerable in a log.
            raise RuleDocumentError(f"duplicate rule_id {rule.rule_id!r}")
        seen.add(rule.rule_id)
    return rules


def document_to_dicts(rules: Iterable[Rule]) -> list:
    return [rule_to_dict(rule) for rule in rules]
