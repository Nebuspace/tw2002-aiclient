"""Login Automaton (DESIGN-v2.md B1) + NEW-vs-RETURNING branch (B3).

A classification-driven expect/respond engine that drives the REAL TWGS
flow captured live against a real TWGS server (see this project's
`logs/session-*.log` and the classify.py anchors it added: ansi_prompt,
game_select, char_create):

  name prompt (blank -- "ENTER for none")
    -> door-select menu ("Select a game :" -> game_letter)
    -> module-entry menu ("T - Play Trade Wars 2002" -> "T")
    -> "What is your name?" -> handle
    -> "Use ANSI graphics?" -> Y
    -> "Show today's log?" -> N
    -> branch:
         NEW:      "start a new character?" -> Y
                    -> password CREATE (generate + save immediately,
                       resend identically through any "didn't match"
                       retries -- the observed live flake)
                    -> "(N)ew Name or (B)BS Name" -> B
                    -> ship name -> confirm -> planet name
                    -> "Planet command" -> Q
                    -> Command [TL=...]
         RETURNING: password CHECK (saved credential, sent once;
                    a wrong/stale saved password is a hard failure, never
                    guessed/retried past _MAX_PASSWORD_RETRIES)
                    -> Command [TL=...]

Deliberately reactive/order-independent rather than a rigid step
sequence: every iteration re-classifies the CURRENT screen and dispatches
on that, so interstitials (pause_key, inactivity warnings, a `[Pause]`
inserted at an unexpected point) never desync it. This is also what makes
`ensure` (B4) idempotent for free -- calling it against a screen already
mid-flow just resumes the unmet suffix.

**TW-02 (send/settle race):** every send this automaton makes now goes
through `settle.send_and_confirm` rather than a bare `session.send()` +
idle-only `wait_settle()` -- an autonomous login run must never treat a
screen that only transiently looked settled mid-transition as proof its
last answer landed. `confirm_prompt` is the classification's own
`wait_hint` from `_decide()` when one is meaningful (currently always
`None` here -- every login step re-classifies the CURRENT screen from
scratch on the next iteration rather than pinning to a specific next
prompt, per the reactive/order-independent design above), so in
practice every send leans on `send_and_confirm`'s idle+stability-
recheck fallback. A failed confirm does NOT abort outright (a slow
multi-part screen -- an ANSI banner, a welcome splash -- can legitimately
take a beat to finish rendering): it's folded into the SAME
`stagnant_rounds`/`last_signature` budget an unrecognized screen already
uses, so a persistently-failing confirm still raises `LoginError`
(`automaton_send_unconfirmed`) within the existing retry ceiling rather
than spinning forever, while a merely-slow one gets a few more loop
iterations to resolve on its own.

The password NEVER touches this module's return values, exceptions, or
any log call -- every send of it goes through `session.send(..., secret=True)`,
which routes to `TranscriptLogger.log_redacted()` (twclient/connection.py),
the same redaction path already proven for `tw do --secret`.

**WO-MS-2 (front_end adapter select):** the whole table above IS the
TWGS-direct flow, unchanged. Before driving it, `run_login` resolves the
profile's optional server-catalog key (`twclient/servers.py`, WO-MS-1) to
a `front_end` and gates on it: `direct`/`auto` (or no catalog key at
all -- today's only real-world shape) fall through to the existing
automaton with zero behavior change; `bbs` fails loudly before sending a
single keystroke -- BBS-menu navigation is a declined Wave-2 item, not a
silently-attempted best-effort, and the current live catalog has zero
`bbs` entries (pruned MS-3c) so this is a guard for future adds, not a
reachable path today. See `_resolve_front_end`/`_bbs_unsupported_message`.
"""

import re

from .settle import send_and_confirm

_MAX_STEPS = 60
_STEP_SETTLE_TIMEOUT_S = 12.0
_MAX_PASSWORD_RETRIES = 6
_STAGNANT_ROUNDS_LIMIT = 3

