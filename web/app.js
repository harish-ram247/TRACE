/* TRACE web demo: intro, circuit backdrop, rotating tagline, claims dataset with an expandable
   then-vs-now verdict and git-history evidence. Calls the TRACE API (POST /ask, GET /chunks/{id},
   GET /lineages/{id}); example answers are precomputed in examples.json. */
"use strict";

const API = (window.TRACE_API || "").replace(/\/$/, "");
const FIRST = "2021-01-01";
const LAST = "2026-11-13";
const $ = (sel) => document.querySelector(sel);
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

const els = {
  form: $("#ask-form"), q: $("#q"), date: $("#date"), fromQ: $("#from-q"), verify: $("#verify"),
  go: $("#go"), msg: $("#form-msg"), rows: $("#rows"), detail: $("#detail"), verdict: $("#verdict"),
  asked: $("#asked"), trace: $("#p-trace .p-body"), plain: $("#p-plain .p-body"), hTrace: $("#h-trace"),
  why: $("#why"), evidence: $("#evidence"), srcList: $("#src-list"), claims: $("#claims-check"),
  doc: $("#ev-doc"), log: $("#log"), chipDate: $("#chip-date"),
};

let rows = [];      // [{ q, asOf, live, trace: {status, body}, plain: {status, body}, lineages }]
let openIndex = -1;
let current = null; // the open row
let seq = 0;        // guards against out-of-order responses

/* ---------- helpers ---------- */
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
function day(iso) { return iso ? iso.slice(0, 10) : null; }
function section(path) { return path.split(" > ").pop(); }
function file(path) { return path.split("/").pop(); }
function span(s) { return `${day(s.valid_from) || FIRST} – ${day(s.valid_until) || "now"}`; }

/** The answer as safe HTML; citations become chips, red with a dagger when the cited version was
 *  not valid on the date asked. */
function answerHtml(text, badLabels) {
  let s = esc(text);
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  return s.replace(/\[(S\d+(?:\s*,\s*S\d+)*)\]/g, (_, ids) =>
    ids.split(/\s*,\s*/).map((id) => badLabels.has(id)
      ? `<span class="cid bad" title="Not valid on the date asked">${id}†</span>`
      : `<span class="cid">${id}</span>`).join(""));
}
const ICON = {
  ok: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="1.75"/><path d="M7.5 12.3l3 3 6-6.3" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
  bad: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="1.75"/><path d="M8.5 8.5l7 7M15.5 8.5l-7 7" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
  na: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="1.75"/><path d="M8 12h8" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
  open: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v10M3 8h10" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>',
};

function validity(s, ref) {
  if (!ref) return { cls: "na", word: "", why: "" };
  const from = day(s.valid_from) || FIRST;
  const until = day(s.valid_until);
  if (ref < from) return { cls: "bad", word: "Not yet written", why: `written ${from}, after the date asked` };
  if (until && ref >= until) return { cls: "bad", word: "Superseded", why: `replaced ${until}, before the date asked` };
  return { cls: "ok", word: "Valid", why: `${from} – ${until || "now"}` };
}
function cited(body) {
  const set = new Set(body.cited_labels || []);
  return (body.sources || []).filter((s) => set.has(s.label));
}
function refDate(row) {
  const t = row.trace && row.trace.status === 200 ? row.trace.body.time : null;
  return t ? day(t.as_of) : null;
}

/* ---------- API ---------- */
async function api(path, options = {}, timeoutMs = 30000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(API + path, { ...options, signal: ctrl.signal, headers: { "Content-Type": "application/json" } });
    let body;
    try { body = await r.json(); } catch { body = { error: { message: r.statusText } }; }
    return { status: r.status, body };
  } catch (e) {
    return { status: e.name === "AbortError" ? 504 : 0, body: { error: { message: String(e.message || e) } } };
  } finally {
    clearTimeout(timer);
  }
}
function ask(question, variant, asOf) {
  const body = { question, variant };
  if (asOf) body.as_of = asOf;
  return api("/ask", { method: "POST", body: JSON.stringify(body) }, 300000);
}
function errorText(status, body) {
  if (status === 429) return "Too many questions in a short time. Wait a moment and try again.";
  if (status === 502 || status === 504) return "The language model is busy right now (it runs on a free tier). Try again in a minute.";
  if (status === 503) return "The server is not fully configured.";
  if (status === 0) return "The TRACE API can't be reached. It may be waking up; try again shortly.";
  return (body && body.error && body.error.message) || `Request failed (${status}).`;
}

