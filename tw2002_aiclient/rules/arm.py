"""The operator-facing arm flow: preview a proposal, ask, launch nothing else.

WO-REFLEX-ARMED-RUN. `tw reflex` proposes; `tw reflex --arm` is the one place
that proposal can become a run, and it becomes one only through a human typing
`y` at a prompt this module raised.

Why this is a module and not a branch in ``session/cli.py``
-----------------------------------------------------------
The same reason ``rules/cli.py`` exists (WO-RULE-WRITER-DRAFTS): that file is
already over the line cap with #218 frozen, and the interesting part here --
what counts as a confirmation -- deserves to be callable by a test without a
daemon, a socket, or an argparse namespace.

**This module cannot send.** It holds no socket, imports no transport, and
takes the launch as a callable from its caller. The "no direct send in reflex
launch code" requirement is therefore a property of the file rather than a
promise about it: there is nothing here to send *with*. A test pins that no
transport name appears in its imports, so the property has to be deleted
deliberately rather than eroded.

The keycode adapter, and the silent failure it exists to prevent
----------------------------------------------------------------
``cockpit.armconfirm.resolve_arm_confirm_key`` is the ratified default-deny
policy and stays the sole authority on *which* keys arm -- this module
deliberately contains no ``y``/``Y`` literal, so there is no second list to
drift out of step with the first.

But that policy is a **curses** gate: it takes an int keycode. A CLI reads a
line of text, and measured directly::

    resolve_arm_confirm_key(ord("y")) -> confirm
    resolve_arm_confirm_key("y")      -> cancel

So handing the typed string straight to the policy -- the obvious wiring, and
one that reads as compliance to any reviewer asking "does it use the approved
gate?" -- builds a flow that can *never* arm. It would satisfy every
zero-launch requirement in the WO and fail only the one that says `y` works.
A bug that fails safe is still a bug, and this one is camouflaged.

:func:`resolve_typed_confirm` is the adapter: a typed answer of length exactly
one is converted with ``ord()`` and handed to the policy; everything else --
``""``, ``"yes"``, a pasted word, a non-string -- is cancelled here without
consulting it. ``"yes"`` cancelling is the WO's "only literal `y`/`Y`", not an
oversight: a flow that accepts ``yes`` has started guessing at intent on the
money path.

Exit codes
----------
``0`` when the system gave a settled answer -- nothing to arm, the human
declined, the daemon refused on drift or on a runner rail. ``1`` when the
command could not proceed at all -- transport failure, a stdin that cannot
carry a confirmation, an identity too incomplete to confirm. The split is "did
you get an answer", not "did it arm", so a STOP stays a success exactly as
``cmd_reflex`` documents.
"""

from __future__ import annotations

import sys
from typing import Any, Callable, Mapping, Optional

from ..cockpit.armconfirm import (
    CANCEL,
    CONFIRM,
    compose_arm_confirm_line,
    resolve_arm_confirm_key,
)

__all__ = [
    "IDENTITY_INCOMPLETE",
    "NON_INTERACTIVE",
    "compose_identity_line",
    "resolve_typed_confirm",
    "run_arm_flow",
]

#: Printed when stdin cannot carry a deliberate keystroke.
#:
#: A pipe is refused rather than read. ``echo y | tw reflex --arm`` is a
#: ``--yes`` flag wearing a different syntax, and the WO forbids the flag; that
#: the bypass arrives through stdin instead of argv does not make it a
#: different thing. The WO's "non-interactive unavailable input sends zero" is
#: this line.
NON_INTERACTIVE = "not armed — stdin is not a terminal; arming needs a typed key"

#: Printed when a proposal arrived without a usable identity.
#:
#: Not a theoretical case worth skipping: a confirmation has to be *of*
#: something, and asking "arm this?" about a proposal we cannot name would
#: collect a real `y` for an unidentifiable act. Refusing costs an operator one
#: retry; the alternative spends turns on a run nobody specified.
IDENTITY_INCOMPLETE = "not armed — the proposal has no complete identity to confirm"


def _text(value: object) -> Optional[str]:
    """The value as a non-empty string, else ``None``."""
    return value if isinstance(value, str) and value else None


def _isatty(stream: object) -> bool:
    """Whether *stream* is a terminal, answering ``False`` when it cannot say.

    Fails closed on purpose. ``AttributeError`` covers a stream with no
    ``isatty`` (a test double, a plain object), ``ValueError`` a closed file,
    ``OSError`` a stream whose fd cannot be queried. Any of those means we
    could not establish that a human is present, and "could not establish" and
    "no" have to arrive at the same place on this path.
    """
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


