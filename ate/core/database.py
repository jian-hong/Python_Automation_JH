"""Test Database tree — component / part / package / operator / version.

Canonical layout (images + waveforms + manifests; Excel linked by sheet_map):

  #Test_Database/
    {Component}/          e.g. OpAmp
      {Part}/             e.g. RS622
        {Package}/        e.g. TTSOP8
          {Operator}/     e.g. Eugene (person folder; not "All")
            {Version_N}/  e.g. Version_1  (campaign — not calendar year)
              _manifest/
                sheet_map.yaml      # folder <-> Excel sheet <-> paste anchors
                test_catalog.yaml
              workbook/             # lab report (editable; Excel MCP target)
              sessions/             # per-run JSON manifests
              {TestKey}/            # ORT, VOS, SlewRate, …
                DUT_{1..N}/
                  screenshots/
                  graphs/

Fixture / gain "config" is NOT a path segment — it lives in sheet_map +
ate/fixture/modes.py and drives operator prompts between batches.

Photo naming: {TEST}_{DUT}_{VARIANT}_{YYYY-MM-DD_HHMMSS}.jpg
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from ate.core.paths import CONFIG_DIR, PARTS_DIR, TEST_DB_ROOT, cloud_kind, expand_user_path

MYT = timezone(timedelta(hours=8))

_VERSION_RE = re.compile(r"^Version_(\d+)$", re.IGNORECASE)
_OWNER_ID_RE = re.compile(r"^[a-z][a-z0-9]*$")
UNASSIGNED_OPERATOR = "_unassigned"
WRITE_BLOCKED_OPERATORS = frozenset({"", "all", "All", "ALL"})
OWNERS_PATH = CONFIG_DIR / "owners.yaml"
_OWNERS_PREAMBLE = (
    "# Operators are people. Family rail is product class (RUN-IC).\n"
    "# Picking an operator defaults their campaign; other families stay.\n"
    "\n"
)


def is_version_name(name: str) -> bool:
    n = str(name or "")
    return bool(_VERSION_RE.match(n) or n.lower().startswith("version"))


def is_campaign_dir(path: Path) -> bool:
    """True if path looks like a Version campaign root."""
    if not path.is_dir():
        return False
    if is_version_name(path.name):
        return True
    return (path / "_manifest").is_dir() or (path / "workbook").is_dir()


def _looks_like_person(raw: str) -> bool:
    s = str(raw or "").strip()
    if not s or s.lower() == "all" or s.startswith("_"):
        return False
    return bool(re.search(r"[A-Za-z]", s))


def owner_id_from_label(label: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9]+", "", str(label or "").strip())
    oid = compact.lower()
    if not oid or not _OWNER_ID_RE.match(oid) or oid == "all":
        raise ValueError("Person name must include letters (not All)")
    return oid


def operator_folder_label(owner_id_or_label: str | None) -> str:
    """Map owners.yaml id/label to a filesystem folder name. Never returns All."""
    raw = str(owner_id_or_label or "").strip()
    if not raw or raw.lower() == "all":
        raise ValueError("Operator=All is view-only; pick a person before writing campaigns")
    for row in load_owners():
        oid = str(row.get("id") or "")
        label = str(row.get("label") or oid)
        if oid.lower() == raw.lower() or label.lower() == raw.lower():
            if oid.lower() == "all":
                raise ValueError("Operator=All is view-only; pick a person before writing campaigns")
            return label
    if raw.startswith("_"):
        return raw
    if _looks_like_person(raw):
        return raw
    return UNASSIGNED_OPERATOR


def require_write_operator(operator: str | None) -> str:
    """Normalize operator folder for writes; reject All / empty."""
    raw = str(operator or "").strip()
    if raw in WRITE_BLOCKED_OPERATORS or raw.lower() == "all":
        raise ValueError("Operator=All is view-only; pick a person before writing campaigns")
    return operator_folder_label(raw)


def prefer_live_operator(
    package_dir: Path,
    version: str,
    part: str,
    parsed: str,
) -> str:
    """Skip leftover _unassigned when a person campaign exists beside it."""
    parsed = (parsed or "").strip() or UNASSIGNED_OPERATOR
    if parsed != UNASSIGNED_OPERATOR and not parsed.startswith("_"):
        return parsed
    try:
        from ate.core.migrate_operator_folders import _pic_label_map

        pic = _pic_label_map().get(str(part).upper(), "")
    except Exception:
        pic = ""
    if pic and pic != UNASSIGNED_OPERATOR and (package_dir / pic / version).is_dir():
        return pic
    if package_dir.is_dir():
        for child in sorted(package_dir.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith("_") or child.name == UNASSIGNED_OPERATOR:
                continue
            if is_version_name(child.name):
                continue
            if (child / version).is_dir():
                return child.name
    return parsed


@dataclass
class DbContext:
    """Active characterization campaign under #Test_Database."""

    component: str = "OpAmp"
    part: str = "RS622"
    package: str = "TTSOP8"
    operator: str = "Eugene"  # person folder under Package/
    version: str = "Version_1"
    model: str = "RS622XK"  # marketing / datasheet model name
    sample_size: int = 4
    part_key: str = "rs622"  # ate/config/parts/<key>.yaml
    year: str = ""  # optional metadata only (not a folder axis)
    notes: str = ""

    def root(self) -> Path:
        op = str(self.operator or UNASSIGNED_OPERATOR).strip() or UNASSIGNED_OPERATOR
        return TEST_DB_ROOT / self.component / self.part / self.package / op / self.version

    def manifest_dir(self) -> Path:
        return self.root() / "_manifest"

    def sessions_dir(self) -> Path:
        return self.root() / "sessions"

    def workbook_dir(self) -> Path:
        return self.root() / "workbook"

    def sheet_map_path(self) -> Path:
        return self.manifest_dir() / "sheet_map.yaml"

    def test_catalog_path(self) -> Path:
        return self.manifest_dir() / "test_catalog.yaml"

    def test_params_path(self) -> Path:
        return self.manifest_dir() / "test_params.yaml"

    def lab_report_path(self) -> Path:
        # Prefer sheet_map workbook path; else first xlsx in workbook/; else part yaml.
        sm = self.load_sheet_map()
        rel = ((sm.get("workbook") or {}) if isinstance(sm, dict) else {}).get("path")
        if rel:
            candidate = (self.manifest_dir() / str(rel)).resolve()
            if candidate.is_file():
                return candidate
        wb = self.workbook_dir()
        if wb.is_dir():
            xlsx = sorted(wb.glob("*.xlsx"))
            if xlsx:
                return xlsx[0]
        return wb / f"{self.model}_Lab_Report_{self.package}.xlsx"

    def test_folder(self, test_key: str) -> Path:
        return self.root() / test_key

    def dut_folder(self, test_key: str, dut_index: int) -> Path:
        return self.test_folder(test_key) / f"DUT_{int(dut_index)}"

    def screenshot_dir(self, test_key: str, dut_index: int | None = None) -> Path:
        if dut_index is None:
            return self.test_folder(test_key) / "screenshots"
        return self.dut_folder(test_key, dut_index) / "screenshots"

    def graph_dir(self, test_key: str, dut_index: int | None = None) -> Path:
        if dut_index is None:
            return self.test_folder(test_key) / "graphs"
        return self.dut_folder(test_key, dut_index) / "graphs"

    def _default_photo_test_key(self) -> str:
        """First real test folder / sheet_map folder; ORT only as OpAmp fallback."""
        skip = {"_manifest", "workbook", "sessions"}
        sm = self.load_sheet_map()
        tests = (sm.get("tests") or {}) if isinstance(sm, dict) else {}
        for key, entry in tests.items() if isinstance(tests, dict) else []:
            folder = ""
            if isinstance(entry, dict):
                folder = str(entry.get("folder") or "")
            name = folder or str(key)
            if name and (self.root() / name).is_dir():
                return name
        root = self.root()
        if root.is_dir():
            for child in sorted(root.iterdir()):
                if child.is_dir() and child.name not in skip and not child.name.startswith("_"):
                    return child.name
        fam = family_for_component(self.component)
        if fam == "opamp":
            return "ORT"
        return "Setup"

    def photo_preview(self, test_key: str | None = None, dut_index: int = 1) -> str:
        key = test_key or self._default_photo_test_key()
        return str(self.screenshot_dir(key, dut_index))

    def identity(self) -> dict[str, Any]:
        tags: list[str] = []
        boards: list[str] = []
        labels: list[dict[str, str]] = []
        try:
            from ate.core.tags import load_tags

            t = load_tags(self)
            tags = list(t.get("tags") or [])
            boards = list(t.get("boards") or [])
            labels = list(t.get("labels") or [])
        except Exception:
            pass
        return {
            "component": self.component,
            "part": self.part,
            "package": self.package,
            "operator": self.operator,
            "version": self.version,
            "model": self.model,
            "sample_size": self.sample_size,
            "part_key": self.part_key,
            "year": self.year,
            "tags": tags,
            "boards": boards,
            "labels": labels,
            "root": str(self.root()),
            "lab_report": str(self.lab_report_path()),
            "sheet_map": str(self.sheet_map_path()),
            "sessions": str(self.sessions_dir()),
            "photo_example": self.photo_preview(),
            "test_database_root": str(TEST_DB_ROOT),
            "cloud_kind": cloud_kind(TEST_DB_ROOT),
        }

    def load_sheet_map(self) -> dict[str, Any]:
        path = self.sheet_map_path()
        if not path.is_file():
            return {}
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data if isinstance(data, dict) else {}

    def load_test_catalog(self) -> dict[str, Any]:
        path = self.test_catalog_path()
        if not path.is_file():
            return {}
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data if isinstance(data, dict) else {}

    def load_test_params(self) -> dict[str, Any]:
        """Version overlay (PRD-004): vcc_list, levels, rails, pass_mode."""
        path = self.test_params_path()
        if not path.is_file():
            return {}
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data if isinstance(data, dict) else {}

    def save_test_params(self, blob: dict[str, Any] | None) -> dict[str, Any]:
        """Write campaign _manifest/test_params.yaml. Does not edit part yaml."""
        require_write_operator(self.operator)
        allowed = (
            "vcc_list",
            "vcc_sweep_list",
            "levels",
            "rails",
            "pass_mode",
            "logic_inputs",
            "isolation",
            "threshold_isolation",
            "gaps",
            "oe",
            "schmitt",
        )
        incoming = blob if isinstance(blob, dict) else {}
        existing = self.load_test_params()
        for key in allowed:
            if key in incoming:
                existing[key] = incoming[key]
        self.manifest_dir().mkdir(parents=True, exist_ok=True)
        path = self.test_params_path()
        text = (
            "# Version overlay (PRD-004 / EPIC-A28). Does not change part yaml or limits yaml.\n"
            "# Keys: vcc_list, levels, rails, pass_mode, logic_inputs, isolation.\n"
            + yaml.safe_dump(existing, sort_keys=False, allow_unicode=True)
        )
        path.write_text(text, encoding="utf-8")
        return {"ok": True, "path": str(path), "test_params": existing}

    def test_entry(self, test_key: str) -> dict[str, Any]:
        sm = self.load_sheet_map()
        tests = sm.get("tests") or {}
        if not isinstance(tests, dict):
            return {}
        # Accept folder key or excel sheet name.
        if test_key in tests:
            return dict(tests[test_key])
        for _k, entry in tests.items():
            if not isinstance(entry, dict):
                continue
            if entry.get("folder") == test_key or entry.get("excel_sheet") == test_key:
                return dict(entry)
        return {}

    def ensure_tree(self, test_keys: Optional[list[str]] = None) -> list[str]:
        """Create sessions/_manifest and DUT screenshot/graph folders."""
        created: list[str] = []
        root = self.root()
        for rel in ("_manifest", "sessions", "workbook"):
            p = root / rel
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
                created.append(str(p))

        keys = list(test_keys or [])
        if not keys:
            sm = self.load_sheet_map()
            tests = sm.get("tests") or {}
            if isinstance(tests, dict):
                for _k, entry in tests.items():
                    if isinstance(entry, dict) and entry.get("folder"):
                        keys.append(str(entry["folder"]))
                    elif isinstance(_k, str):
                        keys.append(_k)
        if not keys:
            try:
                from ate.fixture.modes import enabled_tests_for_part

                keys = list(enabled_tests_for_part(self.part_key) or [])
            except Exception:
                keys = []
        if not keys:
            # Never grow OpAmp GBW/ORT on Level/Power/Logic stubs.
            keys = ["Setup"]

        n = max(1, int(self.sample_size))
        for key in keys:
            for dut in range(1, n + 1):
                for sub in ("screenshots", "graphs"):
                    p = self.dut_folder(key, dut) / sub
                    if not p.exists():
                        p.mkdir(parents=True, exist_ok=True)
                        created.append(str(p))
            shared = self.test_folder(key) / "screenshots"
            if not shared.exists():
                shared.mkdir(parents=True, exist_ok=True)
                created.append(str(shared))
        return created


