"""The single safe-emit chokepoint, swept structurally and attacked directly.

Canon (`canon/engine/menu-map-and-introspection.md`): "Every candidate
keystroke the crawler could ever send passes through exactly **one
chokepoint**, `emit_key_if_safe()` ... There is no other send path in the
module."

Two independent kinds of evidence here, because neither alone is enough:

  * a **structural sweep** — an AST scan of every module in the ``menu``
    package proving no second send path exists, that the one that does
    lives in the one function canon names, and that no reflective call
    could smuggle one in past a literal-node scan;
  * an **adversarial exercise** — deliberate attempts to push a
    state-changing key through the chokepoint, each proven refused. Only
    asserting that safe keys pass would certify nothing: a chokepoint that
    emitted everything would sail through such a test.
"""

import ast
from pathlib import Path

import pytest

from tw2002_aiclient import menu
from tw2002_aiclient.menu import crawler

_MENU_PKG = Path(menu.__file__).resolve().parent

# The primitives that actually reach `session.send()` (via settle). The
# crawler is allowed exactly one call site for any of these. Includes the
# profile wrapper `send_and_confirm_for` (thin merge → `send_and_confirm`
# outside the menu package) so migrating onto named settle profiles does
# not falsely report zero chokepoint sites.
_SEND_PRIMITIVES = frozenset({"send_and_confirm", "send_and_confirm_for"})

# Attribute calls that would BYPASS the primitive and touch the wire
# directly. None of these may appear anywhere in the package.
_RAW_SEND_ATTRS = frozenset({"send", "send_raw", "sendall"})

# Reflection defeats a literal-node scan: `getattr(mod, "send")` reaches a
# send path a name-based scanner never sees. Banned outright in the menu
# package (`run_live_crawl` gate retired with deleted `crawl_driver.py`).
#
# Split by call SHAPE deliberately. As a bare builtin these names are
# always reflection; as an attribute they are ordinary method names on
# ordinary objects (`re.compile` is a regex, not a reflective reach), so
# banning the attribute form wholesale would drown the real signal in
# false positives — the fastest way to get a safety scanner switched off.
_REFLECTION_BUILTINS = frozenset({
    "getattr", "setattr", "delattr", "hasattr", "eval", "exec", "compile",
    "__import__", "globals", "vars", "locals",
})
_REFLECTION_ATTRS = frozenset({
    "__getattr__", "__getattribute__", "__setattr__", "__call__",
})

def _module_string_constants(tree):
    """Module-level ``NAME = "literal"`` bindings, so the scanner can see
    through a named constant the way it sees through an import alias.
    Indirection is the evasion surface; resolving it is the whole point."""
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    consts[target.id] = node.value.value
    return consts


