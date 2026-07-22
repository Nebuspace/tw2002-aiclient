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

**WO-MS-4 (registration policy gate + prompt variety + name bank):**
auto-creating a character on a real server is a policy call, not a pure
mechanics one -- `char_create`'s dispatch below hard-gates on
`profile.allow_register` (default False) BEFORE sending the "Y" that
starts registration, exactly the same posture WO-MS-2 uses for `bbs`.
`_NEW_BRANCH_VARIANTS` is an extension point for modded/variant TWGS
registration prompts: MS-3's own live-probe finding (see
`audit/tw2002-multiserver/multiserver-wo-plan-2026-07-19.md`) is that
every front-end probed so far is byte-identical, so this registry ships
with a single CONSTRUCTED (never live-captured) entry proving the
mechanism end-to-end, not a set of guessed real-world variants -- an
unrecognized NEW-branch prompt still falls through to the same
stagnation/`automaton_stuck` path every unrecognized screen already uses.
`register_with_name_bank()` is the bounded-retry wrapper around
`run_login(bank_draw=True, ...)` for a profile that leaves handle/
ship_name/planet_name unset (`twclient/name_bank.py`): if a drawn handle
turns out to already belong to an existing character (the RETURNING
branch instead of the expected `char_create`), that's a collision, not a
missing-password failure, and it redraws with a fresh session rather than
guessing or reusing someone else's account.
"""

import random
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
# RETURNING re-enter interstitial observed live on game.tw2002.net: TWGS
# shows "You have been on today ..." after password, sometimes alone after
# `[Pause]` is dismissed -- it is NOT covered by the pause_key anchor (no
# `[Pause]` / "press any key" on that beat), so without this it lands in
# `unknown` and wedges ensure in automaton_stuck. Matched on the CURRENT
# prompt line (or the last non-empty line when the prompt is blank) -- NOT
# on stale scrollback above an already-active main_command prompt.
_BEEN_ON_TODAY_RE = re.compile(r"you\s+have\s+been\s+on\s+(?:the\s+game\s+)?today", re.I)

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

# -- WO-MS-4: NEW-branch prompt-coverage extension point --------------------
#
# (pattern, response) pairs checked only while `state["registering"]` is
# True (see _decide below), after every established sub-step above -- so a
# real, currently-recognized step always wins first. Every response here
# must be a purely cosmetic/non-committal (Y/N or similar) confirmation
# with NO game-state effect; this registry is never the place to encode a
# GUESS at a gameplay-affecting choice (this project has been burned by
# exactly that shape before -- DESIGN-v2's "-75 alignment" auto-defaulted
# colonist prompt). A pattern that doesn't match anything here still falls
# through to the same unrecognized-screen/`automaton_stuck` path every
# other unrecognized screen already uses -- never guessed, never sent
# blind.
#
# The one entry below is CONSTRUCTED, never captured against a real
# server (MS-3's own live-probe LOE finding is that every TWGS front-end
# probed so far is byte-identical -- no modded variant has actually been
# observed): it exists to prove the registry mechanism end-to-end (see
# tests/test_login.py's test_new_branch_variant_registry_* pair), and is
# the template for the first REAL variant once one is captured live.
_NEW_BRANCH_VARIANTS = [
    (re.compile(r"enable\s+the\s+weekly\s+news\s+digest\??", re.I), "N"),
]


class LoginError(Exception):
    """The automaton could not make progress toward the target
    classification -- either a screen it doesn't recognize repeated
    _STAGNANT_ROUNDS_LIMIT times running, the step budget ran out, or a
    RETURNING login had no saved password / exhausted retries. Always
    raised rather than guessing -- a stuck automaton must fail loudly,
    never send a keystroke it isn't sure about."""


