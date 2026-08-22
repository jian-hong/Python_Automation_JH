# EPIC-A01 - Product-family plugin boundary (left rail switches real apps)

**PRD:** [PRD-001-ate-multi-product-platform](../prd/PRD-001-ate-multi-product-platform.md)
**Repo:** PythonAutomation
**Status:** closed - accepted
**Accepted:** 2026-08-19 (epic-agent Mode B; code + RPC, not ticket checkboxes)
**Tier:** boundary (with visible surface so WIP is inspectable)
**Depends on:** none
**Blocks:** EPIC-A02, EPIC-A03, EPIC-A04
**Appetite:** 1 wave
**Sliced:** 2026-08-19
**GitHub Issues:** do not open unless founder opts in

---

## Buyer-visible outcome

Operator sees a left-rail product switcher (OpAmp / Logic; Level may appear as stub). Selecting a family changes tests + fixture catalog + brand copy, not only the DB breadcrumb.

---

## Acceptance (from PRD)

> WHEN the operator selects Logic on the left rail, THE SYSTEM SHALL stop listing OpAmp-only fixture gain boards as applicable and SHALL expose only that family's registered tests (may be empty until A02). WHEN the operator selects OpAmp, THE SYSTEM SHALL restore the existing OPA test list and OPA fixture catalog without regressing category-first gates or the START session lock.

---

## Design constraints

- Replace opa-hardcoded `_ensure_tests_registered` with family-package load (plugin table or `ate.tests.<family>` convention).
- Registry must be family-scoped or cleared+reloaded on switch (do not silently merge OPA+Logic ids).
- Preserve START disabled when `session_open` is false.
- Preserve OPA category-first board -> channel -> DUT order when OpAmp is selected.
- Level = stub slot only. No wizard. No Tauri. No new framework. Reuse `TestSpec` + `register()`.
- Logo (`.logo`) is decorative - not the product rail.
- Do not invent Logic characterization in this epic (empty Logic registry OK until A02).

---

## Ticket index

| ID | File | Status | One-line acceptance |
|----|------|--------|---------------------|
| A01-T01 | [A01-T01-family-plugin-load-api.md](../tickets/A01-T01-family-plugin-load-api.md) | closed | Family load API replaces opa-only import; clear/reload on switch; no merge of family registries |
| A01-T02 | [A01-T02-rpc-ui-left-rail.md](../tickets/A01-T02-rpc-ui-left-rail.md) | closed | Left rail switches OpAmp/Logic/Level-stub; tests+fixtures+brand follow family; START + category-first preserved |

**Ponytail:** former T03 (operator-invariant regression) folded into T02 acceptance - not a third ticket.

---

## File contention

| Area | Tickets | Note |
|------|---------|------|
| `ate/core/runner.py` register hook | T01 primary; T02 may call into load API | T01 owns mechanism; T02 must not re-harden opa-only import |
| `ate/core/registry.py` clear/reload | T01 | |
| `ate/tests/` family packages / stub slots | T01 | Logic/Level may be empty packages |
| `ate/worker/server.py` RPC | T02 | `set_family` / `get_family` (or equivalent) |
| `ate/ui/web/*` left rail + brand | T02 | |
| `ate/fixture/modes.py` | T02 (catalog scoping if needed); do not unlock OPA gain | |

Later epics (A02+) must not re-harden opa-only imports.

---

## Completeness (Mode B - 2026-08-19)

**COMPLETE** - acceptance re-derived from code + live RPC (not ticket checkboxes).

Evidence:
1. `python -m ate.core.check_family_load` (8.3 path) -> `OK opamp=16 tests logic=0 tests (no OPA leak after switch)`
2. RPC `set_family logic` -> `test_count=0`, `list_tests` empty, `list_fixture_modes` `[]` (no G11 / G_NEG100)
3. RPC `set_family opamp` -> `test_count=16`, fixtures include `BUFFER,G11,G_NEG100,ATE,G201,G1001`
4. UI: `.family-rail` is the switcher; `.logo` decorative only (`index.html`)
5. START: `#btn-start` starts `disabled`; `refreshSession` sets `disabled = !sessionOpen`; RPC `session_status.open=false` while idle
6. Category-first preserved: `runner.py` still loops `for mode, specs in batches` -> `for channel` -> `for dut`

Next: parent should spawn a **new** epic-agent Mode A to slice **EPIC-A02** (Logic wraps). Do not invent A02 tickets in this Mode B run.
