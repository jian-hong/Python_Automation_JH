---
keywords: defects, dual-stack, dmm, stubs, false-green, visa, claude, handover
main_idea: Recurring ATE defects are dual Instruments (no dmm), enabled stubs that RuntimeError, self-checks that only list tests, and stale PRD anchors -- not the left rail.
---

# 2026-08-20 Recurring defect classes for Claude debug

Handoff plan: `docs/handover/2026-08-20_claude-opus-defect-debug-plan.md`

Do not treat `check_family_load` / `list_tests` as a live-run proof. Logic DMM wraps will fail on `ate.instruments.session.Instruments` (no `dmm`). Nine OPA stubs are still `enabled=True`.