def resolve_typed_confirm(answer: object) -> str:
    """``CONFIRM`` only for a typed answer the policy accepts; else ``CANCEL``.

    Surrounding whitespace is stripped -- a trailing newline always arrives
    from ``readline`` and a leading space is a typo, not an intent. What is
    *not* tolerated is length: after stripping, anything other than a single
    character cancels without reaching the policy, so ``yes``, ``y y`` and an
    empty line are all inert.

    The policy itself decides which single characters confirm. This function
    names none, which is why there is no second key list here to fall out of
    step with ``armconfirm``'s. Never raises.
    """
    if not isinstance(answer, str):
        return CANCEL
    text = answer.strip()
    if len(text) != 1:
        return CANCEL
    return resolve_arm_confirm_key(ord(text))


def compose_identity_line(rule_id: str, classification: str) -> str:
    """The context line above the confirm prompt: which rule, which screen.

    Canon's dialog names *what runs*; this names *why it was chosen*. The
    human is being asked to accept a selection, and a macro name alone does
    not show whether it was picked by the rule they taught or by a different
    one that happens to target the same screen.
    """
    return f"rule {rule_id} · screen {classification}"


def run_arm_flow(
    block: Optional[Mapping[str, Any]],
    classification: object,
    *,
    launch: Callable[[dict], Mapping[str, Any]],
    stream_in: object = None,
    stream_out: object = None,
) -> int:
    """Preview, ask, and on a literal confirmation call *launch* exactly once.

    *block* is the ``reflex`` response's proposal block and *classification*
    its screen class -- the identity the human is about to be shown. *launch*
    receives that identity verbatim and performs the request; this module never
    learns how.

    There is deliberately **no parameter that can answer the prompt**. No
    ``yes``, no ``assume``, no ``force``, no bool of any name: the only input
    that reaches :func:`resolve_typed_confirm` is what was read from
    *stream_in* after the prompt was written. ``stream_in``/``stream_out``
    exist so a test can drive the flow without owning the process's stdio, and
    a test pins that the signature carries no boolean at all -- a caller
    wanting to bypass the human would have to add one, visibly.
    """
    out = stream_out if stream_out is not None else sys.stdout
    inp = stream_in if stream_in is not None else sys.stdin

    proposal = block if isinstance(block, Mapping) else {}
    macro = _text(proposal.get("macro"))
    if macro is None:
        reason = _text(proposal.get("stop_reason")) or "no proposal"
        print(f"not armed — nothing to arm ({reason})", file=out)
        return 0

    rule_id = _text(proposal.get("rule_id"))
    klass = _text(classification)
    if rule_id is None or klass is None:
        print(IDENTITY_INCOMPLETE, file=out)
        return 1

    if not _isatty(inp):
        print(NON_INTERACTIVE, file=out)
        return 1

    print(compose_identity_line(rule_id, klass), file=out)
    # The prompt shares a line with the answer, so it is written rather than
    # printed and flushed explicitly -- an unflushed money-path prompt is a
    # cursor sitting under no question at all.
    out.write(compose_arm_confirm_line(f"Arm {macro}") + " ")
    out.flush()

    try:
        answer = inp.readline()
    except (EOFError, OSError):
        answer = ""
    if not answer:
        # `readline` gives "" only at end of input. Ctrl-D at the prompt lands
        # here, and lands on cancel, like every other non-`y`.
        print("not armed — cancelled (end of input)", file=out)
        return 0
    if resolve_typed_confirm(answer) != CONFIRM:
        print("not armed — cancelled", file=out)
        return 0

    # The identity that was on the glass when the human said yes. The daemon
    # re-derives the proposal and refuses unless all three still match, so this
    # is a claim to be checked, never an instruction to be obeyed.
    resp = launch({"rule_id": rule_id, "macro": macro, "classification": klass})
    resp = resp if isinstance(resp, Mapping) else {}
    if not resp.get("ok"):
        error = _text(resp.get("error")) or "unknown_error"
        print(f"not armed — {error}", file=out)
        # A named refusal is an answer. Only the transport failing is not, and
        # that is `cmd_reflex`'s to report; by here the daemon has spoken.
        return 0
    print(f"armed — running {macro} (rule {rule_id})", file=out)
    return 0