@dataclass
class RunSession:
    """One ATE run archived under sessions/."""

    session_id: str
    started_at: str
    context: dict[str, Any]
    params: dict[str, Any] = field(default_factory=dict)
    instrument_map: dict[str, str] = field(default_factory=dict)
    fixture_plan: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    finished_at: str = ""
    status: str = "running"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_lock = threading.Lock()
_active: Optional[DbContext] = None
_current_session: Optional[RunSession] = None


def _read_bench_defaults() -> dict[str, Any]:
    path = CONFIG_DIR / "bench.yaml"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


def _model_from_part_yaml(part_key: str) -> tuple[str, str, int]:
    path = PARTS_DIR / f"{part_key}.yaml"
    model, package, sample = part_key.upper(), "TTSOP8", 4
    if path.is_file():
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if isinstance(data, dict):
            model = str(data.get("part") or model)
            package = str(data.get("package") or package)
            sample = int(data.get("sample_size") or sample)
    return model, package, sample


def default_context() -> DbContext:
    bench = _read_bench_defaults()
    part_key = str(bench.get("default_part") or "rs622")
    model, package, sample = _model_from_part_yaml(part_key)
    year = str(bench.get("year") or datetime.now(MYT).year)

    # Prefer parsing test_database path from bench.yaml
    td = bench.get("test_database")
    if td:
        p = expand_user_path(str(td))
        # New: …/#Test_Database/OpAmp/RS622/TTSOP8/Eugene/Version_1
        # Legacy: …/#Test_Database/OpAmp/RS622/TTSOP8/Version_1
        try:
            parts = p.parts
            idx = next(i for i, x in enumerate(parts) if x == "#Test_Database" or x == "Test_Database")
            component = parts[idx + 1]
            part = parts[idx + 2]
            package = parts[idx + 3]
            seg4 = parts[idx + 4]
            if is_version_name(seg4):
                operator = UNASSIGNED_OPERATOR
                version = seg4
            else:
                operator = seg4
                version = parts[idx + 5]
            package_dir = Path(*parts[: idx + 4])
            operator = prefer_live_operator(package_dir, version, part, operator)
            return DbContext(
                component=component,
                part=part,
                package=package,
                operator=operator,
                version=version,
                model=model,
                sample_size=sample,
                part_key=part_key,
                year=year,
            )
        except (StopIteration, IndexError):
            pass

    return DbContext(
        component="OpAmp",
        part="RS622",
        package=package,
        operator="Eugene",
        version="Version_1",
        model=model,
        sample_size=sample,
        part_key=part_key,
        year=year,
    )


