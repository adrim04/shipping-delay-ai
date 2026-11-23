// Cliente web del servicio Shipping Delay AI – consume todos los endpoints de /api/v1
const $ = (s) => document.querySelector(s);
const defaultApi = location.protocol.startsWith("http") ? `${location.origin}/api/v1` : "http://localhost:8000/api/v1";
let API = localStorage.getItem("apiUrl") || defaultApi;
const PAGE = 15;
let histOffset = 0;

// ---------------------------------------------------------------- utilidades
async function api(path, opts = {}) {
  const res = await fetch(`${API}${path}`, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(body.detail)
      ? body.detail.map((d) => `${d.loc.slice(-1)}: ${d.msg}`).join("; ")
      : body.detail || res.statusText;
    throw new Error(detail);
  }
  return body;
}
const fmtDate = (s) => new Date(s + (s.endsWith("Z") ? "" : "Z")).toLocaleString("es-BO");
const pct = (v) => `${(v * 100).toFixed(1)}%`;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg; t.className = `toast${err ? " err" : ""}`; t.hidden = false;
  clearTimeout(t._h); t._h = setTimeout(() => (t.hidden = true), 4000);
}
function showMsg(el, html, kind) { el.innerHTML = html; el.className = `msg ${kind}`; el.hidden = false; }
const labelPill = (cls, label) => `<span class="pill ${cls ? "late" : "ontime"}">${esc(label)}</span>`;

// ---------------------------------------------------------------- estado
async function checkHealth() {
  try {
    const h = await api("/health");
    $("#statusDot").classList.add("on");
    $("#statusText").textContent = `conectado · modelo ${h.active_model}`;
  } catch {
    $("#statusDot").classList.remove("on");
    $("#statusText").textContent = "sin conexión";
  }
}

// ---------------------------------------------------------------- pestañas
const loaders = { history: loadHistory, metrics: loadMetrics, data: loadDatasets };
document.querySelectorAll(".tab").forEach((btn) =>
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === `tab-${btn.dataset.tab}`));
    loaders[btn.dataset.tab]?.();
  })
);

// ---------------------------------------------------------------- predicción  (POST /predictions)
$("#predictForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = Object.fromEntries(fd.entries());
  ["customer_care_calls", "customer_rating", "prior_purchases"].forEach((k) => (payload[k] = parseInt(payload[k], 10)));
  ["cost_of_the_product", "discount_offered", "weight_in_gms"].forEach((k) => (payload[k] = parseFloat(payload[k])));
  try {
    const r = await api("/predictions", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    $("#resultEmpty").hidden = true; $("#resultBody").hidden = false;
    const lbl = $("#resultLabel");
    lbl.textContent = r.predicted_label;
    lbl.className = `big-label ${r.predicted_class ? "late" : "ontime"}`;
    $("#gaugeFill").style.width = pct(r.probability_delay);
    $("#probText").textContent = pct(r.probability_delay);
    $("#rId").textContent = r.id; $("#rVersion").textContent = r.model_version; $("#rDate").textContent = fmtDate(r.created_at);
  } catch (err) { toast(`Error: ${err.message}`, true); }
});

$("#randomBtn").addEventListener("click", () => {
  const f = $("#predictForm");
  const pick = (a) => a[Math.floor(Math.random() * a.length)];
  const rnd = (a, b) => Math.floor(a + Math.random() * (b - a + 1));
  f.warehouse_block.value = pick(["A", "B", "C", "D", "F"]);
  f.mode_of_shipment.value = pick(["Ship", "Flight", "Road"]);
  f.product_importance.value = pick(["low", "medium", "high"]);
  f.gender.value = pick(["F", "M"]);
  f.customer_care_calls.value = rnd(2, 7);
  f.customer_rating.value = rnd(1, 5);
  f.cost_of_the_product.value = rnd(96, 310);
  f.prior_purchases.value = rnd(2, 10);
  f.discount_offered.value = Math.random() < 0.25 ? rnd(11, 65) : rnd(1, 10);
  f.weight_in_gms.value = rnd(1001, 7846);
});

