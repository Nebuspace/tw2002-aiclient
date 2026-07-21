"""Menu Crawler -- TW-26 (game_knowledge.py's own module docstring): a
careful, READ-ONLY, AI-driven crawl that enumerates a world's per-game
MENU-MAP into the `game_knowledge` store (`upsert_menu_node`/
`upsert_menu_edge`), for a future TW-28 deterministic-nav pathfinder to
read back.

**THE NEVER-COMMIT GUARANTEE LIVES OUTSIDE THIS MODULE (2026-07-19,
operator-ratified frame change, THIRD re-audit convergence).** A live crawl
runs under the **A+C protocol**: a disposable, zero-credit/zero-asset
character plus a hub-supervisor able to abort mid-crawl -- THAT is what
bounds the worst case to nothing, not this module's own lexical
classification. Everything below (`classify_option_label`, `screen_state`,
`SAFE_ALLOWLIST`) is **best-effort defense-in-depth**: it rejects the
COMMON, recognizable SHAPES of a commit/confirm/purchase/state-changing
action to minimize how often the crawl even brushes up against one --
it is explicitly **not**, and cannot be, a completeness guarantee. An
unbounded natural-language label space can't be lexically classified
with proven completeness; chasing it (an ever-expanding denylist,
prefix-affix handling for every possible re-/over-/mis- form) was
deliberately abandoned as the wrong target once the A+C protocol made it
unnecessary. **Accepted residual, by design, not oversight (2026-07-19,
FOURTH re-audit round, "no round 5" convergence pass):**
(a) **prefix-affixed forms** of a deny verb ("Repurchase" dodging "buy"
    the same way a re-/over-/mis- prefix always would);
(b) **agent-nouns and derived/action-nouns that share a verb's stem**
    ("Buyer"/"Buyout", "Acquirer", "Vendor", "Launcher", "Ejection",
    "Confirmation", "Movement", "Deployment", "Redemption",
    "Forfeiture") -- `_DENY_LABEL_PATTERNS` is deliberately bounded to
    ACTIVE VERB CONJUGATIONS ONLY (bare / -s / -ed / -ing / genuine
    irregulars), never a bare prefix, precisely so these read as
    ordinary informational nouns instead of state-changing verbs;
(c) **the "board" homograph** -- the bare word "Board" is identically
    the common UI noun (a Bounty/Notice Board) and the rare piracy verb
    ("board a ship"); denying only `"boarding"` (the unambiguous active
    verb form) accepts that the bare-verb use case leaks through, since
    re-adding bare `\bboard\b` would re-introduce the noun false
    positive, and the noun is far more common than the verb in ordinary
    play;
(d) a genuinely **novel/synonym/mislabeled** commit action sharing no
    vocabulary with anything named below at all.
All four are bounded to zero real-world impact by the A+C protocol
(disposable zero-asset character, hub-supervised abort) -- none of them
is a completeness gap this module is trying (or needs) to close on its
own. Every fix in this file closes a
PROVEN gap or a common, expected form; none of them, individually or
together, is claimed to close the class -- see each Finding/Fix's own
note for exactly what it closes and what it deliberately doesn't.

Within that frame, the chokepoint discipline below is still real and
still worth keeping tight: every keystroke this module could possibly
send to a live session passes through exactly one chokepoint,
`emit_key_if_safe()` -- there is no other code path in this module that
ever calls `settle.send_and_confirm()` (the only place a keystroke
actually reaches `session.send()`). That chokepoint is **deny-by-default**:
a key is emittable ONLY if `classify_option_label()` affirmatively
matches one of the `SAFE_ALLOWLIST` categories (view / help / list /
display / examine / back / previous). "Quit" is deliberately NOT on this
list (2026-07-19 safety fix, TW-26 re-audit -- see `classify_option_
label`'s own docstring): the BFS-via-replay traversal never needs to
press quit/back to navigate at all (it replays from start), so a "quit"
option -- an ordinary parent-menu quit or a genuine game/session exit
alike -- is always recorded-not-pressed. **A bare Enter is likewise
NEVER emitted** (2026-07-19 hardening pass, second re-audit round -- see
`SAFE_ALLOWLIST` below): a synthetic bare-Enter option is still
discovered on every genuine menu, but is always recorded-not-pressed
rather than sent, the same as any other unrecognized/denied option.
Anything else -- a named state-changing verb (`STATE_CHANGING_KEYS`:
buy/sell/purchase/attack/deploy/genesis/move/jump/tow/land/take/confirm,
plus a broader belt-and-suspenders vocabulary besides), a COMPOUND label
naming more than one action, or any other UNRECOGNIZED/ambiguous label
-- is categorized "unknown"/deny and is **never** passed to
`send_and_confirm`; it is only ever recorded as an unexplored edge via
`upsert_menu_edge` (never pressed to find out where it leads).

**Two layers of best-effort defense-in-depth, not the guarantee itself
(see above):**

1. **Per-OPTION label gate** (`classify_option_label`) -- decides
   whether a single discovered `(key, label)` pair on a menu screen is
   safe to press, from its rendered TEXT LABEL. Never from the raw
   keystroke alone: the same physical key means different things on
   different screens (`B` is "Buy" on one menu, "Back" on another), so
   the label is the only thing this can safely be judged against.
2. **Per-SCREEN safety classification** (`screen_state`) -- decides,
   BEFORE any option on the CURRENT screen is even enumerated, whether
   the screen itself is a commit/confirm/purchase/combat gate (or one of
   `classify.py`'s own login/pause/game-select gate anchors). A screen
   found unsafe here is never enumerated at all -- not even its options'
   labels are read -- so a mislabeled or unexpected destination (a SAFE
   key that happens to lead somewhere it shouldn't) can never be probed
   further, regardless of what layer 1 would have said about its
   options. This is what "BACK OUT to a safe menu without answering"
   means in practice: the crawl simply never sends anything from an
   unsafe frontier and moves on to the next already-queued one.

   **2026-07-19 safety fix (TW-26 re-audit, mack + cipher):** the
   original gate was a pure whole-screen KEYWORD denylist with no notion
   of which line is the actually-live question, so ordinary menu chrome
   sharing the screen with a real commit prompt ("(V)iew Ship Status" /
   "(H)elp" alongside "Proceed? [Yes]") made the whole screen enumerate
   as an ordinary menu. `screen_state` now ALSO checks the ACTIVE prompt
   line (the caller's own `prompt_line`, not the whole screen) for a
   commit SHAPE independent of wording -- a trailing square-bracket
   default-answer token ("...? [Y]:", "...[Yes]") or a free-input
   solicitation ("Enter ... :", "How many ... :") -- and a screen is only
   ever crawlable ("menu") when its active prompt ALSO affirmatively
   looks like a menu-selection invitation (see `_is_menu_select_prompt`).
   The old keyword scan stays as an additional, not sole, layer.
3. **No bare Enter, ever** (2026-07-19 hardening pass, second re-audit
   round) -- a residual breach even the two layers above don't close on
   their own: a bare 2-line vertical confirm like `"(Y)es\n(N)o"` (or
   `"(A)ccept\n(D)ecline"`, `"(O)k\n(C)ancel"`) has its LAST line be an
   ordinary bracket-option line ("(N)o"), which `_is_menu_select_prompt`
   affirmatively -- and correctly, by its own narrow rule -- recognizes
   as a menu-selection shape, and neither `_UNSAFE_SCREEN_PATTERNS` nor
   `_is_commit_shaped_prompt` fire (no "y/n" slash, no "confirm"
   keyword, no trailing SQUARE bracket). A "deny bare_enter only when a
   deny-labeled option is also present" patch would NOT close this
   either -- "Accept"/"Decline"/"Ok"/"Cancel" all classify "unknown",
   not a named deny word, so they would still dodge such a check. Rather
   than chase this with another shape heuristic, `SAFE_ALLOWLIST`
   excludes `"bare_enter"` outright: the crawl's real transitions are
   all discoverable via a menu's LABELED safe options anyway, so Enter's
   marginal coverage is ~nil against a permanent, un-closeable-by-
   heuristic risk. The synthetic bare-Enter option is still discovered
   (so the graph still notes an Enter transition exists) but is now
   always recorded-not-pressed, via the exact same generic "not emitted"
   path every deny/unknown option already uses.

**Traversal: BFS via replay-from-start, not stateful backtracking.**
`crawl_menus()` never remembers "how do I get back" from wherever it
last was -- it only ever remembers, per discovered node, the ORDERED
list of already-proven-safe `(key, label, category)` steps that reached
it from the world's start context. To probe node N's next untried
option, it asks `session_factory()` for a fresh session (already sitting
at that start context) and REPLAYS N's safe-step path via the exact same
`emit_key_if_safe()` chokepoint used for original discovery, one hop at
a time, re-checking `screen_state()` at every hop. This is not merely a
testing convenience: it is what lets the crawler have zero notion of
"cancel this confirm prompt" or "undo my last keystroke" at all -- since
every step on every replayed path was ALREADY proven side-effect-free by
the same gate, replaying it is exactly as safe as the original traversal,
and a dead-end (an unsafe frontier) is simply never replayed past. A live
daemon integration (a separate future lane, not this one) will need a
`session_factory` that can genuinely re-establish that stable start
context (e.g. re-entering the same top-level menu command) rather than
literally rewinding one persistent TCP connection -- see this module's
Concerns in the TW-26 handoff report.

**Schema note (TW-25's `game_knowledge.MENU_EDGE_KINDS` is
`("nav", "info", "action")` -- no `"unknown"` kind exists):** every
recorded-not-pressed edge is written with `kind="action"` regardless of
whether its category is a named `STATE_CHANGING_KEYS` verb or merely
unrecognized -- `upsert_menu_edge` raises `GameKnowledgeError` on any
other kind string. The category itself (never lost) is folded into the
edge's `desc` field (`"<category>: <label>"`) so "buy: Buy New Ship" and
"unknown: K----" stay distinguishable in the data even though they share
one `kind`. Safe/emitted edges use the schema's other two kinds more
precisely: `nav` for back/previous (literal menu navigation) and `info`
for view/help/list/display/examine (reading content without "moving").
("Quit" and "bare_enter" are no longer emittable at all as of the
2026-07-19 safety fixes -- see the module's safety-layer section above
-- so neither ever reaches this edge_kind branch; both are always
recorded via the `kind="action"` unexplored-edge path instead.)
"""

