---
keywords: accordion, fixture-group, test-list, flex-shrink, overflow, collapsed, START overlap, run-plan order
main_idea: Test program boards must start collapsed and expand in document flow. A 360px flex list plus overflow:hidden on details made groups shrink into each other and cover START.
---

# Test program accordion

## Bug
`.test-list` was `display:flex; max-height:360px` and `.fixture-group` had `overflow:hidden`. Flex items with non-visible overflow treat `min-height:auto` as 0, so open groups **shrink and clip siblings**. Screenshot symptom: G11 / G_NEG100 squeezed to a hairline, C001 under START.

## Fix
- All `.fixture-group` and run-plan `<details>` start closed (`open = false`).
- Drop the 360px cap. `flex: 0 0 auto` so rows expand downward and push START.
- Closed content `display:none` so it cannot intercept clicks.
- Run-plan sort uses catalog `tests:` order (slew then settling then gbw then ort), same as the runner.

## Verify (2026-08-20)
Browser hard-stress on `http://127.0.0.1:5174/?v=20260820b`: 12 toggle cycles, independent dual-open, family Logic->OpAmp round-trip, Setup/Run/Results tabs. `fail: []`. Simulated slew+settling+gbw+ort plan ids `["slew","settling","gbw","ort"]`, plans collapsed. START stays below last group.

Live bench run not executed: worker idle, session closed, no MSO/PSU/AWG mapping.
