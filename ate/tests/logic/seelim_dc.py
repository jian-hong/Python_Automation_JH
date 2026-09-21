"""See Lim golden locator. Not the Path B START runtime.

Lookup (missing skipped; never executed at family load):

  1. goldens/see_lin/<PART>/current_tests.py
  2. C:/Users/OoiJianHong/Downloads/See Lim Repo  (several layouts)

Colleague trees (Ariff / See Lim / Eugene Downloads) are READ-ONLY patterns
for Setup Detect AST scan. Do not copy numbers into ate/config/limits --
those files already cite the local Reference PDF extract.

Do not import Lim.*. Do not call input(). Path B DC is ate/tests/logic/logic_dc.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ate.core.paths import REPO_ROOT

SEE_LIN_DIR = REPO_ROOT / "goldens" / "see_lin"
SEE_LIM_FALLBACK = Path(r"C:/Users/OoiJianHong/Downloads/See Lim Repo")

# Read-only detect roots (listed in golden_roots.yaml). Not ingested.
COLLEAGUE_TREES = (
    Path(r"C:/Users/OoiJianHong/Downloads/Ariff Repo"),
    Path(r"C:/Users/OoiJianHong/Downloads/See Lim Repo"),
    Path(r"C:/Users/OoiJianHong/Downloads/Eugene Repo"),
)

_CURRENT = "current_tests.py"


def _part_names(part: str) -> tuple[str, ...]:
    key = str(part or "").strip()
    if not key:
        return ()
    compact = key.replace(" ", "").replace("-", "")
    return tuple(dict.fromkeys((key, key.upper(), key.lower(), compact, compact.upper(), compact.lower())))


def _candidates(part: str) -> list[Path]:
    names = _part_names(part)
    out: list[Path] = []
    for root in (SEE_LIN_DIR, SEE_LIM_FALLBACK):
        for name in names:
            out.append(root / name / _CURRENT)
            out.append(root / name / "current_tests.py")
            out.append(root / f"{name}_current_tests.py")
            out.append(root / name / "logic_tests.py")
    return out


def resolve_current_tests(part: str) -> Optional[Path]:
    """Path to See Lim current_tests.py if that file exists locally; else None."""
    for path in _candidates(part):
        try:
            if path.is_file():
                return path
        except OSError:
            continue
    return None


def golden_roots_present() -> dict[str, bool]:
    return {
        "see_lin": SEE_LIN_DIR.is_dir(),
        "see_lim_fallback": SEE_LIM_FALLBACK.is_dir(),
        "ariff_repo": COLLEAGUE_TREES[0].is_dir(),
        "eugene_repo": COLLEAGUE_TREES[2].is_dir(),
    }
