"""SAFETY LOCK: do not auto-rewrite the live lab report.

The previous apply path purged images and shrank the workbook to ~70KB,
which Excel could not open usefully. Layout changes must be done with an
explicit --i-understand-risks flag and must NEVER purge drawings.

Default: refuse to run.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def main() -> int:
    if "--i-understand-risks" not in sys.argv:
        print(
            "REFUSED: ate.reporting.apply_rules_ort is locked after workbook corruption.\n"
            "Restore source of truth: Downloads\\RS622XK_Lab_Report_TTSOP.backup.xlsx\n"
            "ORT geometry reference (do not overwrite): ...\\workbook\\RS622XK_Lab_Report_TTSOP_layout16.xlsx\n"
            "Pass --i-understand-risks only for a staged dry-run that does NOT purge images."
        )
        return 2
    print("Risk flag set, but image-purging apply is disabled until a safe ZIP-copy layout path exists.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