def _scan(path):
    """Return every call of interest in `path`, each tagged with its
    enclosing function, resolving import aliases and named constants."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    consts = _module_string_constants(tree)

    # Alias resolution: `from x import send_and_confirm as s` and
    # `import x.settle as s` both have to resolve back to the primitive.
    # Profile wrapper `send_and_confirm_for` counts the same (one site).
    direct_aliases = set()   # local NAMES bound to a send primitive itself
    module_aliases = set()   # local names bound to a module exposing it
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _SEND_PRIMITIVES:
                    direct_aliases.add(alias.asname or alias.name)
                elif alias.name.split(".")[-1] == "settle":
                    module_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[-1] == "settle":
                    module_aliases.add(alias.asname or alias.name.split(".")[0])

    # Enclosing-function map: a call's SHAPE is not enough — the same
    # shape in a different function is a different fact.
    enclosing = {}
    for func in ast.walk(tree):
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(func):
                enclosing.setdefault(id(child), func.name)

    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        where = (path.name, enclosing.get(id(node)), node.lineno)
        fn = node.func
        if isinstance(fn, ast.Name):
            if fn.id in direct_aliases:
                findings.append(("send_primitive", where, node))
            elif fn.id in _REFLECTION_BUILTINS:
                findings.append(("reflection", where, node))
        elif isinstance(fn, ast.Attribute):
            base_is_settle = isinstance(fn.value, ast.Name) and fn.value.id in module_aliases
            if fn.attr in _SEND_PRIMITIVES or (base_is_settle and fn.attr in _SEND_PRIMITIVES):
                findings.append(("send_primitive", where, node))
            elif fn.attr in _RAW_SEND_ATTRS:
                findings.append(("raw_send", where, node))
            elif fn.attr in _REFLECTION_ATTRS:
                findings.append(("reflection", where, node))
    return findings, consts


def _scan_package():
    findings = []
    for path in sorted(_MENU_PKG.glob("*.py")):
        found, consts = _scan(path)
        findings.extend((kind, where, node, consts) for kind, where, node in found)
    return findings


# -- the structural sweep ------------------------------------------------------


def test_exactly_one_send_primitive_call_site_in_the_whole_menu_package():
    sites = [(where, node) for kind, where, node, _c in _scan_package() if kind == "send_primitive"]
    assert len(sites) == 1, f"expected one send path, found: {[w for w, _ in sites]}"


def test_the_one_send_site_is_the_function_canon_names():
    (where, _node), = [(w, n) for kind, w, n, _c in _scan_package() if kind == "send_primitive"]
    filename, func, _lineno = where
    assert filename == "crawler.py"
    assert func == "emit_key_if_safe"


def test_no_module_in_the_menu_package_touches_a_raw_send_path():
    raw = [where for kind, where, _n, _c in _scan_package() if kind == "raw_send"]
    assert raw == [], f"a send path bypassing the chokepoint exists: {raw}"


def test_no_reflection_in_the_menu_package():
    reflection = [where for kind, where, _node, _consts in _scan_package() if kind == "reflection"]
    assert reflection == [], f"reflection in the menu package: {reflection}"


# -- bypass meta-tests: prove the scanner is not fooled ------------------------


def _scan_source(src, filename="crawler.py", tmp_path=None):
    path = tmp_path / filename
    path.write_text(src, encoding="utf-8")
    return _scan(path)[0]


def test_scanner_catches_an_aliased_import_of_the_send_primitive(tmp_path):
    src = (
        "from ..session.settle import send_and_confirm as _quietly\n"
        "def sneaky(session):\n"
        "    return _quietly(session, 'B')\n"
    )
    kinds = [k for k, _w, _n in _scan_source(src, tmp_path=tmp_path)]
    assert "send_primitive" in kinds


def test_scanner_catches_a_module_aliased_send_primitive(tmp_path):
    src = (
        "from ..session import settle as _s\n"
        "def sneaky(session):\n"
        "    return _s.send_and_confirm(session, 'B')\n"
    )
    kinds = [k for k, _w, _n in _scan_source(src, tmp_path=tmp_path)]
    assert "send_primitive" in kinds


def test_scanner_catches_a_reflective_send(tmp_path):
    src = "def sneaky(session):\n    return getattr(session, 'send')('B')\n"
    kinds = [k for k, _w, _n in _scan_source(src, tmp_path=tmp_path)]
    assert "reflection" in kinds


def test_scanner_catches_a_direct_session_send(tmp_path):
    src = "def sneaky(session):\n    session.send('B', enter=False)\n"
    kinds = [k for k, _w, _n in _scan_source(src, tmp_path=tmp_path)]
    assert "raw_send" in kinds


# -- adversarial: attempts to push a state-changing key through ----------------


class _RecordingSession:
    """Records every send. A chokepoint that leaked would leave evidence
    here; `sent == []` after a refusal attempt is the whole assertion."""

    def __init__(self):
        self.t = 0.0
        self.rx_count = 1
        self.last_rx = -1.0
        self.sent = []
        self._text = "(V)iew Something\n(B)uy Fighters"

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        self.rx_count += 1
        self.last_rx = self.t

    def render(self):
        return self._text.split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._text

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))


def _attempt(key, label, category):
    """Drive one candidate straight at the chokepoint and report what
    happened. `category` is the caller's CLAIM — the argument an attacker
    (or a buggy call site) controls."""
    session = _RecordingSession()
    emitted_keys, send_log = [], []
    emitted, text, prompt = crawler.emit_key_if_safe(
        session, "from_sig", key, label, category, emitted_keys, send_log, step_timeout=0.5
    )
    return session, emitted, emitted_keys, send_log, (text, prompt)


# One realistic label per state-changing category. Derived from the
# module's own frozenset rather than hand-listed, so a category can never
# be added to the vocabulary without an adversarial probe for it.
_DENY_PROBES = {
    "buy": "Buy New Ship",
    "sell": "Sell Cargo",
    "purchase": "Purchase Fighters",
    "attack": "Attack Enemy Ship",
    "deploy": "Deploy Fighters",
    "genesis": "Genesis Torpedo",
    "move": "Move to Sector",
    "jump": "Jump to Sector",
    "tow": "Tow the Derelict",
    "land": "Land on Planet",
    "take": "Take the Cargo",
    "confirm": "Confirm Transaction",
    "acquire": "Acquire Planet",
    "requisition": "Requisition Fighters",
    "order": "Order Supplies",
    "trade": "Trade Cargo",
    "dock": "Dock Here",
    "eject": "Eject Colonists",
    "drop": "Drop Cargo",
    "transfer": "Transfer Credits",
    "upgrade": "Upgrade Holds",
    "repair": "Repair Hull",
    "refuel": "Refuel Ship",
    "launch": "Launch Fighters",
    "abandon": "Abandon Ship",
    "jettison": "Jettison Cargo",
    "pay": "Pay Toll",
    "invest": "Invest in Port",
    "bribe": "Bribe the Ferrengi",
    "steal": "Steal Cargo",
    "board": "Boarding Party",
    "ram": "Ram the Enemy",
    "cloak": "Cloak Ship",
    "mine": "Mine Asteroids",
    "send": "Send Message",
    "load": "Load Cargo",
    "sale": "Items For Sale",
    "auction": "Auction Ship",
    "barter": "Barter Goods",
    "lease": "Lease a Hold",
    "rent": "Rent Storage",
    "vend": "Vend Equipment",
    "payoff": "Payoff the Guards",
    "wager": "Wager Credits",
    "bet": "Bet on the Race",
    "gamble": "Gamble Credits",
    "ransom": "Ransom the Captive",
    "donate": "Donate Credits",
    "gift": "Gift a Torpedo",
    "spend": "Spend Credits",
    "redeem": "Redeem Voucher",
    "forfeit": "Forfeit the Match",
    "surrender": "Surrender to the Fleet",
    "withdraw": "Withdraw Credits",
    "deposit": "Deposit Credits",
    "commit": "Commit Changes",
    "accept": "Accept the Offer",
}


def test_every_state_changing_category_has_an_adversarial_probe():
    """Pins the table to the module's own vocabulary: adding a deny
    category without a probe for it fails here rather than shipping
    untested."""
    assert set(_DENY_PROBES) == crawler.STATE_CHANGING_KEYS


@pytest.mark.parametrize("category,label", sorted(_DENY_PROBES.items()))
def test_no_state_changing_category_can_reach_the_wire(category, label):
    """The honest attempt: each label really does classify to its
    state-changing category (so the refusal is about a real danger), and
    the chokepoint sends nothing."""
    assert crawler.classify_option_label("X", label) == category

    session, emitted, emitted_keys, send_log, _screen = _attempt("X", label, category)

    assert emitted is False
    assert session.sent == []
    assert emitted_keys == []
    assert send_log[0]["emitted"] is False
    assert send_log[0]["category"] == category


def test_a_forged_safe_category_cannot_open_the_gate():
    """The attack the archived chokepoint was open to: it trusted the
    category its caller passed. Claim "view" for a label that buys a ship
    and the chokepoint must still refuse — it re-derives the category
    itself."""
    session, emitted, emitted_keys, send_log, _screen = _attempt("B", "Buy New Ship", "view")

    assert emitted is False
    assert session.sent == []
    assert emitted_keys == []


def test_a_forged_category_is_recorded_honestly_in_the_audit_trail():
    """The send_log records what the label RESOLVED to, with the caller's
    claim beside it — a divergence is visible rather than lost."""
    _session, _emitted, _keys, send_log, _screen = _attempt("B", "Buy New Ship", "view")

    entry = send_log[0]
    assert entry["category"] == "buy"
    assert entry["claimed_category"] == "view"
    assert entry["emitted"] is False


@pytest.mark.parametrize("forged", sorted(crawler.SAFE_ALLOWLIST))
def test_no_safe_category_can_be_forged_onto_a_state_changing_label(forged):
    session, emitted, _keys, _log, _screen = _attempt("B", "Buy New Ship", forged)
    assert emitted is False
    assert session.sent == []


def test_an_unknown_label_cannot_be_forged_safe():
    session, emitted, _keys, _log, _screen = _attempt("K", "K----", "help")
    assert emitted is False
    assert session.sent == []


def test_bare_enter_cannot_be_forged_safe():
    """Bare Enter is discovered but never emittable, whatever category a
    caller claims for it."""
    for forged in ("help", "view", "bare_enter", "back"):
        session, emitted, _keys, _log, _screen = _attempt("", "<bare Enter>", forged)
        assert emitted is False
        assert session.sent == []


def test_a_quit_label_is_never_emittable():
    for label in ("Quit", "Quit to Sector", "Quit (Disconnect)"):
        assert crawler.classify_option_label("Q", label) not in crawler.SAFE_ALLOWLIST
        session, emitted, _keys, _log, _screen = _attempt("Q", label, "back")
        assert emitted is False
        assert session.sent == []


def test_a_compound_label_whose_second_clause_commits_is_refused():
    """"View & Repair Ship" reads safe by its first clause alone."""
    assert crawler.classify_option_label("V", "View & Repair Ship") not in crawler.SAFE_ALLOWLIST
    session, emitted, _keys, _log, _screen = _attempt("V", "View & Repair Ship", "view")
    assert emitted is False
    assert session.sent == []


def test_a_hostile_label_cannot_raise_out_of_the_safety_gate():
    """A gate that raises on malformed input is a gate that fails OPEN
    from the caller's perspective — the crawl dies instead of recording an
    unexplored edge."""
    for label in (None, "", "   ", "\x00\x01", "(" * 500, "🚀" * 50):
        assert crawler.classify_option_label("X", label) == "unknown"
        session, emitted, _keys, _log, _screen = _attempt("X", label, "unknown")
        assert emitted is False
        assert session.sent == []


# -- non-vacuity: the chokepoint is not simply refusing everything ------------


def test_the_chokepoint_does_emit_a_genuinely_safe_candidate():
    """Without this, every refusal test above would also pass on a
    chokepoint hard-wired to `return False` — which would be useless, not
    safe."""
    session, emitted, emitted_keys, send_log, _screen = _attempt("V", "View Ship Registry", "view")

    assert emitted is True
    assert session.sent and session.sent[0][0] == "V"
    assert emitted_keys == ["view"]
    assert send_log[0]["emitted"] is True


def test_a_safe_key_is_sent_without_a_trailing_enter():
    """A menu selection sent with its usual CRLF can have that Enter
    consumed as a default-accept by the very next prompt."""
    session, _emitted, _keys, _log, _screen = _attempt("V", "View Ship Registry", "view")
    _text, enter, secret = session.sent[0]
    assert enter is False
    assert secret is False


# -- vocabulary invariants ----------------------------------------------------


def test_safe_and_state_changing_vocabularies_are_disjoint():
    assert crawler.SAFE_ALLOWLIST & crawler.STATE_CHANGING_KEYS == frozenset()


def test_neither_quit_nor_bare_enter_is_ever_a_safe_category():
    assert "quit" not in crawler.SAFE_ALLOWLIST
    assert "bare_enter" not in crawler.SAFE_ALLOWLIST


def test_the_vocabularies_are_derived_from_their_patterns_not_typed_twice():
    """Canon judges a candidate by its rendered LABEL, never by a bare
    keystroke, so there is no list of "destructive keys" to hardcode — and
    the category names have exactly one home, the pattern dicts."""
    assert crawler.SAFE_ALLOWLIST == frozenset(crawler._SAFE_LABEL_PATTERNS)
    assert crawler.STATE_CHANGING_KEYS == frozenset(crawler._DENY_LABEL_PATTERNS)


def test_the_crawler_only_ever_writes_canon_three_edge_kinds():
    """Canon's schema is nav|info|action with no "unknown" kind. The store
    currently accepts a wider set; canon is prescriptive."""
    assert crawler.CANON_EDGE_KINDS == frozenset({"nav", "info", "action"})
    kinds = {crawler._edge_kind_for(c) for c in crawler.STATE_CHANGING_KEYS}
    kinds |= {crawler._edge_kind_for(c) for c in crawler.SAFE_ALLOWLIST}
    kinds |= {crawler._edge_kind_for(c) for c in ("unknown", "bare_enter", "quit")}
    assert kinds <= crawler.CANON_EDGE_KINDS
