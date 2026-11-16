// 5G NR Calculator 화면 ↔ Python(nr_calc.py) 연결부.
//
// 구조 (C/RTL 비유):
//   nr_calc.py = 계산 모듈(DUT), Pyodide = 브라우저 안의 Python 인터프리터(시뮬레이터),
//   이 파일 = top 모듈. 화면 입력을 모아 Python 함수에 넘기고 결과를 화면에 그린다.
// 경계 규칙: JS ↔ Python은 JSON 문자열만 주고받는다 (api_call(name, args_json) → result_json).
"use strict";

const PYODIDE_VERSION = "0.27.7";

// Python 쪽 연결 코드. nr_calc.py는 화면과 무관하게 두고, 화면에 필요한 보조 함수만 여기 둔다.
const PY_GLUE = `
import json, os, sys
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())
import nr_calc as n

def _ui_options(cfg):
    """설정에 따라 바뀌는 선택지: 변조 차수, 최대 layer, CDM group 최대 개수 (spec §2.1, §3.3)."""
    cfg = n.make_cfg(cfg)
    t = cfg["dmrs_type"]
    info = n.dmrs_info(t) if t in n.DMRS_TYPE_INFO else None
    cdm_ok = info is not None and 1 <= cfg["n_cdm"] <= info["max_cdm_groups"]
    return {
        "errors": n.validate(cfg),
        "dmrs_info": info,
        "mod_orders": [{"qm": q, "name": n.MOD_NAMES[q]} for q in n.modulation_orders(cfg)]
                      if cfg["mcs_table"] in n.MCS_TABLES else [],
        "v_max": n.v_max(cfg) if cdm_ok else min(cfg["n_tx"], cfg["n_rx"], n.MAX_LAYERS),
        "n_symb_avail": n.n_symb_avail(cfg) if cfg["link"] in ("DL", "UL") else 0,
    }

def _dmrs_preview(cfg, n_symb):
    """심볼 수를 바꿀 때 DMRS 위치·RB당 RE를 바로 보여 주기 위한 함수 (spec §2.3, §3.2)."""
    cfg = n.make_cfg(cfg)
    try:
        return {
            "positions": n.dmrs_symbols(n_symb, cfg["dmrs_pos"]),
            "re": n.n_dmrs_re_per_prb(n_symb, cfg["dmrs_pos"], cfg["dmrs_type"], cfg["n_cdm"]),
        }
    except (ValueError, KeyError) as e:
        return {"error": str(e)}

_API = {
    "best_tbs": n.best_tbs,              # 자원 size mode / 재계산 (spec §4.1, §4.3)
    "find_resources": n.find_resources,  # TB size mode (spec §4.2)
    "ui_options": _ui_options,
    "dmrs_preview": _dmrs_preview,
    "bandwidths": lambda: n.BANDWIDTH_MAX_RB,
}

def api_call(name, args_json):
    try:
        return json.dumps(_API[name](*json.loads(args_json)))
    except Exception as e:
        return json.dumps({"errors": [f"내부 오류: {type(e).__name__}: {e}"], "warnings": []})
`;

// ---------------------------------------------------------------------------
// 작은 도우미
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);
const fmt = (x) => Number(x).toLocaleString("ko-KR");

let apiCall = null;      // Python api_call 함수 (Pyodide 준비 후 설정)
let BW = null;           // 대역폭별 최대 RB 표 (spec §5.3)
let lastNBytes = null;   // TB size mode 입력 Byte (재계산 때 여유 계산용)
let hasResult = false;

function call(name, ...args) {
  return JSON.parse(apiCall(name, JSON.stringify(args)));
}

function setList(id, items) {
  const ul = $(id);
  ul.replaceChildren(...(items || []).map((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    return li;
  }));
}

function fillSelect(sel, options, preferred) {
  // options: [[value, label], ...]. preferred 값이 있으면 유지, 없으면 마지막 값.
  const keep = String(preferred ?? sel.value);
  sel.replaceChildren(...options.map(([v, label]) => new Option(label, v)));
  const values = options.map(([v]) => String(v));
  sel.value = values.includes(keep) ? keep : values[values.length - 1] ?? "";
}

// 정수 입력 읽기. 비었거나 정수가 아니면 오류 목록에 이름을 넣는다.
function readInt(id, label, errors) {
  const raw = $(id).value.trim();
  const v = Number(raw);
  if (raw === "" || !Number.isInteger(v)) errors.push(`${label}: 정수를 입력하세요`);
  return v;
}

