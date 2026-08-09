"""The read-only, never-commit menu crawler (canon: K3).

Enumerates a world's per-world MENU MAP into the ``menu.knowledge`` store
(``upsert_menu_node`` / ``upsert_menu_edge``) so a deterministic navigator
(``menu.nav``) can read it back. Canon:
``canon/engine/menu-map-and-introspection.md`` and the K3 section of
``canon/doctrine/action-safety-guards.md``.

**Human-invoked, supervised discovery — never an autonomous agent.** The
operator starts a crawl against a disposable character with the hub
watching, or the teacher assists a targeted map-fill after an escalation.
(The archived module described this as "AI-driven"; canon's reborn recast
retires that framing, and this module is written to the recast.)

**THE NEVER-COMMIT GUARANTEE LIVES OUTSIDE THIS MODULE — AND TIP HAS NO
LIVE DRIVER TODAY.** The module that held the code-enforced half of it,
``menu/crawl_driver.py`` (``run_live_crawl()``), was retired
(WO-CLEANUP-DEAD-SYMBOLS-BATCH-2026-08-05): it had zero product callers,
because the daemon's ``crawl_start`` protocol verb has never been wired to
a driver. Driving this module against a live connection is not currently
wired to anything — see ``canon/engine/menu-map-and-introspection.md``
§ "The guarantee lives in the supervised run, not the word-list" for the
full picture. What still lives on tip, for a future driver rebuild to wire
back up:

1. ``credentials.is_crawl_sacrificial()`` — the fail-closed
   `crawl_sacrificial` flag reader the retired driver's sacrificial-only
   startup gate read; today it backs only the unrelated ``dev``-sender
   exception (``canon/doctrine/dev-drive-exception.md``), not a live
   crawl;
2. ``control_lock.is_driver_fenced()`` — the boundary-fence signal a
   hub-supervisor abort or a human ``tw attach`` would raise; a rebuilt
   driver would check it ahead of the real session factory, as the
   retired one did.

That pairing (a disposable zero-credit / zero-asset character plus a
supervisor able to abort) is what bounds the worst case to *nothing*. The
classification below is **best-effort defense-in-depth**: its job is to
minimize how often the crawl even brushes up against a commit action, not
to be a completeness proof. An unbounded natural-language label space
cannot be lexically classified with proven completeness; canon records the
accepted residuals explicitly (prefix-affixed deny verbs like
"Repurchase"; agent-/action-nouns sharing a verb stem like "Buyer",
"Ejection", "Confirmation"; the "board" homograph; and a genuinely novel
or mislabeled commit action sharing no vocabulary with anything denied).

Within that frame the chokepoint discipline is real and kept tight: every
candidate keystroke this module could send passes through exactly one
function, `emit_key_if_safe()`, which is the only place in the whole
``menu`` package that reaches ``settle.send_and_confirm`` (and thus
``session.send``). It is **deny-by-default** and **self-verifying**: it
re-derives the category from the label itself rather than trusting the
one its caller passed, so a caller that mislabels a candidate cannot open
the gate (see that function's docstring).

**Categories, never raw keystrokes.** Canon is explicit that a key is
judged from its rendered *text label*, never from the bare keystroke: the
same physical key means different things on different screens (``B`` is
"Buy" on one menu and "Back" on another). There is therefore deliberately
no list of "destructive keys" anywhere in this module — the safe and
state-changing sets below are *label-category* vocabularies, and both
public frozensets are derived from their pattern dicts rather than typed
out a second time.

**Three safety layers.**

1. **Per-option label gate** (`classify_option_label`) — deny-by-default:
   a key is emittable only on an affirmative match to the small safe
   allowlist (view / help / list / display / examine / back / previous).
   A named state-changing verb, a **compound** label naming more than one
   clause ("View & Repair Ship" reads safe by its first clause but commits
   its second), or any unrecognized label classifies ``"unknown"`` and is
   recorded-not-pressed.
2. **Per-screen safety classification** (`screen_state`), evaluated
   *before* any option on the current screen is even enumerated. A screen
   that looks like a commit / confirm / purchase / combat gate — by
   keyword anywhere on screen, structurally by the shape of its active
   prompt line, or by matching one of ``classify``'s own login / pause /
   game-select / char-create / cim gate anchors — is never enumerated at
   all. Not even its options' labels are read. That is what "back out to a
   safe menu without answering" means in practice. The same leg carries
   canon's escalate-only classes (``classify.NEVER_AUTO_ACTION_CLASSES``,
   ``money_prompt`` today — `DECISIONS.md` §A.2, aligning P-QTY): a
   quantity / money / bank-transfer question the server is blocked on is
   refused BY CLASS, so it stays refused even if some future edit loosens
   the keyword scan below it.
3. **No bare Enter, ever.** A bare vertical confirm (``"(Y)es\\n(N)o"``,
   ``"(A)ccept\\n(D)ecline"``) has an ordinary bracket-option line as its
   last line and slips past both layers above. A synthetic bare-Enter
   option is still *discovered* (so the graph notes an Enter transition
   exists) but is never in the safe allowlist. "Quit" is likewise never
   emittable: the replay-from-start traversal never needs to press
   quit/back to navigate, so a quit option — an innocent parent-menu quit
   or a genuine session exit alike — is always recorded-not-pressed.

**Traversal: BFS via replay-from-start, not stateful backtracking.**
`crawl_menus()` never remembers "how do I get back" from wherever it last
was; it remembers, per discovered node, the ordered list of
already-proven-safe ``(key, label, category)`` steps that reached it from
the world's start context. To probe a node's next untried option it asks
``session_factory()`` for a fresh session already sitting at that start
context and replays the safe path through the same chokepoint, one hop at
a time, re-checking `screen_state()` at every hop. This is what lets the
crawler have no notion of "cancel this confirm" or "undo my last
keystroke" at all — every replayed step was already proven side-effect-free
by the same gate. It is also what gives the driver its abort seam: a fresh
session is requested only at a screen boundary, never mid-send.

**Edge kinds — canon's three, deliberately.** Canon's schema is
``nav | info | action`` with no ``"unknown"`` kind, so every
recorded-not-pressed edge is written ``kind="action"`` and the real
category rides in the edge's ``desc`` (``"buy: Buy New Ship"`` vs
``"unknown: K----"``) — the distinction is never lost. The store's own
``MENU_EDGE_KINDS`` now holds exactly those three (it briefly also
accepted ``"escape"`` and ``"unknown"`` — code drift canon never defined,
which this module already declined to write); an import-time assert pins
the two sets equal so neither can drift from canon again.
"""

