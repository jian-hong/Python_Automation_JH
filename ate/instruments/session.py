"""Instrument session — MSO required; PSU/AWG optional at open."""
from __future__ import annotations

from typing import Optional

import pyvisa

from ate.instruments.discovery import find_instruments


class Instruments:
    REQUIRED_AT_OPEN = ("MSO",)

    def __init__(self, mapping: Optional[dict[str, str]] = None) -> None:
        self.rm = pyvisa.ResourceManager()
        self.inst_map = dict(mapping) if mapping else find_instruments()
        print("Final Mapping:")
        print(self.inst_map)

        missing = [k for k in self.REQUIRED_AT_OPEN if k not in self.inst_map]
        if missing:
            raise RuntimeError(f"Required instrument(s) not found: {missing}")

        self.scope = self._open("MSO", required=True)
        self.psu = self._open("PSU", required=False)
        self.gen = self._open("AWG", required=False)

        for key, handle in (("PSU", self.psu), ("AWG", self.gen)):
            if handle is None:
                print(f"{key} not connected — session open without it.")

    def available_devices(self) -> set[str]:
        return set(self.inst_map.keys())

    def _open(self, key: str, required: bool = True):
        url = self.inst_map.get(key)
        if not url:
            if required:
                raise RuntimeError(f"{key} not found")
            return None
        inst = self.rm.open_resource(url)
        inst.timeout = 3000
        return inst

    def reopen_scope(self):
        """Drop a poisoned MSO VISA handle and open a fresh one."""
        url = self.inst_map.get("MSO")
        if not url:
            raise RuntimeError("MSO not in mapping")
        if self.scope is not None:
            try:
                self.scope.close()
            except Exception:
                pass
        self.scope = self.rm.open_resource(url)
        self.scope.timeout = 5000
        return self.scope

    def reset_all(self) -> None:
        for inst in (self.scope, self.gen, self.psu):
            if inst is None:
                continue
            try:
                inst.write("*RST")
            except Exception as exc:
                print(f"Reset failed: {exc}")

    def close_all(self) -> None:
        for inst in (self.scope, self.gen, self.psu):
            if inst is None:
                continue
            try:
                inst.close()
            except Exception:
                pass
