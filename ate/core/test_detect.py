"""Detect unmatched def test_* in golden roots + ate/tests; wrap / enable / copy.

AST-only scan -- never execute golden modules at scan time.
Refuse wrap when source still calls input().
"""
from __future__ import annotations

import ast
import re
import shutil
from pathlib import Path
from typing import Any, Optional

import yaml

from ate.core.paths import CONFIG_DIR, PARTS_DIR, REPO_ROOT

TESTS_ROOT = REPO_ROOT / "ate" / "tests"
GOLDEN_ROOTS_PATH = CONFIG_DIR / "golden_roots.yaml"

SKIP_DIR_NAMES = frozenset({
    ".git", ".github", ".venv", "venv", "node_modules", "__pycache__",
    ".idea", ".vscode", "dist", "build", ".mypy_cache", "_backup",
})
_SECRET_NAME_RE = re.compile(
    r"(^|[/\\])(\.env|.*credentials.*|.*secret.*|id_rsa|.*\.pem)$",
    re.I,
)
_MAX_PY_BYTES = 1_000_000
_TEST_FN_RE = re.compile(r"^test_(.+)$")

# Family key -> package directory under ate/tests/
_FAMILY_PKG_DIR: dict[str, str] = {
    "opamp": "opa",
    "logic": "logic",
    "level": "level",
    "switch": "lim",
    "lim": "lim",
}

_FIXTURE_FOR_FAMILY: dict[str, str] = {
    "opamp": "BUFFER",
    "logic": "LOGIC",
    "level": "LOGIC",
    "switch": "LIM_RS2323",
    "lim": "LIM_RS2323",
}


def _safe_load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def load_golden_roots() -> list[dict[str, Any]]:
    """Configured optional roots. Missing dirs omitted (not an error)."""
    data = _safe_load_yaml(GOLDEN_ROOTS_PATH)
    rows = data.get("roots") if isinstance(data, dict) else None
    out: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = str(row.get("path") or "").strip().strip('"')
        if not raw:
            continue
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = REPO_ROOT / path
        out.append(
            {
                "path": str(path),
                "label": str(row.get("label") or path.name),
                "exists": path.is_dir(),
            }
        )
    return out


def scan_roots() -> list[Path]:
    """Roots that exist: always ate/tests, plus configured goldens that are present."""
    roots: list[Path] = []
    if TESTS_ROOT.is_dir():
        roots.append(TESTS_ROOT.resolve())
    for row in load_golden_roots():
        if not row.get("exists"):
            continue
        p = Path(str(row["path"])).resolve()
        if p not in roots:
            roots.append(p)
    return roots


def _iter_py_files(root: Path) -> list[Path]:
    out: list[Path] = []
    if root.is_file() and root.suffix.lower() == ".py":
        return [root]
    if not root.is_dir():
        return out
    for p in root.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in p.parts):
            continue
        if _SECRET_NAME_RE.search(str(p)):
            continue
        try:
            if p.stat().st_size > _MAX_PY_BYTES:
                continue
        except OSError:
            continue
        out.append(p)
    return out


def guess_family_from_path(path: Path) -> str:
    """Heuristic family from path segments. Operator confirms on wrap."""
    parts = [p.lower() for p in path.parts]
    joined = "/".join(parts)
    if "ate" in parts and "tests" in parts:
        try:
            i = parts.index("tests")
            pkg = parts[i + 1] if i + 1 < len(parts) else ""
            if pkg in ("opa", "opamp"):
                return "opamp"
            if pkg == "logic":
                return "logic"
            if pkg == "level":
                return "level"
            if pkg in ("lim", "switch"):
                return "switch"
            if pkg and pkg not in ("__",):
                return pkg
        except ValueError:
            pass
    if any(
        x in joined
        for x in (
            "/ariff/",
            "\\ariff\\",
            "/soo/",
            "\\soo\\",
            "/logic/",
            "\\logic\\",
            "rs1g",
            "see_lin",
            "seelim",
            "see lim",
            "see-lim",
        )
    ):
        return "logic"
    if any(x in joined for x in ("/lim/", "\\lim\\", "rs2323", "analogswitch", "analog_switch")):
        return "switch"
    if any(x in joined for x in ("/eugene/", "\\eugene\\", "rs622", "/opa/", "\\opa\\", "opamp")):
        return "opamp"
    return ""


def _fn_to_id(name: str) -> str:
    m = _TEST_FN_RE.match(name)
    return m.group(1) if m else name


