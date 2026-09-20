/* Liquid-glass ATE — Test Database + live timeline (DUT / config Continue) */
const RPC = "http://127.0.0.1:8766";
let pendingPrompt = null;
let gateQueue = [];
let runPollActive = false;
let sessionOpen = false;
let activeFamily = "opamp";
let fixtureCatalog = [];
let dbTree = { components: {} };
let dbContext = null;
let lastTimeline = null;
let lastScrollId = "";
let allTests = [];
let substepState = {};
let activeSubstepTestId = "";

async function rpc(method, params = {}) {
  const res = await fetch(RPC, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: Date.now(), method, params }),
  });
  const text = await res.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    if (res.status === 501) {
      throw new Error("Worker :8766 is JSON-RPC POST. Open UI at http://127.0.0.1:5174");
    }
    throw new Error(`Worker HTTP ${res.status}: ${text.slice(0, 160)}`);
  }
  if (body.error) throw new Error(body.error.message || JSON.stringify(body.error));
  return body.result;
}

function $(id) { return document.getElementById(id); }

let knownFamilies = ["opamp", "logic", "level", "switch", "power"];
let familyLabels = { opamp: "OpAmp", logic: "Logic", level: "Level", switch: "Analog SW", power: "Power" };
let railType = "opamp";

const FAMILY_UI = {
  opamp: { brand: "OpAmp ATE", kicker: "Operator console" },
  logic: { brand: "Logic ATE", kicker: "Operator console" },
  switch: { brand: "Analog Switch ATE", kicker: "Operator console" },
  lim: { brand: "Analog Switch ATE", kicker: "Operator console" },
  level: { brand: "Level ATE", kicker: "Level Shifters" },
  power: { brand: "Power ATE", kicker: "LDO / Linear Regulator" },
};

function familyMeta(family) {
  if (!family) return { brand: "ATE", kicker: "Stub — no suite yet" };
  if (FAMILY_UI[family]) return FAMILY_UI[family];
  const nice = (familyLabels[family] || String(family || "ATE")).replace(/_/g, " ");
  return { brand: `${nice} ATE`, kicker: "Imported family" };
}

function renderFamilyRail(known, labels) {
  const rail = document.querySelector(".family-rail");
  if (!rail) return;
  if (Array.isArray(known) && known.length) knownFamilies = known.slice();
  if (labels && typeof labels === "object") {
    familyLabels = { ...familyLabels, ...labels };
  }
  const builtins = new Set(["opamp", "logic", "level", "switch", "power"]);
  rail.querySelectorAll(".family-btn[data-extra='1']").forEach((el) => el.remove());
  (known || []).forEach((fam) => {
    if (fam === "lim") return;
    if (rail.querySelector(`.family-btn[data-family="${fam}"]`)) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "family-btn";
    btn.dataset.family = fam;
    btn.dataset.extra = "1";
    btn.textContent = familyLabels[fam] || fam;
    if (builtins.has(fam)) {
      const powerBtn = rail.querySelector('.family-btn[data-family="power"]');
      if (powerBtn) rail.insertBefore(btn, powerBtn);
      else rail.appendChild(btn);
    } else {
      rail.appendChild(btn);
    }
  });
}

function paintBrand(family) {
  const meta = familyMeta(family);
  const title = $("brand-title");
  if (title) title.textContent = meta.brand;
  const kicker = document.querySelector(".brand-kicker");
  if (kicker) kicker.textContent = meta.kicker;
  document.querySelectorAll(".family-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.family === family);
  });
}

function updateFamilyChrome(family) {
  activeFamily = family == null ? "opamp" : family;
  if (activeFamily && activeFamily !== "lim") railType = activeFamily;
  paintBrand(railType);
  paintInventory(railType);
  if ($("np-category")) {
    const catId = typeForFamily(railType);
    if (catId) $("np-category").value = catId;
  }
  const gainPanel = $("panel-gain-boards");
  if (gainPanel) gainPanel.classList.toggle("hidden", activeFamily !== "opamp");
}

async function syncFamilyFromWorker() {
  const res = await rpc("get_family");
  renderFamilyRail(res.known || [], res.labels || {});
  updateFamilyChrome(res.family || "opamp");
  return activeFamily;
}

async function switchFamily(family) {
  if (!family || family === activeFamily) return activeFamily;
  const res = await rpc("set_family", { family });
  updateFamilyChrome(res.family || family);
  await loadFixtureCatalog();
  await loadTests();
  await loadParamDefaults();
  log(`Family switched: ${activeFamily}\n`);
  return activeFamily;
}

function familyFromComponent(component) {
  const c = String(component || "").trim().toLowerCase().replace(/[\s_]/g, "");
  if (c === "logic") return "logic";
  if (c === "level") return "level";
  if (c === "opamp") return "opamp";
  if (c === "switch" || c === "analogswitch" || c === "analogsw" || c === "lim") return "switch";
  if (c === "power" || c === "ldo" || c === "linearregulator") return "power";
  const hit = knownFamilies.find((f) => String(f).toLowerCase().replace(/[\s_]/g, "") === c);
  if (hit) return hit;
  if (!c) return "opamp";
  return "";
}

function componentFromFamily(family) {
  const labels = { opamp: "OpAmp", logic: "Logic", switch: "AnalogSwitch", lim: "AnalogSwitch", level: "Level", power: "Power" };
  if (labels[family]) return labels[family];
  const comps = Object.keys(dbTree.components || {});
  return comps.find((c) => c.toLowerCase() === family) || "";
}

function pickLatestVersion(vers) {
  const live = (vers || []).filter(Boolean);
  if (!live.length) return "Version_1";
  let best = live[0];
  let bestN = -1;
  for (const v of live) {
    const m = String(v).match(/Version_(\d+)/i);
    const n = m ? Number(m[1]) : 0;
    if (n >= bestN) {
      bestN = n;
      best = v;
    }
  }
  return best;
}

function syncOwnerSelectFromFolder(label) {
  const el = $("owner-select");
  if (!el || !label) return;
  const want = String(label).trim();
  const row = ownersList.find((o) => {
    if (!o || o.id === "all") return false;
    return (o.label || "") === want || String(o.id || "").toLowerCase() === want.toLowerCase();
  });
  if (!row) return;
  if (el.value !== row.id) {
    el.value = row.id;
    saveOwner(row.id);
  }
}

function campaignKnown(sel) {
  const partsObj = ((dbTree.components || {})[sel.component] || {}).parts || {};
  if (!sel.part || !partsObj[sel.part]) return false;
  const pkgs = (partsObj[sel.part].packages || {});
  if (!sel.package || !pkgs[sel.package]) return false;
  const ops = (pkgs[sel.package].operators || {});
  if (!sel.operator || sel.operator === "_unassigned" || !ops[sel.operator]) return false;
  return !!(sel.version && (ops[sel.operator].versions || []).includes(sel.version));
}

function pickLiveOperator(operators, prefer) {
  const list = Array.isArray(operators) ? operators.filter(Boolean) : [];
  const live = list.filter((o) => o !== "_unassigned");
  if (prefer && live.includes(prefer)) return prefer;
  if (live.length) return live[0];
  return list[0] || prefer || "Eugene";
}

function firstCampaignInComponent(component) {
  const partsObj = ((dbTree.components || {})[component] || {}).parts || {};
  const parts = liveKeys(partsObj);
  if (!parts.length) return null;
  const part = parts[0];
  const pkgsObj = (partsObj[part] || {}).packages || {};
  const packages = liveKeys(pkgsObj);
  const pkg = packages[0] || "";
  const opsObj = (pkgsObj[pkg] || {}).operators || {};
  const operators = Object.keys(opsObj).filter((k) => k && !k.startsWith(".") && k !== "_unassigned");
  const prefer = writeOperatorLabel();
  const op = pickLiveOperator(operators, prefer);
  const versions = (opsObj[op] || {}).versions || [];
  return {
    component,
    part,
    package: pkg,
    operator: op,
    version: pickLatestVersion(versions),
    model: "",
    year: ($("db-year") && $("db-year").value) || "2026",
  };
}

const OWNER_KEY = "ate_operator";
let ownersList = [];

function readSavedOwner() {
  try {
    return localStorage.getItem(OWNER_KEY) || "eugene";
  } catch (_) {
    return "eugene";
  }
}

function saveOwner(id) {
  try {
    localStorage.setItem(OWNER_KEY, id);
  } catch (_) { /* ignore */ }
}

async function loadOwners() {
  const el = $("owner-select");
  if (!el) return;
  try {
    const res = await rpc("list_owners");
    ownersList = res.owners || [];
  } catch (_) {
    ownersList = [];
  }
  const cur = readSavedOwner();
  el.innerHTML = ownersList.map((o) => {
    const sel = o.id === cur ? "selected" : "";
    return `<option value="${o.id}" ${sel}>${o.label}</option>`;
  }).join("");
  if (!el.value && ownersList[0]) el.value = ownersList[0].id;
  el.onchange = async () => {
    saveOwner(el.value);
    try {
      await applyOwner(el.value);
    } catch (e) {
      alert(e.message);
    }
  };
}

async function applyOwner(id) {
  const row = ownersList.find((o) => o.id === id);
  if (!row || id === "all") return;
  const part = String(row.default_part || "").toUpperCase();
  const label = row.label || id;
  let folder = label;
  let pkg = row.default_package || "";
  const inv = (inventoryRows || []).find((r) => String(r.part || "").toUpperCase() === part);
  const picFolder = inv ? operatorFromPic(inv.pic) : "";
  if (picFolder) folder = picFolder;
  const partsObj = ((dbTree.components || {})[row.default_component] || {}).parts || {};
  const pkgsObj = (partsObj[part] || {}).packages || {};
  const diskPkgs = liveKeys(pkgsObj).filter((p) => {
    const ops = (pkgsObj[p] || {}).operators || {};
    return ops[folder];
  });
  if (diskPkgs.length) {
    if (!diskPkgs.includes(pkg)) pkg = diskPkgs[0];
  } else if (inv && inv.package) {
    pkg = inv.package;
  }
  const vers = versionsForSel({
    component: row.default_component,
    part,
    package: pkg,
    operator: folder,
  });
  paintCampaign({
    component: row.default_component,
    part,
    package: pkg,
    operator: folder,
    version: pickLatestVersion(vers),
    model: part,
    year: ($("db-year") && $("db-year").value) || "2026",
  });
  await applyDb();
  log(`Operator ${label}: ${row.default_component} / ${part} / ${folder}\n`);
}

function writeOperatorLabel() {
  const id = ($("owner-select") && $("owner-select").value) || readSavedOwner();
  if (!id || id === "all") return "";
  const row = ownersList.find((o) => o.id === id);
  return (row && row.label) || id;
}

function requireWriteOperator() {
  const header = ($("owner-select") && $("owner-select").value) || "";
  if (header === "all") {
    throw new Error("Pick a person operator (not All) before writing folders / DEMO / START");
  }
  const label = ($("db-operator") && $("db-operator").value) || writeOperatorLabel();
  if (!label || label === "All" || label === "all" || label === "_unassigned") {
    throw new Error("Pick a person operator (not All) before writing folders / DEMO / START");
  }
  return label;
}

let inventoryRows = [];
let categoryRows = [];
let campaignLabels = [];
let labelKindVocab = [];
let labelValueVocab = {};

function typeForFamily(family) {
  if (family === "switch" || family === "lim") return "analog_switch";
  return family || "";
}

function suiteForRow(row) {
  const suite = String((row && row.ate_suite) || "").trim();
  if (suite) return suite;
  const cat = categoryRows.find((c) => c.id === ((row && row.category) || ""));
  if (cat && cat.live && cat.family) return cat.family;
  return "";
}

function paintInventory(type) {
  const el = $("inv-select");
  if (!el) return;
  const want = typeForFamily(type || railType);
  const rows = inventoryRows.map((r, i) => ({ r, i })).filter(({ r }) => {
    if (!want) return true;
    return String(r.category || "") === want;
  });
  const nice = familyLabels[type || railType] || type || railType || "SKU";
  el.innerHTML = `<option value="">-- pick a ${nice} --</option>` + rows.map(({ r, i }) => {
    const st = r.status || "";
    const lot = r.lot || "";
    const klass = r.sheet_class || r.category || "";
    const bits = [r.part, klass, r.model || "", r.package || "", lot, st].filter(Boolean);
    return `<option value="${i}">${bits.join(" · ")}</option>`;
  }).join("");
  const hint = $("inv-type-hint");
  if (hint) {
    hint.textContent = `${rows.length} ${nice} SKU(s) on the tracking sheet.`;
  }
}

async function loadCategories() {
  const el = $("np-category");
  if (!el) return;
  try {
    const res = await rpc("list_categories");
    categoryRows = res.categories || [];
  } catch (_) {
    categoryRows = [];
  }
  el.innerHTML = categoryRows.map((c) => {
    const tag = c.live ? "" : " (stub)";
    return `<option value="${c.id}">${c.run_ic || c.id}${tag}</option>`;
  }).join("");
  el.onchange = async () => {
    const row = categoryRows.find((c) => c.id === el.value);
    if (!row) return;
    const comp = row.component || "";
    if ($("db-component") && comp) {
      const comps = Object.keys(dbTree.components || {});
      if (comps.includes(comp)) $("db-component").value = comp;
    }
    if (row.live && row.family) {
      try {
        railType = row.family === "switch" ? "switch" : (row.id === "analog_switch" ? "switch" : (row.family || railType));
        paintInventory(railType);
        await switchFamily(row.family);
      } catch (e) {
        log(`Category family: ${e.message}\n`);
      }
    } else {
      log(`RUN-IC class ${row.run_ic || row.id} is stub -- folders only, no suite.\n`);
    }
  };
}

async function loadInventory() {
  const el = $("inv-select");
  if (!el) return;
  try {
    const res = await rpc("list_inventory");
    inventoryRows = res.parts || [];
  } catch (_) {
    inventoryRows = [];
  }
  paintInventory(railType);
  el.onchange = () => {
    const row = inventoryRows[Number(el.value)];
    if (!row) return;
    if ($("np-category")) {
      // Tracking-sheet class only. ate_suite must not steal Level Shifters -> Logic.
      $("np-category").value = row.category || "opamp";
    }
    if ($("np-part")) $("np-part").value = row.part || "";
    if ($("np-package")) $("np-package").value = row.package || "";
    if ($("np-model")) $("np-model").value = row.model || row.part || "";
    const qty = Number(row.qty);
    if ($("np-sample") && Number.isFinite(qty) && qty >= 1) {
      $("np-sample").value = String(Math.trunc(qty));
    }
    const suite = String(row.ate_suite || "").trim();
    const cat = categoryRows.find((c) => c.id === (row.category || ""));
    if (suite) {
      log(`Tracking class: ${row.sheet_class || row.category}. Live suite: ${suite}.\n`);
      switchFamily(suite).catch((e) => log(`ate_suite: ${e.message}\n`));
    } else if (cat && cat.live && cat.family) {
      switchFamily(cat.family).catch((e) => log(`Category family: ${e.message}\n`));
    } else if (cat) {
      log(`RUN-IC class ${cat.run_ic || cat.id} is stub -- folders only, no suite.\n`);
    }
  };
}

function log(text) {
  const el = $("log");
  if (!el) return;
  el.textContent += text;
  if (el.textContent.length > 80000) {
    el.textContent = el.textContent.slice(-40000);
  }
  el.scrollTop = el.scrollHeight;
}

function setTiles(mapping) {
  document.querySelectorAll(".tile").forEach((t) => {
    const k = t.dataset.k;
    t.classList.toggle("on", !!(mapping && mapping[k]));
    t.classList.toggle("off", !(mapping && mapping[k]));
  });
}

async function loadMappedCoverage() {
  const el = $("setup-map-hint");
  if (!el) return;
  try {
    const c = await rpc("mapped_coverage");
    const miss = c.missing_specs || [];
    const dmm = c.dmm ? "DMM found" : "DMM not in Discover (VOL / Logic IDD need it at run)";
    el.textContent = miss.length
      ? `Map coverage FAIL: ${miss.join(", ")}`
      : (!c.n_map
        ? `Map coverage empty: no sheet_map tests at ${c.sheet_map || "this campaign"}. ${dmm}`
        : `Map coverage OK: ${c.n_map} sheet_map tests registered. ${dmm}`);
  } catch (e) {
    el.textContent = `Map coverage: ${e.message}`;
  }
}

function setRunPill(mode) {
  const el = $("header-bin");
  if (!el) return;
  const map = {
    ready: "READY",
    running: "RUNNING",
    run: "RUN",
    wait: "WAIT",
    pass: "PASS",
    fail: "FAIL",
    stopping: "STOPPING",
  };
  el.textContent = map[mode] || String(mode).toUpperCase();
  el.className = "run-pill " + (mode || "ready");
}

async function syncRunState() {
  try {
    const st = await rpc("session_status");
    if (st.busy || runPollActive) {
      if ($("header-bin")?.classList.contains("stopping")) return;
      setRunPill("running");
    } else if (pendingPrompt) {
      setRunPill("wait");
    } else if ($("header-bin")?.textContent === "STOPPING") {
      setRunPill("ready");
    }
    return st;
  } catch (_) {
    return null;
  }
}

function switchPage(name) {
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  $(`page-${name}`).classList.add("active");
  document.querySelector(`.tab[data-page="${name}"]`).classList.add("active");
  if (name === "results") {
    loadLayoutPreview().catch(() => {});
    loadRunLedger().catch(() => {});
  }
}

function selectedDuts() {
  const picked = [...document.querySelectorAll(".dut-cb:checked")].map((c) => Number(c.value));
  if (picked.length) return picked.sort((a, b) => a - b);
  return [Number($("unit").value) || 1];
}

function selectedChannels() {
  const order = ["CHA", "CHB"];
  const picked = [...document.querySelectorAll(".ch-cb:checked")].map((c) => c.value.toUpperCase());
  if (!picked.length) return ["CHA"];
  // Always Channel A pass (all DUTs) before Channel B
  return order.filter((c) => picked.includes(c));
}

let paramCatalog = { tests: {}, gain_profiles: {}, psu_golden: {}, gbw_steps: [], gbw_run_labels: {}, controls: [], sample_size: 4 };

function isManualMode() {
  return $("manual-mode") && $("manual-mode").checked;
}

function condNum(id, fallback) {
  const el = $(`cond-${id}`);
  if (!el) return fallback;
  const n = Number(el.value);
  return Number.isFinite(n) ? n : fallback;
}

function catalogControlValues() {
  const extra = {};
  for (const c of paramCatalog.controls || []) {
    const id = c && c.id;
    if (!id) continue;
    const el = $(`cond-${id}`);
    if (!el) continue;
    const raw = el.value;
    if (raw === "" || raw == null) continue;
    const n = Number(raw);
    extra[id] = Number.isFinite(n) && String(raw).trim() !== "" && !/^[a-zA-Z]/.test(String(raw))
      ? n
      : raw;
  }
  return extra;
}

function benchValues() {
  const d = mergeTestDefaults(selectedTests());
  const extra = catalogControlValues();
  if (activeFamily !== "opamp") {
    const out = {
      vcc: condNum("vcc", d.vcc),
      n_repeats: d.n_repeats,
      ...extra,
    };
    if (logicStimulus() !== "PSU_MSO") {
      out.freq_hz = d.freq_hz;
      out.amp_vpp = d.amp_vpp;
      if (isManualMode() && $("freq")) {
        out.freq_hz = Number($("freq").value);
        out.amp_vpp = Number($("amp").value);
        out.n_repeats = Number($("repeats").value);
      }
    } else if (isManualMode() && $("repeats")) {
      out.n_repeats = Number($("repeats").value);
    }
    const vccb = extra.vccb != null ? extra.vccb : condNum("vccb", d.vccb);
    if (vccb != null && Number.isFinite(Number(vccb))) out.vccb = Number(vccb);
    return out;
  }
  if (isManualMode()) {
    return {
      vcc: Number($("vcc").value),
      freq_hz: Number($("freq").value),
      amp_vpp: Number($("amp").value),
      n_repeats: Number($("repeats").value),
    };
  }
  return {
    vcc: d.vcc,
    freq_hz: d.freq_hz,
    amp_vpp: d.amp_vpp,
    n_repeats: d.n_repeats,
  };
}

function params() {
  const duts = selectedDuts();
  const channels = selectedChannels();
  const bench = benchValues();
  const ids = selectedTests();
  const gbwOn = ids.includes("gbw");
  const profileKey = (gbwOn && $("gain-profile") && $("gain-profile").value) || "default";
  const labels = paramCatalog.gbw_run_labels || {};
  const runLabel = gbwOn
    ? (($("run-label") && $("run-label").value.trim()) || labels[profileKey] || "")
    : "";
  if ($("unit")) $("unit").value = String(duts[0] || 1);
  const out = {
    ...bench,
    unit_index: duts[0],
    dut_indices: duts,
    channels: channels,
    channel: channels[0],
    reset_before_run: $("reset") ? $("reset").checked : false,
    part: (dbContext && dbContext.part_key) || "rs622",
    year: $("db-year").value || undefined,
    run_label: runLabel,
    gain_profile: gbwOn ? profileKey : "default",
    current_limit_a: (paramCatalog.psu_golden && paramCatalog.psu_golden.current_limit_a) || 0.1,
  };
  return out;
}