// ---------------------------------------------------------------- historial  (GET /predictions)
async function loadHistory() {
  const filter = $("#histFilter").value;
  const version = $("#histVersion").value;
  const q = `?limit=${PAGE}&offset=${histOffset}${filter !== "" ? `&predicted_class=${filter}` : ""}` +
    (version ? `&model_version=${encodeURIComponent(version)}` : "");
  try {
    await loadVersionOptions();
    const h = await api(`/predictions${q}`);
    const tb = $("#histTable tbody");
    tb.innerHTML = h.items.length ? h.items.map((p) => `<tr data-id="${p.id}">
      <td>${p.id}</td><td>${fmtDate(p.created_at)}</td><td>${p.warehouse_block}</td><td>${p.mode_of_shipment}</td>
      <td class="num">${p.customer_care_calls}</td><td class="num">${p.customer_rating}</td>
      <td class="num">${p.cost_of_the_product}</td><td class="num">${p.prior_purchases}</td>
      <td>${p.product_importance}</td><td>${p.gender}</td><td class="num">${p.discount_offered}</td>
      <td class="num">${p.weight_in_gms}</td><td>${labelPill(p.predicted_class, p.predicted_label)}</td>
      <td class="num">${pct(p.probability_delay)}</td><td><code>${esc(p.model_version)}</code></td></tr>`).join("")
      : `<tr><td colspan="15" class="empty">Aún no hay predicciones.</td></tr>`;
    const page = Math.floor(histOffset / PAGE) + 1, pages = Math.max(1, Math.ceil(h.total / PAGE));
    $("#pageInfo").textContent = `Página ${page} de ${pages} · ${h.total} registros`;
    $("#prevPage").disabled = histOffset === 0;
    $("#nextPage").disabled = histOffset + PAGE >= h.total;
  } catch (err) { toast(`Error: ${err.message}`, true); }
}
// Opciones del filtro de versión  (GET /models)
async function loadVersionOptions() {
  const sel = $("#histVersion"), current = sel.value;
  const all = await api("/models");
  sel.innerHTML = `<option value="">Todas las versiones</option>` +
    all.map((m) => `<option value="${esc(m.version)}">${esc(m.version)} · ${esc(m.status)}</option>`).join("");
  sel.value = current;
}

// Detalle de una predicción  (GET /predictions/{id})
async function showDetail(id) {
  try {
    const p = await api(`/predictions/${id}`);
    document.querySelectorAll("#histTable tbody tr").forEach((tr) => tr.classList.toggle("selected", tr.dataset.id === String(id)));
    $("#detailTitle").textContent = `Detalle de la predicción #${p.id}`;
    const rows = [
      ["Resultado", labelPill(p.predicted_class, p.predicted_label)],
      ["Probabilidad de retraso", pct(p.probability_delay)],
      ["Versión del modelo", `<code>${esc(p.model_version)}</code>`],
      ["Fecha", fmtDate(p.created_at)],
      ["Bloque de almacén", esc(p.warehouse_block)], ["Modo de envío", esc(p.mode_of_shipment)],
      ["Llamadas a atención", p.customer_care_calls], ["Calificación del cliente", p.customer_rating],
      ["Costo del producto (USD)", p.cost_of_the_product], ["Compras previas", p.prior_purchases],
      ["Importancia del producto", esc(p.product_importance)], ["Género", esc(p.gender)],
      ["Descuento ofrecido (%)", p.discount_offered], ["Peso (g)", p.weight_in_gms],
    ];
    $("#detailBody").innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
    $("#detailCard").hidden = false;
    $("#detailCard").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (err) { toast(`Error: ${err.message}`, true); }
}
$("#histTable tbody").addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-id]");
  if (tr) showDetail(tr.dataset.id);
});
$("#detailClose").addEventListener("click", () => { $("#detailCard").hidden = true; });
$("#histVersion").addEventListener("change", () => { histOffset = 0; loadHistory(); });

