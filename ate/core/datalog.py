"""STS8200-shaped rolling session report (ate.datalog.v1).

Per operator Version (not shared across people):
  sessions/report.json          -- living LATEST merge (keep unrun tests)
  sessions/session_{id}.json    -- full START snapshot (database._write_session)
  sessions/archive/{id}.json    -- end_session copy of living report
  {test_key}/DUT_n/records/     -- timestamped per-step history (never overwrite)

Do not wipe report.json on START. Merge by test_id+dut(+channel).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

MYT = timezone(timedelta(hours=8))
SCHEMA = "ate.datalog.v1"


def report_path(ctx) -> Path:
    return ctx.sessions_dir() / "report.json"


def archive_dir(ctx) -> Path:
    return ctx.sessions_dir() / "archive"


def _step_key(step: dict[str, Any]) -> tuple:
    """Merge identity: same test on same DUT(+channel) replaces latest only."""
    tid = str(step.get("test_id") or "").strip()
    dut = step.get("dut")
    if dut is None:
        dut = step.get("site")
    try:
        dut_n = int(dut) if dut is not None else 0
    except (TypeError, ValueError):
        dut_n = 0
    ch = str(step.get("channel") or "").strip().upper()
    return (tid, dut_n, ch)


def _folder_for_test(test_id: str, ctx) -> str:
    """Prefer sheet_map folder / excel_sheet; else sanitised test_id."""
    key = str(test_id or "").strip()
    if not key:
        return "unknown"
    try:
        sm = ctx.load_sheet_map() if hasattr(ctx, "load_sheet_map") else {}
        tests = (sm or {}).get("tests") if isinstance(sm, dict) else {}
        if isinstance(tests, dict):
            entry = tests.get(key)
            if isinstance(entry, dict):
                folder = str(entry.get("folder") or entry.get("excel_sheet") or "").strip()
                if folder:
                    return folder
            for _k, entry in tests.items():
                if not isinstance(entry, dict):
                    continue
                if str(entry.get("excel_sheet") or "") == key or str(entry.get("folder") or "") == key:
                    folder = str(entry.get("folder") or entry.get("excel_sheet") or key).strip()
                    if folder:
                        return folder
    except Exception:
        pass
    return re.sub(r"[^\w\-]+", "", key) or "unknown"


def write_step_record(step: dict[str, Any], *, session: dict[str, Any] | None = None, ctx=None) -> Optional[Path]:
    """Append-only history: {test_key}/DUT_n/records/{test_id}_{timestamp}.json."""
    from ate.core.database import get_context

    if not isinstance(step, dict) or not step.get("test_id"):
        return None
    c = ctx or get_context()
    tid = str(step.get("test_id"))
    folder = _folder_for_test(tid, c)
    dut = step.get("dut")
    if dut is None:
        params = (session or {}).get("params") or {}
        dut = params.get("unit_index") or 1
    try:
        dut_n = int(dut)
    except (TypeError, ValueError):
        dut_n = 1
    ts = str(step.get("at") or datetime.now(MYT).isoformat(timespec="seconds"))
    safe_ts = re.sub(r"[^\d\-T]", "", ts.replace(":", "")).replace("T", "_")[:20] or "ts"
    dest_dir = c.dut_folder(folder, dut_n) / "records"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{tid}_{safe_ts}.json"
    if dest.is_file():
        dest = dest_dir / f"{tid}_{safe_ts}_{datetime.now(MYT).strftime('%H%M%S%f')}.json"
    payload = {
        "schema": SCHEMA,
        "test_id": tid,
        "dut": dut_n,
        "at": ts,
        "source_session": str((session or {}).get("session_id") or ""),
        "step": dict(step),
        "identity": dict((session or {}).get("context") or (getattr(c, "identity", lambda: {})() or {})),
    }
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest


def _empty_report(ctx, session: dict[str, Any] | None = None) -> dict[str, Any]:
    from ate.core.tags import load_tags

    ident = dict((session or {}).get("context") or ctx.identity())
    try:
        t = load_tags(ctx)
        ident["tags"] = list(t.get("tags") or [])
        ident["boards"] = list(t.get("boards") or [])
        ident["labels"] = list(t.get("labels") or [])
    except Exception:
        ident.setdefault("tags", [])
        ident.setdefault("boards", [])
        ident.setdefault("labels", [])
    started = str((session or {}).get("started_at") or datetime.now(MYT).isoformat(timespec="seconds"))
    return {
        "schema": SCHEMA,
        "header": {
            "time": datetime.now(MYT).strftime("%Y-%m-%d %H:%M:%S"),
            "program": "ate.worker",
            "user": str(ident.get("operator") or ""),
            "lot_id": "",
            "total": 0,
            "pass": 0,
            "fail": 0,
            "beginning_time": started,
            "ending_time": "",
            "total_testing_time_s": 0,
            "idle_time_s": 0,
            "session_id": str((session or {}).get("session_id") or ""),
            "status": str((session or {}).get("status") or "running"),
        },
        "identity": ident,
        "params": dict((session or {}).get("params") or {}),
        "instrument_map": dict((session or {}).get("instrument_map") or {}),
        "sites": [],
        "steps": [],
        "artifacts": [],
    }


def _ensure_sites(doc: dict[str, Any], dut_indices: list[int] | None) -> None:
    sites = doc.setdefault("sites", [])
    if not isinstance(sites, list):
        doc["sites"] = []
        sites = doc["sites"]
    have = {int(s.get("site")) for s in sites if isinstance(s, dict) and s.get("site") is not None}
    for dut in dut_indices or []:
        d = int(dut)
        if d not in have:
            sites.append({"site": d, "part_id": d, "sbin": 0, "measurements": []})
            have.add(d)


def _recompute_header(doc: dict[str, Any], session: dict[str, Any] | None = None) -> None:
    steps = [s for s in (doc.get("steps") or []) if isinstance(s, dict)]
    total = len(steps)
    passed = sum(1 for s in steps if s.get("success") is True)
    failed = sum(1 for s in steps if s.get("success") is False)
    hdr = doc.setdefault("header", {})
    hdr["total"] = total
    hdr["pass"] = passed
    hdr["fail"] = failed
    # header.time = last merge wall clock (not wiped when some tests stay old)
    hdr["time"] = datetime.now(MYT).strftime("%Y-%m-%d %H:%M:%S")
    if session:
        hdr["session_id"] = str(session.get("session_id") or hdr.get("session_id") or "")
        hdr["status"] = str(session.get("status") or hdr.get("status") or "")
        if session.get("started_at"):
            hdr["beginning_time"] = str(session["started_at"])
        if session.get("finished_at"):
            hdr["ending_time"] = str(session["finished_at"])
            try:
                t0 = datetime.fromisoformat(str(session["started_at"]))
                t1 = datetime.fromisoformat(str(session["finished_at"]))
                hdr["total_testing_time_s"] = max(0, int((t1 - t0).total_seconds()))
            except Exception:
                pass


def _fold_site_measurements(doc: dict[str, Any], params: dict[str, Any] | None = None) -> None:
    """Rebuild site.measurements from merged steps (latest per test wins already)."""
    params = params or {}
    for site in doc.get("sites") or []:
        if isinstance(site, dict):
            site["measurements"] = []
    for step in doc.get("steps") or []:
        if not isinstance(step, dict):
            continue
        meas = step.get("measurements")
        if not isinstance(meas, list) or not meas:
            continue
        site_n = int(step.get("dut") or step.get("site") or params.get("unit_index") or 1)
        for site in doc.get("sites") or []:
            if not isinstance(site, dict):
                continue
            if int(site.get("site") or 0) != site_n:
                continue
            for m in meas:
                if isinstance(m, dict):
                    site.setdefault("measurements", []).append(dict(m))
            break


def _coverage_for(doc: dict[str, Any], ctx) -> list[dict[str, Any]]:
    """enabled tests -> latest|missing using living steps (any DUT counts as latest)."""
    have = {
        str(s.get("test_id") or "").strip()
        for s in (doc.get("steps") or [])
        if isinstance(s, dict) and s.get("test_id")
    }
    enabled: list[str] = []
    try:
        from ate.fixture.modes import enabled_tests_for_part

        pk = str(getattr(ctx, "part_key", "") or getattr(ctx, "part", "") or "")
        ids = enabled_tests_for_part(pk) if pk else None
        if ids:
            enabled = [str(x) for x in ids]
    except Exception:
        enabled = []
    if not enabled:
        enabled = sorted(have)
    out: list[dict[str, Any]] = []
    for tid in enabled:
        out.append({"test_id": tid, "status": "latest" if tid in have else "missing"})
    return out


def sync_report_from_session(session: dict[str, Any], *, ctx=None) -> Path:
    """Merge this START into living sessions/report.json (keep tests not run now).

    Per-operator Version only. session_{id}.json remains the full START snapshot.
    """
    from ate.core.database import get_context

    c = ctx or get_context()
    c.sessions_dir().mkdir(parents=True, exist_ok=True)
    path = report_path(c)

    # Load existing latest; never start empty when a prior report exists.
    if path.is_file():
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
            doc = prev if isinstance(prev, dict) else _empty_report(c, session)
        except Exception:
            doc = _empty_report(c, session)
        if doc.get("schema") != SCHEMA:
            doc = _empty_report(c, session)
    else:
        doc = _empty_report(c, session)

    # Refresh identity/tags/params from current context + session shell.
    fresh = _empty_report(c, session)
    doc["schema"] = SCHEMA
    doc["identity"] = fresh["identity"]
    doc["params"] = fresh["params"]
    if fresh.get("instrument_map"):
        doc["instrument_map"] = fresh["instrument_map"]

    by_key: dict[tuple, dict[str, Any]] = {}
    for step in doc.get("steps") or []:
        if isinstance(step, dict) and step.get("test_id"):
            by_key[_step_key(step)] = dict(step)

    sid = str(session.get("session_id") or "")
    incoming = [s for s in (session.get("steps") or []) if isinstance(s, dict) and s.get("test_id")]
    for step in incoming:
        row = dict(step)
        if not row.get("at"):
            row["at"] = datetime.now(MYT).isoformat(timespec="seconds")
        row["updated_at"] = row["at"]
        if sid:
            row["source_session"] = sid
        key = _step_key(row)
        old = by_key.get(key)
        # One history file per new/changed latest only (re-sync of same step skips).
        changed = (
            old is None
            or old.get("at") != row.get("at")
            or old.get("source_session") != row.get("source_session")
            or old.get("success") != row.get("success")
            or old.get("summary") != row.get("summary")
        )
        by_key[key] = row
        if changed:
            try:
                write_step_record(row, session=session, ctx=c)
            except Exception:
                pass

    doc["steps"] = list(by_key.values())
    # Artifacts: keep prior + append this START's (dedupe by path string)
    arts: list[dict[str, Any]] = []
    seen_art: set[str] = set()
    for a in list(doc.get("artifacts") or []) + list(session.get("artifacts") or []):
        if not isinstance(a, dict):
            continue
        key = str(a.get("path") or a)
        if key in seen_art:
            continue
        seen_art.add(key)
        arts.append(dict(a))
    doc["artifacts"] = arts

    params = session.get("params") or {}
    duts = params.get("dut_indices") if isinstance(params, dict) else None
    if not duts:
        duts = [int(params.get("unit_index") or 1)] if isinstance(params, dict) else [1]
    for step in doc["steps"]:
        if isinstance(step, dict) and step.get("dut") is not None:
            try:
                duts = list({*([int(x) for x in duts]), int(step["dut"])})
            except (TypeError, ValueError):
                pass
    _ensure_sites(doc, [int(x) for x in duts])
    _fold_site_measurements(doc, params if isinstance(params, dict) else {})
    doc["coverage"] = _coverage_for(doc, c)
    _recompute_header(doc, session)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    try:
        from ate.reporting.sts_datalog import export_latest_report

        version_dir = None
        try:
            version_dir = Path(c.root()) if hasattr(c, "root") else None
        except Exception:
            version_dir = None
        export_latest_report(doc, sessions_dir=c.sessions_dir(), version_dir=version_dir)
    except Exception:
        pass
    return path


def archive_report(session: dict[str, Any], *, ctx=None) -> Optional[Path]:
    """Copy current report.json to sessions/archive/{session_id}.json."""
    from ate.core.database import get_context

    c = ctx or get_context()
    src = report_path(c)
    if not src.is_file():
        sync_report_from_session(session, ctx=c)
    dest_dir = archive_dir(c)
    dest_dir.mkdir(parents=True, exist_ok=True)
    sid = str(session.get("session_id") or "session_unknown")
    dest = dest_dir / f"{sid}.json"
    # Prefer the just-synced report contents
    if src.is_file():
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        dest.write_text(json.dumps(session, indent=2), encoding="utf-8")
    return dest


def load_report(ctx=None) -> dict[str, Any]:
    from ate.core.database import get_context

    c = ctx or get_context()
    path = report_path(c)
    if not path.is_file():
        return _empty_report(c)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else _empty_report(c)


_SKIP_WALK = frozenset({"workbook", "_manifest", "screenshots", "graphs"})


def _session_dirs(base: Path, *, depth: int = 0, max_depth: int = 6):
    if depth > max_depth or not base.is_dir():
        return
    name = base.name
    if name.startswith(".") or name.startswith("DUT_") or name in _SKIP_WALK:
        return
    if name == "sessions":
        yield base
        return
    try:
        kids = list(base.iterdir())
    except OSError:
        return
    for child in kids:
        if child.is_dir():
            yield from _session_dirs(child, depth=depth + 1, max_depth=max_depth)


def _parse_campaign_from_sessions(sess: Path, root: Path) -> dict[str, str]:
    try:
        rel = sess.parent.relative_to(root)
        parts = rel.parts
    except ValueError:
        parts = sess.parent.parts[-5:]
    out = {"component": "", "part": "", "package": "", "operator": "", "version": ""}
    if len(parts) >= 5:
        out["component"] = parts[-5]
        out["part"] = parts[-4]
        out["package"] = parts[-3]
        out["operator"] = parts[-2]
        out["version"] = parts[-1]
    return out


def _row_from_session_file(path: Path, root: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    ident = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    if not ident and isinstance(data.get("context"), dict):
        ident = data["context"]
    hdr = data.get("header") if isinstance(data.get("header"), dict) else {}
    sess_dir = path.parent if path.parent.name == "sessions" else path.parent.parent
    parsed = _parse_campaign_from_sessions(sess_dir, root)
    sid = str(hdr.get("session_id") or data.get("session_id") or path.stem)
    started = str(hdr.get("beginning_time") or data.get("started_at") or "")
    if not started:
        try:
            started = datetime.fromtimestamp(path.stat().st_mtime, MYT).isoformat(timespec="seconds")
        except OSError:
            started = ""
    steps = data.get("steps") if isinstance(data.get("steps"), list) else []
    total = int(hdr.get("total") or len(steps) or 0)
    passed = int(hdr.get("pass") or sum(1 for s in steps if isinstance(s, dict) and s.get("success") is True))
    failed = int(hdr.get("fail") or sum(1 for s in steps if isinstance(s, dict) and s.get("success") is False))
    return {
        "session_id": sid,
        "path": str(path),
        "kind": "archive" if path.parent.name == "archive" else ("live" if path.name == "report.json" else "session"),
        "component": str(ident.get("component") or parsed["component"]),
        "part": str(ident.get("part") or parsed["part"]),
        "package": str(ident.get("package") or parsed["package"]),
        "operator": str(ident.get("operator") or hdr.get("user") or parsed["operator"]),
        "version": str(ident.get("version") or parsed["version"]),
        "model": str(ident.get("model") or ""),
        "started": started,
        "status": str(hdr.get("status") or data.get("status") or ""),
        "total": total,
        "pass": passed,
        "fail": failed,
        "tags": list(ident.get("tags") or []),
        "mtime": path.stat().st_mtime if path.is_file() else 0,
        "campaign_root": str(sess_dir.parent),
    }


def list_runs(
    *,
    scope: str = "part",
    component: str = "",
    part: str = "",
    package: str = "",
    operator: str = "",
    version: str = "",
    limit: int = 80,
    ctx=None,
) -> dict[str, Any]:
    """Management ledger of session JSON under the central #Test_Database tree."""
    from ate.core import paths as pathmod
    from ate.core.database import get_context

    c = ctx or get_context()
    root = pathmod.TEST_DB_ROOT
    sc = (scope or "part").strip().lower()
    if sc == "campaign":
        base = c.root()
    elif sc == "all":
        base = root
    else:
        comp = component or c.component
        pt = part or c.part
        pkg = package or c.package
        base = root / comp / pt
        if pkg:
            base = base / pkg
        if operator:
            base = base / operator
            if version:
                base = base / version
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sess in _session_dirs(base):
        files = []
        arch = sess / "archive"
        if arch.is_dir():
            files.extend(sorted(arch.glob("*.json")))
        live = sess / "report.json"
        if live.is_file():
            files.append(live)
        files.extend(sorted(sess.glob("session_*.json")))
        for fp in files:
            key = str(fp.resolve()) if fp.exists() else str(fp)
            if key in seen:
                continue
            seen.add(key)
            row = _row_from_session_file(fp, root)
            if row:
                rows.append(row)
    rows.sort(key=lambda r: (str(r.get("started") or ""), float(r.get("mtime") or 0)), reverse=True)
    cap = max(1, min(200, int(limit or 80)))
    return {
        "root": str(root),
        "scope": sc,
        "base": str(base),
        "cloud_kind": pathmod.cloud_kind(root),
        "runs": rows[:cap],
        "count": min(len(rows), cap),
        "truncated": len(rows) > cap,
    }


def _safe_session_json(path: Path, root: Path) -> Path:
    p = path.resolve()
    base = root.resolve()
    if base not in p.parents and p != base:
        raise PermissionError("path is outside #Test_Database")
    if p.suffix.lower() != ".json":
        raise ValueError("only session JSON can be deleted")
    parent = p.parent.name
    if parent not in ("sessions", "archive"):
        raise ValueError("only sessions/ or sessions/archive JSON")
    if parent == "archive" and p.parent.parent.name != "sessions":
        raise ValueError("archive must sit under sessions/")
    return p


def delete_run_file(path: str, *, ctx=None) -> dict[str, Any]:
    """Delete one session JSON. Never deletes workbook/ or Version folders."""
    from ate.core import paths as pathmod

    root = pathmod.TEST_DB_ROOT
    p = _safe_session_json(Path(path), root)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    p.unlink()
    return {"deleted": str(p), "ok": True}