import re
from collections import deque

from ..session.classify import NEVER_AUTO_ACTION_CLASSES, classify_screen
from ..session.settle import send_and_confirm_for, wait_until_settled
from .knowledge import (
    MENU_EDGE_KINDS,
    record_crawl_status,
    upsert_menu_edge,
    upsert_menu_node,
)
from .sig import menu_signature

# -- the safety vocabulary ----------------------------------------------------
# CATEGORIES, not raw keystrokes: the same physical key is not stable
# across menus (see module docstring), so every set below names the
# semantic label-category a discovered option classifies into, and
# `emitted_keys` / `send_log` record that category, never a bare letter.

_SAFE_LABEL_PATTERNS = {
    "view": re.compile(r"\bview\b", re.I),
    "help": re.compile(r"\bhelp\b", re.I),
    # `\blist\b`'s trailing boundary does not match "listing" (list+ing
    # fails mid-word), so "Port Listing" would classify "unknown" rather
    # than affirmatively safe. `\blisting\b` is spelled out rather than a
    # blanket `\blist` prefix, which would also swallow the unrelated
    # "Listen"/"Listening".
    "list": re.compile(r"\blist\b|\blisting\b", re.I),
    "display": re.compile(r"\bdisplay\b", re.I),
    "examine": re.compile(r"\bexamine\b|\binspect\b", re.I),
    "back": re.compile(r"\bback\b", re.I),
    "previous": re.compile(r"\bprevious\b|\bprev\b", re.I),
    # NOTE: no "quit" entry, deliberately. A bare "(Q)uit" can end the
    # live session outright, and the BFS-via-replay traversal never needs
    # to press quit/back to navigate (it always replays each frontier's
    # safe-step path from a fresh start), so ANY quit-labeled option --
    # an ordinary "back to parent menu" quit or a genuine session exit
    # alike -- is recorded-not-pressed, same as any unrecognized label.
    # There is deliberately no carve-out regex distinguishing the two.
}