# -- D7: known nuisance interjections, matched on raw text regardless of
# classification, checked before the main per-classification dispatch so
# they can't desync any branch. All three are directly observed live
# (DESIGN-v2.md §3 v2.1 item 3 + this project's session logs).
_SHOW_LOG_RE = re.compile(r"show\s+today.?s\s+log", re.I)
_INACTIVITY_RE = re.compile(r"inactivity\s+warning|critical\s+inactivity", re.I)

# -- sub-step text matches inside the NEW-registration branch that don't
# warrant their own classify.py anchor (narrow, single-purpose, only ever
# meaningful mid-registration) -- matched directly against the rendered
# screen text.
_MODULE_ENTRY_MENU_RE = re.compile(r"T\s*-\s*Play\s+Trade\s*Wars\s*2002", re.I)
_TRADER_NAME_CHOICE_RE = re.compile(r"\(N\)ew\s+Name\s+or\s+\(B\)BS\s+Name", re.I)
_SHIP_NAME_PROMPT_RE = re.compile(r"name\s+your\s+ship", re.I)
_SHIP_CONFIRM_RE = re.compile(r"is\s+what\s+you\s+want\s*\?", re.I)
_PLANET_NAME_PROMPT_RE = re.compile(r"name\s+your\s+home\s+planet", re.I)
_PLANET_NAME_BOX_RE = re.compile(r"^\[-+\]$")
_PLANET_COMMAND_RE = re.compile(r"planet\s+command", re.I)
_OUTER_NAME_PROMPT_RE = re.compile(r"enter\s+for\s+none", re.I)


class LoginError(Exception):
    """The automaton could not make progress toward the target
    classification -- either a screen it doesn't recognize repeated
    _STAGNANT_ROUNDS_LIMIT times running, the step budget ran out, or a
    RETURNING login had no saved password / exhausted retries. Always
    raised rather than guessing -- a stuck automaton must fail loudly,
    never send a keystroke it isn't sure about."""


def run_login(session, profile, get_password, save_password, target="main_command", trace=None, servers_path=None):
    """Drive `session` from wherever it currently is to `target`
    classification. `get_password(profile_name) -> str|None` and
    `save_password(profile_name, password)` are injected (not imported
    directly) so this stays network/credential-store-decoupled for
    tests -- the live path (protocol.py) wires them to
    twclient.credentials.get_password/save_password. `servers_path`
    overrides the server catalog location (tests only; real callers
    leave it None and get `twclient.servers.SERVERS_PATH`).

    Returns (final_classification, steps_taken). Raises LoginError on
    failure to progress. Never returns without either reaching `target`
    or raising.
    """
    # WO-MS-2: front_end adapter select -- gates BEFORE anything else in
    # this function (including the pre-existing per-classification
    # dispatch below, which is the unchanged TWGS-direct flow). Raises
    # LoginError outright for `bbs` (never sends a keystroke); returns
    # silently for `direct`/`auto`/no-catalog-key, i.e. every real
    # profile in use today.
    _resolve_front_end(profile, servers_path=servers_path)

    # Local import to avoid a hard dependency loop (classify <- login is
    # the only direction that matters; protocol imports both).
    from .classify import classify_screen

    state = {
        "registering": None,  # None = undetermined yet; True/False once char_create is (or isn't) seen
        "password": None,
        "password_attempts": 0,
    }
    stagnant_rounds = 0
    last_signature = None

    for step in range(_MAX_STEPS):
        rows = session.render()
        text = session.render_text(rows)
        prompt = rows[-1].strip() if rows else ""
        cls = classify_screen(text, prompt)

        if trace is not None:
            trace.append({"step": step, "classification": cls, "prompt": prompt})

        if cls == target:
            return cls, step

        action = _decide(cls, text, prompt, profile, state, get_password, save_password)

        if action is None:
            signature = (cls, prompt)
            stagnant_rounds = stagnant_rounds + 1 if signature == last_signature else 0
            last_signature = signature
            if stagnant_rounds >= _STAGNANT_ROUNDS_LIMIT:
                raise LoginError(f"automaton_stuck:classification={cls!r}:prompt={prompt!r}")
            # Give a still-rendering multi-part screen a moment to finish
            # arriving before we re-classify.
            session.wait_settle(timeout=_STEP_SETTLE_TIMEOUT_S)
            continue

        send_text, secret, wait_hint = action
        _reason, _elapsed, confirmed = send_and_confirm(
            session, send_text, confirm_prompt=wait_hint, enter=True, secret=secret, timeout_s=_STEP_SETTLE_TIMEOUT_S
        )
        if not confirmed:
            # TW-02: the send went out, but the resulting screen was
            # never positively confirmed -- never assume it landed as
            # intended. Folded into the SAME stagnation budget an
            # unrecognized screen already uses (not a fresh reset, and
            # not an immediate abort): a genuinely transient settle-race
            # (a slow multi-part redraw) gets a few more loop iterations
            # to resolve itself via re-classification on the next pass,
            # while a persistently failing confirm still hits the
            # existing retry ceiling instead of spinning forever.
            signature = (cls, prompt, "unconfirmed")
            stagnant_rounds = stagnant_rounds + 1 if signature == last_signature else 0
            last_signature = signature
            if stagnant_rounds >= _STAGNANT_ROUNDS_LIMIT:
                raise LoginError(
                    f"automaton_send_unconfirmed:classification={cls!r}:prompt={prompt!r}:reason={_reason}"
                )
            continue

        stagnant_rounds = 0
        last_signature = None

    raise LoginError(f"automaton_exhausted_steps:{_MAX_STEPS}")


