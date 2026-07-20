"""Menu Crawler tests (TW-26) -- no network, mock/fixture screens only.

`FakeMenuSession` walks a BRANCHING graph (unlike FakeReplaySession/
FakeLoginSession's linear scripts): `transitions[(node_id, sent_text)]`
gives the next node id; an unmapped send defaults to staying put (models
an ignored/invalid keystroke). The advance is deferred to the next
`sleep()` call, same async-response convention as this project's other
fake sessions (see tests/test_skills.py's FakeReplaySession docstring)
-- load-bearing for `settle.send_and_confirm`'s idle-confirm path.

The never-commit guarantee this whole module exists to prove: across a
full crawl of an adversarial graph containing a `[B]uy` option, a
"Quit (Disconnect)" option, an ambiguous unlabeled option, and a SAFE-
labeled option that leads to an actual confirm/purchase prompt --
`set(emitted_keys) <= menu_crawler.SAFE_ALLOWLIST` and
`set(emitted_keys) & menu_crawler.STATE_CHANGING_KEYS == set()`, and no
edge is ever recorded as originating FROM the confirm/purchase screen."""

import pytest

from twclient import game_knowledge, menu_crawler


class FakeMenuSession:
    """`screens`: node_id -> rendered text. `transitions`:
    `(node_id, sent_text) -> next_node_id`; an unmapped `(node_id, key)`
    defaults to staying on `node_id` (an ignored/no-op keystroke, e.g. a
    bare-Enter probe with nothing new to page to). `start` is the node
    id a freshly-constructed session begins parked at.

    `rx_count`/`last_rx` start already "settled" (rx_count=1,
    last_rx far enough in the past) -- this models a session that is
    already sitting at a fully-rendered, quiescent screen the instant
    it's handed to the crawler (the real-world case: login/negotiation
    already happened), so `settle.wait_until_settled`'s very first check
    reports "idle" immediately rather than timing out on a session that
    has (by the fake's own bookkeeping) never received anything."""

    def __init__(self, screens, transitions, start):
        self.t = 0.0
        self.rx_count = 1
        self.last_rx = -1.0
        self._screens = screens
        self._transitions = transitions
        self._id = start
        self.sent = []
        self._pending = None

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self._pending is not None:
            key = self._pending
            self._pending = None
            self._id = self._transitions.get((self._id, key), self._id)
            self.rx_count += 1
            self.last_rx = self.t

    def render(self):
        return self._screens[self._id].split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._screens[self._id]

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))
        self._pending = text


# -- fixture graph (StarDock / shipyard / nested view + adversarial) ---------

SCREENS = {
    "stardock_main": (
        "==-- StarDock Command Menu --==\n"
        "(V)iew Ship Status\n"
        "(L)ist Shipyard Inventory\n"
        "(H)elp\n"
        "(K) ----\n"
        "(Q)uit to Sector"
    ),
    "ship_status_view": (
        "Merchant Cruiser -- Status\n"
        "Hull: 100%  Fuel: Full\n"
        "Nothing else to do here."
    ),
    "shipyard_menu": (
        "Ye Olde Shipyard -- StarDock Shipyard Menu\n"
        "(V)iew Ship Details\n"
        "(B)uy New Ship\n"
        "(Q)uit (Disconnect)"
    ),
    "help_screen": (
        "StarDock Help\n"
        "This menu lets you inspect your ship and browse the shipyard.\n"
        "Nothing else to do here."
    ),
    "sector_leaf": (
        "Sector : 4021\n"
        "Ports : None\n"
        "Warps to Sector(s) : 4022 - 4023"
    ),
    "nested_view_menu": (
        "Merchant Cruiser -- Full Specifications\n"
        "Holds: 40  Fighters: 500  Shields: 200\n"
        "(D)isplay Combat Rating\n"
        "(B)ack"
    ),
    "sneaky_confirm_screen": (
        "Purchase this Merchant Cruiser for 145,000 credits?\n"
        "(Y)es\n"
        "(N)o"
    ),
}

TRANSITIONS = {
    ("stardock_main", "V"): "ship_status_view",
    ("stardock_main", "L"): "shipyard_menu",
    ("stardock_main", "H"): "help_screen",
    ("stardock_main", "Q"): "sector_leaf",
    ("shipyard_menu", "V"): "nested_view_menu",
    ("nested_view_menu", "D"): "sneaky_confirm_screen",
    ("nested_view_menu", "B"): "shipyard_menu",
    # Deliberately NO transitions for "K" (unknown), "B"/buy on
    # shipyard_menu, or "Q"/disconnect on shipyard_menu -- the whole
    # point is that the crawler must never send them in the first
    # place, so there is nothing for these to model.
}


def _session_factory():
    return FakeMenuSession(dict(SCREENS), dict(TRANSITIONS), start="stardock_main")


# -- classify_option_label (per-option safety gate) ---------------------------


@pytest.mark.parametrize(
    "key,label,expected",
    [
        ("V", "View Ship Status", "view"),
        ("H", "Help", "help"),
        ("L", "List Shipyard Inventory", "list"),
        ("D", "Display Combat Rating", "display"),
        ("E", "Examine Cargo", "examine"),
        ("I", "Inspect Manifest", "examine"),
        ("B", "Back", "back"),
        ("P", "Previous Menu", "previous"),
    ],
)
def test_classify_option_label_safe_categories(key, label, expected):
    assert menu_crawler.classify_option_label(key, label) == expected
    assert expected in menu_crawler.SAFE_ALLOWLIST


@pytest.mark.parametrize(
    "key,label,expected",
    [
        ("B", "Buy New Ship", "buy"),
        ("S", "Sell Cargo", "sell"),
        ("P", "Purchase Fighters", "purchase"),
        ("A", "Attack Enemy Ship", "attack"),
        ("D", "Deploy Fighters", "deploy"),
        ("G", "Genesis Torpedo", "genesis"),
        ("M", "Move to Sector", "move"),
        ("J", "Jump to Sector", "jump"),
        ("T", "Tow Ship", "tow"),
        ("L", "Land on Planet", "land"),
        ("K", "Take Cargo", "take"),
        ("C", "Confirm Order", "confirm"),
        ("Y", "Yes", "confirm"),
    ],
)
def test_classify_option_label_deny_categories(key, label, expected):
    assert menu_crawler.classify_option_label(key, label) == expected
    assert expected in menu_crawler.STATE_CHANGING_KEYS


@pytest.mark.parametrize(
    "key,label,expected",
    [
        ("A", "Acquire Ship Parts", "acquire"),
        ("R", "Requisition Fighters", "requisition"),
        ("O", "Order Supplies", "order"),
        ("T", "Trade Goods", "trade"),
        ("D", "Dock at Starbase", "dock"),
        ("E", "Eject Escape Pod", "eject"),
        ("D", "Drop Cargo", "drop"),
        ("T", "Transfer Credits", "transfer"),
        ("U", "Upgrade Shields", "upgrade"),
        ("R", "Repair Hull", "repair"),
        ("R", "Refuel Ship", "refuel"),
        ("L", "Launch Fighters", "launch"),
        ("A", "Abandon Ship", "abandon"),
        ("J", "Jettison Cargo", "jettison"),
        ("P", "Pay Toll", "pay"),
        ("I", "Invest in Stock", "invest"),
        ("B", "Bribe Guard", "bribe"),
        ("S", "Steal Cargo", "steal"),
        ("B", "Boarding the Enemy Ship", "board"),
        ("R", "Ram Enemy Ship", "ram"),
        ("C", "Cloak Ship", "cloak"),
        ("M", "Mine Asteroid", "mine"),
    ],
)
def test_classify_option_label_expanded_deny_vocabulary(key, label, expected):
    """Finding 3 (2026-07-19 re-audit): a broader belt-and-suspenders
    deny vocabulary, on top of Finding 2's structural compound-label
    check -- these are independent layers, not alternatives."""
    assert menu_crawler.classify_option_label(key, label) == expected
    assert expected in menu_crawler.STATE_CHANGING_KEYS