import re
from collections import deque

from .classify import classify_screen
from .game_knowledge import upsert_menu_edge, upsert_menu_node
from .menu_sig import menu_signature
from .settle import send_and_confirm, wait_until_settled

# -- the safety vocabulary ----------------------------------------------------
# CATEGORIES, not raw keystrokes: the same physical key is not stable
# across menus (see module docstring), so every set below names the
# semantic label-category a discovered option is classified into, and
# `emitted_keys`/`send_log` record that category, never a bare letter.

_SAFE_LABEL_PATTERNS = {
    "view": re.compile(r"\bview\b", re.I),
    "help": re.compile(r"\bhelp\b", re.I),
    # Fix B.5 (2026-07-19 convergence pass, mack): the round-3 "listing"
    # DENY word was removed for colliding with THIS category's own
    # gerund ("Port Listing"/"Listing of Ships" wrongly denied) -- but
    # `\blist\b`'s own trailing boundary doesn't match "listing" either
    # (list+ing, boundary fails mid-word), so removing the deny word
    # alone would leave those labels "unknown", not genuinely restore
    # the coverage. Added `\blisting\b` here explicitly (not a blanket
    # `\blist` prefix -- that would also swallow "Listen"/"Listening",
    # an unrelated word) so "Port Listing" affirmatively classifies
    # "list" (SAFE), not merely "no longer denied".
    "list": re.compile(r"\blist\b|\blisting\b", re.I),
    "display": re.compile(r"\bdisplay\b", re.I),
    "examine": re.compile(r"\bexamine\b|\binspect\b", re.I),
    "back": re.compile(r"\bback\b", re.I),
    "previous": re.compile(r"\bprevious\b|\bprev\b", re.I),
    # NOTE: no "quit" entry -- 2026-07-19 safety fix (TW-26 re-audit,
    # Finding 4). A bare "(Q)uit" ends the live session outright, and
    # the BFS-via-replay traversal never needs to press quit/back to
    # navigate in the first place -- it always replays each frontier's
    # safe-step path from a fresh start (see module docstring's
    # Traversal section) -- so ANY "quit"-labeled option, an ordinary
    # "back to parent menu" quit or a genuine game/session exit alike,
    # is simply recorded-not-pressed, same as any other unrecognized
    # label. There is deliberately no carve-out regex distinguishing the
    # two meanings anymore (see `classify_option_label`'s own docstring
    # for why one is no longer needed).
}

