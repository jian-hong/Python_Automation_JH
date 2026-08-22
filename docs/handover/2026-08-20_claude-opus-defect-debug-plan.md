# Claude Code brief: ATE recurring defects -> generate, execute, debug

**Product:** PythonAutomation ATE (`C:\Users\OoiJianHong\Eugene's Repo\PythonAutomation`)
**For:** Claude Code **Opus** only (Cursor cannot dispatch you)
**Date:** 2026-08-20
**Do not** dual-lane this tree while Cursor is also editing (F-0009). One writer.

Copy everything from "PASTE START" through "PASTE END" into Claude Code.

---

PASTE START

You are Claude Code Opus on PythonAutomation ATE. Your job is not a new platform epic. Your job is to **find, prove, and fix the defects we keep shipping as if they were features**. Generate a failing check first, execute it, then debug until the check fails when the defect is present and passes when fixed.

## Law

- Laptop-ASCII only: `-` `--` `>=` `<=` `->` `'` `"` `...`
- Ponytail: fewest files. No wizard, no Tauri, no new plugin framework, no delete of `main.py`.
- Preserve: category-first board -> channel -> DUT, START disabled until Open Session, OPA YAML board-gain lock, `load_family()` clear/reload, left rail (not `.logo`).
- Ports: worker **8766**, UI **5174**. Never 8765 / 3000 / 3001 / 5000.
- Before killing the worker: RPC `session_status`; if `busy=true` do not restart.
- Idle restart: `restart_ate_worker.bat`. UI JS: tell operator **Ctrl+F5**.
- Shell: if PowerShell dies on `Eugene's Repo`, use `C:\Users\OoiJianHong\EUGENE~1\PYTHON~1`.
- Do not open GitHub Issues. Local files under `docs/tickets/` if you must ticket.
- After each real fix: one runnable check that **fails if the bug returns**.

## 1. Start here (prove the tree, then hunt)

Run in order. Time is wall-clock on this Windows host.

1. `venv\Scripts\python.exe -m ate.core.check_family_load`
   Proves: family switch registry. Does **not** prove a test can run. ~10s.
2. POST JSON-RPC `http://127.0.0.1:8766` methods `ping`, `get_family`, `session_status`.
   Proves: worker alive. Does **not** prove instruments. If down and idle, start `run_ate_worker.bat`. ~15s.
3. `set_family` `logic` then `list_tests`; then `set_family` `opamp` then `list_tests`.
   Proves: 7 Logic ids / 16 OPA ids. Does **not** prove wrap bodies. ~20s.
4. Open `http://127.0.0.1:5174` (or `ate\ui\dev_server.py` on 5174). Ctrl+F5. Click Logic then OpAmp.
   Proves: rail + brand + gain boards hide. Does **not** prove START or hardware. ~1 min.

If step 1 fails, **stop product work** and restore family load. Everything below assumes A01/A02 still hold.

## 2. Where defects keep happening (root classes)

These are the repeating failure classes. Fix the class, not one call site.

### D1. Dual stack: two `Instruments` worlds

**What is wrong:** Operator console uses `ate.instruments.session.Instruments` (MSO/PSU/AWG, **no `dmm`**, DMM not in `find_instruments`). Legacy `logic_tests.py` does `dmm = instr.dmm`. Wraps in `ate/tests/logic/wraps.py` call those functions with the ATE session object.

**Where it bites:** `test_supply_current`, `test_output_voltage`, `test_cap_load` (required `DMM`). Timing tests (`tp`/`tidle`/`tdis`/`ten`) need `.scope` `.psu` `.gen` which exist, but still assume PSU/AWG connected.

**False green:** `check_family_load` and `list_tests` show `supply_current` as runnable. `_run_one` then raises `Missing instruments: ['DMM']` or `AttributeError: dmm`.

**Fix direction:** one of (pick cheapest that is honest):
- A) Skip/hide Logic tests whose `required_instruments` are not in `available_devices()` **in the UI** (not only at run fail), and/or
- B) Open DMM in `ate/instruments/session.py` + IDN match in `discovery.py` when Keithley is on the bus, and set `instr.dmm`.

Do not rewrite `logic_tests.py` measurement bodies.

**Stops at until you add a check:** listing 7 tests.

### D2. Stubs look like real tests

**What is wrong:** `ate/tests/opa/stubs.py` registers 9 tests with `enabled=True`. `_run` raises `RuntimeError("... not automated yet")`. Operator checks SSSR/LSSR/PSRR/... and the sequence **fails**.

**Where it bites:** BUFFER group after slew/settling; ATE group (PSRR/CMRR/AOL/VOHL/EMIRR). Same class every time a stub is left enabled.

**Fix direction:** `enabled=False` **or** UI marks stub/not-runnable and START ignores them. Do not delete the stubs (they document yellow lab-report sheets).

**Stops at:** hiding them in CSS only while RPC still returns them as startable.

### D3. Self-check theater

**What is wrong:** We closed epics on `check_family_load` + `list_tests`. That cannot fail D1, D2, VISA poison, or logger omission.