@pytest.mark.parametrize(
    "key,label",
    [
        ("V", "View & Repair Ship"),
        ("V", "View and Upgrade Shields"),
        ("L", "List Cargo and Jettison Excess"),
    ],
)
def test_compound_label_naming_a_second_committing_clause_is_not_emitted(key, label):
    """Finding 2 (2026-07-19 re-audit): a safe-sounding FIRST clause
    doesn't launder a state-changing SECOND clause. These three happen
    to also hit Finding 3's expanded deny vocabulary (repair/upgrade/
    jettison) -- see the next test for the structural check proven
    independent of any deny word at all."""
    category = menu_crawler.classify_option_label(key, label)
    assert category not in menu_crawler.SAFE_ALLOWLIST


def test_compound_safe_sounding_label_with_no_deny_word_is_still_unknown():
    """The structural fix's own independent value (Finding 2): a
    compound label whose second clause dodges every single
    _DENY_LABEL_PATTERNS word must still be rejected structurally, not
    merely because it also happens to hit a deny word (unlike the three
    cases above, this one hits none)."""
    assert menu_crawler.classify_option_label("V", "View and Examine Log") == "unknown"


@pytest.mark.parametrize(
    "key,label",
    [
        ("V", "View Log As Well As Cargo"),
        ("V", "View Manifest Along With Cargo"),
    ],
)
def test_compound_connector_broadened_vocabulary_is_not_emitted(key, label):
    """Fix 1's compound-connector broadening (2026-07-19 THIRD re-audit
    round): "and"/"then"/"&"/","/"/"/"+" alone missed "as well as"/
    "along with" as ways to join a second clause onto an otherwise-safe-
    looking label. Neither hits a deny word on its own (proving the
    structural, vocabulary-independent value of the compound check, same
    as test_compound_safe_sounding_label_with_no_deny_word_is_still_
    unknown above) -- each must still classify "unknown", never safe.

    NOTE: "plus" and "with" were ALSO tried here in the THIRD re-audit
    round but REVERTED in the convergence pass (Fix B.6, mack) -- both
    over-rejected ordinary single-clause labels ("Help with Navigation")
    far more often than they caught a genuine compound. See
    test_compound_connector_with_and_plus_do_not_over_reject_common_
    labels below for the false-positive guard proving the revert."""
    category = menu_crawler.classify_option_label(key, label)
    assert category == "unknown"
    assert category not in menu_crawler.SAFE_ALLOWLIST


@pytest.mark.parametrize(
    "key,label,expected_category",
    [
        ("H", "Help with Navigation", "help"),
        ("V", "View Ship Plus Cargo Manifest", "view"),
    ],
)
def test_compound_connector_with_and_plus_do_not_over_reject_common_labels(key, label, expected_category):
    """Fix B.6 (2026-07-19 convergence pass, mack): "with"/"plus" were
    dropped from `_COMPOUND_LABEL_RE` because they over-reject ordinary
    labels that merely happen to contain either word without naming a
    second action at all -- these must classify SAFE, not "unknown"."""
    category = menu_crawler.classify_option_label(key, label)
    assert category == expected_category
    assert category in menu_crawler.SAFE_ALLOWLIST


def test_simple_single_clause_safe_labels_still_classify_safe():
    """A CLEAN, single-clause label with no conjunction must NOT be
    over-rejected by the compound check (Finding 2's own stated
    counter-examples)."""
    assert menu_crawler.classify_option_label("D", "Display Combat Rating") == "display"
    assert menu_crawler.classify_option_label("V", "View Ship Status") == "view"


# -- Finding 1 / Fix 1 (2026-07-19 THIRD re-audit round, cipher): deny-word
# anchoring -- a TRAILING `\b` let a glued suffix dodge every deny word
# (31/31, proven end-to-end via "(P)revious Owner Buyout" -> "previous"
# (SAFE) -> emitted). Fixed by dropping the trailing boundary (prefix-match
# or a targeted suffix list for collision-prone short stems -- see
# `_DENY_LABEL_PATTERNS`'s own module-level comment for the per-word
# reasoning). These are cipher's + mack's exact repros, as permanent
# regression guards.


def test_deny_word_anchoring_catches_glued_suffix_derived_forms():
    """Fix 1's surviving exact repro: "Sale" reads safe-ish by its FIRST
    word ("List" -- a SAFE_ALLOWLIST word) but names Fix 2's "sale" deny
    word, which the OLD `\bWORD\b` trailing-boundary pattern would have
    let dodge entirely (the original bug this whole Fix 1 was written
    against). Deny is checked before safe, so the leading safe word
    never matters. (The sibling "Buyout"/"Ejection"/"Confirmation" cases
    that USED to live in this parametrize list are no longer caught --
    see test_round5_accepted_residual_action_and_agent_noun_forms below
    for why that is now the deliberately accepted outcome, not a
    regression.)"""
    category = menu_crawler.classify_option_label("S", "List Ship For Sale")
    assert category == "sale"
    assert category not in menu_crawler.SAFE_ALLOWLIST
    assert category in menu_crawler.STATE_CHANGING_KEYS


@pytest.mark.parametrize(
    "key,label,expected_category",
    [
        ("P", "Previous Owner Buyout", "previous"),
        ("E", "View Escape Pod Ejection", "view"),
        ("C", "Display Confirmation", "display"),
    ],
)
def test_round5_accepted_residual_action_and_agent_noun_forms(key, label, expected_category):
    """FOURTH re-audit round convergence pass (2026-07-19, "no round 5"):
    these three labels were round 3's own headline exact-repro
    regression guards (`\bbuy\b`/`\beject\b`/`\bconfirm\b` dodged by a
    glued suffix) -- and are now DELIBERATELY, EXPLICITLY no longer
    caught, because the convergence pass's complete false-positive sweep
    bounded every deny pattern to ACTIVE VERB CONJUGATIONS ONLY (see
    `_DENY_LABEL_PATTERNS`'s own class-wide comment). "Buyout"/
    "Ejection"/"Confirmation" are ACTION/DERIVED-NOUNS sharing a verb's
    stem -- structurally the identical class as "Buyer"/"Vendor"/
    "Launcher" (agent-nouns), which the same sweep fixed as false
    positives. There is no way to keep "informational agent-noun ==
    safe" while also keeping "informational-shaped derived-noun ==
    denied" without hand-picking exceptions per word -- the convergence
    pass chose the SAME uniform rule for both classes and accepted the
    residual, per the module docstring's residual note (b). This is a
    REAL behavior reversal from round 3/4, made explicit here rather
    than silently absorbed -- these three labels now genuinely classify
    SAFE (not merely "unknown") and WOULD be emitted by a live crawl,
    bounded to zero real impact by the A+C protocol (disposable
    zero-asset character, hub-supervised abort)."""
    category = menu_crawler.classify_option_label(key, label)
    assert category == expected_category
    assert category in menu_crawler.SAFE_ALLOWLIST


@pytest.mark.parametrize(
    "key,label,expected_category",
    [
        ("B", "Ship Bought Last Turn", "buy"),
        ("S", "Cargo Sold", "sell"),
        ("T", "Fighters Taken", "take"),
        ("T", "Sector Took Damage", "take"),
        ("S", "Credits Stolen", "steal"),
        ("S", "Cargo Stole", "steal"),
        ("P", "Toll Paid", "pay"),
        ("F", "Credits Spent", "spend"),
        ("C", "Fighters Sent", "send"),
        ("H", "Fully Laden Hold", "load"),
    ],
)
def test_deny_word_anchoring_catches_irregular_forms(key, label, expected_category):
    """Fix 1's irregular-form list -- these share no letter-stem with
    their base verb at all (bought/sold/took/taken/stole/stolen/paid/
    sent/spent/laden), so no suffix-tolerant prefix match would ever
    catch them; each needs its own explicit bounded alternative."""
    category = menu_crawler.classify_option_label(key, label)
    assert category == expected_category
    assert category not in menu_crawler.SAFE_ALLOWLIST


