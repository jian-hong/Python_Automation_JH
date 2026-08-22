"""VISA discovery — mirrors root instruments.find_instruments."""
from __future__ import annotations


def find_instruments() -> dict[str, str]:
    import pyvisa

    rm = pyvisa.ResourceManager()
    resources = rm.list_resources()
    instruments: dict[str, str] = {}

    for res in resources:
        # Skip COM/ASRL — they hang on *IDN? and are never our bench gear
        if str(res).upper().startswith("ASRL"):
            continue
        try:
            inst = rm.open_resource(res)
            inst.timeout = 3000
            idn = inst.query("*IDN?").strip().upper()
            print(f"Found: {res} -> {idn}")
            if "MSO5" in idn:
                instruments["MSO"] = res
            elif "DP832" in idn or ",DP8" in idn:
                instruments["PSU"] = res
            elif "DG8" in idn or "DG811" in idn:
                instruments["AWG"] = res
            inst.close()
        except Exception as exc:
            print(f"Skipping {res}: {exc}")
    return instruments
