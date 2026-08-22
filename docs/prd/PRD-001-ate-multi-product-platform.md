# PRD-001 - ATE multi-product operator platform

**Product:** PythonAutomation ATE (operator console + worker)
**Owner:** founder
**Status:** sliced - EPIC-A01 closed-accepted; EPIC-A02 tickets in docs/tickets
**Repos in scope:** this repo (`PythonAutomation` / origin `jian-hong/Python_Automation_JH`)
**Created:** 2026-08-19
**Epic home:** `docs/epics/EPIC-A02-logic-family-wrap.md` (active); A01 at `docs/epics/EPIC-A01-family-plugin-left-rail.md` (closed). Do **not** open GitHub Issues for epics/tickets unless the founder later opts into issue tracking on `origin`. Ticket files under `docs/tickets/` belong to epic-agent after slice.

---

## 1. Press release

### One console. Many product families. Same operator muscle memory.

**Subheading:** Lab operators and characterization engineers switch OPA, Logic, and later Level apps from a left rail - without losing the Continue gates, session lock, or registered tests they already trust.

**Problem:** "We have an OPA ATE that works on the bench. The Test Database already has folders for Logic and Level, and the campaign dropdown lists them - but picking Logic still shows OPA gain boards and OPA tests. Adding a new product family means editing the runner import list and living with a header that still says OPA ATE. This is an OPA app wearing a database tree, not a platform."

**Solution:** A product-family plugin contract. Each family (OpAmp, Logic, Level-later) owns its registered `TestSpec` package, fixture catalog, and operator-visible labels. The left rail selects the family; the worker loads that family's package; the Run page lists that family's tests. OPA behavior that already shipped (category-first board -> channel -> DUT order, operator Continue short tags, START disabled until Open Session, board gain locked in YAML for OPA fixtures) stays the default for the OpAmp family. Engineers add a new test by `TestSpec` + `register()` in the family package and restarting the worker - not by patching a hard-coded OPA import forever.

**Quote:** "I switched to Logic, saw Logic timing tests, and the OPA G11 board chips were gone. When we added one more OPA sweep, it showed up after worker restart without touching runner.py's family list." - characterization lead, internal pilot (aspirational)

**Call to action:** Approve EPIC-A01 (family plugin boundary). Epic-agent slices only that epic this wave. Keep the live OPA demo green while the rail lands.

---

## 2. FAQ

### External

- **What is shipping in this slice?** A multi-family operator console: left-rail product switch, family-scoped tests and fixture UI, Logic wrapped from existing `logic_tests.py`, and a documented add-test slot that works for any family.
- **Will OPA runs change for operators who stay on OpAmp?** No intentional behavior change. Category-first order, gates, session START lock, and existing OPA tests remain. Regression against the 2026-08-19 live demo is a fail for A01/A02.
- **Can we add Level this quarter?** Level gets an empty (or stub) family slot in the contract so the rail can show it without lying. Full Level characterization suite is out of scope for this PRD.
- **Do we need new instruments?** No. Discover / Open Session / START gate stay. Empty Discover still correctly blocks START.
- **Is this a no-code product?** Not yet. Python `register()` is the supported add-test path. YAML/UI condition knobs are a later surface epic; a wizard is parked.

### Internal

- **What could make this fail?** Shipping a left rail that only changes the `#Test_Database` campaign path while `ATECore._ensure_tests_registered` still does `import ate.tests.opa` only - that is today's bug dressed as a feature. Second failure mode: rewriting fixture modes into a shared free-gain dial and breaking OPA board-lock semantics.
- **What are we assuming?** (1) `TestSpec` + `register()` + `all_tests()` remain the extension point. (2) `logic_tests.py` functions are wrappable without inventing a full Logic suite. (3) One worker process, one active family at a time for v1 (switch family clears or reloads registry - exact mechanism is A01 design, not a second worker). (4) Prior OPA improvements listed in readiness stay.
- **What would we have to be right about?** That "family" is the irreversibility boundary - harder to reverse than UI chrome or one Logic wrapper. If we keep OPA-only imports while painting a rail, every later family pays a tax.
- **Why not delete `main.py` now?** Dual stack is debt, not the platform claim. Deleting legacy without a family contract just moves Logic callers into the wrong place. Parked.
- **GitHub Issues?** `origin` exists (`https://github.com/jian-hong/Python_Automation_JH.git`) but this wave keeps epic sketches and (later) local ticket files in-repo unless the founder opts into Issues.

