# Modular OPA ATE

Liquid-glass operator UI + hidden Python JSON-RPC worker.  
Strong reference: `C:\Users\OoiJianHong\LabAutomation_14.7` (Eugene recipes, Lim registry).

## Quick start

1. Double-click desktop **OPA ATE** shortcut, or run `run_ate_app.bat`
2. Worker listens on `http://127.0.0.1:8766` (8765 is AirGPT — leave it alone)
3. UI opens at `http://127.0.0.1:5174`
4. **Discover → Open Session →** select tests → **START**
5. On fixture change, confirm the operator checklist (STM stub later)

Lab report target: `C:\Users\OoiJianHong\Downloads\RS622XK_Lab_Report_TTSOP.xlsx`

Plug-in scale checklist: docs/ATE_PLUGIN.md (family package, register, campaign tree, sheet_map).

## Layout

```
ate/
  core/         runner, registry, events, paths
  fixture/      modes, operator gate, stm_bridge stub
  instruments/  discovery + session
  drivers/      mso5072 (live JPEG capture)
  tests/opa/    vos, ac_*, slew, gbw, ort, stubs
  reporting/    lab_report.py (ORT photo boxes)
  worker/       JSON-RPC server
  ui/web/       liquid-glass frontend
  ui/src-tauri/ Tauri shell (needs Rust)
  config/       bench.yaml, parts/rs622.yaml
```

## Tauri (choice 1A)

Rust was not installed on this PC at scaffold time. Web UI runs now via `dev_server.py`.  
To finish the native shell:

```bat
winget install Rustlang.Rustup
cd ate\ui
cargo install tauri-cli
cargo tauri build
```

## Fixture modes (batch without prompt)

| Mode | Tests |
|------|--------|
| G201 | vos_sweep, ac_gain_check, ac_vin_sweep |
| BUFFER | slew (+ settling/sssr/lssr stubs) |
| G11 | gbw |
| G_NEG100 | ort → embeds JPEG into ORT sheet |

## Legacy

`run_ate_panel.bat` / `ate_panel.py` still work. Prefer `run_ate_app.bat`.
