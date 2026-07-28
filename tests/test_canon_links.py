"""WO-CANON-LINK-FIX — every cross-reference in `canon/` resolves to a real file.

**Why this needs a test rather than a careful pass.** A markdown link has no
compiler. A concept can move directory, or be split into several concepts under
new names, and every pointer to the old path keeps rendering as an ordinary
link — it just goes nowhere. That is how `canon/` accumulated 8 dead links
across three different faults (a missing directory, a wrong directory, and a
placeholder name that was never written at all) without anything noticing.

Fixing those 8 without this test would leave the *class* untouched: the next
concept that moves regrows them, and the closed work order reads as though the
problem was handled.

**The positive control is not decoration.** A resolver whose pattern silently
matches nothing reports a perfectly clean tree — indistinguishable from success.
So `test_the_scanner_can_actually_see_links` asserts the scan finds a known-good
link of *each* form it claims to check.

It does **not**, however, gate anything. Pytest tests are independent; a control
that fails cannot stop a sibling from passing. That was measured, not assumed:
with `canon/` renamed away, `test_every_canon_link_resolves` PASSED (an empty
scan makes "no broken links" vacuously true) while the control failed — green
and red side by side, asserting opposite things about the same tree. So each
test below carries its own non-vacuity assertion, and the control is a second
opinion rather than a gate.
"""

from __future__ import annotations

import pathlib
import re

CANON = pathlib.Path(__file__).resolve().parent.parent / "canon"

#: Every in-bundle `.md` cross-reference, in both forms the bundle actually uses:
#:
#:   root-relative  `[World Model](/engine/world-model.md)`  -> `canon/engine/world-model.md`
#:   relative       `[ADR-001](001-one-tree-embedded-session.md)` -> sibling of the source file
#:
#: Root-relative is the house convention and is nearly all of them, but
#: `canon/ADR/index.md` links its ADRs as siblings. Checking only the house
#: convention would leave those two silently unverified -- and an unchecked
#: form is where the next dead link hides, since nothing complains.
#:
#: Out of scope, deliberately: same-page anchors (`](#heading)`) and external
#: URLs (`](https://...)`), neither of which names a file in this tree.
_LINK_RE = re.compile(r"\]\((?!https?:)([^)#\s]*\.md)(?:#[^)\s]*)?\)")


def _canon_files():
    return sorted(CANON.rglob("*.md"))


def _resolve(source, target):
    """Where `target`, written in `source`, is supposed to land."""
    if target.startswith("/"):
        return CANON / target.lstrip("/")
    return source.parent / target


def _links():
    """(source_file, raw_target, line_no, resolved_path) for every .md link."""
    out = []
    for path in _canon_files():
        for n, line in enumerate(path.read_text().splitlines(), 1):
            for m in _LINK_RE.finditer(line):
                target = m.group(1)
                out.append((path, target, n, _resolve(path, target)))
    return out


def test_the_scanner_can_actually_see_links():
    """Positive control. A broken pattern and a clean tree print identically,
    so prove the scan finds something real before trusting that it found no
    breakage.

    Deliberately NOT guarded by `skipif(not CANON.is_dir())`. `canon/` is
    tracked at the repo root, so there is no legitimate tree -- checkout or
    worktree -- where it is absent. Such a guard could therefore only ever fire
    on a catastrophe (the doc root gone), and its effect would be to turn that
    catastrophe into three quiet skips inside a green suite. Let it fail loudly.
    """
    assert CANON.is_dir(), (
        f"canon/ is missing at {CANON} -- the doc root is gone; this is not a "
        "reason to skip the link checks"
    )
    links = _links()
    assert links, "the link scan found NOTHING -- the pattern is broken, not the tree clean"
    targets = {t for _, t, _, _ in links}
    assert "/engine/world-model.md" in targets, (
        "the scan missed a link known to exist in this bundle; its 'no broken "
        "links' verdict would be meaningless"
    )
    # Both link FORMS, not just both being non-empty. The relative form is a
    # two-link minority in this bundle, so a pattern that quietly dropped it
    # would still look healthy on the count alone.
    assert any(not t.startswith("/") for t in targets), (
        "the scan saw no relative links, but canon/ADR/index.md writes its ADR "
        "links as siblings -- that whole form is going unchecked"
    )


def test_every_canon_link_resolves():
    # Non-vacuity, checked here rather than relying on the positive control
    # above. The two are separate tests, so nothing makes the control *gate*
    # this one -- and an empty scan makes `broken` empty, which reads as a
    # clean tree. (Observed: with `canon/` renamed away this test passed while
    # the control failed. Green next to red, saying opposite things.)
    links = _links()
    assert links, "the link scan found NOTHING -- this result is vacuous, not clean"
    broken = []
    for path, target, lineno, resolved in links:
        if not resolved.is_file():
            broken.append(f"{path.relative_to(CANON.parent)}:{lineno} -> {target}")
    assert not broken, "canon links pointing at files that do not exist:\n  " + "\n  ".join(
        sorted(broken)
    )


def test_index_lists_only_concepts_that_exist():
    """`index.md` is the bundle's entry point, so a dead link there sends a
    reader looking for a concept that is not merely misfiled but absent.
    Checked separately from the sweep above so the failure names the index."""
    index = CANON / "index.md"
    assert index.is_file(), "canon/index.md is missing"
    missing = [
        m.group(1)
        for m in _LINK_RE.finditer(index.read_text())
        if not _resolve(index, m.group(1)).is_file()
    ]
    assert not missing, f"canon/index.md points at concepts that do not exist: {sorted(missing)}"
