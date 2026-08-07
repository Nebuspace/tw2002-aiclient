"""Login Automaton (canon: `canon/architecture/login-automaton.md`).

A classification-driven expect/respond engine that drives a cold (or
mid-flow) TWGS-direct socket to the in-game `Command [TL=...]` prompt:

  name prompt (blank -- "ENTER for none"; if THIS particular host
             explicitly rejects the blank, one bounded retry with the
             profile's own handle instead -- WO-MICRO-LOGIN-BLANK-REJECT,
             see `_OUTER_NAME_REJECTED_RE`)
    -> door-select menu ("Select a game :" -> game_letter)
    -> module-entry menu ("T - Play Trade Wars 2002" -> "T")
    -> "What is your name?" -> handle
    -> "Use ANSI graphics?" -> Y
    -> "Show today's log?" -> N
    -> branch:
         NEW:      "start a new character?" -> Y
                    -> password CREATE (generate + save immediately,
                       resend identically through any "didn't match"
                       retries)
                    -> "(N)ew Name or (B)BS Name" -> B
                    -> ship name -> confirm -> planet name
                    -> "Planet command" -> Q
                    -> Command [TL=...]
         RETURNING: password CHECK (saved credential, sent EXACTLY ONCE;
                    a wrong/stale/missing saved password is a hard,
                    immediate failure -- the login_password gate
                    reappearing after that one send is treated as a
                    rejection and never re-sent, canon:
                    login-automaton.md's fail-fast/lockout-safe ceiling.
                    `_MAX_PASSWORD_RETRIES` only governs the NEW branch's
                    "didn't match" re-TYPE retries below, which are
                    legitimate confirm-round bounces, not rejections of
                    an already-known-bad value)
                    -> Command [TL=...]

Ported from `archive/pre-rebirth-2026-07-23/code/twclient/login.py`
(WO-P2-020, Wave-3) -- reactive/order-independent by design: every
iteration re-classifies the CURRENT screen and dispatches on that, so
interstitials (pause_key, inactivity warnings, "been on today", "clear
some avoids?") never desync it. This is also what makes `ensure`
idempotent for free -- calling it against a screen already mid-flow just
resumes the unmet suffix.

**WO-P2-020 Wave-3 CUTS vs the archive module** (see this module's own
inline comments for the exact archive line refs):
  - `_resolve_front_end` / the server-catalog `front_end` (direct/bbs/auto)
    gate (archive login.py:199-205, 288-346) -- depends on `servers.py`,
    not ported. Every profile is driven as a direct TWGS connection; a
    later WO can reintroduce the gate once a front-end catalog exists.
  - `register_with_name_bank` + the `bank_draw` handle-collision branch
    (archive login.py:456-469, 550-611) -- depends on `name_bank.py`, not
    ported. A profile must set its own `handle` (or opt into
    `allow_register` with a handle it's fine reusing every run); no
    drawn-identity retry loop exists yet.
  - `credentials.generate_password` (archive credentials.py:281-284) --
    the ported `credentials.py` (WO-P0-005/WO-P1-012) only landed
    read-side `get_password`. `_fresh_password()` below is a small local
    mirror of the same CSPRNG/alnum/8-char shape until a follow-on WO
    promotes it into `credentials.py` proper.

The password NEVER touches this module's return values, exceptions, or
any log call -- every send of it goes through `settle.send_and_confirm`'s
underlying `session.send(..., secret=True)`, which routes to the
transcript logger's redacted write (see
`canon/doctrine/secrets-and-credentials.md`).

That claim about EXCEPTIONS used to be false against one specific server
behavior, and is now true structurally rather than by luck: two raise
sites quoted the observed prompt line verbatim, and on a server that
echoes a password prompt that line IS the credential (measured end to
end into the CLI's JSON -- `tests/test_ensure_login_error_redaction.py`).
Both now raise `LoginStalled`, which cannot carry screen text at all; see
that class for the full account. No raise site in this module interpolates
anything the server painted -- only closed-vocabulary classifications,
config-sourced profile fields, and integers.

The ONE place this module still copies observed text is the opt-in
`trace` list a caller may hand `run_login` (each entry records the
verbatim prompt). Nothing on the product path passes one today; a caller
that starts to must treat it as screen-grade data, not as a safe
diagnostic string.
"""

import re

from .classify import classify_screen
from .settle import send_and_confirm

