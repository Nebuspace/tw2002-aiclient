Goal:        Give every trade-chain STOP reason a human label in the STOP banner
             (today they render as raw internal codes), and stop dropping a
             driver-crash's exception class.
Scope:       tw2002_aiclient/cockpit/stopbanner.py (add the ~20 trade_driver
             ChainHold codes + session/trade_chain.py TradeChainRefused codes to
             INTERVENTION_REASON_LABELS) + tw2002_aiclient/app.py's
             _apply_trade_chain_band (read run_wire's "error" field so a crash
             shows the exception class, not just "driver_error"). Tests.
Constraints: Label-only + one field read — no change to stop LOGIC, thresholds,
             or the codes themselves. Same shape as the shipped
             WO-FIX-CONTROL-ESCALATION-STOP-CAUSE-CODES / route-hazard-label WOs.
             Every code gets a label (no silent fallthrough to raw code).
Accept:      Each trade_driver/trade_chain stop code renders a human label in the
             banner (parametrized codes like credit_delta_anomaly:2:buy:Equipment
             render a readable form, not the raw string); a driver crash surfaces
             the exception class; a table test asserts no code maps to itself raw.
Proof:       Unit/RTL test over the label catalog covering every code +
             _apply_trade_chain_band's error-field read. Full suite green. live-prove: n/a.
Refs:        stopbanner.py:149-190 · trade_driver.py raise sites (381,515,620,645,
             658,670,692,727,760,975,990,997) · session/trade_chain.py:139-152,401-409 ·
             app.py:710-736 · catalog #30.
