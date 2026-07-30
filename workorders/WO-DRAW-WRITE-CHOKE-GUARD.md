# WO-DRAW-WRITE-CHOKE-GUARD

## Goal

Enforce the product's single hardened curses-write path so future screens
cannot bypass `cockpit.draw.safe_write` and send unsanitized remote content
directly to a terminal window.

## Scope

- `tests/test_draw_write_chokepoint.py`

## Constraints

- Tests only. Do not modify product code, UI, canon, dependencies, or runtime.
- Treat preserved commit `719cc30` as reviewable evidence, not pre-approved
  output. Inspect it against current `main`; keep, revise, or rebuild the test
  as evidence requires.
- Scan the current `tw2002_aiclient` Python tree for direct curses glyph-write
  methods and write-named reflection. The sole sanctioned direct call must
  remain inside `cockpit/draw.py::safe_write`.
- Include positive controls proving the scanner reaches the real product tree
  and detects representative direct/reflected violations. A clean result from
  a vacuous scanner is a failure.
- Keep the claim honest: this is a structural drift tripwire, not a sandbox
  against deliberately computed/dynamic attribute names.
- Avoid brittle exact product-file counts and unrelated reflection bans.

## Accept

1. The current product tree reports exactly one direct curses write, located
   in `cockpit/draw.py::safe_write`, and no write-named reflective bypass.
2. Scanner meta-tests detect at least direct `addstr`, another supported
   curses write method, literal reflection, and module-constant reflection.
3. The scan proves it inspected a non-empty/current product population and
   reports actionable file/function/line locations on failure.
4. Ordinary non-write reflection does not trigger the guard.
5. The focused test and full offline suite pass on current `main`.

## Proof

```bash
pytest -q tests/test_draw_write_chokepoint.py
pytest -q tests
```

Live prove is `n/a`: this adds an offline structural regression guard and
does not change product/runtime behavior.

## Refs

- `tw2002_aiclient/cockpit/draw.py::safe_write`
- `tests/test_safe_addstr_choke.py`
- `tests/test_menu_crawl_chokepoint.py` (house scanner idiom)
- Preserved, unmerged evidence: `719cc30`
- Depends on `main` @ `1ed5081`