function selectedTests() {
  return [...document.querySelectorAll("#test-list .test-item input[type=checkbox]:checked")].map((i) => i.value);
}

function mergeTestDefaults(ids) {
  const out = {
    vcc: 5.0,
    freq_hz: 500,
    amp_vpp: 0.004,
    n_repeats: 3,
    channels: ["CHA"],
  };
  const channelUnion = new Set();
  for (const id of ids) {
    const d = paramCatalog.tests[id];
    if (!d) continue;
    Object.assign(out, d);
    if (d.channels) {
      for (const c of d.channels) channelUnion.add(String(c).toUpperCase());
    }
  }
  if (channelUnion.size) {
    out.channels = ["CHA", "CHB"].filter((c) => channelUnion.has(c));
  }
  return out;
}

function applyTestDefaults(force) {
  const ids = selectedTests();
  const manual = isManualMode();
  if ($("param-advanced")) $("param-advanced").classList.toggle("hidden", !manual);
  if (!ids.length) {
    if ($("param-active-hint")) $("param-active-hint").textContent = "Select tests — standard defaults apply.";
    renderRunPlans();
    return;
  }
  const d = mergeTestDefaults(ids);
  if ((force || !isManualMode()) && $("vcc")) {
    $("vcc").value = d.vcc;
    if ($("freq")) $("freq").value = d.freq_hz;
    if ($("amp")) $("amp").value = d.amp_vpp;
    if ($("repeats")) $("repeats").value = d.n_repeats;
    delete $("vcc").dataset.userEdited;
  }
  if (ids.includes("gbw") && d.gain_profile && $("gain-profile")) {
    $("gain-profile").value = d.gain_profile;
    syncGainProfileHint(force);
  }
  const chans = selectedChannels().join("+");
  if ($("param-advanced")) $("param-advanced").classList.toggle("hidden", !manual);
  if ($("param-active-hint")) {
    $("param-active-hint").textContent = manual
      ? `Manual — ${ids.join(", ")} · ${chans}`
      : `${ids.join(", ")} · ${chans} — pick tests / corners above · expand run plan below`;
  }
  renderRunPlans();
}

function fillGainProfiles(rows) {
  const sel = $("gain-profile");
  if (!sel) return;
  sel.innerHTML = (rows || [])
    .map(
      (r) =>
        `<option value="${r.key}">${r.label || r.key} — RF=${r.rf} RI=${r.ri} gain=${r.gain}</option>`
    )
    .join("");
}

function syncGainProfileHint(setLabel) {
  const key = $("gain-profile") && $("gain-profile").value;
  const rows = (paramCatalog.gain_profiles && paramCatalog.gain_profiles.G11) || [];
  const row = rows.find((r) => r.key === key);
  const labels = paramCatalog.gbw_run_labels || {};
  const autoLabel = labels[key] || (row && row.label) || key || "";
  if ($("run-label")) {
    if (setLabel || !$("run-label").dataset.userEdited) {
      $("run-label").value = autoLabel;
    }
  }
  if ($("gbw-plan-title")) {
    $("gbw-plan-title").textContent = autoLabel || "GBW run";
  }
  if (row && $("gain-profile-hint")) {
    $("gain-profile-hint").textContent =
      `RF=${row.rf} RI=${row.ri} gain=${row.gain} — board must match before Continue.`;
  }
  renderRunPlans();
}

function planStepsForTest(t) {
  if (t.fixed_steps && t.fixed_steps.length) return t.fixed_steps;
  if (t.id === "gbw") {
    const steps = paramCatalog.gbw_steps || [];
    if (steps.length) return steps;
  }
  return [{ id: "run", label: "Run / capture", phase: "measure" }];
}

function sortTestsForPlan(tests) {
  const modeRank = new Map(
    (fixtureCatalog || []).map((m, i) => [m.mode, i])
  );
  const within = new Map();
  for (const m of fixtureCatalog || []) {
    (m.tests || []).forEach((id, i) => within.set(id, i));
  }
  return [...tests].sort((a, b) => {
    const ra = modeRank.has(a.fixture_mode) ? modeRank.get(a.fixture_mode) : 99;
    const rb = modeRank.has(b.fixture_mode) ? modeRank.get(b.fixture_mode) : 99;
    if (ra !== rb) return ra - rb;
    const wa = within.has(a.id) ? within.get(a.id) : 99;
    const wb = within.has(b.id) ? within.get(b.id) : 99;
    if (wa !== wb) return wa - wb;
    return String(a.id).localeCompare(String(b.id));
  });
}

function gbwPlanExtrasHtml() {
  const profileKey = ($("gain-profile") && $("gain-profile").value) || "default";
  const rows = (paramCatalog.gain_profiles && paramCatalog.gain_profiles.G11) || [];
  const row = rows.find((r) => r.key === profileKey) || {};
  const runLabel = ($("run-label") && $("run-label").value) || profileKey;
  let opts = rows
    .map(
      (r) =>
        `<option value="${r.key}"${r.key === profileKey ? " selected" : ""}>${r.label || r.key} — RF=${r.rf} RI=${r.ri}</option>`
    )
    .join("");
  if (!opts) {
    opts = `<option value="default" selected>Std G11 — RI=1k RF=10k</option>`;
  }
  const manual = isManualMode();
  const rf = row.rf || "10k";
  const ri = row.ri || "1k";
  return {
    summarySuffix: `G11 locked (RF=${rf} RI=${ri}) · <span id="gbw-plan-title">${runLabel}</span>`,
    bodyPrefix: `
      <input type="hidden" id="run-label" value="${runLabel}" />
      <input type="hidden" id="gain-profile" value="${profileKey}" />
      ${manual ? `<label>Alt network (manual only)
        <select id="gain-profile-manual">${opts}</select>
      </label><p class="hint" id="gain-profile-hint">Must match soldered RF/RI before Continue.</p>` : `<p class="hint" id="gain-profile-hint">Gain 11 locked to G11 board · 50 mVpp @ 1 kHz → sweep to Vout×0.707</p>`}`,
  };
}

function renderOneTestPlan(t, duts, channels) {
  const tag = t.short_tag || t.id;
  const mode = t.fixture_mode || "";
  const instr = (t.required_instruments || []).join("+") || "MSO+PSU+AWG";
  const steps = planStepsForTest(t);
  const dual = t.dual_channel !== false;
  const chans = dual ? channels : [channels[0] || "CHA"];
  let extras = null;
  if (t.id === "gbw") extras = gbwPlanExtrasHtml();
  const summaryCore = extras
    ? `${tag} — ${extras.summarySuffix}`
    : `${tag} — ${t.label} · ${mode} · ${instr}`;
  let html = `<details class="test-plan-details test-plan-collapsible" data-test-id="${t.id}">
    <summary>${summaryCore}</summary>
    <div class="test-plan-body">`;
  if (extras) html += extras.bodyPrefix;
  else if (t.notes) html += `<p class="hint">${t.notes}</p>`;
  for (const ch of chans) {
    const chName = ch === "CHA" ? "Ch A" : ch === "CHB" ? "Ch B" : ch;
    html += `<details class="test-plan-nest">
      <summary>${chName} · all DUTs</summary>
      <div class="test-plan-body">`;
    for (const dut of duts) {
      html += `<details class="test-plan-nest test-plan-nest-dut">
        <summary>DUT ${dut} · ${chName}</summary>
        <div class="test-plan-body"><div class="slew-plan-grid">`;
      for (const step of steps) {
        html += `<div class="slew-step-chip" data-test="${t.id}" data-dut="${dut}" data-ch="${ch}" data-step="${step.id}" data-phase="${step.phase || ""}">${step.label}</div>`;
      }
      html += `</div></div></details>`;
    }
    html += `</div></details>`;
  }
  html += `</div></details>`;
  return html;
}

function renderRunPlans() {
  const box = $("test-plans");
  if (!box) return;
  const ids = selectedTests();
  const picked = sortTestsForPlan(
    ids.map((id) => allTests.find((t) => t.id === id)).filter(Boolean)
  );
  if (!picked.length) {
    box.innerHTML = "";
    return;
  }
  const duts = selectedDuts();
  const channels = selectedChannels();
  box.innerHTML = picked.map((t) => renderOneTestPlan(t, duts, channels)).join("");
  const sel = box.querySelector("#gain-profile-manual");
  if (sel) {
    sel.addEventListener("change", () => {
      const hidden = box.querySelector("#gain-profile");
      if (hidden) hidden.value = sel.value;
      syncGainProfileHint(true);
    });
  }
}

async function loadParamDefaults() {
  try {
    const part = (dbContext && dbContext.part_key) || "rs622";
    paramCatalog = await rpc("list_param_defaults", { part, family: activeFamily });
    if (!paramCatalog.controls) paramCatalog.controls = [];
    const ilim = Number((paramCatalog.psu_golden || {}).current_limit_a);
    const ma = Number.isFinite(ilim) ? Math.round(ilim * 1000) : 100;
    if ($("psu-golden-hint")) {
      $("psu-golden-hint").textContent =
        `PSU: Iset=${ma} mA, OVP=Vset+0.3 V, OCP=Iset+0.1 A. Photo anchors: Results → Waveform layout (sheet_map.yaml).`;
    }
    renderConditions();
    renderDutPicks();
    renderLogicDc();
    applyTestDefaults(false);
    await loadLogicDcPanel();
  } catch (_) {
    paramCatalog = { tests: {}, gain_profiles: {}, psu_golden: { current_limit_a: 0.1 }, gbw_steps: [], gbw_run_labels: {}, controls: [], sample_size: 4 };
    renderConditions();
    renderLogicDc();
    try { await loadLogicDcPanel(); } catch (_) { /* ignore */ }
  }
}

function renderConditions() {
  const panel = $("panel-run-conditions");
  const box = $("run-conditions");
  if (!panel || !box) return;
  const opamp = activeFamily === "opamp";
  panel.classList.toggle("hidden", opamp);
  if (opamp) {
    box.innerHTML = "";
    return;
  }
  const rows = paramCatalog.controls || [];
  if (!rows.length) {
    box.innerHTML = `<p class="hint">No YAML corners for this part. Tests are still checkboxes below. Add vcc_sweep_list / vcc_sweep or a controls: list in ate/config/parts.</p>`;
    return;
  }
  box.innerHTML = rows.map((c) => {
    const id = `cond-${c.id}`;
    const val = c.value != null ? c.value : "";
    const choices = c.choices || [];
    if (choices.length) {
      const have = new Set(choices.map((x) => String(x)));
      const extra = (val !== "" && !have.has(String(val)))
        ? `<option value="${val}" selected>${val}</option>`
        : "";
      const opts = extra + choices.map((x) => {
        const sel = String(x) === String(val) ? "selected" : "";
        return `<option value="${x}" ${sel}>${x}</option>`;
      }).join("");
      return `<label>${c.label}<select id="${id}">${opts}</select></label>`;
    }
    return `<label>${c.label}<input id="${id}" type="number" step="0.01" value="${val}" /></label>`;
  }).join("");
}

function prettyJson(obj) {
  try {
    return JSON.stringify(obj == null ? {} : obj, null, 2);
  } catch (_) {
    return "{}";
  }
}

async function loadLogicDcPanel() {
  const panel = $("panel-logic-dc");
  if (!panel) return;
  const part = (dbContext && dbContext.part_key) || "";
  const logicFam = activeFamily === "logic" || activeFamily === "level";
  if (!logicFam || !part) {
    panel.classList.add("hidden");
    return;
  }
  try {
    const data = await rpc("get_product_model", { part });
    const present = !!(data && data.present);
    panel.classList.toggle("hidden", !present);
    if (!present) {
      if ($("logic-dc-status")) {
        $("logic-dc-status").textContent = "No Path B product_model for this part.";
      }
      return;
    }
    const signed = !!data.greenable;
    if ($("logic-dc-status")) {
      $("logic-dc-status").textContent =
        `${data.part || part}  truth_table.status=${data.truth_table_status || "UNCONFIRMED"}  ` +
        `isolation.status=${data.isolation_status || ""}  ` +
        (signed ? "Datasheet-signed" : "not Datasheet-signed; not greenable");
    }
    const gaps = data.gaps || [];
    if ($("logic-dc-gaps")) {
      $("logic-dc-gaps").textContent = gaps.length ? `Gaps: ${gaps.join(" | ")}` : "Gaps: none listed";
    }
    if ($("logic-dc-vcc-list")) {
      $("logic-dc-vcc-list").value = (data.vcc_list || []).join(", ");
    }
    if ($("logic-dc-pass-mode")) {
      $("logic-dc-pass-mode").value = prettyJson(data.pass_mode || data.limit_mode || {});
    }
    if ($("logic-dc-truth")) {
      $("logic-dc-truth").value = prettyJson(data.truth_table || {});
    }
    if ($("logic-dc-isolation")) {
      $("logic-dc-isolation").value = prettyJson(data.isolation || {});
    }
    if ($("logic-dc-hint")) $("logic-dc-hint").textContent = "";
  } catch (e) {
    panel.classList.add("hidden");
    if ($("logic-dc-hint")) $("logic-dc-hint").textContent = String((e && e.message) || e);
  }
}

function parseCardFieldValue(field, raw, deleted) {
  if (deleted) return { deleted: true, value: null };
  const t = field.type || "text";
  const s = String(raw == null ? "" : raw).trim();
  if (t === "bool") {
    if (!s) return { deleted: true, value: null };
    const low = s.toLowerCase();
    return { deleted: false, value: low === "true" || low === "1" || low === "yes" };
  }
  if (t === "number" || t === "number_or_null") {
    if (!s || lowNull(s)) return { deleted: t === "number_or_null", value: null };
    const n = Number(s);
    if (!Number.isFinite(n)) throw new Error(`${field.key} must be a number (amps/volts as written; do not invent)`);
    return { deleted: false, value: n };
  }
  if (t === "list_csv") {
    if (!s || lowNull(s)) return { deleted: true, value: null };
    const nums = s.split(/[,\s]+/).map((x) => Number(x)).filter((n) => Number.isFinite(n));
    return { deleted: false, value: nums };
  }
  if (t === "json") {
    if (!s || lowNull(s)) return { deleted: true, value: null };
    try {
      return { deleted: false, value: JSON.parse(s) };
    } catch (e) {
      if (s === "none" || s === "true" || s === "false") {
        return { deleted: false, value: s === "none" ? "none" : s === "true" };
      }
      throw new Error(`${field.key} JSON: ${(e && e.message) || e}`);
    }
  }
  if (!s || lowNull(s)) return { deleted: true, value: null };
  return { deleted: false, value: s };
}

function lowNull(s) {
  const low = String(s || "").trim().toLowerCase();
  return low === "null" || low === "none" || low === "~";
}

function formatCardValue(field) {
  const v = field.value;
  const t = field.type || "text";
  if (v === null || v === undefined) return "";
  if (t === "json") {
    try { return JSON.stringify(v, null, 2); } catch (_) { return ""; }
  }
  if (t === "list_csv" && Array.isArray(v)) return v.join(", ");
  if (t === "bool") return v ? "true" : "false";
  return String(v);
}

function renderCardFields(fields) {
  const rows = fields || [];
  let html = "<h3 class=\"subhead\">Card fields (OOP / OCR)</h3>";
  html += "<p class=\"hint\">Each field is assignable, editable, or deletable. Save product_model writes matching <code>product_model</code> keys from <code>docs/datasheet/card_fields.schema.yaml</code>. PaddleOCR maps onto these keys. Do not install Baidu unless asked. Cannot promote Datasheet-signed. Do not invent loads or a uA epsilon.</p>";
  if (!rows.length) {
    html += "<p class=\"hint\">card_fields missing -- worker must load card_fields.schema.yaml.</p>";
    return html;
  }
  html += "<table class=\"logic-dc-table\" id=\"logic-dc-card-fields\"><thead><tr><th>Field</th><th>OOP</th><th>Value</th><th></th></tr></thead><tbody>";
  rows.forEach((f) => {
    const key = f.key || "";
    const oop = f.oop || "";
    const editable = f.editable !== false;
    const deletable = f.deletable !== false;
    const t = f.type || "text";
    const val = formatCardValue(f);
    const disabled = editable ? "" : "disabled";
    const isJson = t === "json";
    const input = isJson
      ? `<textarea class="mono-edit" data-card-field="${key}" data-card-type="${t}" rows="3" ${disabled}>${val}</textarea>`
      : `<input data-card-field="${key}" data-card-type="${t}" type="text" value="${String(val).replace(/"/g, "&quot;")}" ${disabled} />`;
    const del = (deletable && editable)
      ? `<button type="button" class="btn ghost logic-dc-del" data-delete-field="${key}">Delete</button>`
      : "";
    html += `<tr data-card-row="${key}"><td><code>${key}</code></td><td>${oop}</td><td>${input}</td><td>${del}</td></tr>`;
  });
  html += "</tbody></table>";
  return html;
}

function wireCardFieldDeletes() {
  document.querySelectorAll("[data-delete-field]").forEach((btn) => {
    btn.onclick = () => {
      const key = btn.getAttribute("data-delete-field");
      const row = document.querySelector(`[data-card-row="${key}"]`);
      if (!row) return;
      const el = row.querySelector("[data-card-field]");
      if (el) {
        el.value = "";
        el.setAttribute("data-deleted", "1");
      }
      row.setAttribute("data-deleted", "1");
    };
  });
  document.querySelectorAll("[data-card-field]").forEach((el) => {
    el.addEventListener("input", () => {
      el.removeAttribute("data-deleted");
      const row = el.closest("[data-card-row]");
      if (row) row.removeAttribute("data-deleted");
    });
  });
}

function parseJsonField(el, label) {
  const raw = (el && el.value) || "";
  try {
    return JSON.parse(raw);
  } catch (e) {
    throw new Error(`${label} JSON: ${(e && e.message) || e}`);
  }
}

async function saveLogicDcPanel() {
  const part = (dbContext && dbContext.part_key) || "";
  if (!part) throw new Error("Apply a campaign part first");
  const fields = (paramCatalog.logic_dc && paramCatalog.logic_dc.card_fields) || [];
  const byKey = {};
  fields.forEach((f) => { if (f && f.key) byKey[f.key] = f; });
  const patch = {};
  const deleted_fields = [];
  const seen = new Set();
  document.querySelectorAll("[data-card-field]").forEach((el) => {
    const key = el.getAttribute("data-card-field");
    if (!key) return;
    if (el.closest("#logic-dc-card-fields")) return;
    seen.add(key);
    const spec = byKey[key] || { key, type: el.getAttribute("data-card-type") || "text", deletable: true };
    const deleted = el.getAttribute("data-deleted") === "1";
    const parsed = parseCardFieldValue(spec, el.value, deleted);
    if (parsed.deleted) {
      patch[key] = null;
      deleted_fields.push(key);
    } else {
      patch[key] = parsed.value;
    }
  });
  document.querySelectorAll("#logic-dc-card-fields [data-card-field]").forEach((el) => {
    const key = el.getAttribute("data-card-field");
    if (!key) return;
    seen.add(key);
    const spec = byKey[key] || { key, type: el.getAttribute("data-card-type") || "text", deletable: true };
    const row = el.closest("[data-card-row]");
    const deleted = el.getAttribute("data-deleted") === "1" || (row && row.getAttribute("data-deleted") === "1");
    const parsed = parseCardFieldValue(spec, el.value, deleted);
    if (parsed.deleted) {
      patch[key] = null;
      if (!deleted_fields.includes(key)) deleted_fields.push(key);
    } else {
      patch[key] = parsed.value;
      const ix = deleted_fields.indexOf(key);
      if (ix >= 0) deleted_fields.splice(ix, 1);
    }
  });
  if ($("logic-dc-vcc-list") && !seen.has("vcc_list")) {
    const vccRaw = ($("logic-dc-vcc-list").value || "").trim();
    patch.vcc_list = vccRaw
      ? vccRaw.split(/[,\s]+/).map((x) => Number(x)).filter((n) => Number.isFinite(n))
      : [];
  }
  if ($("logic-dc-pass-mode") && !seen.has("pass_mode")) {
    patch.pass_mode = parseJsonField($("logic-dc-pass-mode"), "pass_mode");
  }
  if ($("logic-dc-truth") && !seen.has("truth_table")) {
    patch.truth_table = parseJsonField($("logic-dc-truth"), "truth_table");
  }
  if ($("logic-dc-isolation") && !seen.has("isolation")) {
    patch.isolation = parseJsonField($("logic-dc-isolation"), "isolation");
  }
  if (deleted_fields.length) patch.deleted_fields = deleted_fields;
  const res = await rpc("save_product_model", { part, patch });
  await loadLogicDcPanel();
  await loadParamDefaults();
  if ($("logic-dc-hint")) {
    $("logic-dc-hint").textContent = `Saved ${res.part || part} via card_fields.schema.yaml (status stays unless Datasheet-signed in YAML).`;
  }
}

function renderDutPicks() {
  const box = $("dut-picks");
  if (!box) return;
  const n = Math.max(1, Math.min(16, Number(paramCatalog.sample_size) || 4));
  const prev = new Set([...document.querySelectorAll(".dut-cb:checked")].map((c) => String(c.value)));
  if (!prev.size) prev.add("1");
  let html = `<span class="hint">DUTs:</span>`;
  for (let i = 1; i <= n; i += 1) {
    const checked = prev.has(String(i)) ? "checked" : "";
    html += `<label class="check"><input type="checkbox" class="dut-cb" value="${i}" ${checked} /> ${i}</label>`;
  }
  box.innerHTML = html;
}