def family_for_component(component: str) -> str:
    """Map #Test_Database component folder to ATE family key (product class)."""
    c = (component or "").strip().lower().replace(" ", "").replace("_", "")
    if c in ("logic", "logictranslator", "logicseries"):
        return "logic"
    if c in ("level", "levelshifters", "levelshifter", "leveltranslator"):
        return "level"
    if c in (
        "opamp",
        "operationalamplifier",
        "lownoiseopamp",
        "generalopamp",
        "precisionopamp",
    ):
        return "opamp"
    if c in ("switch", "analogswitch", "analogsw"):
        return "switch"
    if c in ("lim",):
        return "switch"
    if c in ("power", "ldo", "linearregulator"):
        return "power"
    try:
        from ate.core.new_product import load_categories

        for row in load_categories():
            comp = str(row.get("component") or "").strip().lower().replace(" ", "").replace("_", "")
            if comp != c:
                continue
            fam = str(row.get("family") or "").strip()
            if row.get("live") and fam:
                return fam
            return ""
    except Exception:
        pass
    try:
        from ate.core.registry import FAMILY_ALIASES, known_families

        if c in FAMILY_ALIASES:
            return FAMILY_ALIASES[c]
        for fam in known_families():
            key = str(fam).lower().replace(" ", "").replace("_", "")
            if key == c:
                return FAMILY_ALIASES.get(fam, fam)
    except Exception:
        pass
    # Unknown / stub RUN-IC class: empty suite, never steal OpAmp.
    return ""


