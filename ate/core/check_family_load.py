"""Self-check: family load API clears registry on switch (A01-T01).

Run: python -m ate.core.check_family_load
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from ate.core.registry import all_tests, load_family

_OPA_PROBE_IDS = frozenset({"gbw", "slew"})
_LOGIC_PROBE_IDS = frozenset({"tp", "supply_current", "cap_load"})
_OPA_BOARD_MODES = frozenset({"G11", "G_NEG100", "G201", "G1001"})


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


def main() -> int:
    _runner_uses_family_loader()

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

    load_family("opamp")
    restored = {t.id for t in all_tests()}
    if not restored:
        raise AssertionError("load_family(opamp) after logic: all_tests() empty")
    missing_restore = _OPA_PROBE_IDS - restored
    if missing_restore:
        raise AssertionError(
            f"load_family(opamp) after logic: missing OPA ids {sorted(missing_restore)}"
        )
    logic_leak = logic_ids & restored
    if logic_leak:
        raise AssertionError(
            f"load_family(opamp) after logic: Logic ids leaked: {sorted(logic_leak)}"
        )

    print(
        f"OK opamp={len(opa_ids)} logic={len(logic_ids)} restored={len(restored)} tests "
        f"(no cross-family leak)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
