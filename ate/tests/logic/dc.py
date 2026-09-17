"""Path B Logic DC runner (Product Model import name `dc`).

Canonical bodies live in logic_dc.py. Importing this module is the same
2-input / 3-input / N-input runner -- do not add per-chip forks here.
"""

import ate.tests.logic.logic_dc as _logic_dc


def __getattr__(name: str):
    return getattr(_logic_dc, name)