_MAX_STEPS = 60
_STEP_SETTLE_TIMEOUT_S = 12.0
_MAX_PASSWORD_RETRIES = 6
# WO-FIX-LOGIN-ALIAS-PROMPT-UNHANDLED: bounded Alias retries (same spirit as
# password retries) — never an unbounded name hunt.
_MAX_ALIAS_RETRIES = 6
_ALIAS_SUFFIX_LEN = 3
_ALIAS_MAX_LEN = 20
_STAGNANT_ROUNDS_LIMIT = 3
# Path-specific grace for the RETURNING login_password reappearance only
# (Mack HIGH follow-up) -- covers a realistic multi-hundred-ms-to-a-couple-
# seconds slow/two-stage post-password transition (the regression test's
# 0.6s resolves in round 1) while keeping total rejection detection
# (this × _STAGNANT_ROUNDS_LIMIT ~= 7.5s) well inside `ensure_session`'s
# 20s budget, so a genuine `returning_password_rejected` actually reaches
# the caller instead of being pre-empted by that outer generic timeout.
# Every OTHER stagnation path (unrecognized screens) keeps the longer
# generic `_STEP_SETTLE_TIMEOUT_S` grace -- only this one narrow situation
# is known to always resolve fast (a real screen change) or never (a
# settled rejection), so it's the one safe to shorten.
_RETURNING_REJECT_SETTLE_S = 2.5

# -- known nuisance interjections, matched on raw text regardless of
# classification, checked before the main per-classification dispatch so
# they can't desync any branch.
_SHOW_LOG_RE = re.compile(r"show\s+today.?s\s+log", re.I)
_INACTIVITY_RE = re.compile(r"inactivity\s+warning|critical\s+inactivity", re.I)
# Live a-net Star Wars (letter C): after MODULE_ENTRY ``T`` the host prints
# this closed-game refusal then returns the player to TWGS game_select
# (hub capture anet-postpause-194645Z). Fail loud — never loop door↔Play.
_CLOSED_GAME_RE = re.compile(
    r"this\s+is\s+a\s+closed\s+game|request\s+a\s+player\s+account\s+from\s+the\s+game\s+administrator",
    re.I,
)
# RETURNING re-enter interstitial: TWGS shows "You have been on today ..."
# after password, sometimes alone after `[Pause]` is dismissed -- not
# covered by the pause_key anchor, so without this it lands in `unknown`
# and wedges the automaton in automaton_stuck. Matched on the CURRENT
# prompt line (or the last non-empty line when the prompt is blank) --
# NOT on stale scrollback above an already-active main_command prompt.
_BEEN_ON_TODAY_RE = re.compile(r"you\s+have\s+been\s+on\s+(?:the\s+game\s+)?today", re.I)
# After re-enter, TWGS may ask whether to clear the avoid list. Optional
# Y/N -- default N (keep avoids; clearing would wipe trader navigation
# memory). Override via profile `clear_avoids_on_login = true`.
_CLEAR_AVOIDS_RE = re.compile(
    r"do\s+you\s+wish\s+to\s+clear\s+some\s+avoids\s*\?\s*\(\s*Y\s*/\s*N\s*\)",
    re.I,
)

# -- sub-step text matches inside the NEW-registration branch that don't
# warrant their own classify.py anchor (narrow, single-purpose, only ever
# meaningful mid-registration) -- matched against the CURRENT prompt line
# only (never the whole screen -- pyte doesn't clear cells the server
# never overwrites, so an earlier sub-step's own prompt text lingers
# on-screen well after being answered; a whole-text match would re-fire
# on that stale scrollback).
_MODULE_ENTRY_MENU_RE = re.compile(r"T\s*-\s*Play\s+Trade\s*Wars\s*2002", re.I)
_ENTER_YOUR_CHOICE_RE = re.compile(r"enter\s+your\s+choice\s*:", re.I)


def _option_block_above_prompt(text: str, prompt: str) -> str:
    """Lines of the CURRENT option list attached to ``prompt`` (or the last
    ``Enter your choice:`` in ``text``).

    Walks upward from that prompt line and stops at the first blank once any
    option line has been collected — so stale scrollback above a blank
    separator is excluded. Same structural discipline as classify's
    ``_range_has_no_dash_style_menu`` (mirror direction); no magic line count.
    """
    lines = (text or "").splitlines()
    if not lines:
        return ""
    prompt_key = (prompt or "").strip().lower()
    idx = None
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip().lower()
        if prompt_key and prompt_key in stripped:
            idx = i
            break
        if _ENTER_YOUR_CHOICE_RE.search(lines[i]):
            idx = i
            break
    if idx is None:
        return ""
    collected: list[str] = []
    for i in range(idx - 1, -1, -1):
        if not lines[i].strip():
            if collected:
                break
            continue
        collected.append(lines[i])
    collected.reverse()
    return "\n".join(collected)