# 2026-07-19 safety fix, THIRD re-audit round (cipher): every pattern
# below used to be `\bWORD\b` -- a TRAILING word boundary that a glued
# suffix defeats outright (cipher proved "Buyout" dodges `\bbuy\b`,
# "Ejection" dodges `\beject\b`, "Payment" dodges `\bpay\b` -- 31/31
# deny words, end-to-end: "(P)revious Owner Buyout" -> "previous" (SAFE)
# -> emitted). Fix (round 3): drop the TRAILING boundary -- a plain
# BLANKET prefix match (`\bWORD`, no bound at all past the stem) for
# most words, with a TARGETED suffix list (`\bWORD(s|ed|ing|...)?\b`)
# reserved only for short/common stems where blanket over-matched an
# unrelated safe word ("mine"->"mineral", "tow"->"towel").
#
# CONVERGENCE PASS (2026-07-19, FOURTH re-audit round, mack + cipher --
# "no round 5"): that round-3 BLANKET default itself was swept for a
# COMPLETE class of false positives it created: informational labels
# naming an AGENT-NOUN
# ("Buyer", "Acquirer", "Vendor", "Launcher"), a DERIVED/ACTION-NOUN
# sharing the verb's stem ("Buyout", "Ejection", "Confirmation",
# "Movement", "Deployment", "Redemption", "Forfeiture"), or a completely
# UNRELATED common English word that merely starts with the same letters
# ("mine"->"mineral", "steal"->"stealth", "rent"->"rental"/"renter"). The
# module docstring's residual note (see above) now explicitly accepts
# ALL of these as residual, not just prefix-affixed forms ("Repurchase")
# -- **every pattern below is bounded to ACTIVE VERB CONJUGATIONS ONLY**
# (bare form / -s / -ed / -ing / relevant irregulars), never a bare
# prefix and never an agent-/action-noun suffix. This DELIBERATELY
# REVERSES several round-3 catches (bare "Buyout"/"Ejection"/
# "Confirmation" no longer deny) -- see `test_round5_accepted_residual_
# action_and_agent_noun_forms` in the test suite for the explicit
# before/after documentation of that reversal. Irregular forms sharing
# no letter-stem with their verb at all (bought/sold/took/stole/stolen/
# paid/sent/spent/laden) are unaffected -- they were never blanket
# prefixes to begin with, and stay as their own bounded alternatives.
_DENY_LABEL_PATTERNS = {
    "buy": re.compile(r"\bbuy(s|ing)?\b|\bbought\b", re.I),  # NOT blanket -- "Buyer"/"Buyout"
    "sell": re.compile(r"\bsell(s|ing)?\b|\bsold\b", re.I),  # NOT blanket -- "Seller"
    "purchase": re.compile(r"\bpurchase(s|d)?\b|\bpurchasing\b", re.I),  # NOT blanket -- "Purchaser"
    # "fire"/"fight" were already targeted (round 3/4); "attack" itself
    # is narrowed here too -- NOT blanket, "Attacker" is an agent-noun.
    "attack": re.compile(r"\battack(s|ed|ing)?\b|\bfire(s|d)?\b|\bfiring\b|\bfight(s|ing)?\b", re.I),
    "deploy": re.compile(r"\bdeploy(s|ed|ing)?\b", re.I),  # NOT blanket -- "Deployment"
    "genesis": re.compile(r"\bgenesis", re.I),  # no common derived form; effectively a proper noun here
    # "moving" needs its own alternative (silent-e drop, same pattern as
    # "mine"/"mining"); "warp" narrowed for consistency though no strong
    # collision risk was found for it specifically.
    "move": re.compile(r"\bmove(s|d)?\b|\bmoving\b|\bwarp(s|ed|ing)?\b", re.I),  # NOT blanket -- "Movement"
    "jump": re.compile(r"\bjump(s|ed|ing)?\b", re.I),  # NOT blanket -- "Jumper"
    "tow": re.compile(r"\btow(s|ed|ing)?\b", re.I),  # NOT blanket -- "towel"
    "land": re.compile(r"\bland(s|ed|ing)?\b", re.I),  # NOT blanket -- "landscape"
    # "taking" needs its own alternative (silent-e drop); "n" covers
    # "taken" (a regular concatenation, not truly irregular -- only
    # "took" shares no stem at all). "claim" narrowed too -- NOT
    # blanket, "Claimant" is an agent-noun.
    "take": re.compile(r"\btake(s|n)?\b|\btaking\b|\btook\b|\bclaim(s|ed|ing)?\b", re.I),
    # Covers both an explicit "Confirm" option AND a bare "Yes"/"Y" label
    # ever reachable via the per-option scan (belt-and-braces: the
    # screen-level gate in `screen_state()` should already have kept the
    # crawler from ever enumerating a confirm prompt's options at all --
    # this is the second, independent layer, not the only one). "yes"
    # KEEPS its trailing boundary -- "yesterday" would otherwise dodge.
    # "confirm" itself is narrowed -- NOT blanket, "Confirmation" is now
    # accepted residual (see the class-wide note above this dict).
    "confirm": re.compile(r"\bconfirm(s|ed|ing)?\b|\byes\b", re.I),
    # 2026-07-19 safety fix (TW-26 re-audit, Finding 3) -- a broader
    # belt-and-suspenders vocabulary of state-changing verbs, on top of
    # Finding 2's structural compound-label check below (a label naming
    # one of these ALONGSIDE an otherwise-safe clause is denied either
    # way, since deny is checked first regardless).
    "acquire": re.compile(r"\bacquire(s|d)?\b|\bacquiring\b", re.I),  # NOT blanket -- "Acquirer"
    "requisition": re.compile(r"\brequisition(s|ed|ing)?\b", re.I),
    "order": re.compile(r"\border(s|ed|ing)?\b", re.I),  # NOT blanket -- "orderly"
    # Fix B.2 (2026-07-19 THIRD re-audit round, false positive): a
    # blanket prefix on "trade" catches "Trader(s)" -- an agent-noun /
    # guild role ("View Traders Guild Info"), not a state-changing verb.
    # Narrowed to actual verb forms; "trading" needs its own alternative
    # (silent-e drop, same pattern as "mine"/"mining" and "fire"/"firing").
    "trade": re.compile(r"\btrade(s|d)?\b|\btrading\b", re.I),  # NOT blanket -- "Trader"
    "dock": re.compile(r"\bdock(s|ed|ing)?\b", re.I),  # NOT blanket -- "docket"
    "eject": re.compile(r"\beject(s|ed|ing)?\b", re.I),  # NOT blanket -- "Ejection" (accepted residual)
    "drop": re.compile(r"\bdrop(s|ped|ping)?\b", re.I),  # NOT blanket -- "dropdown"
    # Doubled consonant before -ed/-ing (transferred/transferring),
    # standard English spelling -- NOT blanket, "Transferor"/"Transferee"
    # are agent-nouns.
    "transfer": re.compile(r"\btransfer(s|red|ring)?\b", re.I),
    "upgrade": re.compile(r"\bupgrade(s|d)?\b|\bupgrading\b", re.I),  # NOT blanket -- "upgradeable"
    "repair": re.compile(r"\brepair(s|ed|ing)?\b", re.I),  # NOT blanket -- "Repairman"/"Repairer"
    "refuel": re.compile(r"\brefuel(s|ed|ing)?\b", re.I),
    # Fix 1 confirmed FP (2026-07-19 FOURTH re-audit round, mack):
    # "Launcher" (an instrument-noun, e.g. torpedo launcher hardware) --
    # NOT blanket.
    "launch": re.compile(r"\blaunch(s|ed|ing)?\b", re.I),
    "abandon": re.compile(r"\babandon(s|ed|ing)?\b", re.I),  # NOT blanket -- "Abandonment"
    "jettison": re.compile(r"\bjettison(s|ed|ing)?\b", re.I),
    "pay": re.compile(r"\bpay(s|ing|ment)?\b|\bpaid\b", re.I),  # NOT blanket -- "payload"
    "invest": re.compile(r"\binvest(s|ed|ing|ment)?\b", re.I),  # NOT blanket -- "investigate"
    "bribe": re.compile(r"\bbribe(s|d)?\b|\bbribing\b", re.I),  # NOT blanket -- "bribery"
    # "Stealth" is a VERY common word in a space game (stealth systems/
    # mode) -- NOT blanket; the old blanket `\bsteal` would have wrongly
    # denied it.
    "steal": re.compile(r"\bsteal(s|ing)?\b|\bstole\b|\bstolen\b", re.I),
    # Fix B.4 (2026-07-19 THIRD re-audit round, false positive -- your
    # call, per the dispatch): "Board" as a bare word is FAR more often
    # the common UI noun ("Bounty Board", "Notice Board") than the rare
    # piracy verb ("board a ship"). Narrowed to the active "-ing" form
    # only, so the noun stays safe while the verb is still caught (and
    # still audit-labeled "board:" rather than collapsing to "unknown")
    # when it IS actually used as a verb. FOURTH re-audit round
    # (convergence pass): CONFIRMED to stay this way -- re-adding bare
    # `\bboard\b` re-introduces the "Bounty Board" FP, since the noun
    # and the rare verb are the identical bare word (a homograph). The
    # niche bare-verb leak is accepted residual under the A+C protocol.
    "board": re.compile(r"\bboarding\b", re.I),
    "ram": re.compile(r"\bram(s|med|ming)?\b", re.I),  # NOT blanket -- "ramble"
    # Fix B.3 (2026-07-19 THIRD re-audit round, false positive): a
    # blanket prefix on "cloak" catches the ordinary word "Cloakroom".
    # Narrowed to a targeted suffix list, same discipline as the other
    # short/common stems above.
    "cloak": re.compile(r"\bcloak(s|ed|ing)?\b", re.I),  # NOT blanket -- "Cloakroom"
    # "mining" needs its own alternative (silent-e drop: mine -> mining,
    # not "mineing") on top of the targeted suffix list -- NOT blanket,
    # "mineral" is the textbook over-match risk here.
    "mine": re.compile(r"\bmine(s|d)?\b|\bmining\b", re.I),
    # 2026-07-19 safety fix, THIRD re-audit round (Fix 2 -- a KNOWN
    # vocabulary gap, explicitly not claimed complete; see the module's
    # own escalation on denylist provability): trade/commerce/wager verbs
    # absent in any form until now.
    "send": re.compile(r"\bsend(s|ing)?\b|\bsent\b", re.I),  # irregular past tense
    "load": re.compile(r"\bload(s|ed|ing)?\b|\bladen\b", re.I),  # irregular participle
    # Fix 1 confirmed FP (2026-07-19 FOURTH re-audit round, cipher):
    # "sale" is fundamentally a NOUN in English (there is no verb "to
    # sale" -- the verb is "sell", already its own category above), so
    # unlike the true verbs elsewhere in this dict, even the REGULAR
    # plural "Sales" is the collision to avoid ("Sales Tax", "Sales
    # History"), not a derived/agent form. Bounded on BOTH sides with NO
    # suffix at all -- deliberately the one exception to this dict's
    # "verb-conjugation suffixes" pattern, because "sale" was never
    # conjugating a verb in the first place. Still catches the bare
    # singular "(item) For Sale".
    "sale": re.compile(r"\bsale\b", re.I),
    # NOTE: no "listing" entry -- Fix B.5 (2026-07-19, mack's own-goal
    # catch): "listing" collides with the SAFE "list" category's own
    # gerund ("Port Listing"/"Listing of Ships" wrongly denied). "list"
    # as ordinary navigation is far more common than "auction listing"
    # as a state-changing action -- removed; "auction" alone still
    # catches the auction-specific case ("Start an Auction"). See
    # `_SAFE_LABEL_PATTERNS["list"]`'s own comment -- removing this deny
    # word alone wasn't sufficient; that pattern was ALSO widened.
    "auction": re.compile(r"\bauction(s|ed|ing)?\b", re.I),  # NOT blanket -- "Auctioneer"
    "barter": re.compile(r"\bbarter(s|ed|ing)?\b", re.I),
    "lease": re.compile(r"\blease(s|d)?\b|\bleasing\b", re.I),  # NOT blanket -- "Lessee"/"Lessor"
    "rent": re.compile(r"\brent(s|ed|ing)?\b", re.I),  # NOT blanket -- "Renter"/"Rental"
    "vend": re.compile(r"\bvend(s|ed|ing)?\b", re.I),  # NOT blanket -- "Vendor" (Fix 1 confirmed FP)
    "payoff": re.compile(r"\bpayoffs?\b", re.I),
    "wager": re.compile(r"\bwager(s|ed|ing)?\b", re.I),
    "bet": re.compile(r"\bbet(s|ting)?\b", re.I),  # NOT blanket -- "better"/"between"
    "gamble": re.compile(r"\bgamble(s|d)?\b|\bgambling\b", re.I),  # NOT blanket -- "Gambler"
    "ransom": re.compile(r"\bransom(s|ed|ing)?\b", re.I),
    "donate": re.compile(r"\bdonate(s|d)?\b|\bdonating\b", re.I),  # NOT blanket -- "Donation" (accepted residual)
    # Like "sale" above, "gift" as a common English NOUN ("View
    # Available Gifts") is the collision to avoid more than any derived
    # verb form -- bounded with no suffix, own judgment call (not one of
    # the 4 explicitly confirmed FPs, but the identical noun-not-verb
    # reasoning applies). Bare imperative "Gift a Torpedo" still matches.
    "gift": re.compile(r"\bgift\b", re.I),
    "spend": re.compile(r"\bspend(s|ing)?\b|\bspent\b", re.I),  # NOT blanket -- "Spender" (Fix 1 confirmed FP)
    "redeem": re.compile(r"\bredeem(s|ed|ing)?\b", re.I),  # NOT blanket -- "Redemption" (accepted residual)
    "forfeit": re.compile(r"\bforfeit(s|ed|ing)?\b", re.I),  # NOT blanket -- "Forfeiture" (accepted residual)
    "surrender": re.compile(r"\bsurrender(s|ed|ing)?\b", re.I),
    # Optional additions (2026-07-19 THIRD re-audit round, cipher --
    # on-domain for a player_bank: withdraw/deposit; central to any
    # confirm flow: commit/accept), added only after collision-checking
    # each against the 7 SAFE_LABEL_PATTERNS categories and common
    # English derived forms:
    # Fix 2 (FOURTH re-audit round, cipher): dropped "al" -- "Withdrawal"
    # is always a noun (a completed/historical transaction record), zero
    # commit-coverage upside from catching it.
    "withdraw": re.compile(r"\bwithdraw(s|n|ing)?\b", re.I),
    "deposit": re.compile(r"\bdeposit(s|ed|ing)?\b", re.I),  # kept as-is -- real commit usage, FP unlikely
    # Fix 3 (FOURTH re-audit round): dropped "ted" and "ment" -- neither
    # "Committed" nor "Commitment" is caught anymore (both read as
    # adjectival/informational -- "Committed Resources", "View
    # Commitment Report" -- far more often than an active commit
    # action); bare "Commit"/"Commits"/"Committing" still catches the
    # verb. NOT blanket -- "committee" was already excluded before this
    # trim and remains excluded.
    "commit": re.compile(r"\bcommit(s|ting)?\b", re.I),
    # Fix 3 (FOURTH re-audit round): dropped "ed" -- "Accepted" reads as
    # an adjective far more often than an active accept action ("Accepted
    # Applications" is an informational status list); bare "Accept"/
    # "Accepts"/"Accepting" still catches the verb (keeps the Accept/
    # Decline screen-level closure -- see `screen_state`'s Fix 3). NOT
    # blanket -- "acceptable" was already excluded before this trim.
    "accept": re.compile(r"\baccept(s|ing)?\b", re.I),
}

