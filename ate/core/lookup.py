"""Local datasheet lookup. RAG-ready index. Web fetch is last resort.

Never dumps RUN-IC catalog into #Test_Database.
"""
from __future__ import annotations

import hashlib
import re
import zlib
from pathlib import Path
from typing import Any, Optional

import yaml

from ate.core.paths import CONFIG_DIR, expand_user_path
from ate.core.specs import LIMITS_DIR, load_part_yaml

INDEX_PATH = CONFIG_DIR / "datasheets.yaml"
TEXT_DIR = CONFIG_DIR / "datasheets" / "text"
_DEFAULT_REF = Path.home() / "Downloads" / "Reference" / "Reference"
_PART_FILE = re.compile(r"^(?:\[PROBLEM\]\s*)?(RS[0-9A-Z\-]+)_\(Rev", re.I)
_FAMILY_FILE = re.compile(r"^(?:\[PROBLEM\]\s*)?(RS[0-9A-Z]+)X_\(Rev", re.I)
_TJ = re.compile(rb"\[([^\]]{1,3000})\]\s*TJ")
_TJ1 = re.compile(rb"\((?:\\.|[^\\)]){1,120}\)\s*Tj")
_PDF_STR = re.compile(rb"\((?:\\.|[^\\)]){1,80}\)")

# Family PDF stem -> inventory parts we actually test.
# Do not map look-alike stems onto a different class:
#   RS22X_(RevC.3).pdf is RS222/RS224 opamp, not analog switch RS2323.
#   [PROBLEM] RS32X_(RevC.4).pdf is RS321/RS358/RS324 opamp, not LDO RS3213.
FAMILY_PARTS = {
    "RS62X": ["RS622"],
    "RS35X": ["RS358", "LM358"],
    "RS855X": ["RS8551"],
}


def reference_root() -> Path:
    cfg = CONFIG_DIR / "bench.yaml"
    if cfg.is_file():
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        raw = str((data or {}).get("reference_root") or "").strip()
        if raw:
            return expand_user_path(raw)
    return _DEFAULT_REF


def _pdf_str(raw: bytes) -> str:
    inner = raw[1 : raw.rfind(b")")].decode("latin-1", "replace")
    return inner.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")


def _pdf_plain(path: Path, limit: int = 40000) -> str:
    data = path.read_bytes()
    chunks: list[bytes] = []
    n = 0
    for m in re.finditer(rb"stream\r?\n(.{1,400000}?)endstream", data, re.S):
        n += 1
        if n > 80:
            break
        s = m.group(1)
        if s.startswith(b"\r\n"):
            s = s[2:]
        elif s.startswith(b"\n"):
            s = s[1:]
        try:
            s = zlib.decompress(s)
        except Exception:
            pass
        chunks.append(s)
    blob = b"\n".join(chunks)
    bits: list[str] = []
    for m in _TJ.finditer(blob):
        for s in _PDF_STR.findall(m.group(1)):
            t = _pdf_str(s)
            if t:
                bits.append(t)
    for m in _TJ1.finditer(blob):
        t = _pdf_str(m.group(0))
        if t:
            bits.append(t)
    # Glyphs are often one TJ each; joining with spaces shreds "VOH" into "V O H".
    text = re.sub(r"\s+", " ", "".join(bits)).strip()
    return text[:limit]


def scan_pdfs(root: Path | None = None) -> list[dict[str, Any]]:
    base = root or reference_root()
    rows: list[dict[str, Any]] = []
    if not base.is_dir():
        return rows
    for path in sorted(base.glob("*.pdf")):
        name = path.name
        exact = _PART_FILE.match(name)
        fam = _FAMILY_FILE.match(name)
        parts: list[str] = []
        kind = "unknown"
        if fam and re.search(r"[0-9]X_\(Rev", name, re.I):
            stem = fam.group(1).upper() + "X"
            parts = list(FAMILY_PARTS.get(stem, []))
            kind = "family"
        elif exact:
            parts = [exact.group(1).upper()]
            kind = "part"
        rows.append(
            {
                "file": name,
                "path": str(path),
                "parts": parts,
                "kind": kind,
                "bytes": path.stat().st_size,
            }
        )
    return rows