function wirePassModeSync() {
  document.querySelectorAll(".logic-dc-mode").forEach((sel) => {
    sel.onchange = () => {
      const id = sel.getAttribute("data-id");
      if (!id) return;
      document.querySelectorAll(`.logic-dc-mode[data-id="${id}"]`).forEach((other) => {
        if (other !== sel) other.value = sel.value;
      });
    };
  });
}

function passModeSelect(sid, cur, extraClass) {
  const modes = [
    ["", "infer"],
    ["range", "range"],
    ["min-only", "min-only"],
    ["max-only", "max-only"],
    ["fail-open", "fail-open"],
    ["unspec", "unspec"],
  ];
  const c = String(cur || "").replace(/_/g, "-");
  const opts = modes.map(([v, lab]) => `<option value="${v}" ${v === c ? "selected" : ""}>${lab}</option>`).join("");
  const cls = extraClass ? `logic-dc-mode ${extraClass}` : "logic-dc-mode";
  return `<select class="${cls}" data-id="${sid}">${opts}</select>`;
}

function numOrNull(raw) {
  const t = String(raw == null ? "" : raw).trim();
  if (!t || t.toLowerCase() === "null" || t.toLowerCase() === "none") return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

function seedVccGrid(dc) {
  const g = (dc && (dc.vcc_plan || dc.vcc_grid)) || {};
  const schmitt = !!(dc && dc.schmitt) || String(g.kind || "") === "schmitt_VT";
  const fixed = Array.isArray(g.fixed_points) ? g.fixed_points.map((p) => ({ ...p })) : [];
  const ranges = Array.isArray(g.ranges) ? g.ranges.map((r) => ({ ...r })) : [];
  if (!fixed.length && !ranges.length) {
    (dc.vcc_list || dc.vcc_sweep_list || []).forEach((v) => {
      fixed.push(schmitt
        ? { vcc: v, VT_plus: ["", ""], VT_minus: ["", ""] }
        : { vcc: v, VIH_min_V: "", VIL_max_V: "" });
    });
  }
  const pinDrive = (dc && dc.pin_drive) || {};
  const hasAwg = Object.values(pinDrive).some((d) => d && String(d.src || "").toLowerCase() === "awg");
  const stim = g.stimulus || dc.stimulus || (hasAwg ? "AWG" : "PSU_MSO");
  const pm = schmitt
    ? { "VT+": "range", "VT-": "range", HYST: "range", ...((g.pass_mode) || {}) }
    : { VIH: "min_only", VIL: "max_only", ...((g.pass_mode) || {}) };
  return {
    stimulus: stimToken(stim) || (hasAwg ? "AWG" : "PSU_MSO"),
    pass_mode: pm,
    kind: g.kind || (schmitt ? "schmitt_VT" : ""),
    fixed_points: fixed,
    ranges,
    status: g.status || "UNCONFIRMED",
  };
}

function isSchmittGrid(dc) {
  const g = (dc && (dc.vcc_plan || dc.vcc_grid)) || {};
  return !!(dc && dc.schmitt) || String(g.kind || "") === "schmitt_VT";
}

function bandPassModeSelect(cur, cls) {
  return passModeSelect("vcc-band", cur, cls || "vcc-band-mode").replace('data-id="vcc-band"', "");
}

function stimToken(raw) {
  const s = String(raw || "").trim().toUpperCase().replace(/[-\/\s]/g, "_");
  if (s === "PSU_MSO" || s === "PSUMSO") return "PSU_MSO";
  if (s === "AWG") return "AWG";
  return "";
}

function mergeVccGridJs(grid) {
  const owned = {};
  ((grid && grid.ranges) || []).forEach((band) => {
    const start = Number(band.start);
    const stop = Number(band.stop);
    const step = Number(band.step) > 0 ? Number(band.step) : 0.1;
    if (!Number.isFinite(start) || !Number.isFinite(stop) || step <= 0 || stop + 1e-9 < start) return;
    const n = Math.round((stop - start) / step);
    for (let i = 0; i <= n; i += 1) {
      const v = Math.round((start + i * step) * 1e6) / 1e6;
      if (v > stop + 1e-8) break;
      owned[String(v)] = v;
    }
  });
  ((grid && grid.fixed_points) || []).forEach((pt) => {
    const v = Number(pt.vcc);
    if (!Number.isFinite(v)) return;
    const key = String(Math.round(v * 1e6) / 1e6);
    owned[key] = Number(key);
  });
  return Object.keys(owned).map((k) => owned[k]).sort((a, b) => a - b);
}

function logicStimulus() {
  const el = document.querySelector('input[name="logic-dc-stimulus"]:checked');
  if (el && el.value) return stimToken(el.value) || el.value;
  const dc = paramCatalog.logic_dc || {};
  return stimToken((dc.vcc_grid && dc.vcc_grid.stimulus) || dc.stimulus) || "AWG";
}

function applyStimulusHide() {
  const hide = logicStimulus() === "PSU_MSO";
  ["freq-label", "amp-label"].forEach((id) => {
    if ($(id)) $(id).classList.toggle("hidden", hide);
  });
  const awgNote = $("logic-dc-awg-note");
  if (awgNote) awgNote.classList.toggle("hidden", hide);
}

function collectVccGridFromUi() {
  const stimEl = document.querySelector('input[name="logic-dc-stimulus"]:checked');
  const stimulus = stimToken(stimEl && stimEl.value) || "AWG";
  const dc = paramCatalog.logic_dc || {};
  const prev = (dc.vcc_grid || dc.vcc_plan) || {};
  const schmitt = isSchmittGrid(dc);
  const fixed = [];
  document.querySelectorAll("#logic-dc-fixed-points .vcc-chip").forEach((chip) => {
    const vcc = numOrNull(chip.querySelector(".vcc-fixed-vcc") && chip.querySelector(".vcc-fixed-vcc").value);
    if (vcc == null) return;
    const item = { vcc };
    const modeEl = chip.querySelector(".vcc-band-mode");
    if (modeEl && modeEl.value) item.pass_mode = String(modeEl.value).replace(/-/g, "_");
    if (schmitt) {
      const plusLo = numOrNull(chip.querySelector(".vcc-fixed-vtplus-lo") && chip.querySelector(".vcc-fixed-vtplus-lo").value);
      const plusHi = numOrNull(chip.querySelector(".vcc-fixed-vtplus-hi") && chip.querySelector(".vcc-fixed-vtplus-hi").value);
      const minusLo = numOrNull(chip.querySelector(".vcc-fixed-vtminus-lo") && chip.querySelector(".vcc-fixed-vtminus-lo").value);
      const minusHi = numOrNull(chip.querySelector(".vcc-fixed-vtminus-hi") && chip.querySelector(".vcc-fixed-vtminus-hi").value);
      if (plusLo != null || plusHi != null) item.VT_plus = [plusLo, plusHi];
      if (minusLo != null || minusHi != null) item.VT_minus = [minusLo, minusHi];
    } else {
      item.VIH_min_V = numOrNull(chip.querySelector(".vcc-fixed-vih") && chip.querySelector(".vcc-fixed-vih").value);
      item.VIL_max_V = numOrNull(chip.querySelector(".vcc-fixed-vil") && chip.querySelector(".vcc-fixed-vil").value);
    }
    fixed.push(item);
  });
  const ranges = [];
  document.querySelectorAll("#logic-dc-ranges .vcc-range-row").forEach((row) => {
    const start = numOrNull(row.querySelector(".vcc-range-start") && row.querySelector(".vcc-range-start").value);
    const stop = numOrNull(row.querySelector(".vcc-range-stop") && row.querySelector(".vcc-range-stop").value);
    if (start == null || stop == null) return;
    const stepRaw = numOrNull(row.querySelector(".vcc-range-step") && row.querySelector(".vcc-range-step").value);
    const item = {
      start,
      stop,
      step: stepRaw == null ? 0.1 : stepRaw,
    };
    const modeEl = row.querySelector(".vcc-band-mode");
    if (modeEl && modeEl.value) item.pass_mode = String(modeEl.value).replace(/-/g, "_");
    if (schmitt) {
      item.VT_plus = [
        numOrNull(row.querySelector(".vcc-range-vtplus-lo") && row.querySelector(".vcc-range-vtplus-lo").value),
        numOrNull(row.querySelector(".vcc-range-vtplus-hi") && row.querySelector(".vcc-range-vtplus-hi").value),
      ];
      item.VT_minus = [
        numOrNull(row.querySelector(".vcc-range-vtminus-lo") && row.querySelector(".vcc-range-vtminus-lo").value),
        numOrNull(row.querySelector(".vcc-range-vtminus-hi") && row.querySelector(".vcc-range-vtminus-hi").value),
      ];
    } else {
      item.VIH_min_V = numOrNull(row.querySelector(".vcc-range-vih") && row.querySelector(".vcc-range-vih").value);
      item.VIL_max_V = numOrNull(row.querySelector(".vcc-range-vil") && row.querySelector(".vcc-range-vil").value);
    }
    const label = String((row.querySelector(".vcc-range-label") && row.querySelector(".vcc-range-label").value) || "").trim();
    if (label) item.label = label;
    ranges.push(item);
  });
  const pm = {};
  document.querySelectorAll("#logic-dc-grid-pass-mode .logic-dc-mode").forEach((sel) => {
    const id = sel.getAttribute("data-id");
    if (id && sel.value) pm[id] = String(sel.value).replace(/-/g, "_");
  });
  const out = {
    stimulus,
    pass_mode: Object.keys(pm).length
      ? pm
      : (schmitt ? { "VT+": "range", "VT-": "range" } : { VIH: "min_only", VIL: "max_only" }),
    fixed_points: fixed,
    ranges,
    status: prev.status || "UNCONFIRMED",
  };
  if (schmitt) out.kind = "schmitt_VT";
  const kindEl = $("logic-dc-grid-kind");
  if (kindEl && kindEl.value) out.kind = kindEl.value;
  return out;
}

function refreshVccPreview() {
  const preview = $("logic-dc-vcc-preview");
  const vccInput = $("logic-dc-vcc");
  const merged = mergeVccGridJs(collectVccGridFromUi());
  const txt = merged.length ? merged.join(", ") : "--";
  if (preview) preview.textContent = `Preview merged vcc_list: ${txt}`;
  if (vccInput) vccInput.value = merged.join(", ");
}

function pairVal(arr, idx) {
  if (!Array.isArray(arr) || arr[idx] == null || arr[idx] === "") return "";
  return arr[idx];
}

function fixedChipHtml(pt, schmitt) {
  const v = pt && pt.vcc != null ? pt.vcc : "";
  const mode = (pt && pt.pass_mode) || (schmitt ? "range" : "min-only");
  const modeHtml = `<label>pass_mode ${bandPassModeSelect(mode, "vcc-band-mode")}</label>`;
  if (schmitt) {
    const plus = (pt && (pt.VT_plus || pt["VT+"])) || [];
    const minus = (pt && (pt.VT_minus || pt["VT-"])) || [];
    return `<div class="vcc-chip">
    <label>VCC <input class="vcc-fixed-vcc" type="number" step="0.01" value="${v}" /></label>
    <label>VT+ min <input class="vcc-fixed-vtplus-lo" type="number" step="0.01" value="${pairVal(plus, 0)}" /></label>
    <label>VT+ max <input class="vcc-fixed-vtplus-hi" type="number" step="0.01" value="${pairVal(plus, 1)}" /></label>
    <label>VT- min <input class="vcc-fixed-vtminus-lo" type="number" step="0.01" value="${pairVal(minus, 0)}" /></label>
    <label>VT- max <input class="vcc-fixed-vtminus-hi" type="number" step="0.01" value="${pairVal(minus, 1)}" /></label>
    ${modeHtml}
    <button type="button" class="btn ghost vcc-remove-fixed">remove</button>
  </div>`;
  }
  const vih = pt && pt.VIH_min_V != null && pt.VIH_min_V !== "" ? pt.VIH_min_V : "";
  const vil = pt && pt.VIL_max_V != null && pt.VIL_max_V !== "" ? pt.VIL_max_V : "";
  return `<div class="vcc-chip">
    <label>VCC <input class="vcc-fixed-vcc" type="number" step="0.01" value="${v}" /></label>
    <label>VIH min <input class="vcc-fixed-vih" type="number" step="0.01" value="${vih}" /></label>
    <label>VIL max <input class="vcc-fixed-vil" type="number" step="0.01" value="${vil}" /></label>
    ${modeHtml}
    <button type="button" class="btn ghost vcc-remove-fixed">remove</button>
  </div>`;
}

function rangeRowHtml(band, schmitt) {
  const b = band || {};
  const step = b.step != null && b.step !== "" ? b.step : 0.1;
  const lab = b.label || "";
  const mode = b.pass_mode || (schmitt ? "range" : "min-only");
  const modeHtml = `<label>pass_mode ${bandPassModeSelect(mode, "vcc-band-mode")}</label>`;
  if (schmitt) {
    const plus = b.VT_plus || b["VT+"] || [];
    const minus = b.VT_minus || b["VT-"] || [];
    return `<div class="vcc-range-row">
    <label>start <input class="vcc-range-start" type="number" step="0.01" value="${b.start != null ? b.start : ""}" /></label>
    <label>stop <input class="vcc-range-stop" type="number" step="0.01" value="${b.stop != null ? b.stop : ""}" /></label>
    <label>step <input class="vcc-range-step" type="number" step="0.01" value="${step}" /></label>
    <label>VT+ min <input class="vcc-range-vtplus-lo" type="number" step="0.01" value="${pairVal(plus, 0)}" /></label>
    <label>VT+ max <input class="vcc-range-vtplus-hi" type="number" step="0.01" value="${pairVal(plus, 1)}" /></label>
    <label>VT- min <input class="vcc-range-vtminus-lo" type="number" step="0.01" value="${pairVal(minus, 0)}" /></label>
    <label>VT- max <input class="vcc-range-vtminus-hi" type="number" step="0.01" value="${pairVal(minus, 1)}" /></label>
    ${modeHtml}
    <label>label <input class="vcc-range-label" type="text" value="${lab}" /></label>
    <button type="button" class="btn ghost vcc-remove-range">remove</button>
  </div>`;
  }
  const vih = b.VIH_min_V != null && b.VIH_min_V !== "" ? b.VIH_min_V : "";
  const vil = b.VIL_max_V != null && b.VIL_max_V !== "" ? b.VIL_max_V : "";
  return `<div class="vcc-range-row">
    <label>start <input class="vcc-range-start" type="number" step="0.01" value="${b.start != null ? b.start : ""}" /></label>
    <label>stop <input class="vcc-range-stop" type="number" step="0.01" value="${b.stop != null ? b.stop : ""}" /></label>
    <label>step <input class="vcc-range-step" type="number" step="0.01" value="${step}" /></label>
    <label>VIH min <input class="vcc-range-vih" type="number" step="0.01" value="${vih}" /></label>
    <label>VIL max <input class="vcc-range-vil" type="number" step="0.01" value="${vil}" /></label>
    ${modeHtml}
    <label>label <input class="vcc-range-label" type="text" value="${lab}" /></label>
    <button type="button" class="btn ghost vcc-remove-range">remove</button>
  </div>`;
}

function pinWiringHtml(dc) {
  const labels = dc.pin_wiring_labels || [];
  const pins = dc.pins || [];
  const drive = dc.pin_drive || {};
  let items = labels.slice();
  if (!items.length) {
    items = pins.map((p) => {
      const d = drive[p.name];
      const extra = d && d.src ? ` <- ${String(d.src).toUpperCase()} CH${d.ch}` : "";
      return `${p.name} pin ${p.number != null ? p.number : "?"} ${p.role || ""}${extra}`;
    });
    if (dc.oe && dc.oe.pin) items.push(`OE ${dc.oe.pin} active-${dc.oe.active}`);
    if (dc.is_open_drain) items.push("open-drain: VOH N/A skip");
    if (dc.is_sequential) items.push("sequential: gate 2^n / ICC / dICC stay disabled");
    items.push(dc.wire_map && Object.keys(dc.wire_map).length
      ? "wire_map present (CONFIRMED pins + pin_drive only)"
      : "wire_map empty -- labels from pins + pin_drive; do not invent nets");
  }
  return (
    "<h3 class=\"subhead\">Pin / wiring map</h3>" +
    "<p class=\"hint\">From product_model pins + pin_drive. Human Continue after verify. Never invent nets. Missing pin numbers stay ? (HOLD).</p>" +
    `<ul class="hint" id="logic-dc-wire-labels">${items.map((x) => `<li>${escapeAttr(x)}</li>`).join("")}</ul>`
  );
}

function familyClassToken(dc) {
  const rec = (dc && dc.recipe) || {};
  return String((dc && dc.product_class) || rec.runner || rec.product_class || "")
    .toLowerCase()
    .replace(/-/g, "_");
}

function familyScaleHint(dc) {
  const cls = familyClassToken(dc);
  const nIn = ((dc && dc.logic_inputs) || []).length;
  const oe = dc && dc.oe;
  const seq = !!(dc && dc.is_sequential);
  const corners = seq ? 0 : (1 << nIn);
  const bits = [
    `N-input + OE scale: n=${nIn} ICC 2^n=${corners}${oe ? " + OE" : " (OE none)"}`,
  ];
  if (cls.indexOf("nand") >= 0) {
    bits.push("LIVE NAND: other=H invert. Do not copy G08 CMOS.");
  } else if (cls.indexOf("nor") >= 0) {
    bits.push("LIVE NOR: other=L invert. TTL not G08 CMOS.");
  } else if (cls.indexOf("xor") >= 0) {
    bits.push("LIVE XOR: track+invert. G86 VIL 0.20*VCC; VIH HOLD.");
  } else if (cls.indexOf("inv") >= 0) {
    bits.push("LIVE INV: n=1 Y=NOT A. NC is not OE.");
  } else if (cls.indexOf("dual_and") >= 0 || (cls.indexOf("dual") >= 0 && cls.indexOf("and") >= 0)) {
    bits.push("LIVE dual AND: CHA then CHB. Do not skip rewire.");
  } else if (cls.indexOf("dual_or") >= 0 || (cls.indexOf("dual") >= 0 && cls.indexOf("or") >= 0)) {
    bits.push("LIVE dual OR: CHA then CHB. Do not skip rewire.");
  }
  if (dc && dc.dual_channel_continue) {
    bits.push("2Gxx dual-channel Continue CHA then CHB -- do not skip rewire prompt (OpAmp-style switch). Recable Channel B after CHA Human Continue.");
  }
  if (dc && dc.is_open_drain) bits.push("Open-drain: hide VOH (N_A).");
  if (dc && dc.schmitt) bits.push("Schmitt: VT+ / VT- range. Do not collapse to VIH.");
  if (oe) bits.push(`OE ${oe.pin} active-${oe.active} -- IOZ when inactive only.`);
  return bits.join(" ");
}

function logicDcFlowNodes(dc) {
  const pins = (dc && dc.pins) || [];
  const drive = (dc && dc.pin_drive) || {};
  return pins.map((p, i) => {
    const d = drive[p.name] || {};
    const num = p.number != null ? p.number : "?";
    return {
      id: "pin-" + String(p.name || i),
      label: `${p.name || "?"} pin ${num}`,
      role: p.role || "pin",
      x: 56 + (i % 4) * 120,
      y: 36 + Math.floor(i / 4) * 64,
      src: d.src || "",
      ch: d.ch,
    };
  });
}

function logicDcFlowHtml(dc) {
  const nodes = logicDcFlowNodes(dc);
  const w = 520;
  const h = Math.max(120, 48 + Math.ceil(Math.max(nodes.length, 1) / 4) * 64);
  const shapes = nodes.map((n) => {
    const lab = escapeAttr(n.label);
    return `<g class="logic-dc-flow-node" data-id="${escapeAttr(n.id)}" transform="translate(${n.x},${n.y})">
      <rect class="logic-dc-flow-chip" x="-48" y="-16" width="96" height="32" rx="6" />
      <text text-anchor="middle" dy="4">${lab}</text>
    </g>`;
  }).join("");
  return (
    "<h3 class=\"subhead\">Pin / wiring D&amp;D</h3>" +
    "<p class=\"hint\">Vanilla pin/wiring D&amp;D canvas (#logic-dc-flow). Drag nodes to layout only -- never invent nets. No React xyflow. No xyflow npm.</p>" +
    `<div id="logic-dc-flow" class="logic-dc-flow" data-w="${w}" data-h="${h}">
      <svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${shapes}</svg>
    </div>`
  );
}

function wireLogicDcFlow() {
  const box = $("logic-dc-flow");
  if (!box) return;
  const svg = box.querySelector("svg");
  if (!svg) return;
  let drag = null;
  svg.onpointerdown = (ev) => {
    const g = ev.target && ev.target.closest && ev.target.closest(".logic-dc-flow-node");
    if (!g) return;
    const m = g.getAttribute("transform") || "";
    const nums = /translate\(([^,]+),([^)]+)\)/.exec(m);
    drag = {
      el: g,
      x: nums ? Number(nums[1]) : 0,
      y: nums ? Number(nums[2]) : 0,
      px: ev.clientX,
      py: ev.clientY,
    };
    try { g.setPointerCapture(ev.pointerId); } catch (e) {}
  };
  svg.onpointermove = (ev) => {
    if (!drag) return;
    const nx = drag.x + (ev.clientX - drag.px);
    const ny = drag.y + (ev.clientY - drag.py);
    drag.el.setAttribute("transform", `translate(${nx},${ny})`);
  };
  svg.onpointerup = () => { drag = null; };
  svg.onpointercancel = () => { drag = null; };
}

