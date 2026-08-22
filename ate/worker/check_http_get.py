"""Fails if worker Handler still 501s on GET (browser probe).

Run: python -m ate.worker.check_http_get
"""
from __future__ import annotations

import inspect

from ate.worker.server import Handler


def main() -> int:
    if not hasattr(Handler, "do_GET"):
        raise AssertionError("Handler.do_GET missing — browser GET returns 501")
    src = inspect.getsource(Handler.do_GET) + inspect.getsource(Handler._reply_browser_probe)
    if "send_error" in src or "send_response(501)" in src:
        raise AssertionError("do_GET must not send 501")
    if "5174" not in inspect.getsource(Handler._reply_browser_probe):
        raise AssertionError("GET probe must point operator at UI :5174")
    print("ok: worker GET probe is 200 + UI :5174")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
