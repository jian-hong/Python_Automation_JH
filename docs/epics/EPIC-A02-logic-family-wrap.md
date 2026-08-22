# EPIC-A02 - Logic family wraps existing `logic_tests.py`

**PRD:** [PRD-001-ate-multi-product-platform](../prd/PRD-001-ate-multi-product-platform.md)
**Repo:** PythonAutomation
**Status:** closed-accepted
**Sliced:** 2026-08-19
**Closed:** 2026-08-20 (R-0003 verify; acceptance re-derived from code + RPC)
**Tier:** capability
**Depends on:** EPIC-A01 (closed-accepted 2026-08-19)
**Blocks:** none hard; improves A01 demo honesty
**Appetite:** 1 wave
**GitHub Issues:** do not open unless founder opts in

---

## Buyer-visible outcome

Switching to Logic on the left rail lists Logic tests backed by existing `logic_tests.py` measurement functions (timing / TP and other in-tree entry points), not OPA stubs or an invented Logic suite.

---

## Acceptance (from PRD)

> WHEN Logic is selected and at least one Logic `TestSpec` is registered, THE SYSTEM SHALL list those tests on the Run page. WHEN the operator runs a wrapped Logic test with an open session, THE SYSTEM SHALL invoke the existing logic test function path (wrap, do not rewrite the measurement body in this epic).

**Fixture constraint (this epic):** Logic `TestSpec.fixture_mode` and `list_fixture_modes` under Logic SHALL NOT present OPA G11 / G_NEG100 / VOS research boards as if they applied to Logic.

**Out of epic:** inventing new Logic characterization beyond wrap; Level suite (Level stays stub); A03 add-test docs; A04 per-family condition UI.

---

## Design constraints

- Reuse `TestSpec` + `register()` + `load_family("logic")` from A01. Do not invent a plugin framework.
- Wrap bodies live in repo-root `logic_tests.py`; `ate/tests/logic` holds thin `_run` + `register()` only (same pattern as `ate/tests/opa/ac_gain.py` -> `opa_tests`).
- Real wrap targets (measurement functions): `test_tp`, `test_tidle`, `test_tdis`, `test_ten`, `test_supply_current`, `test_output_voltage`, `test_cap_load`.
- Do **not** register `test_parameter` / `TEST_CONFIGURATIONS` as a TestSpec (metadata only).
- Do not rewrite measurement SCPI / setup inside the wrap modules.
- Level package remains empty stub.
- OPA OpAmp path must keep working after Logic load/clear cycle.

---

## Ticket index

| ID | File | Status | One-line acceptance |
|----|------|--------|---------------------|
| A02-T01 | [A02-T01-logic-testspec-wraps.md](../tickets/A02-T01-logic-testspec-wraps.md) | closed-accepted | Logic rail lists wrapped `logic_tests` specs; run path calls legacy functions; no OPA G11/G_NEG100 as Logic fixtures |

**Ponytail:** one ticket. Fixture honesty folded into T01 (not a second ticket). No A03/A04 slice.

---

## File contention

| Area | Tickets | Note |
|------|---------|------|
| `ate/tests/logic/**` | T01 | Own wrap modules + `__init__` import list |
| `logic_tests.py` | read-only for wrap | Do not rewrite measurement bodies |
| `ate/core/check_family_load.py` | T01 may extend | Assert Logic non-empty + no OPA leak |
| `ate/fixture/modes.py` / `list_fixture_modes` | T01 only if needed | Logic must not surface G11/G_NEG100; empty Logic catalog OK |
| `ate/tests/level/` | leave stub | |
| A03/A04 surfaces | out of epic | |

---

## Completeness (Mode B / R-0003 evidence 2026-08-20)

Acceptance re-derived from code + RPC (not ticket checkboxes only):

- `python -m ate.core.check_family_load` -> `OK opamp=16 logic=7 restored=16 tests (no cross-family leak)`
- RPC idle: `set_family logic` -> `test_count=7`, ids `cap_load,output_voltage,supply_current,tdis,ten,tidle,tp` (no gbw/slew); `list_fixture_modes=[]`
- RPC: `set_family opamp` restores 16 tests including `gbw`,`slew` and OPA fixture catalog
- Static: `ate/tests/logic/wraps.py` thin `_run` -> `logic_tests.test_*`; `fixture_mode="LOGIC"`; seven wraps; no `test_parameter`; `ate/tests/level` stub empty

**Verdict:** COMPLETE / closed-accepted. Do not start A03 from this close.