def load_owners() -> list[dict[str, Any]]:
    path = OWNERS_PATH
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = data.get("owners") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict) and row.get("id"):
            out.append(row)
    return out


def save_owners(rows: list[dict[str, Any]]) -> None:
    """Write owners.yaml. Does not touch #Test_Database folders."""
    payload = {"owners": list(rows)}
    body = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    OWNERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    OWNERS_PATH.write_text(_OWNERS_PREAMBLE + body, encoding="utf-8")


def upsert_owner(
    *,
    label: str,
    owner_id: str = "",
    default_family: str = "",
    default_part: str = "",
    default_component: str = "",
    default_package: str = "",
    task: str = "",
    parts: list[str] | None = None,
    update_defaults: bool = False,
) -> dict[str, Any]:
    """Append or update a person in owners.yaml. Never id=all. Never deletes folders."""
    name = str(label or "").strip()
    if not name or name.lower() == "all" or name.startswith("_"):
        raise ValueError("Person folder must be a real name (not All)")
    oid = str(owner_id or "").strip().lower() or owner_id_from_label(name)
    if oid == "all" or not _OWNER_ID_RE.match(oid):
        raise ValueError("Person id must be lowercase ascii (not All)")
    fam = str(default_family or "").strip().lower()
    part_key = str(default_part or "").strip().lower()
    component = str(default_component or "").strip()
    package = str(default_package or "").strip()
    job = str(task or "").strip()
    extra_parts = [str(p).strip().lower() for p in (parts or []) if str(p).strip()]
    if part_key and part_key not in extra_parts:
        extra_parts.append(part_key)
    rows = load_owners()
    found: dict[str, Any] | None = None
    for row in rows:
        rid = str(row.get("id") or "").lower()
        rlab = str(row.get("label") or "")
        if rid == oid or rlab.lower() == name.lower():
            found = row
            break
    if found is not None:
        if str(found.get("id") or "").lower() == "all":
            raise ValueError("All is view-only")
        if update_defaults:
            if fam:
                found["default_family"] = fam
            if part_key:
                found["default_part"] = part_key
            if component:
                found["default_component"] = component
            if package:
                found["default_package"] = package
            if job:
                found["task"] = job
            found["label"] = name
            cur_parts = [str(p).strip().lower() for p in (found.get("parts") or []) if str(p).strip()]
            for p in extra_parts:
                if p and p not in cur_parts:
                    cur_parts.append(p)
            found["parts"] = cur_parts
            save_owners(rows)
            return {"owner": found, "action": "updated", "owners": rows}
        return {"owner": found, "action": "exists", "owners": rows}
    row = {
        "id": oid,
        "label": name,
        "default_family": fam or "opamp",
        "default_part": part_key or "rs622",
        "default_component": component or "OpAmp",
        "default_package": package or "TTSOP8",
        "parts": extra_parts,
    }
    if job:
        row["task"] = job
    rows.append(row)
    save_owners(rows)
    return {"owner": row, "action": "created", "owners": rows}


