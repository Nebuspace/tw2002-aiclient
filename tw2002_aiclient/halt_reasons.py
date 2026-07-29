"""The qualified halt-reason shape, `<code>:<detail>` — one source of truth.

A halt reason carries what produced it: `never_auto_action` becomes
`never_auto_action:money_prompt`. Two producers emit that shape
(`loops.player` and `session.sector_explore`) and both need to parse it back,
so the encoder, the decoder, and the separator live here rather than being
re-derived at each site.

**Why a root-level module and not a helper on one of the producers.** The
duplication this replaces was not an oversight; `loops/player.py` recorded the
reason it existed:

    duplicated rather than shared, because the alternative is either a new
    shared package for six lines or an import that drags the explore module
    into the loop player.

That trade-off was real — the second option makes `sector_explore` depend on
`loops.player` for three lines of string formatting, and import direction is
how modules quietly become entangled. The resolution is the first option done
cheaply: this module is **dependency-neutral by construction**. It imports
nothing from `session`, `loops`, `cockpit`, or the adapters, so either producer
may depend on it and neither is dragged toward the other.

Keep it that way. The moment this file imports a sibling it stops being a
primitive and becomes an edge in the very graph it exists to avoid.
"""

from __future__ import annotations

from typing import Optional

#: The one separator. Anything that splits or joins a qualified reason reads it
#: from here, so the two halves of the shape cannot drift apart.
QUALIFIER_SEP = ":"


def qualify(code: str, detail: str) -> str:
    """``code:detail`` -- a halt reason that carries what produced it."""
    return f"{code}{QUALIFIER_SEP}{detail}"


def halt_reason_code(reason: object) -> Optional[str]:
    """The bare CODE from a possibly-qualified ``reason``.

    ``never_auto_action:money_prompt`` -> ``never_auto_action``; an
    unqualified reason is returned unchanged; a non-string (or ``None``)
    yields ``None`` rather than a guess.

    This is the one place the qualified shape is parsed, so every consumer
    that needs "which halt code is this" asks the same question the same
    way. Splits on the FIRST separator only: a detail that itself contained
    a colon would otherwise silently truncate.
    """
    if not isinstance(reason, str) or not reason:
        return None
    return reason.split(QUALIFIER_SEP, 1)[0]