def _is_module_entry_menu(text: str, prompt: str) -> bool:
    """True only when the CURRENT menu offers ``T - Play Trade Wars 2002``.

    Whole-screen search is unsafe: pyte leaves prior doors' text in the
    grid. Scope to the option block above the current prompt so a stale
    ``T - Play`` above a blank separator cannot vouch for a later menu.
    Live a-net module-entry lists T/I/S *and* H/M/X in the SAME block —
    that must still return True (hub 194056Z capture).
    """
    window = _option_block_above_prompt(text, prompt)
    return bool(window and _MODULE_ENTRY_MENU_RE.search(window))


_TRADER_NAME_CHOICE_RE = re.compile(r"\(N\)ew\s+Name\s+or\s+\(B\)BS\s+Name", re.I)
_SHIP_NAME_PROMPT_RE = re.compile(r"name\s+your\s+ship", re.I)
_SHIP_CONFIRM_RE = re.compile(r"is\s+what\s+you\s+want\s*\?", re.I)
_PLANET_NAME_PROMPT_RE = re.compile(r"name\s+your\s+home\s+planet", re.I)
_PLANET_NAME_BOX_RE = re.compile(r"^\[-+\]$")
_PLANET_COMMAND_RE = re.compile(r"planet\s+command", re.I)
_OUTER_NAME_PROMPT_RE = re.compile(r"enter\s+for\s+none", re.I)
# WO-MICRO-LOGIN-BLANK-REJECT: some hosts advertise "(ENTER for none)" and
# then explicitly refuse the blank the canon-correct send supplies --
# captured live against twgs.microblaster.net (see
# audit/micro-unknown-step6-corpus-20260726.md). Matched against the WHOLE
# screen (not just the current prompt line), the same discipline as
# `_SHOW_LOG_RE` above: the rejection text sits a line or more ABOVE the
# re-printed prompt by the time it's next classified, never on the current
# prompt line itself.
_OUTER_NAME_REJECTED_RE = re.compile(r"login\s+name\s+is\s+required", re.I)

# Classes that mean we have TRULY left the server game door after sending
# ``profile.game_letter``. A mid-paint flash to ``unknown`` / generic
# ``menu`` must NOT latch ``game_select_answered`` -- that is the wedge
# behind live a-net ``automaton_stuck:classification='game_select':step=12``
# after the chrome-footer classify fix (WO-ANET-GAME-SELECT-LETTER-STEP12):
# letter sends, a transitional frame briefly leaves ``game_select``, the
# latch fires, the door reappears, and ``_decide`` refuses to re-send.
_POST_GAME_SELECT_PROGRESS = frozenset(
    {
        "login_name",
        "login_alias",
        "login_password",
        "ansi_prompt",
        "char_create",
        "pause_key",
        "main_command",
        "money_prompt",
    }
)


def _left_game_select_for_real(cls, text, prompt=""):
    """True when ``cls`` is genuine post-door progress, not a paint flash.

    ``prompt`` is the CURRENT bottom-row prompt, forwarded to
    ``_is_module_entry_menu`` so its ``_option_block_above_prompt`` anchor
    can scope the option list correctly (same discipline as ``_decide``'s
    menu branch).
    """
    if cls in _POST_GAME_SELECT_PROGRESS:
        return True
    if cls == "menu" and _is_module_entry_menu(text or "", prompt or ""):
        return True
    return False


# -- NEW-branch prompt-coverage extension point -----------------------------
#
# (pattern, response) pairs checked only while `state["registering"]` is
# True, after every established sub-step above -- so a real, currently
# recognized step always wins first. Every response here must be a purely
# cosmetic/non-committal (Y/N or similar) confirmation with NO game-state
# effect -- never a GUESS at a gameplay-affecting choice. A pattern that
# doesn't match anything here still falls through to the same
# unrecognized-screen/`automaton_stuck` path every other unrecognized
# screen already uses -- never guessed, never sent blind.
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


