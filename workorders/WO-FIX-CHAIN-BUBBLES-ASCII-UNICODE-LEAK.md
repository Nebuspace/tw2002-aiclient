Goal:        Make chain-route bubbles honor ascii mode like every other box border,
             so an ascii-only terminal stops leaking unicode box-drawing glyphs.
Scope:       tw2002_aiclient/cockpit/chain_bubbles.py — route its hardcoded glyphs
             (_CHAIN_CONNECTOR "═════", "╭"/"─"/"╮" corners) through the same
             unicode_ok() switch draw.py already uses. Test.
Constraints: Rendering-only — no change to bubble content, layout math, or chain
             logic. Match the exact ascii fallbacks the rest of the app uses (draw.py
             convention), don't invent new ascii glyphs.
Accept:      With ascii mode on (TW2002_ASCII=1 / unicode_ok() false), chain bubbles
             draw ascii corners/connectors matching the main GAME box; with unicode
             on, output is byte-identical to today. The failing
             test_ascii_twin_full_tier_game_box_ascii_corners_no_unicode_leak passes.
Proof:       That PTY test green + a unit assertion that chain_bubbles emits no
             unicode box glyphs under ascii mode. Full suite green. live-prove: n/a.
Refs:        chain_bubbles.py:18,159 · draw.py:124 (unicode_ok) ·
             test_cockpit_viewport_pty.py:490-505 · catalog #21.
