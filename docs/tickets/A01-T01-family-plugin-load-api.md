# A01-T01 - Family plugin load API

**Epic:** EPIC-A01
**PRD:** PRD-001
**Status:** closed
**Step:** current: 4 / 4 - verified closed
**Model (implement):** composer-2.5-fast
**Model (verify/close):** Grok 4.5 high (`cursor-grok-4.5-high`)
**Adversary rule:** R-0003 - implementer is never the verifier
**Verified:** 2026-08-19 by independent verifier (Grok 4.5 high); verifier != implementer

---

## Problem

`ATECore` always registers OpAmp tests only. Switching product family later cannot work while this hard import remains.

Evidence:

- `ate/core/runner.py` ~139-140: `_ensure_tests_registered` does `import ate.tests.opa` only
- `ate/core/registry.py`: global `_REGISTRY` with `register()` / `all_tests()` - no clear/reload API for family switch
- `ate/worker/server.py` `list_tests` returns `all_tests()` after that opa-only path
- No `ate/tests/logic` package; Logic exists only as legacy `logic_tests.py` and DB folders

---

## Acceptance

WHEN the worker (or a small self-check) loads family `opamp`, THE SYSTEM SHALL expose the existing OPA registered tests via `all_tests()` / `list_tests`.

WHEN the load API switches to family `logic` (empty package OK), THE SYSTEM SHALL clear prior OPA registry entries and SHALL NOT leave OPA test ids mixed into `all_tests()`.

WHEN source is grepped / self-checked, THE SYSTEM SHALL NOT contain an opa-only hard import as the sole registration path in `_ensure_tests_registered` (family table or `ate.tests.<family>` loader instead).

---

## Why it is not a one-liner

Trap: painting a UI rail while leaving `import ate.tests.opa` as the only register path (PRD internal FAQ). Second trap: appending Logic onto the same `_REGISTRY` without clear -> silent merge of OPA+Logic ids. Third: inventing a new plugin framework instead of reusing `TestSpec` + `register()`.

---

## Files likely touched

- `ate/core/runner.py` - replace `_ensure_tests_registered` with family loader
- `ate/core/registry.py` - add clear / family-scoped reload helper (minimum)
- `ate/tests/opa/` - keep as OpAmp package (default)
- `ate/tests/logic/` - empty or stub package so import does not fail (no real Logic tests yet; A02 owns wrap)
- `ate/tests/level/` - optional stub package for rail honesty (empty)
- Optional tiny self-check script under `ate/` or `scripts/` if cheapest place for the runnable check

Do **not** touch UI left rail in this ticket (T02). Do **not** wrap `logic_tests.py` (A02).

---

## Step

```
Step: current: 4 / 4 - verified closed (2026-08-19; verifier != implementer)
```

Suggested steps for the runner (update the counter as you go):

1. Add registry clear + family load table / convention
2. Wire runner default family = opamp; remove opa-only sole path
3. Stub empty logic (and level if needed) packages
4. Runnable check green; leave note for verify run

---

## Agent prompt

> Implement EPIC-A01 ticket A01-T01 only (family plugin load API). Repo: PythonAutomation.
>
> **Goal:** Replace opa-only `ATECore._ensure_tests_registered` (`ate/core/runner.py` ~139-140 `import ate.tests.opa`) with a family plugin load API. Default family remains OpAmp and must still register all existing OPA tests.
>
> **Do:**
> 1. Introduce a small family table or `ate.tests.<family>` import convention (OpAmp -> `ate.tests.opa`; Logic -> `ate.tests.logic`; Level stub optional).
> 2. On family switch / load: clear the in-process registry then import that family's package so ids do not silently merge.
> 3. Add `clear()` (or equivalent) on `ate/core/registry.py` if missing; reuse `TestSpec` + `register()` - no new framework.
> 4. Create empty/stub `ate/tests/logic` (and Level stub if the table needs it) so Logic load succeeds with zero tests until A02.
> 5. One runnable check that fails if opa-only hard-import is still the sole registration path, and that proves load(opamp) then load(logic) does not leave OPA ids in `all_tests()`.
>
> **Constraints:**
> - Preserve START gate elsewhere (do not change `btn-start` / session lock).
> - Preserve category-first OPA path when OpAmp is loaded (do not rewrite run order).
> - Do not merge OPA+Logic registry ids.
> - Level may be stub only. Logo is not the rail (UI is T02).
> - No wizard, no Tauri, no wrapping `logic_tests.py` (A02).
> - YAGNI / ponytail: fewest files; do not gold-plate plugin discovery.
>
> **Out of ticket:** left-rail UI, RPC for family switch (T02), Logic measurement wraps (A02).
>
> **Model:** implement with composer-2.5-fast. Do not self-close; a different Grok 4.5 high run verifies.
>
> After edits that affect the worker, if idle, restart via `restart_ate_worker.bat` per workspace rule.

---

## Verify (different run - R-0003)

Implementer must not run this as the close gate. Verifier (Grok 4.5 high) runs:

1. **Static:** `rg "_ensure_tests_registered|import ate\\.tests\\.opa" ate/core/runner.py` - sole opa hard-import must be gone or only used inside a family table entry for opamp.
2. **Runnable check** shipped by implementer (exact command they leave in the PR/ticket comment), expecting:
   - load opamp -> `all_tests()` non-empty with known OPA ids (e.g. gbw / slew)
   - load logic -> `all_tests()` contains no those OPA ids (empty OK)
3. Optional smoke: worker restart + `list_tests` RPC still returns OPA tests on default boot.

Close only if acceptance WHEN/SHALL statements hold; then update epic ticket index status in the same action.