# A label naming MORE than one action/clause -- Finding 2 (2026-07-19
# re-audit): "View & Repair Ship" reads safe by its FIRST clause alone,
# but pressing it commits to whatever its second clause does too. This
# is checked STRUCTURALLY in `classify_option_label`, independent of
# `_DENY_LABEL_PATTERNS`'s vocabulary -- a compound label whose second
# clause dodges every deny word above (e.g. "View and Examine Log") is
# still never classified safe; a clean, single-clause label ("Display
# Combat Rating") is unaffected. THIRD re-audit round (2026-07-19):
# broadened past "and"/"then"/"&"/","/"/"/"+" to ALSO catch "as well as"/
# "along with" -- lower-false-positive connector phrases. "plus" and
# "with" were tried and REVERTED (Fix B.6, convergence pass, mack): both
# over-reject ordinary single-clause labels ("Help with Navigation" ->
# wrongly "unknown") far more often than they catch a genuine compound,
# and completeness is no longer the goal (see module docstring) -- a
# false positive here actively cripples legitimate crawl coverage,
# which now outweighs the marginal compound-detection gain.
_COMPOUND_LABEL_RE = re.compile(
    r"\b(?:and|then|as\s+well\s+as|along\s+with)\b|[&,/+]", re.I
)

# NOTE: "bare_enter" is deliberately NOT unioned in here anymore --
# 2026-07-19 hardening pass (second re-audit round, safety layer 3 in
# the module docstring above). A bare 2-line vertical confirm like
# "(Y)es\n(N)o" (or "(A)ccept\n(D)ecline") dodges BOTH the screen-level
# checks above -- its last line is an ordinary bracket-option line, so
# `_is_menu_select_prompt` correctly (by its own narrow rule) calls it a
# menu, and neither "y/n" nor "confirm" nor a trailing square bracket
# appears anywhere to trip the keyword/shape checks. Rather than chase
# this with yet another shape heuristic, bare Enter is simply never
# emittable, full stop: `classify_option_label` still returns
# `"bare_enter"` (so send_log/crawl_menus can still record that an
# Enter transition was discovered), but it is never a member of
# SAFE_ALLOWLIST, so `emit_key_if_safe`'s `category in SAFE_ALLOWLIST`
# check is False for it and it is recorded-not-pressed via the exact
# same generic path every other deny/unknown option already uses.
SAFE_ALLOWLIST = frozenset(_SAFE_LABEL_PATTERNS)
STATE_CHANGING_KEYS = frozenset(_DENY_LABEL_PATTERNS)

