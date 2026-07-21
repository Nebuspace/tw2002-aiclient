"""The shared menu-screen signature primitive.

A stable hash of a menu screen's identifying text. Three consumers rely on
this hash being computed identically everywhere it's used: `menu_crawler`
(the producer, persisting nodes as it discovers them), `menu_nav.localize`
(the "you are here" lookup), and the future escalation-driven map-extension
work. This lives in its own pure module -- importing ONLY `hashlib` -- so
none of those three transitively pull in `menu_crawler`'s daemon deps
(`.settle`, and through it `session`/the live connection) just to hash a
screen's text.

Trailing/leading blank lines and trailing per-line whitespace are
normalized away so cosmetically-identical renders (e.g. differing only in
trailing padding) hash identically.
"""

import hashlib


def menu_signature(full_text):
    """A stable hash of a menu screen's identifying text -- computed by
    the caller, never by game_knowledge itself (see that module's
    docstring). Trailing/leading blank lines and trailing per-line
    whitespace are normalized away so cosmetically-identical renders
    (e.g. differing only in trailing padding) hash identically."""
    normalized = "\n".join(line.rstrip() for line in full_text.strip("\n").splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