// ---------------------------------------------------------------------------
// 시스템 설정 읽기 (spec §2.1) → nr_calc의 cfg dict와 같은 키
// ---------------------------------------------------------------------------
function readCfg(errors) {
  return {
    scs_khz: Number($("scs_khz").value),
    n_rb_max: readInt("n_rb_max", "최대 RB", errors),
    n_tx: Number($("n_tx").value),
    n_rx: Number($("n_rx").value),
    link: document.querySelector("input[name=link]:checked").value,
    n_dl: readInt("n_dl", "DL 심볼", errors),
    n_f: readInt("n_f", "Flexible 심볼", errors),
    n_ul: readInt("n_ul", "UL 심볼", errors),
    mcs_table: $("mcs_table").value,
    dmrs_pos: Number($("dmrs_pos").value),
    dmrs_type: Number($("dmrs_type").value),
    n_cdm: Number($("n_cdm").value),
    x_overhead: Number($("x_overhead").value),
  };
}

// ---------------------------------------------------------------------------
// 대역폭 선택 (보조 입력, spec §5.3)
// ---------------------------------------------------------------------------
function fillBandwidths() {
  const scs = $("scs_khz").value;
  const prevMHz = ($("bandwidth").value.split(":")[1]) || "100";
  const opts = [["", "직접 입력"]];
  for (const fr of ["FR1", "FR2"]) {
    const table = BW[fr][scs];
    if (!table) continue;
    for (const [mhz, rb] of Object.entries(table)) {
      const frLabel = scs === "60" ? ` ${fr}` : "";
      opts.push([`${fr}:${mhz}`, `${mhz} MHz${frLabel} → ${rb} RB`]);
    }
  }
  // 같은 대역폭이 있으면 유지, 없으면 가장 넓은 대역폭
  const same = opts.find(([v]) => v.split(":")[1] === prevMHz);
  fillSelect($("bandwidth"), opts, same ? same[0] : opts[opts.length - 1][0]);
  applyBandwidth();
}

function applyBandwidth() {
  const v = $("bandwidth").value;
  if (!v) return;
  const [fr, mhz] = v.split(":");
  $("n_rb_max").value = BW[fr][$("scs_khz").value][mhz];
}

// ---------------------------------------------------------------------------
// 설정이 바뀔 때 선택지 갱신
// ---------------------------------------------------------------------------
function refreshOptions() {
  if (!apiCall) return;

  // UL에서는 1024QAM 표 선택 불가 (spec §4.5)
  const isUL = document.querySelector("input[name=link]:checked").value === "UL";
  const opt1024 = $("mcs_table").querySelector("option[value='1024qam']");
  opt1024.disabled = isUL;
  if (isUL && $("mcs_table").value === "1024qam") $("mcs_table").value = "256qam";

  const inputErrors = [];
  const cfg = readCfg(inputErrors);

  // 심볼 합 표시
  const sum = cfg.n_dl + cfg.n_f + cfg.n_ul;
  $("symb_sum").textContent = Number.isNaN(sum) ? "" : (sum === 14 ? "합 14 ✓" : `합 ${sum} (14가 되어야 함)`);

  if (inputErrors.length) {
    setList("sys_errors", inputErrors);
    markStale();
    return;
  }

  // CDM group 선택지: 1 ~ 선택한 type의 최대 개수 (spec D8, §3.3)
  let opts = call("ui_options", cfg);
  if (opts.dmrs_info) {
    const max = opts.dmrs_info.max_cdm_groups;
    const cur = Math.min(Number($("n_cdm").value), max);  // 최대를 넘으면 최대값으로
    fillSelect($("n_cdm"), opts.dmrs_info.cdm_choices.map((c) => [c, `${c}개`]), cur);
    $("cdm_hint").textContent =
      `type ${cfg.dmrs_type}: CDM group 최대 ${max}개 · group당 ${opts.dmrs_info.re_per_cdm_group} RE`;
    cfg.n_cdm = Number($("n_cdm").value);
    opts = call("ui_options", cfg);  // CDM 값을 맞춘 뒤 다시 (최대 layer가 CDM에 따라 바뀜)
  }
  setList("sys_errors", opts.errors);

  // 변조 차수·layer 선택지 (입력 창과 결과 창 모두)
  const modOpts = opts.mod_orders.map((m) => [m.qm, `${m.name} (Qm=${m.qm})`]);
  const vOpts = Array.from({ length: Math.max(opts.v_max, 1) }, (_, i) => [i + 1, `${i + 1}`]);
  fillSelect($("in_qm"), modOpts);
  fillSelect($("r_qm"), modOpts);
  fillSelect($("in_v"), vOpts, Math.min(Number($("in_v").value) || 1, opts.v_max));
  fillSelect($("r_v"), vOpts, Math.min(Number($("r_v").value) || 1, opts.v_max));

  // 심볼·RB 입력 상한
  for (const id of ["in_symb", "r_symb"]) $(id).max = Math.max(opts.n_symb_avail, 3);
  for (const id of ["in_prb", "r_prb"]) $(id).max = cfg.n_rb_max;
  if (Number($("in_symb").value) > opts.n_symb_avail && opts.n_symb_avail > 0) {
    $("in_symb").value = opts.n_symb_avail;
  }

  updateDmrsPreview("in_symb", "in_dmrs");
  markStale();
}

