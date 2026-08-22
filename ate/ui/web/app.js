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

const FAMILY_UI = {
  opamp: { brand: "OpAmp ATE", kicker: "Operator console" },
  logic: { brand: "Logic ATE", kicker: "Operator console" },
  level: { brand: "Level ATE", kicker: "Stub — no suite yet" },
};

function paintBrand(family) {
  const meta = FAMILY_UI[family] || FAMILY_UI.opamp;
  const title = $("brand-title");
  if (title) title.textContent = meta.brand;
  const kicker = document.querySelector(".brand-kicker");
  if (kicker) kicker.textContent = meta.kicker;
  document.querySelectorAll(".family-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.family === family);
  });
}

function updateFamilyChrome(family) {
  activeFamily = family || "opamp";
  paintBrand(activeFamily);
  const gainPanel = $("panel-gain-boards");
  if (gainPanel) gainPanel.classList.toggle("hidden", activeFamily !== "opamp");
}

async function syncFamilyFromWorker() {
  const res = await rpc("get_family");
  updateFamilyChrome(res.family || "opamp");
  return activeFamily;
}

async function switchFamily(family) {
  if (!family || family === activeFamily) return activeFamily;
  const res = await rpc("set_family", { family });
  updateFamilyChrome(res.family || family);
  await loadFixtureCatalog();
  await loadTests();
  log(`Family switched: ${activeFamily}\n`);
  return activeFamily;
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

let paramCatalog = { tests: {}, gain_profiles: {}, psu_golden: {}, gbw_steps: [], gbw_run_labels: {} };

function isManualMode() {
  return $("manual-mode") && $("manual-mode").checked;
}

function benchValues() {
  const d = mergeTestDefaults(selectedTests());
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
  return {
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
}

function selectedTests() {
  return [...document.querySelectorAll(".test-item input:checked")].map((i) => i.value);
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
  if (!ids.length) {
    $("param-active-hint").textContent = "Select tests — standard defaults apply.";
    renderRunPlans();
    return;
  }
  const d = mergeTestDefaults(ids);
  if (force || !isManualMode()) {
    $("vcc").value = d.vcc;
    $("freq").value = d.freq_hz;
    $("amp").value = d.amp_vpp;
    $("repeats").value = d.n_repeats;
    delete $("vcc").dataset.userEdited;
  }
  // Channel A/B — operator choice only; never overwrite from test catalog
  if (ids.includes("gbw") && d.gain_profile && $("gain-profile")) {
    $("gain-profile").value = d.gain_profile;
    syncGainProfileHint(force);
  }
  const chans = selectedChannels().join("+");
  const manual = isManualMode();
  $("param-advanced").classList.toggle("hidden", !manual);
  $("param-active-hint").textContent = manual
    ? `Manual — ${ids.join(", ")} · ${chans}`
    : `${ids.join(", ")} · ${chans} — board gain locked · expand run plan below`;
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
    paramCatalog = await rpc("list_param_defaults", { part });
    applyTestDefaults(false);
  } catch (_) {
    paramCatalog = { tests: {}, gain_profiles: {}, psu_golden: { current_limit_a: 0.1 }, gbw_steps: [], gbw_run_labels: {} };
  }
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

const CAMPAIGN_KEY = "ate_last_campaign";
const DEFAULT_CAMPAIGN = {
  component: "OpAmp",
  part: "RS622",
  package: "TTSOP8",
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
  try {
    localStorage.setItem(
      CAMPAIGN_KEY,
      JSON.stringify({
        component: sel.component || "",
        part: sel.part || "",
        package: sel.package || "",
        version: sel.version || "",
        model: sel.model || "",
        year: sel.year || "",
      })
    );
  } catch (_) { /* ignore */ }
}

function ensureTreeHasCampaign(sel) {
  if (!dbTree.components) dbTree.components = {};
  const c = sel.component || DEFAULT_CAMPAIGN.component;
  const p = sel.part || DEFAULT_CAMPAIGN.part;
  const pkg = sel.package || DEFAULT_CAMPAIGN.package;
  const ver = sel.version || DEFAULT_CAMPAIGN.version;
  if (!dbTree.components[c]) dbTree.components[c] = { parts: {} };
  if (!dbTree.components[c].parts[p]) dbTree.components[c].parts[p] = { packages: {} };
  if (!dbTree.components[c].parts[p].packages[pkg]) {
    dbTree.components[c].parts[p].packages[pkg] = { versions: [ver] };
  }
  const vers = dbTree.components[c].parts[p].packages[pkg].versions || [];
  if (!vers.includes(ver)) vers.push(ver);
  dbTree.components[c].parts[p].packages[pkg].versions = vers;
}

function paintCampaign(sel) {
  ensureTreeHasCampaign(sel);
  refreshDbCascades(sel);
  if (sel.model && $("db-model")) $("db-model").value = sel.model;
  if (sel.year && $("db-year") && !$("db-year").value) $("db-year").value = sel.year;
  if ($("db-breadcrumb") && sel.component) {
    $("db-breadcrumb").textContent =
      `${sel.component} / ${sel.part} / ${sel.package} / ${sel.version}` +
      (sel.model ? ` · ${sel.model}` : "");
  }
}

function currentDbSelection() {
  return {
    component: $("db-component").value,
    part: $("db-part").value,
    package: $("db-package").value,
    version: $("db-version").value,
    model: $("db-model").value,
    year: $("db-year").value,
  };
}

function refreshDbCascades(preserve) {
  const comps = Object.keys(dbTree.components || {});
  const sel = preserve || currentDbSelection();
  const component = comps.includes(sel.component) ? sel.component : comps[0];
  fillSelect($("db-component"), comps, component);

  const partsObj = (dbTree.components[component] || {}).parts || {};
  const parts = Object.keys(partsObj);
  const part = parts.includes(sel.part) ? sel.part : parts[0];
  fillSelect($("db-part"), parts, part);

  const pkgsObj = (partsObj[part] || {}).packages || {};
  const packages = Object.keys(pkgsObj);
  const pkg = packages.includes(sel.package) ? sel.package : packages[0];
  fillSelect($("db-package"), packages, pkg);

  const versions = (pkgsObj[pkg] || {}).versions || [];
  const version = versions.includes(sel.version) ? sel.version : versions[0];
  fillSelect($("db-version"), versions, version);
}

function renderDbHints(ctx) {
  dbContext = ctx;
  if (!ctx) return;
  $("db-breadcrumb").textContent =
    `${ctx.component} / ${ctx.part} / ${ctx.package} / ${ctx.version} · ${ctx.model}`;
  $("db-model").value = ctx.model || "";
  if (!$("db-year").value && ctx.year) $("db-year").value = ctx.year;
  $("db-path-hint").textContent = `Photos: ${ctx.photo_example}`;
  $("db-excel-hint").textContent = `Lab report: ${ctx.lab_report}`;
  $("results-db-hint").textContent =
    `Lab report: ${ctx.lab_report} · sessions: ${ctx.sessions}`;
  const n = ctx.sample_size || 4;
  $("unit").max = n;
  document.querySelectorAll(".dut-cb").forEach((cb) => {
    const v = Number(cb.value);
    cb.disabled = v > n;
    if (v > n) cb.checked = false;
  });
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
    fixtureCatalog = await rpc("list_fixture_modes");
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
    version: ctx.version || saved.version,
    model: ctx.model || saved.model,
    year: ctx.year || saved.year || $("db-year")?.value || "2026",
  };
  paintCampaign(sel);
  renderDbHints({ ...saved, ...ctx, ...sel });
  // Re-apply so worker + UI agree after restart (campaign was never "gone", just not restored)
  try {
    const res = await rpc("set_db_context", {
      component: sel.component,
      part: sel.part,
      package: sel.package,
      version: sel.version,
      model: sel.model || undefined,
      year: sel.year || undefined,
    });
    renderDbHints(res.context);
    saveCampaign({ ...sel, ...(res.context || {}) });
    log(`Campaign ready: ${(res.context && res.context.root) || sel.component}\n`);
  } catch (e) {
    log(`Campaign restore warn: ${e.message}\n`);
  }
  if (info.guide?.orchestration) {
    log("DB guide:\n" + info.guide.orchestration.map((s) => `  ${s}`).join("\n") + "\n");
  }
}

async function applyDb() {
  const sel = currentDbSelection();
  const res = await rpc("set_db_context", {
    component: sel.component,
    part: sel.part,
    package: sel.package,
    version: sel.version,
    model: sel.model || undefined,
    year: sel.year || undefined,
  });
  renderDbHints(res.context);
  saveCampaign({ ...sel, ...(res.context || {}) });
  log(`Campaign applied: ${res.context.root}\n`);
  if (res.created?.length) {
    log(`Created ${res.created.length} folder(s) under DUT tree\n`);
  }
  await loadParamDefaults();
}

async function loadTests() {
  const tests = await rpc("list_tests");
  allTests = tests;
  const box = $("test-list");
  box.innerHTML = "";
  if (!tests.length) {
    const stub =
      activeFamily === "level"
        ? "Level family is a stub slot — no characterization suite yet."
        : activeFamily === "logic"
          ? "Logic family loaded — no tests registered yet (A02)."
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
    const items = groups.get(mode) || [];
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
      grid.innerHTML += `
        <label class="test-item" for="${id}">
          <input id="${id}" type="checkbox" value="${t.id}" ${checked} />
          <span><strong>${tag}</strong> — ${t.label}<br/><span class="mode-tag">${t.fixture_mode} · ${instr}${isResearch ? " · research" : ""}</span></span>
        </label>`;
    }
    wrap.appendChild(grid);
    box.appendChild(wrap);
  }
  renderRunPlans();
  document.querySelectorAll(".test-item input").forEach((inp) => {
    inp.addEventListener("change", () => {
      renderRunPlans();
      applyTestDefaults(false);
    });
  });
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

document.querySelectorAll(".family-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const family = btn.dataset.family;
    if (!family || family === activeFamily) return;
    try {
      await switchFamily(family);
    } catch (e) {
      alert(e.message);
    }
  });
});

