"""JSON-RPC worker for Tauri UI — hidden pythonw process."""
from __future__ import annotations

import json
import socketserver
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

# Ensure repo root on path
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ate.core.paths import JSONRPC_HOST, JSONRPC_PORT
from ate.core.registry import FAMILY_PACKAGES, active_family, all_tests
from ate.core.runner import ATECore, RunParams

WORKER_VERSION = "0.2.3"


class _State:
    core: ATECore | None = None
    event_subscribers: list = []
    lock = threading.Lock()
    run_thread: threading.Thread | None = None


def _build_run_params(params: dict[str, Any]) -> RunParams:
    from ate.core.database import get_context
    from ate.core.param_defaults import resolve_gain_profile, noninv_gain
    from dataclasses import replace as dc_replace

    ctx = get_context()
    p = params or {}
    duts_raw = p.get("dut_indices")
    dut_indices: list[int] = []
    if isinstance(duts_raw, list) and duts_raw:
        dut_indices = [int(x) for x in duts_raw]
    part = str(p.get("part") or ctx.part_key or "rs622")
    gain_profile = str(p.get("gain_profile") or "default")
    run_label = str(p.get("run_label") or "").strip()
    rp = RunParams(
        vcc=float(p.get("vcc", 5.0)),
        freq_hz=float(p.get("freq_hz", 500.0)),
        amp_vpp=float(p.get("amp_vpp", 0.004)),
        n_repeats=int(p.get("n_repeats", 3)),
        lab_report=str(p.get("lab_report") or ctx.lab_report_path()),
        research_excel=str(p.get("research_excel") or ""),
        reset_before_run=bool(p.get("reset_before_run", False)),
        unit_index=int(p.get("unit_index", 1)),
        dut_indices=dut_indices,
        part=part,
        channel=str(p.get("channel") or "CHA").upper(),
        channels=[
            str(c).upper()
            for c in (p.get("channels") or [])
            if str(c).strip()
        ],
        run_label=run_label,
        gain_profile=gain_profile,
        current_limit_a=float(p.get("current_limit_a", 0.10)),
    )
    ids_hint = list(p.get("test_ids") or [])
    if "gbw" in ids_hint:
        prof = resolve_gain_profile("G11", gain_profile, part)
        if prof.get("gain") is not None:
            rp = dc_replace(
                rp,
                gain=float(prof["gain"]),
                rf=str(prof.get("rf") or ""),
                ri=str(prof.get("ri") or ""),
            )
        if not rp.run_label and prof.get("label"):
            rp = dc_replace(rp, run_label=str(prof["label"]))
    if p.get("rf") and p.get("ri"):
        rp = dc_replace(
            rp,
            rf=str(p.get("rf")),
            ri=str(p.get("ri")),
            gain=float(noninv_gain(str(p.get("rf")), str(p.get("ri")))),
        )
    if not rp.research_excel:
        from ate.core.paths import RESEARCH_EXCEL_PATH

        rp.research_excel = str(RESEARCH_EXCEL_PATH)
    return rp


def _run_sequence_worker(ids: list[str], rp: RunParams) -> None:
    core = _core()
    try:
        core.run_sequence(ids, rp)
    except Exception as exc:
        _emit(
            {
                "type": "log",
                "payload": {"text": f"Run failed: {exc}\n", "level": "error"},
            }
        )


def _emit(event: dict) -> None:
    # Events are polled via get_events; keep a ring buffer
    with _State.lock:
        _State.event_subscribers.append(event)
        if len(_State.event_subscribers) > 500:
            _State.event_subscribers = _State.event_subscribers[-300:]


def _core() -> ATECore:
    if _State.core is None:
        _State.core = ATECore(emit=_emit)
    return _State.core