/* ---------- claims dataset ---------- */
function evalSummary(res, ref, withClaims) {
  if (!res) return null;
  if (res.status !== 200) return { error: res.status };
  const b = res.body;
  const srcs = cited(b);
  const out = {};
  out.source_valid = b.not_found || !srcs.length ? null : srcs.every((s) => validity(s, ref).cls === "ok");
  const v = b.verification;
  if (withClaims && v && v.claims && v.claims.length) {
    const rowsC = v.revised_claims && v.revised_claims.length ? v.revised_claims : v.claims;
    out.claims_supported = `${rowsC.filter((c) => c.label === "supported_current").length}/${rowsC.length}`;
  }
  if (b.not_found) out.answer = "not_found";
  return out;
}
function jsonHtml(obj) {
  const val = (v) => v === true ? '<span class="t">true</span>' : v === false ? '<span class="f">false</span>'
    : v === null ? '<span class="c">null</span>' : typeof v === "number" ? `<span class="n">${v.toFixed(2)}</span>`
    : `<span class="s">"${esc(v)}"</span>`;
  const keys = Object.keys(obj);
  const lines = [`{ <span class="c">${keys.length} items</span>`];
  keys.forEach((k, i) => {
    const inner = obj[k];
    const comma = i < keys.length - 1 ? "," : "";
    if (inner === null || typeof inner !== "object") { lines.push(`  <span class="k">"${k}"</span>: ${val(inner)}${comma}`); return; }
    const ik = Object.keys(inner);
    lines.push(`  <span class="k">"${k}"</span>: {`);
    ik.forEach((kk, j) => lines.push(`    <span class="k">"${kk}"</span>: ${val(inner[kk])}${j < ik.length - 1 ? "," : ""}`));
    lines.push(`  }${comma}`);
  });
  lines.push("}");
  return `<pre class="json">${lines.join("\n")}</pre>`;
}
function cellAnswer(res, ref, kind) {
  if (!res) return '<span class="loading">Answering…</span>';
  if (res.status !== 200) return `<span class="na">${esc(errorText(res.status, res.body))}</span>`;
  const b = res.body;
  if (b.not_found) return `<span class="na">${kind === "trace" ? "Not in the docs valid on that date." : "No answer found."}</span>`;
  const bad = new Set(cited(b).filter((s) => validity(s, ref).cls === "bad").map((s) => s.label));
  return answerHtml(b.answer, bad);
}
function rowHtml(r, i) {
  const ref = r.trace && r.trace.status === 200 ? refDate(r) : r.asOf;
  const pending = !r.trace;
  const ev = pending ? '<span class="loading">Evaluating…</span>'
    : jsonHtml({ trace: evalSummary(r.trace, ref, true), plain_rag: evalSummary(r.plain, ref, false) });
  const open = i === openIndex;
  const when = ref ? `as of ${esc(ref)}` : "date from the question";
  return `<div class="tr row" role="row" data-i="${i}" aria-expanded="${open}">
    <div class="q" role="cell">${r.live ? '<span class="live">Your question</span><br>' : ""}“${esc(r.q)}”<br><span class="when">${when}</span></div>
    <div class="ans${pending ? "" : ""}" role="cell" data-k="trace_answer">${cellAnswer(r.trace, ref, "trace")}</div>
    <div class="ans" role="cell" data-k="plain_rag_answer">${cellAnswer(r.plain, ref, "plain")}</div>
    <div role="cell" data-k="eval_scores">${ev}</div>
    <div class="open" role="cell"><button type="button" aria-expanded="${open}" aria-label="${open ? "Close" : "Open"} the verdict for: ${esc(r.q)}">${ICON.open}</button></div>
  </div>`;
}
function renderRows() {
  const detail = els.detail;
  els.rows.innerHTML = rows.map(rowHtml).join("");
  els.rows.appendChild(detail); // keep the detail node alive while the rows are re-rendered
  placeDetail();
}
function placeDetail() {
  const rowEl = els.rows.querySelector(`.row[data-i="${openIndex}"]`);
  if (openIndex < 0 || !rowEl) { els.detail.hidden = true; return; }
  rowEl.after(els.detail);
  els.detail.hidden = false;
}
function openRow(i, { scroll = false } = {}) {
  openIndex = i;
  current = rows[i];
  selected = null;
  closeEvidence();
  renderRows();
  if (current.trace) {
    els.verdict.setAttribute("aria-busy", "false");
    renderVerdict(current);
  } else {
    showLoading(current.q);
  }
  const ref = refDate(current) || current.asOf;
  if (ref && els.chipDate) els.chipDate.textContent = ref;
  if (scroll) els.rows.querySelector(`.row[data-i="${i}"]`).scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
}
function closeRow() {
  openIndex = -1;
  current = null;
  renderRows();
}
els.rows.addEventListener("click", (e) => {
  const row = e.target.closest(".row");
  if (!row || e.target.closest(".detail")) return;
  const i = Number(row.dataset.i);
  if (i === openIndex) closeRow(); else openRow(i);
});