@pytest.mark.parametrize(
    "key,label,expected_category",
    [
        ("A", "Start an Auction", "auction"),
        ("B", "Barter for Goods", "barter"),
        ("L", "Lease This Ship", "lease"),
        ("R", "Rent a Cargo Hold", "rent"),
        ("V", "Vend Excess Cargo", "vend"),
        ("P", "Collect Your Payoff", "payoff"),
        ("W", "Place a Wager", "wager"),
        ("B", "Bet on the Race", "bet"),
        ("G", "Gamble Your Credits", "gamble"),
        ("R", "Demand a Ransom", "ransom"),
        ("D", "Donate to the Guild", "donate"),
        ("G", "Gift a Torpedo", "gift"),
        ("R", "Redeem Your Points", "redeem"),
        ("F", "Forfeit the Match", "forfeit"),
        ("S", "Surrender Your Ship", "surrender"),
    ],
)
def test_fix_2_new_deny_vocabulary(key, label, expected_category):
    """Fix 2 (2026-07-19 THIRD re-audit round) -- a KNOWN vocabulary
    gap, explicitly not claimed complete (see the module's own
    escalation on denylist provability): trade/commerce/wager verbs
    absent in any form until now."""
    category = menu_crawler.classify_option_label(key, label)
    assert category == expected_category
    assert category in menu_crawler.STATE_CHANGING_KEYS


@pytest.mark.parametrize(
    "key,label,expected_category",
    [
        ("W", "Withdraw Credits", "withdraw"),
        ("D", "Deposit Credits", "deposit"),
        ("C", "Commit Your Choice", "commit"),
        ("A", "Accept the Offer", "accept"),
    ],
)
def test_optional_banking_and_confirm_deny_vocabulary(key, label, expected_category):
    """Convergence-pass optional additions (cipher, on-domain): withdraw/
    deposit for a player_bank, commit/accept as central confirm verbs.
    Each was collision-checked against the 7 SAFE_LABEL_PATTERNS
    categories and common derived forms before being added (see
    `_DENY_LABEL_PATTERNS`'s own inline comments -- "committee",
    "acceptable" are the textbook near-misses, both cleanly excluded)."""
    category = menu_crawler.classify_option_label(key, label)
    assert category == expected_category
    assert category in menu_crawler.STATE_CHANGING_KEYS


@pytest.mark.parametrize(
    "key,label,expected_category",
    [
        ("C", "View the Committee Roster", "view"),
        ("A", "Display Acceptable Cargo Types", "display"),
    ],
)
def test_optional_banking_and_confirm_words_do_not_over_reject(key, label, expected_category):
    """The collision-check itself, made explicit: "committee" and
    "acceptable" must NOT be caught by "commit"/"accept"'s suffix-tolerant
    patterns -- both derive from, but are structurally distinct from,
    their base verb (neither is "commit"/"accept" + one of the listed
    suffixes)."""
    category = menu_crawler.classify_option_label(key, label)
    assert category == expected_category
    assert category in menu_crawler.SAFE_ALLOWLIST


@pytest.mark.parametrize(
    "key,label,expected_category",
    [
        ("V", "View Ship Status", "view"),
        ("D", "Display Combat Rating", "display"),
        ("P", "Previous Menu", "previous"),
        ("P", "Previous Owner", "previous"),
        ("L", "List Ships", "list"),
        ("B", "Back to Sector", "back"),
    ],
)
def test_deny_word_anchoring_does_not_over_reject_common_safe_labels(key, label, expected_category):
    """The explicit false-positive guard required alongside Fix 1: the
    suffix-tolerant/targeted anchoring change must NOT cause any of these
    ordinary, previously-safe labels to start denying -- in particular
    "Previous Owner" (no "Buyout") must stay safe, proving the fix keys
    off the DENY word's derived form, not merely "any word near a safe
    word neutralizes it"."""
    assert menu_crawler.classify_option_label(key, label) == expected_category
    assert expected_category in menu_crawler.SAFE_ALLOWLIST


# -- 2026-07-19 convergence pass (operator-ratified A+C protocol frame change):
# the label gate is now BEST-EFFORT defense-in-depth, not a completeness
# guarantee (see module docstring) -- this pass is exactly two things: fix
# the one common-form miss below (Fix A), and fix every false-positive
# coverage regression the THIRD re-audit round introduced (Fix B).


def test_fix_a_firing_is_denied_the_same_way_mining_is():
    """Fix A (a common-form MISS, mack): the round-3 silent-e fix
    patched "mine" -> "mining" but missed the IDENTICAL bug on
    "fire" -> "firing" in the "attack" pattern -- "firing" doesn't
    literally contain the substring "fire" (fir+ing, not fire+ing), so
    the old `\\bfire(s|d|ing)?\\b` never matched it. "Display Auto-Firing
    Toggle" dodged to "display" (SAFE) and would have been emitted."""
    assert menu_crawler.classify_option_label("F", "Display Auto-Firing Toggle") == "attack"
    assert menu_crawler.classify_option_label("F", "Auto-Firing Toggle") == "attack"


@pytest.mark.parametrize(
    "key,label,expected_category",
    [
        ("F", "View Fighter Status", "view"),
        ("T", "View Traders Guild Info", "view"),
        ("C", "View Station Cloakroom", "view"),
        ("B", "View Bounty Board", "view"),
        ("L", "Port Listing", "list"),
        ("N", "Notice Board", "unknown"),
    ],
)
def test_fix_b_false_positives_do_not_over_reject(key, label, expected_category):
    """Fix B (6 coverage-BLOCKER false positives, mack + cipher):
    ordinary TW2002 domain nouns and safe-category gerunds that a
    round-3 anchoring/vocabulary change wrongly denied.
    - "Fighter" is a NOUN (the combat units) -- "fight" no longer has an
      "-er" suffix alternative.
    - "Trader(s)" is an agent-noun/guild role -- "trade" is narrowed to
      verb forms only (trades/traded/trading), no longer a blanket
      prefix.
    - "Cloakroom" is an ordinary word -- "cloak" is narrowed to a
      targeted suffix list, no longer a blanket prefix.
    - "Board"/"Notice Board" is the common UI noun (a bounty/notice
      board) -- "board" is narrowed to the active "-ing" verb form only
      ("boarding"), so bare "Board" is "unknown" (still never emitted,
      just no longer mislabeled "board").
    - "Listing" collided with the SAFE "list" category's own gerund --
      the "listing" deny word was removed outright (mack's own-goal
      catch), and `_SAFE_LABEL_PATTERNS["list"]` was widened to
      explicitly include "listing" too (removing the deny word alone
      would have left it merely "unknown", not genuinely restored to
      SAFE -- see that pattern's own inline comment). "Port Listing" is
      now affirmatively "list" (SAFE); "Notice Board" stays "unknown"
      (still never emitted, just no longer mislabeled "board" -- there
      is no equivalent safe-category widening for a bare noun with no
      verb at all)."""
    assert menu_crawler.classify_option_label(key, label) == expected_category
    if expected_category == "unknown":
        assert expected_category not in menu_crawler.SAFE_ALLOWLIST
    else:
        assert expected_category in menu_crawler.SAFE_ALLOWLIST


