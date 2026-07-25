"""MT-06 / WO-MT-06-HELP-ASCII-INVENTORY — argparse help/epilog ASCII pin.

``tw --help`` dies under ``PYTHONIOENCODING=ascii`` when any reachable
``help=`` / epilog / description carries ★ / em-dash / …. Attach already
has a function-local ASCII pin; this module covers the **whole** parser
tree from ``build_parser()``.

Until Max rules the CLI-ASCII write-choke (MT-05), product strings are
**not** silently scrubbed. Current tip still has known non-ASCII help
strings — they live in ``KNOWN_NON_ASCII_HELP`` so a *new* offender fails
this suite while the banked ones stay visible for the product WO.

``KNOWN_NON_ASCII_HELP`` is a **PARKING BAY, not an accepted state.** Every
string in it is a live ``tw --help`` crash under ``PYTHONIOENCODING=ascii``
that is being *tolerated pending the open glyph ruling* (MT-05) — it is
debt, deliberately parked and deliberately visible, never a design decision
that these strings may carry non-ASCII. A green run of this suite therefore
means "no NEW offenders", **not** "help is ASCII-clean". The bay is
discharged by shrinking it to empty once Max rules; if it is still
non-empty when you read this, the ruling is still open.

Scale note: the bay holds **3 distinct strings** covering **4 parser
occurrences** — the ``--secret`` help text is attached to both the ``do``
and ``send`` subcommands, so entry count and offender count legitimately
differ. Do not "fix" that mismatch by adding a duplicate entry.
"""

from __future__ import annotations

from tw2002_aiclient.session import cli

# Exact strings measured on origin tip d338409 (do not silent-scrub product).
# When MT-05 / Max glyph ruling lands, shrink this set to empty.
KNOWN_NON_ASCII_HELP = frozenset(
    {
        "password entry — never persisted to the transcript log",
        "screen only — omit prompt/class/settled footer",
        "world_id slug under state/world/ (joins …/game_knowledge.json)",
    }
)


def _parser_text_inventory(parser, path="(root)"):
    """Yield (path, kind, text) for every operator-facing argparse string."""
    desc = getattr(parser, "description", None)
    if isinstance(desc, str) and desc:
        yield path, "description", desc
    epilog = getattr(parser, "epilog", None)
    if isinstance(epilog, str) and epilog:
        yield path, "epilog", epilog
    for action in getattr(parser, "_actions", []):
        help_text = getattr(action, "help", None)
        if isinstance(help_text, str) and help_text:
            label = action.dest or ",".join(action.option_strings) or "?"
            yield f"{path}:{label}", "help", help_text
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            for name, sub in choices.items():
                sub_path = name if path == "(root)" else f"{path}/{name}"
                yield from _parser_text_inventory(sub, sub_path)


def test_build_parser_help_strings_are_ascii_or_known_banked():
    """New non-ASCII help/epilog fails here before operators hit MT-05 crash."""
    inventory = list(_parser_text_inventory(cli.build_parser()))
    assert inventory, "parser inventory empty -- walk is broken"

    offenders = [(path, kind, text) for path, kind, text in inventory if not text.isascii()]
    unexpected = [(p, k, t) for p, k, t in offenders if t not in KNOWN_NON_ASCII_HELP]
    assert unexpected == [], (
        "new non-ASCII argparse text (not in KNOWN_NON_ASCII_HELP) — "
        f"bank it in STATUS for Max/MT-05 or wait for glyph ruling: {unexpected!r}"
    )

    seen = {t for _, _, t in offenders}
    missing_known = KNOWN_NON_ASCII_HELP - seen
    assert not missing_known, (
        "KNOWN_NON_ASCII_HELP entry gone from parser — remove from allowlist "
        f"(product scrub or rename): {missing_known!r}"
    )


def test_format_help_still_exposes_the_menumap_star_hole():
    """Anti-vacuity + banked surface: format_help() still cannot encode ascii.

    Measured tip carries U+2605 (★) in menumap coverage output wiring that
    reaches ``format_help`` / top-level help. When MT-05 closes the choke,
    flip this to ``encode('ascii')`` success (or delete).
    """
    help_text = cli.build_parser().format_help()
    assert "\u2605" in help_text, "expected menumap ★ still in format_help (banked MT-05 hole)"
    try:
        help_text.encode("ascii")
    except UnicodeEncodeError:
        return
    raise AssertionError(
        "format_help() is now pure ASCII — remove this banked-hole pin and "
        "tighten test_build_parser_help_strings_are_ascii_or_known_banked"
    )