# Every pattern below is bounded to ACTIVE VERB CONJUGATIONS ONLY (bare
# form / -s / -ed / -ing / genuine irregulars) -- never a bare prefix,
# never an agent-/action-noun suffix. Two failure modes are being held
# apart:
#
#   * a TRAILING word boundary alone is defeated by a glued suffix
#     ("Buyout" dodges `\bbuy\b`, "Ejection" dodges `\beject\b"), so the
#     conjugation alternatives are spelled out explicitly;
#   * a BLANKET prefix (`\bbuy`) over-matches ordinary informational
#     nouns ("Buyer", "Vendor", "Movement", "Redemption") and unrelated
#     English words ("mine" -> "mineral", "steal" -> "stealth"), which
#     would cripple legitimate crawl coverage.
#
# Canon accepts the resulting agent-/derived-noun leak as a residual
# bounded to zero real-world impact by the sacrificial-character +
# supervised-abort protocol -- it is not a gap this vocabulary claims to
# close.
_DENY_LABEL_PATTERNS = {
    "buy": re.compile(r"\bbuy(s|ing)?\b|\bbought\b", re.I),  # NOT blanket -- "Buyer"/"Buyout"
    "sell": re.compile(r"\bsell(s|ing)?\b|\bsold\b", re.I),  # NOT blanket -- "Seller"
    "purchase": re.compile(r"\bpurchase(s|d)?\b|\bpurchasing\b", re.I),  # NOT blanket -- "Purchaser"
    "attack": re.compile(r"\battack(s|ed|ing)?\b|\bfire(s|d)?\b|\bfiring\b|\bfight(s|ing)?\b", re.I),
    "deploy": re.compile(r"\bdeploy(s|ed|ing)?\b", re.I),  # NOT blanket -- "Deployment"
    "genesis": re.compile(r"\bgenesis", re.I),  # effectively a proper noun here; no derived form
    "move": re.compile(r"\bmove(s|d)?\b|\bmoving\b|\bwarp(s|ed|ing)?\b", re.I),  # NOT blanket -- "Movement"
    "jump": re.compile(r"\bjump(s|ed|ing)?\b", re.I),  # NOT blanket -- "Jumper"
    "tow": re.compile(r"\btow(s|ed|ing)?\b", re.I),  # NOT blanket -- "towel"
    "land": re.compile(r"\bland(s|ed|ing)?\b", re.I),  # NOT blanket -- "landscape"
    "take": re.compile(r"\btake(s|n)?\b|\btaking\b|\btook\b|\bclaim(s|ed|ing)?\b", re.I),
    # Covers an explicit "Confirm" option AND a bare "Yes" label ever
    # reachable via the per-option scan -- the second, independent layer
    # behind `screen_state`'s own confirm-screen gate. "yes" KEEPS its
    # trailing boundary so "yesterday" cannot dodge it.
    "confirm": re.compile(r"\bconfirm(s|ed|ing)?\b|\byes\b", re.I),
    "acquire": re.compile(r"\bacquire(s|d)?\b|\bacquiring\b", re.I),  # NOT blanket -- "Acquirer"
    "requisition": re.compile(r"\brequisition(s|ed|ing)?\b", re.I),
    "order": re.compile(r"\border(s|ed|ing)?\b", re.I),  # NOT blanket -- "orderly"
    "trade": re.compile(r"\btrade(s|d)?\b|\btrading\b", re.I),  # NOT blanket -- "Trader(s) Guild"
    "dock": re.compile(r"\bdock(s|ed|ing)?\b", re.I),  # NOT blanket -- "docket"
    "eject": re.compile(r"\beject(s|ed|ing)?\b", re.I),  # NOT blanket -- "Ejection" (residual)
    "drop": re.compile(r"\bdrop(s|ped|ping)?\b", re.I),  # NOT blanket -- "dropdown"
    "transfer": re.compile(r"\btransfer(s|red|ring)?\b", re.I),  # NOT blanket -- "Transferee"
    "upgrade": re.compile(r"\bupgrade(s|d)?\b|\bupgrading\b", re.I),  # NOT blanket -- "upgradeable"
    "repair": re.compile(r"\brepair(s|ed|ing)?\b", re.I),  # NOT blanket -- "Repairman"
    "refuel": re.compile(r"\brefuel(s|ed|ing)?\b", re.I),
    "launch": re.compile(r"\blaunch(s|ed|ing)?\b", re.I),  # NOT blanket -- "Launcher"
    "abandon": re.compile(r"\babandon(s|ed|ing)?\b", re.I),  # NOT blanket -- "Abandonment"
    "jettison": re.compile(r"\bjettison(s|ed|ing)?\b", re.I),
    "pay": re.compile(r"\bpay(s|ing|ment)?\b|\bpaid\b", re.I),  # NOT blanket -- "payload"
    "invest": re.compile(r"\binvest(s|ed|ing|ment)?\b", re.I),  # NOT blanket -- "investigate"
    "bribe": re.compile(r"\bbribe(s|d)?\b|\bbribing\b", re.I),  # NOT blanket -- "bribery"
    "steal": re.compile(r"\bsteal(s|ing)?\b|\bstole\b|\bstolen\b", re.I),  # NOT blanket -- "stealth"
    # "Board" bare is far more often the common UI noun ("Bounty Board",
    # "Notice Board") than the rare piracy verb; only the unambiguous
    # active form is denied. Canon records the bare-verb leak as accepted
    # residual rather than re-introducing the noun false positive.
    "board": re.compile(r"\bboarding\b", re.I),
    "ram": re.compile(r"\bram(s|med|ming)?\b", re.I),  # NOT blanket -- "ramble"
    "cloak": re.compile(r"\bcloak(s|ed|ing)?\b", re.I),  # NOT blanket -- "Cloakroom"
    "mine": re.compile(r"\bmine(s|d)?\b|\bmining\b", re.I),  # NOT blanket -- "mineral"
    "send": re.compile(r"\bsend(s|ing)?\b|\bsent\b", re.I),  # irregular past tense
    "load": re.compile(r"\bload(s|ed|ing)?\b|\bladen\b", re.I),  # irregular participle
    # "sale" is fundamentally a NOUN (the verb is "sell", its own category
    # above), so even the regular plural "Sales" is the collision to avoid
    # ("Sales Tax", "Sales History"), not a derived form. Bounded on BOTH
    # sides with no suffix -- deliberately the one exception to this
    # dict's verb-conjugation shape. Still catches "(item) For Sale".
    "sale": re.compile(r"\bsale\b", re.I),
    # NOTE: no "listing" entry -- it collides with the SAFE "list"
    # category's own gerund ("Port Listing" would be wrongly denied), and
    # ordinary list navigation is far more common than an auction
    # listing. "auction" alone still catches the auction-specific case.
    "auction": re.compile(r"\bauction(s|ed|ing)?\b", re.I),  # NOT blanket -- "Auctioneer"
    "barter": re.compile(r"\bbarter(s|ed|ing)?\b", re.I),
    "lease": re.compile(r"\blease(s|d)?\b|\bleasing\b", re.I),  # NOT blanket -- "Lessee"
    "rent": re.compile(r"\brent(s|ed|ing)?\b", re.I),  # NOT blanket -- "Rental"
    "vend": re.compile(r"\bvend(s|ed|ing)?\b", re.I),  # NOT blanket -- "Vendor"
    "payoff": re.compile(r"\bpayoffs?\b", re.I),
    "wager": re.compile(r"\bwager(s|ed|ing)?\b", re.I),
    "bet": re.compile(r"\bbet(s|ting)?\b", re.I),  # NOT blanket -- "better"/"between"
    "gamble": re.compile(r"\bgamble(s|d)?\b|\bgambling\b", re.I),  # NOT blanket -- "Gambler"
    "ransom": re.compile(r"\bransom(s|ed|ing)?\b", re.I),
    "donate": re.compile(r"\bdonate(s|d)?\b|\bdonating\b", re.I),  # NOT blanket -- "Donation"
    # Like "sale", "gift" as a common noun ("View Available Gifts") is the
    # collision to avoid more than any derived verb form. The bare
    # imperative "Gift a Torpedo" still matches.
    "gift": re.compile(r"\bgift\b", re.I),
    "spend": re.compile(r"\bspend(s|ing)?\b|\bspent\b", re.I),  # NOT blanket -- "Spender"
    "redeem": re.compile(r"\bredeem(s|ed|ing)?\b", re.I),  # NOT blanket -- "Redemption"
    "forfeit": re.compile(r"\bforfeit(s|ed|ing)?\b", re.I),  # NOT blanket -- "Forfeiture"
    "surrender": re.compile(r"\bsurrender(s|ed|ing)?\b", re.I),
    # "Withdrawal" is always a noun (a completed transaction record) --
    # zero commit-coverage upside from catching it.
    "withdraw": re.compile(r"\bwithdraw(s|n|ing)?\b", re.I),
    "deposit": re.compile(r"\bdeposit(s|ed|ing)?\b", re.I),
    # "Committed"/"Commitment" read as adjectival/informational far more
    # often than as an active commit ("Committed Resources", "View
    # Commitment Report"); bare "Commit"/"Commits"/"Committing" still
    # catch the verb.
    "commit": re.compile(r"\bcommit(s|ting)?\b", re.I),
    # "Accepted" reads as an adjective far more often than an active
    # accept ("Accepted Applications"); the bare verb forms still catch
    # the Accept/Decline screen-level closure.
    "accept": re.compile(r"\baccept(s|ing)?\b", re.I),
}