function markStale() {
  if (hasResult) $("r_stale").hidden = false;
}

function dmrsText(positions, re, cfg) {
  return `type ${cfg.dmrs_type}, CDM ${cfg.n_cdm}개 · ${positions.length}심볼 (${positions.join(", ")}) · RB당 ${re} RE`;
}

function updateDmrsPreview(symbId, outId, suffix = "") {
  const errs = [];
  const cfg = readCfg(errs);
  const n = Number($(symbId).value);
  if (errs.length || !Number.isInteger(n)) { $(outId).textContent = ""; return; }
  const p = call("dmrs_preview", cfg, n);
  $(outId).textContent = p.error ? p.error : `DMRS ${dmrsText(p.positions, p.re, cfg)}${suffix}`;
}

// ---------------------------------------------------------------------------
// 결과 표시 (spec §2.3)
// ---------------------------------------------------------------------------
function render(res, cfg) {
  setList("res_warnings", res.warnings);
  setList("res_errors", res.errors);
  if (res.tbs_bits === undefined) {
    // 오류만 있는 결과: 이전 결과를 숨겨 혼동을 막는다
    $("res_body").hidden = true;
    $("res_empty").hidden = true;
    hasResult = false;
    return;
  }
  $("res_empty").hidden = true;
  $("res_body").hidden = false;
  $("r_stale").hidden = true;
  hasResult = true;

  $("r_tbs_bits").textContent = fmt(res.tbs_bits);
  $("r_tbs_bytes").textContent = fmt(res.tbs_bytes);

  const m = $("r_margin");
  if (res.margin_bytes === null) {
    m.textContent = "";
    m.className = "margin";
  } else if (res.margin_bytes >= 0) {
    m.textContent = `입력 ${fmt(lastNBytes)} Byte 대비 +${fmt(res.margin_bytes)} Byte 여유`;
    m.className = "margin pos";
  } else {
    m.textContent = `입력 ${fmt(lastNBytes)} Byte 대비 ${fmt(-res.margin_bytes)} Byte 부족`;
    m.className = "margin neg";
  }

  $("r_qm").value = String(res.qm);
  $("r_v").value = String(res.v);
  $("r_prb").value = res.n_prb;
  $("r_symb").value = res.n_symb;

  const tableName = $("mcs_table").selectedOptions[0].textContent.split(" ")[0];
  $("r_mcs").textContent = `${res.mcs} (${tableName} 표, ${res.mod_name})`;
  $("r_rate").textContent = `R×1024 = ${res.r_x1024} → R = ${res.r.toFixed(4)}`;
  $("r_dmrs").textContent = dmrsText(res.dmrs_pos_list, res.n_dmrs_re_per_prb, cfg);
  $("r_dr").textContent = `${res.data_rate_mbps.toLocaleString("ko-KR", { maximumFractionDigits: 3 })} Mbps ` +
    `(슬롯 ${(1 / (cfg.scs_khz / 15)).toFixed(3).replace(/\.?0+$/, "")} ms당 TBS 1개)`;
}

function cfgOrShowErrors() {
  const errs = [];
  const cfg = readCfg(errs);
  if (errs.length) {
    setList("res_errors", errs);
    setList("res_warnings", []);
    return null;
  }
  return cfg;
}

// ---------------------------------------------------------------------------
// 버튼 동작
// ---------------------------------------------------------------------------
function onTbMode(e) {
  e.preventDefault();
  const cfg = cfgOrShowErrors();
  if (!cfg) return;
  const raw = $("n_bytes").value.trim();
  const nBytes = Number(raw);
  if (raw === "" || !Number.isInteger(nBytes)) {
    render({ errors: ["송신 데이터는 1 이상의 정수(Byte)여야 합니다"], warnings: [] }, cfg);
    return;
  }
  lastNBytes = nBytes;
  render(call("find_resources", cfg, nBytes), cfg);
}

function onResMode(e) {
  e.preventDefault();
  const cfg = cfgOrShowErrors();
  if (!cfg) return;
  const errs = [];
  const prb = readInt("in_prb", "RB 개수", errs);
  const symb = readInt("in_symb", "심볼 수", errs);
  if (errs.length) { render({ errors: errs, warnings: [] }, cfg); return; }
  lastNBytes = null;
  render(call("best_tbs", cfg, Number($("in_qm").value), Number($("in_v").value), prb, symb, null), cfg);
}

