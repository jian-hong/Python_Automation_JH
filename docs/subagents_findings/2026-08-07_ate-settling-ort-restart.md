---
keywords: ate, settling, ort, gbw, restart, BUFFER, G_NEG100, desktop-shortcut
main_idea: Separate Settling (BUFFER) / ORT (G_NEG100) / GBW (G11); desktop OPA ATE.lnk now restarts 8766+5174; ORT uses live channel; Settling locks 200ns/500mV scales from operator shot.
---

# 2026-08-07 ATE Settling / ORT / restart

## Done
- `restart_ate_app.bat` + desktop `OPA ATE.lnk` retargeted
- `ate/tests/opa/settling.py` registered `settling` / BUFFER
- `ort.py` passes `params.channel`; POS/NEG presets frozen
- Worker restarted idle; list_tests shows three fixture modes

## Operator
Ctrl+F5 console. Pick tests individually. Campaign OpAmp/RS622/TTSOP8/Version_1.