**Where it bites:** every "verify" that greps ids.

**Fix direction:** add a **no-hardware** check that:
- Builds a fake `Instruments` with no `dmm` and asserts DMM Logic wraps do not claim success.
- Imports stub `_run` and asserts they are not in the default selected set / are disabled.
- Optionally `inspect.signature` / `co_names` that Logic wraps still call `logic_tests.test_*`.

A check that cannot fail is not a check.

### D4. Worker / UI process cache

**What is wrong:** Python worker does not reload modules. JS is cached (`app.js?v=...`). Operator sees old rail / empty Logic / old brand. Agents "fix" code the running process is not executing.

**Where it bites:** every UI/RPC change; `Eugene's Repo` apostrophe also breaks some agent shells so they restart the wrong cwd.

**Fix direction:** after `ate/core`, `ate/worker`, `ate/tests` edits: idle-check then `restart_ate_worker.bat`. After `ate/ui/web/*`: bump `?v=` cache token **and** say Ctrl+F5. Confirm with `ping` version or a log line you just added.

**Stops at:** editing files without a live RPC round-trip.

### D5. VISA `VI_ERROR_SYSTEM_ERROR` / screenshot poison

**What is wrong:** MSO `:DISP:DATA?` leftover bytes poison the next query. Recurs on GBW/ORT/slew screenshot paths.

**Where it already is:** `scope_setup.recover_scope_session`, runner pre-run recover, GBW retry with screenshots off, emergency MSO reopen.

**Where it still bites:** any new capture that skips recover; timeout 3s vs screenshot 10s; Ultra Sigma holding VISA.

**Fix direction:** do not add a second recover helper. Grep every `DISP:DATA` / screenshot caller; if it does not call `recover_scope_session` after failure, that is the bug. Live debug only with instruments.

**Stops at:** unit tests without a scope.

### D6. Campaign tree vs family rail

**What is wrong:** `#Test_Database` Component dropdown (OpAmp/Logic/Level folders) is **not** `set_family`. Operator can sit on Logic rail with OpAmp campaign paths (or the reverse). We already shipped this confusion once as "platform".

**Where it bites:** photos/lab report land under the wrong family folder; operator thinks Apply campaign switched tests.

**Fix direction (minimum):** when rail family and `db-component` disagree, show a one-line warning in Setup. Optional later: selecting rail suggests matching component. Do not silently rewrite the DB tree.

**Stops at:** warning text without a test that the mismatch is visible.

### D7. Docs that still describe the old bug

**What is wrong:** PRD section 4 "Code anchors" still says `_ensure_tests_registered` -> `import ate.tests.opa` and "no `ate/tests/logic`". `TEST_DESIGN.md` still teaches `main.py` as the way to add tests. Agents re-open the opa-only import because the PRD told them it is current.

**Fix direction:** patch those anchors to `load_family` / `ate/tests/logic/wraps.py`. Keep dual-stack warning: console = `ate/`; CLI = `main.py`.

**Stops at:** README poetry.

### D8. Wrap contract holes (Logic)

**What is wrong:**
- Wraps call `legacy_fn(instr, params.vcc)` and drop `logger=None` -> no `datalog.py` lines from the console path.
- `current_limit` comes from `configurations` inside `logic_tests`; ATE `RunParams.current_limit_a` is unused by wraps.
- `cap_load` ignores `params` entirely.

Not all of these must be fixed this run. **Must** not pretend DMM tests work (D1). Logger/datalog is worth doing if cheap; do not invent a new logger stack.

### D9. Empty Discover is not an app crash

**What is wrong:** 2026-08-19 demo `Discovered {}`. People treat that as the UI being broken. START correctly stays disabled.

**Rule:** if `discover` is `{}`, fix USB/VISA/Ultra Sigma, not the glass UI. Do not fake mapping.

### D10. False FAIL from stubs + missing DMM in one START

**What is wrong:** Operator selects "all BUFFER" including stubs, or Logic including DMM tests, one START, first stub/DMM miss aborts confidence in the whole platform.

**Fix:** D2 + D1 UI filtering. Keep run-abort on real measurement errors.

## 3. What already changed (do not regress)

| Change | What was wrong | What changed | Stops at |
|--------|----------------|--------------|----------|
| A01 family load | Rail would be paint; runner imported opa only | `load_family` + `clear` + `FAMILY_PACKAGES` | Live test execution |
| A01 left rail | Campaign dropdown != tests | `.family-rail` + `get_family`/`set_family` | Hardware |
| A02 Logic wraps | Logic rail empty | 7 thin wraps of `logic_tests.test_*` | DMM/logger/live TP |
| Category-first | Wrong prompt order | board -> channel -> DUT | New families using OPA modes |
| VISA recover | Screenshot poison | `recover_scope_session` | Call sites that skip it |
| Safe idle | PSU/AWG live during Continue | `_safe_idle_for_operator` | Tests that skip idle |

Do not re-harden `import ate.tests.opa` in `runner.py`.