class LoginStalled(LoginError):
    """The automaton stopped making progress: either a screen it does not
    recognize repeated `_STAGNANT_ROUNDS_LIMIT` times running, or a send
    whose resulting screen was never positively confirmed that many times
    running. Carries WHY and WHERE -- never WHAT WAS ON THE SCREEN.

    **Why a type instead of an f-string.** Both raise sites used to quote
    the observed prompt line verbatim
    (`f"automaton_stuck:classification={cls!r}:prompt={prompt!r}"`), and
    `protocol._dispatch_ensure` folds whatever escapes here into
    `resp["error"]` -- printed by BOTH `cli.print_response` branches and
    stored by `guardian._maybe_reconnect` in `last_reconnect_error`. On a
    server that ECHOES at a password prompt -- precisely the behavior
    canon's RX-side no-leak guarantee openly rests on never happening
    (`canon/doctrine/secrets-and-credentials.md`, Code Divergence #1) --
    that prompt line IS the operator's credential. So the app made a fresh
    COPY of the secret into a diagnostic string that nothing required, and
    handed it to every downstream renderer. Driven end to end through the
    real daemon socket and the real CLI, not reasoned about:
    `tests/test_ensure_login_error_redaction.py`.

    Closed at the SOURCE, the way `credentials.SecretStoreUnreadable` and
    `env.DotenvUnreadable` were: an error INCAPABLE of carrying the payload
    makes every existing and future renderer safe by construction --
    `str`, `repr`, `args`, the traceback, the wire frame, the guardian
    field -- where sanitising each renderer is whack-a-mole against a
    growing set of callers, and a scrub of the raised text could never be
    sound anyway (a wrapped or partially-echoed credential, a SIBLING
    profile's secret painted earlier in the session, or a secret typed by
    hand into an attach are all screen content this module never held a
    copy of to match against).

    Everything it does carry is bounded by construction:
      `code`           one of this module's own two literals
      `classification` `classify.classify_screen`'s CLOSED vocabulary --
                       anything it cannot name is `unknown`, never a slice
                       of the screen
      `step`           the automaton's own loop counter
      `settle_reason`  `settle.wait_for_settle`'s own token
                       (`prompt`/`idle`/`timeout`)

    Deliberately NO length, shape, or character-class summary of the
    prompt: doctrine invariant 2 counts a length as a leak in its own
    right, and any such digest would be a partial disclosure of exactly
    the bytes this type exists to keep out.

    A subclass of `LoginError` rather than a sibling, because every caller
    that already catches `LoginError` (`protocol._dispatch_ensure`,
    `guardian._maybe_reconnect`, `daemon.py`'s widest catch) must keep
    catching these unchanged -- this narrows what the error CARRIES, not
    what it MEANS. The `code:key=value:` message shape is preserved so the
    substring-matching consumers keep working.
    """

    def __init__(self, code, classification, step, settle_reason=None):
        self.code = code
        self.classification = classification
        self.step = step
        self.settle_reason = settle_reason
        detail = f"{code}:classification={classification!r}:step={step}"
        if settle_reason is not None:
            detail = f"{detail}:reason={settle_reason}"
        super().__init__(detail)


class LoginProfile:
    """Bounded profile shape `run_login()` needs to drive one login
    (WO-P2-020 Wave-3 CUT vs archive credentials.py:90-143's `Profile`):
    no server-catalog `server` key, `crawl_sacrificial`, or
    `autonomous`/`autopilot` fields -- those belong to surfaces
    (`servers.py`'s multi-front-end resolution, `autopilot.py`) that
    haven't landed yet. `protocol.py`'s `ensure` handler builds one of
    these straight from `config/profiles.toml`."""

    def __init__(self, name, handle, game_letter, allow_register=False,
                 ship_name=None, planet_name=None, clear_avoids_on_login=False):
        self.name = name
        self.handle = handle
        self.game_letter = game_letter
        self.allow_register = bool(allow_register)
        self.ship_name = ship_name or (f"{handle}Ship" if handle else None)
        self.planet_name = planet_name or (f"{handle}World" if handle else None)
        self.clear_avoids_on_login = bool(clear_avoids_on_login)