def remove_owner(owner_id_or_label: str) -> dict[str, Any]:
    """Drop a person from owners.yaml only. Never deletes Version folders."""
    raw = str(owner_id_or_label or "").strip()
    if not raw or raw.lower() == "all":
        raise ValueError("Cannot remove All")
    rows = load_owners()
    keep: list[dict[str, Any]] = []
    removed: dict[str, Any] | None = None
    for row in rows:
        rid = str(row.get("id") or "").lower()
        rlab = str(row.get("label") or "")
        if rid == "all":
            keep.append(row)
            continue
        if rid == raw.lower() or rlab.lower() == raw.lower():
            removed = row
            continue
        keep.append(row)
    if removed is None:
        raise ValueError(f"No person {raw!r} in owners.yaml")
    save_owners(keep)
    return {"removed": removed, "owners": keep}


def remember_operator(
    operator: str,
    *,
    component: str = "",
    part: str = "",
    package: str = "",
    family: str = "",
    update_defaults: bool = False,
) -> str:
    """Create owners.yaml row for a new person, then return folder label."""
    raw = str(operator or "").strip()
    if not raw or raw.lower() == "all" or raw == UNASSIGNED_OPERATOR or raw.startswith("_"):
        return require_write_operator(raw)
    fam = str(family or "").strip() or family_for_component(component)
    upsert_owner(
        label=raw,
        default_family=fam,
        default_part=str(part or "").strip().lower(),
        default_component=str(component or "").strip(),
        default_package=str(package or "").strip(),
        task=str(part or "").strip().upper(),
        update_defaults=update_defaults,
    )
    return require_write_operator(raw)