# Structural guarantee, not just convention: no category can ever be
# both emittable and named-dangerous. If this ever tripped it would mean
# a single category word was added to both dicts above by mistake.
assert not (SAFE_ALLOWLIST & STATE_CHANGING_KEYS), (
    "menu_crawler: SAFE_ALLOWLIST and STATE_CHANGING_KEYS must stay disjoint"
)

# NOTE: no "quit", no "bare_enter" here either -- neither can ever be
# assigned to an emitted option anymore (removed from
# `_SAFE_LABEL_PATTERNS`/`SAFE_ALLOWLIST`, see above), so neither would
# ever reach this edge_kind lookup regardless.
_NAV_CATEGORIES = frozenset({"back", "previous"})
_INFO_CATEGORIES = frozenset({"view", "help", "list", "display", "examine"})

# Placeholder `to_node` for a recorded-not-pressed option: the crawler
# never presses it, so there is no real destination signature to record
# -- `game_knowledge`'s own docstring explicitly allows an edge whose
# `to_node` was never separately upserted as a node (see
# `upsert_menu_edge`'s docstring), which is exactly this case.
UNEXPLORED_TARGET = "<unexplored>"

# A hard cap on how many frontier nodes a single crawl will visit --
# same bounded-rail philosophy as skills.py's `_MAX_PLAY_CYCLES`: an
# unattended crawl must never be capable of looping forever even against
# a pathological or mis-fixtured menu graph.
_DEFAULT_MAX_NODES = 200