# -- FOURTH re-audit round, convergence pass ("no round 5") -------------------
# Round-4 confirmed the remaining defect is ONE finite class: blanket
# (no-trailing-boundary) deny patterns false-positiving on INFORMATIONAL
# labels (past-participles, agent-nouns, derived-nouns). Every
# `_DENY_LABEL_PATTERNS` entry that was still a blanket prefix is now bounded
# to active-verb-conjugation forms only -- see that dict's own class-wide
# comment for the full rationale and the accepted-residual tradeoff.


@pytest.mark.parametrize(
    "key,label,expected_category",
    [
        ("S", "View Sales Tax Summary", "view"),  # Fix 1 confirmed FP: sale -> "Sales Tax"
        ("L", "View Launcher Specs", "view"),  # Fix 1 confirmed FP: launch -> "Launcher"
        ("V", "Display Vendor Directory", "display"),  # Fix 1 confirmed FP: vend -> "Vendor"
        ("G", "View Available Gifts", "view"),  # own judgment call, same noun-not-verb reasoning as sale
    ],
)
def test_fix1_complete_sweep_confirmed_false_positives_are_safe(key, label, expected_category):
    """Fix 1's 4 confirmed false positives (mack, "the complete sweep"):
    "sale"/"launch"/"vend"/"spend" (spend's own guard is the next test,
    since its label needs a distinct shape) were still blanket prefixes
    after the THIRD re-audit round and wrongly denied ordinary
    informational/noun uses. Each of these labels leads with a genuine
    SAFE_ALLOWLIST word and must classify accordingly -- deny is checked
    first, so if the deny word still matched, the leading safe word
    would never be reached."""
    category = menu_crawler.classify_option_label(key, label)
    assert category == expected_category
    assert category in menu_crawler.SAFE_ALLOWLIST


def test_fix1_spender_false_positive_is_safe():
    """The 4th confirmed FP: "spend" -> "Spender" (an agent-noun, e.g. a
    leaderboard). Separate test since the natural example label doesn't
    fit the other three's shared parametrize pattern as cleanly."""
    category = menu_crawler.classify_option_label("S", "View Top Spender Rankings")
    assert category == "view"
    assert category in menu_crawler.SAFE_ALLOWLIST


def test_fix2_withdrawal_is_safe():
    """Fix 2 (cipher): dropped "al" from "withdraw" -- "Withdrawal" is
    always a noun (a completed/historical transaction record), zero
    commit-coverage upside from catching it."""
    category = menu_crawler.classify_option_label("W", "View Withdrawal Notice")
    assert category == "view"
    assert category in menu_crawler.SAFE_ALLOWLIST


def test_fix3_accepted_and_commitment_participles_are_not_denied():
    """Fix 3: "Accepted"/"Commitment" no longer deny ("ed" dropped from
    accept, "ted"/"ment" dropped from commit) -- both read as adjectival/
    informational status far more often than an active commit action.
    Neither label has an OTHER safe word present, so the honest outcome
    is "unknown" (same as "Notice Board" above) -- still never emitted,
    just no longer wrongly flagged as a state-changing verb; there is no
    natural SAFE_ALLOWLIST category for a bare status adjective with no
    verb in the label at all."""
    for label in ("Accepted Applications", "View Commitment Report"):
        category = menu_crawler.classify_option_label("X", label)
        assert category not in menu_crawler.STATE_CHANGING_KEYS
    # the second one DOES lead with "View" and should be affirmatively safe
    assert menu_crawler.classify_option_label("X", "View Commitment Report") == "view"


@pytest.mark.parametrize(
    "key,label,expected_category",
    [
        ("B", "Buy Ship", "buy"),
        ("S", "Sell Cargo", "sell"),
        ("A", "Attack Enemy", "attack"),
        ("F", "Fire Weapons", "attack"),
        ("D", "Deploy Fighters", "deploy"),
        ("T", "Trade Ship", "trade"),
    ],
)
def test_core_active_commit_verbs_still_deny_after_the_complete_sweep(key, label, expected_category):
    """The sweep's OWN required invariant (per the dispatch): narrowing
    every blanket pattern to active-verb-conjugation forms must NOT lose
    the core commit-verb coverage itself -- the bare imperative form of
    every one of these still matches and denies."""
    category = menu_crawler.classify_option_label(key, label)
    assert category == expected_category
    assert category in menu_crawler.STATE_CHANGING_KEYS


def test_classify_option_label_ambiguous_is_unknown_not_pressed():
    """An unrecognized label -- not matching ANY safe or deny keyword --
    is deny-by-default, never treated as safe just because it also
    doesn't match a named danger word."""
    assert menu_crawler.classify_option_label("K", "----") == "unknown"
    assert menu_crawler.classify_option_label("Z", "Special Options") == "unknown"
    assert "unknown" not in menu_crawler.SAFE_ALLOWLIST


def test_classify_option_label_bare_enter_is_never_safe():
    """2026-07-19 hardening pass (second re-audit round): `key == ""`
    still returns its own `"bare_enter"` category -- so send_log/the
    recorded edge can still say an Enter transition was discovered --
    but that category is deliberately never a member of SAFE_ALLOWLIST
    anymore, so it is always recorded-not-pressed (see
    test_bare_enter_is_never_emitted_even_on_a_genuine_menu below for
    the full end-to-end proof, and the module docstring's safety-layer
    3 for the residual-breach rationale)."""
    assert menu_crawler.classify_option_label("", "<bare Enter>") == "bare_enter"
    assert "bare_enter" not in menu_crawler.SAFE_ALLOWLIST


def test_classify_option_label_bare_question_mark_is_help():
    assert menu_crawler.classify_option_label("?", "") == "help"


def test_bare_quit_is_not_emitted():
    """Finding 4 (2026-07-19 re-audit): a bare "(Q)uit" ends the live
    session outright, and the BFS-via-replay traversal never needs to
    press quit/back to navigate in the first place (it always replays
    from start -- see module docstring). "Quit to Sector" -- an
    ordinary, textbook-benign back-to-parent-menu label -- used to
    classify "quit" (SAFE); it now classifies "unknown" and is never
    emitted, same as every other unrecognized label. `back`/`previous`
    are unaffected (still safe)."""
    assert menu_crawler.classify_option_label("Q", "Quit to Sector") == "unknown"
    assert "quit" not in menu_crawler.SAFE_ALLOWLIST
    assert menu_crawler.classify_option_label("B", "Back") == "back"
    assert menu_crawler.classify_option_label("P", "Previous Menu") == "previous"


def test_classify_option_label_quit_game_carve_out_is_never_safe():
    """A "quit" that ALSO names a full game/session exit (the real
    captured shape in tests/fixtures/game_select_menu.txt: "<Q> Quit
    (Disconnect)") is "unknown", same as every other "quit"-labeled
    option post-Finding-4 -- there is no longer a separate carve-out
    needed to distinguish it from an ordinary back-to-parent-menu quit,
    since NEITHER meaning is ever safe anymore."""
    assert menu_crawler.classify_option_label("Q", "Quit (Disconnect)") == "unknown"
    assert menu_crawler.classify_option_label("Q", "Quit Game") == "unknown"
    assert menu_crawler.classify_option_label("Q", "Log Off") == "unknown"


def test_safe_allowlist_and_state_changing_keys_are_disjoint():
    """Trivially assertable, per the TW-26 dispatch -- also asserted at
    module import time (see menu_crawler.py's module-level assert), so
    this is belt-and-braces documentation of the same guarantee."""
    assert menu_crawler.SAFE_ALLOWLIST & menu_crawler.STATE_CHANGING_KEYS == set()


# -- enumerate_options ---------------------------------------------------------


def test_enumerate_options_bracket_style_glues_key_into_word():
    options, is_menu = menu_crawler.enumerate_options(SCREENS["stardock_main"])
    as_dict = dict(options)
    assert as_dict["V"] == "View Ship Status"
    assert as_dict["L"] == "List Shipyard Inventory"
    assert as_dict["H"] == "Help"
    assert is_menu is True


