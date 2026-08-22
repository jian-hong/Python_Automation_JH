---
keywords: ui, fluency, pollLoop, gbw-label, page-in, reduced-motion, timeline-scroll
main_idea: Operator console jank was idle 3-RPC/350ms polling, stacked DUT listeners, GBW G11 label on Slew sessions, and smooth-scroll fighting the timeline. Landing now fades tabs, polls slower when idle, and Ctrl+F5 cache is 20260820d.
---

# Console fluency / landing (2026-08-20)

Idle Setup was calling get_events + get_pending_prompt + session_status every 350 ms.
`loadTests` re-bound DUT/channel change handlers on every family switch.
`params()` stamped `G11_1k_10k` even when only Slew+Settling were checked.
`renderTimeline` smooth-scrolled on every event.

Fix: `pollLoop` 900 ms idle / 350 ms running; DUT listeners once in boot; GBW
run_label only if GBW is selected; instant nearest scroll when current step
changes; page-in 160 ms + `prefers-reduced-motion`; log cap 80k.

Check: `python -m ate.ui.check_console_fluency`
UI: Ctrl+F5 after `app.js?v=20260820e`