class MenuCrawlError(Exception):
    """Raised only for a structural crawl failure (never for an ordinary
    unsafe/unexplored screen -- those are handled silently, by design;
    see module docstring)."""


# -- screen-level safety classification ---------------------------------------

# Distinctive shapes of a commit/confirm/purchase/combat gate --
# `classify.py` has no anchors for these (its taxonomy is login/pause/
# sector/port/menu, a different concern), so this module names them
# itself. Deliberately broad/conservative: any one of these matching
# ANYWHERE on the screen marks the whole screen unsafe to crawl from.
# Kept as an ADDITIONAL layer, not the sole gate -- see
# `_is_commit_shaped_prompt` below for the structural, keyword-
# independent layer added by the 2026-07-19 safety fix.
_UNSAFE_SCREEN_PATTERNS = (
    re.compile(r"\(\s*y\s*/\s*n\s*\)", re.I),
    re.compile(r"\[\s*y\s*/\s*n\s*\]", re.I),
    re.compile(r"are\s+you\s+sure", re.I),
    re.compile(r"\bconfirm\b", re.I),
    re.compile(r"do\s+you\s+(wish|want)\s+to", re.I),
    re.compile(r"\bpurchase\b", re.I),
    re.compile(r"how\s+many\s+(holds|units)", re.I),
    # NOT a bare `\bcombat\b` -- that also matches a perfectly safe
    # informational label like "Display Combat Rating"/"View Combat
    # Log" (caught live in this module's own test fixtures). Anchored to
    # phrases that mean combat is ACTUALLY active/starting, not merely
    # mentioned.
    re.compile(r"\bunder\s+attack\b|enemies?\s+present|\bfire\s+(phasers|photons|weapons)\b"
               r"|\bcombat\s+(has\s+begun|is\s+engaged)\b|\bentering\s+combat\b", re.I),
)

# classify.py gate anchors that mean "this isn't an ordinary navigable
# menu screen at all" -- a login/pause/door-select/character-creation
# gate, or a genuine CIM report. Never crawled through.
_NON_MENU_GATE_CLASSES = frozenset({
    "login_password", "login_name", "pause_key", "ansi_prompt",
    "game_select", "char_create", "cim_report",
})

# -- Finding 1 (2026-07-19 mack + cipher re-audit): structural,
# keyword-independent commit-shape detection on the ACTIVE prompt line
# (the caller's own `prompt_line` -- the single line the server is
# actually blocked on, mirroring classify.py's own gate-anchor-vs-
# content-anchor distinction). The whole-screen keyword scan above is a
# pure DENYLIST with no notion of which line is live; ordinary menu
# chrome sharing the screen with a real commit prompt ("(V)iew Ship
# Status" / "(H)elp" alongside "Fire photon torpedoes now? [Y]:" or
# "Proceed? [Yes]") dodged every keyword above and enumerated as an
# ordinary menu. These two patterns catch the SHAPE of a commit prompt
# instead, independent of wording.
_TRAILING_DEFAULT_BRACKET_RE = re.compile(
    # "...? [Y]:" / "...[Yes]" / "...[0]:" -- a trailing SQUARE-bracket
    # default-answer token. Square brackets are this game's convention
    # for a suggested/default VALUE (mirrors classify.py's own "Command
    # [TL=...]:" status-bracket convention); this module's own menu
    # OPTIONS are always PAREN/ANGLE brackets ("(Q)uit"), never square --
    # that is what lets this stay structural instead of colliding with
    # an ordinary bracket-option menu line. The bracket's content is
    # restricted to short alnum-only text so a multi-field status
    # bracket like "[TL=00:00:00]" (punctuation inside) never matches.
    r"\[\s*[a-zA-Z0-9]{1,10}\s*\]\s*:?\s*$"
)
_FREE_INPUT_PROMPT_RE = re.compile(
    # "Enter quantity to buy:" / "How many fighters to deploy:" -- a
    # free-value solicitation with no fixed menu of options to choose
    # from at all, so there is no safe bare-Enter or safe label to press
    # here regardless of what else is on screen. Deliberately broad: a
    # benign "Enter your choice:" selection invitation also matches this
    # shape and is classified unsafe too -- a false "unsafe" here only
    # under-explores the menu graph (harmless); see module docstring's
    # fail-closed philosophy.
    r"\b(?:enter|how\s+many|how\s+much|what\s+is|type\s+in)\b.*[:?]\s*$",
    re.I,
)


def _is_commit_shaped_prompt(prompt_line):
    """True iff the ACTIVE prompt line structurally looks like a
    commit/confirm/default-answer/free-input request, independent of its
    exact wording -- Finding 1's fix, checked in `screen_state` as an
    ADDITIONAL layer alongside (not a replacement for) the whole-screen
    keyword scan above."""
    if not prompt_line:
        return False
    return bool(
        _TRAILING_DEFAULT_BRACKET_RE.search(prompt_line)
        or _FREE_INPUT_PROMPT_RE.search(prompt_line)
    )


def _is_menu_select_prompt(prompt_line):
    """Deny-by-default, mirroring `classify_option_label`'s own
    philosophy (Finding 1): a screen is crawlable ("menu") ONLY when its
    active prompt AFFIRMATIVELY looks like an ordinary menu-selection
    invitation -- never merely because `enumerate_options` found >=2
    bracket lines somewhere on the screen. The one recognized shape: the
    active prompt line IS ITSELF one of the menu's own qualifying option
    lines -- the real captured shape in this project's own fixtures (a
    StarDock-style menu's last rendered line is its own final option,
    e.g. "(Q)uit to Sector", not a separate "Enter your choice:" line).
    A commit-shaped prompt (checked first) always loses even if it also
    happens to look like an option line.

    `_BRACKET_OPTION_RE`/`_DASH_OPTION_LINE_RE` are defined below in the
    option-enumeration section -- the same forward-reference precedent
    `screen_state` already relies on for `enumerate_options` itself.
    Extend this allowlist only against a live-captured screen shape that
    needs it (classify.py's own module docstring sets this precedent
    for its anchors) -- a false negative here only under-explores the
    menu graph (harmless)."""
    if not prompt_line or _is_commit_shaped_prompt(prompt_line):
        return False
    return bool(_BRACKET_OPTION_RE.search(prompt_line) or _DASH_OPTION_LINE_RE.match(prompt_line))


