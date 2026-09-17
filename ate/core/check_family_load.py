"""Self-check: family load API clears registry on switch (A01-T01).

Also asserts family-scoped param catalog + timing (A04-T01).

Run: python -m ate.core.check_family_load
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from ate.core.param_defaults import (
    _OPA_SETTLE_DEFAULT_S,
    _OPA_SETTLE_SLEW_S,
    _OPA_TIMEOUT_S,
    catalog_for_ui,
    timing_for,
)
from ate.core.registry import TestSpec, all_tests, load_family

_OPA_PROBE_IDS = frozenset({"gbw", "slew"})
_LOGIC_PROBE_IDS = frozenset(
    {
        "tp",
        "supply_current",
        "cap_load",
        "delta_supply_current",
        "vih",
        "supply_current_sweep",
        "vih_vil",
        "voh_load",
        "vol_load",
        "input_threshold",
        "delta_icc",
        "ii",
        "ioz",
    }
)
_OPA_BOARD_MODES = frozenset({"G11", "G_NEG100", "G201", "G1001"})
_OPA_SETTLE_S = frozenset({_OPA_SETTLE_DEFAULT_S, _OPA_SETTLE_SLEW_S})


def _runner_uses_family_loader() -> None:
    runner_src = (
        Path(__file__).resolve().parent / "runner.py"
    ).read_text(encoding="utf-8")
    if re.search(r"import\s+ate\.tests\.opa\b", runner_src):
        raise AssertionError(
            "runner.py still has direct import ate.tests.opa "
            "(must use load_family / family table only)"
        )
    if "load_family" not in runner_src:
        raise AssertionError("runner.py must call load_family for registration")


def _assert_no_opa_timing_fallback(family: str) -> None:
    t = timing_for(family)
    if not t:
        raise AssertionError(
            f"timing_for({family!r}): expected family-local timing, got empty"
        )
    settle = t.get("settle_s")
    timeout = t.get("timeout_s")
    if timeout == _OPA_TIMEOUT_S and settle in _OPA_SETTLE_S:
        raise AssertionError(
            f"timing_for({family!r}): fell back to OPA settle/timeout "
            f"(settle_s={settle}, timeout_s={timeout})"
        )


def _assert_logic_catalog(catalog: dict) -> None:
    steps = catalog.get("gbw_steps") or []
    if any(s.get("id") == "cfg_g11" for s in steps):
        raise AssertionError("logic catalog: cfg_g11 step must not appear")
    profiles = catalog.get("gain_profiles") or {}
    if "G11" in profiles and profiles["G11"]:
        raise AssertionError("logic catalog: G11 gain_profiles must be empty")
    tests = catalog.get("tests") or {}
    if "gbw" in tests or "slew" in tests:
        raise AssertionError("logic catalog: must not expose OPA test defaults")


def _assert_opa_catalog(catalog: dict) -> None:
    steps = catalog.get("gbw_steps") or []
    if not any(s.get("id") == "cfg_g11" for s in steps):
        raise AssertionError("opamp catalog: missing cfg_g11 GBW step")
    profiles = catalog.get("gain_profiles") or {}
    if not profiles.get("G11"):
        raise AssertionError("opamp catalog: missing G11 gain_profiles")


def _assert_testspec_no_timing_fields() -> None:
    fields = getattr(TestSpec, "__dataclass_fields__", {})
    for name in ("settle_s", "timeout", "timeout_s"):
        if name in fields:
            raise AssertionError(f"TestSpec must not have {name!r} (A04-T01)")


def _check_family_conditions() -> None:
    _assert_testspec_no_timing_fields()

    opa_cat = catalog_for_ui("rs622", family="opamp")
    _assert_opa_catalog(opa_cat)

    logic_cat = catalog_for_ui("rs29511", family="logic")
    _assert_logic_catalog(logic_cat)
    if not logic_cat.get("tests"):
        raise AssertionError("logic catalog: tests dict must not be empty")
    # A09: rs29511 must not list Ariff-only DC ids
    if "delta_supply_current" in (logic_cat.get("tests") or {}):
        raise AssertionError("rs29511 catalog must not include Ariff delta_supply_current")
    ariff_cat = catalog_for_ui("rs1g08", family="logic")
    _assert_logic_catalog(ariff_cat)
    if "delta_supply_current" not in (ariff_cat.get("tests") or {}):
        raise AssertionError("rs1g08 catalog must include delta_supply_current")
    if "input_threshold" not in (ariff_cat.get("tests") or {}):
        raise AssertionError("rs1g08 catalog must include Path B input_threshold")
    if "icc" not in (ariff_cat.get("tests") or {}):
        raise AssertionError("rs1g08 catalog must include Path B icc")
    if "vccb" in ((ariff_cat.get("tests") or {}).get("icc") or {}):
        raise AssertionError("rs1g08 icc must not inherit RS0204 vccb")
    if "input_threshold" in (logic_cat.get("tests") or {}):
        raise AssertionError("rs29511 catalog must not include Path B input_threshold")
    if "cap_load" in (ariff_cat.get("tests") or {}):
        raise AssertionError("rs1g08 catalog must not include Soo cap_load")
    for need in ("vih_vil", "voh_load", "vol_load", "supply_current_sweep"):
        if need not in (ariff_cat.get("tests") or {}):
            raise AssertionError(f"rs1g08 catalog must include {need}")
    if "voh_load" in (logic_cat.get("tests") or {}) or "vih_vil" in (logic_cat.get("tests") or {}):
        raise AssertionError("rs29511 catalog must not include Ariff voh_load/vih_vil")
    if "vol_load" in (logic_cat.get("tests") or {}):
        raise AssertionError("rs29511 catalog must not include Ariff vol_load")
    if "supply_current_sweep" in (logic_cat.get("tests") or {}):
        raise AssertionError("rs29511 catalog must not include supply_current_sweep")
    rs0204_cat = catalog_for_ui("rs0204", family="logic")
    _assert_logic_catalog(rs0204_cat)
    if "vih" not in (rs0204_cat.get("tests") or {}):
        raise AssertionError("rs0204 catalog must include vih")
    if (rs0204_cat.get("tests") or {}).get("vih", {}).get("vccb") != 3.3:
        raise AssertionError("rs0204 catalog must overlay vccb from part yaml")
    if "cap_load" in (rs0204_cat.get("tests") or {}):
        raise AssertionError("rs0204 catalog must not include Soo cap_load")
    if "gbw" in (rs0204_cat.get("tests") or {}):
        raise AssertionError("rs0204 catalog must not expose gbw")

    demo_cat = catalog_for_ui("rs622", family="demo_ingest")
    _assert_logic_catalog(demo_cat)

    unknown_cat = catalog_for_ui("rs622", family="unknown_family_xyz")
    _assert_logic_catalog(unknown_cat)

    slew_t = timing_for("opamp", "slew")
    if slew_t.get("settle_s") != _OPA_SETTLE_SLEW_S or slew_t.get("timeout_s") != _OPA_TIMEOUT_S:
        raise AssertionError(f"opamp slew timing mismatch: {slew_t}")

    _assert_no_opa_timing_fallback("logic")
    _assert_no_opa_timing_fallback("switch")
    _assert_no_opa_timing_fallback("lim")
    _assert_no_opa_timing_fallback("power")
    _assert_no_opa_timing_fallback("demo_ingest")

    from ate.core.database import family_for_component

    if family_for_component("demo_ingest") != "demo_ingest":
        raise AssertionError("family_for_component(demo_ingest) must match extra family key")
    if family_for_component("AnalogSwitch") != "switch":
        raise AssertionError("family_for_component(AnalogSwitch) must be switch")
    if family_for_component("Power") != "power":
        raise AssertionError("family_for_component(Power) must be power")

    switch_cat = catalog_for_ui("rs2323", family="switch")
    _assert_logic_catalog(switch_cat)
    if "iplus" not in (switch_cat.get("tests") or {}):
        raise AssertionError("switch catalog: iplus missing")
    if "gbw" in (switch_cat.get("tests") or {}):
        raise AssertionError("switch catalog must not expose gbw")
    rs2227_cat = catalog_for_ui("rs2227", family="switch")
    if "iplus" not in (rs2227_cat.get("tests") or {}):
        raise AssertionError("rs2227 analog-switch catalog must include iplus")
    power_cat = catalog_for_ui("rs3213", family="power")
    _assert_logic_catalog(power_cat)
    if "iq" not in (power_cat.get("tests") or {}):
        raise AssertionError("power catalog: iq missing")
    if "gbw" in (power_cat.get("tests") or {}):
        raise AssertionError("power catalog must not expose gbw")
    ariff_ctrls = {c["id"]: c for c in (ariff_cat.get("controls") or []) if isinstance(c, dict)}
    if (ariff_cat.get("psu_golden") or {}).get("current_limit_a") != 0.05:
        raise AssertionError("rs1g08 psu_golden current_limit_a must overlay 0.05 from part yaml")
    if "vcc" not in ariff_ctrls:
        raise AssertionError("rs1g08 catalog controls must include vcc")
    ariff_choices = ariff_ctrls["vcc"].get("choices") or []
    if 1.65 not in ariff_choices or 5.5 not in ariff_choices:
        raise AssertionError(f"rs1g08 vcc dropdown missing sweep corners: {ariff_choices}")
    rs0204_ctrls = {c["id"]: c for c in (rs0204_cat.get("controls") or []) if isinstance(c, dict)}
    if "vccb" not in rs0204_ctrls:
        raise AssertionError("rs0204 catalog controls must include vccb")
    switch_ctrls = {c["id"]: c for c in (switch_cat.get("controls") or []) if isinstance(c, dict)}
    if "vcc" not in switch_ctrls:
        raise AssertionError("switch catalog controls must include vcc")
    if 3.3 not in (switch_ctrls["vcc"].get("choices") or []):
        raise AssertionError("rs2323 vcc dropdown must include 3.3 from vcc_sweep")
    if demo_cat.get("controls"):
        raise AssertionError("demo_ingest + rs622 must not inherit OpAmp vcc controls")


def main() -> int:
    _runner_uses_family_loader()
    _check_family_conditions()

    load_family("opamp")
    opa_ids = {t.id for t in all_tests()}
    if not opa_ids:
        raise AssertionError("load_family(opamp): all_tests() empty")
    missing = _OPA_PROBE_IDS - opa_ids
    if missing:
        raise AssertionError(
            f"load_family(opamp): missing expected OPA ids {sorted(missing)}"
        )

    load_family("logic")
    logic_ids = {t.id for t in all_tests()}
    if not logic_ids:
        raise AssertionError("load_family(logic): all_tests() empty")
    missing_logic = _LOGIC_PROBE_IDS - logic_ids
    if missing_logic:
        raise AssertionError(
            f"load_family(logic): missing expected Logic ids {sorted(missing_logic)}"
        )
    bad_modes = {
        t.fixture_mode
        for t in all_tests()
        if t.fixture_mode in _OPA_BOARD_MODES
    }
    if bad_modes:
        raise AssertionError(
            f"load_family(logic): OPA fixture modes on Logic specs: {sorted(bad_modes)}"
        )
    leaked = opa_ids & logic_ids
    if leaked:
        raise AssertionError(
            f"load_family(logic): OPA ids still in registry: {sorted(leaked)}"
        )

    loaded_level = load_family("level")
    if loaded_level != "level":
        raise AssertionError(f"load_family(level) returned {loaded_level!r}, want 'level'")
    level_ids = {t.id for t in all_tests()}
    if "vih" not in level_ids:
        raise AssertionError("load_family(level) must not be an empty stub")
    if opa_ids & level_ids:
        raise AssertionError(f"load_family(level): OPA ids leaked: {sorted(opa_ids & level_ids)}")

    load_family("switch")
    lim_ids = {t.id for t in all_tests()}
    if "iplus" not in lim_ids:
        raise AssertionError("load_family(switch): missing iplus")
    if load_family("lim") != "switch":
        raise AssertionError("load_family(lim) must alias to switch")
    lim_ids = {t.id for t in all_tests()}
    lim_opa = opa_ids & lim_ids
    if lim_opa:
        raise AssertionError(f"load_family(switch): OPA ids leaked: {sorted(lim_opa)}")
    lim_bad = {
        t.fixture_mode for t in all_tests() if t.fixture_mode in _OPA_BOARD_MODES
    }
    if lim_bad:
        raise AssertionError(f"load_family(switch): OPA fixture modes: {sorted(lim_bad)}")

    load_family("opamp")
    restored = {t.id for t in all_tests()}
    if not restored:
        raise AssertionError("load_family(opamp) after switch: all_tests() empty")
    missing_restore = _OPA_PROBE_IDS - restored
    if missing_restore:
        raise AssertionError(
            f"load_family(opamp) after switch: missing OPA ids {sorted(missing_restore)}"
        )
    logic_leak = logic_ids & restored
    if logic_leak:
        raise AssertionError(
            f"load_family(opamp) after switch: Logic ids leaked: {sorted(logic_leak)}"
        )
    lim_leak = lim_ids & restored
    if lim_leak:
        raise AssertionError(
            f"load_family(opamp) after switch: switch ids leaked: {sorted(lim_leak)}"
        )

    load_family("power")
    pwr_ids = {t.id for t in all_tests()}
    if "iq" not in pwr_ids:
        raise AssertionError("load_family(power): missing iq")
    if opa_ids & pwr_ids:
        raise AssertionError(f"load_family(power): OPA ids leaked: {sorted(opa_ids & pwr_ids)}")
    load_family("opamp")
    restored = {t.id for t in all_tests()}
    if pwr_ids & restored:
        raise AssertionError(f"load_family(opamp) after power: LDO ids leaked: {sorted(pwr_ids & restored)}")

    load_family("demo_ingest")
    demo_ids = {t.id for t in all_tests()}
    if "demo_probe" not in demo_ids:
        raise AssertionError("load_family(demo_ingest): missing demo_probe")
    if opa_ids & demo_ids:
        raise AssertionError(
            f"load_family(demo_ingest): OPA ids leaked: {sorted(opa_ids & demo_ids)}"
        )
    load_family("opamp")
    restored = {t.id for t in all_tests()}
    if _OPA_PROBE_IDS - restored:
        raise AssertionError("load_family(opamp) after demo_ingest: OPA ids missing")

    load_family("")
    if all_tests():
        raise AssertionError("load_family(''): stub must leave registry empty")
    if load_family("") != "":
        raise AssertionError("load_family('') must return empty family key")
    load_family("opamp")
    restored = {t.id for t in all_tests()}
    if _OPA_PROBE_IDS - restored:
        raise AssertionError("load_family(opamp) after stub clear: OPA ids missing")

    print(
        f"OK opamp={len(opa_ids)} logic={len(logic_ids)} level={len(level_ids)} switch={len(lim_ids)} "
        f"power={len(pwr_ids)} demo={len(demo_ids)} restored={len(restored)} tests (no cross-family leak); "
        f"family-scoped catalog/timing OK"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
