"""STS8200-shaped session export: markdown, HTML (print-to-PDF), simple PDF.

Mirrors the production datalog sheet (Parameter / Unit / Min / Max / Typ / Value / Result).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _fmt(v: Any) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, float):
        if abs(v) >= 100:
            return f"{v:.2f}"
        if abs(v) >= 1:
            return f"{v:.4f}"
        return f"{v:.6g}"
    return str(v)


def _iter_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in doc.get("steps") or []:
        if not isinstance(step, dict):
            continue
        meas = step.get("measurements") if isinstance(step.get("measurements"), list) else []
        if not meas:
            rows.append(
                {
                    "id": str(step.get("test_id") or ""),
                    "unit": "",
                    "min": "",
                    "max": "",
                    "typ": "",
                    "value": "",
                    "result": "PASS" if step.get("success") else ("FAIL" if step.get("success") is False else ""),
                    "dut": step.get("dut"),
                    "test_id": step.get("test_id"),
                }
            )
            continue
        for m in meas:
            if not isinstance(m, dict):
                continue
            res = str(m.get("result") or "")
            if res == "pass":
                res = "PASS"
            elif res == "fail":
                res = "FAIL"
            elif res == "unspec":
                res = "UNSPEC"
            rows.append(
                {
                    "id": str(m.get("id") or step.get("test_id") or ""),
                    "unit": str(m.get("unit") or ""),
                    "min": m.get("min"),
                    "max": m.get("max"),
                    "typ": m.get("typ"),
                    "value": m.get("value"),
                    "result": res,
                    "dut": step.get("dut"),
                    "test_id": step.get("test_id"),
                    "source": m.get("source") or "",
                }
            )
    return rows


def render_markdown(doc: dict[str, Any]) -> str:
    hdr = doc.get("header") or {}
    ident = doc.get("identity") or {}
    rows = _iter_rows(doc)
    fail_n = sum(1 for r in rows if r.get("result") == "FAIL")
    pass_n = sum(1 for r in rows if r.get("result") == "PASS")
    lines = [
        "# STS Datalog Sheet",
        "",
        f"- Time: {hdr.get('time') or ''}",
        f"- Program: {hdr.get('program') or 'ate.worker'}",
        f"- User: {hdr.get('user') or ident.get('operator') or ''}",
        f"- Part: {ident.get('part') or ''} {ident.get('model') or ''} {ident.get('package') or ''}",
        f"- Operator / Version: {ident.get('operator') or ''} / {ident.get('version') or ''}",
        f"- Session: {hdr.get('session_id') or ''}",
        f"- Beginning: {hdr.get('beginning_time') or ''}",
        f"- Ending: {hdr.get('ending_time') or ''}",
        f"- Total: {len(rows)}  Pass: {pass_n}  Fail: {fail_n}",
        "",
        "| Parameter | Unit | Min | Max | Typ | Value | Result | DUT | Test |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(r.get("id") or ""),
                    str(r.get("unit") or ""),
                    _fmt(r.get("min")),
                    _fmt(r.get("max")),
                    _fmt(r.get("typ")),
                    _fmt(r.get("value")),
                    str(r.get("result") or ""),
                    str(r.get("dut") or ""),
                    str(r.get("test_id") or ""),
                ]
            )
            + " |"
        )
    fails = [r for r in rows if r.get("result") == "FAIL"]
    lines.extend(["", "## Fails", ""])
    if not fails:
        lines.append("None.")
    else:
        for r in fails:
            lines.append(
                f"- {r.get('id')} value={_fmt(r.get('value'))} "
                f"min={_fmt(r.get('min'))} max={_fmt(r.get('max'))} DUT={r.get('dut')}"
            )
    return "\n".join(lines) + "\n"


def render_html(doc: dict[str, Any]) -> str:
    hdr = doc.get("header") or {}
    ident = doc.get("identity") or {}
    rows = _iter_rows(doc)
    body_rows = []
    for r in rows:
        cls = str(r.get("result") or "").lower()
        body_rows.append(
            "<tr class='{cls}'><td>{id}</td><td>{unit}</td><td>{mn}</td>"
            "<td>{mx}</td><td>{typ}</td><td>{val}</td><td>{res}</td>"
            "<td>{dut}</td><td>{tid}</td></tr>".format(
                cls=cls,
                id=str(r.get("id") or ""),
                unit=str(r.get("unit") or ""),
                mn=_fmt(r.get("min")),
                mx=_fmt(r.get("max")),
                typ=_fmt(r.get("typ")),
                val=_fmt(r.get("value")),
                res=str(r.get("result") or ""),
                dut=str(r.get("dut") or ""),
                tid=str(r.get("test_id") or ""),
            )
        )
    title = f"{ident.get('part') or 'ATE'} STS Datalog"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>{title}</title>
<style>
body {{ font-family: Calibri, Arial, sans-serif; font-size: 12px; margin: 16px; color: #111; }}
h1 {{ font-size: 18px; margin: 0 0 8px; }}
.meta {{ margin: 0 0 12px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #333; padding: 3px 6px; text-align: left; }}
th {{ background: #eee; }}
tr.fail td {{ background: #f8d0d0; font-weight: 600; }}
tr.pass td {{ background: #e7f5e7; }}
@media print {{ body {{ margin: 8px; }} }}
</style></head><body>
<h1>STS Datalog Sheet</h1>
<p class="meta">
Time: {hdr.get('time') or ''}<br/>
Program: {hdr.get('program') or 'ate.worker'} &nbsp; User: {hdr.get('user') or ident.get('operator') or ''}<br/>
Part: {ident.get('part') or ''} {ident.get('model') or ''} {ident.get('package') or ''}<br/>
Operator / Version: {ident.get('operator') or ''} / {ident.get('version') or ''}<br/>
Session: {hdr.get('session_id') or ''}<br/>
Beginning: {hdr.get('beginning_time') or ''} &nbsp; Ending: {hdr.get('ending_time') or ''}<br/>
Total {len(rows)} &nbsp; Pass {sum(1 for r in rows if r.get('result')=='PASS')} &nbsp;
Fail {sum(1 for r in rows if r.get('result')=='FAIL')}
</p>
<table>
<thead><tr><th>Parameter</th><th>Unit</th><th>Min</th><th>Max</th><th>Typ</th><th>Value</th><th>Result</th><th>DUT</th><th>Test</th></tr></thead>
<tbody>
{''.join(body_rows)}
</tbody></table>
<p>Print this page to PDF (Ctrl+P). Limits come from ate/config/limits/&lt;key&gt;.yaml (datasheet min/typ/max), not a website catalog dump.</p>
</body></html>
"""


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_simple_pdf(path: Path, lines: list[str], *, title: str = "STS Datalog") -> None:
    """Minimal multi-page text PDF. No extra dependency."""
    write_table_pdf(path, lines=lines, title=title)