def screen_state(full_text, prompt_line):
    """Classify the CURRENT screen before any further step is taken --
    the second, independent safety layer (see module docstring).
    Returns one of:

    - `"unsafe"` -- a commit/confirm/purchase/combat prompt (by keyword,
      ANYWHERE on screen, OR by structural shape on the active prompt
      line -- see `_is_commit_shaped_prompt`), or one of classify.py's
      own login/pause/game-select/cim_report gate anchors. Never
      enumerated, never pressed from -- this is what "BACK OUT ...
      without answering" means (see `crawl_menus`).
    - `"menu"` -- a genuine multi-option navigable menu: at least 2
      DIFFERENT qualifying option lines (the same threshold classify.py's
      own `_is_menu` uses, for the same reason: a single inline same-line
      confirmation like "Use (N)ew or (B)BS Name [B]?" must never count
      as a navigable menu) AND the active prompt line affirmatively looks
      like a menu-selection invitation (see `_is_menu_select_prompt`) --
      NOT merely "2+ bracket lines exist somewhere on the screen".
    - `"other"` -- neither of the above: ordinary content with no
      enumerable options (a dead-end leaf; nothing further to press).

    NOTE: classifying "menu" here no longer implies a bare Enter is safe
    to send on it -- as of the 2026-07-19 hardening pass, `"bare_enter"`
    is never in `SAFE_ALLOWLIST` regardless of this function's result
    (see the module docstring's safety-layer 3 and `classify_option_
    label`'s own docstring). This function's contract is unchanged: it
    still decides whether the screen's LABELED options may be
    enumerated/pressed at all.

    THIRD re-audit round (2026-07-19, cipher): a bare 2-line vertical
    confirm ("Proceed?\n(Y)es\n(N)o") has "(N)o" as its active prompt
    line -- an ordinary bracket-option line -- so `_is_menu_select_prompt`
    correctly (by its own narrow rule) still calls it "menu", and no
    keyword/shape check above fires (no "y/n" slash, no trailing square
    bracket). This is now ALSO closed here: whenever `enumerate_options`
    finds EXACTLY 2 real (non-bare_enter) option lines and EITHER
    classifies to a `STATE_CHANGING_KEYS` category via
    `classify_option_label`, the WHOLE screen is unsafe, regardless of
    the other line's wording -- "Yes"/"No" is closed by "Yes" alone
    denying via the "confirm" category, independent of any accept-word
    vocabulary coincidence. This does NOT close every 2-option confirm
    (an "Accept"/"Decline" pair still classifies "menu" here -- neither
    option is a named deny word -- see `SAFE_ALLOWLIST` excluding
    `"bare_enter"` for why that residual case is still never pressed).
    """
    if any(p.search(full_text) for p in _UNSAFE_SCREEN_PATTERNS):
        return "unsafe"
    if _is_commit_shaped_prompt(prompt_line):
        return "unsafe"
    if classify_screen(full_text, prompt_line) in _NON_MENU_GATE_CLASSES:
        return "unsafe"
    _options, is_menu = enumerate_options(full_text)
    if is_menu:
        real_options = [(key, label) for key, label in _options if key != ""]
        if len(real_options) == 2 and any(
            classify_option_label(key, label) in STATE_CHANGING_KEYS for key, label in real_options
        ):
            return "unsafe"
    if is_menu and _is_menu_select_prompt(prompt_line):
        return "menu"
    return "other"


# -- option enumeration --------------------------------------------------------

# Re-authored here rather than imported from classify.py: that module's
# `_BRACKET_OPTION_RE`/`_DASH_OPTION_RE` answer a boolean "is this a
# menu" question; this module needs to ENUMERATE (key, label) pairs to
# feed the safety gate -- a different concern, same deliberate-
# duplication precedent classify.py's own docstring already establishes
# for its CIM anchors vs state_parser's data-extraction ones.
#
# The bracket pattern's tail is captured lazily up to the NEXT
# bracket-option on the same (possibly packed) line, or end of line --
# so "(B)uy Ship (V)iew Ship" enumerates as two options, not one polluted
# by the other's text.
_BRACKET_OPTION_RE = re.compile(
    r"[(<]\s*([a-zA-Z!?])\s*[)>](.*?)(?=[(<]\s*[a-zA-Z!?]\s*[)>]|$)"
)
_DASH_OPTION_LINE_RE = re.compile(r"^\s*([a-zA-Z])\s*[-:]\s*(.+)$")


def enumerate_options(full_text):
    """Scan `full_text` for labeled menu options, bracket style
    ("(B)uy Ship" -- the on-screen hotkey letter is embedded INSIDE the
    label word) and dash style ("Q - Quit" -- hotkey and label are
    separate tokens). Returns `(options, is_menu)`: `options` is an
    ordered list of `(key, label)` tuples (plus a synthetic
    `("", "<bare Enter>")` entry IFF `is_menu`); `is_menu` is True iff at
    least 2 DIFFERENT lines each qualify (mirrors classify.py's own
    `_is_menu` threshold -- see `screen_state`'s docstring for why).

    Bracket-style reconstruction: "(V)iew" is really the single word
    "View" with its hotkey highlighted -- the key letter is glued back
    onto the tail ONLY when there is no whitespace between the bracket
    and the tail (the "(V)iew" shape); a bracket followed by a space
    before its tail (the "(?) Help" shape) is already a separate word
    and is never glued (gluing it would corrupt "Help" into "?Help")."""
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
    """Deny-by-default: returns a SAFE_ALLOWLIST category ONLY on an
    affirmative match; anything else -- a named STATE_CHANGING_KEYS verb,
    a COMPOUND label naming more than one action (Finding 2, below), or
    a plausible-looking but unrecognized label -- is `"unknown"` and is
    never treated as emittable by `emit_key_if_safe()`. Deny patterns are
    checked BEFORE the compound check, which is checked BEFORE safe ones:
    a label containing both a nav word and a state-changing word
    (however unlikely) is treated as unsafe, never the reverse.

    "Quit" is never a SAFE_ALLOWLIST category (2026-07-19 safety fix,
    Finding 4) -- there is deliberately no carve-out regex distinguishing
    an ordinary parent-menu quit from a full game/session exit anymore,
    since neither is ever pressed: the BFS-via-replay traversal never
    needs to press quit to navigate at all (see module docstring).

    A bare Enter (`key == ""`) still returns its own `"bare_enter"`
    category -- so `send_log`/the recorded-not-pressed edge can still
    say an Enter transition was discovered -- but `"bare_enter"` is
    likewise never a SAFE_ALLOWLIST category (2026-07-19 hardening pass,
    safety layer 3 in the module docstring): it is unconditionally
    recorded-not-pressed, regardless of how safe the screen it was
    discovered on looks."""
    if key == "":
        return "bare_enter"
    norm = (label or "").strip().lower()
    if key == "?" and not norm:
        return "help"
    for category, pattern in _DENY_LABEL_PATTERNS.items():
        if pattern.search(norm):
            return category
    if _COMPOUND_LABEL_RE.search(norm):
        # A compound label names more than one action/clause -- reject
        # SAFE classification structurally even when no individual
        # clause happens to hit a _DENY_LABEL_PATTERNS word above
        # (Finding 2). Recorded-not-pressed, same as any other unknown.
        return "unknown"
    for category, pattern in _SAFE_LABEL_PATTERNS.items():
        if pattern.search(norm):
            return category
    return "unknown"


