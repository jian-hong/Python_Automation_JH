"""Fixture / gain modes — discrete RF/RI boards, not free numerical gain.



Closed-loop gain is set by pre-soldered (or jumpered) resistor ratios on the

DUT fixture. Without an STM relay bank we cannot dial an arbitrary number;

we only switch among discrete topologies:



  General lab testboard (normal production / datasheet flow):

    Buffer:         RF=short, RI=open  →  gain = 1

    Non-inverting:  A_CL = 1 + RF/RI   →  G11 (=11)

    Inverting:      A_CL = −RF/RI      →  G_NEG100 (−100)



  Research / special boards (NOT the general testboard):

    High-gain VOS/AC ≈ 201, datasheet VOS = 1001



Operator prompts fire only when the fixture mode changes between batches.

"""

from __future__ import annotations



from enum import Enum

from pathlib import Path

from typing import Any



import yaml



from ate.core.paths import PARTS_DIR





class FixtureMode(str, Enum):

    BUFFER = "BUFFER"  # Voltage follower — general testboard

    G11 = "G11"  # Non-inv GBW — general testboard

    G_NEG100 = "G_NEG100"  # Inverting ORT — general testboard

    G201 = "G201"  # High-gain VOS / AC — research only

    G1001 = "G1001"  # Datasheet VOS — research only

    ATE = "ATE"  # Future ATE-only configs





# Canonical batch order for the GENERAL lab board first; VOS research last.

FIXTURE_RUN_ORDER: tuple[str, ...] = (

    "BUFFER",  # follower — slew / step / settling

    "G11",  # non-inv ×11 — GBW

    "G_NEG100",  # inverting −100 — ORT

    "ATE",  # future STM / relay bank

    "G201",  # research: high-gain VOS / AC

    "G1001",  # research: datasheet VOS

)



_DEFAULT_CATALOG: dict[str, dict[str, Any]] = {

    "BUFFER": {

        "label": "Voltage Follower (Buffer)",

        "board_class": "general",

        "topology": "buffer",

        "rf": "short",

        "ri": "open",

        "gain": 1,

        "gain_editable": False,

        "checklist": [

            "General testboard in BUFFER / voltage-follower mode",

            "RF = short, RI = open (gain = 1 — not software-selectable)",

            "RL = 10 kΩ, CL as required by test",

            "Probes: CH1 = IN+, CH2 = VOUT",

        ],

        "tests": ["slew", "settling", "sssr", "lssr", "no_phase_reversal", "power_on"],

    },

    "G11": {

        "label": "Non-inverting Gain = 11",

        "board_class": "general",

        "topology": "non_inverting",

        "rf": "10k",

        "ri": "1k",

        "gain": 11,

        "gain_editable": False,

        "checklist": [

            "General testboard Gain = 11 (RF=10k, RI=1k → 1+RF/RI)",

            "IN+ referenced per GBW procedure",

            "Probes: CH1 = OutB, CH2 = junction/input as specified",

        ],

        "tests": ["gbw"],

    },

    "G_NEG100": {

        "label": "Inverting Gain = −100 (ORT)",

        "board_class": "general",

        "topology": "inverting",

        "rf": "100k",

        "ri": "1k",

        "gain": -100,

        "gain_editable": False,

        "checklist": [

            "General testboard inverting Gain = −100 (RF=100k, RI=1k)",

            "RL = 10 kΩ, CL = 100 pF",

            "Ready for positive then negative overload squares",

        ],

        "tests": ["ort"],

    },

    "ATE": {

        "label": "ATE-only configs (future)",

        "board_class": "general",

        "topology": "ate",

        "rf": "n/a",

        "ri": "n/a",

        "gain": None,

        "gain_editable": False,

        "checklist": ["ATE fixture / STM relay bank not yet automated"],

        "tests": ["psrr", "cmrr", "aol", "vohl", "emirr"],

    },

    "G201": {

        "label": "Research only — High-gain VOS / AC (≈201)",

        "board_class": "research",

        "topology": "non_inverting",

        "rf": "as_board",

        "ri": "as_board",

        "gain": 201,

        "gain_editable": False,

        "checklist": [

            "NOT the general lab testboard — special high-gain VOS/AC fixture",

            "Closed-loop gain ≈ 201 from board RF/RI (discrete; not dialable)",

            "Virtual-ground junction probe ready for AC tests",

        ],

        "tests": ["vos_sweep", "ac_gain_check", "ac_vin_sweep"],

    },

    "G1001": {

        "label": "Research only — Datasheet VOS Gain = 1001",

        "board_class": "research",

        "topology": "non_inverting",

        "rf": "100k",

        "ri": "100",

        "gain": 1001,

        "gain_editable": False,

        "checklist": [

            "NOT the general lab testboard — VOS characterization board",

            "PCB Gain = 1001 (RF=100k, RI=100Ω → 1+RF/RI)",

            "100Ω pulldown on IN+ as per VOS plan",

        ],

        "tests": ["vos_lab"],

    },

}





