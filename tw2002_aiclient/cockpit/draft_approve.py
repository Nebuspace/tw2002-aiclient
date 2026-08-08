"""Analyze draft human-approval gate — WO-P5-070, bridged by
WO-DRAFT-APPROVE-KERNEL-BRIDGE.

After an Analyze overlay closes, the AI teacher's proposed rule is a
**draft** — inert until the human explicitly approves it.  This module
owns the draft schema, the ``y/N`` approval gate (same default-deny key
policy as :mod:`armconfirm`), and promotion to a playback-eligible stub.

No live I/O, no send path, no ledger writer — ``app.py`` records
approval attribution on confirm only, and persists via
``rules.writer.write_draft`` / ``promote_draft`` after the Play identity
session collects the three human fields (WO-PLAY-RULE-IDENTITY).

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

from typing import Any, Mapping

from tw2002_aiclient.alignment_gate import AlignmentRefusal, refuse_pvp_aggression_rule
from tw2002_aiclient.cockpit import assign_trigger

CONFIRM = "confirm"
CANCEL = "cancel"

#: Identity-entry outcomes (sequential rule_id → do → priority).
CONTINUE = "continue"
COMPLETE = "complete"
REFUSE = "refuse"

#: Fields a human must supply; the teacher cannot know any of them.
HUMAN_SUPPLIED_FIELDS = ("rule_id", "do", "priority", "scope")

#: Literal scope spellings — same set the kernel admits (no aliases).
SCOPE_ONE_SHOT = "one-shot"
SCOPE_REPEATING = "repeating"
_SCOPES = frozenset({SCOPE_ONE_SHOT, SCOPE_REPEATING})

#: Control-strip labels — never look like filled-in suggestions.
_IDENTITY_LABELS = {
    "rule_id": "rule id",
    "do": "macro (do)",
    "priority": "priority (int)",
    "scope": "scope (one-shot|repeating)",
}

# Enter / backspace without importing curses (screens may also pass KEY_*).
_ENTER_KEYS = frozenset({10, 13, 343})  # \n, \r, curses.KEY_ENTER
_BACKSPACE_KEYS = frozenset({8, 127, 263})  # BS, DEL, curses.KEY_BACKSPACE


class DraftBridgeError(ValueError):
    """A stub could not be translated into a kernel rule document."""


_CONFIRM_KEYS = frozenset({ord("y"), ord("Y")})

DRAFT_APPROVE_TONE = "info"
IDENTITY_TONE = "info"
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
    scope: object,
) -> dict:
    """Translate an analyze *stub* into a kernel rule document. **Pure.**

    Returns a dict shaped for
    :func:`~tw2002_aiclient.rule_engine.rule_from_dict`, always carrying
    ``approved: False``. Touches no filesystem and approves nothing --
    persistence is ``rules.writer.write_draft``'s job and blessing is
    ``promote_draft``'s, and this function deliberately calls neither so that
    "what can create a rule" and "what can bless one" keep their single
    answers.

    **Refuses rather than invents.** ``rule_id``, ``do``, ``priority`` and
    ``scope`` are keyword-only and have **no defaults** -- omitting one is a
    ``TypeError`` from Python itself, before any of this code runs, which is a
    stronger guarantee than a check I could later be argued out of. Supplying
    one as ``None`` or empty raises :class:`DraftBridgeError`. ``scope`` must
    be the literal ``one-shot`` or ``repeating`` — the kernel's silent
    one-shot default is exactly what Play identity exists to close.

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
    for name, value in (
        ("rule_id", rule_id),
        ("do", do),
        ("priority", priority),
        ("scope", scope),
    ):
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(name)
    if missing:
        raise DraftBridgeError(
            "a human must supply "
            + ", ".join(missing)
            + " -- these are never defaulted (a minted priority would collide "
            "every rule into autopilot_ambiguous_rules; a minted scope would "
            "silently one-shot every rule)"
        )
    if scope not in _SCOPES:
        raise DraftBridgeError(
            "scope must be one-shot or repeating — never defaulted"
        )

    when = stub.get("when") if isinstance(stub, Mapping) else None
    guards = when.get("guards") if isinstance(when, Mapping) else None

    document: dict[str, Any] = {
        "rule_id": rule_id,
        "screen_match": screen,
        "do": do,
        "priority": priority,
        "scope": scope,
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
    try:
        refuse_pvp_aggression_rule(document)
    except AlignmentRefusal as exc:
        raise DraftBridgeError(str(exc)) from None

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


def compose_draft_approve_line(screen: object = None, *, unicode_ok: object = True) -> str:
    """``Approve analyze draft (<screen>)?  y/N`` — never raises."""
    label = screen if isinstance(screen, str) and screen else "?"
    return f"Approve analyze draft ({label})?{ _HINT_GAP}{CONFIRM_HINT}"


def resolve_draft_approve_key(key: object) -> str:
    """``CONFIRM`` for ``y``/``Y`` only; ``CANCEL`` for everything else."""
    if isinstance(key, bool) or not isinstance(key, int):
        return CANCEL
    return CONFIRM if key in _CONFIRM_KEYS else CANCEL


def create_identity_session(stub: object = None) -> dict:
    """Start sequential collection of ``rule_id`` / ``do`` / ``priority``.

    Pure session dict — no filesystem. Esc cancels with nothing written;
    Enter advances only after the current field validates.
    """
    return {
        "stub": stub if isinstance(stub, dict) else None,
        "field_index": 0,
        "buf": "",
        "values": {},
        "refuse_reason": None,
    }


def identity_field_name(session: object) -> str:
    """Current field name, or ``""`` if the session is malformed."""
    if not isinstance(session, dict):
        return ""
    idx = session.get("field_index")
    if not isinstance(idx, int) or idx < 0 or idx >= len(HUMAN_SUPPLIED_FIELDS):
        return ""
    return HUMAN_SUPPLIED_FIELDS[idx]


def compose_identity_prompt(session: object = None, *, unicode_ok: object = True) -> str:
    """Control-strip prompt for the current identity field. Never raises."""
    del unicode_ok  # reserved for future glyph policy; keep signature stable
    if not isinstance(session, dict):
        return "Rule identity — (session lost)  Esc cancel"
    field = identity_field_name(session)
    if not field:
        return "Rule identity — (session lost)  Esc cancel"
    label = _IDENTITY_LABELS.get(field, field)
    buf = session.get("buf") if isinstance(session.get("buf"), str) else ""
    refuse = session.get("refuse_reason")
    refuse = refuse if isinstance(refuse, str) and refuse else None
    base = f"{label}: {buf}_"
    if refuse:
        return f"{refuse} — {base}"
    return f"Rule identity — {base}  (Enter next · Esc cancel)"


def compose_rule_blessed_line(
    rule_id: object = None,
    do: object = None,
    scope: object = None,
) -> str:
    """Status after a successful write+promote — names the rule and points at V.

    Discloses that ``repeating`` arms under the hard cycle ceiling
    (WO-AUTOLOOP-CYCLES); ``one-shot`` stays one pass.
    """
    rid = rule_id if isinstance(rule_id, str) and rule_id.strip() else "?"
    macro = do if isinstance(do, str) and do.strip() else "?"
    sc = scope if isinstance(scope, str) and scope.strip() else "?"
    if sc == "repeating":
        return (
            f"rule blessed — {rid} does {macro} [{sc}]; "
            f"V can propose multi-pass (capped)"
        )
    return (
        f"rule blessed — {rid} does {macro} [{sc}]; "
        f"V can propose it (arm is one-pass)"
    )


def _commit_identity_field(session: dict) -> str:
    """Validate ``session['buf']`` into ``values``; advance or complete.

    Returns ``COMPLETE``, ``CONTINUE``, or ``REFUSE`` (sets ``refuse_reason``).
    """
    field = identity_field_name(session)
    raw = session.get("buf") if isinstance(session.get("buf"), str) else ""
    raw = raw.strip()
    if not raw:
        session["refuse_reason"] = (
            f"{field} required — never defaulted (Max 2026-07-29)"
        )
        return REFUSE

    if field == "priority":
        try:
            value = int(raw, 10)
        except ValueError:
            session["refuse_reason"] = "priority must be an int"
            return REFUSE
    elif field == "scope":
        if raw not in _SCOPES:
            session["refuse_reason"] = (
                "scope must be one-shot or repeating — never defaulted"
            )
            return REFUSE
        value = raw
    else:
        value = raw

    values = session.get("values")
    if not isinstance(values, dict):
        values = {}
        session["values"] = values
    values[field] = value
    session["buf"] = ""
    session["refuse_reason"] = None

    next_idx = int(session.get("field_index") or 0) + 1
    if next_idx >= len(HUMAN_SUPPLIED_FIELDS):
        return COMPLETE
    session["field_index"] = next_idx
    return CONTINUE


def resolve_identity_key(session: object, key: object) -> str:
    """Drive the identity session. Mutates ``session``. Never raises.

    ``COMPLETE`` — all four fields committed (read ``session['values']``).
    ``CANCEL`` — Esc / non-int keycodes that are not editing keys.
    ``REFUSE`` — Enter with a blank / invalid field (stay on the field).
    ``CONTINUE`` — buffer changed or advanced to the next field.
    """
    if not isinstance(session, dict):
        return CANCEL
    if isinstance(key, bool) or not isinstance(key, int):
        return CANCEL
    if key == 27:  # Esc — abort with nothing written
        return CANCEL
    if key in _BACKSPACE_KEYS:
        buf = session.get("buf") if isinstance(session.get("buf"), str) else ""
        session["buf"] = buf[:-1]
        session["refuse_reason"] = None
        return CONTINUE
    if key in _ENTER_KEYS:
        return _commit_identity_field(session)
    if 32 <= key < 127:
        buf = session.get("buf") if isinstance(session.get("buf"), str) else ""
        session["buf"] = buf + chr(key)
        session["refuse_reason"] = None
        return CONTINUE
    # Unknown keys: ignore (stay in session) rather than cancel — a stray
    # KEY_RESIZE must not discard half-typed identity.
    return CONTINUE