/* ---------- verdict ---------- */
function renderAsked(row) {
  const t = row.trace.status === 200 ? row.trace.body.time : null;
  if (!t) { els.asked.innerHTML = `<span class="asked-q show">Asked: “${esc(row.q)}”</span>`; return; }
  let why = "date you set";
  if (t.assumed) why = "no date in the question, so today";
  else if (t.source !== "explicit") why = `read from “${esc(t.matched)}”`;
  const parts = [
    `<span class="asked-q">Asked: “${esc(row.q)}”</span>`,
    `<span><span class="k">As of</span><b class="nw">${esc(day(t.as_of))}</b> <span class="note">${why}</span></span>`,
  ];
  const ts = cited(row.trace.body);
  if (ts.length) parts.push(`<span class="ex-k"><span class="k">TRACE source</span><span class="nw">${esc(span(ts[0]))}</span></span>`);
  if (row.plain.status === 200) {
    const ref = day(t.as_of);
    const bad = cited(row.plain.body).find((s) => validity(s, ref).cls === "bad");
    if (bad) parts.push(`<span class="ex-k"><span class="k">Plain RAG source</span><span class="nw stale">${esc(span(bad))}</span></span>`);
  }
  els.asked.innerHTML = parts.join("");
}
function panelHtml(kind, res, ref) {
  if (res.status !== 200) return `<p class="p-msg err">${esc(errorText(res.status, res.body))}</p>`;
  const b = res.body;
  const srcs = cited(b);
  const bad = srcs.filter((s) => validity(s, ref).cls === "bad");
  const badLabels = new Set(bad.map((s) => s.label));
  let html = b.not_found
    ? `<p class="p-answer muted">${kind === "trace" ? "Not in the docs valid on that date." : "No answer found in the retrieved passages."}</p>`
    : `<p class="p-answer">${answerHtml(b.answer, badLabels)}</p>`;
  let call;
  if (b.not_found) {
    call = { cls: "na", head: kind === "trace" ? "Declined rather than guess" : "Nothing to judge", sub: kind === "trace" ? "No version valid on that date answers this question." : "" };
  } else if (!srcs.length) {
    call = { cls: "na", head: "No source cited", sub: "" };
  } else if (bad.length) {
    call = { cls: "bad", head: `† Cites ${bad.length > 1 ? "versions" : "a version"} not valid on ${ref}`,
      sub: bad.map((s) => `${s.label} · ${section(s.section_path)}: ${validity(s, ref).why}`).join("; ") };
  } else if (kind === "trace") {
    const s = srcs[0];
    call = { cls: "ok", head: `Source valid on ${ref}`, sub: `${s.label} · ${section(s.section_path)}: ${span(s)}` };
  } else {
    call = { cls: "ok", head: `Its sources happen to be valid on ${ref}`, sub: "Plain RAG ignores dates; this time it picked the right version." };
  }
  html += `<p class="call ${call.cls}">${ICON[call.cls]}<span>${esc(call.head)}${call.sub ? `<span class="sub">${esc(call.sub)}</span>` : ""}</span></p>`;
  const v = b.verification;
  if (kind === "trace" && v && v.claims && v.claims.length) {
    const rowsC = v.revised_claims && v.revised_claims.length ? v.revised_claims : v.claims;
    const ok = rowsC.filter((c) => c.label === "supported_current").length;
    html += `<p class="claims-line"><b>${ok} of ${rowsC.length}</b> claims supported by a source valid on that date</p>`;
  }
  return html;
}
function renderVerdict(row) {
  const ref = refDate(row);
  renderAsked(row);
  const verified = row.trace.status === 200 && row.trace.body.verification;
  els.hTrace.textContent = verified ? "TRACE + claim check" : "TRACE";
  els.trace.innerHTML = panelHtml("trace", row.trace, ref);
  els.plain.innerHTML = panelHtml("plain", row.plain, ref);
  const any = [row.trace, row.plain].some((r) => r.status === 200 && cited(r.body).length);
  els.why.hidden = !any;
  if (!els.evidence.hidden) renderEvidence(row);
}
function showLoading(q) {
  els.verdict.setAttribute("aria-busy", "true");
  els.asked.innerHTML = `<span class="asked-q show">Asking: “${esc(q)}”</span>`;
  const msg = '<p class="loading">Resolving the date, retrieving the docs valid then, answering. Usually 3 to 10 seconds.</p>';
  els.trace.innerHTML = msg;
  els.plain.innerHTML = msg;
  els.why.hidden = true;
  closeEvidence();
}

