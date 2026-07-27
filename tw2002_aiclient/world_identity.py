"""World identity -- the shared per-world keying (``world_id``) that every
durable per-world store keys its persisted state on.

``canon/engine/world-identity.md`` is the authoritative spec this module
implements: a world is **host + in-game game letter + character/handle** --
NOT just host+game -- because a fresh character registration produces a
freshly generated galaxy even on the same game letter.  Two different
characters registered on the same nominal game are two different worlds, and
their maps/threats/learned-loops must never bleed into each other.
``world_id()`` is the single anti-galaxy-bleed guarantee every per-world
store (world model, game-data store, menu map, macro library, candidate
mining) keys off of; a store keyed only by host+game risks exactly that
collision.

Deterministic, no I/O -- pure string derivation.  Safe to call from any
process (CLI, daemon, or a test) without touching disk, and safe to call
redundantly (the same inputs always produce the same slug).

**Interface pinned -- downstream consumers code directly against this exact
signature; do not change it without coordinating:**

    world_id(host: str, game_letter: str, handle: str) -> str
    world_id_from_profile(profile) -> str
"""

import re

# Filesystem-safe slug alphabet: anything outside alnum/dash/underscore
# becomes an underscore.  Deliberately NOT collapsed/stripped -- collapsing
# repeated or trailing underscores risks two distinct raw inputs sanitizing
# down to the same slug (e.g. "john" and "john!" must stay distinct as
# "john" vs "john_", not both collapse to "john").
_UNSAFE_RE = re.compile(r"[^A-Za-z0-9_-]")


class WorldIdentityError(Exception):
    """Raised for a structurally unusable identity component -- missing,
    None, or empty/whitespace-only host/game_letter/handle.  Never raised
    for a merely unusual-but-present value (stray punctuation, mixed case,
    etc.) -- those are sanitized, not rejected."""


def _sanitize(value: object, field_name: str) -> str:
    if value is None or not str(value).strip():
        raise WorldIdentityError(
            f"world_id: {field_name} must be a non-empty string, got {value!r}"
        )
    return _UNSAFE_RE.sub("_", str(value).strip())


def world_id(host: str, game_letter: str, handle: str) -> str:
    """Filesystem-safe stable slug identifying one world: one telnet host,
    one in-game game letter, one character handle.  Two different characters
    on the same host+game_letter produce two different slugs -- this is the
    anti-galaxy-bleed guarantee every per-world store keys its persisted
    state on.

    ``host`` is lowercased before sanitizing -- network hostnames are
    conventionally case-insensitive, so "Host.Example" and "host.example"
    must resolve to the SAME world.  ``game_letter`` and ``handle`` are
    sanitized as-given, case preserved -- both are exact in-game identifiers
    (not free-form user text) where case can be a real distinction, not noise
    to fold away.
    """
    if host is None or not str(host).strip():
        raise WorldIdentityError(
            f"world_id: host must be a non-empty string, got {host!r}"
        )
    h = _sanitize(str(host).lower(), "host")
    g = _sanitize(game_letter, "game_letter")
    c = _sanitize(handle, "handle")
    return f"{h}__{g}__{c}"


def world_id_from_profile(profile: object) -> str:
    """Convenience wrapper: pulls ``.host``/``.game_letter``/``.handle`` off
    a ``credentials.Profile`` (or any duck-typed object exposing the same
    three attributes) instead of making every caller unpack a Profile by
    hand."""
    return world_id(profile.host, profile.game_letter, profile.handle)