def build_index(*, persist: bool = True) -> dict[str, Any]:
    from ate.core.new_product import load_inventory

    pdfs = scan_pdfs()
    by_part: dict[str, dict[str, Any]] = {}
    for row in pdfs:
        for part in row.get("parts") or []:
            cur = by_part.get(part)
            if cur is None or (cur.get("kind") == "family" and row.get("kind") == "part"):
                by_part[part] = row
    inv = []
    for r in load_inventory():
        part = str(r.get("part") or "").upper()
        hit = by_part.get(part)
        inv.append(
            {
                "part": part,
                "part_key": part.lower(),
                "model": r.get("model"),
                "package": r.get("package"),
                "category": r.get("category"),
                "pdf": (hit or {}).get("file"),
                "pdf_path": (hit or {}).get("path"),
                "limits": f"ate/config/limits/{part.lower()}.yaml",
            }
        )
    doc = {
        "source": str(reference_root()),
        "note": "Local PDFs first. Web fetch only if a tested SKU has no file here.",
        "pdfs": pdfs,
        "inventory": inv,
    }
    if persist:
        INDEX_PATH.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return doc


def resolve_pdf(part: str, *, index: dict[str, Any] | None = None) -> Optional[Path]:
    sku = re.sub(r"[^A-Za-z0-9\-]+", "", str(part or "")).upper()
    if not sku:
        return None
    doc = index if index is not None else (
        yaml.safe_load(INDEX_PATH.read_text(encoding="utf-8")) if INDEX_PATH.is_file() else None
    )
    if not isinstance(doc, dict):
        doc = build_index(persist=False)
    for row in doc.get("inventory") or []:
        if str(row.get("part") or "").upper() == sku and row.get("pdf_path"):
            p = Path(str(row["pdf_path"]))
            if p.is_file():
                return p
    for row in doc.get("pdfs") or []:
        if sku in [str(x).upper() for x in (row.get("parts") or [])]:
            p = Path(str(row.get("path") or ""))
            if p.is_file():
                return p
    # Direct filename
    root = reference_root()
    for p in root.glob("*.pdf") if root.is_dir() else []:
        if sku.lower() in p.name.lower():
            return p
    return None


def extract_and_store_text(part: str, pdf: Path) -> Path:
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    dest = TEXT_DIR / f"{part.lower()}.txt"
    dest.write_text(_pdf_plain(pdf), encoding="utf-8")
    return dest


def _from_part_tables(part_key: str) -> list[dict[str, Any]]:
    data = load_part_yaml(part_key)
    out: list[dict[str, Any]] = []
    for row in data.get("voh_table") or []:
        if not isinstance(row, dict):
            continue
        vcc = row.get("vcc")
        mn = row.get("spec_min")
        if vcc is None or mn is None:
            continue
        sid = str(row.get("id") or "").strip() or f"VOH_{str(vcc).replace('.', 'p')}V"
        out.append(
            {
                "id": sid,
                "test": "voh_load",
                "unit": "V",
                "min": float(mn),
                "source": f"parts/{part_key}.yaml voh_table",
            }
        )
    for row in data.get("vol_table") or []:
        if not isinstance(row, dict):
            continue
        vcc = row.get("vcc")
        mx = row.get("spec_max")
        if vcc is None or mx is None:
            continue
        sid = str(row.get("id") or "").strip() or f"VOL_{str(vcc).replace('.', 'p')}V"
        out.append(
            {
                "id": sid,
                "test": "vol_load",
                "unit": "V",
                "max": float(mx),
                "source": f"parts/{part_key}.yaml vol_table",
            }
        )
    lim = data.get("display_limit_ua")
    if lim not in (None, ""):
        out.append(
            {
                "id": "IPLUS_uA",
                "test": "iplus",
                "unit": "uA",
                "max": float(lim),
                "source": f"parts/{part_key}.yaml display_limit_ua",
            }
        )
    vout = data.get("vout_nominal")
    if vout not in (None, ""):
        out.append(
            {
                "id": "VOUT_V",
                "test": "iq",
                "unit": "V",
                "typ": float(vout),
                "source": f"parts/{part_key}.yaml vout_nominal",
            }
        )
    return out


