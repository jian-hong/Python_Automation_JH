"""Test registry — pattern from LabAutomation_14.7 Lim REGISTERED_TESTS."""

from __future__ import annotations



from dataclasses import dataclass, field

from typing import Any, Callable, Optional



from ate.fixture.modes import fixture_mode_rank, within_mode_test_rank





@dataclass

class TestSpec:

    """One pluggable OPA/ATE test."""



    id: str

    label: str

    required_instruments: frozenset[str]

    fixture_mode: str

    lab_sheet: str  # sheet name in RS622XK_Lab_Report_TTSOP.xlsx

    run: Callable[..., Any]

    enabled: bool = True

    notes: str = ""

    scope_preset: dict[str, Any] = field(default_factory=dict)
    fixed_steps: list[dict[str, Any]] = field(default_factory=list)
    dual_channel: bool = True  # pause for CHA/CHB probe switch per DUT
    short_tag: str = ""  # optional UI short name; else derived from id





_REGISTRY: dict[str, TestSpec] = {}

_ACTIVE_FAMILY: str = ""

# Family key -> package that registers tests on import (A01 plugin table)
FAMILY_PACKAGES: dict[str, str] = {
    "opamp": "ate.tests.opa",
    "logic": "ate.tests.logic",
    "level": "ate.tests.level",
}

DEFAULT_FAMILY = "opamp"


def clear() -> None:
    """Drop all registered tests (call before loading another family)."""
    _REGISTRY.clear()


def active_family() -> str:
    return _ACTIVE_FAMILY


def load_family(family: str | None = None) -> str:
    """Clear registry and import the family's test package."""
    global _ACTIVE_FAMILY
    key = (family or DEFAULT_FAMILY).strip().lower()
    pkg = FAMILY_PACKAGES.get(key)
    if pkg is None:
        known = ", ".join(sorted(FAMILY_PACKAGES))
        raise ValueError(f"Unknown family {family!r}; known: {known}")
    clear()
    import importlib
    import sys

    mod = importlib.import_module(pkg)
    subs = getattr(mod, "__all__", None) or []
    if subs:
        for name in subs:
            subname = f"{pkg}.{name}"
            smod = sys.modules.get(subname) or importlib.import_module(subname)
            importlib.reload(smod)
    else:
        importlib.reload(mod)
    _ACTIVE_FAMILY = key
    return key



def register(spec: TestSpec) -> TestSpec:

    _REGISTRY[spec.id] = spec

    return spec





def get(test_id: str) -> Optional[TestSpec]:

    return _REGISTRY.get(test_id)





def all_tests() -> list[TestSpec]:

    """Return tests in fixture-canonical order (same board grouped)."""

    specs = list(_REGISTRY.values())

    specs.sort(

        key=lambda s: (

            fixture_mode_rank(s.fixture_mode),

            within_mode_test_rank(s.fixture_mode, s.id),

            s.id,

        )

    )

    return specs





def filter_runnable(available: set[str]) -> list[TestSpec]:

    """Skip tests whose required instruments are missing (Lim filter_runnable)."""

    runnable: list[TestSpec] = []

    for spec in all_tests():

        if not spec.enabled:

            continue

        missing = sorted(spec.required_instruments - available)

        if missing:

            print(f"  SKIPPING {spec.label}: missing {', '.join(missing)}")

            continue

        runnable.append(spec)

    return runnable





def group_by_fixture(test_ids: list[str]) -> list[tuple[str, list[TestSpec]]]:

    """Batch selected tests by fixture mode so same board runs together.



    Reorders into FIXTURE_RUN_ORDER (BUFFER → G11 → G_NEG100 → …; VOS research last)

    and within each mode uses the part catalog test list. Operator prompt

    fires once per batch (i.e. only when the physical config must change).

    """

    specs = [get(tid) for tid in test_ids]

    specs = [s for s in specs if s is not None]

    if not specs:

        return []



    specs.sort(

        key=lambda s: (

            fixture_mode_rank(s.fixture_mode),

            within_mode_test_rank(s.fixture_mode, s.id),

            s.id,

        )

    )



    batches: list[tuple[str, list[TestSpec]]] = []

    current_mode = specs[0].fixture_mode

    current: list[TestSpec] = [specs[0]]

    for spec in specs[1:]:

        if spec.fixture_mode == current_mode:

            current.append(spec)

        else:

            batches.append((current_mode, current))

            current_mode = spec.fixture_mode

            current = [spec]

    batches.append((current_mode, current))

    return batches