def get_context() -> DbContext:
    global _active
    with _lock:
        if _active is None:
            _active = default_context()
        return _active


def set_context(
    *,
    component: Optional[str] = None,
    part: Optional[str] = None,
    package: Optional[str] = None,
    operator: Optional[str] = None,
    version: Optional[str] = None,
    model: Optional[str] = None,
    part_key: Optional[str] = None,
    year: Optional[str] = None,
    sample_size: Optional[int] = None,
) -> DbContext:
    global _active
    with _lock:
        cur = _active or default_context()
        next_part = part or cur.part
        # Derive part_key from part name when yaml exists (rs29511 / rs1g08 / rs622)
        if part_key:
            pk = part_key
        else:
            candidate = str(next_part or "").strip().lower()
            if candidate and (PARTS_DIR / f"{candidate}.yaml").is_file():
                pk = candidate
            else:
                pk = cur.part_key
        m, pkg, sample = _model_from_part_yaml(pk)
        next_op = operator if operator is not None else cur.operator
        next_op = require_write_operator(next_op)
        ctx = DbContext(
            component=component or cur.component,
            part=next_part,
            package=package or (pkg if pk != cur.part_key else cur.package) or pkg,
            operator=next_op,
            version=version or cur.version,
            # Prefer part-yaml model when switching parts (do not keep RS622XK on Logic)
            model=model or m or cur.model,
            sample_size=int(
                sample_size
                if sample_size is not None
                else (sample if pk != cur.part_key else cur.sample_size or sample)
            ),
            part_key=pk,
            year=year if year is not None else cur.year,
        )
        # Sync identity fields from sheet_map if present.
        sm = ctx.load_sheet_map()
        if sm:
            ctx.component = str(sm.get("component") or ctx.component)
            ctx.part = str(sm.get("part") or ctx.part)
            ctx.package = str(sm.get("package") or ctx.package)
            if sm.get("operator"):
                ctx.operator = require_write_operator(str(sm.get("operator")))
            ctx.version = str(sm.get("version") or ctx.version)
            if sm.get("sample_size"):
                ctx.sample_size = int(sm["sample_size"])
        ctx.ensure_tree()
        _active = ctx
        return ctx


def list_tree(root: Optional[Path] = None) -> dict[str, Any]:
    """Scan #Test_Database into component → part → package → operator → versions."""
    base = Path(root) if root else TEST_DB_ROOT
    tree: dict[str, Any] = {"root": str(base), "components": {}}
    if not base.is_dir():
        return tree
    def _live_dirs(parent: Path, *, keep: frozenset[str] | None = None):
        keep = keep or frozenset()
        return sorted(
            p
            for p in parent.iterdir()
            if p.is_dir()
            and not p.name.startswith(".")
            and (not p.name.startswith("_") or p.name in keep)
        )

    for comp in _live_dirs(base):
        parts: dict[str, Any] = {}
        for part in _live_dirs(comp):
            if part.name.lower() == "stub":
                continue
            packages: dict[str, Any] = {}
            for pkg in _live_dirs(part):
                operators: dict[str, Any] = {}
                for child in _live_dirs(pkg, keep=frozenset({UNASSIGNED_OPERATOR})):
                    # Legacy: Package/Version_N
                    if is_campaign_dir(child) and is_version_name(child.name):
                        op_key = UNASSIGNED_OPERATOR
                        ops = operators.setdefault(op_key, {"versions": []})
                        if child.name not in ops["versions"]:
                            ops["versions"].append(child.name)
                        continue
                    # New: Package/Operator/Version_N
                    versions: list[str] = []
                    for ver in sorted(p for p in child.iterdir() if p.is_dir()):
                        if is_campaign_dir(ver):
                            versions.append(ver.name)
                    if versions or is_campaign_dir(child):
                        operators[child.name] = {"versions": versions}
                packages[pkg.name] = {"operators": operators}
            parts[part.name] = {"packages": packages}
        tree["components"][comp.name] = {"parts": parts}
    return tree