def run_login(
    session,
    profile,
    get_password,
    save_password,
    target="main_command",
    trace=None,
    save_alias=None,
):
    """Drive `session` from wherever it currently is to `target`
    classification. `get_password(profile_name) -> str|None` and
    `save_password(profile_name, password)` are injected (not imported
    directly) so this stays network/credential-store-decoupled for tests
    -- the live path (`protocol.py`) wires them to
    `credentials.get_password` / a local secrets-file writer (see that
    module's `_save_password`).

    Optional ``save_alias(profile_name, alias)`` records the in-game Alias
    when a TWGS dialect rejects ``profile.handle`` (WO-FIX-LOGIN-ALIAS-
    PROMPT-UNHANDLED). Alias is not a secret; the live saver merges it into
    the secrets entry as ``in_game_alias`` so it stays discoverable next to
    the password without inventing a third store.

    Returns `(final_classification, steps_taken)`. Raises `LoginError` on
    failure to progress. Never returns without either reaching `target`
    or raising."""
    state = {
        "registering": None,  # None = undetermined yet; True/False once char_create is (or isn't) seen
        "password": None,
        "password_attempts": 0,
        # WO-MICRO-LOGIN-BLANK-REJECT: has the bounded outer-name-gate
        # retry (blank, then ONE retry with the profile's handle) already
        # spent its one retry this run? See `_decide()`'s `login_name`
        # branch.
        "outer_name_handle_tried": False,
        # WO-FIX-LOGIN-ALIAS-PROMPT-UNHANDLED
        "alias": None,
        "alias_attempts": 0,
        "save_alias": save_alias,
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

        # Door re-entry: if game_select is PERSISTENTLY classified while
        # ``game_select_answered`` is True (stagnant_rounds >= 1 at the top
        # of this iteration), the host has genuinely returned to the door
        # after the automaton had already left it -- clear both flags so the
        # configured letter can re-send.
        #
        # Requires stagnant_rounds >= 1 (not 0): a single transient stale
        # redraw (``restale_game_select`` test shape) reaches this check with
        # stagnant_rounds == 0 (the preceding send reset it to 0) and then
        # has its settle wait interrupted by the next real screen arriving,
        # so it NEVER accumulates a second consecutive None-return for the
        # same signature.  Stagnant_rounds == 0 is the exclusion gap that
        # keeps the stale-redraw test green while still recovering a genuine
        # persistent re-entry on the second stagnant iteration.
        if (
            cls == "game_select"
            and getattr(session, "game_select_answered", False)
            and stagnant_rounds >= 1
        ):
            session.game_select_answered = False
            session.game_select_letter_sent = False

        # Cleared past game-select only once we've LEFT that screen for a
        # known post-door class after sending the configured letter --
        # never on send-confirm alone, and never on a mid-paint flash to
        # ``unknown`` / generic ``menu`` (WO-ANET-GAME-SELECT-LETTER-STEP12).
        if (
            getattr(session, "game_select_letter_sent", False)
            and _left_game_select_for_real(cls, text, prompt)
        ):
            session.game_select_answered = True

        if cls == target:
            return cls, step

        action = _decide(
            cls, text, prompt, profile, state, get_password, save_password, session
        )

        if action is None:
            signature = (cls, prompt)
            stagnant_rounds = stagnant_rounds + 1 if signature == last_signature else 0
            last_signature = signature
            # RETURNING password gate reappearing (see _decide()'s own
            # comment at this exact condition) is the one stagnation shape
            # known to always resolve either FAST (a genuine slow/two-stage
            # transition finishing) or NEVER (a settled rejection) -- so it
            # gets the shorter, path-specific grace instead of the generic
            # unrecognized-screen budget, keeping total detection time well
            # inside `ensure_session`'s 20s caller budget (see
            # `_RETURNING_REJECT_SETTLE_S`'s own module-level comment).
            returning_reject = (
                cls == "login_password" and state["registering"] is False and state["password"] is not None
            )
            if stagnant_rounds >= _STAGNANT_ROUNDS_LIMIT:
                if returning_reject:
                    # Specific error over the generic one below so callers
                    # can distinguish "wrong saved credential" from any
                    # other stuck screen.
                    raise LoginError(f"returning_password_rejected:profile={profile.name}")
                # The unrecognized screen itself is NOT quoted here -- see
                # `LoginStalled`. Every renderer that has no screen beside
                # it (the guardian field, a log line, a persisted status
                # file) stops being a credential sink.
                #
                # This comment used to add "the operator still has it: the
                # same `ensure` failure response carries `prompt`, `screen`
                # and `classification` from `build_response`". Two thirds of
                # that is no longer true and the change was deliberate: canon
                # `DECISIONS.md` C.2 ruled the screen mirror out of
                # structured ensure diagnostics, so
                # `protocol._login_failure_response` now returns
                # `classification` (this same closed vocabulary) WITHOUT
                # `screen` or `prompt`. The operator's screen is still the
                # operator's -- via a live attach, the `screen` verb, or a
                # `subscribe` feed -- it just no longer rides the failure
                # payload.
                raise LoginStalled("automaton_stuck", cls, step)
            # Give a still-rendering multi-part screen a moment to finish
            # arriving before we re-classify.
            session.wait_settle(
                timeout=_RETURNING_REJECT_SETTLE_S if returning_reject else _STEP_SETTLE_TIMEOUT_S
            )
            continue

        send_text, secret, wait_hint = action
        # TWGS menu-style single-key selections (game_select's "Select a
        # game :") must NOT get a trailing CRLF -- settle.py's live
        # phantom-blank-line hazard.
        enter = cls != "game_select"
        _reason, _elapsed, confirmed = send_and_confirm(
            session, send_text, confirm_prompt=wait_hint, enter=enter, secret=secret, timeout_s=_STEP_SETTLE_TIMEOUT_S
        )
        if cls == "game_select":
            session.game_select_letter_sent = True
        if not confirmed:
            # The send went out, but the resulting screen was never
            # positively confirmed -- never assume it landed as intended.
            # Folded into the SAME stagnation budget an unrecognized
            # screen already uses: a genuinely transient settle-race (a
            # slow multi-part redraw) gets a few more loop iterations to
            # resolve itself via re-classification on the next pass,
            # while a persistently failing confirm still hits the
            # existing retry ceiling instead of spinning forever.
            signature = (cls, prompt, "unconfirmed")
            stagnant_rounds = stagnant_rounds + 1 if signature == last_signature else 0
            last_signature = signature
            if stagnant_rounds >= _STAGNANT_ROUNDS_LIMIT:
                # Same carrier as `automaton_stuck` above, and strictly
                # worse: this branch is reached on the NEW-registration
                # path AFTER the credential has been sent, so the echoing
                # server's copy of it is the likeliest thing on the prompt
                # line. `_reason` is settle.py's own closed token and stays.
                raise LoginStalled(
                    "automaton_send_unconfirmed", cls, step, settle_reason=_reason
                )
            continue

        stagnant_rounds = 0
        last_signature = None

    raise LoginError(f"automaton_exhausted_steps:{_MAX_STEPS}")


def _decide(cls, text, prompt, profile, state, get_password, save_password, session):
    """Return `(send_text, secret, wait_prompt_hint)` for the current
    screen, or `None` if nothing in the table matches (caller treats that
    as possible-stagnation and re-polls). Order matters only where two
    rules could otherwise both look plausible; see inline notes.

    `session` is threaded through only for the game_select branch below
    -- it READS the PER-CONNECTION `game_select_answered` flag (see
    session.py), deliberately not folded into `state` (this function's
    other bookkeeping) because the vector this guards against is a LATER
    `run_login` call -- a later `ensure` against the SAME connection --
    with its own fresh `state` dict; a per-run flag would never see the
    earlier answer at all. This function only ever READS the flag, never
    sets it: `run_login` itself latches it True, and only once the send
    is actually CONFIRMED -- latching at decide-time, before the send is
    even attempted, would be a wedge hazard an unconfirmed or
    outright-failed send could never recover from."""

    # -- nuisances first: these can interleave with any branch. ----------
    if cls == "pause_key":
        # Closed-game refusal often shares the screen with ``[Pause]``
        # (a-net live). Detect BEFORE dismissing the pause so we do not
        # loop forever via door re-entry (hub 194645Z).
        if _CLOSED_GAME_RE.search(text or ""):
            raise LoginError(f"game_closed:profile={profile.name}")
        return "", False, None
    if _CLOSED_GAME_RE.search(text or ""):
        raise LoginError(f"game_closed:profile={profile.name}")
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
    # Intentional whole-grid match (stale-scrollback hazard accepted):
    # "show today's log?" sits in the BODY a line or more above the
    # current prompt by the time we classify, never on the prompt line
    # itself -- a prompt-only search would miss the live gate. One-shot
    # interstitial; unlikely to linger as a false-fire after answer.
    if _SHOW_LOG_RE.search(text):
        return "N", False, None
    # Stale-scrollback hazard: pyte keeps prior "clear avoids?" cells.
    # Scope to current prompt line OR the option-block attached to that
    # prompt (same helper as MODULE_ENTRY) — never the whole grid.
    if _CLEAR_AVOIDS_RE.search(prompt) or _CLEAR_AVOIDS_RE.search(
        _option_block_above_prompt(text, prompt)
    ):
        # Keep avoids unless the profile explicitly opts in (rare).
        clear = bool(getattr(profile, "clear_avoids_on_login", False))
        return ("Y" if clear else "N"), False, None
    # Stale-scrollback hazard: pyte can leave a prior inactivity banner in
    # the grid. Whole-grid `.search(text)` would blank-Enter against an
    # unrelated later prompt (Accept #4 — "harmless" claim falsified).
    # Scope to current prompt line OR the option-block attached to that
    # prompt (same helper as MODULE_ENTRY / CLEAR_AVOIDS) so a fresh
    # warning still matches in the BODY above the prompt, never only on
    # the last line.
    if _INACTIVITY_RE.search(prompt) or _INACTIVITY_RE.search(
        _option_block_above_prompt(text, prompt)
    ):
        # Keepalive nudge for a LIVE inactivity banner -- blank Enter
        # resets the server's idle clock without altering any pending
        # field entry.
        return "", False, None

    # -- outer BBS-level connection name vs. the TW2002 module's own
    # character-handle prompt: both anchor to login_name, disambiguated
    # by the exact wording captured live ("... (ENTER for none)").
    if cls == "login_name":
        if _OUTER_NAME_PROMPT_RE.search(prompt):
            if _OUTER_NAME_REJECTED_RE.search(text):
                # WO-MICRO-LOGIN-BLANK-REJECT: this same outer gate is
                # re-printed AND the host has explicitly told us why --
                # "A login name is required." -- so the canon-correct
                # blank we just sent was refused. A host demanding a name
                # is telling us plainly what it wants: retry ONCE with the
                # profile's own handle rather than resending the same
                # blank forever (captured live against
                # twgs.microblaster.net -- see
                # audit/micro-unknown-step6-corpus-20260726.md).
                if state["outer_name_handle_tried"]:
                    # The one bounded retry is already spent and this same
                    # gate is STILL rejecting -- do not keep guessing.
                    # Fail loud with a NAME that says what the host did,
                    # never the generic unknown/automaton_stuck shape (see
                    # this WO's Accept). Only `profile.name` (a config
                    # value, not screen text) is interpolated, matching
                    # every other plain `LoginError` raise in this
                    # function (`registration_not_permitted`,
                    # `returning_password_rejected`, etc.).
                    raise LoginError(f"login_name_rejected:profile={profile.name}")
                state["outer_name_handle_tried"] = True
                return profile.handle, False, None
            return "", False, None
        return profile.handle, False, None

    if cls == "login_alias":
        # WO-FIX-LOGIN-ALIAS-PROMPT-UNHANDLED: server rejected the configured
        # handle and demands a distinct Alias. Mint handle+suffix, persist,
        # bounded retries — never automaton_stuck on this known gate.
        state["registering"] = True
        state["alias_attempts"] += 1
        if state["alias_attempts"] > _MAX_ALIAS_RETRIES:
            raise LoginError(f"alias_retries_exhausted:profile={profile.name}")
        alias = _fresh_alias(getattr(profile, "handle", None) or "Trader")
        state["alias"] = alias
        saver = state.get("save_alias")
        if callable(saver):
            saver(profile.name, alias)
        return alias, False, None

    if cls == "ansi_prompt":
        return "Y", False, None

    if cls == "game_select":
        # A real game-select prompt is answered exactly ONCE per TCP
        # connection -- a SECOND `game_select` classification on this
        # same connection is BY DEFINITION a misfire (most likely a
        # stale pyte buffer from earlier in the connection, classified
        # via a later ordinary screen sharing the same generic prompt),
        # not a genuine second game-select screen to answer. Refusing
        # here -- returning None, the same "nothing matched" signal any
        # other unrecognized screen produces -- routes it through the
        # SAME stagnation/`automaton_stuck` fail-loud path, never a blind
        # keystroke.
        if getattr(session, "game_select_answered", False):
            return None
        return profile.game_letter, False, None

    if cls == "menu" and _is_module_entry_menu(text, prompt):
        return "T", False, None

    if cls == "char_create":
        # Auto-creating a character on a real server is a policy call,
        # not a pure mechanics one -- refuse BEFORE the "Y" that starts
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
        # create one".
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
                # maximally recoverable even if a later step fails. The
                # value is fixed for the whole run, so an early save is
                # never stale.
                save_password(profile.name, state["password"])
            # NEW branch: the create/repeat "didn't match" dance is a
            # legitimate re-TYPE retry, not a rejection of an
            # already-known-bad value -- keep the existing bounded budget.
            state["password_attempts"] += 1
            if state["password_attempts"] > _MAX_PASSWORD_RETRIES:
                raise LoginError(f"password_retries_exhausted:profile={profile.name}")
            return state["password"], True, None

        # RETURNING branch (canon: login-automaton.md) -- the saved
        # credential is sent EXACTLY ONCE, never re-sent. `state["password"]`
        # already being set here means this same gate has already been
        # answered once this run and reappeared anyway.
        #
        # Mack HIGH (adversarial review): raising HERE, immediately and
        # unconditionally, false-rejects a genuinely valid login whenever
        # the server's post-password response is slow/two-stage (an early
        # byte, then the real next screen a couple hundred ms later) --
        # this same reappearance is, for one instant, indistinguishable
        # from a genuine rejection. Returning `None` instead (this
        # function's own "nothing matched yet" signal) hands it to
        # `run_login`'s EXISTING stagnant-rounds grace: a transient
        # reappearance resolves within that grace once the real screen
        # arrives (no action returned here means no re-send either --
        # "sent once" still holds); a genuinely persistent, settled
        # rejection exhausts the grace and `run_login` raises the specific
        # `returning_password_rejected` error itself once `cls` is STILL
        # `login_password` with this same state after
        # `_STAGNANT_ROUNDS_LIMIT` rounds (see that raise site).
        if state["password"] is not None:
            return None
        saved = get_password(profile.name)
        if saved is None:
            raise LoginError(
                f"returning_no_saved_password:profile={profile.name}:handle={profile.handle}"
            )
        state["password"] = saved
        state["password_attempts"] += 1
        return state["password"], True, None

    # These sub-step matches are against the CURRENT prompt line only
    # (never the whole screen -- see the regexes' own module-level
    # comment for the stale-scrollback trap this avoids).
    if _TRADER_NAME_CHOICE_RE.search(prompt):
        return "B", False, None

    if _SHIP_NAME_PROMPT_RE.search(prompt):
        return profile.ship_name, False, None

    if _SHIP_CONFIRM_RE.search(prompt):
        return "Y", False, None

    # Intentional hybrid (stale-scrollback hazard gated): the current
    # bottom line is only a generic input-box marker ("[---...---]"), so
    # `_PLANET_NAME_BOX_RE` on ``prompt`` anchors us to THIS sub-step;
    # only then may `_PLANET_NAME_PROMPT_RE` search the full screen for
    # "name your home planet" (wording that sits above the box, never on
    # the prompt line). The box gate prevents a stale planet-name body
    # from firing against an unrelated later prompt.
    if _PLANET_NAME_BOX_RE.search(prompt) and _PLANET_NAME_PROMPT_RE.search(text):
        return profile.planet_name, False, None

    if _PLANET_COMMAND_RE.search(prompt):
        return "Q", False, None

    # Modded/variant-server NEW-branch extras. Scoped to
    # state["registering"] so this can never fire for the RETURNING
    # branch or before char_create has even been seen. Checked LAST,
    # after every established sub-step above, so a real recognized step
    # always takes priority.
    if state["registering"]:
        for pattern, response in _NEW_BRANCH_VARIANTS:
            if pattern.search(prompt):
                return response, False, None

    return None


def _fresh_password(length=8):
    """Delegate to the canonical mint in ``credentials.generate_password``
    (WO-PASSWORD-MINT-CANON).  Single source of truth for CSPRNG alnum ≤8."""
    from .credentials import generate_password
    return generate_password(length)


def _fresh_alias(handle: str) -> str:
    """Handle + short CSPRNG suffix for TWGS Alias prompts (bounded retries)."""
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(_ALIAS_SUFFIX_LEN))
    base = (handle or "Trader").strip() or "Trader"
    # Drop characters some hosts reject in aliases; keep alnum.
    cleaned = "".join(ch for ch in base if ch.isalnum())
    if not cleaned:
        cleaned = "Trader"
    max_base = max(1, _ALIAS_MAX_LEN - len(suffix))
    if len(cleaned) > max_base:
        cleaned = cleaned[:max_base]
    return f"{cleaned}{suffix}"