def _resolve_front_end(profile, servers_path=None):
    """WO-MS-2 seam: resolve which login table `run_login` should drive,
    from the profile's optional server-catalog key (`server`, WO-MS-1).
    A profile with no catalog key -- a bare host/port profile, today's
    only real-world shape, and every existing test double in this
    suite -- has nothing to resolve at all: `getattr(..., None)` treats
    that identically to a resolved `direct`/`auto` catalog entry, i.e.
    the pre-existing TWGS-direct automaton, unchanged.

    Returns None on success (direct/auto/no-server); raises LoginError
    for `bbs` (no BBS-navigation flow exists -- a declined Wave-2 item)
    or for any front_end value this automaton doesn't recognize. Never
    guesses: an unrecognized value fails loudly rather than silently
    falling through to `direct`."""
    server_key = getattr(profile, "server", None)
    if not server_key:
        return None

    from . import servers as servers_mod

    rec = servers_mod.get_server(server_key, path=servers_path)
    front_end = rec["front_end"]
    if front_end in ("direct", "auto"):
        return None
    if front_end == "bbs":
        raise LoginError(_bbs_unsupported_message(rec, servers_path))
    # servers.py's own catalog loader already constrains front_end to
    # {direct, bbs, auto} at load time (ServerCatalogError otherwise) --
    # this branch can't be reached via a real catalog file. Defensive
    # belt-and-braces only: never guess if a value somehow reaches here.
    raise LoginError(f"front_end_unrecognized:server={server_key}:front_end={front_end!r}")


def _bbs_unsupported_message(rec, servers_path):
    """Actionable failure text for a BBS-wrapped server: BBS-menu
    navigation isn't implemented (declined Wave-2 item), so this names
    the catalog's TWGS-direct alternative for the same hostname, if one
    is cataloged -- the current live catalog has zero `bbs` entries
    (pruned MS-3c), so this is a guard for future adds, proven here
    against a synthetic catalog."""
    from . import servers as servers_mod

    alt = next(
        (
            other
            for other in servers_mod.list_servers(path=servers_path)
            if other["key"] != rec["key"] and other["hostname"] == rec["hostname"] and other["front_end"] == "direct"
        ),
        None,
    )
    if alt is not None:
        return (
            f"front_end_bbs_unsupported:server={rec['key']}:hostname={rec['hostname']}:bbs_port={rec['port']}:"
            f"use_instead_server={alt['key']}:direct_alt_port={alt['port']}"
        )
    return (
        f"front_end_bbs_unsupported:server={rec['key']}:hostname={rec['hostname']}:bbs_port={rec['port']}:"
        f"no_cataloged_direct_alternative"
    )