def find_campaign_root(
    component: str,
    part: str,
    package: str,
    version: str = "Version_1",
    *,
    operator: Optional[str] = None,
    base: Optional[Path] = None,
) -> Optional[Path]:
    """Prefer Package/Operator/Version; fall back to legacy Package/Version."""
    root = Path(base) if base else TEST_DB_ROOT
    pkg = root / component / part / package
    if operator:
        try:
            op = require_write_operator(operator)
        except ValueError:
            op = str(operator)
        cand = pkg / op / version
        if cand.is_dir():
            return cand
    # Any operator folder that owns this version
    if pkg.is_dir():
        for child in sorted(pkg.iterdir()):
            if not child.is_dir() or is_version_name(child.name):
                continue
            cand = child / version
            if cand.is_dir():
                return cand
        legacy = pkg / version
        if legacy.is_dir():
            return legacy
    return None



def list_test_folders(ctx: Optional[DbContext] = None) -> list[dict[str, Any]]:
    ctx = ctx or get_context()
    sm = ctx.load_sheet_map()
    tests = sm.get("tests") or {}
    rows: list[dict[str, Any]] = []
    if isinstance(tests, dict):
        for key, entry in tests.items():
            if not isinstance(entry, dict):
                continue
            folder = str(entry.get("folder") or key)
            rows.append(
                {
                    "key": key,
                    "folder": folder,
                    "excel_sheet": entry.get("excel_sheet"),
                    "fixture_mode": entry.get("fixture_mode"),
                    "automated": bool(entry.get("automated", False)),
                    "dut_iterations": int(entry.get("dut_iterations") or ctx.sample_size),
                    "path": str(ctx.test_folder(folder)),
                    "photo_path": ctx.photo_preview(folder, 1),
                }
            )
    return rows


def artifact_name(
    test_key: str,
    dut_index: int,
    variant: str,
    *,
    timestamp: Optional[str] = None,
    ext: str = "jpg",
) -> str:
    ts = timestamp or datetime.now(MYT).strftime("%Y-%m-%d_%H%M%S")
    return f"{test_key}_{int(dut_index)}_{variant}_{ts}.{ext.lstrip('.')}"


def begin_session(
    params: dict[str, Any],
    *,
    instrument_map: Optional[dict[str, str]] = None,
    fixture_plan: Optional[list[dict[str, Any]]] = None,
) -> RunSession:
    global _current_session
    ctx = get_context()
    ctx.ensure_tree()
    ts = datetime.now(MYT).strftime("%Y-%m-%d_%H%M%S")
    label = str((params or {}).get("run_label") or "").strip()
    slug = re.sub(r"[^\w\-]+", "_", label)[:48].strip("_") if label else ""
    sid = f"session_{slug}_{ts}" if slug else f"session_{ts}"
    session = RunSession(
        session_id=sid,
        started_at=datetime.now(MYT).isoformat(timespec="seconds"),
        context=ctx.identity(),
        params=dict(params or {}),
        instrument_map=dict(instrument_map or {}),
        fixture_plan=list(fixture_plan or []),
    )
    with _lock:
        _current_session = session
    _write_session(session)
    try:
        from ate.core.datalog import sync_report_from_session

        sync_report_from_session(session.to_dict())
    except Exception:
        pass
    return session


def record_step(
    test_id: str,
    *,
    success: bool,
    summary: str = "",
    error: str = "",
    fixture_mode: str = "",
    artifacts: Optional[list[dict[str, Any]]] = None,
    measurements: Optional[list[dict[str, Any]]] = None,
    dut: int | None = None,
    channel: str | None = None,
) -> None:
    stamped: list[dict[str, Any]] | None = None
    ok = bool(success)
    if measurements:
        from ate.core.specs import any_fail, enrich_measurement, load_part_specs

        pk = str(get_context().part_key or "")
        overlay = get_context().load_test_params()
        specs = load_part_specs(pk, overlay=overlay)
        stamped = [
            enrich_measurement(dict(m), specs=specs, test_id=test_id)
            for m in measurements
            if isinstance(m, dict)
        ]
        if any_fail(stamped):
            ok = False
    with _lock:
        session = _current_session
        if session is None:
            return
        row: dict[str, Any] = {
            "test_id": test_id,
            "success": ok,
            "summary": summary,
            "error": error,
            "fixture_mode": fixture_mode,
            "at": datetime.now(MYT).isoformat(timespec="seconds"),
        }
        if dut is not None:
            row["dut"] = int(dut)
        if channel:
            row["channel"] = str(channel).strip().upper()
        if stamped:
            row["measurements"] = stamped
        session.steps.append(row)
        if artifacts:
            session.artifacts.extend(artifacts)
        snap = session
    _write_session(snap)
    try:
        from ate.core.datalog import sync_report_from_session

        sync_report_from_session(snap.to_dict())
    except Exception:
        pass