def sync_limits_from_local(part: str, *, part_key: str = "", web_ok: bool = False) -> dict[str, Any]:
    """Fill ate/config/limits/<key>.yaml from local PDF + part yaml. Web only if web_ok and missing."""
    from ate.core.datasheet import _guess_specs, _merge_specs

    sku = str(part or "").strip().upper()
    pk = str(part_key or sku).strip().lower()
    pdf = resolve_pdf(sku)
    guessed: list[dict[str, Any]] = []
    text_path = ""
    source = "local-index"
    if pdf and pdf.is_file():
        text_path = str(extract_and_store_text(pk, pdf))
        stored = Path(text_path)
        blob = stored.read_text(encoding="utf-8") if stored.is_file() else _pdf_plain(pdf)
        guessed = _guess_specs(blob, sku)
        for g in guessed:
            g["source"] = f"local:{pdf.name}"
    guessed = _merge_specs(guessed, _from_part_tables(pk))
    if not pdf and web_ok:
        from ate.core.datasheet import fetch_and_store

        return fetch_and_store(sku, part_key=pk)
    lim_path = LIMITS_DIR / f"{pk}.yaml"
    old: dict[str, Any] = {}
    if lim_path.is_file():
        loaded = yaml.safe_load(lim_path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            old = loaded
    existing = list(old["specs"]) if isinstance(old.get("specs"), list) else []
    merged = _merge_specs(existing, guessed)
    old_ids = {str(s.get("id")) for s in existing if isinstance(s, dict)}
    new_ids = {str(s.get("id")) for s in merged if isinstance(s, dict)} - old_ids
    ds_notes = str(((old.get("datasheet") or {}) if isinstance(old.get("datasheet"), dict) else {}).get("notes") or "")
    # "do not attach" is a family-PDF warning, not a freeze. Only rs622 / hand-kept skip rewrite.
    hand = pk == "rs622" or "hand-kept" in ds_notes.lower()
    if lim_path.is_file() and (hand or not new_ids):
        ds = dict(old.get("datasheet") or {}) if isinstance(old.get("datasheet"), dict) else {}
        if pdf and pdf.is_file() and str(ds.get("file") or "") != str(pdf):
            payload = dict(old)
            ds.update(
                {
                    "lang": "en",
                    "source": "local-reference",
                    "file": str(pdf),
                    "extract": text_path or ds.get("extract") or "",
                }
            )
            payload["datasheet"] = ds
            lim_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
            return {
                "part": sku,
                "part_key": pk,
                "pdf": str(pdf),
                "yaml": str(lim_path),
                "specs": existing if existing else merged,
                "source": "hand-limits" if hand else source,
                "wrote": True,
                "note": "Datasheet path updated; existing spec rows kept.",
            }
        return {
            "part": sku,
            "part_key": pk,
            "pdf": str(pdf) if pdf else "",
            "yaml": str(lim_path),
            "specs": existing if existing else merged,
            "source": "hand-limits" if hand else (source if pdf else "unfound"),
            "wrote": False,
            "note": "Existing limits kept.",
        }
    payload = dict(old)
    payload["part"] = sku
    ds = dict(payload.get("datasheet") or {}) if isinstance(payload.get("datasheet"), dict) else {}
    ds.update(
        {
            "lang": "en",
            "source": "local-reference" if pdf else ds.get("source") or "unfound",
            "file": str(pdf) if pdf else ds.get("file") or "",
            "extract": text_path,
        }
    )
    payload["datasheet"] = ds
    payload["specs"] = merged
    LIMITS_DIR.mkdir(parents=True, exist_ok=True)
    lim_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {
        "part": sku,
        "part_key": pk,
        "pdf": str(pdf) if pdf else "",
        "yaml": str(lim_path),
        "specs": payload["specs"],
        "source": source if pdf else "unfound",
        "wrote": True,
        "note": "Local PDF/index only. Did not scrape the website.",
    }


def sync_inventory_limits(*, web_ok: bool = False) -> dict[str, Any]:
    from ate.core.new_product import load_inventory

    build_index(persist=True)
    seen: set[str] = set()
    results = []
    for row in load_inventory():
        part = str(row.get("part") or "").strip()
        pk = part.lower()
        if not part or pk in seen:
            continue
        seen.add(pk)
        results.append(sync_limits_from_local(part, part_key=pk, web_ok=web_ok))
    return {"ok": True, "count": len(results), "parts": results}