## 4. Execute order (generate -> run -> debug)

One lane. After each job, leave the check that fails if the job is undone.

### Job 1 - Make D1 fail in CI/self-check (no bench)

Generate a tiny check (extend `ate/core/check_family_load.py` or sibling `ate/core/check_wrap_contract.py`):

- `load_family("logic")`
- For ids `supply_current`, `output_voltage`, `cap_load`: `required_instruments` must include `DMM`
- Assert `ate.instruments.session.Instruments` source has no `self.dmm` **or** discovery can return `DMM` -- currently it cannot. The check should **name the gap**: either implement DMM open **or** assert UI/RPC `filter_runnable` would skip them.

Then implement the honest skip **or** DMM open. Prefer skip/hide until Keithley is actually on the bench (discovery has no DMM IDN branch today).

Debug: run the new check; it must go red if someone registers those tests as requiring only PSU.

### Job 2 - Stubs not startable (D2)

`enabled=False` on `_stub(...)` **or** UI refuses START if any selected test has `notes` containing Stub / `enabled=false`. RPC `list_tests` must expose `enabled`. Default OpAmp test grid should not look like PSRR is a one-click pass.

Check: grep that stub `register(... enabled=True)` is gone; or a self-check that stub ids are disabled.

### Job 3 - Stale PRD/TEST_DESIGN anchors (D7)

Edit PRD section 4 code anchors to match `load_family`. Add one paragraph to `TEST_DESIGN.md`: console tests register under `ate/tests/<family>/`, not only `main.py`.

### Job 4 - Family vs campaign warning (D6)

One hint in Setup when `get_family` and `db-component` disagree. No auto-rewrite of folders.

### Job 5 - Live bench debug (only if Discover is non-empty)

Human must have MSO/PSU/AWG. Then:

1. Discover -> Open Session. If missing PSU/AWG, do not lie.
2. OpAmp: one test only (`slew` or `gbw`), DUT 1, CHA. Watch log for `VI_ERROR_SYSTEM_ERROR`. If it fires, confirm `recover_scope_session` ran; if a new capture path skipped it, that is the patch.
3. Do **not** START stub tests.
4. Logic timing (`tp`) only if PSU+AWG present. Do not START DMM tests until Job 1 is honest.
5. STOP must safe-idle (PSU off, AWG parked).

If Discover is `{}`, stop Job 5 and report bench, not code.

### Job 6 - Optional logger pass-through (D8)

If Job 1-2 are done and you have budget: pass a no-op or ATE session logger into `legacy_fn(..., logger=...)`. Do not require Excel `limits.TEST_SPECS` to succeed the wrap if that blocks. If `log_test` would raise on unknown names, catch and log -- do not crash the run.

## 5. Numbers (last measured, 2026-08-20 unless re-run)

Re-run before you trust these.

| Gate | Last result | Where |
|------|-------------|--------|
| `python -m ate.core.check_family_load` | `OK opamp=16 logic=7 restored=16` | local venv |
| `set_family logic` `list_tests` | 7 ids, `fixture_mode=LOGIC` | RPC 8766 |
| `list_fixture_modes` on Logic | `[]` | RPC |
| `set_family opamp` | 16 tests, 6 fixture modes | RPC |
| Discover (2026-08-19 demo) | `{}` | browser MCP |
| DMM on ATE session | **absent** | `ate/instruments/session.py` |
| Stub tests | 9 enabled RuntimeError | `ate/tests/opa/stubs.py` |
| START without session | disabled | `app.js` |

## 6. Corrections (discard these older claims)

- "Logic family works" meant **list_tests non-empty**, not a passing TP/IDD run.
- PRD anchors that still mention opa-only `_ensure_tests_registered` are **stale**, not current architecture.
- Empty Discover is **not** a glass-UI defect.
- Closing A02 did **not** prove `instr.dmm` exists.

## 7. Out of scope this Claude run

- EPIC-A03 add-test docs wizard / A04 conditions UI (unless Job 1-4 are done and founder asks)
- Full Level suite
- Deleting `main.py`
- Faking instruments
- Unlocking OPA board gain
- Dual Cursor + Claude writers

## 8. What needs the human

1. Plug MSO/PSU/AWG (and optional Keithley) or accept Job 5 skipped.
2. Close Ultra Sigma if VISA is busy.
3. Ctrl+F5 after you bump UI cache.
4. Do not START yellow stub sheets until Job 2 lands.
5. If you want DMM Logic live, say so -- that is Job 1 path B, not skip.

## 9. Done when

- New self-check fails if DMM Logic tests are presented as runnable without DMM.
- Stub tests cannot be STARTed as if automated.
- PRD/TEST_DESIGN no longer teach the opa-only import as current.
- Family vs campaign mismatch is visible.
- `check_family_load` still green (A01/A02 not regressed).
- You write `docs/subagents_findings/YYYY-MM-DD_claude-defect-debug.md` with keywords + main_idea and update `docs/subagents_findings/INDEX.md`.

PASTE END