function renderCustomiseParameters(dc) {
  const grid = seedVccGrid(dc);
  const schmitt = isSchmittGrid(dc);
  const n = (dc && dc.sample_size) || paramCatalog.sample_size || 1;
  const stimPsu = grid.stimulus === "PSU_MSO" ? "checked" : "";
  const stimAwg = grid.stimulus !== "PSU_MSO" ? "checked" : "";
  const chips = (grid.fixed_points || []).map((pt) => fixedChipHtml(pt, schmitt)).join("") || "<p class=\"hint\">No fixed points. Add VCC.</p>";
  const ranges = (grid.ranges || []).map((r) => rangeRowHtml(r, schmitt)).join("") || "<p class=\"hint\">No range sweeps. Add range.</p>";
  const preview = mergeVccGridJs(grid);
  const dualOn = !!(dc && dc.dual_channel_continue);
  const dualChk = dualOn ? "checked" : "";
  const pm = grid.pass_mode || {};
  const gridModes = schmitt
    ? ("VT+ " + passModeSelect("VT+", pm["VT+"] || pm.VTPLUS || "range") +
      " VT- " + passModeSelect("VT-", pm["VT-"] || pm.VTMINUS || "range") +
      " HYST " + passModeSelect("HYST", pm.HYST || "range"))
    : ("VIH " + passModeSelect("VIH", pm.VIH || "min_only") +
      " VIL " + passModeSelect("VIL", pm.VIL || "max_only"));
  const oe = dc && dc.oe;
  const oeTxt = oe ? `${oe.pin} active ${oe.active}` : "none";
  const nIn = ((dc && dc.logic_inputs) || []).length;
  const corners = dc && dc.is_sequential ? 0 : (dc.icc_corners || (nIn ? (1 << nIn) : 0));
  return (
    "<h3 class=\"subhead\">Customise Parameters</h3>" +
    "<p class=\"hint\">vcc_plan editor: FIXED POINTS chips + RANGE SWEEPS + per-band limits + pass_mode (range / min-only / max-only). Same limits for every stepped VCC in a band. Preview merged vcc_list before START. Save Version overlay writes <code>_manifest/test_params.yaml</code> (test_params + vcc_plan). Card-CONFIRMED vcc_grid unlocks threshold numbers; overlay must not stamp UNCONFIRMED over CONFIRMED. Glyph gaps stay fail-closed. No xyflow. No invent.</p>" +
    `<p class="hint" id="logic-dc-family-scale">${familyScaleHint(dc || {})}</p>` +
    `<p class="hint">logic_inputs ${(dc.logic_inputs || []).join(",") || "--"} · OE ${oeTxt} · ICC corners ${corners}${dc && dc.is_sequential ? " (sequential -- 2^n disabled)" : " (2^n)"}</p>` +
    pinWiringHtml(dc || {}) +
    logicDcFlowHtml(dc || {}) +
    `<label class="check"><input type="checkbox" id="logic-dc-dual-continue" ${dualChk} /> 2Gxx dual-channel Continue (CHA then CHB). Off on 1Gxx. RS2G08/RS2G32 CONFIRMED CHA then CHB. Do not skip rewire prompt (OpAmp-style switch). Extra rs2g yaml without Datasheet card forbidden.</label>` +
    `<div class="logic-dc-stim">
      <label class="check"><input type="radio" name="logic-dc-stimulus" value="PSU_MSO" ${stimPsu} /> PSU_MSO</label>
      <label class="check"><input type="radio" name="logic-dc-stimulus" value="AWG" ${stimAwg} /> AWG</label>
    </div>` +
    "<p class=\"hint\" id=\"logic-dc-awg-note\">AWG: Freq/Amp stay on Advanced bench. PSU_MSO hides Freq/Amp (omit -- do not invent Hz/V).</p>" +
    `<label>n (sample_size)<input id="logic-dc-n" type="number" min="1" step="1" value="${n}" /></label>` +
    `<div id="logic-dc-grid-pass-mode"><p class="hint">vcc_plan pass_mode ${schmitt ? "(Schmitt VT range)" : "(VIH min_only / VIL max_only)"}: ${gridModes}</p></div>` +
    (grid.kind ? `<input type="hidden" id="logic-dc-grid-kind" value="${grid.kind}" />` : "") +
    "<h3 class=\"subhead\">FIXED POINTS</h3>" +
    `<div id="logic-dc-fixed-points">${chips}</div>` +
    "<button type=\"button\" class=\"btn ghost\" id=\"logic-dc-add-fixed\">Add VCC</button>" +
    "<h3 class=\"subhead\">RANGE SWEEPS</h3>" +
    `<div id="logic-dc-ranges">${ranges}</div>` +
    "<button type=\"button\" class=\"btn ghost\" id=\"logic-dc-add-range\">Add range</button>" +
    `<p class="hint" id="logic-dc-vcc-preview">Preview merged vcc_list: ${preview.length ? preview.join(", ") : "--"}</p>`
  );
}

function wireCustomiseParams() {
  const boxF = $("logic-dc-fixed-points");
  const boxR = $("logic-dc-ranges");
  const schmitt = isSchmittGrid(paramCatalog.logic_dc || {});
  if ($("logic-dc-add-fixed") && boxF) {
    $("logic-dc-add-fixed").onclick = () => {
      boxF.insertAdjacentHTML("beforeend", fixedChipHtml({ vcc: "", VIH_min_V: "", VIL_max_V: "" }, schmitt));
      refreshVccPreview();
    };
  }
  if ($("logic-dc-add-range") && boxR) {
    $("logic-dc-add-range").onclick = () => {
      boxR.insertAdjacentHTML("beforeend", rangeRowHtml({ start: "", stop: "", step: 0.1 }, schmitt));
      refreshVccPreview();
    };
  }
  const panel = $("logic-dc-body");
  if (panel) {
    panel.onclick = (ev) => {
      const t = ev.target;
      if (t && t.classList && t.classList.contains("vcc-remove-fixed")) {
        const chip = t.closest(".vcc-chip");
        if (chip) chip.remove();
        refreshVccPreview();
      }
      if (t && t.classList && t.classList.contains("vcc-remove-range")) {
        const row = t.closest(".vcc-range-row");
        if (row) row.remove();
        refreshVccPreview();
      }
    };
    panel.oninput = (ev) => {
      if (ev.target && ev.target.closest && (ev.target.closest(".vcc-chip") || ev.target.closest(".vcc-range-row"))) {
        refreshVccPreview();
      }
    };
  }
  document.querySelectorAll('input[name="logic-dc-stimulus"]').forEach((el) => {
    el.onchange = () => applyStimulusHide();
  });
  applyStimulusHide();
  refreshVccPreview();
  wireLogicDcFlow();
}

function renderLogicDc() {
  const panel = $("panel-logic-dc");
  const body = $("logic-dc-body");
  const meta = $("logic-dc-meta");
  const hint = $("logic-dc-hint");
  if (!panel || !body) return;
  const dc = paramCatalog.logic_dc;
  const show = activeFamily === "logic" && dc && (dc.logic_inputs || []).length;
  panel.classList.toggle("hidden", !show);
  if (!show) {
    body.innerHTML = "";
    if (meta) meta.textContent = "";
    return;
  }
  const inputs = dc.logic_inputs || [];
  const oe = dc.oe;
  const oeTxt = oe ? `${oe.pin} active ${oe.active}` : "none";
  const seq = !!dc.is_sequential;
  const od = !!dc.is_open_drain;
  if (meta) {
    meta.textContent =
      `${dc.part || ""} · inputs ${inputs.join(",")} · OE ${oeTxt}` +
      ` · schmitt ${dc.schmitt ? "yes" : "no"}` +
      (od ? " · open-drain (VOH N/A skip)" : "") +
      (seq ? " · sequential (gate 2^n disabled)" : ` · ICC ${dc.icc_corners || 0} corners (2^n)`) +
      (dc.isolation_status ? ` · isolation ${dc.isolation_status}` : "");
  }
  const enabled = dc.enabled_tests || [];
  const enHtml = "<h3 class=\"subhead\">Enabled tests</h3>" +
    (enabled.length
      ? `<p class="logic-dc-chips">${enabled.map((id) => `<span class="mode-tag">${id}</span>`).join(" ")}</p>`
      : "<p class=\"hint\">No enabled_tests on this part yaml.</p>");
  const vcc = (dc.vcc_list || dc.vcc_sweep_list || []).join(", ");
  const epsA = dc.stable_eps_A;
  const epsAShow = (epsA === null || epsA === undefined || epsA === "") ? "" : String(epsA);
  const customiseHtml = renderCustomiseParameters(dc);
  const recipeHtml =
    "<h3 class=\"subhead\">Recipe</h3>" +
    `<p class="hint">logic_inputs: ${inputs.join(", ") || "--"} · vcc_list: ${vcc || "--"} · ICC pins: ${(dc.icc_pins || []).join(",") || "--"}</p>` +
    `<p class="hint">Voltage settle uses stable_eps_V. Current uses stable_eps_A (amps) only; never reuse volts as amps. Blank/null = NON_TIGHT (wait settle_s once; not greenable as tight-settle). Set a grounded amp number for eps/N hard-FAIL. Tight claim without eps FAIL-closes. Do not invent a uA default.</p>` +
    `<label>vcc_list (comma; filled from preview)<input id="logic-dc-vcc" type="text" value="${vcc}" /></label>` +
    `<label>stable_eps_A overlay (amps; blank = null / NON_TIGHT)<input id="logic-dc-stable-eps-a" type="text" value="${epsAShow}" placeholder="null" /></label>`;
  const cardHtml = renderCardFields(dc.card_fields || []);
  const tt = dc.truth_table || [];
  const pins = tt.length ? Object.keys(tt[0]) : inputs.concat([dc.output_pin || "Y"]);
  let ttHtml = "<h3 class=\"subhead\">Truth table</h3>";
  if (!tt.length) {
    ttHtml += "<p class=\"hint\">No truth_table in product_model.</p>";
  } else {
    ttHtml += "<table class=\"logic-dc-table\"><thead><tr>" +
      pins.map((p) => `<th>${p}</th>`).join("") +
      "</tr></thead><tbody>" +
      tt.map((row) => "<tr>" + pins.map((p) => `<td>${row[p] ?? ""}</td>`).join("") + "</tr>").join("") +
      "</tbody></table>";
  }
  const iso = dc.isolation || {};
  let isoHtml = "<h3 class=\"subhead\">Isolation (run = first track, else invert; skip PROPOSED)</h3>";
  isoHtml += "<table class=\"logic-dc-table\"><thead><tr><th>Sweep</th><th>Hold</th><th>Y</th><th>Status</th><th>Used</th></tr></thead><tbody>";
  inputs.forEach((pin) => {
    const block = iso[pin] || {};
    const run = block.run || [];
    const all = (block.all && block.all.length) ? block.all : run;
    const runKey = (p) => {
      const hold = p.hold || p.fix || {};
      const holdTxt = Object.keys(hold).map((k) => `${k}=${hold[k]}`).join(" ");
      return `${p.sweep || pin}|${holdTxt}|${p.y_expect || ""}`;
    };
    const runSet = new Set(run.map(runKey));
    if (!all.length) {
      isoHtml += `<tr><td>${pin}</td><td colspan="4">UNSURE -- no derivable combo</td></tr>`;
      return;
    }
    all.forEach((p) => {
      const hold = p.hold || p.fix || {};
      const holdTxt = Object.keys(hold).map((k) => `${k}=${hold[k]}`).join(" ") || "--";
      const st = p.status || p.source || "";
      const used = runSet.has(runKey(p)) ? "run" : "";
      isoHtml += `<tr><td>${p.sweep || pin}</td><td>${holdTxt}</td><td>${p.y_expect || ""}</td><td>${st}</td><td>${used}</td></tr>`;
    });
  });
  isoHtml += "</tbody></table>";
  const cornerRows = dc.icc_corner_rows || [];
  const cornerPins = dc.icc_pins || inputs;
  let cornerHtml = seq
    ? "<h3 class=\"subhead\">ICC corners (sequential -- gate 2^n / ICC / ΔICC stay disabled)</h3>"
    : `<h3 class="subhead">ICC corners (${dc.icc_corners || cornerRows.length} = 2^n)</h3>`;
  if (seq) {
    cornerHtml += "<p class=\"hint\">RS164-class sequential: do not tick Path B icc / delta_icc / input_threshold 2^n.</p>";
  } else if (!cornerRows.length) {
    cornerHtml += "<p class=\"hint\">No derived ICC corners.</p>";
  } else {
    cornerHtml += "<table class=\"logic-dc-table\" id=\"logic-dc-corners\"><thead><tr>" +
      cornerPins.map((p) => `<th>${p}</th>`).join("") +
      "</tr></thead><tbody>" +
      cornerRows.map((row) => "<tr>" + cornerPins.map((p) => `<td>${row[p] ?? ""}</td>`).join("") + "</tr>").join("") +
      "</tbody></table>";
    if ((dc.icc_corners || 0) > cornerRows.length) {
      cornerHtml += `<p class="hint">Showing first ${cornerRows.length} of ${dc.icc_corners}.</p>`;
    }
  }
  const specs = dc.specs || [];
  let specHtml = "<h3 class=\"subhead\">Limits + pass_mode</h3>";
  specHtml += "<table class=\"logic-dc-table\"><thead><tr><th>Id</th><th>Mode</th><th>Min</th><th>Max</th><th>Test</th></tr></thead><tbody>";
  specs.forEach((s) => {
    const sid = s.id || "";
    if (od && /^voh/i.test(sid)) {
      specHtml += `<tr><td>${sid}</td><td>N/A</td><td>unspec</td><td>unspec</td><td>open-drain skip</td></tr>`;
      return;
    }
    const unspec = s.min == null && s.max == null ? " unspec" : "";
    let note = s.test || "";
    if (dc.has_oe && /^ioz/i.test(sid)) note += " (IOZ when OE inactive only)";
    specHtml += `<tr><td>${sid}</td><td>${passModeSelect(sid, s.pass_mode)}</td>` +
      `<td>${s.min != null ? s.min : "unspec"}</td><td>${s.max != null ? s.max : "unspec"}</td><td>${note}${unspec}</td></tr>`;
  });
  specHtml += "</tbody></table>";
  const gaps = (dc.gaps || []).map((g) => `<li>${g}</li>`).join("");
  const gapHtml = gaps ? `<h3 class="subhead">Gaps</h3><ul class="hint">${gaps}</ul>` : "";
  body.innerHTML = enHtml + customiseHtml + recipeHtml + cardHtml + ttHtml + isoHtml + cornerHtml + specHtml + gapHtml;
  if (hint && !hint.textContent) {
    hint.textContent = "Save Version overlay writes _manifest/test_params.yaml (vcc_plan + vcc_grid + merged vcc_list + pass_mode + n + stable_eps_A). Save product_model writes card_fields.schema.yaml keys. Ctrl+F5 after worker restart if RPC is new.";
  }
  wirePassModeSync();
  wireCardFieldDeletes();
  wireCustomiseParams();
}

function kindLabel(kind) {
  if (kind === "dut_change") return "DUT";
  if (kind === "config_change") return "Board";
  if (kind === "channel_change") return "Channel";
  if (kind === "measure") return "Measure";
  return kind || "Operator";
}

function shortGateTitle(promptOrTitle) {
  if (promptOrTitle && typeof promptOrTitle === "object") {
    const tag = String(promptOrTitle.test_tag || "").trim();
    if (tag) return tag.length > 28 ? `${tag.slice(0, 25)}...` : tag;
    promptOrTitle = promptOrTitle.title;
  }
  const t = String(promptOrTitle || "Operator action");
  return t.length > 44 ? `${t.slice(0, 41)}...` : t;
}

function updateGateDock(prompt) {
  const dock = $("gate-dock");
  const bubbles = $("gate-bubbles");
  const btn = $("gate-dock-btn");
  const badge = $("gate-badge");
  if (!dock || !bubbles) return;

  if (prompt && prompt.id) {
    const idx = gateQueue.findIndex((p) => p.id === prompt.id);
    if (idx >= 0) gateQueue[idx] = prompt;
    else gateQueue.push(prompt);
  } else {
    gateQueue = [];
  }

  const waiting = gateQueue.length;
  dock.classList.toggle("has-pending", waiting > 0);
  if (badge) badge.textContent = String(waiting);
  if (btn) btn.classList.toggle("hidden", waiting === 0);

  bubbles.innerHTML = gateQueue
    .map(
      (p) =>
        `<button type="button" class="gate-bubble" data-id="${p.id}" title="${p.title || ""}">
          <span class="gate-bubble-kind">${kindLabel(p.kind)}${p.test_tag ? " · " + p.test_tag : ""}</span>
          <span class="gate-bubble-title">${shortGateTitle(p)}</span>
        </button>`
    )
    .join("");

  bubbles.querySelectorAll(".gate-bubble").forEach((el) => {
    el.onclick = () => {
      const p = gateQueue.find((x) => x.id === el.dataset.id);
      if (p) openOperatorModal(p);
    };
  });
}

function openOperatorModal(payload) {
  pendingPrompt = payload;
  const kind = kindLabel(payload.kind);
  const tag = String(payload.test_tag || "").trim();
  $("modal-kind").textContent = tag ? `${kind} · ${tag}` : kind;
  $("modal-title").textContent = payload.title || "Operator action";
  $("modal-next").textContent = payload.next_hint || "";
  $("modal-list").innerHTML = (payload.checklist || [])
    .map((c) => `<li>${c}</li>`)
    .join("");
  $("modal").classList.remove("hidden");
  setRunPill("wait");
}

function showModal(payload) {
  updateGateDock(payload);
  openOperatorModal(payload);
}

function hideModal() {
  if (pendingPrompt) {
    gateQueue = gateQueue.filter((p) => p.id !== pendingPrompt.id);
    updateGateDock(gateQueue[0] || null);
  }
  pendingPrompt = null;
  $("modal").classList.add("hidden");
}

async function syncPendingGate({ autoOpen = true } = {}) {
  try {
    const p = await rpc("get_pending_prompt");
    if (p) {
      updateGateDock(p);
      if (autoOpen && ($("modal").classList.contains("hidden") || pendingPrompt?.id !== p.id)) {
        openOperatorModal(p);
      }
      return p;
    }
    updateGateDock(null);
    if (pendingPrompt) hideModal();
    return null;
  } catch (_) {
    return null;
  }
}

async function respondContinue() {
  if (!pendingPrompt) {
    const p = await syncPendingGate({ autoOpen: true });
    if (!p) return false;
  }
  await rpc("operator_respond", { prompt_id: pendingPrompt.id, continue: true });
  hideModal();
  return true;
}

function fmtTs(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch (_) {
    return iso;
  }
}

function entryLine(e) {
  const tag =
    e.kind === "dut_change" ? "DUT" :
    e.kind === "config_change" ? "CFG" :
    e.kind === "channel_change" ? "CH" :
    "TEST";
  const ts = e.finished_at || e.started_at;
  const msg = e.message ? ` — ${e.message}` : "";
  const ch = e.channel ? ` · ${e.channel}` : "";
  return `<li class="${e.status}" data-id="${e.id}">
    <span class="ts">${fmtTs(ts)} · ${tag} · ${e.status}</span>
    <strong>${e.label}</strong>${ch}${msg}
  </li>`;
}

function renderStepStatusBar(tl) {
  const bar = $("step-status-bar");
  if (!bar) return;
  const rows = (tl && tl.entries) ? tl.entries : [];
  if (!rows.length) {
    bar.innerHTML = "";
    return;
  }
  bar.innerHTML = rows.map((e) => {
    const st = e.status || "pending";
    const ch = e.channel ? ` [${e.channel}]` : "";
    const msg = e.message ? e.message : (e.next_hint || "");
    return `<div class="step-row ${st}" data-id="${e.id}">
      <span class="step-dot"></span>
      <span class="step-label">${e.label}${ch}</span>
      <span class="step-msg">${st}${msg ? " · " + msg : ""}</span>
    </div>`;
  }).join("");

  // Substeps only while a selected test is actively running
  const runningEntry =
    tl && tl.current && tl.current.status === "running" ? tl.current : null;
  const subTestId = runningEntry && runningEntry.test_id ? runningEntry.test_id : "";
  const subTest = subTestId ? allTests.find((t) => t.id === subTestId) : null;
  if (
    runningEntry &&
    subTest &&
    selectedTests().includes(subTestId) &&
    subTest.fixed_steps &&
    subTest.fixed_steps.length &&
    Object.keys(substepState).length
  ) {
    const subHtml = subTest.fixed_steps.map((s) => {
      const st = substepState[s.id] || "pending";
      return `<div class="step-row ${st}">
        <span class="step-dot"></span>
        <span class="step-label">↳ ${s.label}</span>
        <span class="step-msg">${st}</span>
      </div>`;
    }).join("");
    bar.innerHTML += subHtml;
  }
}

