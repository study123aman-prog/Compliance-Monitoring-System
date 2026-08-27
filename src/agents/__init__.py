"""
agents package — the four specialist agents plus a shared base class.

Design note (viva): in production each agent runs its own detection models over a
live data feed (order flow, comms, regulatory publications). In this reference
demo the *detection outcome* for each scenario is provided as data in
scenarios.py, and each agent surfaces the portion addressed to it as an Opinion
and an ALERT envelope. This keeps the demo deterministic and focused on the parts
the design is really about — coordination, consensus, escalation and audit —
rather than re-implementing ML detectors.
"""
