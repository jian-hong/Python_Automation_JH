---
keywords: ate, platform, readiness, registry, logic, opa, playwright, demo, 5174, 8766
main_idea: Live ATE is Level 3/5 -- OPA operator console with a register() slot for new OPA tests. Not a multi-product platform; no left-rail app switcher; Logic/Level are disk folders only.
---

# 2026-08-19 ATE platform readiness

## Live
- Worker `http://127.0.0.1:8766` ping v0.2.2, busy=false
- UI `http://127.0.0.1:5174` Setup/Run/Results
- Discover `{}` -- no MSO/PSU/AWG this session; START correctly disabled
- Component dropdown sees Level / Logic / OpAmp; tests stay OPA

## Verdict
Level 3 of 5 (OPA app). Platform (left-rail Logic/OPA, no-code new tests) is Level 1-2 scaffold.

## Slot that exists
`TestSpec` + `register()` + part YAML `tests:` + fixture catalog. Runner still `import ate.tests.opa` only.

## Slot that does not exist
Product plugins, `ate/tests/logic`, UI to add tests/conditions, left nav (logo is decorative).