def test_enumerate_options_bare_enter_only_on_genuine_menu():
    options, is_menu = menu_crawler.enumerate_options(SCREENS["stardock_main"])
    assert ("", "<bare Enter>") in options
    options2, is_menu2 = menu_crawler.enumerate_options(SCREENS["ship_status_view"])
    assert is_menu2 is False
    assert ("", "<bare Enter>") not in options2


def test_enumerate_options_dash_style():
    text = "==-- Trade Wars 2002 --==\nT - Play Trade Wars 2002\nI - Introduction & Help\nX - Exit"
    options, is_menu = menu_crawler.enumerate_options(text)
    as_dict = dict(options)
    assert as_dict["T"] == "Play Trade Wars 2002"
    assert as_dict["I"] == "Introduction & Help"
    assert is_menu is True


def test_enumerate_options_packed_line_does_not_bleed_between_options():
    text = "A StarDock Menu\n(B)uy Ship (V)iew Ship\nMore filler text"
    options, _is_menu = menu_crawler.enumerate_options(text)
    as_dict = dict(options)
    assert as_dict["B"] == "Buy Ship"
    assert as_dict["V"] == "View Ship"


def test_enumerate_options_single_line_inline_confirmation_not_a_menu():
    """classify.py's own established false-positive case: an inline
    same-line confirmation must not count as a navigable menu (needs
    >=2 DIFFERENT qualifying lines)."""
    text = "Use (N)ew Name or (B)BS Name [B] ?"
    _options, is_menu = menu_crawler.enumerate_options(text)
    assert is_menu is False


def test_enumerate_options_question_mark_key_not_glued():
    options, _is_menu = menu_crawler.enumerate_options("Menu\n(?) Help\n(Q)uit")
    as_dict = dict(options)
    assert as_dict["?"] == "Help"  # not "?Help"


# -- screen_state (screen-level safety classification) ------------------------


def test_screen_state_menu():
    assert menu_crawler.screen_state(SCREENS["stardock_main"], "(Q)uit to Sector") == "menu"


def test_screen_state_unsafe_confirm_prompt():
    assert menu_crawler.screen_state(SCREENS["sneaky_confirm_screen"], "(N)o") == "unsafe"


@pytest.mark.parametrize(
    "text",
    [
        "Buy this ship for 50,000 credits (Y/N)",
        "Are you sure you want to jettison your cargo?",
        "Confirm your order below.",
        "Do you want to attack the enemy vessel?",
        "How many holds of Fuel Ore do you want to buy?",
        "WARNING: you are under attack! Enemies present.",
    ],
)
def test_screen_state_unsafe_patterns(text):
    assert menu_crawler.screen_state(text, text.splitlines()[-1]) == "unsafe"


def test_default_answer_prompt_with_chrome_is_unsafe():
    """Finding 1 (mack's exact adversarial repro, 2026-07-19 re-audit):
    ordinary menu chrome ("(V)iew Ship Status" / "(H)elp") shares the
    screen with a real commit prompt worded to dodge the OLD keyword
    scan -- "[Y]:" has no "/N", and "photon" (singular) dodges the
    "photons" (plural) combat anchor. The OLD whole-screen `is_menu`
    check (>=2 bracket lines exist somewhere) would have misclassified
    this as a navigable menu and offered `bare_enter` on it. The active
    prompt line's trailing "[Y]:" default-answer SHAPE must catch it
    regardless of wording."""
    text = "(V)iew Ship Status\n(H)elp\nFire photon torpedoes now? [Y]:"
    prompt_line = "Fire photon torpedoes now? [Y]:"
    assert menu_crawler.screen_state(text, prompt_line) == "unsafe"


def test_default_answer_prompt_with_full_chrome_and_narrative_is_unsafe():
    """Finding 1 (cipher's exact adversarial repro, 2026-07-19
    re-audit): a full header + (V)iew/(H)elp/(Q)uit chrome block, plus a
    narrative lead-in sentence, precedes the real commit prompt. None of
    this dodges via keyword coincidentally -- "complete this trade" and
    "Proceed? [Yes]" hit no _UNSAFE_SCREEN_PATTERNS keyword at all; only
    the structural trailing "[Yes]" default-answer shape on the active
    prompt line catches it."""
    text = (
        "=== Sol System Command Deck ===\n"
        "(V)iew Ship Status\n"
        "(H)elp\n"
        "(Q)uit to Sector\n"
        "You are about to complete this trade.\n"
        "Proceed? [Yes]"
    )
    prompt_line = "Proceed? [Yes]"
    assert menu_crawler.screen_state(text, prompt_line) == "unsafe"


@pytest.mark.parametrize(
    "text",
    [
        "Deploy how many fighters at this sector [0]:",
        "Torpedo target sector [0]:",
        "Transfer all credits to this player [Y]:",
        "Jettison entire cargo hold [N]:",
        "Self destruct sequence -- proceed [N]:",
        "Enter quantity to buy: ",
    ],
)
def test_screen_state_default_answer_and_free_input_prompts_are_unsafe(text):
    """Finding 1's breadth sweep: every one of these dodges the OLD
    whole-screen keyword scan (no "purchase"/"confirm"/"are you sure"/
    "how many holds or units"/y-n-slash wording), but each is caught
    structurally -- either a trailing square-bracket default-answer
    token, or a free-input solicitation ("Enter ... :")."""
    assert menu_crawler.screen_state(text, text.splitlines()[-1]) == "unsafe"


def test_screen_state_other_leaf_content():
    assert menu_crawler.screen_state(SCREENS["ship_status_view"], "Nothing else to do here.") == "other"


def test_screen_state_login_gate_is_unsafe():
    text = "Please enter your password:"
    assert menu_crawler.screen_state(text, text) == "unsafe"


# -- residual breach, closed by the 2026-07-19 hardening pass ------------------
# (team-lead's second-round review): a bare vertical Y/N-shaped confirm has
# its LAST line be an ordinary bracket-option line, so `_is_menu_select_prompt`
# correctly (by its own narrow rule) still calls it "menu" -- neither
# `_UNSAFE_SCREEN_PATTERNS` nor `_is_commit_shaped_prompt` fire (no "y/n"
# slash, no "confirm" keyword, no trailing square bracket). This is NOT a
# screen_state bug -- the fix lives entirely at the SAFE_ALLOWLIST layer
# (bare_enter is never emittable, full stop), proven below.


@pytest.mark.parametrize(
    "text,prompt_line",
    [
        ("(O)k\n(C)ancel", "(C)ancel"),
    ],
)
def test_vertical_confirm_shapes_still_classify_menu(text, prompt_line):
    """The RESIDUAL class Finding 3's screen-level deny-option check
    (below) does NOT close: `screen_state` still (and correctly, per its
    own contract) classifies this as "menu", because neither "Ok" nor
    "Cancel" classifies to a STATE_CHANGING_KEYS category -- there is no
    deny word for Finding 3 to key off. (The sibling "(Y)es\n(N)o" case
    USED to live in this parametrize list, and so did
    "(A)ccept\n(D)ecline" -- but Finding 3 closes Yes/No at the screen
    level, and the convergence pass's optional "accept" deny word closes
    Accept/Decline the same way -- see
    test_two_option_confirm_with_a_deny_classified_option_is_unsafe below
    -- so neither belongs here anymore.) What still protects "Ok"/
    "Cancel": deny-by-default at the per-option layer (both classify
    "unknown") plus bare_enter never being emittable (the previous
    2026-07-19 hardening pass)."""
    assert menu_crawler.screen_state(text, prompt_line) == "menu"