def run_login(session, profile, get_password, save_password, target="main_command", trace=None, servers_path=None,
              bank_draw=False):
    """Drive `session` from wherever it currently is to `target`
    classification. `get_password(profile_name) -> str|None` and
    `save_password(profile_name, password)` are injected (not imported
    directly) so this stays network/credential-store-decoupled for
    tests -- the live path (protocol.py) wires them to
    twclient.credentials.get_password/save_password. `servers_path`
    overrides the server catalog location (tests only; real callers
    leave it None and get `twclient.servers.SERVERS_PATH`).

    `bank_draw` (WO-MS-4, default False -- every existing caller/test is
    unaffected): set True only when `profile.handle` was freshly drawn
    from the name bank rather than pinned by the operator (see
    `register_with_name_bank`). It changes exactly one thing: reaching
    the RETURNING branch (no `char_create` seen, i.e. the handle already
    belongs to an existing character) raises the distinct
    `bank_draw_handle_collision` LoginError instead of the generic
    `returning_no_saved_password` -- a drawn-and-collided handle is a
    "redraw and retry" signal, not the ordinary "this profile's saved
    credential is missing/stale" failure.

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
        "bank_draw": bank_draw,  # WO-MS-4
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

        # Cleared past game-select only once we've LEFT that screen after
        # sending the configured letter at least once this connection --
        # never on send-confirm alone (a false-positive idle settle can
        # confirm while the CURRENT screen is still `game_select`, which
        # would wedge ensure/automaton_stuck if latched there).
        if cls != "game_select" and getattr(session, "game_select_letter_sent", False):
            session.game_select_answered = True

        if cls == target:
            return cls, step

        action = _decide(cls, text, prompt, profile, state, get_password, save_password, session)

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
        # TWGS menu-style single-key selections (game_select's
        # `Selection (? for menu):` / `Select a game :`) must NOT get a
        # trailing CRLF -- settle.py's live phantom-blank-line hazard.
        enter = cls != "game_select"
        _reason, _elapsed, confirmed = send_and_confirm(
            session, send_text, confirm_prompt=wait_hint, enter=enter, secret=secret, timeout_s=_STEP_SETTLE_TIMEOUT_S
        )
        if cls == "game_select":
            session.game_select_letter_sent = True
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


def _decide(cls, text, prompt, profile, state, get_password, save_password, session):
    """Return (send_text, secret, wait_prompt_hint) for the current
    screen, or None if nothing in the table matches (caller treats that
    as possible-stagnation and re-polls). Order matters only where two
    rules could otherwise both look plausible; see inline notes.

    `session` is threaded through only for the game_select branch below
    -- it READS the PER-CONNECTION `game_select_answered` flag (see
    session.py), deliberately not folded into `state` (this function's
    other bookkeeping) because the vector this guards against is a
    LATER `run_login` call -- a later `ensure` against the SAME
    connection -- with its own fresh `state` dict; a per-run flag would
    never see the earlier answer at all. This function only ever READS
    the flag, never sets it: `run_login` itself latches it True, and
    only once the send is actually CONFIRMED (see its own comment) --
    latching here at decide-time, before the send is even attempted, was
    a wedge hazard (mack/cipher, adversarial review) an unconfirmed or
    outright-failed send could never recover from."""

    # -- D7 nuisances first: these can interleave with any branch. -------
    if cls == "pause_key":
        return "", False, None
    if _BEEN_ON_TODAY_RE.search(prompt):
        return "", False, None
    if cls == "unknown" and not prompt.strip():
        for line in reversed(text.splitlines()):
            stripped = line.strip()
            if not stripped:
                continue
            if _BEEN_ON_TODAY_RE.search(stripped):
                return "", False, None
            break
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
        # Safety fix: a real game-select prompt is answered exactly ONCE
        # per TCP connection -- a SECOND `game_select` classification on
        # this same connection is BY DEFINITION a misfire (most likely a
        # stale pyte buffer from earlier in the connection, classified
        # via a later ordinary screen sharing the same generic prompt),
        # not a genuine second game-select screen to answer. Refusing
        # here -- returning None, the same "nothing matched" signal any
        # other unrecognized screen produces -- routes it through the
        # SAME stagnation/`automaton_stuck` fail-loud path, never a
        # blind keystroke. `getattr(..., False)` guards test doubles
        # that predate this flag (matches this project's convention
        # elsewhere for optional session surfaces).
        #
        # Only READS `game_select_answered` -- never sets it here. That
        # flag flips True only once run_login observes a non-`game_select`
        # classification AFTER `game_select_letter_sent` (see run_login's
        # loop prologue) -- never on send-confirm alone. While the CURRENT
        # screen is still `game_select`, keep returning the configured
        # letter so a false-positive confirm or TWGS timeout re-prompt
        # can retry instead of wedging in automaton_stuck.
        if getattr(session, "game_select_answered", False):
            return None
        return profile.game_letter, False, None

    if cls == "menu" and _MODULE_ENTRY_MENU_RE.search(text):
        return "T", False, None

    if cls == "char_create":
        # WO-MS-4 hard-gate: auto-creating a character on a real server is
        # a policy call, not a pure mechanics one (same posture WO-MS-2
        # uses for `bbs`) -- refuse BEFORE the "Y" that starts
        # registration if the profile hasn't explicitly opted in. Checked
        # every time this classification is seen, not just once, so a
        # non-opted-in profile can never be talked into registering no
        # matter how it got to this screen.
        if not getattr(profile, "allow_register", False):
            raise LoginError(
                f"registration_not_permitted:profile={profile.name}:set allow_register=true to opt in"
            )
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
            if state["bank_draw"]:
                # WO-MS-4: this handle was FRESHLY DRAWN from the name
                # bank for a NEW registration, not pinned by the operator
                # -- landing in RETURNING means it collided with an
                # existing character, not that a real saved credential is
                # missing/stale. Distinct error so the caller
                # (register_with_name_bank) can tell "redraw and retry"
                # apart from a genuine returning_no_saved_password
                # failure, and so this never falls through to sending
                # whatever password.py happens to have on file for
                # `profile.name` under a DIFFERENT character's handle.
                raise LoginError(
                    f"bank_draw_handle_collision:profile={profile.name}:handle={profile.handle}"
                )

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

    # WO-MS-4: modded/variant-server NEW-branch extras. Scoped to
    # state["registering"] so this can never fire for the RETURNING
    # branch or before char_create has even been seen -- see
    # _NEW_BRANCH_VARIANTS' own module-level comment. Checked LAST, after
    # every established sub-step above, so a real recognized step always
    # takes priority; anything that matches nothing here (the common
    # case -- no live variant has been observed) falls through to the
    # same unrecognized-screen/automaton_stuck path as always.
    if state["registering"]:
        for pattern, response in _NEW_BRANCH_VARIANTS:
            if pattern.search(prompt):
                return response, False, None

    return None


def _fresh_password():
    from .credentials import generate_password

    return generate_password()


def register_with_name_bank(session_provider, profile, get_password, save_password, target="main_command",
                             name_bank_path=None, rng=None, max_attempts=5, trace=None, servers_path=None):
    """WO-MS-4 rider: drives `run_login` with a fresh (handle, ship_name,
    planet_name) drawn from the name bank (`twclient/name_bank.py`) on
    each attempt, for a `profile` that leaves those fields unset in
    `profiles.toml` (any field it DOES set explicitly always wins --
    resolve_bank_identity() never overrides it). `profile.allow_register`
    must already be True; this function doesn't set it -- it's the
    operator's opt-in, not this helper's to grant.

    `session_provider` is a zero-arg callable returning a fresh,
    already-connected, ready-to-drive session for each attempt.
    Reconnecting an in-progress TWGS session mid-flow isn't a thing --
    once the server has moved past the name prompt there's no way back to
    it short of a genuinely new connection, so a collision (see below)
    always starts over from a fresh session, never resumes the old one.

    Bounded retry: if the drawn handle already belongs to an existing
    character on this server -- `run_login(bank_draw=True)` raises
    `bank_draw_handle_collision` the moment it lands in the RETURNING
    branch instead of the expected NEW `char_create` prompt -- a new
    candidate is drawn and retried, up to `max_attempts` times, before
    failing loudly. Any OTHER LoginError (an unrelated failure -- a stuck
    automaton, an exhausted password retry, a front_end gate, an
    unrecognized NEW-branch prompt) propagates immediately, unretried.

    `rng` is an injectable `random.Random` (deterministic tests); `name_bank_path`
    overrides the bank file location (tests only). Returns whatever
    `run_login` returns on success: `(final_classification, steps_taken)`.
    """
    from . import name_bank as name_bank_mod
    from .credentials import Profile

    rng = rng or random.Random()
    last_error = None

    for _attempt in range(max_attempts):
        session = session_provider()
        handle, ship_name, planet_name = name_bank_mod.resolve_bank_identity(profile, rng=rng, path=name_bank_path)
        attempt_profile = Profile(
            name=profile.name,
            host=profile.host,
            port=profile.port,
            game_letter=profile.game_letter,
            handle=handle,
            ship_name=ship_name,
            planet_name=planet_name,
            server=profile.server,
            allow_register=getattr(profile, "allow_register", False),
        )
        try:
            return run_login(
                session, attempt_profile, get_password, save_password, target=target, trace=trace,
                servers_path=servers_path, bank_draw=True,
            )
        except LoginError as exc:
            if "bank_draw_handle_collision" not in str(exc):
                raise
            last_error = exc
            continue

    raise LoginError(f"bank_draw_exhausted_attempts:{max_attempts}:last={last_error}")