def _registered_keys(family: str | None = None) -> set[str]:
    """Ids / lab_sheets / test_* names currently registered (optionally load family)."""
    from ate.core.registry import all_tests, load_family

    if family:
        try:
            load_family(family)
        except Exception:
            pass
    keys: set[str] = set()
    for t in all_tests():
        keys.add(str(t.id).lower())
        keys.add(f"test_{t.id}".lower())
        sheet = str(getattr(t, "lab_sheet", "") or "").strip().lower()
        if sheet:
            keys.add(sheet)
            keys.add(sheet.replace(" ", "_"))
            keys.add(sheet.replace(" ", "").lower())
    return keys


def _ast_has_input(fn: ast.FunctionDef) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "input":
                return True
    return False


def _ast_has_instr_param(fn: ast.FunctionDef) -> bool:
    for arg in list(fn.args.args) + list(fn.args.kwonlyargs):
        if arg.arg == "instr":
            return True
    return False


def _blocked_reason(fn: ast.FunctionDef, src: str) -> str:
    # AST Call only -- do not regex the source segment (docstrings can say "no input()").
    if _ast_has_input(fn):
        return "calls input() -- rewrite to pause_hook / Continue before wrap"
    if not _ast_has_instr_param(fn):
        return "missing instr parameter"
    return ""


