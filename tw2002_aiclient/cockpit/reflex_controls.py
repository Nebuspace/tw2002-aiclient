"""Play reflex offer key + confirm label (WO-PLAY-REFLEX-ARM).

`V`/`v` asks what the taught rule library proposes for the live screen.
Raising the offer is free; launching is not. The money-path confirm gate
(`cockpit.armconfirm`) still owns `y`/`Y` only, default-deny — this module
only names WHICH key *offers* the preview and how the confirm line spells
the macro the human is about to agree to.

Hardening family (matches ``panic.py`` / ``autoloop_controls.py``): every
public function is never-raises regardless of input shape.
"""

from __future__ import annotations

REFLEX_OFFER_KEYS: tuple[int, ...] = (ord("v"), ord("V"))
REFLEX_OFFER_INTENT = "reflex_offer"

# Calm teach-band spelling (WO-PLAY-REFLEX-AFFORDANCE). Imported by
# ``teachband.TEACH_TOKENS`` so the standing chrome and the key handler
# cannot drift onto different labels — same pattern as ``panic.PANIC_TOKEN``.
REFLEX_TOKEN = "V)reflex"


def resolve_reflex_offer_key(key: object) -> bool:
    """True only for the int keycodes that offer a reflex preview."""
    if type(key) is not int:  # bool is a subclass of int — reject it
        return False
    return key in REFLEX_OFFER_KEYS


def compose_reflex_confirm_action(macro: object) -> str:
    """Confirm-line action text: ``Arm <macro>`` (``LIVE?`` added by armconfirm).

    Never invents a macro name. A non-string / empty macro becomes ``?`` so the
    gate still names *something* rather than raising a blank ``Arm  LIVE?``.
    Callers that lack a complete identity must refuse the gate before this —
    this composer is for the path that already has a proposal to show.
    """
    name = macro if isinstance(macro, str) and macro.strip() else "?"
    return f"Arm {name}"


def describe_proposal(*, macro: object, rule_id: object, classification: object) -> str:
    """Status-line preview of a fireable proposal (not an arm claim)."""
    m = macro if isinstance(macro, str) and macro else "?"
    r = rule_id if isinstance(rule_id, str) and rule_id else "?"
    c = classification if isinstance(classification, str) and classification else "?"
    return f"proposes {m} (rule {r}) · {c}"


def describe_stop(stop_reason: object) -> str:
    """Status-line for a successful STOP (ok transport, nothing to arm)."""
    reason = stop_reason if isinstance(stop_reason, str) and stop_reason else "no proposal"
    return f"reflex: nothing — {reason}"


def describe_transport_fail(reason: object) -> str:
    """Status-line for a transport / daemon refusal (ok=False)."""
    r = reason if isinstance(reason, str) and reason else "unknown"
    return f"reflex failed — {r}"