@pytest.mark.parametrize(
    "text,prompt_line",
    [
        ("(Y)es\n(N)o", "(N)o"),
        ("Proceed?\n(Y)es\n(N)o", "(N)o"),
        ("(A)ccept\n(D)ecline", "(D)ecline"),
    ],
)
def test_two_option_confirm_with_a_deny_classified_option_is_unsafe(text, prompt_line):
    """Finding 3 (2026-07-19 THIRD re-audit round, cipher's exact
    repro): when a screen has EXACTLY 2 qualifying (non-bare_enter)
    option lines and EITHER classifies to a STATE_CHANGING_KEYS category
    ("Yes" -> "confirm", "Accept" -> the convergence pass's optional
    "accept" deny word), the whole screen is unsafe regardless of the
    other line's wording -- this closes the Y/N- and Accept/Decline-
    vertical-confirm shapes independent of `_is_commit_shaped_prompt`'s
    keyword/shape checks."""
    assert menu_crawler.screen_state(text, prompt_line) == "unsafe"


@pytest.mark.parametrize(
    "text",
    [
        "(Y)es\n(N)o",
        "(A)ccept\n(D)ecline",
        "(O)k\n(C)ancel",
    ],
)
def test_vertical_confirm_shapes_never_emit_any_option(text):
    """Since bare_enter is now never in SAFE_ALLOWLIST (2026-07-19
    hardening pass), and "Yes"/"Accept" each deny via their own named
    deny word ("confirm"/"accept") while "No"/"Decline"/"Ok"/"Cancel"
    all classify "unknown" (no deny word, no safe word, no compound) --
    NOTHING discovered on any of these screens, including the synthetic
    bare_enter, is ever emittable, whether or not `screen_state` also
    calls the whole screen "menu" or "unsafe" (see the two tests above:
    Yes/No and Accept/Decline are now BOTH "unsafe"; Ok/Cancel is still
    "menu") -- this per-option guarantee holds regardless."""
    options, is_menu = menu_crawler.enumerate_options(text)
    assert is_menu is True
    assert options  # sanity: this really is a multi-option screen
    for key, label in options:
        category = menu_crawler.classify_option_label(key, label)
        assert category not in menu_crawler.SAFE_ALLOWLIST


def test_bare_enter_is_never_emitted_even_on_a_genuine_menu():
    """`emit_key_if_safe` itself, directly: a bare Enter candidate
    discovered on an otherwise-genuine, screen_state()=="menu" screen is
    never sent -- `session.send()` is never called, `emitted_keys` stays
    empty, and the send_log entry records `emitted: False`. Uses
    "(O)k\n(C)ancel" -- since the THIRD re-audit round, both the Yes/No
    AND Accept/Decline shapes are caught at the screen level (Finding 3
    and the optional "accept" deny word respectively), so neither
    genuinely screen_state()s "menu" anymore; Ok/Cancel still does (see
    test_vertical_confirm_shapes_still_classify_menu)."""
    session = FakeMenuSession({"confirm": "(O)k\n(C)ancel"}, {}, start="confirm")
    emitted_keys, send_log = [], []
    emitted, text, prompt = menu_crawler.emit_key_if_safe(
        session, "confirm", "", "<bare Enter>", "bare_enter", emitted_keys, send_log
    )
    assert emitted is False
    assert text is None and prompt is None
    assert session.sent == []
    assert emitted_keys == []
    assert send_log == [{
        "from_node": "confirm", "key": "", "label": "<bare Enter>",
        "category": "bare_enter", "emitted": False,
    }]


# -- emit_key_if_safe (the chokepoint) -----------------------------------------


def test_emit_key_if_safe_sends_a_safe_category():
    session = FakeMenuSession(dict(SCREENS), dict(TRANSITIONS), start="stardock_main")
    emitted_keys, send_log = [], []
    emitted, text, prompt = menu_crawler.emit_key_if_safe(
        session, "stardock_main", "V", "View Ship Status", "view", emitted_keys, send_log
    )
    assert emitted is True
    assert session.sent == [("V", False, False)]  # enter=False for a real key -- settle.py's own guidance
    assert emitted_keys == ["view"]
    assert text is not None and "Status" in text
    assert send_log == [{
        "from_node": "stardock_main", "key": "V", "label": "View Ship Status",
        "category": "view", "emitted": True,
    }]


def test_emit_key_if_safe_never_sends_a_deny_category():
    session = FakeMenuSession(dict(SCREENS), dict(TRANSITIONS), start="shipyard_menu")
    emitted_keys, send_log = [], []
    emitted, text, prompt = menu_crawler.emit_key_if_safe(
        session, "shipyard_menu", "B", "Buy New Ship", "buy", emitted_keys, send_log
    )
    assert emitted is False
    assert text is None and prompt is None
    assert session.sent == []  # session.send() was NEVER called
    assert emitted_keys == []
    assert send_log == [{
        "from_node": "shipyard_menu", "key": "B", "label": "Buy New Ship",
        "category": "buy", "emitted": False,
    }]


def test_emit_key_if_safe_never_sends_an_unknown_category():
    session = FakeMenuSession(dict(SCREENS), dict(TRANSITIONS), start="stardock_main")
    emitted_keys, send_log = [], []
    emitted, text, prompt = menu_crawler.emit_key_if_safe(
        session, "stardock_main", "K", "----", "unknown", emitted_keys, send_log
    )
    assert emitted is False
    assert session.sent == []
    assert emitted_keys == []


# -- crawl_menus: full end-to-end never-commit proof --------------------------


def test_crawl_menus_enumerates_the_graph_into_game_knowledge(tmp_path):
    path = tmp_path / "game_knowledge.json"
    result = menu_crawler.crawl_menus(_session_factory, path, step_timeout=8.0)

    nodes = {n["signature"]: n for n in game_knowledge.list_menu_nodes(path)}
    edges = game_knowledge.list_menu_edges(path)

    # every safely-reachable screen was upserted as a node
    labels = {n["label"] for n in nodes.values()}
    assert "==-- StarDock Command Menu --==" in labels
    assert "Ye Olde Shipyard -- StarDock Shipyard Menu" in labels
    assert "Merchant Cruiser -- Full Specifications" in labels
    assert "Merchant Cruiser -- Status" in labels
    assert "StarDock Help" in labels
    # "Sector : 4021" ("sector_leaf") is ONLY reachable via
    # stardock_main's "(Q)uit to Sector" option -- post-Finding-4 that
    # option is never pressed (see test_bare_quit_is_not_emitted), so
    # this node is correctly never discovered. This is a POSITIVE proof
    # of the fix, not an incidental gap: updated 2026-07-19 from
    # asserting the opposite.
    assert "Sector : 4021" not in labels
    # the confirm screen is recorded as EXISTING (a legit menu-map fact)...
    assert "Purchase this Merchant Cruiser for 145,000 credits?" in labels
    assert result["nodes_visited"] >= 6


def test_crawl_menus_never_commits_across_the_whole_graph(tmp_path):
    """THE never-commit guarantee, proven trivially per the TW-26
    dispatch: across a full crawl of a graph containing a `[B]uy`
    option, a "Quit (Disconnect)" option, an ambiguous unlabeled option,
    and a SAFE-labeled option that leads to an ACTUAL confirm/purchase
    prompt -- the emitted-keys set stays inside SAFE_ALLOWLIST and
    never touches STATE_CHANGING_KEYS."""
    path = tmp_path / "game_knowledge.json"
    result = menu_crawler.crawl_menus(_session_factory, path, step_timeout=8.0)

    emitted = set(result["emitted_keys"])
    assert emitted <= menu_crawler.SAFE_ALLOWLIST
    assert emitted & menu_crawler.STATE_CHANGING_KEYS == set()

    # No send_log entry categorized as a named danger verb was ever
    # actually emitted -- checked by CATEGORY, never by raw keystroke
    # letter: the same letter ("B") is legitimately "Buy" on the
    # shipyard menu and "Back" on the nested view menu, so a raw-key
    # assertion can't distinguish them (see module docstring) -- only
    # the resolved category can.
    dangerous_emitted = [
        e for e in result["send_log"]
        if e["emitted"] and e["category"] in menu_crawler.STATE_CHANGING_KEYS
    ]
    assert dangerous_emitted == []
    # and no confirm-prompt Y/N answer was ever sent from the sneaky
    # confirm screen specifically (it was never even enumerated).
    confirm_sig = menu_crawler._signature(SCREENS["sneaky_confirm_screen"])
    from_confirm_screen = [e for e in result["send_log"] if e["from_node"] == confirm_sig]
    assert from_confirm_screen == []