# A label naming MORE than one clause: "View & Repair Ship" reads safe by
# its first clause alone but commits whatever its second clause does.
# Checked STRUCTURALLY, independent of the deny vocabulary -- a compound
# whose second clause dodges every deny word ("View and Examine Log") is
# still never classified safe; a clean single-clause label ("Display
# Combat Rating") is unaffected. "plus" and "with" are deliberately NOT
# connectors here: both over-reject ordinary single-clause labels ("Help
# with Navigation") far more often than they catch a genuine compound,
# and a false positive actively cripples legitimate crawl coverage.
_COMPOUND_LABEL_RE = re.compile(
    r"\b(?:and|then|as\s+well\s+as|along\s+with)\b|[&,/+]", re.I
)

# Derived from the pattern dicts, never typed out a second time -- the
# vocabulary has exactly one home, so a category cannot be added to a
# pattern dict and silently missed by the frozenset (or vice versa).
# `"bare_enter"` is deliberately absent from SAFE_ALLOWLIST: see the
# module docstring's safety layer 3.
SAFE_ALLOWLIST = frozenset(_SAFE_LABEL_PATTERNS)
STATE_CHANGING_KEYS = frozenset(_DENY_LABEL_PATTERNS)

# Structural, not convention: no category can ever be both emittable and
# named-dangerous. Tripping this would mean one category word was added
# to both dicts above by mistake.
assert not (SAFE_ALLOWLIST & STATE_CHANGING_KEYS), (
    "menu.crawler: SAFE_ALLOWLIST and STATE_CHANGING_KEYS must stay disjoint"
)

# Canon's edge schema is exactly these three (no "unknown" kind), and the
# store's vocabulary is checked at import to be exactly the same set --
# introspected from the store's own constant rather than assumed.
#
# EQUALITY, not containment, and that is the point. The store once accepted
# a wider set ("escape"/"unknown"); a containment check stayed happily green
# throughout, because everything canon defines was still in there. Only
# equality can see the failure mode that actually happened -- the store
# growing a kind canon never defined, which would let a recorded-not-pressed
# option persist as its own kind instead of folding its category into `desc`.
CANON_EDGE_KINDS = frozenset({"nav", "info", "action"})
assert CANON_EDGE_KINDS == MENU_EDGE_KINDS, (
    "menu.crawler: the knowledge store's edge vocabulary has drifted from canon's "
    f"nav|info|action -- store has {sorted(MENU_EDGE_KINDS)}"
)

_NAV_CATEGORIES = frozenset({"back", "previous"})
_INFO_CATEGORIES = frozenset({"view", "help", "list", "display", "examine"})

# Placeholder `to_node` for a recorded-not-pressed option: the crawler
# never presses it, so there is no real destination signature to record.
UNEXPLORED_TARGET = "<unexplored>"

# The sentinel key an Enter transition is recorded under (Enter itself is
# the empty string, which the store rejects as an edge key).
ENTER_EDGE_KEY = "<enter>"

# A hard cap on how many frontier nodes a single crawl visits -- the same
# bounded-rail philosophy as the run-loop rails: a supervised crawl must
# never be capable of looping forever against a pathological or
# mis-fixtured menu graph.
_DEFAULT_MAX_NODES = 200


# -- screen-level safety classification ---------------------------------------

# Distinctive shapes of a commit / confirm / purchase / combat gate.
# `classify` has no anchors for these (its taxonomy is login / pause /
# sector / port / menu, a different concern), so this module names them.
# Deliberately broad: any one matching ANYWHERE on the screen marks the
# whole screen unsafe to crawl from.
#
# THIS IS THE LOAD-BEARING LEG, not a supplement to the structural one --
# a correction, because this comment used to say the opposite ("an
# additional layer, not the sole gate"). Measured by replaying 91 archived
# session transcripts through the real render pipeline (11,240 settled
# prompt frames the operator answered): of the 6,548 frames `screen_state`
# refuses, this keyword scan is the SOLE reason for 2,990 of them -- an
# order of magnitude more than the structural prompt-shape leg's 271, and
# more than the classify-class leg's 694. It carries, alone, the entire
# 899-frame "Your offer [N] ?" port-haggle family that canon marks
# escalate-only (P-QTY / DECISIONS.md A.2); on those frames the structural
# leg contributed literally nothing before the trailing-"?" widening
# below, and still carries only 115 of the 899 after it.
#
# Two consequences, both real:
#   * narrowing this list is a SAFETY edit, however cosmetic it looks. The
#     tests that force it empty and demand a money screen still be refused
#     (tests/test_menu_crawler.py) exist because of that, and they are the
#     only thing standing under most of these frames;
#   * it is still a pure denylist over unbounded natural language, so it
#     is best-effort by construction (module docstring). Being the biggest
#     leg and being a complete one are different claims -- this is the
#     first and not the second, which is precisely why the never-commit
#     GUARANTEE lives outside this module in the driver.
#
# See `_is_commit_shaped_prompt` for the structural, keyword-independent
# leg -- narrower in reach, and valuable for being INDEPENDENT of wording
# rather than for volume.
_UNSAFE_SCREEN_PATTERNS = (
    re.compile(r"\(\s*y\s*/\s*n\s*\)", re.I),
    re.compile(r"\[\s*y\s*/\s*n\s*\]", re.I),
    re.compile(r"are\s+you\s+sure", re.I),
    re.compile(r"\bconfirm\b", re.I),
    re.compile(r"do\s+you\s+(wish|want)\s+to", re.I),
    re.compile(r"\bpurchase\b", re.I),
    re.compile(r"how\s+many\s+(holds|units)", re.I),
    # The money/quantity family the line above only sampled (canon P-QTY /
    # DECISIONS §A.2). Added ALONGSIDE it rather than widening it, so the
    # captured holds/units shape keeps its own pin: a later tightening
    # here can never silently un-cover the one screen actually captured.
    # Requires the quantity question to name a commerce verb or credits,
    # which is what keeps it off the safe informational prompts a crawl
    # exists to enumerate ("How many sectors have I visited?").
    re.compile(
        r"how\s+m(?:any|uch)\b[^\n]*?\b(?:buy|sell|purchase|deploy|drop|transfer|deposit|withdraw|credits?)\b",
        re.I,
    ),
    re.compile(r"\b(?:transfer|deposit|withdraw)\b[^\n]*?\bcredits?\b", re.I),
    # NOT a bare `\bcombat\b` -- that also matches the perfectly safe
    # informational "Display Combat Rating" / "View Combat Log". Anchored
    # to phrases meaning combat is ACTUALLY active, not merely mentioned.
    re.compile(r"\bunder\s+attack\b|enemies?\s+present|\bfire\s+(phasers|photons|weapons)\b"
               r"|\bcombat\s+(has\s+begun|is\s+engaged)\b|\bentering\s+combat\b", re.I),
)