/* ---------- evidence: git history view ---------- */
let selected = null; // { chunkId, versionId }
function evidenceSources(row) {
  const out = new Map();
  for (const [kind, res] of [["TRACE", row.trace], ["Plain RAG", row.plain]]) {
    if (!res || res.status !== 200) continue;
    for (const s of cited(res.body)) {
      if (!out.has(s.chunk_id)) out.set(s.chunk_id, { s, by: [], answers: [] });
      out.get(s.chunk_id).by.push({ kind, label: s.label });
      out.get(s.chunk_id).answers.push(res.body.answer || "");
    }
  }
  return [...out.values()];
}
function citedBy(item, cls) {
  return item.by.map((b) => `<span class="by ${cls}"><b>${esc(b.label)}</b> ${esc(b.kind)}</span>`).join("");
}
function renderEvidence(row) {
  const ref = refDate(row);
  const items = evidenceSources(row);
  if (!selected || !items.some((i) => i.s.chunk_id === selected.chunkId)) {
    selected = items.length ? { chunkId: items[0].s.chunk_id, versionId: items[0].s.chunk_id } : null;
  }
  els.srcList.innerHTML = items.map((i) => {
    const v = validity(i.s, ref);
    const cur = selected && selected.chunkId === i.s.chunk_id;
    return `<li><button type="button" class="src" data-chunk="${i.s.chunk_id}" aria-current="${cur}">
      <span class="sname">${esc(section(i.s.section_path))}</span>
      <span class="smeta">${esc(file(i.s.source_path))} · ${esc(span(i.s))}</span>
      <span class="sby">${citedBy(i, v.cls === "bad" ? "bad" : "ok")}</span>
      ${v.word ? `<span class="st ${v.cls}">${v.word} on ${esc(ref)}</span>` : ""}</button></li>`;
  }).join("");
  const v = row.trace.status === 200 && row.trace.body.verification;
  if (v && v.claims && v.claims.length) {
    const rowsC = v.revised_claims && v.revised_claims.length ? v.revised_claims : v.claims;
    const word = { supported_current: ["ok", "Supported"], supported_outdated: ["bad", "Outdated source"], unsupported: ["bad", "Unsupported"] };
    els.claims.innerHTML = `<h4 class="th">trace_claim_check</h4><table class="claims-t"><thead><tr><th>verdict</th><th>claim</th><th title="Entailment score from the verifier">score</th></tr></thead><tbody>${
      rowsC.map((c) => {
        const [cls, w] = word[c.label] || ["na", c.label];
        return `<tr><td><span class="st ${cls}">${w}</span></td><td>${esc(c.text)}</td><td>${Number(c.entailment).toFixed(2)}</td></tr>`;
      }).join("")}</tbody></table>`;
  } else {
    els.claims.innerHTML = "";
  }
  if (selected) showSource(row, items.find((i) => i.s.chunk_id === selected.chunkId), items);
  else { els.doc.innerHTML = '<p class="doc-empty">No sources were cited.</p>'; els.log.innerHTML = ""; }
}
function hitTokens(answers, sectionName) {
  const toks = new Set();
  for (const a of answers) {
    for (const m of a.matchAll(/`([^`]+)`/g)) toks.add(m[1].toLowerCase());
    for (const m of a.matchAll(/'([^']{2,})'/g)) toks.add(m[1].toLowerCase());
    for (const m of a.matchAll(/\b\d+(?:\.\d+)*\b/g)) if (m[0].length > 1) toks.add(m[0]);
  }
  toks.delete(sectionName.toLowerCase());
  return [...toks];
}
async function lineageFor(row, chunkId) {
  row.lineages = row.lineages || {};
  if (row.lineages[chunkId]) return row.lineages[chunkId];
  const c = await api(`/chunks/${chunkId}`);
  if (c.status !== 200) return null;
  const l = await api(`/lineages/${c.body.lineage_id}`);
  if (l.status !== 200) return null;
  row.lineages[chunkId] = { ...l.body, source_path: c.body.source_path, section_path: c.body.section_path };
  return row.lineages[chunkId];
}
async function mergedHistory(row, item, items) {
  const name = section(item.s.section_path);
  const related = items.filter((i) => section(i.s.section_path) === name);
  const versions = new Map();
  for (const i of related) {
    const lin = await lineageFor(row, i.s.chunk_id);
    if (!lin) continue;
    for (const v of lin.versions) if (!versions.has(v.id)) versions.set(v.id, { ...v, path: lin.source_path });
  }
  const citers = new Map(related.map((i) => [i.s.chunk_id, i]));
  return { versions: [...versions.values()].sort((a, b) => (a.valid_from || "").localeCompare(b.valid_from || "")), citers };
}
async function showSource(row, item, items) {
  const ref = refDate(row);
  const s = item.s;
  const { versions, citers } = await mergedHistory(row, item, items);
  const shown = versions.find((v) => v.id === selected.versionId) || { ...s, id: s.chunk_id, path: s.source_path };
  const shownItem = citers.get(shown.id);
  const toks = hitTokens(shownItem ? shownItem.answers : item.answers, section(s.section_path));
  let hits = 0;
  const body = (shown.text || s.text || "").split("\n").map((line, i) => {
    const hit = toks.some((t) => line.toLowerCase().includes(t)) && line.trim() !== "";
    if (hit) hits += 1;
    return `<span class="ln${hit ? " hit" : ""}"><span class="n">${i + 1}</span><span class="t">${esc(line) || " "}</span></span>`;
  }).join("");
  const label = shownItem ? `Cited by ${shownItem.by.map((b) => `${b.kind} ${b.label}`).join(", ")}` : "Version";
  els.doc.innerHTML = `<div class="doc-head"><span class="doc-path">${esc(shown.path || s.source_path)} › ${esc(section(s.section_path))}</span>
    <span class="doc-ver">${esc(label)} · <b>${esc(span(shown))}</b></span></div>
    <pre class="doc" tabindex="0" aria-label="Section text">${body}</pre>
    <p class="doc-note">${hits ? "Highlighted: lines containing values from the answer." : "No line matches a value from the answer."}</p>`;
  if (!versions.length) { els.log.innerHTML = '<li><span class="meta">History unavailable right now.</span></li>'; return; }
  const out = [];
  const askedRow = `<li class="asked-row"><span class="log-k">Date asked</span><b>${esc(ref)}</b></li>`;
  let placed = !ref;
  let prevPath = null;
  versions.forEach((v, idx) => {
    const from = day(v.valid_from) || FIRST;
    if (!placed && ref < from) { out.push(askedRow); placed = true; }
    const c = citers.get(v.id);
    const cls = c ? (validity(c.s, ref).cls === "bad" ? "bad" : "ok") : "";
    const moved = prevPath && v.path !== prevPath ? `<span class="meta">moved to <code>${esc(file(v.path))}</code></span>` : "";
    prevPath = v.path;
    out.push(`<li class="${v.id === shown.id ? "cur" : ""} ${cls}"><button type="button" data-version="${v.id}" aria-pressed="${v.id === shown.id}">
      <span class="when">${esc(span(v))}</span>${c ? `<span class="tags">${citedBy(c, cls)}</span>` : ""}${moved}
      <span class="meta">${v.introduced_commit ? `commit <code>${esc(v.introduced_commit.slice(0, 10))}</code>` : "initial version"}</span></button></li>`);
    if (idx === versions.length - 1 && v.valid_until) {
      if (!placed && ref >= day(v.valid_until)) { out.push(askedRow); placed = true; }
      out.push(`<li class="end"><span class="meta">After ${esc(day(v.valid_until))}: the section was renamed or moved; its later versions are tracked separately.</span></li>`);
    }
  });
  if (!placed) out.push(askedRow);
  els.log.innerHTML = out.join("");
}
function closeEvidence() {
  els.evidence.hidden = true;
  els.why.setAttribute("aria-expanded", "false");
  els.why.querySelector("span").textContent = "Why? Show the evidence";
}
els.srcList.addEventListener("click", (e) => {
  const btn = e.target.closest(".src");
  if (!btn || !current) return;
  const id = Number(btn.dataset.chunk);
  selected = { chunkId: id, versionId: id };
  renderEvidence(current);
});
els.log.addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-version]");
  if (!btn || !current || !selected) return;
  selected.versionId = Number(btn.dataset.version);
  const items = evidenceSources(current);
  const item = items.find((i) => i.s.chunk_id === selected.chunkId);
  if (item) showSource(current, item, items);
});
els.why.addEventListener("click", () => {
  if (!els.evidence.hidden) { closeEvidence(); return; }
  els.evidence.hidden = false;
  els.why.setAttribute("aria-expanded", "true");
  els.why.querySelector("span").textContent = "Hide the evidence";
  if (current) renderEvidence(current);
});

/* ---------- ask your own ---------- */
els.fromQ.addEventListener("change", () => { els.date.disabled = els.fromQ.checked; });
els.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = els.q.value.trim();
  els.msg.hidden = true;
  if (q.length < 3) {
    els.msg.textContent = "Type a question of at least 3 characters.";
    els.msg.hidden = false;
    els.q.focus();
    return;
  }
  let asOf = null;
  if (!els.fromQ.checked) {
    const d = els.date.value.trim();
    const ok = /^\d{4}-\d{2}-\d{2}$/.test(d) && !Number.isNaN(Date.parse(d));
    if (!ok || d < FIRST || d > LAST) {
      els.msg.textContent = `Enter a date as YYYY-MM-DD, between ${FIRST} and ${LAST}.`;
      els.msg.hidden = false;
      els.date.focus();
      return;
    }
    asOf = `${d}T23:59:59+00:00`;
  }
  const my = ++seq;
  const row = { q, asOf: asOf ? asOf.slice(0, 10) : null, live: true, trace: null, plain: null, lineages: {} };
  rows.unshift(row);
  if (openIndex >= 0) openIndex += 1;
  openRow(0, { scroll: true });
  els.go.disabled = true;
  els.go.textContent = "Asking…";
  const variant = els.verify.checked ? "temporal_verified" : "temporal";
  const [trace, plain] = await Promise.all([ask(q, variant, asOf), ask(q, "plain", null)]);
  els.go.disabled = false;
  els.go.textContent = "Ask";
  row.trace = trace;
  row.plain = plain;
  if (my !== seq && rows.indexOf(row) !== openIndex) { renderRows(); return; }
  openRow(rows.indexOf(row));
});

/* ---------- circuit board backdrop ---------- */
function buildCircuit() {
  const svg = $("#circuit");
  const W = 1600, H = 1000, G = 20;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const dirs = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]];
  const paths = [];
  for (let n = 0; n < 120; n++) {
    // start near an edge of the board, walk inward with 45-degree turns
    const side = Math.floor(rnd() * 4);
    let x = side === 0 ? 0 : side === 1 ? W : Math.round((rnd() * W) / G) * G;
    let y = side === 2 ? 0 : side === 3 ? H : Math.round((rnd() * H) / G) * G;
    let d = side === 0 ? 0 : side === 1 ? 4 : side === 2 ? 2 : 6;
    let p = `M${x} ${y}`;
    const segs = 3 + Math.floor(rnd() * 4);
    for (let s = 0; s < segs; s++) {
      const len = (2 + Math.floor(rnd() * 9)) * G;
      x += dirs[d][0] * len; y += dirs[d][1] * len;
      p += `L${x} ${y}`;
      d = (d + (rnd() < 0.5 ? 1 : 7)) % 8;
      if (d % 2 === 1 && rnd() < 0.5) d = (d + (rnd() < 0.5 ? 1 : 7)) % 8;
    }
    paths.push({ p, x, y });
  }
  const dl = () => `${(rnd() * 0.7).toFixed(2)}s`;
  let out = "";
  paths.forEach((t, i) => {
    out += `<path d="${t.p}" pathLength="1" class="${i % 5 === 0 ? "hi" : ""}" style="--dl:${dl()}"/>`;
    out += `<circle cx="${t.x}" cy="${t.y}" r="3.2" style="--dl:${dl()}"/>`;
  });
  if (!reduceMotion) {
    paths.filter((_, i) => i % 9 === 0).forEach((t) => {
      out += `<path class="pulse" d="${t.p}" pathLength="100" style="--d:${(5 + rnd() * 6).toFixed(1)}s;--dl:-${(rnd() * 8).toFixed(1)}s"/>`;
    });
  }
  svg.innerHTML = out;
}

/* ---------- rotating tagline (scan-line morph) ---------- */
const TAGLINES = ["Know what was true, and when.", "Answers as of any date.", "Every claim, traced to its source."];
function startTaglines() {
  const h = $("#headline"), a = h.querySelector(".hl-a"), b = h.querySelector(".hl-b");
  const ctr = $("#ctr"), bar = $("#ctr-bar");
  if (reduceMotion) return;
  let i = 0;
  const tick = () => { bar.classList.remove("run"); void bar.offsetWidth; bar.classList.add("run"); };
  tick();
  setInterval(() => {
    i = (i + 1) % TAGLINES.length;
    b.innerHTML = TAGLINES[i]; // constant strings
    h.classList.add("morph");
    setTimeout(() => {
      a.innerHTML = TAGLINES[i];
      h.classList.remove("morph");
      b.innerHTML = "";
      ctr.textContent = String(i + 1).padStart(2, "0");
      tick();
    }, 780);
  }, 5200);
}

/* ---------- intro ---------- */
function runIntro() {
  const root = document.documentElement;
  if (!root.classList.contains("intro-on")) { startTaglines(); return; }
  $("#circuit").classList.add("draw-in");
  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    try { sessionStorage.setItem("trace-intro", "seen"); } catch {}
    root.classList.add("intro-out");
    setTimeout(() => {
      root.classList.remove("intro-on", "intro-out");
      $("#circuit").classList.remove("draw-in");
      startTaglines();
    }, 900);
  };
  const timer = setTimeout(finish, 3100);
  const skip = () => { clearTimeout(timer); finish(); };
  $("#intro").addEventListener("click", skip);
  $("#intro-skip").addEventListener("click", skip);
  addEventListener("keydown", skip, { once: true });
}

/* ---------- start ---------- */
(async function start() {
  buildCircuit();
  runIntro();
  let examples = [];
  try {
    const r = await fetch("examples.json", { cache: "no-cache" });
    if (r.ok) examples = await r.json();
  } catch { examples = []; }
  rows = examples.map((ex) => ({
    q: ex.question, asOf: ex.as_of, live: false, lineages: ex.lineages || {},
    trace: { status: 200, body: ex.trace }, plain: { status: 200, body: ex.plain },
  }));
  if (rows.length) openRow(0);
  else renderRows();
})();