---

## 3. Out of scope

Explicit park / refuse for this PRD:

- Inventing a full Logic characterization suite beyond wrapping existing `logic_tests.py` entry points into `ate/tests/logic` `TestSpec`s
- Full Level product app (beyond an empty/stub family slot so the rail is honest)
- Hardware appearing when Discover returns `{}`
- Rewriting PyVISA helpers (`instruments.py` session stack) as a platform rewrite
- No-code test wizard
- Tauri native shell as a required delivery (scaffold may exist; not this PRD's success gate)
- STM relay bank / arbitrary gain dial
- Deleting legacy `main.py` / `opa_tests.py` / teaching rewrite of `TEST_DESIGN.md` away from legacy (doc sync may follow; not blocking)
- Linear project board; GitHub epic/ticket Issues unless founder opts in
- Changing the START-disabled-until-Open-Session rule
- Unlocking OPA board gain as a free numerical control (YAML lock stays correct for OPA fixtures)

---

## 4. Success assertion

Testable from the operator / engineer seat:

> **WHEN** an operator picks a product family on the left rail (OPA / OpAmp or Logic), **THE SYSTEM SHALL** load that family's registered tests and fixture catalog into the Run console, and **SHALL NOT** present OPA-only gain boards (G11 / G_NEG100 / VOS research chips) as if they applied to Logic.
>
> **WHEN** an engineer adds a new test via `TestSpec` + `register()` inside the active family's package and restarts the worker, **THE SYSTEM SHALL** list that test in the console without requiring an edit to `runner.py` beyond the single family-package import (or family plugin table) introduced by EPIC-A01.
>
> **WHEN** no instrument session is open, **THE SYSTEM SHALL** keep START disabled.

Code anchors for the assertion (verified 2026-08-19):

- OPA-only register today: `ate/core/runner.py` `_ensure_tests_registered` -> `import ate.tests.opa`
- START gate: `ate/ui/web/app.js` `$("btn-start").disabled = !sessionOpen` (initial HTML `disabled`)
- Brand hardcode: `ate/ui/web/index.html` `<h1>OPA ATE</h1>`; logo decorative (`.logo` CSS), not a product rail
- Campaign folders != family plugins: `ate/core/database.py` component tree; UI cascades list Level/Logic/OpAmp but tests stay OPA (`list_tests` -> `all_tests()` after opa import only)
- Logic legacy exists, not registered: repo-root `logic_tests.py` (e.g. `test_tp`); no `ate/tests/logic`
- OPA fixture gain lock: `ate/fixture/modes.py` + part YAML; correct to preserve under OpAmp family

---

## 5. Code-verified baseline (2026-08-19)

Do not treat as aspirational:

| Area | State | Evidence |
|------|-------|----------|
| Worker / UI | Live ping v0.2.2; Setup/Run/Results | readiness finding; ports 8766 / 5174 |
| Modular core | `TestSpec`, `register()`, runner, fixture modes, operator gate, DB tree | `ate/core/*`, `ate/fixture/*` |
| OPA automated | slew, settling, gbw, ort, vos_sweep, ac_gain_check, ac_vin_sweep | `ate/tests/opa/*` |
| OPA stubs | 9x `RuntimeError` stubs (SSSR/LSSR/phase/power-on + PSRR/CMRR/AOL/VOHL/EMIRR) | `ate/tests/opa/stubs.py` |
| Operator flow | category-first board -> channel -> DUTs; short tags | `ate/core/runner.py`, findings 2026-08-07 |
| Platform gap | campaign dropdown changes folder; tests do not | UI + opa-only import |
| Readiness scores | compile 95, UI 88, OPA tests 82, new OPA test slot 70, new OPA part 55, Logic/Level apps 28, no-code 18, left-rail 12 | founder + readiness finding |
| Dual stack | `ate/` console vs legacy `main.py` / `opa_tests.py` / `logic_tests.py` | repo root |

Prior improvements **must be kept** (non-negotiable for OpAmp family): category-first order, Continue popup short tags, safe-idle before gates, START session gate, existing OPA automated tests, board gain locked for OPA fixtures.

---

## 6. Model / dispatch law (this wave)

Recorded for agents; not a product feature.

| Role | Model |
|------|-------|
| prd-agent, epic-agent, verify / close | Grok 4.5 high (`cursor-grok-4.5-high`) |
| ticket-runner (this wave, founder override) | cheapest (`composer-2.5-fast`) |
| Claude Code (separate product) | Opus only. Cursor **cannot** dispatch Claude Code. |

**F-0009:** one ticket-runner per working tree. Do not dual-lane.

**WIP:** epic-agent slices **at most one epic** per wave. A01 closed; A02 sliced (do not implement from this PRD document - ticket-runner owns A02-T01).

---

## 7. Epic sketches (irreversibility order)

Epics are sketches here. Epic-agent owns ticket files. Appetite default: one focused agent wave unless noted.

Ordering law: irreversibility, not value. A01 before A02 before A03 before A04.

### EPIC-A01 - Product-family plugin boundary (left rail switches real apps)

| Field | Value |
|-------|-------|
| Tier | boundary (with visible surface so WIP is inspectable) |
| Repo | this repo |
| Contract impact | additive (new family plugin / load API; OPA remains default path) |
| Depends on | none |
| Blocks | EPIC-A02, EPIC-A03, EPIC-A04 |
| Appetite | 1 wave |

**Buyer-visible outcome:** Operator sees a left-rail product switcher (OpAmp / Logic; Level may appear as stub). Selecting a family changes tests + fixture catalog + brand copy, not only the DB breadcrumb.

**Acceptance:**
> WHEN the operator selects Logic on the left rail, THE SYSTEM SHALL stop listing OpAmp-only fixture gain boards as applicable and SHALL expose only that family's registered tests (may be empty until A02). WHEN the operator selects OpAmp, THE SYSTEM SHALL restore the existing OPA test list and OPA fixture catalog without regressing category-first gates or the START session lock.

**Design constraints (for tickets, not pre-solved here):**
- Replace opa-hardcoded `_ensure_tests_registered` with family-package load (plugin table or `ate.tests.<family>` convention).
- Registry must be family-scoped or cleared+reloaded on switch (do not silently merge OPA+Logic ids).
- Preserve START disabled when `session_open` is false.
- Human-inspectable: founder can click the rail and see the Run page change.

**File contention note:** A01 owns `ate/core/runner.py` register hook, registry family scoping if needed, and left-rail UI (`ate/ui/web/*`). Later epics must not re-harden opa-only imports.

---

### EPIC-A02 - Logic family wraps existing `logic_tests.py`

| Field | Value |
|-------|-------|
| Tier | capability |
| Repo | this repo |
| Contract impact | additive |
| Depends on | EPIC-A01 |
| Blocks | none hard; improves A01 demo |
| Appetite | 1 wave |

**Buyer-visible outcome:** Switching to Logic lists Logic tests backed by existing `logic_tests.py` functions (e.g. timing / TP paths already in-tree), not OPA stubs.

**Acceptance:**
> WHEN Logic is selected and at least one Logic `TestSpec` is registered, THE SYSTEM SHALL list those tests on the Run page. WHEN the operator runs a wrapped Logic test with an open session, THE SYSTEM SHALL invoke the existing logic test function path (wrap, do not rewrite the measurement body in this epic).

**Out of epic:** inventing new Logic characterization beyond wrap; Level suite.

---

### EPIC-A03 - Add-test slot for any family

| Field | Value |
|-------|-------|
| Tier | capability |
| Repo | this repo |
| Contract impact | none (docs + convention + self-check; may add tiny family `__init__` pattern) |
| Depends on | EPIC-A01 |
| Blocks | none |
| Appetite | short wave |

**Buyer-visible outcome:** An engineer following one doc can add a test under any family package; after worker restart it appears. One runnable self-check fails if the convention breaks.

**Acceptance:**
> WHEN a new `TestSpec` is registered via the family package `__init__` import convention and the worker is restarted, THE SYSTEM SHALL include it in `list_tests` / Run UI without editing `runner.py` beyond the A01 family loader. WHEN the self-check is run, THE SYSTEM SHALL fail if opa-only hard-import returns.

**Secondary (explicitly not blocking A03):** new OPA part YAML authoring remains lower priority (readiness score ~55).

---

### EPIC-A04 - Per-family operator custom conditions

| Field | Value |
|-------|-------|
| Tier | surface |
| Repo | this repo |
| Contract impact | additive |
| Depends on | EPIC-A01 (family context); benefits from A02 for Logic params |
| Blocks | none |
| Appetite | 1 wave |

**Buyer-visible outcome:** Manual / catalog params already used on Run extend per family (Logic conditions vs OPA gain profiles), without a no-code wizard.

**Acceptance:**
> WHEN OpAmp is active, THE SYSTEM SHALL keep OPA param catalog behavior (including board-locked gain profiles). WHEN Logic is active, THE SYSTEM SHALL show Logic-relevant condition fields and SHALL NOT require OPA G11 board confirmation for Logic-only runs.

**Out of epic:** no-code wizard (parked).

---

### PARKED (not epics this PRD)

| Item | Unlock condition |
|------|------------------|
| No-code test wizard | A03 slot proven; founder asks for non-Python authors |
| Tauri native shell as success gate | Web console meets family switch; packaging appetite opens |
| STM relay / free gain | Hardware + DR; must not break OPA YAML lock until then |
| Delete legacy `main.py` | A02 Logic path proven through `ate/`; dual-stack tax measured |
| Full Level suite | Separate PRD or amendment after A01 stub slot exists |

---

## 8. Blocking vs later (product claim)

**Blocking for "platform" claim (this PRD):**

1. Product-family plugin contract + left rail that switches tests + fixture catalog + runner family import (EPIC-A01)
2. Preserve OPA operator flow (constraint on A01+; verified by regression)
3. Add-test slot for any family: docs + convention + one self-check (EPIC-A03)

**Worth doing, not blocking:**

4. YAML/UI custom conditions per family (EPIC-A04)
5. No-code wizard (parked)
6. Tauri shell (parked)
7. STM relay (parked)
8. Delete legacy main (parked)

**A02** is the honest demo partner for A01 (Logic not empty). A01 closed-accepted; A02 sliced (local tickets). A03/A04 not sliced this wave.

---

## 9. Feedback ledger

Append only. Never rewrite prior rows.

| # | Date | Raised in | Feedback | Routed to | Outcome |
|---|------|-----------|----------|-----------|---------|
| F1 | 2026-08-19 | founder session (F1) | Make this a **product** not just an OPA app. Left panel to switch different apps for different product types (Logic, OPA, later Level). Customisable to add new tests and new conditions. Other devices / new tests must have a slot. Prior improvements must be kept. | EPIC-A01 (boundary), EPIC-A02 (Logic wrap), EPIC-A03 (add-test slot), EPIC-A04 (conditions surface); Level full suite + wizard + Tauri + STM + delete legacy -> PARKED / out of scope | **Ack - this PRD.** Mode A authoring complete. Epic-agent next: slice **EPIC-A01** only. No tickets filed by prd-agent. |
| F2 | 2026-08-19 | epic-agent Mode A | Slice EPIC-A01 only into local ticket files (ponytail: 2 tickets; T03 invariants folded into T02). | EPIC-A01 | **Sliced.** Epic: `docs/epics/EPIC-A01-family-plugin-left-rail.md`. Tickets: A01-T01, A01-T02 under `docs/tickets/`. A02-A04 not sliced. No GitHub Issues. |
| F3 | 2026-08-19 | epic-agent Mode B | Re-derive EPIC-A01 acceptance from code + live RPC (not ticket checkboxes). | EPIC-A01 | **COMPLETE / closed-accepted.** Logic clears tests+fixtures; OpAmp restores 16 tests + G11/G_NEG100 catalog; START session-gated; category-first intact. Finding: `docs/subagents_findings/2026-08-19_epic-a01-mode-b-complete.md`. A02 not sliced here. |
| F4 | 2026-08-19 | epic-agent Mode A | Slice EPIC-A02 only (Logic wraps `logic_tests.py` into `ate/tests/logic` TestSpecs). | EPIC-A02 | **Sliced.** Epic: `docs/epics/EPIC-A02-logic-family-wrap.md`. Ticket: A02-T01 under `docs/tickets/`. Ponytail: 1 ticket (fixture honesty folded in). A03/A04 not sliced. No GitHub Issues. |

---

## 10. Recommended next action

1. Spawn **ticket-runner** on **A02-T01** (`docs/tickets/A02-T01-logic-testspec-wraps.md`) with composer-2.5-fast; verify/close with a different Grok 4.5 high run (R-0003).
2. Do not reopen A01; do not slice A03/A04 until A02 closes and founder asks.
3. After A02-T01 closes: epic-agent Mode B on EPIC-A02 (code + RPC, not checkboxes).

**NEEDS-YOU:** (none for slice; next is implement A02-T01)