# `classify` gate anchors meaning "this is not an ordinary navigable menu
# screen at all" -- a login / pause / door-select / character-creation
# gate, or a genuine CIM report. Never crawled through.
#
# UNIONED, never restated: `classify.NEVER_AUTO_ACTION_CLASSES` is canon's
# escalate-only set (DECISIONS §A.2 -- `money_prompt` today). Deriving it
# means a class added there is refused HERE the same day, with no second
# edit to remember; a literal copy of "money_prompt" would have been a
# second source of truth and the drift would be silent in the unsafe
# direction. This module already learned that lesson in `classify`'s own
# history (one exclusivity check, not divergent copies).
_NON_MENU_GATE_CLASSES = frozenset({
    "login_password", "login_name", "pause_key", "ansi_prompt",
    "game_select", "char_create", "cim_report",
}) | NEVER_AUTO_ACTION_CLASSES

# Structural, keyword-independent commit-shape detection on the ACTIVE
# prompt line (the single line the server is actually blocked on). The
# whole-screen keyword scan above has no notion of which line is live, so
# ordinary menu chrome sharing a screen with a real commit prompt
# ("(V)iew Ship Status" alongside "Proceed? [Yes]") dodges every keyword
# and enumerates as an ordinary menu. These two catch the SHAPE instead,
# independent of wording.
#
# What this leg is NOT: the robust backstop under a weak keyword list.
# This comment used to imply that ordering and the corpus says otherwise
# (see the keyword scan's own comment for the numbers) -- these two
# patterns are the SOLE reason 271 of 6,548 refused frames are refused,
# against the keyword scan's 2,990. The right way to read the pair is
# COMPLEMENTARY, not ranked: this leg is narrow but wording-independent
# and prompt-line-scoped, which is the only thing that catches a commit
# prompt phrased in vocabulary nobody thought to deny; the keyword scan is
# broad but blind to which line is live. Neither is the other's safety
# net, and the never-commit guarantee is not either of them (module
# docstring: it is the driver's sacrificial-profile gate plus the
# boundary-aligned abort).
_TRAILING_DEFAULT_BRACKET_RE = re.compile(
    # "...? [Y]:" / "...[Yes]" / "...[0]:" / "...[N] ?" -- a trailing
    # SQUARE-bracket default-answer token. Square brackets are this game's
    # convention for a suggested/default VALUE; this module's own menu
    # OPTIONS are always paren/angle brackets ("(Q)uit"), never square,
    # which is what lets this stay structural instead of colliding with an
    # ordinary bracket-option line.
    #
    # BOTH trailers, ":" and "?", because TradeWars writes both and the
    # punctuation after the token is not the tell -- the token is. The "?"
    # arm was measured before it was added, replaying 91 archived session
    # transcripts back through the real TelnetHandler -> pyte pipeline
    # (11,240 settled prompt frames the operator actually answered): it
    # changes 12 of them, ALL "other" -> "unsafe", and ZERO
    # "menu" -> "unsafe" -- the crawler gives up no screen it was actually
    # exploring. What it buys is a SECOND leg under prompts the keyword
    # scan ABOVE was carrying alone (see `_UNSAFE_SCREEN_PATTERNS`' own
    # comment): the port haggle's "Your offer [550] ?" family, 899 frames.
    #
    # The payload class stays alnum-only, deliberately, and that is what
    # keeps the comma-grouped majority of that same haggle family --
    # "Your offer [4,710] ?" -- OUT. Measured, admitting commas buys zero
    # additional state changes (every such frame is already refused by
    # keyword) while spending the one restriction that keeps an ordinary
    # status bracket like "[TL=00:00:00]" (punctuation inside) from
    # matching. So it is a KNOWN, deliberately-open hole, not an oversight;
    # tests/test_menu_crawler.py pins it as one.
    r"\[\s*[a-zA-Z0-9]{1,10}\s*\]\s*[:?]?\s*$"
)
_FREE_INPUT_PROMPT_RE = re.compile(
    # "Enter quantity to buy:" / "How many fighters to deploy:" -- a
    # free-value solicitation with no fixed menu of options at all, so
    # there is no safe bare-Enter and no safe label to press here
    # regardless of what else is on screen. Deliberately broad: a benign
    # "Enter your choice:" invitation also matches and is classified
    # unsafe too -- a false "unsafe" only under-explores the graph, which
    # is the harmless direction.
    r"\b(?:enter|how\s+many|how\s+much|what\s+is|type\s+in)\b.*[:?]\s*$",
    re.I,
)


