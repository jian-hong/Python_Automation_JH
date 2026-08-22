# A02-T01 - Logic TestSpec wraps of `logic_tests.py`

**Epic:** EPIC-A02
**PRD:** PRD-001
**Status:** closed-accepted
**Closed:** 2026-08-20 (R-0003 verifier Grok 4.5 high)
**Step:** current: 5 / 5 - verify PASS; closed
**Depends on:** EPIC-A01 closed (family load + left rail already in tree)
**Model (implement):** composer-2.5-fast
**Model (verify/close):** Grok 4.5 high (`cursor-grok-4.5-high`)
**Adversary rule:** R-0003 - implementer is never the verifier

---

## Problem

A01 left rail can switch to Logic, but `ate/tests/logic` is an empty stub. `list_tests` after `set_family logic` returns zero tests, so the rail still looks like an empty promise. Real Logic measurement entry points already exist at repo root and are not registered.

Evidence:

- `ate/tests/logic/__init__.py` - stub docstring only; no `register()` / `__all__` imports
- `logic_tests.py` - real measurement functions: `test_tp` (~41), `test_tidle` (~183), `test_tdis` (~261), `test_ten` (~337), `test_supply_current` (~413), `test_output_voltage` (~456), `test_cap_load` (~500)
- `ate/core/check_family_load.py` - currently accepts `logic=0` tests as OK
- `ate/worker/server.py` ~156-158: `list_fixture_modes` returns `[]` for non-opamp (keep OPA boards off Logic); Logic `TestSpec.fixture_mode` must still not pretend OPA G11 / G_NEG100 apply
- Wrap pattern already in tree: `ate/tests/opa/ac_gain.py` thin `_run` -> `opa_tests.test_ac_gain_check`

---

## Acceptance

WHEN `load_family("logic")` (or RPC `set_family` / left-rail Logic) completes, THE SYSTEM SHALL list registered Logic tests on `all_tests()` / `list_tests` / the Run page for at least the wrapped ids from existing `logic_tests.py` measurement functions (e.g. `tp` / timing and the other wrap targets below).

WHEN an operator runs one of those Logic tests with an open session, THE SYSTEM SHALL invoke the corresponding existing `logic_tests.test_*` function (thin wrap only - measurement body stays in `logic_tests.py`).

WHEN Logic is the active family, THE SYSTEM SHALL NOT present OPA fixture gain boards G11 / G_NEG100 / VOS research chips as applicable Logic fixture modes (`list_fixture_modes` under Logic must not return those ids; Logic `TestSpec.fixture_mode` values must not be those OPA board names).

WHEN `load_family("opamp")` runs after Logic, THE SYSTEM SHALL restore OPA tests without registry merge leftovers from Logic ids.

WHEN Level is loaded, THE SYSTEM SHALL remain an empty stub (no invented Level suite in this ticket).

---

## Why it is not a one-liner

Trap: inventing a full Logic characterization suite instead of wrapping in-tree functions. Trap: copying OPA `fixture_mode="G11"` / `G_NEG100` onto Logic specs so the UI tag implies OPA boards. Trap: rewriting SCPI / setup inside `ate/tests/logic` instead of calling `logic_tests`. Trap: registering `test_parameter` metadata as a fake test. Trap: leaving `__init__.py` stub so `load_family("logic")` still yields zero tests.

---

## Files likely touched

- `ate/tests/logic/` - one module per wrap or a small set of modules; `__init__.py` imports them so `load_family` registers (mirror `ate/tests/opa/__init__.py`)
- `logic_tests.py` - **read-only** (call into; do not rewrite measurement bodies)
- `ate/core/check_family_load.py` - extend: Logic must be non-empty with at least one expected Logic id; still no OPA leak; OpAmp restore still works
- `ate/fixture/modes.py` / `ate/worker/server.py` `list_fixture_modes` - only if needed to keep Logic catalog free of G11/G_NEG100 (empty Logic catalog is OK)

Do **not** touch A03 docs / add-test wizard. Do **not** build Level suite. Do **not** unlock OPA board gain. Do **not** slice A03/A04.

**Wrap targets (register these):**

| Legacy function | Suggested `TestSpec.id` (flexible) | Instruments (from signature) |
|-----------------|--------------------------------------|------------------------------|
| `test_tp` | `tp` | MSO, PSU, AWG |
| `test_tidle` | `tidle` | MSO, PSU, AWG |
| `test_tdis` | `tdis` | MSO, PSU, AWG |
| `test_ten` | `ten` | MSO, PSU, AWG |
| `test_supply_current` | `supply_current` | PSU, DMM |
| `test_output_voltage` | `output_voltage` | PSU, DMM |
| `test_cap_load` | `cap_load` | DMM |

