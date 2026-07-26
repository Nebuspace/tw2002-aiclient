"""MT-06 / WO-ASCII-ENCODE-HONESTY — argparse help/epilog must stay ASCII.

``tw --help`` prints every reachable ``help=`` / epilog / description through
the terminal's own codec. A single ★ / em-dash / … raises
``UnicodeEncodeError`` on ascii/latin-1 instead of printing help.

``KNOWN_NON_ASCII_HELP`` is the parking bay for *temporary* debt only. It
must stay empty once §B / WO-ASCII-ENCODE-HONESTY has scrubbed product help
to ASCII twins (``--`` / ``*`` / ``...``). A non-empty bay means a regression
or a new offender parked without a ruling.
"""

from __future__ import annotations

from tw2002_aiclient.session import cli

# Empty after WO-ASCII-ENCODE-HONESTY. Do not re-bank product strings here —
# scrub at the ``help=`` site or open a new WO.
KNOWN_NON_ASCII_HELP: frozenset[str] = frozenset()


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
    """Every argparse help/epilog/description is ASCII (bay empty)."""
    inventory = list(_parser_text_inventory(cli.build_parser()))
    assert inventory, "parser inventory empty -- walk is broken"

    offenders = [(path, kind, text) for path, kind, text in inventory if not text.isascii()]
    unexpected = [(p, k, t) for p, k, t in offenders if t not in KNOWN_NON_ASCII_HELP]
    assert unexpected == [], (
        "non-ASCII argparse text — scrub at help= (ASCII twin) or bank only "
        f"with an open Max/§B ruling: {unexpected!r}"
    )

    seen = {t for _, _, t in offenders}
    missing_known = KNOWN_NON_ASCII_HELP - seen
    assert not missing_known, (
        "KNOWN_NON_ASCII_HELP entry gone from parser — remove from allowlist "
        f"(product scrub or rename): {missing_known!r}"
    )


def test_format_help_encodes_as_ascii():
    """``tw --help`` must not UnicodeEncodeError under PYTHONIOENCODING=ascii."""
    help_text = cli.build_parser().format_help()
    help_text.encode("ascii")  # raises on regression
    assert "menumap" in help_text
    assert "\u2605" not in help_text