function updateSubstepChip(testId, stepId, status) {
  if (!testId || !selectedTests().includes(testId)) return;
  if (testId !== activeSubstepTestId) {
    substepState = {};
    activeSubstepTestId = testId;
  }
  substepState[stepId] = status;
  document.querySelectorAll(`.slew-step-chip[data-step="${stepId}"]`).forEach((el) => {
    el.classList.remove("done", "running", "pending", "pass", "fail");
    el.classList.add(status);
  });
  if (lastTimeline) renderStepStatusBar(lastTimeline);
}

function renderTimeline(tl) {
  if (!tl || !tl.entries) return;
  lastTimeline = tl;
  const pct = tl.progress_pct || 0;
  $("progress-bar").style.width = `${pct}%`;
  $("progress-meta").textContent =
    `${tl.done_count || 0} / ${tl.total_count || 0} · ${pct}%` +
    (tl.session_id ? ` · ${tl.session_id}` : "");

  const waiting = tl.waiting;
  const next = tl.next;
  const banner = $("next-banner");
  if (waiting) {
    banner.className = "next-banner wait";
    banner.textContent = `WAITING: ${waiting.label}` +
      (waiting.next_hint ? ` → ${waiting.next_hint}` : " — press Continue");
  } else if (tl.current && tl.current.status === "running") {
    banner.className = "next-banner";
    banner.textContent = `RUNNING: ${tl.current.label}` +
      (next ? ` · Next: ${next.label}` : "");
  } else if (next) {
    banner.className = "next-banner";
    banner.textContent = `NEXT: ${next.label}` +
      (next.next_hint ? ` — ${next.next_hint}` : "");
  } else if (tl.finished_at) {
    banner.className = "next-banner";
    banner.textContent = `DONE · finished ${fmtTs(tl.finished_at)}`;
  } else {
    banner.className = "next-banner";
    banner.textContent = "Next: —";
  }

  $("timeline").innerHTML = (tl.entries || []).map(entryLine).join("");
  $("history").innerHTML = (tl.history || []).slice().reverse().map(entryLine).join("");
  renderStepStatusBar(tl);

  const cid = (tl.current || {}).id;
  if (cid && cid !== lastScrollId) {
    lastScrollId = cid;
    const cur = document.querySelector(`#timeline li[data-id="${cid}"]`);
    if (cur) cur.scrollIntoView({ block: "nearest" });
  }
}

function fillSelect(el, values, selected) {
  if (!el) return;
  el.innerHTML = (values || []).map((v) => {
    const sel = v === selected ? "selected" : "";
    return `<option value="${v}" ${sel}>${v}</option>`;
  }).join("");
}

function escapeAttr(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");
}

function liveKeys(obj) {
  return Object.keys(obj || {}).filter((k) => k && !k.startsWith("_") && !k.startsWith("."));
}

const comboStore = {};
const COMBO_REMOVABLE = new Set(["setup-label-value", "db-tag-input", "tag-board-select"]);
let comboMenu = null;
let comboOpenId = "";
let comboHi = -1;
let comboPicks = [];
let combosReady = false;
let comboDirty = false;

function comboMenuEl() {
  if (comboMenu) return comboMenu;
  comboMenu = document.createElement("div");
  comboMenu.id = "ate-combo-menu";
  comboMenu.className = "combo-menu hidden";
  comboMenu.setAttribute("role", "listbox");
  document.body.appendChild(comboMenu);
  return comboMenu;
}

function syncComboChrome(el) {
  if (!el) return;
  const wrap = el.closest(".combo");
  const clear = wrap && wrap.querySelector(".combo-clear");
  if (clear) clear.classList.toggle("hidden", !String(el.value || "").trim());
}

function fillCombo(el, values, selected) {
  if (!el) return;
  const uniq = [];
  const seen = new Set();
  for (const v of values || []) {
    const s = String(v || "").trim();
    if (!s || seen.has(s)) continue;
    seen.add(s);
    uniq.push(s);
  }
  const keep = (selected != null && String(selected).trim())
    ? String(selected).trim()
    : String(el.value || "").trim();
  if (keep && !seen.has(keep)) uniq.unshift(keep);
  if (el.id) comboStore[el.id] = uniq;
  if (keep) el.value = keep;
  syncComboChrome(el);
  if (comboOpenId && el.id === comboOpenId) renderComboMenu();
}

function closeComboMenu() {
  comboOpenId = "";
  comboHi = -1;
  comboPicks = [];
  if (comboMenu) comboMenu.classList.add("hidden");
}

function comboFiltered(input) {
  const q = String(input.value || "").trim().toLowerCase();
  const all = comboStore[input.id] || [];
  if (!comboDirty || !q) return all.slice();
  return all.filter((v) => String(v).toLowerCase().includes(q));
}

function renderComboMenu() {
  const input = comboOpenId ? $(comboOpenId) : null;
  const menu = comboMenuEl();
  if (!input) {
    closeComboMenu();
    return;
  }
  const wrap = input.closest(".combo") || input;
  const rect = wrap.getBoundingClientRect();
  const q = String(input.value || "").trim();
  const rows = comboFiltered(input);
  const exact = (comboStore[input.id] || []).some((v) => String(v).toLowerCase() === q.toLowerCase());
  comboPicks = [];
  if (q && !exact) comboPicks.push({ add: true, value: q });
  rows.forEach((v) => comboPicks.push({ add: false, value: v }));
  if (comboHi >= comboPicks.length) comboHi = comboPicks.length - 1;
  menu.innerHTML = "";
  if (!comboPicks.length) {
    const empty = document.createElement("div");
    empty.className = "combo-empty";
    empty.textContent = "type to add";
    menu.appendChild(empty);
  } else {
    comboPicks.forEach((pick, i) => {
      const row = document.createElement("div");
      row.className = "combo-opt" + (i === comboHi ? " hi" : "");
      const lab = document.createElement("button");
      lab.type = "button";
      lab.className = pick.add ? "combo-add" : "combo-opt-lab";
      lab.textContent = pick.add ? ("Add " + pick.value) : pick.value;
      lab.onmousedown = (ev) => {
        ev.preventDefault();
        applyComboPick(input, pick.value);
      };
      row.appendChild(lab);
      if (!pick.add && COMBO_REMOVABLE.has(input.id)) {
        const x = document.createElement("button");
        x.type = "button";
        x.className = "combo-opt-x";
        x.textContent = "x";
        x.title = "Remove";
        x.onmousedown = (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          removeComboOption(input, pick.value);
        };
        row.appendChild(x);
      }
      menu.appendChild(row);
    });
  }
  const need = Math.min(240, Math.max(36, comboPicks.length * 28 + 12));
  let top = rect.bottom + 2;
  if (top + need > window.innerHeight - 8 && rect.top > need + 8) {
    top = Math.max(4, rect.top - need - 2);
  }
  menu.style.left = Math.max(4, rect.left) + "px";
  menu.style.top = top + "px";
  menu.style.width = Math.max(rect.width, 160) + "px";
  menu.classList.remove("hidden");
}

function openCombo(input) {
  if (!input || !input.id) return;
  comboOpenId = input.id;
  comboHi = -1;
  comboDirty = false;
  renderComboMenu();
}

function toggleCombo(input) {
  if (comboOpenId === input.id) closeComboMenu();
  else openCombo(input);
}

function applyComboPick(input, value) {
  if (!input) return;
  if (input.id === "db-tag-input") {
    addCampaignTagFromText(value);
    input.value = "";
    syncComboChrome(input);
    closeComboMenu();
    return;
  }
  if (input.id === "tag-board-select") {
    input.value = value;
    syncComboChrome(input);
    closeComboMenu();
    return;
  }
  input.value = value;
  syncComboChrome(input);
  closeComboMenu();
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function removeComboOption(input, value) {
  const v = String(value || "");
  comboStore[input.id] = (comboStore[input.id] || []).filter((x) => x !== v);
  if (input.value === v) input.value = "";
  syncComboChrome(input);
  if (input.id === "db-tag-input" || input.id === "tag-board-select") {
    const tok = input.id === "tag-board-select" && !v.includes(":") ? `board:${v}` : v;
    campaignTags = (campaignTags || []).filter((t) => t !== tok && t !== v);
    campaignLabels = (campaignLabels || []).filter((lab) => labelToken(lab) !== tok && labelToken(lab) !== v);
    if (tok.startsWith("board:") || input.id === "tag-board-select") {
      const b = tok.startsWith("board:") ? tok.slice(6) : v;
      campaignBoards = (campaignBoards || []).filter((x) => x !== b);
      boardVocab = (boardVocab || []).filter((x) => x !== b);
    }
    if (tok.includes(":")) {
      const i = tok.indexOf(":");
      const kind = tok.slice(0, i);
      const val = tok.slice(i + 1);
      if (labelValueVocab[kind]) {
        labelValueVocab[kind] = labelValueVocab[kind].filter((x) => x !== val);
      }
    }
    paintTagsEditor();
    saveCampaignLabels().catch((e) => log(`Labels: ${e.message}\n`));
  }
  if (input.id === "setup-label-value") {
    const kind = (($("setup-label-kind") && $("setup-label-kind").value) || "tag").trim();
    if (labelValueVocab[kind]) {
      labelValueVocab[kind] = labelValueVocab[kind].filter((x) => x !== v);
    }
    campaignLabels = (campaignLabels || []).filter((lab) => !(lab.kind === kind && lab.value === v));
    campaignTags = (campaignTags || []).filter((t) => t !== labelToken({ kind, value: v }));
    paintTagsEditor();
    saveCampaignLabels().catch((e) => log(`Labels: ${e.message}\n`));
  }
  renderComboMenu();
}

function onComboKey(input, ev) {
  const tagger = input.id === "db-tag-input";
  if (ev.key === "Escape") {
    closeComboMenu();
    return;
  }
  if (ev.key === "ArrowDown") {
    ev.preventDefault();
    if (comboOpenId !== input.id) openCombo(input);
    else {
      comboHi = Math.min(comboPicks.length - 1, comboHi + 1);
      renderComboMenu();
    }
    return;
  }
  if (ev.key === "ArrowUp") {
    ev.preventDefault();
    if (comboOpenId !== input.id) openCombo(input);
    else {
      comboHi = Math.max(0, comboHi - 1);
      renderComboMenu();
    }
    return;
  }
  if (tagger && (ev.key === " " || ev.key === ",") && String(input.value).trim()) {
    ev.preventDefault();
    addCampaignTagFromText(input.value);
    input.value = "";
    syncComboChrome(input);
    closeComboMenu();
    return;
  }
  if (ev.key === "Enter") {
    ev.preventDefault();
    ev.stopImmediatePropagation();
    if (input.id === "setup-label-value") {
      if (comboOpenId === input.id && comboHi >= 0 && comboPicks[comboHi]) {
        applyComboPick(input, comboPicks[comboHi].value);
      }
      if ($("btn-setup-add-label")) $("btn-setup-add-label").click();
      return;
    }
    if (comboOpenId === input.id && comboHi >= 0 && comboPicks[comboHi]) {
      applyComboPick(input, comboPicks[comboHi].value);
      return;
    }
    const typed = String(input.value || "").trim();
    if (tagger && typed) {
      addCampaignTagFromText(typed);
      input.value = "";
      syncComboChrome(input);
      closeComboMenu();
      return;
    }
    if (typed) applyComboPick(input, typed);
  }
}

function bindCombo(wrap) {
  if (!wrap || wrap.dataset.comboBound) return;
  wrap.dataset.comboBound = "1";
  const input = wrap.querySelector("input");
  const caret = wrap.querySelector(".combo-caret");
  const clear = wrap.querySelector(".combo-clear");
  if (!input) return;
  if (!input.id) input.id = "combo-" + Math.random().toString(36).slice(2, 8);
  if (caret) {
    caret.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      toggleCombo(input);
      input.focus();
    });
  }
  if (clear) {
    clear.innerHTML = '<span aria-hidden="true">x</span>';
    clear.setAttribute("aria-label", "Clear");
    clear.addEventListener("mousedown", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      input.value = "";
      syncComboChrome(input);
      closeComboMenu();
      input.dispatchEvent(new Event("change", { bubbles: true }));
      input.focus();
    });
  }
  input.addEventListener("mousedown", () => {
    if (comboOpenId !== input.id) openCombo(input);
  });
  input.addEventListener("input", () => {
    comboDirty = true;
    syncComboChrome(input);
    if (comboOpenId === input.id) renderComboMenu();
    else openCombo(input);
  });
  input.addEventListener("keydown", (ev) => onComboKey(input, ev));
}

function initCombos() {
  document.querySelectorAll(".combo").forEach(bindCombo);
  if (combosReady) return;
  combosReady = true;
  document.addEventListener("mousedown", (ev) => {
    if (!comboOpenId) return;
    const t = ev.target;
    if (t && t.closest && t.closest("#ate-combo-menu")) return;
    const wrap = t && t.closest && t.closest(".combo");
    const input = wrap && wrap.querySelector("input");
    if (input && input.id === comboOpenId) return;
    closeComboMenu();
  });
  window.addEventListener("resize", closeComboMenu);
}

function addCampaignTagFromText(raw) {
  const t = String(raw || "").trim();
  if (!t || t.startsWith("(")) return false;
  let kind = "tag";
  let value = t;
  if (t.includes(":")) {
    const i = t.indexOf(":");
    kind = t.slice(0, i).trim() || "tag";
    value = t.slice(i + 1).trim();
  }
  if (!value) return false;
  addSetupLabel(kind, value);
  return true;
}

function tagComboValues() {
  const out = [];
  const seen = new Set((campaignTags || []).map((t) => String(t).toLowerCase()));
  const add = (tok) => {
    const s = String(tok || "").trim();
    if (!s || seen.has(s.toLowerCase())) return;
    seen.add(s.toLowerCase());
    out.push(s);
  };
  for (const [kind, vals] of Object.entries(labelValueVocab || {})) {
    for (const v of vals || []) {
      add(kind === "tag" ? v : `${kind}:${v}`);
    }
  }
  for (const b of boardVocab || []) add(`board:${b}`);
  return out;
}

function operatorFromPic(pic) {
  const raw = String(pic || "").trim();
  if (!raw || raw.toLowerCase() === "rs") return "";
  const row = (ownersList || []).find((o) => {
    const id = String(o.id || "").toLowerCase();
    const lab = String(o.label || "").toLowerCase();
    return id === raw.toLowerCase() || lab === raw.toLowerCase();
  });
  if (!row || row.id === "all") return "";
  return row.label || row.id || "";
}

function componentForCategory(catId) {
  const row = (categoryRows || []).find((c) => c.id === catId);
  if (row && row.component) return row.component;
  return componentFromFamily(catId) || "";
}

function mergeInventoryIntoTree() {
  for (const row of inventoryRows || []) {
    const component = componentForCategory(row.category) || "";
    const part = String(row.part || "").trim().toUpperCase();
    if (!component || !part) continue;
    const op = operatorFromPic(row.pic) || writeOperatorLabel() || "Eugene";
    ensureTreeHasCampaign({
      component,
      part,
      package: row.package || "SOT23",
      operator: op,
      version: "Version_1",
      model: row.model || part,
    });
  }
}

function campaignFromInventory(family) {
  const want = typeForFamily(family);
  const rows = (inventoryRows || []).filter((r) => String(r.category || "") === want);
  const row = rows.find((r) => suiteForRow(r)) || rows[0];
  if (!row) return null;
  return {
    component: componentForCategory(row.category) || componentFromFamily(family),
    part: String(row.part || "").toUpperCase(),
    package: row.package || "SOT23",
    operator: operatorFromPic(row.pic) || writeOperatorLabel() || "Eugene",
    version: "Version_1",
    model: row.model || row.part || "",
    year: ($("db-year") && $("db-year").value) || "2026",
  };
}

function versionsForSel(sel) {
  const partsObj = ((dbTree.components || {})[sel.component] || {}).parts || {};
  const pkgsObj = (partsObj[sel.part] || {}).packages || {};
  const opsObj = (pkgsObj[sel.package] || {}).operators || {};
  return ((opsObj[sel.operator] || {}).versions || []).filter(Boolean);
}

const CAMPAIGN_KEY = "ate_last_campaign";
const CAMPAIGN_BY_FAMILY_KEY = "ate_last_campaign_by_family";
const DEFAULT_CAMPAIGN = {
  component: "OpAmp",
  part: "RS622",
  package: "TTSOP8",
  operator: "Eugene",
  version: "Version_1",
  model: "RS622XK",
  year: "2026",
};

function readSavedCampaign() {
  try {
    const raw = localStorage.getItem(CAMPAIGN_KEY);
    if (!raw) return { ...DEFAULT_CAMPAIGN };
    return { ...DEFAULT_CAMPAIGN, ...JSON.parse(raw) };
  } catch (_) {
    return { ...DEFAULT_CAMPAIGN };
  }
}

function saveCampaign(sel) {
  const payload = {
    component: sel.component || "",
    part: sel.part || "",
    package: sel.package || "",
    operator: sel.operator || "",
    version: sel.version || "",
    model: sel.model || "",
    year: sel.year || "",
  };
  try {
    localStorage.setItem(CAMPAIGN_KEY, JSON.stringify(payload));
  } catch (_) { /* ignore */ }
  try {
    const fam = familyFromComponent(sel.component);
    const all = JSON.parse(localStorage.getItem(CAMPAIGN_BY_FAMILY_KEY) || "{}");
    all[fam] = payload;
    localStorage.setItem(CAMPAIGN_BY_FAMILY_KEY, JSON.stringify(all));
  } catch (_) { /* ignore */ }
}

function readSavedByFamily(family) {
  try {
    const all = JSON.parse(localStorage.getItem(CAMPAIGN_BY_FAMILY_KEY) || "{}");
    const hit = all[family];
    return hit && hit.component ? hit : null;
  } catch (_) {
    return null;
  }
}

function ensureTreeHasCampaign(sel) {
  if (!dbTree.components) dbTree.components = {};
  const c = sel.component || DEFAULT_CAMPAIGN.component;
  const p = sel.part || DEFAULT_CAMPAIGN.part;
  const pkg = sel.package || DEFAULT_CAMPAIGN.package;
  const op = sel.operator || DEFAULT_CAMPAIGN.operator;
  const ver = sel.version || DEFAULT_CAMPAIGN.version;
  if (!dbTree.components[c]) dbTree.components[c] = { parts: {} };
  if (!dbTree.components[c].parts[p]) dbTree.components[c].parts[p] = { packages: {} };
  if (!dbTree.components[c].parts[p].packages[pkg]) {
    dbTree.components[c].parts[p].packages[pkg] = { operators: {} };
  }
  const pkgNode = dbTree.components[c].parts[p].packages[pkg];
  if (!pkgNode.operators) pkgNode.operators = {};
  if (!pkgNode.operators[op]) pkgNode.operators[op] = { versions: [ver] };
  const vers = pkgNode.operators[op].versions || [];
  if (!vers.includes(ver)) vers.push(ver);
  pkgNode.operators[op].versions = vers;
}

function paintCampaign(sel) {
  ensureTreeHasCampaign(sel);
  refreshDbCascades(sel);
  if ($("db-model")) $("db-model").value = sel.model || sel.part || "";
  if (sel.year && $("db-year") && !$("db-year").value) $("db-year").value = sel.year;
  if ($("db-breadcrumb") && sel.component) {
    $("db-breadcrumb").textContent =
      `${sel.component} / ${sel.part} / ${sel.package} / ${sel.operator || "?"} / ${sel.version}` +
      (sel.model ? ` · ${sel.model}` : "");
  }
  if (sel.operator) syncOwnerSelectFromFolder(sel.operator);
}

function currentDbSelection() {
  return {
    component: $("db-component").value,
    part: $("db-part").value,
    package: $("db-package").value,
    operator: ($("db-operator") && $("db-operator").value) || "",
    version: $("db-version").value,
    model: $("db-model").value,
    year: $("db-year").value,
  };
}

function refreshDbCascades(preserve, changedId) {
  mergeInventoryIntoTree();
  const comps = liveKeys(dbTree.components);
  const sel = preserve || currentDbSelection();
  const component = sel.component || comps[0] || "";
  fillCombo($("db-component"), comps, component);

  const partsObj = ((dbTree.components || {})[component] || {}).parts || {};
  const parts = liveKeys(partsObj);
  let part = sel.part || parts[0] || "";
  if (changedId === "db-component" && parts.length && !parts.includes(part)) part = parts[0];
  fillCombo($("db-part"), parts, part);

  const pkgsObj = (partsObj[part] || {}).packages || {};
  const packages = liveKeys(pkgsObj);
  let pkg = sel.package || packages[0] || "";
  if ((changedId === "db-component" || changedId === "db-part") && packages.length && !packages.includes(pkg)) {
    pkg = packages[0];
  }
  fillCombo($("db-package"), packages, pkg);

  const opsObj = (pkgsObj[pkg] || {}).operators || {};
  const diskOps = Object.keys(opsObj).filter((k) => k && !k.startsWith(".") && k !== "_unassigned");
  const yamlOps = ownersList.filter((o) => o && o.id !== "all").map((o) => o.label || o.id);
  const operators = [];
  const seenOps = new Set();
  diskOps.concat(yamlOps).forEach((name) => {
    if (!name || seenOps.has(name)) return;
    seenOps.add(name);
    operators.push(name);
  });
  const preferOp = sel.operator && sel.operator !== "_unassigned"
    ? sel.operator
    : writeOperatorLabel();
  let operator = pickLiveOperator(operators, preferOp) || sel.operator || "";
  if ((changedId === "db-component" || changedId === "db-part" || changedId === "db-package")
      && operators.length && !operators.includes(operator)) {
    operator = pickLiveOperator(operators, writeOperatorLabel());
  }
  fillCombo($("db-operator"), operators, operator);

  const versions = versionsForSel({ component, part, package: pkg, operator }) || ["Version_1"];
  const versionList = versions.length ? versions : ["Version_1"];
  let version = sel.version || versionList[0];
  if (changedId && changedId !== "db-version" && versionList.length && !versionList.includes(version)) {
    version = pickLatestVersion(versionList);
  }
  fillCombo($("db-version"), versionList, version);
}

