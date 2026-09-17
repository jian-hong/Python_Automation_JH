"""Self-check for F23 / A16 detect-wrap-copy.

Run: python -m ate.core.check_test_detect
"""
from __future__ import annotations

import sys
from pathlib import Path

from ate.core import test_detect as td
from ate.core.paths import REPO_ROOT

FIXTURE_DIR = Path(__file__).resolve().parent / "_check_data"
FIXTURE_PY = FIXTURE_DIR / "detect_probe_source.py"


def _write_fixture() -> Path:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    FIXTURE_PY.write_text(
        '''\
"""Fixture for check_test_detect — not a live family module."""

def test_detect_probe(instr, logger=None):
    """Clean golden: has instr, no stdin prompts."""
    psu = instr.psu
    return {"ok": True, "psu": bool(psu)}


def test_cpd(instr, logger=None):
    """Dirty golden: must be blocked."""
    input("Testing...")
    return {}
''',
        encoding="utf-8",
    )
    return FIXTURE_PY


def check_test_detect() -> list[str]:
    errors: list[str] = []
    fixture = _write_fixture()

    # Missing golden roots must not crash
    try:
        roots = td.load_golden_roots()
        _ = td.list_detected_tests(family="logic")
    except Exception as exc:
        errors.append(f"list_detected_tests crashed: {exc}")
        return errors

    # Direct file scan
    rows = td.scan_file(fixture, registered=set())
    by_id = {r["id"]: r for r in rows}
    if "detect_probe" not in by_id:
        errors.append("expected detect_probe in scan_file results")
    else:
        if by_id["detect_probe"].get("blocked"):
            errors.append(
                f"detect_probe should be clean, got blocked_reason="
                f"{by_id['detect_probe'].get('blocked_reason')!r}"
            )
    if "cpd" not in by_id:
        errors.append("expected cpd (dirty) in scan_file results")
    else:
        if not by_id["cpd"].get("blocked"):
            errors.append("cpd with input() must be blocked")
        if "input" not in str(by_id["cpd"].get("blocked_reason") or "").lower():
            errors.append(f"cpd blocked_reason should mention input(): {by_id['cpd']}")

    # Refuse dirty wrap
    try:
        td.wrap_detected_test(
            file=str(fixture),
            fn="test_cpd",
            family="demo_ingest",
        )
        errors.append("wrap of dirty test_cpd must raise")
    except ValueError as exc:
        if "input" not in str(exc).lower():
            errors.append(f"dirty wrap error should mention input(): {exc}")
    except Exception as exc:
        errors.append(f"dirty wrap unexpected: {exc}")

    # Clean wrap into demo_ingest
    pkg = REPO_ROOT / "ate" / "tests" / "demo_ingest"
    mod = pkg / "imported_detect_probe.py"
    init = pkg / "__init__.py"
    init_bak = init.read_text(encoding="utf-8") if init.is_file() else ""
    try:
        out = td.wrap_detected_test(
            file=str(fixture),
            fn="test_detect_probe",
            family="demo_ingest",
        )
        if not out.get("ok") or out.get("id") != "detect_probe":
            errors.append(f"clean wrap failed: {out}")
        from ate.core.registry import all_tests, load_family

        load_family("demo_ingest")
        ids = {t.id for t in all_tests()}
        if "detect_probe" not in ids:
            errors.append("detect_probe missing from demo_ingest registry after wrap")
    except Exception as exc:
        errors.append(f"clean wrap failed: {exc}")
    finally:
        if mod.is_file():
            mod.unlink()
        # restore init
        if init_bak:
            init.write_text(init_bak, encoding="utf-8")
        else:
            # strip imported_detect_probe lines
            if init.is_file():
                lines = [
                    ln
                    for ln in init.read_text(encoding="utf-8").splitlines()
                    if "imported_detect_probe" not in ln
                ]
                init.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        try:
            from ate.core.registry import load_family

            load_family("demo_ingest")
        except Exception:
            pass

    # Cross-family copy refused
    try:
        td.enable_tests_on_part(
            dest_part="rs1g07",
            test_ids=["slew"],
            source_part="rs622",
        )
        errors.append("cross-family enable must refuse")
    except ValueError as exc:
        if "cross-family" not in str(exc).lower() and "family" not in str(exc).lower():
            errors.append(f"cross-family error unclear: {exc}")
    except Exception as exc:
        errors.append(f"cross-family unexpected: {exc}")

    # Missing root skip: temp non-existent path in config is fine via load_golden_roots
    missing = [r for r in roots if not r.get("exists")]
    _ = missing  # expected; not an error
    labels = {str(r.get("label") or "") for r in roots}
    for need in ("see_lin", "See-Lim-Repo", "Ariff-Repo", "Eugene-Repo"):
        if need not in labels:
            errors.append(f"golden_roots.yaml must list {need} (skipped if missing, read-only)")

    return errors


def main() -> int:
    errs = check_test_detect()
    if errs:
        print("FAIL check_test_detect:")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("OK check_test_detect: clean wrap / dirty block / missing root skip / cross-family refuse")
    return 0


if __name__ == "__main__":
    sys.exit(main())
