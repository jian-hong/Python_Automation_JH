# SIM-first CONFIRMED Path B DC walk

Keywords: path-b, logic-dc, SIM, TestSpec.run, visa-free, rs1gt34, rs1g97, rs1g126, rs1g08, rs1g07, rs1g14, rs1g32, rs1gt08, rs1gt32, rs1g125, rs164, interpolate, vplus, PSU CH3, 0.65*VCC, Schmitt VT, ICCT provisional, HOLD rs1g74 rs1g123

Main idea: `check_logic_dc._confirmed_sim_sweep_ok` walks enabled Path B `TestSpec.run` with mock PSU/DMM/AWG/MSO and patched `power_on_protected` (no 1.5s sleep). Overlay recipe settle only -- never overlay `vcc_list` (pops CONFIRMED `vcc_grid`).

FAIL fixes:
- `vcc_grid_owned` evaluates card `N*VCC` / `VCC-0.1` per step so formula bands get numeric VIH/VIL (else search limit=None).
- PSU_MSO leftover after CH3 defaults to AWG CH1+ (DP832 has no CH4; CH2 stays Y-load).
- `_logic_vplus` skips OpAmp `vplus_v` on PSU CH3 when CH3 is a logic input (G32 VOL was measuring VCC).
- `threshold_search` interpolate uses last (finest) crossing; rearm uses this-stage `points` index not `samples`.
- `_provisional_dc(delta_icc)` follows unsigned ICCT (process still runs via `_icct_blob`).
- Schmitt VT+/- attach CONFIRMED range min/max from `vcc_grid` (not plain VIH).
- SIM DUT is edge-aware combinational so search rearm un-trips (Schmitt-hold would keep Y high and freeze coarse 1.0/1.5 midpoint).

HOLD: rs1g74 / rs1g123 UNCONFIRMED sequential stubs (Path B ids OFF; no CONFIRMED unlock; no invent VT+/-). RS164 Path B ids OFF. G07 voh OFF. G97 ioz OFF. Do not invent limits. Not Verify PASS.