["db-component", "db-part", "db-package"].forEach((id) => {
  $(id).addEventListener("change", () => refreshDbCascades());
});

$("btn-apply-db").onclick = async () => {
  try {
    await applyDb();
  } catch (e) {
    alert(e.message);
  }
};

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

$("btn-discover").onclick = async () => {
  try {
    const m = await rpc("discover");
    setTiles(m);
    log(`Discovered ${JSON.stringify(m)}\n`);
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
    const need = ["MSO", "PSU", "AWG"];
    const miss = need.filter((k) => !m[k]);
    if (miss.length) {
      alert(
        `Session open but missing: ${miss.join(", ")}\n\n` +
          "Close Ultra Sigma / other VISA apps, check DP832 USB+power, then Open Session again."
      );
    }
    await refreshSession();
  } catch (e) {
    alert(e.message);
  }
};

$("btn-shot").onclick = async () => {
  try {
    const r = await rpc("screenshot", { test_key: "ORT" });
    log(`Screenshot: ${r.path}\n`);
    alert(`JPEG saved:\n${r.path}`);
  } catch (e) {
    alert(e.message);
  }
};

$("btn-folder").onclick = async () => {
  try {
    const duts = selectedDuts();
    const ids = selectedTests();
    const testKey = ids.includes("slew")
      ? "SlewRate"
      : ids.includes("settling")
        ? "SettlingTime"
        : ids.includes("gbw")
          ? "GBW"
          : "ORT";
    await rpc("open_screenshots", {
      test_key: testKey,
      unit_index: duts[0],
    });
  } catch (e) {
    alert(e.message);
  }
};