def _is_commit_shaped_prompt(prompt_line):
    """True iff the ACTIVE prompt line structurally looks like a commit /
    confirm / default-answer / free-input request, independent of its exact
    wording. Checked in `screen_state` as an ADDITIONAL layer alongside
    (never a replacement for) the whole-screen keyword scan."""
    if not prompt_line:
        return False
    return bool(
        _TRAILING_DEFAULT_BRACKET_RE.search(prompt_line)
        or _FREE_INPUT_PROMPT_RE.search(prompt_line)
    )


def _is_menu_select_prompt(prompt_line):
    """Deny-by-default, mirroring `classify_option_label`: a screen is
    crawlable ("menu") ONLY when its active prompt AFFIRMATIVELY looks like
    an ordinary menu-selection invitation -- never merely because
    `enumerate_options` found >=2 bracket lines somewhere on the screen.

    The one recognized shape: the active prompt line IS ITSELF one of the
    menu's own qualifying option lines -- the real captured shape (a
    StarDock-style menu's last rendered line is its own final option,
    "(Q)uit to Sector", not a separate "Enter your choice:" line). A
    commit-shaped prompt, checked first, always loses even if it also
    happens to look like an option line.

    Extend this allowlist only against a live-captured screen shape that
    needs it: a false negative here only under-explores the graph."""
    if not prompt_line or _is_commit_shaped_prompt(prompt_line):
        return False
    return bool(_BRACKET_OPTION_RE.search(prompt_line) or _DASH_OPTION_LINE_RE.match(prompt_line))


def screen_state(full_text, prompt_line):
    """Classify the CURRENT screen before any further step is taken -- the
    second, independent safety layer. Returns one of:

    - ``"unsafe"`` -- a commit / confirm / purchase / combat prompt (by
      keyword ANYWHERE on screen, or by structural shape on the active
      prompt line), one of `classify`'s login / pause / game-select /
      char-create / cim gate anchors, or one of canon's escalate-only
      classes (`classify.NEVER_AUTO_ACTION_CLASSES`). Never enumerated,
      never pressed from -- this is what "back out without answering"
      means.
    - ``"menu"`` -- a genuine multi-option navigable menu: at least 2
      DIFFERENT qualifying option lines (the same threshold `classify`'s
      own `_is_menu` uses, and for the same reason: a single inline
      same-line confirmation like "Use (N)ew or (B)BS Name [B]?" must
      never count as navigable) AND an active prompt line that
      affirmatively looks like a menu-selection invitation.
    - ``"other"`` -- neither: ordinary content with no enumerable options
      (a dead-end leaf; nothing further to press).

    Classifying "menu" does NOT imply a bare Enter is safe to send on it:
    ``"bare_enter"`` is never in `SAFE_ALLOWLIST` regardless of this
    function's result. This function decides only whether the screen's
    LABELED options may be enumerated at all.

    A bare 2-line vertical confirm ("Proceed?\\n(Y)es\\n(N)o") has "(N)o"
    as its active prompt line -- an ordinary bracket-option line -- so
    `_is_menu_select_prompt` correctly still calls it menu-shaped, and no
    keyword/shape check above fires (no "y/n" slash, no trailing square
    bracket). That is closed here too: when `enumerate_options` finds
    EXACTLY 2 real (non-bare-Enter) options and EITHER classifies to a
    `STATE_CHANGING_KEYS` category, the whole screen is unsafe regardless
    of the other line's wording -- "Yes"/"No" closes on "Yes" alone via
    the "confirm" category, independent of any accept-word coincidence.
    This does NOT close every 2-option confirm (an "Accept"/"Decline" pair
    still classifies "menu" -- neither is a named deny word); that
    residual is covered by bare Enter never being emittable."""
    if any(p.search(full_text) for p in _UNSAFE_SCREEN_PATTERNS):
        return "unsafe"
    if _is_commit_shaped_prompt(prompt_line):
        return "unsafe"
    if classify_screen(full_text, prompt_line) in _NON_MENU_GATE_CLASSES:
        return "unsafe"
    options, is_menu = enumerate_options(full_text)
    if is_menu:
        real_options = [(key, label) for key, label in options if key != ""]
        if len(real_options) == 2 and any(
            classify_option_label(key, label) in STATE_CHANGING_KEYS for key, label in real_options
        ):
            return "unsafe"
    if is_menu and _is_menu_select_prompt(prompt_line):
        return "menu"
    return "other"


# -- option enumeration --------------------------------------------------------

# Re-authored here rather than imported from `classify`: that module's own
# bracket/dash patterns answer a boolean "is this a menu" question, while
# this module needs to ENUMERATE (key, label) pairs to feed the safety
# gate -- a different concern.
#
# The bracket pattern's tail is captured lazily up to the NEXT
# bracket-option on the same (possibly packed) line, or end of line, so
# "(B)uy Ship (V)iew Ship" enumerates as two options rather than one
# polluted by the other's text.
_BRACKET_OPTION_RE = re.compile(
    r"[(<]\s*([a-zA-Z!?])\s*[)>](.*?)(?=[(<]\s*[a-zA-Z!?]\s*[)>]|$)"
)
_DASH_OPTION_LINE_RE = re.compile(r"^\s*([a-zA-Z])\s*[-:]\s*(.+)$")