**Do not register:** `test_parameter` / `TEST_CONFIGURATIONS`.

**Fixture:** use a Logic-only mode string (e.g. `LOGIC`) on every Logic `TestSpec`. Prefer `dual_channel=False` unless a wrap truly needs CHA/CHB probe switch (Logic legacy paths are not OPA dual-channel boards).

---

## Step

```
Step: current: 5 / 5 - verify notes + idle worker restart if needed
```

Suggested steps for the runner (update the counter as you go):

1. Add thin wrap modules under `ate/tests/logic/` calling `logic_tests.test_*`
2. Wire `ate/tests/logic/__init__.py` `__all__` / imports so `load_family("logic")` registers all wraps
3. Set Logic-only `fixture_mode` (not G11 / G_NEG100 / G201 / G1001); keep Level stub empty
4. Extend `check_family_load` (or equivalent) for Logic non-empty + no OPA boards/ids leak + OpAmp restore
5. Idle worker restart if needed; leave verify notes for adversary run

---

## Agent prompt

> Implement EPIC-A02 ticket A02-T01 only (Logic TestSpec wraps). Repo: PythonAutomation. Requires EPIC-A01 family load + left rail already in tree.
>
> **Goal:** Switching to Logic lists real Logic tests backed by existing `logic_tests.py` functions. Wrap, do not rewrite measurement bodies. Do not invent a full Logic suite. Do not implement A03/A04.
>
> **Do:**
> 1. Under `ate/tests/logic/`, add thin `_run` + `register(TestSpec(...))` wrappers for: `test_tp`, `test_tidle`, `test_tdis`, `test_ten`, `test_supply_current`, `test_output_voltage`, `test_cap_load` from repo-root `logic_tests.py` (same pattern as `ate/tests/opa/ac_gain.py` -> `opa_tests`).
> 2. Update `ate/tests/logic/__init__.py` so `load_family("logic")` imports those modules and fills the registry (mirror `ate/tests/opa/__init__.py`).
> 3. Use a Logic-only `fixture_mode` (e.g. `"LOGIC"`). Do **not** set Logic specs to OPA board modes G11, G_NEG100, G201, G1001, or treat those boards as Logic fixtures. Keep `list_fixture_modes` under Logic free of those OPA boards (empty catalog OK).
> 4. Set `dual_channel=False` on Logic specs unless a wrap truly needs CHA/CHB switching.
> 5. Do not register `test_parameter` / config metadata as a test. Leave `ate/tests/level` as empty stub.
> 6. Extend `python -m ate.core.check_family_load` (or equivalent) so Logic load yields non-empty Logic ids, no OPA id leak, and OpAmp reload still restores OPA tests.
>
> **Constraints:**
> - Measurement SCPI/setup stays in `logic_tests.py` - wraps call it, do not copy/rewrite bodies.
> - Reuse `TestSpec` + `register()` + A01 `load_family` - no new framework.
> - Preserve OPA OpAmp behavior and START session gate (do not regress A01).
> - No wizard, no Tauri, no Level suite, no A03/A04 work.
> - YAGNI / ponytail: fewest files; one module-per-test or a small split is fine; no gold plating.
>
> **Out of ticket:** A03 add-test docs, A04 custom conditions UI, inventing new Logic measurements, rewriting `logic_tests.py` algorithms.
>
> **Model:** implement with composer-2.5-fast. Do not self-close; a different Grok 4.5 high run verifies.
>
> After edits that affect the worker, if idle, restart via `restart_ate_worker.bat` per workspace rule. Tell operator Ctrl+F5 if UI already shows Logic empty from a prior session.

---

## Verify (different run - R-0003)

Implementer must not run this as the close gate. Verifier (Grok 4.5 high) runs:

1. **Runnable:** `python -m ate.core.check_family_load` (or the extended check) - Logic non-empty with expected Logic ids; no OPA ids after Logic load; OpAmp restore still has known OPA ids (e.g. gbw / slew).
2. **Static:** grepped wrap modules under `ate/tests/logic/` import/call `logic_tests.test_*` (or equivalent) and do not contain rewritten measurement loops copied from `logic_tests.py`. Confirm no Logic `TestSpec.fixture_mode` in `{G11, G_NEG100, G201, G1001}`.
3. **RPC / UI smoke (idle worker):** `set_family logic` -> `list_tests` non-empty with Logic ids; `list_fixture_modes` has no G11 / G_NEG100 / G201 / G1001. `set_family opamp` restores OPA tests. Level still empty/stub.
4. Optional: one wrapped id's `run` callable resolves to a path that reaches `logic_tests` (import smoke), without requiring live instruments for close if session unavailable - note if hardware gate blocked that optional step.

Close only if acceptance WHEN/SHALL statements hold; then update epic ticket index status in the same action.