def _decide(cls, text, prompt, profile, state, get_password, save_password):
    """Return (send_text, secret, wait_prompt_hint) for the current
    screen, or None if nothing in the table matches (caller treats that
    as possible-stagnation and re-polls). Order matters only where two
    rules could otherwise both look plausible; see inline notes."""

    # -- D7 nuisances first: these can interleave with any branch. -------
    if cls == "pause_key":
        return "", False, None
    if _SHOW_LOG_RE.search(text):
        return "N", False, None
    if _INACTIVITY_RE.search(text):
        # A keepalive nudge mid-automaton -- we're actively driving, so
        # this is defensive (the steady-state idle-keepalive is D10's
        # job once at main_command); harmless blank Enter resets the
        # server's idle clock without altering any pending field entry.
        return "", False, None

    # -- outer BBS-level connection name vs. the TW2002 module's own
    # character-handle prompt: both anchor to login_name, disambiguated
    # by the exact wording captured live ("... (ENTER for none)").
    if cls == "login_name":
        if _OUTER_NAME_PROMPT_RE.search(prompt):
            return "", False, None
        return profile.handle, False, None

    if cls == "ansi_prompt":
        return "Y", False, None

    if cls == "game_select":
        return profile.game_letter, False, None

    if cls == "menu" and _MODULE_ENTRY_MENU_RE.search(text):
        return "T", False, None

    if cls == "char_create":
        # This prompt only appears when the handle was NOT found in the
        # player database -- answering it is structurally always "yes,
        # create one" (DESIGN-v2 B3).
        state["registering"] = True
        return "Y", False, None

    if cls == "login_password":
        if state["registering"] is None:
            # Reached a password gate without ever seeing char_create --
            # the handle WAS found in the database. RETURNING branch.
            state["registering"] = False

        if state["registering"]:
            if state["password"] is None:
                state["password"] = get_password(profile.name) or _fresh_password()
                # Saved the moment it's chosen, before the first send --
                # maximally recoverable even if a later step fails (the
                # credential-mismatch fix: DESIGN-v2 D9). The value is fixed for
                # the whole run, so an early save is never stale.
                save_password(profile.name, state["password"])
        else:
            if state["password"] is None:
                saved = get_password(profile.name)
                if saved is None:
                    raise LoginError(
                        f"returning_no_saved_password:profile={profile.name}:handle={profile.handle}"
                    )
                state["password"] = saved

        state["password_attempts"] += 1
        if state["password_attempts"] > _MAX_PASSWORD_RETRIES:
            raise LoginError(f"password_retries_exhausted:profile={profile.name}")
        return state["password"], True, None

    # These sub-step matches were originally against the whole screen
    # `text` and hit the exact stale-scrollback trap classify.py's own
    # module docstring warns about: pyte doesn't clear cells the server
    # never overwrites, so "Use (N)ew Name or (B)BS Name" and "What do
    # you want to name your ship?" both linger on-screen well after
    # being answered. Caught live (this build's own cold-register
    # proof): a leftover "(B)BS Name" match kept re-firing "B" as the
    # SHIP name, and a leftover "name your ship" match re-fired the ship
    # name at the CONFIRM prompt, which the server took as "No" and
    # looped forever. Fixed the same way classify.py's gate anchors are:
    # match only the CURRENT prompt line, since the real captured trace
    # confirms each of these IS the exact bottom line at send-time.
    if _TRADER_NAME_CHOICE_RE.search(prompt):
        return "B", False, None

    if _SHIP_NAME_PROMPT_RE.search(prompt):
        return profile.ship_name, False, None

    if _SHIP_CONFIRM_RE.search(prompt):
        return "Y", False, None

    # The planet-name prompt is the one sub-step whose current bottom
    # line is a generic input-box marker ("[---...---]"), not text
    # containing "planet" -- so it's matched with a compound condition
    # instead: the box-marker SHAPE as the current prompt, plus the
    # "name your home planet" wording anywhere in the full screen (this
    # marker/wording pairing is unique to this one step, so it can't
    # re-fire on later unrelated stale content the way a bare full-text
    # scan could).
    if _PLANET_NAME_BOX_RE.search(prompt) and _PLANET_NAME_PROMPT_RE.search(text):
        return profile.planet_name, False, None

    if _PLANET_COMMAND_RE.search(prompt):
        return "Q", False, None

    return None


def _fresh_password():
    from .credentials import generate_password

    return generate_password()