function renderDbHints(ctx) {
  dbContext = ctx;
  if (!ctx) return;
  $("db-breadcrumb").textContent =
    `${ctx.component} / ${ctx.part} / ${ctx.package} / ${ctx.operator || "?"} / ${ctx.version} · ${ctx.model}`;
  $("db-model").value = ctx.model || "";
  if (!$("db-year").value && ctx.year) $("db-year").value = ctx.year;
  let photo = ctx.photo_example || "";
  if (/\/ORT\//i.test(photo) && railType && railType !== "opamp") {
    photo += " (OpAmp default -- Apply campaign)";
  }
  $("db-path-hint").textContent = `Photos: ${photo}`;
  $("db-excel-hint").textContent = `Lab report: ${ctx.lab_report}`;
  $("results-db-hint").textContent =
    `Lab report: ${ctx.lab_report} · sessions: ${ctx.sessions}`;
  if ($("central-db-hint") && ctx.test_database_root) {
    $("central-db-hint").textContent =
      `Central DB (${ctx.cloud_kind || "local"}): ${ctx.test_database_root}`;
  }
  const n = ctx.sample_size || 4;
  $("unit").max = n;
  document.querySelectorAll(".dut-cb").forEach((cb) => {
    const v = Number(cb.value);
    cb.disabled = v > n;
    if (v > n) cb.checked = false;
  });
  refreshTagsUI();
}

async function pollEvents() {
  try {
    const events = await rpc("get_events");
    for (const ev of events || []) {
      if (ev.type === "log") log(ev.payload?.text || "");
      if (ev.type === "timeline") renderTimeline(ev.payload);
      if (ev.type === "progress") {
        if (ev.payload.status === "waiting_operator") {
          setRunPill("wait");
        } else if (ev.payload.status === "running") {
          if (!pendingPrompt) setRunPill("run");
        }
        if (ev.payload.test_id && ev.payload.status === "running" && !ev.payload.substep) {
          if (ev.payload.test_id !== activeSubstepTestId) {
            substepState = {};
            activeSubstepTestId = ev.payload.test_id;
          }
        }
        if (ev.payload.substep && ev.payload.test_id) {
          updateSubstepChip(
            ev.payload.test_id,
            ev.payload.substep,
            ev.payload.status
          );
        }
        if (
          ev.payload.test_id &&
          (ev.payload.status === "pass" || ev.payload.status === "fail")
        ) {
          substepState = {};
          activeSubstepTestId = "";
          if (lastTimeline) renderStepStatusBar(lastTimeline);
        }
      }
      if (ev.type === "operator_prompt") showModal(ev.payload);
    }
    if (runPollActive || pendingPrompt) {
      await syncPendingGate({ autoOpen: true });
      await syncRunState();
    }
  } catch (_) {
    /* worker may be starting */
  }
}

function formatGain(g) {
  if (g === null || g === undefined) return "n/a";
  return String(g);
}

function renderGainBoards(modes) {
  const box = $("gain-boards");
  if (!box) return;
  if (activeFamily !== "opamp") {
    box.innerHTML = "";
    return;
  }
  const list = modes || [];
  const general = list.filter((m) => (m.board_class || "general") === "general" && m.gain != null && m.mode !== "ATE");
  const research = list.filter((m) => m.board_class === "research");
  const chip = (m, kind) => `
      <div class="gain-chip ${kind}" title="RF=${m.rf || "?"} RI=${m.ri || "?"}">
        <strong>${m.mode} → ${formatGain(m.gain)}</strong>
        <span>${m.label || ""} · locked</span>
      </div>`;
  box.innerHTML =
    `<div class="gain-section-label">General testboard</div>` +
    general.map((m) => chip(m, "general")).join("") +
    (research.length
      ? `<div class="gain-section-label">VOS research only (not general board)</div>` +
        research.map((m) => chip(m, "research")).join("")
      : "");
}

async function loadFixtureCatalog() {
  try {
    const part = (dbContext && dbContext.part_key) || "rs622";
    fixtureCatalog = await rpc("list_fixture_modes", { part });
  } catch (_) {
    fixtureCatalog = [];
  }
  renderGainBoards(fixtureCatalog);
}

async function loadDb() {
  dbTree = await rpc("list_db_tree");
  const info = await rpc("get_db_context");
  const ctx = info.context || {};
  const saved = readSavedCampaign();
  const sel = {
    component: ctx.component || saved.component,
    part: ctx.part || saved.part,
    package: ctx.package || saved.package,
    operator: ctx.operator || saved.operator || writeOperatorLabel() || "Eugene",
    version: ctx.version || saved.version,
    model: ctx.model || saved.model,
    year: ctx.year || saved.year || $("db-year")?.value || "2026",
  };
  paintCampaign(sel);
  renderDbHints({ ...saved, ...ctx, ...sel });
  try {
    await applyDb();
  } catch (e) {
    log(`Campaign restore warn: ${e.message}\n`);
  }
  if (info.guide?.orchestration) {
    log("DB guide:\n" + info.guide.orchestration.map((s) => `  ${s}`).join("\n") + "\n");
  }
}

let campaignTags = [];
let campaignBoards = [];
let boardVocab = [];

function renderTagChips(el, tags, { removable = false, compact = false } = {}) {
  if (!el) return;
  el.innerHTML = "";
  const list = tags || [];
  const expanded = el.dataset.expanded === "1";
  const showAll = !compact || expanded || list.length <= 1;
  const visible = showAll ? list : list.slice(-1);
  for (const t of visible) {
    const chip = document.createElement("span");
    chip.className = "tag-chip";
    chip.textContent = t;
    chip.setAttribute("aria-label", t);
    if (removable) {
      const x = document.createElement("button");
      x.type = "button";
      x.className = "tag-chip-x";
      x.innerHTML = '<span aria-hidden="true">x</span>';
      x.setAttribute("aria-label", `Remove ${t}`);
      x.title = "Remove";
      x.onclick = () => {
        campaignTags = campaignTags.filter((v) => v !== t);
        campaignLabels = (campaignLabels || []).filter((lab) => labelToken(lab) !== t);
        if (t.startsWith("board:")) {
          const b = t.slice(6);
          campaignBoards = campaignBoards.filter((v) => v !== b);
        }
        paintTagsEditor();
        saveCampaignLabels().catch((e) => log(`Labels: ${e.message}\n`));
      };
      chip.appendChild(x);
    }
    el.appendChild(chip);
  }
  if (compact && list.length > 1 && !expanded) {
    const more = document.createElement("button");
    more.type = "button";
    more.className = "tag-chip tag-chip-more";
    more.textContent = `+${list.length - 1} more`;
    more.title = "Show all tags";
    more.onclick = () => {
      el.dataset.expanded = "1";
      paintTagsEditor();
    };
    el.appendChild(more);
  }
  if (compact && expanded && list.length > 1) {
    const hide = document.createElement("button");
    hide.type = "button";
    hide.className = "tag-chip tag-chip-more";
    hide.textContent = "hide";
    hide.onclick = () => {
      el.dataset.expanded = "0";
      paintTagsEditor();
    };
    el.appendChild(hide);
  }
  if (!list.length) {
    const empty = document.createElement("span");
    empty.className = "hint";
    empty.textContent = "none";
    el.appendChild(empty);
  }
}

function labelToken(lab) {
  const k = String((lab && lab.kind) || "tag");
  const v = String((lab && lab.value) || "");
  return k === "tag" ? v : `${k}:${v}`;
}

function fillLabelValueSelect() {
  const kindEl = $("setup-label-kind");
  const valEl = $("setup-label-value");
  if (!valEl) return;
  const kind = (kindEl && kindEl.value) || "board";
  const vals = (labelValueVocab[kind] || []).slice();
  fillCombo(valEl, vals, valEl.value || "");
}

function fillLabelKindSelect() {
  const el = $("setup-label-kind");
  if (!el) return;
  const kinds = labelKindVocab.length ? labelKindVocab : [
    { id: "board", label: "Board" },
    { id: "board_type", label: "Board type" },
    { id: "tag", label: "Tag" },
    { id: "task", label: "Task" },
  ];
  const ids = kinds.map((k) => k.id || k);
  fillCombo(el, ids, el.value || ids[0] || "board");
  fillLabelValueSelect();
  fillLabelScopeSelect();
}

function fillLabelScopeSelect() {
  const el = $("label-scope");
  if (!el) return;
  const opts = ["this campaign", "this class", "all products"];
  const cur = el.value && opts.includes(el.value) ? el.value : (el.value || "this campaign");
  fillCombo(el, opts, cur);
}

function labelRememberScope() {
  const raw = String(($("label-scope") && $("label-scope").value) || "campaign").trim().toLowerCase();
  if (raw.includes("class") || raw === "family") return "family";
  if (raw.includes("all")) return "all";
  return "campaign";
}

function paintTagsEditor() {
  renderTagChips($("db-tag-chips"), campaignTags, { removable: true, compact: true });
  renderTagChips($("tags-editor-chips"), campaignTags, { removable: true, compact: false });
  const setup = $("setup-label-chips");
  if (setup) {
    setup.innerHTML = "";
    setup.classList.add("hidden");
  }
}

async function refreshTagsUI() {
  try {
    const data = await rpc("list_tags");
    campaignTags = Array.isArray(data.tags) ? data.tags.slice() : [];
    campaignBoards = Array.isArray(data.boards) ? data.boards.slice() : [];
    campaignLabels = Array.isArray(data.labels) ? data.labels.slice() : [];
    boardVocab = Array.isArray(data.boards_vocab) ? data.boards_vocab.slice() : [];
    labelKindVocab = Array.isArray(data.kinds) ? data.kinds.slice() : [];
    labelValueVocab = (data.label_values && typeof data.label_values === "object") ? data.label_values : {};
    const sel = $("tag-board-select");
    if (sel) fillCombo(sel, boardVocab.length ? boardVocab : [], sel.value || "");
    const tagIn = $("db-tag-input");
    if (tagIn) {
      if (document.activeElement === tagIn) {
        comboStore["db-tag-input"] = tagComboValues();
        if (comboOpenId === "db-tag-input") renderComboMenu();
      } else {
        fillCombo(tagIn, tagComboValues(), "");
        tagIn.value = "";
        syncComboChrome(tagIn);
      }
    }
    fillLabelKindSelect();
    paintTagsEditor();
    if ($("tags-path-hint")) {
      $("tags-path-hint").textContent =
        `TAGS.txt: ${data.tags_txt || "—"} · yaml: ${data.tags_yaml || "—"} · ${railType || "family"} labels`;
    }
  } catch (e) {
    if ($("tags-path-hint")) $("tags-path-hint").textContent = `Tags: ${e.message}`;
  }
}

async function applyDb() {
  const sel = currentDbSelection();
  const operator = sel.operator || requireWriteOperator();
  const existing = versionsForSel({ ...sel, operator });
  if (sel.version && !existing.includes(sel.version)) {
    try {
      await rpc("ensure_version", {
        component: sel.component,
        part: sel.part,
        package: sel.package,
        operator,
        version: sel.version,
        copy_from_version: (dbContext && dbContext.version) || existing[existing.length - 1] || "",
        sample_size: Number((dbContext && dbContext.sample_size) || 4),
        open_folder: false,
        apply: false,
      });
      dbTree = await rpc("list_db_tree");
      mergeInventoryIntoTree();
    } catch (e) {
      const msg = String((e && e.message) || e);
      if (!/already exists/i.test(msg)) log(`Version: ${msg}\n`);
    }
  }
  const res = await rpc("set_db_context", {
    component: sel.component,
    part: sel.part,
    package: sel.package,
    operator,
    version: sel.version,
    model: sel.model || undefined,
    year: sel.year || undefined,
  });
  renderDbHints(res.context);
  saveCampaign({ ...sel, operator, ...(res.context || {}) });
  log(`Campaign applied: ${res.context.root}\n`);
  if (res.created?.length) {
    log(`Created ${res.created.length} folder(s) under DUT tree\n`);
  }
  if (res.family_error) {
    log(`${res.family_error}\n`);
  }
  if ("family" in res) updateFamilyChrome(res.family);
  await loadOwners();
  await loadParamDefaults();
  await loadFixtureCatalog();
  await loadTests();
  await loadMappedCoverage();
  await refreshDetectedPanel();
  await refreshTagsUI();
  syncOwnerSelectFromFolder(operator);
}

function fillDetectFamilySelect(preserveUser) {
  const el = $("detect-family");
  if (!el) return;
  const fams = (knownFamilies || []).filter((f) => f !== "lim");
  const fallback = fams.length ? fams : ["opamp", "logic", "switch"];
  const keep = el.value;
  let cur = (activeFamily && fallback.includes(activeFamily)) ? activeFamily : (fallback[0] || "logic");
  if (preserveUser && keep && fallback.includes(keep)) cur = keep;
  fillSelect(el, fallback, cur);
}

function fillDetectCopyFrom() {
  const el = $("detect-copy-from");
  if (!el) return;
  const sel = currentDbSelection();
  const partsObj = ((dbTree.components || {})[sel.component] || {}).parts || {};
  const parts = Object.keys(partsObj).filter((p) => p !== sel.part);
  const opts = [""].concat(parts);
  el.innerHTML = "";
  opts.forEach((p) => {
    const o = document.createElement("option");
    o.value = p;
    o.textContent = p || "-- same-family part --";
    el.appendChild(o);
  });
}

async function refreshDetectedPanel(opts) {
  const box = $("detected-tests");
  const hint = $("detect-hint");
  if (!box) return;
  fillDetectFamilySelect(!!(opts && opts.preserveWrap));
  fillDetectCopyFrom();
  try {
    const res = await rpc("list_detected_tests", { family: activeFamily });
    const rows = res.detected || [];
    box.innerHTML = "";
    if (!rows.length) {
      box.innerHTML = '<p class="hint">No unmatched def test_* (or golden roots missing).</p>';
    } else {
      rows.slice(0, 80).forEach((r) => {
        const div = document.createElement("div");
        div.className = "test-item";
        const blocked = !!r.blocked;
        const status = blocked ? "blocked" : "ready";
        const reason = blocked ? (r.blocked_reason || "blocked") : "wrap-ready";
        const shortFile = String(r.file || "").replace(/\\/g, "/").split("/").slice(-2).join("/");
        div.innerHTML =
          `<label style="display:flex;gap:8px;align-items:flex-start;width:100%">` +
          `<input type="checkbox" class="detect-cb" data-id="${r.id}" data-fn="${r.fn || ""}" ` +
          `data-file="${encodeURIComponent(r.file || "")}" ${blocked ? "disabled" : ""} />` +
          `<span><strong>${r.id}</strong> <span class="hint">(${status})</span><br/>` +
          `<span class="hint">${shortFile}:${r.lineno || "?"} — ${reason}</span></span></label>`;
        box.appendChild(div);
      });
    }
    const missing = (res.roots || []).filter((x) => !x.exists).map((x) => x.label || x.path);
    if (hint) {
      hint.textContent =
        `Scanned ${res.scanned_files || 0} files → ${res.count || 0} unmatched` +
        (res.blocked_count ? ` (${res.blocked_count} blocked)` : "") +
        (missing.length ? `. Missing golden: ${missing.join(", ")}` : ".");
    }
  } catch (e) {
    box.innerHTML = "";
    if (hint) hint.textContent = `Detect scan: ${e.message}`;
  }
}

async function loadTests() {
  const tests = await rpc("list_tests");
  allTests = tests;
  const box = $("test-list");
  box.innerHTML = "";
  if (!tests.length) {
    const stub =
      activeFamily === "level"
        ? "No enabled tests for this Level part. Pick RS0204 for the dual-rail suite."
          : activeFamily === "logic"
          ? "Logic family loaded -- no enabled tests for this part/campaign."
          : (activeFamily === "lim" || activeFamily === "switch")
            ? "Analog Switch family loaded -- no enabled tests for this part/campaign."
            : activeFamily === "power"
              ? "Power / LDO family loaded -- no enabled tests for this part/campaign."
            : "No tests registered for this family.";
    box.innerHTML = `<p class="hint">${stub}</p>`;
    renderRunPlans();
    return;
  }
  const preferred = new Set();

  const groups = new Map();
  for (const t of tests) {
    const mode = t.fixture_mode || "OTHER";
    if (!groups.has(mode)) groups.set(mode, []);
    groups.get(mode).push(t);
  }

  // Preserve fixture catalog order when known; unknown modes append
  const modeOrder = (fixtureCatalog || []).map((m) => m.mode);
  const modes = [
    ...modeOrder.filter((m) => groups.has(m)),
    ...[...groups.keys()].filter((m) => !modeOrder.includes(m)),
  ];

  for (const mode of modes) {
    const items = sortTestsForPlan(groups.get(mode) || []);
    const cat = fixtureCatalog.find((m) => m.mode === mode);
    const isResearch = (cat?.board_class || (mode === "G201" || mode === "G1001" ? "research" : "general")) === "research";
    const gainTxt = cat && cat.gain != null ? ` · gain ${formatGain(cat.gain)}` : "";
    const label = cat?.label || mode;
    const wrap = document.createElement("details");
    wrap.className = "fixture-group" + (isResearch ? " research" : "");
    wrap.open = false;
    wrap.innerHTML = `<summary class="fixture-group-title">${mode}${gainTxt} — ${label}</summary>`;
    const grid = document.createElement("div");
    grid.className = "fixture-group-tests";
    for (const t of items) {
      const id = `t-${t.id}`;
      const checked = !isResearch && preferred.has(t.id) ? "checked" : "";
      const tag = t.short_tag || t.id;
      const instr = (t.required_instruments || []).join("+") || "MSO+PSU+AWG";
      const specRows = (t.specs || []).map((s) => {
        const sid = s.id || "";
        const unspec = s.min == null && s.max == null;
        const lim = unspec
          ? "unspec"
          : [s.min != null ? `min ${s.min}` : "", s.max != null ? `max ${s.max}` : ""].filter(Boolean).join(" ");
        return `<div class="test-spec-row"><span class="mode-tag">${sid}</span> ${passModeSelect(sid, s.pass_mode, "test-pass-mode")} <span class="hint">${lim}</span></div>`;
      }).join("");
      const info = (t.info && (t.info.description || t.info.title)) || t.notes || "";
      const specLine = specRows || "<span class=\"mode-tag\">datasheet unspec -- Results: Fetch limits</span>";
      grid.innerHTML += `
        <div class="test-item">
          <label class="check" for="${id}">
            <input id="${id}" type="checkbox" value="${t.id}" ${checked} />
            <span><strong>${tag}</strong> — ${t.label}</span>
          </label>
          <div class="test-spec-block">${specLine}<br/><span class="mode-tag">${t.fixture_mode} · ${instr}${isResearch ? " · research" : ""}</span>${info ? `<br/><span class="hint">${info}</span>` : ""}</div>
        </div>`;
    }
    wrap.appendChild(grid);
    box.appendChild(wrap);
  }
  renderRunPlans();
  document.querySelectorAll(".test-item input[type=checkbox]").forEach((inp) => {
    inp.addEventListener("change", () => {
      renderRunPlans();
      applyTestDefaults(false);
    });
  });
  document.querySelectorAll(".test-pass-mode").forEach((sel) => {
    sel.addEventListener("click", (ev) => ev.stopPropagation());
  });
  wirePassModeSync();
  applyTestDefaults(false);
}

async function refreshSession() {
  try {
    const st = await rpc("session_status");
    sessionOpen = !!st.open;
    setTiles(st.mapping || {});
    $("btn-start").disabled = !sessionOpen;
    $("session-hint").textContent = sessionOpen
      ? `Session open: ${Object.keys(st.mapping || {}).join(", ")}`
      : "Init = Discover → Open Session";
    if (st.db) renderDbHints(st.db);
    if (st.timeline) renderTimeline(st.timeline);
  } catch (e) {
    $("session-hint").textContent = `Worker offline — start ate worker. (${e.message})`;
  }
}

document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => switchPage(t.dataset.page));
});