def emit_key_if_safe(session, from_node, key, label, category, emitted_keys, send_log, step_timeout=8.0):
    """THE single chokepoint every candidate crawl keystroke passes
    through (the never-commit guarantee's audit target -- see module
    docstring). Every candidate, safe or not, gets exactly one
    `send_log` entry; `session.send()` (via `settle.send_and_confirm`)
    is reached ONLY when `category in SAFE_ALLOWLIST` -- there is no
    other branch in this function that can reach it.

    Returns `(emitted, text, prompt)`. `emitted=False` always pairs with
    `text=prompt=None` (nothing was sent, nothing new to read).
    `emitted=True, text=None` means the key WAS sent but never positively
    confirmed settled (`send_and_confirm`'s `confirmed=False`) -- the
    caller must treat the resulting screen as untrustworthy and read
    nothing further from it, exactly like an ordinary unsafe screen."""
    emitted = category in SAFE_ALLOWLIST
    send_log.append({
        "from_node": from_node,
        "key": key,
        "label": label,
        "category": category,
        "emitted": emitted,
    })
    if not emitted:
        return False, None, None

    # settle.py's own documented workaround: a menu single-key selection
    # sent WITH its usual trailing CRLF can have that Enter consumed by
    # the very next prompt -- never append one for a real key. Bare
    # Enter (key == "") would be the one case that legitimately needs
    # `enter` -- but since the 2026-07-19 hardening pass, `category ==
    # "bare_enter"` is never in SAFE_ALLOWLIST, so `key == ""` can never
    # actually reach this line at all (the `if not emitted` return above
    # always fires first). Left in place defensively/for documentation
    # rather than deleted -- it costs nothing and stays correct if this
    # function is ever called directly, outside SAFE_ALLOWLIST's gate.
    enter = key == ""
    _reason, _elapsed, confirmed = send_and_confirm(
        session, key, confirm_prompt=None, enter=enter, secret=False, timeout_s=step_timeout,
    )
    emitted_keys.append(category)
    if not confirmed:
        return True, None, None

    rows = session.render()
    text = session.render_text(rows)
    prompt = rows[-1].strip() if rows else ""
    return True, text, prompt


# -- signature / labeling ------------------------------------------------------

# Back-compat alias -- the signature logic itself lives in the pure
# `menu_sig` module now (so sibling pure-logic consumers can import it
# without dragging in this module's daemon deps), but `menu_nav` and
# other callers reach it as `menu_crawler._signature`; keep that name
# resolvable.
_signature = menu_signature


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
    already-proven-safe `(key, label, category)` path from a FRESH
    session positioned at the world's start context -- see module
    docstring's "Traversal" section for why this is what lets the
    crawler need no explicit "cancel"/"undo" action at all. Returns
    `(session, text, prompt)`, or `None` if the replay itself hit an
    unsafe/unconfirmed screen partway (defensive -- a deterministic mock
    menu should never actually do this, but a live game might)."""
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


def crawl_menus(session_factory, path, max_nodes=_DEFAULT_MAX_NODES, step_timeout=8.0):
    """Crawl the menu graph reachable from `session_factory()`'s start
    context via BFS-by-replay (see module docstring), writing every
    discovered node/edge into the `game_knowledge` store at `path` (an
    already-resolved, world_id-keyed path -- obtain it via
    `game_knowledge.knowledge_path(host, game_letter, handle, ...)`,
    mirroring that module's own "identity resolved once, at the call
    site" convention).

    `session_factory` is a zero-arg callable returning a FRESH session
    already sitting at the world's stable start context every time it is
    called (see module docstring's Traversal section).

    Returns `{"nodes_visited": int, "emitted_keys": [...], "send_log":
    [...]}`. `emitted_keys` is the flat list of SAFE_ALLOWLIST category
    strings this crawl actually sent (never a raw keystroke, never a
    STATE_CHANGING_KEYS category -- see `emit_key_if_safe`); `send_log`
    is the full, richer per-candidate audit trail (every option this
    crawl ever discovered, safe or not, with its resolved category and
    whether it was actually emitted)."""
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
            # BACK OUT: this frontier is either a genuine
            # commit/confirm/combat/login gate, or simply content with
            # no enumerable options -- either way, NOTHING is ever
            # pressed from it. The node itself was already upserted by
            # whichever edge discovered it (or, for the root, just
            # above) -- recording that it exists is still valuable for
            # a future pathfinder, it is just never explored past.
            continue

        options, _is_menu = enumerate_options(text)
        for key, label in options:
            category = classify_option_label(key, label)
            emitted, new_text, new_prompt = emit_key_if_safe(
                session, sig, key, label, category, emitted_keys, send_log, step_timeout
            )
            if not emitted:
                kind = "action"  # game_knowledge has no "unknown" kind -- see module docstring
                upsert_menu_edge(
                    path, sig, key or "<enter>", UNEXPLORED_TARGET, kind=kind, desc=f"{category}: {label}"
                )
                continue
            if new_text is None:
                # Sent, but never positively confirmed settled -- the
                # resulting screen is untrustworthy; nothing safe to
                # read, nothing recorded, nothing queued.
                continue

            new_sig = menu_signature(new_text)
            upsert_menu_node(path, new_sig, label=_first_line(new_text))
            edge_kind = "nav" if category in _NAV_CATEGORIES else "info" if category in _INFO_CATEGORIES else "action"
            upsert_menu_edge(path, sig, key or "<enter>", new_sig, kind=edge_kind, desc=label)
            if new_sig not in seen:
                seen.add(new_sig)
                queue.append((new_sig, steps + [(key, label, category)]))

            # `session` has moved past `sig` -- re-anchor before probing
            # the NEXT sibling option at `sig` (see module docstring).
            reached = _replay(session_factory, steps, emitted_keys, send_log, step_timeout)
            if reached is None:
                break  # can't safely get back to `sig` -- stop probing further siblings here
            session, text, prompt = reached

    return {
        "nodes_visited": nodes_visited,
        "emitted_keys": list(emitted_keys),
        "send_log": list(send_log),
    }
