"""Analyze draft human-approval gate — WO-P5-070, bridged by
WO-DRAFT-APPROVE-KERNEL-BRIDGE.

After an Analyze overlay closes, the AI teacher's proposed rule is a
**draft** — inert until the human explicitly approves it.  This module
owns the draft schema, the ``y/N`` approval gate (same default-deny key
policy as :mod:`armconfirm`), and promotion to a playback-eligible stub.

No live I/O, no send path, no ledger writer — ``app.py`` records
approval attribution on confirm only.

Two vocabularies, one bridge
----------------------------
The stub shape here (``when``/``do``/``source``/``playback_eligible``) predates
the kernel rule schema (``rule_id``/``screen_match``/``do``/``priority``) and
they are **disjoint**: the kernel's parser rejects unknown fields, so
``source`` and ``playback_eligible`` are refused outright, and ``rule_id`` and
``priority`` have no source in a stub at all.

:func:`bridge_to_kernel_document` is the one crossing. It is a **pure
translation** — no filesystem, no approval — and it **refuses rather than
invents**. What the teacher observed (the screen class) it carries across;
what only a human can decide (*what to call this*, *what it does*, *how it
ranks*) it demands as arguments and rejects if absent.

That asymmetry is the whole design, and it is Max's ruling of 2026-07-29:
*no invented defaults*. A minted ``priority`` would be the worst of them --
every AI-authored rule would arrive at the same rank, and the kernel STOPs on
a tie (``autopilot_ambiguous_rules``) rather than guessing, so a default would
convert "the teacher proposed something" into "the autopilot halts" at exactly
the moment the library became useful.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from tw2002_aiclient.cockpit import assign_trigger

CONFIRM = "confirm"
CANCEL = "cancel"

#: Fields a human must supply; the teacher cannot know any of them.
HUMAN_SUPPLIED_FIELDS = ("rule_id", "do", "priority")


class DraftBridgeError(ValueError):
    """A stub could not be translated into a kernel rule document."""

_CONFIRM_KEYS = frozenset({ord("y"), ord("Y")})

DRAFT_APPROVE_TONE = "info"
CONFIRM_HINT = "y/N"
_HINT_GAP = "  "


def create_analyze_draft(screen_class: object = None) -> dict:
    """Return an inert analyze-sourced draft rule (never playback-eligible)."""
    stub = assign_trigger.create_stub(screen_class)
    stub["source"] = "analyze"
    stub["approved"] = False
    stub["playback_eligible"] = False
    return stub


def screen_of(stub: object) -> str:
    """The settled screen class a stub was scaffolded for, or ``""``.

    ``""`` for anything malformed rather than a raise, matching this module's
    house posture for hostile input. The caller decides whether an empty class
    is fatal -- :func:`bridge_to_kernel_document` says it is, because a rule
    with no screen to match is not a rule.
    """
    if not isinstance(stub, Mapping):
        return ""
    when = stub.get("when")
    if not isinstance(when, Mapping):
        return ""
    screen = when.get("screen")
    return screen if isinstance(screen, str) else ""


def bridge_to_kernel_document(
    stub: object,
    *,
    rule_id: object,
    do: object,
    priority: object,
    scope: object = None,
) -> dict:
    """Translate an analyze *stub* into a kernel rule document. **Pure.**

    Returns a dict shaped for
    :func:`~tw2002_aiclient.rule_engine.rule_from_dict`, always carrying
    ``approved: False``. Touches no filesystem and approves nothing --
    persistence is ``rules.writer.write_draft``'s job and blessing is
    ``promote_draft``'s, and this function deliberately calls neither so that
    "what can create a rule" and "what can bless one" keep their single
    answers.

    **Refuses rather than invents.** ``rule_id``, ``do`` and ``priority`` are
    keyword-only and have **no defaults** -- omitting one is a ``TypeError``
    from Python itself, before any of this code runs, which is a stronger
    guarantee than a check I could later be argued out of. Supplying one as
    ``None`` or empty raises :class:`DraftBridgeError`.

    How much of this check is load-bearing -- measured, not assumed
    ---------------------------------------------------------------------
    Mostly it is not, and saying so is the point. ``rule_from_dict`` already
    refuses ``None`` **and** ``""`` for all three fields, so those paths reach
    the kernel's refusal whether or not this branch exists. Exercised against
    the parser, the cases this adds are exactly two: a **whitespace-only**
    ``rule_id`` or ``do`` (``"   "`` is a non-empty string, so the parser
    admits it and a rule named ``"   "`` would be born).

    It is kept for that pair and for the *message*: the kernel says "rule.do
    must be a non-empty string", which is true and tells an operator nothing
    about whose job it is to supply one. Accept 2 asks for an operator-visible
    reason that no value was minted, and this is where that sentence lives.

    The real guarantee is above it and is structural: the three parameters
    have **no defaults**, so omitting one raises ``TypeError`` before any of
    this runs. Type-checking ``priority`` is left to ``rule_from_dict``
    entirely -- re-implementing it here would be the second admission path
    ``rules/store.py`` exists to refuse.
    """
    screen = screen_of(stub)
    if not screen:
        raise DraftBridgeError(
            "the analyze stub carries no screen class; there is nothing to match on"
        )

    missing = []
    for name, value in (("rule_id", rule_id), ("do", do), ("priority", priority)):
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(name)
    if missing:
        raise DraftBridgeError(
            "a human must supply "
            + ", ".join(missing)
            + " -- these are never defaulted (a minted priority would collide "
            "every rule into autopilot_ambiguous_rules)"
        )

    when = stub.get("when") if isinstance(stub, Mapping) else None
    guards = when.get("guards") if isinstance(when, Mapping) else None

    document: dict[str, Any] = {
        "rule_id": rule_id,
        "screen_match": screen,
        "do": do,
        "priority": priority,
        # Always False, and there is no parameter to ask otherwise -- same
        # shape as `write_draft`. Blessing lives in `promote_draft` alone.
        "approved": False,
    }
    if guards is not None:
        # Forwarded, never re-shaped. Today `assign_trigger.create_stub` always
        # emits `[]` (guard atoms are Phase 6), so this is inert -- but a guard
        # that ever appears must be judged by the kernel's parser, not
        # translated by a second opinion here.
        document["guards"] = guards
    if scope is not None:
        document["scope"] = scope
    return document


def promote_to_approved(draft: object) -> dict | None:
    """Copy ``draft`` with approval flags set, or ``None`` if not a dict."""
    if not isinstance(draft, dict):
        return None
    out = dict(draft)
    when = out.get("when")
    if isinstance(when, dict):
        out["when"] = dict(when)
        guards = when.get("guards")
        if isinstance(guards, list):
            out["when"]["guards"] = list(guards)
    out["approved"] = True
    out["playback_eligible"] = True
    return out


def compose_bridge_command(screen: object = None) -> str:
    """The exact command an operator types to finish a recorded proposal.

    The cockpit cannot collect ``rule_id``/``do``/``priority`` -- it has no
    typed-entry surface at all, and Max ruled (2026-07-29) that they must be
    human-supplied rather than minted. So the settled screen class, which is
    the one thing the teacher genuinely observed, is handed over pre-filled
    and the three human decisions are left as visible placeholders.

    Placeholders are UPPERCASE so it is obvious the line is not runnable as
    printed. A copy-pasteable command with plausible-looking values would be
    worse than none: it would invite exactly the minted defaults the ruling
    forbids, typed by a human who thought they were accepting a suggestion.
    """
    label = screen if isinstance(screen, str) and screen else "?"
    return f"tw rule draft --screen {label} --rule-id ID --do MACRO --priority N"


def compose_draft_approve_line(screen: object = None, *, unicode_ok: object = True) -> str:
    """``Approve analyze draft (<screen>)?  y/N`` — never raises."""
    label = screen if isinstance(screen, str) and screen else "?"
    return f"Approve analyze draft ({label})?{ _HINT_GAP}{CONFIRM_HINT}"


def resolve_draft_approve_key(key: object) -> str:
    """``CONFIRM`` for ``y``/``Y`` only; ``CANCEL`` for everything else."""
    if isinstance(key, bool) or not isinstance(key, int):
        return CANCEL
    return CONFIRM if key in _CONFIRM_KEYS else CANCEL
