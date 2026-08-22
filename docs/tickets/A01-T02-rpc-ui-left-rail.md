# A01-T02 - RPC + UI left rail (family switch surface)

**Epic:** EPIC-A01
**PRD:** PRD-001
**Status:** closed
**Step:** current: 5 / 5 - verified closed
**Depends on:** A01-T01 (family load API must exist)
**Model (implement):** composer-2.5-fast
**Model (verify/close):** Grok 4.5 high (`cursor-grok-4.5-high`)
**Adversary rule:** R-0003 - implementer is never the verifier
**Verified:** 2026-08-19 by independent verifier (Grok 4.5 high / R-0003); verifier != implementer

---

## Problem

Campaign / `#Test_Database` dropdowns list Level / Logic / OpAmp folders, but the Run page always shows OPA tests and OPA gain boards. Brand is hard-coded `OPA ATE`. There is no product-family left rail (logo is decorative CSS only).

Evidence:

- `ate/ui/web/index.html` ~20: `<h1>OPA ATE</h1>`; `.logo` is decorative
- `ate/ui/web/app.js` ~846: `rpc("list_tests")` after opa-only registration; ~762-787 gain boards from `list_fixture_modes`
- `ate/ui/web/app.js` ~914-916 / ~1018-1023: START disabled unless `sessionOpen` (must keep)
- `ate/worker/server.py` ~124-145: `list_tests` / `list_fixture_modes` have no family parameter
- Readiness finding: left-rail score ~12; campaign folders != family plugins

T01 owns the load API; this ticket wires operator-visible switch + invariants.

---

## Acceptance

WHEN the operator selects Logic on the left rail, THE SYSTEM SHALL stop listing OpAmp-only fixture gain boards (G11 / G_NEG100 / VOS research chips) as applicable for that family and SHALL expose only that family's registered tests (empty list OK until A02).

WHEN the operator selects OpAmp, THE SYSTEM SHALL restore the existing OPA test list and OPA fixture / gain-board catalog, and brand copy SHALL reflect OpAmp (not remain stuck on Logic).

WHEN Level is shown, THE SYSTEM SHALL treat it as a stub slot (selectable or visibly stubbed; no fake Level characterization suite).

WHEN no instrument session is open, THE SYSTEM SHALL keep START disabled (`btn-start` remains gated on session open).

WHEN OpAmp is selected and the operator runs the existing OPA flow, THE SYSTEM SHALL preserve category-first board -> channel -> DUT ordering (no regression of 2026-08-07 category-first behavior).

---

## Why it is not a one-liner

Trap: changing only the campaign breadcrumb / DB component dropdown while tests stay OPA. Trap: using the logo as the rail. Trap: family switch that appends without calling T01 clear/reload. Trap: breaking START gate or category-first while adding chrome.

---

## Files likely touched

- `ate/worker/server.py` - RPC `set_family` / `get_family` (names flexible) calling T01 load API; optionally scope `list_fixture_modes` when Logic/Level
- `ate/ui/web/index.html` - left-rail markup (OpAmp / Logic / Level stub); brand heading hook
- `ate/ui/web/app.js` - rail click -> RPC -> refresh `list_tests` + gain boards + brand; keep START gate
- `ate/ui/web/styles.css` - minimal rail layout (not a redesign)
- May call into `ate/core/runner.py` load API from T01 - do not reintroduce opa-only sole import
- Fixture catalog: hide or empty OPA gain-board UI when family != opamp (`#gain-boards` / `renderGainBoards`)

Do **not** implement Logic `TestSpec` wraps of `logic_tests.py` (A02). Do **not** unlock OPA board gain.

---

## Step

```
Step: current: 5 / 5 - verified closed (2026-08-19; verifier != implementer)
```

Suggested steps:

1. Worker RPC for get/set active family -> T01 loader
2. Left rail HTML/CSS (not logo); Level stub honest
3. On switch: refresh tests + fixture/gain UI + brand copy
4. Confirm START still disabled without session; OpAmp restores OPA list
5. Note category-first verify path for adversary run; Ctrl+F5 note for operator

---

## Agent prompt

> Implement EPIC-A01 ticket A01-T02 only (RPC + UI left rail). Repo: PythonAutomation. Requires A01-T01 family load API already in tree.
>
> **Goal:** Operator left rail switches real apps: OpAmp / Logic / Level-stub. Selecting a family changes registered tests, fixture/gain-board presentation, and brand copy - not only the `#Test_Database` campaign path.
>
> **Do:**
> 1. Add worker RPC to get/set active family; call T01 clear+reload. Default boot = OpAmp.
> 2. Add a left-rail product switcher in `ate/ui/web/` (HTML/CSS/JS). Do **not** turn `.logo` into the rail - logo stays decorative.
> 3. On Logic: hide OPA gain boards (G11 / research chips) as applicable; `list_tests` shows Logic family only (empty OK).
> 4. On OpAmp: restore OPA tests + OPA fixture/gain catalog; brand follows family (e.g. not hard-stuck "OPA ATE" after visiting Logic).
> 5. Level = stub slot only (visible stub / disabled / empty - honest, no fake suite).
> 6. Preserve: `$("btn-start").disabled = !sessionOpen` and "Open Session first" guard. Preserve category-first OPA gate order when OpAmp selected (do not rewrite runner DUT/channel sequencing).
>
> **Constraints:**
> - Do not merge OPA+Logic registry ids (use T01 reload).
> - No wizard, no Tauri, no new framework.
> - Do not wrap `logic_tests.py` (A02).
> - Do not unlock OPA YAML board gain.
> - YAGNI: minimal CSS; reuse existing `list_tests` / `list_fixture_modes` refresh patterns in `app.js`.
>
> **Out of ticket:** A02 Logic wraps; A03 add-test docs; A04 per-family conditions UI.
>
> **Model:** implement with composer-2.5-fast. Do not self-close; different Grok 4.5 high run verifies.
>
> After worker/RPC changes, if idle restart via `restart_ate_worker.bat`. Tell operator Ctrl+F5 for static UI.

---

## Verify (different run - R-0003)

Verifier (Grok 4.5 high), not the implementer:

1. **Human / browser (preferred):** With worker+UI up, click Logic -> Run page shows no OPA gain chips as applicable and no OPA test grid (or empty Logic list). Click OpAmp -> OPA tests + gain boards return; brand matches OpAmp.
2. **START gate:** With no session (`session_status` open=false or Discover empty), START remains disabled.
3. **RPC:** `set_family`/`get_family` (or shipped names) + `list_tests` after Logic contains no OPA ids; after OpAmp contains known OPA ids.
4. **Category-first regression:** Code review of runner gate order unchanged for OpAmp, **or** short live Continue-path smoke if instruments available. Cite `docs/subagents_findings/2026-08-07_ate-category-first-order.md` as the behavior baseline.
5. Confirm logo is not the only/family control.

Close only if all Acceptance WHEN/SHALL hold; update epic ticket index in the same action.