def end_session(status: str = "completed") -> Optional[Path]:
    global _current_session
    with _lock:
        session = _current_session
        if session is None:
            return None
        session.finished_at = datetime.now(MYT).isoformat(timespec="seconds")
        session.status = status
        _current_session = None
        snap = session
    path = _write_session(snap)
    try:
        from ate.core.datalog import archive_report, sync_report_from_session

        sync_report_from_session(snap.to_dict())
        archive_report(snap.to_dict())
    except Exception:
        pass
    try:
        from ate.reporting.session_paste import paste_session_photos

        paste_session_photos(snap.to_dict())
    except Exception:
        pass
    try:
        from ate.reporting.session_values import fill_workbook_from_report

        fill_workbook_from_report(ctx=get_context())
    except Exception:
        pass
    try:
        from ate.reporting.golden_workbook import check_golden_workbook

        check_golden_workbook(fix=False)
    except Exception:
        pass
    return path


def current_session() -> Optional[dict[str, Any]]:
    with _lock:
        return None if _current_session is None else _current_session.to_dict()


def _write_session(session: RunSession) -> Path:
    ctx = get_context()
    dest_dir = ctx.sessions_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{session.session_id}.json"
    path.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")
    return path


def how_to_use() -> dict[str, Any]:
    """Operator-facing orientation: where we are, where photos go, how Excel links."""
    ctx = get_context()
    return {
        "heading": "ATE <-> #Test_Database orchestration",
        "tree": (
            f"{ctx.component} / {ctx.part} / {ctx.package} / {ctx.operator} / {ctx.version} "
            f"(model {ctx.model}, sample_size={ctx.sample_size})"
        ),
        "root": str(ctx.root()),
        "axes": {
            "component": "Family under #Test_Database (OpAmp, Logic, AnalogSwitch, …)",
            "part": "Device under test folder name (RS622)",
            "package": "Package variant (TTSOP8)",
            "operator": "Person folder (Eugene / Ariff / …). All is view-only.",
            "version": "Characterization campaign Version_N (not calendar year)",
            "year": "Optional metadata on the run session only",
            "config": "Fixture / gain mode (BUFFER, G11, G_NEG100 general; G201/G1001 = VOS research only)",
            "model": "Datasheet / lab-report model name (RS622XK)",
        },
        "photos": {
            "pattern": "{TEST}_{DUT}_{VARIANT}_{YYYY-MM-DD_HHMMSS}.jpg",
            "location": str(ctx.root() / "{TestKey}" / "DUT_N" / "screenshots"),
            "example": ctx.photo_preview("ORT", 1),
            "excel_link": str(ctx.sheet_map_path()),
        },
        "excel": {
            "lab_report": str(ctx.lab_report_path()),
            "mcp": "user-excel (excel_describe_sheets / excel_read_sheet / …)",
            "note": "sheet_map.yaml maps each test folder → Excel sheet + paste anchors",
        },
        "sessions": {
            "folder": str(ctx.sessions_dir()),
            "note": "Each START writes session_YYYY-MM-DD_HHMMSS.json with full identity + results",
        },
        "orchestration": [
            "1. Select Component / Part / Package / Version in Setup",
            "2. Discover → Open Session (instruments)",
            "3. Select tests — runner batches by fixture mode",
            "4. Operator Continue only when board/config must change",
            "5. Photos land under DUT_N/screenshots with parseable names",
            "6. ORT (and later other tests) paste into lab report via sheet_map anchors",
            "7. Session JSON records who/what/where for every run",
            "8. Results -> Run ledger lists those JSON files for every operator on this SKU",
            "9. Central tree is #Test_Database (SharePoint/OneDrive sync that folder; A13 MCP stays parked)",
        ],
    }