def test_crawl_menus_records_buy_option_as_unexplored_never_pressed(tmp_path):
    path = tmp_path / "game_knowledge.json"
    result = menu_crawler.crawl_menus(_session_factory, path, step_timeout=8.0)

    edges = game_knowledge.list_menu_edges(path)
    buy_edges = [e for e in edges if e["desc"] is not None and e["desc"].startswith("buy:")]
    assert len(buy_edges) == 1
    assert buy_edges[0]["to_node"] == menu_crawler.UNEXPLORED_TARGET
    assert buy_edges[0]["kind"] == "action"
    assert "B" not in result["emitted_keys"]
    buy_log_entries = [e for e in result["send_log"] if e["category"] == "buy"]
    assert buy_log_entries and all(e["emitted"] is False for e in buy_log_entries)


def test_crawl_menus_records_quit_disconnect_as_unexplored_never_pressed(tmp_path):
    path = tmp_path / "game_knowledge.json"
    menu_crawler.crawl_menus(_session_factory, path, step_timeout=8.0)

    edges = game_knowledge.list_menu_edges(path)
    disconnect_edges = [e for e in edges if e["desc"] == "unknown: Quit (Disconnect)"]
    assert len(disconnect_edges) == 1
    assert disconnect_edges[0]["to_node"] == menu_crawler.UNEXPLORED_TARGET


def test_crawl_menus_records_ordinary_quit_as_unexplored_never_pressed(tmp_path):
    """Finding 4 regression guard, at the full crawl_menus level: even
    an ordinary, textbook-benign "(Q)uit to Sector" label (stardock_main
    -- NOT the disconnect-flavored one above) is now recorded-not-pressed
    like any other unknown option, and its destination ("sector_leaf")
    is correctly never discovered (see
    test_crawl_menus_enumerates_the_graph_into_game_knowledge)."""
    path = tmp_path / "game_knowledge.json"
    result = menu_crawler.crawl_menus(_session_factory, path, step_timeout=8.0)

    edges = game_knowledge.list_menu_edges(path)
    quit_edges = [e for e in edges if e["desc"] == "unknown: Quit to Sector"]
    assert len(quit_edges) == 1
    assert quit_edges[0]["to_node"] == menu_crawler.UNEXPLORED_TARGET
    assert "quit" not in result["emitted_keys"]


def test_crawl_menus_records_ambiguous_unlabeled_key_as_unexplored(tmp_path):
    path = tmp_path / "game_knowledge.json"
    menu_crawler.crawl_menus(_session_factory, path, step_timeout=8.0)

    edges = game_knowledge.list_menu_edges(path)
    ambiguous_edges = [e for e in edges if e["desc"] == "unknown: ----"]
    assert len(ambiguous_edges) == 1
    assert ambiguous_edges[0]["to_node"] == menu_crawler.UNEXPLORED_TARGET


def test_crawl_menus_backs_out_of_a_screen_that_turns_out_to_be_a_confirm_prompt(tmp_path):
    """The adversarial case: pressing a SAFE-labeled key ("(D)isplay
    Combat Rating") unexpectedly lands on an actual purchase-confirm
    screen. The destination is still recorded as a node (a legitimate
    menu-map fact), but NOTHING is ever pressed FROM it -- no outgoing
    edges, no Y/N in the send-log at all."""
    path = tmp_path / "game_knowledge.json"
    menu_crawler.crawl_menus(_session_factory, path, step_timeout=8.0)

    confirm_sig = menu_crawler._signature(SCREENS["sneaky_confirm_screen"])
    nodes = {n["signature"] for n in game_knowledge.list_menu_nodes(path)}
    assert confirm_sig in nodes  # recorded as existing

    edges = game_knowledge.list_menu_edges(path)
    outgoing_from_confirm = [e for e in edges if e["from_node"] == confirm_sig]
    assert outgoing_from_confirm == []  # never enumerated/pressed from


def test_crawl_menus_root_itself_unsafe_never_presses_anything(tmp_path):
    """Edge case: the world's own start context is already a
    confirm/purchase prompt. The crawler must not enumerate or press
    anything at all -- the safety check applies uniformly to every
    frontier, including the root."""
    screens = {"start": SCREENS["sneaky_confirm_screen"]}
    transitions = {}

    def factory():
        return FakeMenuSession(dict(screens), dict(transitions), start="start")

    path = tmp_path / "game_knowledge.json"
    result = menu_crawler.crawl_menus(factory, path, step_timeout=8.0)

    assert result["emitted_keys"] == []
    assert result["nodes_visited"] == 1
    assert game_knowledge.list_menu_edges(path) == []
    nodes = game_knowledge.list_menu_nodes(path)
    assert len(nodes) == 1  # the root itself is still recorded as existing


def test_crawl_menus_root_yes_no_confirm_is_closed_at_the_screen_level(tmp_path):
    """End-to-end proof of Finding 3 (2026-07-19 THIRD re-audit round):
    a "(Y)es\n(N)o" root now `screen_state()`s as "unsafe" (not "menu"),
    so crawl_menus never even enumerates it -- exactly like any other
    unsafe root (see the sibling
    test_crawl_menus_root_itself_unsafe_never_presses_anything). This is
    a STRONGER guarantee than the previous round's (where this exact
    root screen_state()'d "menu" and relied on deny-by-default plus
    bare_enter exclusion alone) -- see
    test_crawl_menus_root_accept_decline_confirm_is_also_closed_at_the_
    screen_level below for the Accept/Decline sibling (also now closed,
    via the convergence pass's optional "accept" deny word) and
    test_crawl_menus_root_ok_cancel_confirm_never_presses_anything for
    the genuinely still-open residual case."""
    screens = {"confirm_root": "(Y)es\n(N)o"}
    transitions = {}  # nothing SHOULD ever be sent, so nothing to model

    def factory():
        return FakeMenuSession(dict(screens), dict(transitions), start="confirm_root")

    path = tmp_path / "game_knowledge.json"
    result = menu_crawler.crawl_menus(factory, path, step_timeout=8.0)

    assert result["emitted_keys"] == []
    assert result["nodes_visited"] == 1
    assert game_knowledge.list_menu_edges(path) == []  # never enumerated at all
    nodes = game_knowledge.list_menu_nodes(path)
    assert len(nodes) == 1  # the root itself is still recorded as existing


def test_crawl_menus_root_accept_decline_confirm_is_also_closed_at_the_screen_level(tmp_path):
    """Convergence pass: since "accept" was added as an optional deny
    word, "(A)ccept\n(D)ecline" is now ALSO closed by Finding 3 at the
    screen level, the same way Yes/No is -- `screen_state()`s "unsafe",
    crawl_menus never enumerates it, edges stay empty. This USED to be
    the residual case (round 3); it no longer is."""
    screens = {"confirm_root": "(A)ccept\n(D)ecline"}
    transitions = {}

    def factory():
        return FakeMenuSession(dict(screens), dict(transitions), start="confirm_root")

    path = tmp_path / "game_knowledge.json"
    result = menu_crawler.crawl_menus(factory, path, step_timeout=8.0)

    assert result["emitted_keys"] == []
    assert result["nodes_visited"] == 1
    assert game_knowledge.list_menu_edges(path) == []
    nodes = game_knowledge.list_menu_nodes(path)
    assert len(nodes) == 1


