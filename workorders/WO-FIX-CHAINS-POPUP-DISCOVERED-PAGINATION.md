Goal:        Give the L)chains "Discovered profit chains" popup a windowed viewport
             so a large discovered set (live-witnessed: 19,484 cycles) is navigable
             and doesn't format every row per draw tick.
Scope:       tw2002_aiclient/cockpit/chains.py (ChainsSession — add scroll-offset
             concept keeping selected_index visible) + chain_search_view.py
             (format_profit_chain_lines — accept/honor a window slice) + the draw
             call site in screens.py. Add a "showing N of M" indicator.
Constraints: Display-only — no send path, no change to discovery/ranking/arm logic.
             Selection semantics unchanged (same chain arms as before, just now
             visible/reachable). Keep the taught-vs-discovered section split intact.
Accept:      With >box-height discovered chains: pressing down past the fold scrolls
             the window (selected row always drawn), a "showing N of M" indicator
             renders, and only the visible slice is formatted per frame (not all M).
             A small set (< box height) renders unchanged.
Proof:       RTL/PTY or unit test over ChainsSession.move + the formatter with a
             synthetic 200-chain payload asserting the visible window tracks the
             cursor and the formatted-line count is bounded by box height. live-prove: n/a.
Refs:        chain_search_view.py:170-233 · cockpit/chains.py:274-326 · draw.py draw_lines ·
             screens.py:2211-2234 · workorders/WO-LIVE-WITNESS-FIRST-TRADE-LOOP.md:24 · catalog #32.
