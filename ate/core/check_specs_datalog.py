"""Self-check: measurement stamp honesty vs limits yaml.

Run: python -m ate.core.check_specs_datalog
"""
from __future__ import annotations

import sys


def main() -> int:
    errors: list[str] = []
    from ate.core.specs import enrich_measurement, judge_value, load_part_specs

    if judge_value(0.1, -1, 1) != "pass":
        errors.append("in-window pass")
    if judge_value(9, None, 1) != "fail":
        errors.append("over max fail")
    if judge_value(4.9, 4.8, 9, pass_mode="min-only") != "pass":
        errors.append("min-only must ignore max")
    if judge_value(0.2, 1, 0.5, pass_mode="max-only") != "pass":
        errors.append("max-only must ignore min")
    if judge_value(0.4, 1, 2, pass_mode="range") != "fail":
        errors.append("range below min must fail")
    specs = load_part_specs("rs622")
    row = enrich_measurement({"id": "VOS_mV", "value": 0.7}, specs=specs, test_id="vos_sweep")
    if row.get("result") != "pass" or row.get("max") != 3.0:
        errors.append(f"VOS enrich {row}")
    row2 = enrich_measurement({"id": "VOS_mV", "value": 9}, specs=specs, test_id="vos_sweep")
    if row2.get("result") != "fail":
        errors.append(f"VOS over max {row2}")
    from ate.tests.opa.noise import input_referred_uvpp
    from ate.tests.opa.mapped_dc import CASES

    if abs(input_referred_uvpp(0.011011, 1001) - 11.0) > 0.05:
        errors.append("noise input-referred math")
    if any(c.test_id == "noise" for c in CASES):
        errors.append("noise must not stay a mapped_dc screenshot stub")
    en = next((s for s in specs if s.get("id") == "EN_1kHz_nVrtHz"), {})
    if en.get("typ") != 11:
        errors.append(f"EN_1kHz typ must be 11 from RS62X table, got {en}")
    vn = enrich_measurement({"id": "VN_IN_PP_uV", "value": 12}, specs=specs, test_id="noise")
    if vn.get("result") != "unspec":
        errors.append(f"VN_IN_PP_uV must stay unspec without min/max, got {vn}")
    from pathlib import Path
    import tempfile

    root = Path(__file__).resolve().parents[1]
    vos_src = (root / "tests" / "opa" / "vos.py").read_text(encoding="utf-8")
    if '"id": "VOS_mV"' not in vos_src:
        errors.append("vos_sweep must return VOS_mV measurement (not only fit.vos_mV)")
    voh_src = (root / "tests" / "logic" / "ariff_dc.py").read_text(encoding="utf-8")
    if "VOH_{" not in voh_src:
        errors.append("voh_load must emit VOH_* measurements")
    if "ICC_uA" not in voh_src:
        errors.append("supply_current_sweep must return ICC_uA")
    iplus_src = (root / "tests" / "lim" / "rs2323.py").read_text(encoding="utf-8")
    if "IPLUS_uA" not in iplus_src:
        errors.append("iplus must return IPLUS_uA")
    rs0204_src = (root / "tests" / "logic" / "rs0204.py").read_text(encoding="utf-8")
    if "VOH_DROP_V" not in rs0204_src or "ICC_uA" not in rs0204_src:
        errors.append("rs0204 voh/icc must return VOH_DROP_V and ICC_uA")
    from ate.core.specs import mock_demo_measurements

    icc_demo = mock_demo_measurements("supply_current_sweep", part_key="rs1g08")
    if not any(m.get("id") == "ICC_uA" for m in icc_demo):
        errors.append(f"DEMO supply_current_sweep must stamp ICC_uA, got {icc_demo}")
    from ate.reporting.sts_datalog import export_sts

    tmp = Path(tempfile.mkdtemp(prefix="ate_sts_"))
    exported = export_sts(
        {
            "header": {"time": "t"},
            "identity": {"part": "RS622", "operator": "Eugene"},
            "steps": [
                {
                    "test_id": "gbw",
                    "dut": 1,
                    "success": True,
                    "measurements": [
                        {
                            "id": "GBW_MHz",
                            "unit": "MHz",
                            "typ": 7,
                            "value": 7,
                            "result": "unspec",
                        }
                    ],
                }
            ],
        },
        tmp,
    )
    pdf = Path(exported["pdf"]).read_bytes()
    if b"Parameter" not in pdf or b"GBW_MHz" not in pdf:
        errors.append("STS PDF must be a column table containing Parameter and GBW_MHz")
    sw = load_part_specs("rs2323")
    if any(s.get("id") in ("SR_Vus", "GBW_MHz") for s in sw):
        errors.append("rs2323 must not carry RS222 opamp slew/GBW")
    ldo = load_part_specs("rs3213")
    if any(s.get("id") in ("SR_Vus", "GBW_MHz") for s in ldo):
        errors.append("rs3213 LDO must not carry RS358 opamp slew/GBW")
    from ate.core.lookup import INDEX_PATH

    if not INDEX_PATH.is_file():
        errors.append("build datasheets.yaml first (check_lookup)")
    if errors:
        print("FAIL check_specs_datalog:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("OK check_specs_datalog")
    return 0


if __name__ == "__main__":
    sys.exit(main())