def scan_file(path: Path, *, registered: set[str] | None = None) -> list[dict[str, Any]]:
    """AST-scan one .py for def test_* not already registered."""
    try:
        src = path.read_text(encoding="utf-8-sig", errors="replace")
        tree = ast.parse(src)
    except (OSError, SyntaxError) as exc:
        return [
            {
                "id": path.stem,
                "fn": "",
                "file": str(path),
                "lineno": 0,
                "family_guess": guess_family_from_path(path),
                "blocked": True,
                "blocked_reason": f"parse error: {exc}",
                "matched": False,
            }
        ]
    reg = registered if registered is not None else set()
    rows: list[dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        tid = _fn_to_id(node.name)
        matched = (
            tid.lower() in reg
            or node.name.lower() in reg
            or tid.replace("_", "").lower() in {k.replace("_", "") for k in reg}
        )
        if matched:
            continue
        reason = _blocked_reason(node, src)
        rows.append(
            {
                "id": tid,
                "fn": node.name,
                "file": str(path),
                "lineno": int(node.lineno or 0),
                "family_guess": guess_family_from_path(path),
                "blocked": bool(reason),
                "blocked_reason": reason,
                "matched": False,
            }
        )
    return rows


def list_detected_tests(*, family: str | None = None) -> dict[str, Any]:
    """Scan all roots; return unmatched def test_* (blocked or wrap-ready)."""
    from ate.core.registry import active_family, known_families, load_family

    roots_meta = load_golden_roots()
    prev = active_family()
    registered: set[str] = set()
    try:
        for fam in known_families():
            try:
                load_family(fam)
                registered |= _registered_keys(None)
            except Exception:
                continue
        if family:
            try:
                load_family(family)
            except Exception:
                pass
        elif prev:
            try:
                load_family(prev)
            except Exception:
                pass
    finally:
        if prev and active_family() != prev:
            try:
                load_family(prev)
            except Exception:
                pass

    detected: list[dict[str, Any]] = []
    scanned_files = 0
    for root in scan_roots():
        for py in _iter_py_files(root):
            if py.name.startswith("imported_") and "ate" in py.parts and "tests" in py.parts:
                continue
            scanned_files += 1
            detected.extend(scan_file(py, registered=registered))

    detected.sort(key=lambda r: (r.get("blocked", False), str(r.get("id") or ""), str(r.get("file") or "")))
    return {
        "ok": True,
        "roots": roots_meta,
        "scanned_files": scanned_files,
        "detected": detected,
        "count": len(detected),
        "blocked_count": sum(1 for r in detected if r.get("blocked")),
    }


def _family_tests_dir(family: str) -> Path:
    key = (family or "").strip().lower()
    if key == "opa":
        key = "opamp"
    if key == "lim":
        key = "switch"
    dirname = _FAMILY_PKG_DIR.get(key, key)
    if not dirname or not re.match(r"^[a-z][a-z0-9_]*$", dirname):
        raise ValueError(f"Invalid family {family!r}")
    dest = TESTS_ROOT / dirname
    if not dest.is_dir():
        raise ValueError(f"Family package missing: {dest}")
    return dest


def _ensure_init_imports(pkg_dir: Path, module_stem: str) -> None:
    init = pkg_dir / "__init__.py"
    text = init.read_text(encoding="utf-8") if init.is_file() else ""
    pkg = f"ate.tests.{pkg_dir.name}"
    line = f"from {pkg} import {module_stem}  # noqa: F401"
    if module_stem in text and f"import {module_stem}" in text:
        return
    if not text.strip():
        text = f'"""Family package — modules call register(TestSpec)."""\n\n'
    if "__all__" in text:
        # Append import before __all__ if possible
        text = text.rstrip() + "\n" + line + "\n"
        m = re.search(r"__all__\s*=\s*\[([^\]]*)\]", text)
        if m and f'"{module_stem}"' not in m.group(0) and f"'{module_stem}'" not in m.group(0):
            inner = m.group(1).rstrip()
            sep = ", " if inner.strip() else ""
            new_inner = f'{inner}{sep}"{module_stem}"'
            text = text[: m.start(1)] + new_inner + text[m.end(1) :]
    else:
        text = text.rstrip() + "\n" + line + f'\n__all__ = ["{module_stem}"]\n'
    init.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def wrap_detected_test(
    *,
    file: str,
    fn: str = "",
    test_id: str = "",
    family: str,
    enable_part: str = "",
    lab_sheet: str = "",
) -> dict[str, Any]:
    """Write imported_<id>.py TestSpec wrap from a clean golden def test_*."""
    src_path = Path(str(file or "")).expanduser()
    if not src_path.is_file():
        raise ValueError(f"Source file not found: {file}")
    src = src_path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        raise ValueError(f"Cannot parse source: {exc}") from exc

    target_fn = (fn or "").strip()
    tid = (test_id or "").strip()
    found: ast.FunctionDef | None = None
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        if target_fn and node.name != target_fn:
            continue
        if tid and _fn_to_id(node.name) != tid and node.name != tid:
            continue
        if not target_fn and not tid:
            # first test_* if unspecified
            found = node
            break
        found = node
        break
    if found is None:
        raise ValueError(f"No matching def test_* in {src_path.name}")

    tid = tid or _fn_to_id(found.name)
    if not re.match(r"^[a-z][a-z0-9_]*$", tid):
        raise ValueError(f"Invalid test id {tid!r}")

    reason = _blocked_reason(found, src)
    if reason:
        raise ValueError(f"Refusing wrap: {reason}")

    fam = (family or "").strip().lower()
    if fam in ("opa",):
        fam = "opamp"
    if fam == "lim":
        fam = "switch"
    pkg_dir = _family_tests_dir(fam)
    module_stem = f"imported_{tid}"
    dest = pkg_dir / f"{module_stem}.py"
    if dest.is_file():
        bak = dest.with_suffix(dest.suffix + f".bak_{dest.stat().st_mtime_ns}")
        shutil.copy2(dest, bak)

    fixture = _FIXTURE_FOR_FAMILY.get(fam, "LOGIC")
    sheet = (lab_sheet or tid.replace("_", " ").title()).strip() or tid
    label = tid.replace("_", " ").title()
    src_disp = str(src_path).replace("\\", "/")

    body = f'''"""Imported TestSpec wrap for {tid} (F23 / A16).

Source (reference only, not imported at runtime):
  {src_disp}:{found.lineno}

Do not call input(). Use params.pause_hook for Continue gates.
Fill the measurement body when the golden recipe is ready.
"""
from __future__ import annotations

from typing import Any

from ate.core.registry import TestSpec, register
from ate.core.runner import RunParams

_FIXTURE = {fixture!r}
_NOTE = "Imported from golden; fill measurement body. Source: {src_disp}"


def _pause(params: RunParams, title: str) -> bool:
    hook = params.pause_hook
    if hook is None:
        return True
    return bool(hook(title))


def _run(instr, params: RunParams) -> dict[str, Any]:
    if not _pause(params, f"{label}: confirm wiring from imported golden, then Continue"):
        return {{"summary": "aborted", "data": {{}}}}
    return {{
        "summary": f"{tid} imported scaffold -- fill body",
        "data": {{"imported_from": {src_disp!r}, "fn": {found.name!r}}},
    }}


register(
    TestSpec(
        id={tid!r},
        label={label!r},
        required_instruments=frozenset({{"PSU"}}),
        fixture_mode=_FIXTURE,
        lab_sheet={sheet!r},
        run=_run,
        dual_channel=False,
        notes=_NOTE,
    )
)
'''
    dest.write_text(body, encoding="utf-8")
    _ensure_init_imports(pkg_dir, module_stem)

    from ate.core.registry import all_tests, load_family, refresh_family_table

    refresh_family_table()
    loaded = load_family(fam)
    ids = {t.id for t in all_tests()}
    if tid not in ids:
        raise RuntimeError(f"Wrap wrote {dest} but {tid!r} not in registry after load_family({fam})")

    enabled = None
    if enable_part:
        enabled = enable_tests_on_part(
            dest_part=enable_part,
            test_ids=[tid],
            family=fam,
        )

    return {
        "ok": True,
        "id": tid,
        "family": loaded,
        "module": str(dest),
        "lab_sheet": sheet,
        "enabled": enabled,
        "test_count": len(ids),
    }


def _part_yaml_path(part_key: str) -> Path:
    key = re.sub(r"[^a-z0-9]+", "", (part_key or "").strip().lower())
    if not key:
        raise ValueError("part key required")
    return PARTS_DIR / f"{key}.yaml"


def family_for_part(part_key: str) -> str:
    from ate.core.database import family_for_component

    path = _part_yaml_path(part_key)
    data = _safe_load_yaml(path)
    comp = str(data.get("component") or "")
    fam = family_for_component(comp) if comp else ""
    if fam:
        return fam
    # product_class fallback via run_ic categories
    pc = str(data.get("product_class") or "").strip().lower()
    if pc in ("opamp", "logic", "level", "switch", "lim"):
        return "switch" if pc == "lim" else pc
    return ""


def enable_tests_on_part(
    *,
    dest_part: str,
    test_ids: list[str],
    family: str = "",
    source_part: str = "",
    update_catalog: bool = True,
) -> dict[str, Any]:
    """Append test ids to dest part enabled_tests. Same-family only."""
    from ate.core.registry import all_tests, load_family

    dest_key = re.sub(r"[^a-z0-9]+", "", (dest_part or "").strip().lower())
    if not dest_key:
        raise ValueError("dest_part required")
    ids = [str(x).strip() for x in (test_ids or []) if str(x).strip()]
    if not ids:
        raise ValueError("test_ids required")

    dest_fam = family_for_part(dest_key)
    src_key = re.sub(r"[^a-z0-9]+", "", (source_part or "").strip().lower())
    if src_key:
        src_fam = family_for_part(src_key)
        if not src_fam or not dest_fam or src_fam != dest_fam:
            raise ValueError(
                f"Cross-family copy refused: source={src_key!r}/{src_fam!r} "
                f"dest={dest_key!r}/{dest_fam!r}"
            )
        fam = src_fam
    else:
        fam = (family or dest_fam or "").strip().lower()
        if fam == "lim":
            fam = "switch"
        if not fam:
            raise ValueError(f"Cannot resolve family for part {dest_key!r}")
        if dest_fam and dest_fam != fam:
            raise ValueError(
                f"Cross-family copy refused: family={fam!r} dest={dest_key!r}/{dest_fam!r}"
            )

    load_family(fam)
    known = {t.id for t in all_tests()}
    missing = [i for i in ids if i not in known]
    if missing:
        raise ValueError(f"Ids not in family {fam!r} registry: {missing}")

    path = _part_yaml_path(dest_key)
    if not path.is_file():
        raise ValueError(f"Part yaml missing: {path}")
    data = _safe_load_yaml(path)
    existing = data.get("enabled_tests")
    if not isinstance(existing, list):
        existing = []
    merged = list(existing)
    added: list[str] = []
    for i in ids:
        if i not in merged:
            merged.append(i)
            added.append(i)
    data["enabled_tests"] = merged
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    catalog_path = None
    catalog_added: list[str] = []
    if update_catalog:
        try:
            from ate.core.database import get_context

            ctx = get_context()
            if str(ctx.part_key or "").lower() == dest_key or str(ctx.part or "").lower() == dest_key:
                cpath = ctx.root() / "_manifest" / "test_catalog.yaml"
                catalog_path = str(cpath)
                cdata = _safe_load_yaml(cpath) if cpath.is_file() else {}
                cen = cdata.get("enabled_tests")
                if not isinstance(cen, list):
                    cen = []
                for i in ids:
                    if i not in cen:
                        cen.append(i)
                        catalog_added.append(i)
                cdata["enabled_tests"] = cen
                cpath.parent.mkdir(parents=True, exist_ok=True)
                cpath.write_text(
                    yaml.safe_dump(cdata, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )
        except Exception:
            pass

    return {
        "ok": True,
        "dest_part": dest_key,
        "family": fam,
        "enabled_tests": merged,
        "added": added,
        "catalog_path": catalog_path,
        "catalog_added": catalog_added,
    }


def copy_enabled_tests(*, source_part: str, dest_part: str) -> dict[str, Any]:
    """Copy source part's enabled_tests onto dest (same family)."""
    from ate.fixture.modes import enabled_tests_for_part

    src_key = re.sub(r"[^a-z0-9]+", "", (source_part or "").strip().lower())
    ids = enabled_tests_for_part(src_key) or []
    if not ids:
        raise ValueError(f"Source part {src_key!r} has no enabled_tests")
    return enable_tests_on_part(
        dest_part=dest_part,
        test_ids=list(ids),
        source_part=src_key,
    )