def test_crawl_menus_root_ok_cancel_confirm_never_presses_anything(tmp_path):
    """The genuinely still-open residual case: neither "Ok" nor "Cancel"
    classifies to a STATE_CHANGING_KEYS category, so `screen_state`
    still (correctly, per its own contract) calls this root "menu" --
    crawl_menus DOES enumerate it. What still protects it: deny-by-
    default at the per-option layer (both options classify "unknown")
    plus bare_enter never being emittable (the previous 2026-07-19
    hardening pass). Every option is still recorded as an unexplored
    edge; none is ever a real destination."""
    screens = {"confirm_root": "(O)k\n(C)ancel"}
    transitions = {}  # nothing SHOULD ever be sent, so nothing to model

    def factory():
        return FakeMenuSession(dict(screens), dict(transitions), start="confirm_root")

    path = tmp_path / "game_knowledge.json"
    result = menu_crawler.crawl_menus(factory, path, step_timeout=8.0)

    assert result["emitted_keys"] == []
    assert result["nodes_visited"] == 1  # root only -- nothing new was ever discovered
    assert all(not e["emitted"] for e in result["send_log"])

    edges = game_knowledge.list_menu_edges(path)
    assert edges  # Ok, Cancel, and bare_enter were all discovered candidates
    assert all(e["to_node"] == menu_crawler.UNEXPLORED_TARGET for e in edges)


def test_crawl_menus_bare_enter_edge_uses_enter_sentinel_key(tmp_path):
    """`upsert_menu_edge` requires a non-empty `key` string -- a bare
    Enter (`""`) must never be passed to it directly. 2026-07-19
    hardening pass: bare_enter is now NEVER emitted (see
    test_bare_enter_is_never_emitted_even_on_a_genuine_menu), so every
    "<enter>"-keyed edge discovered across a whole crawl is now always
    the recorded-not-pressed shape -- `to_node == UNEXPLORED_TARGET`,
    never a real destination."""
    path = tmp_path / "game_knowledge.json"
    menu_crawler.crawl_menus(_session_factory, path, step_timeout=8.0)

    edges = game_knowledge.list_menu_edges(path)
    enter_edges = [e for e in edges if e["key"] == "<enter>"]
    assert enter_edges  # at least one bare-Enter probe happened somewhere
    assert all(e["to_node"] == menu_crawler.UNEXPLORED_TARGET for e in enter_edges)
    assert "bare_enter" in {menu_crawler.classify_option_label("", "x")}  # sanity on category name


def test_crawl_menus_respects_max_nodes_rail(tmp_path):
    path = tmp_path / "game_knowledge.json"
    result = menu_crawler.crawl_menus(_session_factory, path, max_nodes=1, step_timeout=8.0)
    assert result["nodes_visited"] == 1


# -- end-to-end adversarial fixture (2026-07-19 re-audit, Findings 1/2/4) -----
# A second, purpose-built graph -- distinct from SCREENS/TRANSITIONS above --
# combining all three re-audited findings in one crawl: a safe-labeled
# option ("(D)isplay Reactor Core") that unexpectedly lands on a
# commit-shaped screen wearing ordinary menu chrome (Finding 1, mirrors
# cipher's exact repro); a same-screen option with a compound label whose
# clauses are each individually safe-sounding ("View and Examine
# Engines" -- Finding 2, with no deny word to also catch it); and the
# ordinary "(Q)uit to Sector" option present throughout (Finding 4).

ADV_SCREENS = {
    "adv_main": (
        "Sol System Command Deck\n"
        "(V)iew Ship Status\n"
        "(H)elp\n"
        "(D)isplay Reactor Core\n"
        "(U) View and Examine Engines\n"
        "(Q)uit to Sector"
    ),
    "adv_view_status": "Merchant Cruiser -- Status\nHull: 100%\nNothing else to do here.",
    "adv_help": "Sol System Help\nNothing else to do here.",
    "adv_reactor_trap": (
        "Sol System Command Deck\n"
        "(V)iew Ship Status\n"
        "(H)elp\n"
        "(Q)uit to Sector\n"
        "You are about to complete this trade.\n"
        "Proceed? [Yes]"
    ),
}

ADV_TRANSITIONS = {
    ("adv_main", "V"): "adv_view_status",
    ("adv_main", "H"): "adv_help",
    ("adv_main", "D"): "adv_reactor_trap",
    # Deliberately NO transitions for "U" (compound label, never
    # pressed) or "Q" (quit, never pressed) -- same precedent as
    # TRANSITIONS above: the crawler must never send them in the first
    # place, so there is nothing for these to model.
}


def _adversarial_session_factory():
    return FakeMenuSession(dict(ADV_SCREENS), dict(ADV_TRANSITIONS), start="adv_main")


def test_crawl_menus_never_emits_bare_enter_on_a_commit_shaped_screen(tmp_path):
    """End-to-end adversarial proof required by the TW-26 re-audit
    dispatch: across a full crawl of ADV_SCREENS/ADV_TRANSITIONS --
    emitted keys stay inside SAFE_ALLOWLIST and out of
    STATE_CHANGING_KEYS (as `test_crawl_menus_never_commits_across_the_
    whole_graph` already proves for the original graph), AND -- the crux
    of Finding 1 -- nothing at all, including a bare Enter, is ever sent
    FROM the commit-shaped "adv_reactor_trap" screen, even though it was
    reached via a legitimately safe-classified option label."""
    path = tmp_path / "adversarial_knowledge.json"
    result = menu_crawler.crawl_menus(_adversarial_session_factory, path, step_timeout=8.0)

    emitted = set(result["emitted_keys"])
    assert emitted <= menu_crawler.SAFE_ALLOWLIST
    assert emitted & menu_crawler.STATE_CHANGING_KEYS == set()

    # "(D)isplay Reactor Core" was legitimately safe -- it IS pressed,
    # proving this is a genuine trap-door case (Finding 1's own gate is
    # what saves it), not an option that was already denied at layer 1.
    display_entries = [e for e in result["send_log"] if e["label"] == "Display Reactor Core"]
    assert display_entries and all(e["emitted"] is True for e in display_entries)

    # nothing -- including bare_enter -- was ever sent FROM the trap
    # screen itself: `screen_state` refused to enumerate it at all.
    trap_sig = menu_crawler._signature(ADV_SCREENS["adv_reactor_trap"])
    from_trap = [e for e in result["send_log"] if e["from_node"] == trap_sig]
    assert from_trap == []

    # Finding 2: the compound label is recorded-not-pressed even though
    # neither of its clauses hits a _DENY_LABEL_PATTERNS word.
    compound_entries = [e for e in result["send_log"] if e["label"] == "View and Examine Engines"]
    assert compound_entries and all(e["emitted"] is False for e in compound_entries)

    # Finding 4: the ordinary "(Q)uit to Sector" option is never pressed.
    quit_entries = [e for e in result["send_log"] if e["label"] == "Quit to Sector"]
    assert quit_entries and all(e["emitted"] is False for e in quit_entries)

    # 2026-07-19 hardening pass (safety layer 3): a bare_enter candidate
    # is discovered on every genuine menu in this graph (adv_main,
    # adv_view_status/adv_help are leaf "other" screens with none) --
    # but it is NEVER emitted anywhere across the whole crawl.
    bare_enter_entries = [e for e in result["send_log"] if e["category"] == "bare_enter"]
    assert bare_enter_entries and all(e["emitted"] is False for e in bare_enter_entries)
    assert "bare_enter" not in result["emitted_keys"]