def enumerate_options(full_text):
    """Scan `full_text` for labeled menu options, bracket style ("(B)uy
    Ship" -- the hotkey letter is embedded INSIDE the label word) and dash
    style ("Q - Quit" -- hotkey and label are separate tokens). Returns
    ``(options, is_menu)``: `options` is an ordered list of ``(key,
    label)`` tuples plus a synthetic ``("", "<bare Enter>")`` entry iff
    `is_menu`; `is_menu` is True iff at least 2 DIFFERENT lines qualify.

    Bracket-style reconstruction: "(V)iew" is really the single word
    "View" with its hotkey highlighted -- the key letter is glued back
    onto the tail ONLY when there is no whitespace between the bracket and
    the tail. A bracket followed by a space ("(?) Help") is already a
    separate word and is never glued (gluing would corrupt "Help" into
    "?Help")."""
    qualifying_lines = 0
    options = []
    for line in full_text.splitlines():
        found = False
        for m in _BRACKET_OPTION_RE.finditer(line):
            key = m.group(1)
            tail_raw = m.group(2)
            tail = tail_raw.strip()
            glue = bool(tail_raw) and not tail_raw[:1].isspace() and key != "?"
            label = (key + tail) if glue else tail
            options.append((key, label))
            found = True
        dash_m = _DASH_OPTION_LINE_RE.match(line)
        if dash_m:
            options.append((dash_m.group(1), dash_m.group(2).strip()))
            found = True
        if found:
            qualifying_lines += 1
    is_menu = qualifying_lines >= 2
    if is_menu:
        options.append(("", "<bare Enter>"))
    return options, is_menu


# -- the per-option safety gate ------------------------------------------------

def classify_option_label(key, label):
    """Deny-by-default: returns a `SAFE_ALLOWLIST` category ONLY on an
    affirmative match. Anything else -- a named `STATE_CHANGING_KEYS`
    verb, a COMPOUND label naming more than one clause, or a
    plausible-looking but unrecognized label -- is ``"unknown"`` and is
    never emittable.

    Order matters: deny patterns are checked BEFORE the compound check,
    which is checked BEFORE safe ones, so a label containing both a nav
    word and a state-changing word is treated as unsafe, never the
    reverse.

    "Quit" is never a safe category: the replay-from-start traversal never
    needs to press quit to navigate at all.

    A bare Enter (``key == ""``) returns its own ``"bare_enter"`` category
    -- so the audit trail can still record that an Enter transition was
    discovered -- but ``"bare_enter"`` is likewise never in
    `SAFE_ALLOWLIST`: it is unconditionally recorded-not-pressed,
    regardless of how safe the screen it was discovered on looks.

    Pure and total: any label is accepted (``None`` normalizes to the
    empty string, which classifies ``"unknown"``), so no hostile or
    malformed label can raise out of the safety gate."""
    if key == "":
        return "bare_enter"
    norm = (label or "").strip().lower()
    if key == "?" and not norm:
        return "help"
    for category, pattern in _DENY_LABEL_PATTERNS.items():
        if pattern.search(norm):
            return category
    if _COMPOUND_LABEL_RE.search(norm):
        # More than one clause -- reject SAFE classification structurally
        # even when no individual clause hits a deny word.
        return "unknown"
    for category, pattern in _SAFE_LABEL_PATTERNS.items():
        if pattern.search(norm):
            return category
    return "unknown"


def emit_key_if_safe(session, from_node, key, label, category, emitted_keys, send_log, step_timeout=8.0):
    """THE single chokepoint every candidate crawl keystroke passes
    through -- the never-commit guarantee's audit target. Every candidate,
    safe or not, gets exactly one `send_log` entry; ``session.send()`` (via
    ``settle.send_and_confirm``) is reached ONLY when the category the
    chokepoint itself resolves is in `SAFE_ALLOWLIST`. There is no other
    branch in this function, and no other call site in the whole ``menu``
    package, that can reach it.

    **Self-verifying, deliberately stricter than the archived shape.** The
    `category` argument is treated as the caller's *claim*, not as
    authority: the chokepoint re-derives the category from ``(key,
    label)`` itself and emits only when the resolved category both matches
    the claim and is in the allowlist. A caller that computes a category
    wrongly, passes a stale one, or forges a safe-looking one for a
    state-changing label therefore cannot open the gate -- the guarantee
    is structural rather than a convention every call site must remember.
    (`classify_option_label` is pure, so on every honest path the resolved
    and claimed categories are identical and this costs nothing.)

    Returns ``(emitted, text, prompt)``. ``emitted=False`` always pairs
    with ``text=prompt=None`` (nothing was sent, nothing new to read).
    ``emitted=True, text=None`` means the key WAS sent but never
    positively confirmed settled -- the caller must treat the resulting
    screen as untrustworthy and read nothing further from it, exactly like
    an ordinary unsafe screen."""
    resolved = classify_option_label(key, label)
    emitted = resolved == category and resolved in SAFE_ALLOWLIST
    send_log.append({
        "from_node": from_node,
        "key": key,
        "label": label,
        # The RESOLVED category is the audit record; the caller's claim is
        # recorded beside it so a divergence is visible rather than lost.
        "category": resolved,
        "claimed_category": category,
        "emitted": emitted,
    })
    if not emitted:
        return False, None, None

    # A menu single-key selection sent WITH its usual trailing CRLF can
    # have that Enter consumed by the very next prompt, so never append
    # one for a real key. Bare Enter (key == "") is the one case that
    # would legitimately need `enter` -- but "bare_enter" is never in
    # SAFE_ALLOWLIST, so `key == ""` cannot reach this line at all (the
    # `if not emitted` return always fires first). Kept for correctness if
    # this function is ever called directly.
    enter = key == ""
    _reason, _elapsed, confirmed = send_and_confirm_for(
        session, key, profile="stable_idle", enter=enter, secret=False, timeout_s=step_timeout,
    )
    emitted_keys.append(resolved)
    if not confirmed:
        return True, None, None

    rows = session.render()
    text = session.render_text(rows)
    prompt = rows[-1].strip() if rows else ""
    return True, text, prompt


# -- signature / labeling ------------------------------------------------------

def _first_line(full_text):
    for line in full_text.splitlines():
        if line.strip():
            return line.strip()[:80]
    return None


# -- traversal ------------------------------------------------------------------

