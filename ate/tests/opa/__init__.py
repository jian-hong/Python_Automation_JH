"""Import all OPA test modules so registry fills.

Import order is cosmetic — all_tests() / group_by_fixture() reorder by
FIXTURE_RUN_ORDER (BUFFER → G11 → G_NEG100 → …; VOS research last).
"""
from ate.tests.opa import vos, ac_gain, ac_vin, slew, gbw, ort, settling, stubs  # noqa: F401

__all__ = ["vos", "ac_gain", "ac_vin", "slew", "gbw", "ort", "settling", "stubs"]