const familyRail = document.querySelector(".family-rail");
if (familyRail) {
  familyRail.addEventListener("click", async (ev) => {
    const btn = ev.target.closest(".family-btn");
    if (!btn) return;
    const family = btn.dataset.family;
    if (!family) return;
    const sameRail = family === railType;
    railType = family;
    if (!(inventoryRows || []).length) {
      await loadInventory();
    } else {
      paintInventory(family);
    }
    if ($("np-category")) {
      const catId = typeForFamily(family);
      if (catId) $("np-category").value = catId;
    }
    try {
      mergeInventoryIntoTree();
      const component = componentFromFamily(family);
      const fromInv = campaignFromInventory(family);
      const last = readSavedByFamily(family);
      const lastOk = !!(last && last.component === component && liveKeys(
        (((dbTree.components || {})[last.component] || {}).parts) || {}
      ).includes(last.part));
      const sel = lastOk
        ? last
        : (fromInv || firstCampaignInComponent(component));
      const wantComp = (sel && sel.component) || component;
      if (sameRail && $("db-component") && $("db-component").value === wantComp && sel && $("db-part") && $("db-part").value === sel.part) {
        paintBrand(railType);
        return;
      }
      if (sel) {
        if ($("np-part")) $("np-part").value = sel.part || "";
        if ($("np-package")) $("np-package").value = sel.package || "";
        if ($("np-model")) $("np-model").value = sel.model || sel.part || "";
        paintCampaign(sel);
        await applyDb();
      } else {
        const firstInv = (inventoryRows || []).find((r) => String(r.category || "") === typeForFamily(family));
        const suite = suiteForRow(firstInv) || family;
        await switchFamily(suite);
      }
      paintBrand(railType);
      await refreshTagsUI();
    } catch (e) {
      alert(e.message);
    }
  });
}

["db-component", "db-part", "db-package", "db-operator", "db-version"].forEach((id) => {
  const el = $(id);
  if (!el) return;
  el.addEventListener("change", async () => {
    if (!String(($("db-component") && $("db-component").value) || "").trim()) return;
    if (!String(($("db-part") && $("db-part").value) || "").trim()) return;
    refreshDbCascades(currentDbSelection(), id);
    if ((id === "db-component" || id === "db-part") && $("db-model")) {
      $("db-model").value = "";
    }
    // Component change also switches family suite in the same click
    if (id === "db-component") {
      const fam = familyFromComponent(($("db-component") && $("db-component").value) || "");
      if (fam) {
        railType = fam;
        paintInventory(fam);
        paintBrand(fam);
      }
      if (fam && fam !== activeFamily) {
        try {
          await switchFamily(fam);
        } catch (e) {
          log(`Family switch: ${e.message}\n`);
        }
      }
    }
    const sel = currentDbSelection();
    if (sel.operator) syncOwnerSelectFromFolder(sel.operator);
    if ($("db-breadcrumb") && sel.component) {
      $("db-breadcrumb").textContent =
        `${sel.component} / ${sel.part} / ${sel.package} / ${sel.operator || "?"} / ${sel.version}` +
        (sel.model ? ` · ${sel.model}` : "");
    }
    if (!campaignKnown(sel)) {
      log("Typed new campaign path -- click Apply campaign to create folders\n");
      return;
    }
    log("Campaign path updated -- click Apply campaign to load tests / folders\n");
  });
});

$("btn-apply-db").onclick = async () => {
  try {
    await applyDb();
  } catch (e) {
    alert(e.message);
  }
};

async function savePersonFromSetup() {
  const label = requireWriteOperator();
  const sel = currentDbSelection();
  const res = await rpc("upsert_owner", {
    label,
    component: sel.component,
    part: sel.part,
    package: sel.package,
    family: railType || "",
    task: sel.part,
    update_defaults: true,
  });
  ownersList = res.owners || ownersList;
  if (res.owner && res.owner.id) saveOwner(res.owner.id);
  await loadOwners();
  syncOwnerSelectFromFolder(label);
  const row = (res.owner || {});
  if ($("person-hint")) {
    $("person-hint").textContent =
      `${res.action || "saved"} ${row.label || label}` +
      (row.task ? ` · task ${row.task}` : "") +
      " (owners.yaml). Apply campaign to create folders.";
  }
  log(`Person ${res.action || "saved"}: ${row.label || label}\n`);
}

if ($("btn-save-person")) {
  $("btn-save-person").onclick = async () => {
    try {
      await savePersonFromSetup();
    } catch (e) {
      alert(e.message);
    }
  };
}
if ($("btn-forget-person")) {
  $("btn-forget-person").onclick = async () => {
    try {
      const label = (($("db-operator") && $("db-operator").value) || "").trim();
      if (!label || label.toLowerCase() === "all") {
        throw new Error("Pick a person (not All) to forget");
      }
      if (!confirm(`Forget ${label} from owners.yaml? Version folders on disk stay.`)) return;
      const res = await rpc("remove_owner", { owner: label });
      ownersList = res.owners || [];
      await loadOwners();
      const fallback = ownersList.find((o) => o.id === "eugene") || ownersList.find((o) => o.id !== "all");
      if ($("owner-select") && fallback) {
        $("owner-select").value = fallback.id;
        saveOwner(fallback.id);
      }
      if ($("person-hint")) {
        $("person-hint").textContent = `Forgot ${label} in yaml. Folders under ${label} were not deleted.`;
      }
      log(`Forgot person ${label} (yaml only)\n`);
    } catch (e) {
      alert(e.message);
    }
  };
}

async function saveTestParamsOverlay() {
  const pass_mode = {};
  document.querySelectorAll("#logic-dc-body .logic-dc-mode").forEach((sel) => {
    const id = sel.getAttribute("data-id");
    if (id && sel.value) pass_mode[id] = sel.value;
  });
  document.querySelectorAll(".test-pass-mode").forEach((sel) => {
    const id = sel.getAttribute("data-id");
    if (id && sel.value) pass_mode[id] = sel.value;
  });
  const blob = { pass_mode };
  const logicPanel = $("panel-logic-dc");
  const logicOpen = logicPanel && !logicPanel.classList.contains("hidden");
  const vccInput = $("logic-dc-vcc") || $("logic-dc-vcc-list");
  if (logicOpen && vccInput) {
    const vccRaw = (vccInput.value || "").trim();
    blob.vcc_list = vccRaw
      ? vccRaw.split(/[,\s]+/).map((x) => Number(x)).filter((n) => Number.isFinite(n))
      : [];
  }
  const epsAInput = $("logic-dc-stable-eps-a");
  if (logicOpen && epsAInput) {
    const raw = (epsAInput.value || "").trim();
    if (!raw || raw.toLowerCase() === "null" || raw.toLowerCase() === "none") {
      blob.stable_eps_A = null;
    } else {
      const n = Number(raw);
      if (!Number.isFinite(n)) {
        throw new Error("stable_eps_A must be a number in amps, or blank for null (NON_TIGHT)");
      }
      blob.stable_eps_A = n;
    }
  }
  if (logicOpen && $("logic-dc-fixed-points")) {
    const grid = collectVccGridFromUi();
    blob.vcc_grid = grid;
    blob.vcc_plan = grid;
    blob.vcc_list = mergeVccGridJs(grid);
    blob.pass_mode = blob.pass_mode || {};
    const dc = paramCatalog.logic_dc || {};
    if (!dc.schmitt && !isSchmittGrid(dc)) {
      if (!blob.pass_mode.VIH) blob.pass_mode.VIH = "min_only";
      if (!blob.pass_mode.VIL) blob.pass_mode.VIL = "max_only";
    }
    const nEl = $("logic-dc-n");
    if (nEl) {
      const n = Number(nEl.value);
      if (Number.isFinite(n) && n >= 1) blob.sample_size = Math.trunc(n);
    }
    const dualEl = $("logic-dc-dual-continue");
    if (dualEl) {
      blob.recipe = blob.recipe || {};
      blob.recipe.dual_channel_continue = !!dualEl.checked;
      if (dualEl.checked) blob.recipe.channels = ["CHA", "CHB"];
    }
  }
  const res = await rpc("save_test_params", { test_params: blob });
  const hint = $("logic-dc-hint");
  if (hint) hint.textContent = `Saved ${res.path || "_manifest/test_params.yaml"}`;
  log(`Saved Version overlay test_params.yaml\n`);
  await loadParamDefaults();
  await loadTests();
  return res;
}

if ($("btn-save-test-params")) {
  $("btn-save-test-params").onclick = async () => {
    try {
      await saveTestParamsOverlay();
    } catch (e) {
      alert(e.message);
    }
  };
}
if ($("btn-save-pass-mode")) {
  $("btn-save-pass-mode").onclick = async () => {
    try {
      await saveTestParamsOverlay();
    } catch (e) {
      alert(e.message);
    }
  };
}

async function saveCampaignLabels() {
  const payload = (campaignLabels && campaignLabels.length)
    ? { labels: campaignLabels, remember_scope: labelRememberScope() }
    : { tags: campaignTags, boards: campaignBoards, remember_scope: labelRememberScope() };
  const res = await rpc("save_tags", payload);
  campaignTags = res.tags || campaignTags;
  campaignBoards = res.boards || campaignBoards;
  campaignLabels = Array.isArray(res.labels) ? res.labels : campaignLabels;
  paintTagsEditor();
  if (res.excel_status === "ok") {
    log(`Tags in Excel ${res.excel_cell || res.excel}\n`);
  } else if (res.excel_status === "locked") {
    log("Excel locked - close the lab workbook to stamp tags\n");
  }
  return res;
}

function addSetupLabel(kind, value) {
  const k = String(kind || "tag").trim();
  const v = String(value || "").trim();
  if (!k || !v || v.startsWith("(")) return;
  const lab = { kind: k, value: v };
  const tok = labelToken(lab);
  if ((campaignLabels || []).some((x) => labelToken(x) === tok)) return;
  campaignLabels = (campaignLabels || []).concat([lab]);
  if (!campaignTags.includes(tok)) campaignTags.push(tok);
  if (k === "board" && !campaignBoards.includes(v)) campaignBoards.push(v);
  paintTagsEditor();
  saveCampaignLabels().catch((e) => alert(e.message));
}

if ($("setup-label-kind")) {
  $("setup-label-kind").onchange = () => fillLabelValueSelect();
}
if ($("btn-setup-add-label")) {
  $("btn-setup-add-label").onclick = () => {
    let kind = (($("setup-label-kind") && $("setup-label-kind").value) || "board").trim();
    let value = (($("setup-label-value") && $("setup-label-value").value) || "").trim();
    if (value.includes(":")) {
      const i = value.indexOf(":");
      kind = value.slice(0, i).trim() || kind;
      value = value.slice(i + 1).trim();
    }
    addSetupLabel(kind, value);
    if ($("setup-label-value")) $("setup-label-value").value = "";
  };
}
if ($("btn-tag-add-board")) {
  $("btn-tag-add-board").onclick = () => {
    const b = ($("tag-board-select") && $("tag-board-select").value) || "";
    if (!b || b.startsWith("(")) return;
    addSetupLabel("board", b);
  };
}
if ($("btn-tag-add-free")) {
  $("btn-tag-add-free").onclick = () => {
    const t = (($("tag-free") && $("tag-free").value) || "").trim();
    if (!t) return;
    addCampaignTagFromText(t);
    if ($("tag-free")) $("tag-free").value = "";
  };
}
if ($("tag-free")) {
  $("tag-free").addEventListener("keydown", (ev) => {
    if ((ev.key === " " || ev.key === "," || ev.key === "Enter") && String($("tag-free").value || "").trim()) {
      ev.preventDefault();
      addCampaignTagFromText($("tag-free").value);
      $("tag-free").value = "";
    }
  });
}
if ($("btn-tags-save")) {
  $("btn-tags-save").onclick = async () => {
    try {
      const res = await rpc("save_tags", {
        tags: campaignTags,
        boards: campaignBoards,
        labels: campaignLabels,
        remember_scope: labelRememberScope(),
      });
      campaignTags = res.tags || campaignTags;
      campaignBoards = res.boards || campaignBoards;
      campaignLabels = Array.isArray(res.labels) ? res.labels : campaignLabels;
      paintTagsEditor();
      if ($("tags-path-hint")) {
        $("tags-path-hint").textContent =
          res.excel_status === "ok"
            ? `Saved TAGS.txt: ${res.tags_txt} · Excel ${res.excel_cell}`
            : `Saved TAGS.txt: ${res.tags_txt}`;
      }
      log(`Tags saved (${(res.tags || []).length})\n`);
    } catch (e) {
      alert(e.message);
    }
  };
}
if ($("btn-tags-reload")) {
  $("btn-tags-reload").onclick = () => refreshTagsUI().catch((e) => alert(e.message));
}
if ($("btn-tags-clear")) {
  $("btn-tags-clear").onclick = async () => {
    if (!confirm("Clear all tags on this campaign? TAGS.txt and yaml update. Excel stamps if the workbook is closed.")) return;
    try {
      campaignTags = [];
      campaignBoards = [];
      campaignLabels = [];
      await saveCampaignLabels();
      log("Tags cleared\n");
    } catch (e) {
      alert(e.message);
    }
  };
}
if ($("btn-tags-import")) {
  $("btn-tags-import").onclick = async () => {
    try {
      const src = (($("tag-import-root") && $("tag-import-root").value) || "").trim();
      if (!src) {
        alert("Paste a campaign root path");
        return;
      }
      const res = await rpc("import_tags", { from_root: src, merge: true });
      campaignTags = res.tags || [];
      campaignBoards = res.boards || [];
      campaignLabels = Array.isArray(res.labels) ? res.labels : campaignLabels;
      paintTagsEditor();
      log(`Imported tags from ${src}\n`);
    } catch (e) {
      alert(e.message);
    }
  };
}
if ($("btn-tags-filter")) {
  $("btn-tags-filter").onclick = async () => {
    try {
      const tag = (($("tag-filter") && $("tag-filter").value) || "").trim();
      if (!tag) return;
      const res = await rpc("filter_campaigns_by_tag", {
        tag,
        component: ($("db-component") && $("db-component").value) || "",
      });
      const ul = $("tag-filter-results");
      if (!ul) return;
      ul.innerHTML = "";
      for (const c of res.campaigns || []) {
        const li = document.createElement("li");
        li.textContent = `${c.component}/${c.part}/${c.package}/${c.operator}/${c.version}`;
        li.title = c.root;
        ul.appendChild(li);
      }
      if (!(res.campaigns || []).length) {
        const li = document.createElement("li");
        li.textContent = "No campaigns matched";
        ul.appendChild(li);
      }
    } catch (e) {
      alert(e.message);
    }
  };
}

$("btn-open-db").onclick = async () => {
  try {
    await rpc("open_db_root");
  } catch (e) {
    alert(e.message);
  }
};

$("btn-open-sessions").onclick = async () => {
  try {
    await rpc("open_sessions");
  } catch (e) {
    alert(e.message);
  }
};

if ($("btn-open-central")) {
  $("btn-open-central").onclick = async () => {
    try {
      await rpc("open_central_db");
    } catch (e) {
      alert(e.message);
    }
  };
}

$("btn-import-xlsx").onclick = async () => {
  try {
    const path = ($("db-xlsx-path") && $("db-xlsx-path").value.trim()) || "";
    const res = await rpc("import_workbook", path ? { source_path: path } : { pick: true });
    if (res.workbook) {
      $("db-excel-hint").textContent = "Lab report: " + res.workbook;
    }
    if (res.context) renderDbHints(res.context);
    log("Imported workbook: " + (res.workbook || "?") + "\n");
    log("sheet_map: " + res.sheet_map_action + " — " + (res.note || "") + "\n");
    if (res.sheets && res.sheets.length) {
      log("Sheets: " + res.sheets.join(", ") + "\n");
    }
  } catch (e) {
    alert(e.message);
  }
};

if ($("btn-import-family")) {
  $("btn-import-family").onclick = async () => {
    try {
      const source = ($("db-family-source") && $("db-family-source").value.trim()) || "";
      const family = ($("db-family-key") && $("db-family-key").value.trim()) || "";
      if (!source) {
        alert("Paste a GitHub URL / owner/repo, or a local family folder.");
        return;
      }
      const res = await rpc("import_family", { source, family });
      renderFamilyRail(res.known || [], res.labels || {});
      if (res.family) {
        log("Imported family: " + res.family + " -> " + (res.dest || "") + "\n");
        log((res.note || "") + "\n");
        if (res.load_error) log("Load warning: " + res.load_error + "\n");
        if (res.copied) log("Copied: " + res.copied.join(", ") + "\n");
      }
      await syncFamilyFromWorker();
      if (res.family && res.family !== "opamp") {
        try { await switchFamily(res.family); } catch (_) { /* stay on current */ }
      }
    } catch (e) {
      alert(e.message);
    }
  };
}

$("btn-discover").onclick = async () => {
  try {
    const m = await rpc("discover");
    setTiles(m);
    log(`Discovered ${JSON.stringify(m)}\n`);
    await loadMappedCoverage();
  } catch (e) {
    alert(e.message);
  }
};

$("btn-open").onclick = async () => {
  try {
    const m = await rpc("open_session");
    setTiles(m);
    sessionOpen = true;
    $("btn-start").disabled = false;
    log(`Session open ${JSON.stringify(m)}\n`);
    if (m.golden_auto) {
      log(`Excel golden_auto/auto (pretty never auto): ${m.golden_auto}\n`);
    }
    const need = ["MSO", "PSU", "AWG"];
    const miss = need.filter((k) => !m[k]);
    if (miss.length) {
      alert(
        `Session open but missing: ${miss.join(", ")}\n\n` +
          "Close Ultra Sigma / other VISA apps, check DP832 USB+power, then Open Session again."
      );
    }
    await refreshSession();
    await loadMappedCoverage();
    if (!m.DMM) {
      log("DMM not in session -- OpAmp VOL and Logic IDD/VOUT/cap_load will fail until Discover finds it\n");
    }
  } catch (e) {
    alert(e.message);
  }
};

function shotFolderKey() {
  const ids = selectedTests();
  if (ids.includes("slew")) return "SlewRate";
  if (ids.includes("settling")) return "SettlingTime";
  if (ids.includes("gbw")) return "GBW";
  if (ids.includes("ort")) return "ORT";
  const first = ids[0];
  if (!first) return "ORT";
  const row = (allTests || []).find((t) => t.id === first);
  return (row && row.lab_sheet) || first;
}

function paintDemoTimeline(res) {
  const steps = res.steps || [];
  const n = steps.length;
  const now = new Date().toISOString();
  const entries = steps.map((s, i) => ({
    id: `demo-${i}`,
    kind: "test",
    label: `${s.fixture_mode ? s.fixture_mode + " · " : ""}${s.label || s.test_id}`,
    status: "done",
    test_id: s.test_id,
    finished_at: now,
    message: `DEMO mock ${(s.instruments || []).join("+") || "none"}`,
  }));
  renderTimeline({
    entries,
    done_count: n,
    total_count: n,
    progress_pct: n ? 100 : 0,
    finished_at: now,
    session_id: String(res.session || "").split(/[\\/]/).pop() || "demo",
  });
}

$("btn-shot").onclick = async () => {
  try {
    const r = await rpc("screenshot", { test_key: shotFolderKey() });
    log(`Screenshot: ${r.path}\n`);
    alert(`JPEG saved:\n${r.path}`);
  } catch (e) {
    alert(e.message);
  }
};

$("btn-folder").onclick = async () => {
  try {
    const duts = selectedDuts();
    await rpc("open_screenshots", {
      test_key: shotFolderKey(),
      unit_index: duts[0],
    });
  } catch (e) {
    alert(e.message);
  }
};

if ($("btn-tests-all")) {
  $("btn-tests-all").onclick = () => {
    document.querySelectorAll("#test-list .test-item input[type=checkbox]").forEach((i) => { i.checked = true; });
    renderRunPlans();
    applyTestDefaults(false);
  };
}
if ($("btn-tests-none")) {
  $("btn-tests-none").onclick = () => {
    document.querySelectorAll("#test-list .test-item input[type=checkbox]").forEach((i) => { i.checked = false; });
    renderRunPlans();
    applyTestDefaults(false);
  };
}

if ($("btn-new-product")) {
  $("btn-new-product").onclick = async () => {
    const part = ($("np-part") && $("np-part").value.trim()) || "";
    if (!part) return alert("Enter a part number we are testing");
    try {
      const operator = requireWriteOperator();
      const pkg = ($("np-package") && $("np-package").value.trim()) || "SOT23";
      const model = ($("np-model") && $("np-model").value.trim()) || part;
      const res = await rpc("ensure_product", {
        category: $("np-category") && $("np-category").value,
        part,
        package: pkg,
        model,
        operator,
        sample_size: Number($("np-sample") && $("np-sample").value) || 4,
        open_folder: true,
      });
      if ($("np-hint")) $("np-hint").textContent = `${res.note || ""} ${res.root || ""}`;
      log(`New product: ${res.root}\n${res.note || ""}\n`);
      if (res.loaded_family) updateFamilyChrome(res.loaded_family);
      dbTree = await rpc("list_db_tree");
      paintCampaign({
        component: res.component,
        part,
        package: pkg,
        operator: res.operator || operator,
        version: "Version_1",
        model,
        year: ($("db-year") && $("db-year").value) || "2026",
      });
      await applyDb();
    } catch (e) {
      alert(e.message);
    }
  };
}

if ($("btn-new-session")) {
  $("btn-new-session").onclick = async () => {
    try {
      requireWriteOperator();
      await applyDb();
      const label = ($("session-run-label") && $("session-run-label").value.trim()) || "";
      const res = await rpc("new_run_session", { run_label: label });
      log(`+ Session: ${res.session_id}\n${res.path || ""}\n${res.note || ""}\n`);
      if ($("session-hint")) {
        $("session-hint").textContent =
          `Last run record: ${res.session_id}. Discover → Open Session still required for instruments.`;
      }
    } catch (e) {
      alert(e.message);
    }
  };
}

