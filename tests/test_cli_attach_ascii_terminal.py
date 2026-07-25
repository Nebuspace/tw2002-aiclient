"""D1 -- `tw attach` must not die on the terminals it exists to serve.

`cmd_attach`'s ATTACHED banner carried a U+2014 EM DASH. On an 8-bit or
ascii stdout that `print()` raises `UnicodeEncodeError`, so attach died at
the banner: rc 1, a traceback, and not one keystroke delivered. The
terminals where this fires are not exotic -- a latin-1 locale is precisely
the environment an 8-bit TradeWars host is played from.

The sharp part is that the fix for the *neighbouring* defect already knew
this. The unencodable-key notice thirty lines below was deliberately built
pure-ASCII, with a correct five-line rationale ("it must not itself depend
on the terminal rendering a non-ASCII character") -- while the banner above
it stayed lethal on exactly those terminals. The mitigation sat downstream
of the failure it was designed for. So the guard here is a PROPERTY over
the whole function, not an assertion about one line: a hand-checked line is
what produced this bug.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.attach_terminal_harness import (  # noqa: F401  (fixture import)
    CBREAK_MARKER,
    attach_daemon,
    run_attach_on_terminal,
)
from tw2002_aiclient.session import cli

DETACH = bytes([29])  # Ctrl-]

# The encodings under which our own output is lethal if it is not ASCII.
# `LC_ALL=C` is deliberately NOT here: measured on this interpreter, PEP
# 540 turns UTF-8 mode ON for a C/POSIX locale, so stdout stays utf-8 and
# the em-dash survives. Asserting a crash there would have been a test
# that passes for the wrong reason on one machine and fails on another.
LETHAL_STDOUT_ENV = [
    pytest.param({"PYTHONIOENCODING": "latin-1"}, id="latin-1"),
    pytest.param({"PYTHONIOENCODING": "ascii"}, id="ascii"),
    pytest.param({"LC_ALL": "en_US.ISO8859-1"}, id="iso8859-1-locale"),
    pytest.param({"LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"},
                 id="true-C-locale-no-utf8-mode"),
]


# -- the property: every operator-facing string in cmd_attach is ASCII ------

def _string_constants(func_name):
    """Every `str` constant in `func_name`'s AST subtree, with its line."""
    tree = ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return [
                (child.lineno, child.value)
                for child in ast.walk(node)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            ]
    raise AssertionError(f"{func_name} not found in {cli.__file__}")


def test_every_string_in_cmd_attach_is_ascii():
    """The property, stated over the function rather than over the banner.

    Deliberately includes the docstring: an exception list is a place for
    the next non-ASCII string to hide, and "every str constant here is
    ASCII" is a rule that cannot be satisfied by accident.
    """
    constants = _string_constants("cmd_attach")
    assert constants, "no string constants found -- the AST walk is broken"
    offenders = [
        (lineno, [f"U+{ord(c):04X}" for c in value if not c.isascii()])
        for lineno, value in constants
        if not value.isascii()
    ]
    assert offenders == [], (
        f"non-ASCII string(s) in cmd_attach at cli.py {offenders} -- these "
        "raise UnicodeEncodeError and kill attach on an 8-bit terminal"
    )


def test_the_ascii_guard_would_catch_a_regression():
    """Anti-vacuity: prove the guard above can FAIL. A property test that
    cannot fail certifies nothing, and this one is a pure-ASCII assertion
    over source text -- the easiest kind to write in an always-true shape.
    Runs the identical predicate over a function known to carry an em-dash
    (`cmd_watch`'s docstring) and requires it to trip.
    """
    offenders = [
        lineno for lineno, value in _string_constants("cmd_watch")
        if not value.isascii()
    ]
    assert offenders, (
        "cmd_watch no longer has a non-ASCII string, so this anti-vacuity "
        "check is inert -- repoint it at another non-ASCII site, or drop it "
        "if cli.py became ASCII-only file-wide"
    )


