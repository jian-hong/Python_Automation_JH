# 2026-09-21 JH coordinator P1/P2 -- vanilla D&D + excel/VOL/HANDOVER

**Keywords:** path-b, xyflow, logic-dc-flow, customise, vcc_plan, PSU_MSO, NAND, NOR, INV, XOR, dual_channel_continue, do not skip rewire, golden_auto, excel_plots, VOL board-change, 5-step cheat, inventory

**main_idea:** P0 already CONFIRMED (ate_ds_extract/models still missing). P1 is vanilla `#logic-dc-flow` pin/wiring D&D (layout only) -- No xyflow npm -- plus family scale NAND/NOR/INV/XOR/dual CHA then CHB do-not-skip-rewire. P2 binds golden_auto excel_plots (vih/vil/icc/ii only) on the 6 scale-wave YAMLs, inventory rows without invented lots, GT34 VOL recable in format_handoff_begin, HANDOVER 5-step cheat. 17 CONFIRMED SIM stay. G07 VOH N_A. G74/G123 PARKED. No invent ICCT/OE/VOL live.

## Traps

- `_panel_ok` fails if `xyflow` is in app.js without contiguous `no xyflow`. Phrase "No xyflow npm" (not only "No React xyflow").
- `check_ui_contract` bans `if !foo` without parens -- always `if (!foo)`.
- Family hint must test `nor` before generic `or` (gate_nor2 contains "or").
- Scale-wave excel_plots must not bind voh/vol/ioz/delta_icc (tests not enabled).
- Overlay must not demote CONFIRMED vcc_grid.status (collectVccGridFromUi keeps prev.status).
- live.vol stays NOT_RUN; recable lines only, no invented measured rows.
- HANDOVER.md and docs/LOGIC_DC_HANDOVER.md must stay twins (sequential cp, not parallel Write).
- SHA chicken-egg: stamp operator doc with content SHA, then stamp commit is new HEAD.