$("#histRefresh").addEventListener("click", loadHistory);
$("#histFilter").addEventListener("change", () => { histOffset = 0; loadHistory(); });
$("#prevPage").addEventListener("click", () => { histOffset = Math.max(0, histOffset - PAGE); loadHistory(); });
$("#nextPage").addEventListener("click", () => { histOffset += PAGE; loadHistory(); });

// ---------------------------------------------------------------- métricas  (GET /metrics, GET /models)
async function loadMetrics() {
  try {
    const [m, all] = await Promise.all([api("/metrics"), api("/models")]);
    const th = m.quality_thresholds;
    const kpi = (k, v, key) => {
      const t = th[key];
      const gate = t === undefined ? "" : `<div class="t ${v >= t ? "pass" : "fail"}">${v >= t ? "✓" : "✗"} umbral ≥ ${t}</div>`;
      return `<div class="kpi"><div class="k">${k}</div><div class="v">${v.toFixed(3)}</div>${gate}</div>`;
    };
    $("#kpis").innerHTML =
      kpi("ROC-AUC", m.roc_auc, "roc_auc") + kpi("Accuracy", m.accuracy, "accuracy") + kpi("F1", m.f1_score, "f1") +
      kpi("Precision", m.precision) + kpi("Recall", m.recall) +
      `<div class="kpi info"><div class="k">Modelo activo</div><div class="v">${esc(m.algorithm)}</div>
       <div class="t">${esc(m.version)} · ${m.train_rows}/${m.test_rows} filas</div></div>`;

    const cm = m.confusion_matrix, tot = cm.tn + cm.fp + cm.fn + cm.tp;
    const cell = (v, good, name) => {
      const a = 0.15 + 0.75 * (v / tot) * 2;
      const bg = good ? `rgba(46,125,107,${a})` : `rgba(217,130,43,${a})`;
      return `<div class="cell" style="background:${bg}">${v}<small>${name}</small></div>`;
    };
    $("#cmatrix").innerHTML = `<div class="cm">
      <div></div><div class="h">Pred. a tiempo</div><div class="h">Pred. retraso</div>
      <div class="h">Real a tiempo</div>${cell(cm.tn, true, "VN")}${cell(cm.fp, false, "FP")}
      <div class="h">Real retraso</div>${cell(cm.fn, false, "FN")}${cell(cm.tp, true, "VP")}</div>
      <p class="muted">Clase positiva = <b>con retraso</b>. ${cm.tp + cm.tn} de ${tot} aciertos en el conjunto de prueba.</p>`;

    const fi = m.feature_importance.slice(0, 10), max = Math.max(...fi.map((f) => f.importance), 1e-9);
    $("#fimp").innerHTML = `<div class="bars">${fi.map((f) => `<div class="bar-row"><span>${esc(f.feature)}</span>
      <div class="track"><div class="fill" style="width:${(f.importance / max) * 100}%"></div></div>
      <span class="val">${f.importance.toFixed(3)}</span></div>`).join("")}</div>`;

    $("#compTable").innerHTML = `<thead><tr><th>Algoritmo</th><th class="num">CV ROC-AUC</th><th class="num">ROC-AUC test</th>
      <th class="num">Accuracy</th><th class="num">Precision</th><th class="num">Recall</th><th class="num">F1</th><th>Hiperparámetros</th></tr></thead>
      <tbody>${m.comparison.map((c) => `<tr${c.algorithm === m.algorithm ? ' style="font-weight:600"' : ""}>
      <td>${esc(c.algorithm)}${c.algorithm === m.algorithm ? " ★" : ""}</td><td class="num">${c.cv_roc_auc.toFixed(3)}</td>
      <td class="num">${c.roc_auc.toFixed(3)}</td><td class="num">${c.accuracy.toFixed(3)}</td><td class="num">${c.precision.toFixed(3)}</td>
      <td class="num">${c.recall.toFixed(3)}</td><td class="num">${c.f1.toFixed(3)}</td><td><code>${esc(JSON.stringify(c.params))}</code></td></tr>`).join("")}</tbody>`;

    $("#modelsTable").innerHTML = `<thead><tr><th>Versión</th><th>Estado</th><th>Algoritmo</th><th>Dataset</th>
      <th class="num">ROC-AUC</th><th class="num">Accuracy</th><th class="num">F1</th><th>Entrenado</th><th>Notas de calidad</th></tr></thead>
      <tbody>${all.map((v) => `<tr><td><code>${esc(v.version)}</code></td><td><span class="pill ${v.status}">${v.status}</span></td>
      <td>${esc(v.algorithm)}</td><td>#${v.dataset_id}</td><td class="num">${v.roc_auc.toFixed(3)}</td>
      <td class="num">${v.accuracy.toFixed(3)}</td><td class="num">${v.f1_score.toFixed(3)}</td>
      <td>${fmtDate(v.trained_at)}</td><td>${esc(v.quality_notes || "")}</td></tr>`).join("")}</tbody>`;
  } catch (err) { toast(`Error: ${err.message}`, true); }
}