function onRecalc(e) {
  e.preventDefault();
  const cfg = cfgOrShowErrors();
  if (!cfg) return;
  const errs = [];
  const prb = readInt("r_prb", "RB 개수", errs);
  const symb = readInt("r_symb", "심볼 수", errs);
  if (errs.length) { setList("res_errors", errs); return; }
  // 결과 창 수정 후 재계산 = best_tbs (spec §4.3). TB size mode였으면 입력 대비 여유도 다시 계산
  const res = call("best_tbs", cfg, Number($("r_qm").value), Number($("r_v").value), prb, symb, lastNBytes);
  if (res.tbs_bits === undefined) {
    // 재계산 오류는 결과 창을 유지한 채 메시지만 표시
    setList("res_errors", res.errors);
    setList("res_warnings", []);
    return;
  }
  render(res, cfg);
}

function onModeChange() {
  const mode = document.querySelector("input[name=mode]:checked").value;
  $("form_tb").hidden = mode !== "tb";
  $("form_res").hidden = mode !== "res";
}

// ---------------------------------------------------------------------------
// 시작: Pyodide 불러오기 → nr_calc.py 넣기 → 화면 연결
// ---------------------------------------------------------------------------
async function boot() {
  const status = $("status");
  if (location.protocol === "file:") {
    status.className = "status failed";
    status.textContent = "파일을 직접 열면 동작하지 않습니다. 로컬 서버(python -m http.server 8000)로 http://localhost:8000 에서 여세요.";
    return;
  }
  try {
    const pyodide = await loadPyodide();
    // nr_calc.py를 그대로 가져와 Pyodide의 가상 파일 시스템에 넣는다 (수정하면 새로고침만으로 반영)
    const resp = await fetch("nr_calc.py", { cache: "no-store" });
    if (!resp.ok) throw new Error(`nr_calc.py를 읽지 못했습니다 (HTTP ${resp.status})`);
    pyodide.FS.writeFile("nr_calc.py", await resp.text());
    pyodide.runPython(PY_GLUE);
    apiCall = pyodide.globals.get("api_call");
    BW = call("bandwidths");
    const pyVer = pyodide.runPython("import sys; sys.version.split()[0]");
    status.className = "status ready";
    status.textContent = `준비 완료 · Pyodide ${PYODIDE_VERSION} (Python ${pyVer})`;
  } catch (err) {
    status.className = "status failed";
    status.textContent = `Python 엔진을 불러오지 못했습니다: ${err.message}. 처음 실행이면 인터넷(또는 로컬 서버) 연결을 확인하세요.`;
    console.error(err);
    return;
  }

  fillBandwidths();
  refreshOptions();
  $("r_stale").hidden = true;

  // 설정 변경 → 선택지 갱신
  $("scs_khz").addEventListener("change", () => { fillBandwidths(); refreshOptions(); });
  $("bandwidth").addEventListener("change", () => { applyBandwidth(); refreshOptions(); });
  $("n_rb_max").addEventListener("input", () => { $("bandwidth").value = ""; refreshOptions(); });
  for (const id of ["n_tx", "n_rx", "mcs_table", "n_dl", "n_f", "n_ul", "dmrs_pos", "dmrs_type", "n_cdm", "x_overhead"]) {
    $(id).addEventListener("change", refreshOptions);
  }
  for (const id of ["n_dl", "n_f", "n_ul"]) $(id).addEventListener("input", refreshOptions);
  for (const r of document.querySelectorAll("input[name=link]")) r.addEventListener("change", refreshOptions);
  for (const r of document.querySelectorAll("input[name=mode]")) r.addEventListener("change", onModeChange);

  // 심볼 수를 바꾸면 DMRS 위치를 바로 다시 보여 준다 (spec §2.3)
  $("in_symb").addEventListener("input", () => updateDmrsPreview("in_symb", "in_dmrs"));
  $("r_symb").addEventListener("input", () => {
    const errs = [];
    const cfg = readCfg(errs);
    const n = Number($("r_symb").value);
    if (errs.length || !Number.isInteger(n)) return;
    const p = call("dmrs_preview", cfg, n);
    $("r_dmrs").textContent = p.error ? p.error : `${dmrsText(p.positions, p.re, cfg)} (재계산 전)`;
  });

  $("form_tb").addEventListener("submit", onTbMode);
  $("form_res").addEventListener("submit", onResMode);
  $("form_recalc").addEventListener("submit", onRecalc);
  for (const b of document.querySelectorAll("button.primary")) b.disabled = false;
}

// PWA: service worker 등록 → 앱 파일과 Pyodide를 캐시에 저장해 오프라인에서도 실행 (sw.js)
if ("serviceWorker" in navigator && location.protocol !== "file:") {
  navigator.serviceWorker.register("sw.js").catch((err) => console.warn("service worker 등록 실패:", err));
}

boot();