if ($("btn-refresh-detected")) {
  $("btn-refresh-detected").onclick = async () => {
    try {
      await refreshDetectedPanel({ preserveWrap: true });
    } catch (e) {
      alert(e.message);
    }
  };
}

if ($("btn-copy-tests")) {
  $("btn-copy-tests").onclick = async () => {
    try {
      requireWriteOperator();
      const src = ($("detect-copy-from") && $("detect-copy-from").value) || "";
      const dest = ($("db-part") && $("db-part").value) || "";
      if (!src) return alert("Pick a same-family source part");
      if (!dest) return alert("Apply a campaign part first");
      const res = await rpc("enable_tests_on_part", {
        source_part: src,
        dest_part: dest,
      });
      log(`Copy tests ${src} → ${dest}: added ${(res.added || []).join(", ") || "(none new)"}\n`);
      await loadTests();
    } catch (e) {
      alert(e.message);
    }
  };
}

async function wrapSelectedDetected() {
  const fam = ($("detect-family") && $("detect-family").value) || activeFamily || "logic";
  const part = ($("db-part") && $("db-part").value) || "";
  const cbs = Array.from(document.querySelectorAll("#detected-tests .detect-cb:checked"));
  if (!cbs.length) {
    alert("Tick one or more wrap-ready detected tests");
    return;
  }
  for (const cb of cbs) {
    const file = decodeURIComponent(cb.dataset.file || "");
    const fn = cb.dataset.fn || "";
    const id = cb.dataset.id || "";
    const res = await rpc("wrap_detected_test", {
      file,
      fn,
      test_id: id,
      family: fam,
      enable_part: part,
    });
    log(`Wrap ${res.id} → ${res.module} (family ${res.family})\n`);
    if (res.loaded_family) updateFamilyChrome(res.loaded_family);
  }
  await loadTests();
  await refreshDetectedPanel({ preserveWrap: true });
}

// Click on detected panel: double-click row or use wrap via refresh button area
if ($("detected-tests")) {
  const wrapBtn = document.createElement("button");
  wrapBtn.type = "button";
  wrapBtn.id = "btn-wrap-detected";
  wrapBtn.className = "btn accent";
  wrapBtn.textContent = "Wrap + enable on part";
  wrapBtn.style.marginTop = "8px";
  wrapBtn.onclick = async () => {
    try {
      requireWriteOperator();
      await wrapSelectedDetected();
    } catch (e) {
      alert(e.message);
    }
  };
  const hint = $("detect-hint");
  if (hint && hint.parentNode) hint.parentNode.insertBefore(wrapBtn, hint);
}

if ($("btn-demo")) {
  $("btn-demo").onclick = async () => {
    try {
      requireWriteOperator();
      const ids = selectedTests();
      if (!ids.length) return alert("Select at least one test");
      await applyDb();
      const res = await rpc("run_demo", { test_ids: ids, params: params() });
      log(`DEMO: ${res.note || ""}\nSession: ${res.session || ""}\n`);
      (res.steps || []).forEach((s) => {
        const inst = (s.instruments || []).join("+") || "none";
        log(`  ${s.fixture_mode || "-"} ${s.test_id} -> ${inst} ${JSON.stringify(s.mock)}\n`);
      });
      await paintSessionReport();
      try {
        const exp = await rpc("export_datalog");
        log(`STS datalog: ${exp.pdf || exp.markdown || ""}\n`);
      } catch (e) {
        log(`STS export: ${e.message}\n`);
      }
      setRunPill("pass");
      paintDemoTimeline(res);
      switchPage("run");
    } catch (e) {
      alert(e.message);
    }
  };
}

$("btn-start").onclick = async () => {
  const ids = selectedTests();
  if (!ids.length) return alert("Select at least one test");
  const duts = selectedDuts();
  if (!duts.length) return alert("Select at least one DUT");
  if (!sessionOpen) return alert("Open Session first");
  if (runPollActive) return alert("Run already in progress");
  try {
    requireWriteOperator();
  } catch (e) {
    return alert(e.message);
  }
  try {
    await applyDb();
  } catch (_) {
    /* keep previous campaign if apply fails */
  }
  switchPage("run");
  $("timeline").innerHTML = "";
  $("history").innerHTML = "";
  $("step-status-bar").innerHTML = "";
  substepState = {};
  activeSubstepTestId = "";
  lastScrollId = "";
  gateQueue = [];
  updateGateDock(null);
  $("progress-bar").style.width = "0%";
  $("progress-meta").textContent = "starting…";
  $("next-banner").textContent = "Building plan…";
  setRunPill("running");
  runPollActive = true;
  try {
    await rpc("run_sequence_async", { test_ids: ids, params: params() });
    await waitForRunComplete();
    const results = await rpc("get_last_run_results");
    await paintSessionReport();
    let allOk = true;
    for (const r of results || []) {
      allOk = allOk && r.success;
    }
    try {
      const exp = await rpc("export_datalog");
      log(`STS datalog: ${exp.pdf || exp.html || ""}\n`);
    } catch (_) { /* keep table even if export fails */ }
    try {
      const tl = await rpc("get_timeline");
      if (tl) renderTimeline(tl);
    } catch (_) { /* ignore */ }
    setRunPill(allOk ? "pass" : "fail");
    switchPage("results");
  } catch (e) {
    setRunPill("fail");
    alert(e.message);
  } finally {
    runPollActive = false;
  }
};

async function waitForRunComplete() {
  for (let i = 0; i < 7200; i++) {
    const st = await rpc("session_status");
    if (!st.busy) return;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("Run timed out waiting for worker");
}

$("btn-stop").onclick = async () => {
  try {
    setRunPill("stopping");
    await rpc("stop");
    runPollActive = false;
    hideModal();
    gateQueue = [];
    updateGateDock(null);
    await syncRunState();
    log("STOP sent — bench safe idle, run cancelled\n");
    setRunPill("ready");
  } catch (e) {
    setRunPill("fail");
    alert(e.message);
  }
};

$("modal-continue").onclick = async () => {
  try {
    await respondContinue();
  } catch (e) {
    alert(e.message);
  }
};

$("modal-abort").onclick = async () => {
  if (!pendingPrompt) return;
  await rpc("operator_respond", { prompt_id: pendingPrompt.id, continue: false });
  hideModal();
};

if ($("gate-dock-btn")) {
  $("gate-dock-btn").onclick = async () => {
    const p = await syncPendingGate({ autoOpen: true });
    if (!p) alert("No pending operator action — test may still be running (check RUN bin).");
  };
}

document.addEventListener("keydown", (e) => {
  if (e.defaultPrevented) return;
  const tag = (e.target && e.target.tagName) || "";
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  if (e.key === "c" || e.key === "C") {
    if (pendingPrompt || gateQueue.length) {
      e.preventDefault();
      respondContinue().catch((err) => alert(err.message));
    }
  }
});

let layoutState = { test_key: "", cells: [] };
let runLedgerScope = "part";
let runLedgerBound = false;

function runWhen(s) {
  return String(s || "").replace("T", " ").slice(0, 19);
}

function fmtSpec(v) {
  if (v === null || v === undefined || v === "") return "";
  return String(v);
}

async function paintSessionReport() {
  const tb = $("results-table") && $("results-table").querySelector("tbody");
  if (!tb) return null;
  const doc = await rpc("get_session_report");
  tb.innerHTML = "";
  const steps = doc.steps || [];
  let n = 0;
  for (const s of steps) {
    const meas = Array.isArray(s.measurements) && s.measurements.length
      ? s.measurements
      : [{ id: "", result: s.success ? "pass" : "fail" }];
    for (const m of meas) {
      n += 1;
      const res = String((m && m.result) || (s.success ? "pass" : "fail"));
      tb.innerHTML += `<tr><td>${s.dut ?? ""}</td><td>${s.test_id || ""}</td><td>${(m && m.id) || ""}</td><td>${fmtSpec(m && m.pass_mode)}</td><td>${fmtSpec(m && m.min)}</td><td>${fmtSpec(m && m.max)}</td><td>${fmtSpec(m && m.typ)}</td><td>${fmtSpec(m && m.value)}</td><td>${res}</td><td>${s.summary || s.error || ""}</td></tr>`;
    }
  }
  if (!n) {
    tb.innerHTML = `<tr><td colspan="10">No session measurements yet -- START or DEMO</td></tr>`;
  }
  if ($("results-db-hint") && doc.identity) {
    const fail = (doc.header && doc.header.fail) || 0;
    $("results-db-hint").textContent =
      `Lab report: ${(doc.identity && doc.identity.lab_report) || ""} · pass ${(doc.header && doc.header.pass) || 0} / fail ${fail}`;
  }
  return doc;
}

async function loadRunLedger(scope) {
  const tb = $("run-ledger") && $("run-ledger").querySelector("tbody");
  const hint = $("run-ledger-hint");
  if (!tb) return;
  if (scope) runLedgerScope = scope;
  try {
    const res = await rpc("list_runs", { scope: runLedgerScope, limit: 80 });
    tb.innerHTML = "";
    const runs = res.runs || [];
    if (hint) {
      hint.textContent =
        `${res.count || 0} run(s) · ${res.cloud_kind || "local"} · ${res.root || ""}` +
        (res.truncated ? " (truncated)" : "");
    }
    if (!runs.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 6;
      td.textContent = "No session JSON yet -- START or DEMO writes sessions/";
      tr.appendChild(td);
      tb.appendChild(tr);
      return;
    }
    for (const r of runs) {
      const tr = document.createElement("tr");
      for (const text of [
        runWhen(r.started),
        r.operator || "?",
        r.part || "",
        r.version || "",
        `${r.pass || 0}/${r.fail || 0}`,
      ]) {
        const td = document.createElement("td");
        td.textContent = text;
        tr.appendChild(td);
      }
      const td = document.createElement("td");
      const mk = (label, act) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "btn ghost";
        b.textContent = label;
        b.dataset.act = act;
        b.dataset.path = r.path || "";
        b.dataset.root = r.campaign_root || "";
        b.dataset.component = r.component || "";
        b.dataset.part = r.part || "";
        b.dataset.package = r.package || "";
        b.dataset.operator = r.operator || "";
        b.dataset.version = r.version || "";
        b.dataset.model = r.model || "";
        return b;
      };
      td.appendChild(mk("Open", "open"));
      td.appendChild(mk("Apply", "apply"));
      td.appendChild(mk("Delete", "delete"));
      tr.appendChild(td);
      tb.appendChild(tr);
    }
    if (!runLedgerBound && tb) {
      runLedgerBound = true;
      tb.addEventListener("click", onRunLedgerClick);
    }
  } catch (e) {
    if (hint) hint.textContent = `Runs: ${e.message}`;
  }
}

async function onRunLedgerClick(ev) {
  const b = ev.target && ev.target.closest && ev.target.closest("button[data-act]");
  if (!b) return;
  const act = b.dataset.act;
  try {
    if (act === "open") {
      await rpc("open_path", { path: b.dataset.path });
      return;
    }
    if (act === "apply") {
      paintCampaign({
        component: b.dataset.component,
        part: b.dataset.part,
        package: b.dataset.package,
        operator: b.dataset.operator,
        version: b.dataset.version,
        model: b.dataset.model || b.dataset.part,
        year: ($("db-year") && $("db-year").value) || "2026",
      });
      await applyDb();
      switchPage("setup");
      return;
    }
    if (act === "delete") {
      if (!confirm("Delete this session JSON? Campaign folders and the lab xlsx stay.")) return;
      await rpc("delete_run", { path: b.dataset.path });
      await loadRunLedger();
    }
  } catch (e) {
    alert(e.message);
  }
}

function shotUrl(shot) {
  return shot && shot.url ? shot.url : "";
}

function layoutLabel(cell) {
  const pol = cell.polarity ? `${cell.polarity} ` : "";
  return `U${cell.unit} ${pol}${cell.channel || ""}`.trim();
}

function fillLayoutSelect(preview) {
  const sel = $("layout-test");
  if (!sel) return;
  const tests = preview.tests || [];
  if (!tests.length) {
    sel.innerHTML = '<option value="">-- no mapped tests --</option>';
    return;
  }
  const current = preview.test_key || sel.value;
  sel.innerHTML = tests.map((t) => {
    const label = `${t.excel_sheet} (${t.test_key})`;
    const selAttr = t.test_key === current ? " selected" : "";
    return `<option value="${t.test_key}"${selAttr}>${label}</option>`;
  }).join("");
}

function showCompare(cell) {
  const box = $("layout-compare");
  const pair = $("layout-compare-pair");
  const latest = $("layout-img-latest");
  const prev = $("layout-img-prev");
  if (!box || !cell) return;
  $("layout-compare-title").textContent = `${layoutLabel(cell)} @ ${cell.anchor}`;
  if (cell.latest) {
    latest.src = shotUrl(cell.latest);
    latest.alt = cell.latest.name;
  } else {
    latest.removeAttribute("src");
    latest.alt = "no latest";
  }
  if (cell.previous) {
    prev.src = shotUrl(cell.previous);
    prev.alt = cell.previous.name;
    prev.parentElement.style.display = "";
  } else {
    prev.removeAttribute("src");
    prev.alt = "no previous";
    prev.parentElement.style.display = cell.latest ? "none" : "";
  }
  box.classList.remove("hidden");
  if (pair) pair.classList.toggle("overlay", !!($("layout-overlay") && $("layout-overlay").checked));
}

function renderLayoutGrid(preview) {
  const grid = $("layout-grid");
  const src = $("layout-source");
  if (src) src.textContent = preview.hint || preview.source || "";
  if (!grid) return;
  layoutState = { test_key: preview.test_key || "", cells: preview.cells || [] };
  const units = [...new Set(layoutState.cells.map((c) => c.unit).filter(Boolean))].sort((a, b) => a - b);
  if (units.length) grid.style.gridTemplateColumns = `repeat(${Math.min(units.length, 4)}, minmax(0, 1fr))`;
  grid.innerHTML = "";
  layoutState.cells.forEach((cell, idx) => {
    const el = document.createElement("div");
    el.className = "layout-cell";
    el.dataset.idx = String(idx);
    const shot = cell.latest;
    const img = shot
      ? `<img src="${shotUrl(shot)}" alt="${shot.name}" />`
      : `<div class="layout-empty">no shot yet</div>`;
    el.innerHTML = `${img}<div class="layout-meta">${layoutLabel(cell)} · ${cell.n_shots || 0} files</div><input data-raw="${cell.raw}" value="${cell.anchor || ""}" />`;
    el.addEventListener("click", (ev) => {
      if (ev.target.tagName === "INPUT") return;
      grid.querySelectorAll(".layout-cell").forEach((n) => n.classList.remove("active"));
      el.classList.add("active");
      showCompare(cell);
    });
    grid.appendChild(el);
  });
}

async function loadLayoutPreview(testKey) {
  const key = testKey || ($("layout-test") && $("layout-test").value) || "";
  const preview = await rpc("layout_preview", key ? { test_key: key } : {});
  fillLayoutSelect(preview);
  renderLayoutGrid(preview);
  return preview;
}

async function saveLayoutPreview() {
  const grid = $("layout-grid");
  if (!grid || !layoutState.test_key) return;
  const photos = {};
  grid.querySelectorAll("input[data-raw]").forEach((inp) => {
    photos[inp.dataset.raw] = inp.value.trim();
  });
  await rpc("save_photo_layout", { test_key: layoutState.test_key, photos });
  await loadLayoutPreview(layoutState.test_key);
}

function tick() {
  $("clock").textContent = new Date().toLocaleTimeString();
}

function pollLoop() {
  pollEvents().finally(() => {
    const ms = runPollActive || pendingPrompt ? 350 : 900;
    setTimeout(pollLoop, ms);
  });
}

(async function boot() {
  initCombos();
  tick();
  setInterval(tick, 1000);
  pollLoop();
  paintCampaign(readSavedCampaign());
  ["vcc", "freq", "amp", "repeats"].forEach((id) => {
    const el = $(id);
    if (el) el.addEventListener("input", () => { el.dataset.userEdited = "1"; });
  });
  if ($("manual-mode")) {
    $("manual-mode").addEventListener("change", () => applyTestDefaults(false));
  }
  document.querySelectorAll(".dut-cb").forEach((inp) => {
    inp.addEventListener("change", renderRunPlans);
  });
  document.querySelectorAll(".ch-cb").forEach((inp) => {
    inp.addEventListener("change", () => {
      inp.dataset.userEdited = "1";
      renderRunPlans();
    });
  });
  if ($("layout-test")) {
    const onLayoutTest = () => {
      loadLayoutPreview($("layout-test").value).catch((e) => alert(e.message));
    };
    $("layout-test").addEventListener("change", onLayoutTest);
    $("layout-test").addEventListener("input", onLayoutTest);
  }
  if ($("btn-layout-reload")) {
    $("btn-layout-reload").onclick = () => loadLayoutPreview($("layout-test") && $("layout-test").value).catch((e) => alert(e.message));
  }
  if ($("btn-layout-save")) {
    $("btn-layout-save").onclick = () => saveLayoutPreview().catch((e) => alert(e.message));
  }
  const bindRuns = (id, scope) => {
    const el = $(id);
    if (!el) return;
    el.onclick = () => loadRunLedger(scope).catch((e) => alert(e.message));
  };
  bindRuns("btn-runs-campaign", "campaign");
  bindRuns("btn-runs-part", "part");
  bindRuns("btn-runs-all", "all");
  if ($("btn-runs-reload")) {
    $("btn-runs-reload").onclick = () => loadRunLedger().catch((e) => alert(e.message));
  }
  if ($("btn-export-datalog")) {
    $("btn-export-datalog").onclick = async () => {
      try {
        const exp = await rpc("export_datalog");
        log(`STS datalog\n  ${exp.markdown || ""}\n  ${exp.html || ""}\n  ${exp.pdf || ""}\n`);
        if (exp.html) {
          try { await rpc("open_path", { path: exp.html }); } catch (_) { /* ignore */ }
        }
      } catch (e) {
        alert(e.message);
      }
    };
  }
  if ($("btn-save-logic-dc")) {
    $("btn-save-logic-dc").onclick = async () => {
      try {
        await saveLogicDcPanel();
      } catch (e) {
        if ($("logic-dc-hint")) $("logic-dc-hint").textContent = String((e && e.message) || e);
        alert(e.message);
      }
    };
  }
  if ($("btn-fill-excel")) {
    $("btn-fill-excel").onclick = async () => {
      try {
        const res = await rpc("fill_workbook");
        log(`Excel fill: ${res.status || ""} filled=${res.filled || 0} plots=${res.plots || 0} ${res.excel || ""} ${res.policy || ""}\n`);
        if (res.status === "orphan") {
          alert(`Excel orphan FAIL: ${res.error || "second xlsx under workbook/"}`);
        }
        if (res.status === "ultimate") {
          alert(`Excel ultimate_manual FAIL: ${res.error || "never auto-write the jot book"}`);
        }
        if ($("results-db-hint")) {
          $("results-db-hint").textContent = `Excel ${res.status}: ${res.excel || ""} (${res.filled || 0} cells)`;
        }
      } catch (e) {
        alert(e.message);
      }
    };
  }
  if ($("btn-fetch-datasheet")) {
    $("btn-fetch-datasheet").onclick = async () => {
      try {
        const part = (($("db-part") && $("db-part").value) || "").trim();
        if (!part) throw new Error("Apply a campaign part first");
        const res = await rpc("fetch_datasheet", { part });
        log(`Limits ${res.part}: source=${res.source || ""} pdf=${res.pdf || ""} specs=${(res.specs || []).length}\n${res.note || ""}\n`);
        if ($("results-db-hint")) {
          $("results-db-hint").textContent = `Fetched ${res.part} limits -> ${res.yaml || ""}`;
        }
        await loadTests();
      } catch (e) {
        alert(e.message);
      }
    };
  }
  if ($("layout-overlay")) {
    $("layout-overlay").addEventListener("change", () => {
      const pair = $("layout-compare-pair");
      if (pair) pair.classList.toggle("overlay", $("layout-overlay").checked);
    });
  }
  for (let i = 0; i < 20; i++) {
    try {
      await rpc("ping");
      $("session-hint").textContent = "Worker online — Discover → Open Session";
      await loadDb();
      await loadOwners();
      await loadCategories();
      await loadInventory();
      mergeInventoryIntoTree();
      refreshDbCascades(currentDbSelection());
      syncOwnerSelectFromFolder(($("db-operator") && $("db-operator").value) || "");
      await syncFamilyFromWorker();
      await loadFixtureCatalog();
      await loadParamDefaults();
      await syncPendingGate({ autoOpen: false });
      const st = await syncRunState();
      if (st && st.busy) {
        runPollActive = true;
        switchPage("run");
        waitForRunComplete()
          .then(() => paintSessionReport())
          .then(() => { runPollActive = false; })
          .catch(() => { runPollActive = false; });
      } else {
        await paintSessionReport();
      }
      await loadTests();
      await refreshSession();
      return;
    } catch (e) {
      if (i === 0) {
        $("session-hint").textContent =
          "Waiting for worker on :8766 — double-click restart_ate_worker.bat";
      }
      if (i === 19) {
        log(`Worker not reachable: ${e.message}\n`);
        $("session-hint").textContent =
          "Worker offline — run restart_ate_worker.bat then Ctrl+F5";
      }
      await new Promise((r) => setTimeout(r, 1500));
    }
  }
})();