def load_fixture_catalog(part: str = "rs622") -> dict[str, dict[str, Any]]:

    path = PARTS_DIR / f"{part}.yaml"

    if path.is_file():

        with path.open(encoding="utf-8") as fh:

            data = yaml.safe_load(fh) or {}

        modes = data.get("fixture_modes") or data.get("modes")

        if isinstance(modes, dict) and modes:

            # Merge YAML over defaults so missing keys (gain_editable, topology) remain.

            merged = dict(_DEFAULT_CATALOG)

            for key, entry in modes.items():

                base = dict(merged.get(key) or {})

                if isinstance(entry, dict):

                    base.update(entry)

                merged[key] = base

            return merged

    return dict(_DEFAULT_CATALOG)





def mode_checklist(mode: str, part: str = "rs622") -> list[str]:

    catalog = load_fixture_catalog(part)

    entry = catalog.get(mode) or catalog.get(mode.upper()) or {}

    checklist = entry.get("checklist") or []

    return list(checklist)





def mode_gain(mode: str, part: str = "rs622", default: float = 1.0) -> float:

    """Closed-loop gain for a discrete fixture mode (from RF/RI catalog).



    Default is 1 (buffer / general board), never the research VOS ≈201.

    """

    catalog = load_fixture_catalog(part)

    entry = catalog.get(mode) or catalog.get(str(mode).upper()) or {}

    g = entry.get("gain")

    if g is None:

        return float(default)

    return float(g)





def fixture_mode_rank(mode: str) -> int:

    """Sort key for batching — unknown modes go last."""

    try:

        return FIXTURE_RUN_ORDER.index(mode)

    except ValueError:

        return len(FIXTURE_RUN_ORDER)





def within_mode_test_rank(mode: str, test_id: str, part: str = "rs622") -> int:

    """Prefer catalog `tests:` order inside a mode."""

    catalog = load_fixture_catalog(part)

    entry = catalog.get(mode) or {}

    order = list(entry.get("tests") or [])

    try:

        return order.index(test_id)

    except ValueError:

        return len(order)





def catalog_for_ui(part: str = "rs622") -> list[dict[str, Any]]:

    """Serialize fixture modes for the operator UI (read-only gain display)."""

    catalog = load_fixture_catalog(part)

    rows: list[dict[str, Any]] = []

    for mode in FIXTURE_RUN_ORDER:

        entry = catalog.get(mode)

        if not entry:

            continue

        rows.append(

            {

                "mode": mode,

                "label": entry.get("label") or mode,

                "gain": entry.get("gain"),

                "board_class": entry.get("board_class") or "general",

                "topology": entry.get("topology"),

                "rf": entry.get("rf"),

                "ri": entry.get("ri"),

                "gain_editable": bool(entry.get("gain_editable", False)),

                "tests": list(entry.get("tests") or []),

            }

        )

    return rows