def _open_and_settle(session_factory, step_timeout):
    session = session_factory()
    wait_until_settled(session, timeout_s=step_timeout)
    rows = session.render()
    text = session.render_text(rows)
    prompt = rows[-1].strip() if rows else ""
    return session, text, prompt


def _replay(session_factory, steps, emitted_keys, send_log, step_timeout):
    """Reach a previously-discovered frontier by replaying its
    already-proven-safe ``(key, label, category)`` path from a FRESH
    session positioned at the world's start context -- see the module
    docstring's Traversal section for why this is what lets the crawler
    need no "cancel"/"undo" action at all. Returns ``(session, text,
    prompt)``, or ``None`` if the replay itself hit an unsafe/unconfirmed
    screen partway (defensive -- a deterministic fixture menu should never
    do this, but a live game might)."""
    session, text, prompt = _open_and_settle(session_factory, step_timeout)
    for key, label, category in steps:
        if screen_state(text, prompt) != "menu":
            return None
        from_node = menu_signature(text)
        emitted, new_text, new_prompt = emit_key_if_safe(
            session, from_node, key, label, category, emitted_keys, send_log, step_timeout
        )
        if not emitted or new_text is None:
            return None
        text, prompt = new_text, new_prompt
    return session, text, prompt


def _edge_kind_for(category):
    """Canon's three-kind fold. `nav` for literal menu navigation, `info`
    for reading content without moving, `action` for everything else --
    every recorded-not-pressed option regardless of whether its category
    is a named state-changing verb or merely unrecognized."""
    if category in _NAV_CATEGORIES:
        return "nav"
    if category in _INFO_CATEGORIES:
        return "info"
    return "action"


def crawl_menus(session_factory, path, max_nodes=_DEFAULT_MAX_NODES, step_timeout=8.0,
                record_status=True):
    """Crawl the menu graph reachable from ``session_factory()``'s start
    context via BFS-by-replay, writing every discovered node/edge into the
    ``menu.knowledge`` store at `path` (an already-resolved, world-keyed
    path -- resolving world identity is the caller's job).

    `session_factory` is a zero-arg callable returning a FRESH session
    already sitting at the world's stable start context every time it is
    called.

    Returns ``{"nodes_visited": int, "truncated": bool,
    "frontier_remaining": int, "emitted_keys": [...], "send_log": [...]}``.
    `emitted_keys` is the flat list of `SAFE_ALLOWLIST` category strings
    this crawl actually sent (never a raw keystroke, never a
    `STATE_CHANGING_KEYS` category); `send_log` is the richer
    per-candidate audit trail -- every option this crawl ever discovered,
    safe or not, with its resolved category and whether it was emitted.

    `truncated` is True when the `max_nodes` rail stopped the walk with
    frontier nodes still queued: the resulting map is a genuine partial.
    Unless `record_status` is False, the outcome is stamped into the store
    (``"complete"`` or ``"truncated"``) so a consumer can never mistake a
    partial map for a finished one. An abort or a structural failure
    unwinds out of this function without a stamp -- stamping those is the
    driver's job, since only it sees them."""
    emitted_keys = []
    send_log = []
    seen = set()
    queue = deque()

    session, text, prompt = _open_and_settle(session_factory, step_timeout)
    root_sig = menu_signature(text)
    upsert_menu_node(path, root_sig, label=_first_line(text))
    seen.add(root_sig)
    queue.append((root_sig, []))

    nodes_visited = 0
    while queue and nodes_visited < max_nodes:
        sig, steps = queue.popleft()
        nodes_visited += 1

        reached = _replay(session_factory, steps, emitted_keys, send_log, step_timeout)
        if reached is None:
            continue
        session, text, prompt = reached

        if screen_state(text, prompt) != "menu":
            # BACK OUT: this frontier is either a genuine commit / confirm
            # / combat / login gate, or simply content with no enumerable
            # options -- either way NOTHING is ever pressed from it. The
            # node itself was already upserted by whichever edge
            # discovered it (or, for the root, just above): recording that
            # it exists is still valuable for a future navigator, it is
            # just never explored past.
            continue

        options, _is_menu = enumerate_options(text)
        for key, label in options:
            category = classify_option_label(key, label)
            emitted, new_text, new_prompt = emit_key_if_safe(
                session, sig, key, label, category, emitted_keys, send_log, step_timeout
            )
            if not emitted:
                upsert_menu_edge(
                    path, sig, key or ENTER_EDGE_KEY, UNEXPLORED_TARGET,
                    kind="action", desc=f"{category}: {label}",
                )
                continue
            if new_text is None:
                # Sent, but never positively confirmed settled -- the
                # resulting screen is untrustworthy; nothing safe to read,
                # nothing recorded, nothing queued.
                continue

            new_sig = menu_signature(new_text)
            upsert_menu_node(path, new_sig, label=_first_line(new_text))
            upsert_menu_edge(
                path, sig, key or ENTER_EDGE_KEY, new_sig,
                kind=_edge_kind_for(category), desc=label,
            )
            if new_sig not in seen:
                seen.add(new_sig)
                queue.append((new_sig, steps + [(key, label, category)]))

            # `session` has moved past `sig` -- re-anchor before probing
            # the NEXT sibling option at `sig`.
            reached = _replay(session_factory, steps, emitted_keys, send_log, step_timeout)
            if reached is None:
                break  # can't safely get back to `sig` -- stop probing siblings here
            session, text, prompt = reached

    truncated = bool(queue)
    if record_status:
        record_crawl_status(
            path,
            status="truncated" if truncated else "complete",
            reason="max_nodes rail reached with frontier remaining" if truncated else None,
            nodes_visited=nodes_visited,
            frontier_remaining=len(queue),
        )

    return {
        "nodes_visited": nodes_visited,
        "truncated": truncated,
        "frontier_remaining": len(queue),
        "emitted_keys": list(emitted_keys),
        "send_log": list(send_log),
    }
