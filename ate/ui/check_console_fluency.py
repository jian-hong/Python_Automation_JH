"""Fails if the operator console regresses fluency / GBW label leak.

Run: python -m ate.ui.check_console_fluency
"""
from __future__ import annotations

from pathlib import Path

WEB = Path(__file__).resolve().parent / "web"


def main() -> int:
    js = (WEB / "app.js").read_text(encoding="utf-8")
    css = (WEB / "styles.css").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")

    if "gbwOn" not in js or 'ids.includes("gbw")' not in js:
        raise AssertionError("params() must stamp G11 run_label only when GBW is selected")
    if "function pollLoop" not in js:
        raise AssertionError("idle poll must slow down (pollLoop), not 350ms forever")
    if 'addEventListener("change", renderRunPlans)' in js.split("async function loadTests")[1].split("async function refreshSession")[0]:
        raise AssertionError("loadTests must not re-bind DUT/channel listeners")
    if "lastScrollId" not in js or 'behavior: "smooth"' in js:
        raise AssertionError("timeline must not smooth-scroll on every poll")
    if "prefers-reduced-motion" not in css:
        raise AssertionError("CSS must respect prefers-reduced-motion")
    if ".modal.hidden" not in css:
        raise AssertionError("Continue modal must stay hidden until a prompt")
    if "app.js?v=20260820e" not in html or "styles.css?v=20260820e" not in html:
        raise AssertionError("index.html cache tokens must match app.js + styles.css")
    if "SettlingTime" not in js:
        raise AssertionError("Open Screenshots must know SettlingTime folder")

    print("ok: console fluency; GBW label gated; modal hidden; cache 20260820e")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