def _attach_help_strings():
    """Every help string `tw --help` / `tw attach --help` can print FOR THE
    ATTACH VERB: the subparser's own one-liner (which argparse keeps as a
    pseudo-action on the `_SubParsersAction`, NOT on the child parser) plus
    each of its arguments'.

    The distinction is load-bearing and cost this test a first draft: reading
    only `choices["attach"]._actions` collects `--keys`/`--run-dir`/`-h`,
    which were already ASCII, so the test passed against the unfixed tree
    while the em-dash it was written for sat untouched on the `add_parser(...,
    help=...)` line. Verified by running it red.
    """
    parser = cli.build_parser()
    subparsers_action = next(
        a for a in parser._actions if hasattr(a, "choices") and a.choices
    )
    helps = [
        pseudo.help
        for pseudo in subparsers_action._choices_actions
        if pseudo.dest == "attach" and pseudo.help
    ]
    assert helps, "no help entry found for the `attach` subparser"
    helps += [a.help for a in subparsers_action.choices["attach"]._actions if a.help]
    return helps


def test_the_attach_verbs_help_strings_are_ascii():
    """`tw attach --help` and `tw --help` both print these, on the same
    terminals. Fixing the banner while leaving the verb's own help text
    lethal would repeat the exact irony this WO is about."""
    non_ascii = [h for h in _attach_help_strings() if not h.isascii()]
    assert non_ascii == [], f"non-ASCII in attach's help output: {non_ascii}"


def test_the_help_string_check_actually_reaches_the_subparser_one_liner():
    """Anti-vacuity for the test above: prove the collected set really does
    include the `add_parser(..., help=...)` one-liner, not just the
    arguments' help. Without this, the check silently narrows again."""
    helps = _attach_help_strings()
    assert any("take the keyboard" in h for h in helps), (
        f"the attach subparser's own help one-liner is not being checked: {helps}"
    )


# -- the behaviour: a real attach on a real 8-bit terminal -----------------

@pytest.mark.parametrize("env_overrides", LETHAL_STDOUT_ENV)
def test_attach_survives_the_banner_on_a_non_utf8_terminal(
    attach_daemon, tmp_path, env_overrides
):
    """RED before the fix: rc 1, `UnicodeEncodeError` in the output, the
    cbreak spy's marker never reached (attach died at the banner, before
    it ever took the keyboard), and the daemon received nothing.

    Note what is gated on what: injection waits for the SETCBREAK marker,
    not for the banner. Waiting on the banner would be doubly wrong here --
    `setcbreak`'s TCSAFLUSH would discard the key, and on these very
    terminals the banner is the thing that may not print.
    """
    rc, out, armed = run_attach_on_terminal(
        attach_daemon, tmp_path, env_overrides=env_overrides, keys=b"a" + DETACH
    )

    assert "UnicodeEncodeError" not in out, out
    assert "Traceback" not in out, out
    assert armed, (
        "attach never reached tty.setcbreak -- it died before taking the "
        f"keyboard, which is the banner crash itself. Output: {out!r}"
    )
    assert rc == 0, out
    assert attach_daemon.session.raw_sent == [b"a"], (
        "the operator's keystroke must reach the daemon on this terminal"
    )


@pytest.mark.parametrize("env_overrides", LETHAL_STDOUT_ENV)
def test_the_banner_itself_is_printed_on_a_non_utf8_terminal(
    attach_daemon, tmp_path, env_overrides
):
    """Not merely "did not crash": the operator is actually told they are
    attached. A fix that suppressed the banner on these terminals would
    pass the test above and still leave the pilot flying blind."""
    rc, out, armed = run_attach_on_terminal(
        attach_daemon, tmp_path, env_overrides=env_overrides, keys=DETACH
    )

    assert armed, out
    assert "ATTACHED" in out, out
    assert "Ctrl-] detach" in out, out
    assert rc == 0