// ---------------------------------------------------------------- datasets  (POST/GET /datasets)
async function loadDatasets() {
  try {
    const ds = await api("/datasets");
    $("#retrainDataset").innerHTML = ds.map((d) => `<option value="${d.id}">#${d.id} · ${esc(d.filename)} (${d.row_count} filas)</option>`).join("");
    $("#dsTable").innerHTML = `<thead><tr><th>#</th><th>Archivo</th><th class="num">Filas</th><th>Balance (0 / 1)</th>
      <th>Observaciones de calidad</th><th>Subido</th></tr></thead>
      <tbody>${ds.map((d) => `<tr><td>${d.id}</td><td>${esc(d.filename)}</td><td class="num">${d.row_count}</td>
      <td>${pct(d.class_balance["0"] || 0)} / ${pct(d.class_balance["1"] || 0)}</td>
      <td>${d.validation_notes.length ? esc(d.validation_notes.join("; ")) : "Sin observaciones"}</td>
      <td>${fmtDate(d.uploaded_at)}</td></tr>`).join("")}</tbody>`;
  } catch (err) { toast(`Error: ${err.message}`, true); }
}

$("#uploadForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = $("#fileInput").files[0];
  if (!file) return;
  const fd = new FormData(); fd.append("file", file);
  try {
    const d = await api("/datasets", { method: "POST", body: fd });
    showMsg($("#uploadMsg"), `✓ Dataset <b>#${d.id}</b> registrado (${d.row_count} filas).` +
      (d.validation_notes.length ? `<br>Observaciones: ${esc(d.validation_notes.join("; "))}` : ""), "ok");
    await loadDatasets();
    $("#retrainDataset").value = d.id;
  } catch (err) { showMsg($("#uploadMsg"), `✗ ${esc(err.message)}`, "err"); }
});

// ---------------------------------------------------------------- reentrenamiento  (POST /retrain)
$("#retrainBtn").addEventListener("click", async () => {
  const btn = $("#retrainBtn");
  btn.disabled = true; btn.textContent = "Entrenando… (puede tardar ~30 s)";
  try {
    const r = await api("/retrain", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset_id: parseInt($("#retrainDataset").value, 10) || null, algorithm: $("#retrainAlgo").value }),
    });
    const m = r.new_model;
    showMsg($("#retrainMsg"), `<b>${r.status}</b> · ${esc(r.message)}<br>ROC-AUC ${m.roc_auc.toFixed(3)} · Accuracy ${m.accuracy.toFixed(3)} · F1 ${m.f1_score.toFixed(3)}` +
      (r.previous_model_version ? `<br>Modelo anterior: <code>${esc(r.previous_model_version)}</code>` : ""), r.status === "COMPLETADO" ? "ok" : "warn");
    checkHealth();
  } catch (err) { showMsg($("#retrainMsg"), `✗ ${esc(err.message)}`, "err"); }
  finally { btn.disabled = false; btn.textContent = "Reentrenar"; }
});

// ---------------------------------------------------------------- inicio
$("#apiUrl").value = API;
$("#apiUrl").addEventListener("change", (e) => {
  API = e.target.value.replace(/\/$/, ""); localStorage.setItem("apiUrl", API); checkHealth();
});
checkHealth();
setInterval(checkHealth, 15000);