def write_table_pdf(
    path: Path,
    *,
    lines: list[str] | None = None,
    rows: list[dict[str, Any]] | None = None,
    meta: list[str] | None = None,
    title: str = "STS Datalog",
) -> None:
    """Landscape table PDF: Parameter Unit Min Max Typ Value Result DUT Test."""
    page_w, page_h = 792, 612
    margin, leading = 28, 11
    headers = ["Parameter", "Unit", "Min", "Max", "Typ", "Value", "Result", "DUT", "Test"]
    col_w = [110, 44, 52, 52, 52, 60, 52, 32, 80]
    table: list[list[str]] = []
    if rows is not None:
        table.append(headers)
        for r in rows:
            table.append(
                [
                    str(r.get("id") or "")[:22],
                    str(r.get("unit") or "")[:8],
                    _fmt(r.get("min"))[:10],
                    _fmt(r.get("max"))[:10],
                    _fmt(r.get("typ"))[:10],
                    _fmt(r.get("value"))[:12],
                    str(r.get("result") or "")[:8],
                    str(r.get("dut") or "")[:4],
                    str(r.get("test_id") or "")[:14],
                ]
            )
    else:
        for line in lines or [""]:
            table.append([line[:120]])
    head = list(meta or [])
    usable = max(1, int((page_h - 2 * margin - (len(head) + 1) * leading) / leading))
    body = table[1:] if rows is not None else table
    hdr = table[:1] if rows is not None else []
    chunks = [body[i : i + usable] for i in range(0, max(len(body), 1), usable)] or [[]]
    n = len(chunks)
    font_n = 3 + 2 * n
    objs: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Count {n} /Kids [{ ' '.join(str(3 + 2 * i) + ' 0 R' for i in range(n)) }] >>".encode(),
    ]
    for i, chunk in enumerate(chunks):
        page_n = 3 + 2 * i
        content_n = page_n + 1
        y = page_h - margin
        cmds = ["BT", "/F1 8 Tf"]
        for line in head:
            cmds.append(f"1 0 0 1 {margin} {y} Tm ({_pdf_escape(line[:110])}) Tj")
            y -= leading
        y -= 4
        draw = hdr + chunk if hdr else chunk
        for ri, cols in enumerate(draw):
            x = margin
            if rows is not None:
                cmds.append("/F1 8 Tf")
                for ci, val in enumerate(cols):
                    w = col_w[ci] if ci < len(col_w) else 48
                    cmds.append(f"1 0 0 1 {x} {y} Tm ({_pdf_escape(str(val)[:18])}) Tj")
                    x += w
            else:
                cmds.append(f"1 0 0 1 {margin} {y} Tm ({_pdf_escape(str(cols[0])[:120])}) Tj")
            y -= leading
            if ri == 0 and hdr:
                y -= 2
        cmds.append("ET")
        stream = "\n".join(cmds).encode("latin-1", "replace")
        objs.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w} {page_h}] "
                f"/Contents {content_n} 0 R /Resources << /Font << /F1 {font_n} 0 R >> >> >>"
            ).encode()
        )
        objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body_obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode())
        out.extend(body_obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objs) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer << /Size {len(objs) + 1} /Root 1 0 R /Info << /Title ({_pdf_escape(title)}) >> >>\n".encode()
    )
    out.extend(f"startxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(bytes(out))


def export_sts(doc: dict[str, Any], dest_dir: Path) -> dict[str, str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    md_path = dest_dir / "datalog.md"
    html_path = dest_dir / "datalog.html"
    pdf_path = dest_dir / "datalog.pdf"
    md = render_markdown(doc)
    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(render_html(doc), encoding="utf-8")
    ident = doc.get("identity") or {}
    hdr = doc.get("header") or {}
    title = f"{ident.get('part') or 'ATE'} STS Datalog"
    meta = [
        f"STS Datalog  {ident.get('part') or ''} {ident.get('model') or ''} {ident.get('package') or ''}",
        f"Operator {ident.get('operator') or ''}  Version {ident.get('version') or ''}  Session {hdr.get('session_id') or ''}",
        f"Time {hdr.get('time') or ''}  Begin {hdr.get('beginning_time') or ''}  End {hdr.get('ending_time') or ''}",
    ]
    write_table_pdf(pdf_path, rows=_iter_rows(doc), meta=meta, title=title)
    return {
        "markdown": str(md_path),
        "html": str(html_path),
        "pdf": str(pdf_path),
    }


def export_latest_report(
    doc: dict[str, Any],
    *,
    sessions_dir: Path,
    version_dir: Path | None = None,
) -> dict[str, str]:
    """STS latest: sessions/datalog.* plus Version-root report.pdf overwrite.

    Copies measured rows + min/max/result from the living session doc.
    Never invents pass numbers.
    """
    paths = dict(export_sts(doc, sessions_dir))
    src_pdf = Path(paths.get("pdf") or "")
    blob = src_pdf.read_bytes() if src_pdf.is_file() else b""
    if blob:
        sessions_latest = Path(sessions_dir) / "report.pdf"
        sessions_latest.write_bytes(blob)
        paths["sessions_report_pdf"] = str(sessions_latest)
    if version_dir is None:
        return paths
    version_dir = Path(version_dir)
    version_dir.mkdir(parents=True, exist_ok=True)
    latest = version_dir / "report.pdf"
    if blob:
        latest.write_bytes(blob)
    else:
        ident = doc.get("identity") or {}
        hdr = doc.get("header") or {}
        title = f"{ident.get('part') or 'ATE'} STS Datalog"
        meta = [
            f"STS Datalog  {ident.get('part') or ''} {ident.get('model') or ''} {ident.get('package') or ''}",
            f"Operator {ident.get('operator') or ''}  Version {ident.get('version') or ''}  Session {hdr.get('session_id') or ''}",
            f"Time {hdr.get('time') or ''}  Begin {hdr.get('beginning_time') or ''}  End {hdr.get('ending_time') or ''}",
        ]
        write_table_pdf(latest, rows=_iter_rows(doc), meta=meta, title=title)
    paths["latest"] = str(latest)
    paths["version_pdf"] = str(latest)
    return paths