def dispatch(method: str, params: dict[str, Any]) -> Any:
    core = _core()

    if method == "ping":
        return {"ok": True, "version": WORKER_VERSION}

    if method == "get_family":
        return {
            "family": core.family or active_family() or "opamp",
            "known": sorted(FAMILY_PACKAGES.keys()),
            "default": "opamp",
        }

    if method == "set_family":
        if core.busy:
            raise RuntimeError("Runner busy — wait for run to finish")
        fam = str(params.get("family") or "").strip().lower() or None
        loaded = core.load_family(fam)
        return {"family": loaded, "test_count": len(all_tests())}

    if method == "list_tests":
        from ate.core.timeline import short_test_tag

        return [
            {
                "id": t.id,
                "label": t.label,
                "short_tag": short_test_tag(t),
                "fixture_mode": t.fixture_mode,
                "lab_sheet": t.lab_sheet,
                "required_instruments": sorted(t.required_instruments),
                "notes": t.notes,
                "fixed_steps": list(t.fixed_steps) if t.fixed_steps else [],
                "dual_channel": bool(getattr(t, "dual_channel", True)),
            }
            for t in all_tests()
        ]

    if method == "list_fixture_modes":
        if core.family != "opamp":
            return []
        from ate.fixture.modes import catalog_for_ui

        return catalog_for_ui(str(params.get("part") or "rs622"))

    if method == "list_db_tree":
        from ate.core.database import list_tree

        return list_tree()

    if method == "get_db_context":
        from ate.core.database import get_context, how_to_use, list_test_folders

        ctx = get_context()
        return {
            "context": ctx.identity(),
            "tests": list_test_folders(ctx),
            "guide": how_to_use(),
        }

    if method == "set_db_context":
        from ate.core.database import list_test_folders, set_context
        from ate.core.paths import sync_defaults_from_context

        ctx = set_context(
            component=params.get("component"),
            part=params.get("part"),
            package=params.get("package"),
            version=params.get("version"),
            model=params.get("model"),
            part_key=params.get("part_key"),
            year=params.get("year"),
            sample_size=params.get("sample_size"),
        )
        sync_defaults_from_context()
        return {
            "context": ctx.identity(),
            "tests": list_test_folders(ctx),
            "created": ctx.ensure_tree(),
        }

    if method == "db_how_to":
        from ate.core.database import how_to_use

        return how_to_use()

    if method == "open_db_root":
        from ate.core.database import get_context
        import os

        folder = get_context().root()
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))
        return {"folder": str(folder)}

    if method == "open_sessions":
        from ate.core.database import get_context
        import os

        folder = get_context().sessions_dir()
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))
        return {"folder": str(folder)}

    if method == "import_workbook":
        from ate.core.workbook_import import import_workbook

        return import_workbook(
            source_path=str(params.get("source_path") or params.get("path") or ""),
            dest_name=str(params.get("dest_name") or ""),
            pick=bool(params.get("pick")),
        )

    if method == "discover":
        return core.discover()

    if method == "open_session":
        return core.open_session()

    if method == "close_session":
        core.close_session()
        return {"ok": True}

    if method == "session_status":
        from ate.core.database import current_session, get_context

        return {
            "open": core.session_open,
            "mapping": core.mapping,
            "busy": core.busy,
            "db": get_context().identity(),
            "run_session": current_session(),
            "timeline": core.timeline_snapshot(),
        }

    if method == "get_timeline":
        return core.timeline_snapshot()

    if method == "screenshot":
        path = core.capture_screenshot(
            prefix=params.get("prefix", "manual"),
            test_key=str(params.get("test_key") or "ORT"),
        )
        return {"path": path}

    if method == "open_screenshots":
        from ate.core.database import get_context
        from ate.reporting.lab_report import ensure_screenshot_dir
        import os

        ctx = get_context()
        unit = params.get("unit_index")
        test_key = str(params.get("test_key") or "ORT")
        dut = int(unit) if unit is not None else None
        folder = ensure_screenshot_dir(test_key, dut)
        os.startfile(str(folder))
        return {"folder": str(folder), "db": ctx.identity()}

    if method == "list_param_defaults":
        from ate.core.param_defaults import catalog_for_ui

        part = str(params.get("part") or "rs622")
        return catalog_for_ui(part)

    if method == "run_sequence":
        ids = list(params.get("test_ids") or [])
        p = params.get("params") or {}
        rp = _build_run_params({**p, "test_ids": ids})
        results = core.run_sequence(ids, rp)
        return [
            {
                "test_id": r.test_id,
                "success": r.success,
                "summary": r.summary,
                "error": r.error,
                "dut": r.dut,
                "channel": r.channel,
                "fixture_mode": r.fixture_mode,
            }
            for r in results
        ]

    if method == "run_sequence_async":
        ids = list(params.get("test_ids") or [])
        p = params.get("params") or {}
        if core.busy:
            raise RuntimeError("Runner busy")
        rp = _build_run_params({**p, "test_ids": ids})
        with _State.lock:
            if _State.run_thread and _State.run_thread.is_alive():
                raise RuntimeError("Run thread already active")
            _State.run_thread = threading.Thread(
                target=_run_sequence_worker,
                args=(ids, rp),
                daemon=True,
            )
            _State.run_thread.start()
        return {"ok": True, "started": True}

    if method == "get_last_run_results":
        return core.last_run_results()
    if method == "operator_respond":
        core.operator_respond(params)
        return {"ok": True}

    if method == "operator_force_continue":
        pending = core.pending_operator()
        if not pending:
            return {"ok": False, "reason": "no_pending"}
        core.operator_respond({"prompt_id": pending["id"], "continue": True})
        return {"ok": True, "prompt_id": pending["id"]}

    if method == "get_pending_prompt":
        return core.pending_operator()

    if method == "get_events":
        with _State.lock:
            ev = list(_State.event_subscribers)
            _State.event_subscribers.clear()
        # Re-attach pending prompt so UI recovers after refresh / drained events
        pending = core.pending_operator()
        if pending and not any(e.get("type") == "operator_prompt" for e in ev):
            ev.append({"type": "operator_prompt", "payload": pending})
        return ev

    if method == "stop":
        core.request_cancel()
        core.emergency_cleanup()
        return {"ok": True, "stopped": True}

    if method == "emergency_cleanup":
        core.request_cancel()
        core.emergency_cleanup()
        return {"ok": True}

    raise ValueError(f"Unknown method: {method}")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("RPC %s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_HEAD(self) -> None:
        self._reply_browser_probe(body=False)

    def do_GET(self) -> None:
        """Health/probe for browsers. RPC remains POST JSON-RPC."""
        self._reply_browser_probe(body=True)

    def _reply_browser_probe(self, *, body: bool) -> None:
        accept = (self.headers.get("Accept") or "").lower()
        if "text/html" in accept:
            payload = (
                "<!doctype html><meta charset=utf-8>"
                "<title>ATE worker</title>"
                "<p>JSON-RPC worker on :8766 (POST).</p>"
                "<p>Open the console: "
                "<a href='http://127.0.0.1:5174'>http://127.0.0.1:5174</a></p>"
            ).encode()
            ctype = "text/html; charset=utf-8"
        else:
            payload = json.dumps(
                {
                    "ok": True,
                    "service": "ate-worker",
                    "rpc": "POST",
                    "ui": "http://127.0.0.1:5174",
                    "version": WORKER_VERSION,
                }
            ).encode()
            ctype = "application/json"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self._cors()
        self.end_headers()
        if body:
            self.wfile.write(payload)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            req = json.loads(raw.decode("utf-8"))
            method = req.get("method")
            params = req.get("params") or {}
            req_id = req.get("id")
            result = dispatch(method, params)
            body = {"jsonrpc": "2.0", "id": req_id, "result": result}
            code = 200
        except Exception as exc:
            body = {
                "jsonrpc": "2.0",
                "id": req.get("id") if "req" in dir() else None,
                "error": {"message": str(exc), "traceback": traceback.format_exc()},
            }
            code = 200
        data = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


def main() -> None:
    host = JSONRPC_HOST
    port = JSONRPC_PORT
    # Warm registry
    _core()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"ATE JSON-RPC worker listening on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Worker stopping…", flush=True)
        try:
            _core().emergency_cleanup()
            _core().close_session()
        except Exception:
            pass


if __name__ == "__main__":
    main()