$("btn-start").onclick = async () => {
  const ids = selectedTests();
  if (!ids.length) return alert("Select at least one test");
  const duts = selectedDuts();
  if (!duts.length) return alert("Select at least one DUT");
  if (!sessionOpen) return alert("Open Session first");
  if (runPollActive) return alert("Run already in progress");
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
    const tb = $("results-table").querySelector("tbody");
    tb.innerHTML = "";
    let allOk = true;
    for (const r of results || []) {
      allOk = allOk && r.success;
      const ch = r.channel ? ` ${r.channel}` : "";
      tb.innerHTML += `<tr><td>${r.dut ?? ""}${ch}</td><td>${r.test_id}</td><td>${r.success}</td><td>${r.summary || r.error || ""}</td></tr>`;
    }
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
  for (let i = 0; i < 20; i++) {
    try {
      await rpc("ping");
      $("session-hint").textContent = "Worker online — Discover → Open Session";
      await loadDb();
      await syncFamilyFromWorker();
      await loadFixtureCatalog();
      await loadParamDefaults();
      await syncPendingGate({ autoOpen: false });
      const st = await syncRunState();
      if (st && st.busy) {
        runPollActive = true;
        switchPage("run");
        waitForRunComplete()
          .then(() => rpc("get_last_run_results"))
          .then((results) => {
            runPollActive = false;
            if (results && results.length) {
              const tb = $("results-table").querySelector("tbody");
              if (tb) {
                tb.innerHTML = "";
                for (const r of results) {
                  const ch = r.channel ? ` ${r.channel}` : "";
                  tb.innerHTML += `<tr><td>${r.dut ?? ""}${ch}</td><td>${r.test_id}</td><td>${r.success}</td><td>${r.summary || r.error || ""}</td></tr>`;
                }
              }
            }
          })
          .catch(() => { runPollActive = false; });
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
