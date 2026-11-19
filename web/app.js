/* TRACE web demo: then-vs-now verdict (TRACE vs plain RAG) and a git-history view of the evidence.
   Calls the TRACE API: POST /ask, GET /chunks/{id}, GET /lineages/{id}. Example answers are
   precomputed in examples.json (scripts/build_web_examples.py) so the first screen never waits. */
"use strict";

const API = (window.TRACE_API || "").replace(/\/$/, "");
const FIRST = "2021-01-01";
const LAST = "2026-11-13";
const $ = (sel) => document.querySelector(sel);

const els = {
  form: $("#ask"), q: $("#q"), ex: $("#ex"), date: $("#date"), fromQ: $("#from-q"), verify: $("#verify"),
  go: $("#go"), msg: $("#form-msg"), verdict: $("#verdict"), asked: $("#asked"),
  trace: $("#p-trace .p-body"), plain: $("#p-plain .p-body"), hTrace: $("#h-trace"), why: $("#why"),
  evidence: $("#evidence"), srcList: $("#src-list"), claims: $("#claims"), doc: $("#ev-doc"), log: $("#log"),
};

let examples = [];
let current = null; // { q, trace: {status, body}, plain: {status, body}, lineages: {} }
let seq = 0; // guards against out-of-order responses

/* ---------- helpers ---------- */
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
function day(iso) { return iso ? iso.slice(0, 10) : null; }
function section(path) { return path.split(" > ").pop(); }
function file(path) { return path.split("/").pop(); }

/** The answer as safe HTML. Citations become chips; a chip for a version not valid on the date
 *  asked is red and carries the dagger that keys it to the verdict line below. */
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
};

/** Was this source valid on the date asked? -> {cls, word, why} */
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
function refDate(result) {
  const t = result.trace.status === 200 ? result.trace.body.time : null;
  return t ? day(t.as_of) : null;
}
function span(s) { return `${day(s.valid_from) || FIRST} – ${day(s.valid_until) || "now"}`; }

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

/* ---------- verdict ---------- */
function renderAsked(result) {
  const t = result.trace.status === 200 ? result.trace.body.time : null;
  if (!t) { els.asked.innerHTML = `<span class="asked-q show">Asked: “${esc(result.q)}”</span>`; return; }
  let why = "date you set";
  if (t.assumed) why = "no date in the question, so today";
  else if (t.source !== "explicit") why = `read from “${esc(t.matched)}”`;
  const parts = [
    `<span class="asked-q">Asked: “${esc(result.q)}”</span>`,
    `<span><span class="k">As of</span><b class="nw">${esc(day(t.as_of))}</b> <span class="note">${why}</span></span>`,
  ];
  const ts = cited(result.trace.body);
  if (ts.length) parts.push(`<span class="ex-k"><span class="k">TRACE source</span><span class="nw">${esc(span(ts[0]))}</span></span>`);
  if (result.plain.status === 200) {
    const ref = day(t.as_of);
    const bad = cited(result.plain.body).find((s) => validity(s, ref).cls === "bad");
    if (bad) parts.push(`<span class="ex-k"><span class="k">Plain RAG source</span><span class="nw stale">${esc(span(bad))}</span></span>`);
  }
  parts.push('<span class="ex-k corpus"><span class="k">Corpus</span>Vite docs, 2020-12 – 2026-11-13</span>');
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
    const rows = v.revised_claims && v.revised_claims.length ? v.revised_claims : v.claims;
    const ok = rows.filter((c) => c.label === "supported_current").length;
    html += `<p class="claims-line"><b>${ok} of ${rows.length}</b> claims supported by a source valid on that date</p>`;
  }
  return html;
}

function renderVerdict(result) {
  const ref = refDate(result);
  renderAsked(result);
  const verified = result.trace.status === 200 && result.trace.body.verification;
  els.hTrace.textContent = verified ? "TRACE + claim check" : "TRACE";
  els.trace.innerHTML = panelHtml("trace", result.trace, ref);
  els.plain.innerHTML = panelHtml("plain", result.plain, ref);
  els.verdict.classList.remove("landed");
  void els.verdict.offsetWidth; // restart the landing animation
  els.verdict.classList.add("landed");
  const any = [result.trace, result.plain].some((r) => r.status === 200 && cited(r.body).length);
  els.why.hidden = !any;
  if (!els.evidence.hidden) renderEvidence(result);
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

/** Every cited version, with which system cited it under which label. */
function evidenceSources(result) {
  const out = new Map();
  for (const [kind, res] of [["TRACE", result.trace], ["Plain RAG", result.plain]]) {
    if (res.status !== 200) continue;
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

function renderEvidence(result) {
  const ref = refDate(result);
  const items = evidenceSources(result);
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
      ${v.word ? `<span class="sstat"><span class="st ${v.cls}">${v.word} on ${esc(ref)}</span></span>` : ""}</button></li>`;
  }).join("");

  const v = result.trace.status === 200 && result.trace.body.verification;
  if (v && v.claims && v.claims.length) {
    const rows = v.revised_claims && v.revised_claims.length ? v.revised_claims : v.claims;
    const word = { supported_current: ["ok", "Supported"], supported_outdated: ["bad", "Outdated source"], unsupported: ["bad", "Unsupported"] };
    els.claims.innerHTML = `<h3 class="th">TRACE claim check</h3><table class="claims-t"><thead><tr><th class="th">Verdict</th><th class="th">Claim</th><th class="th" title="Entailment score from the verifier">Score</th></tr></thead><tbody>${
      rows.map((c) => {
        const [cls, w] = word[c.label] || ["na", c.label];
        return `<tr><td><span class="st ${cls}">${w}</span></td><td>${esc(c.text)}</td><td>${Number(c.entailment).toFixed(2)}</td></tr>`;
      }).join("")}</tbody></table>`;
  } else {
    els.claims.innerHTML = "";
  }
  if (selected) showSource(result, items.find((i) => i.s.chunk_id === selected.chunkId), items);
  else { els.doc.innerHTML = '<p class="doc-empty">No sources were cited.</p>'; els.log.innerHTML = ""; }
}

/** Tokens worth highlighting: numbers, `code`, and quoted values from the answers that cite this source. */
function hitTokens(answers, sectionName) {
  const toks = new Set();
  for (const a of answers) {
    for (const m of a.matchAll(/`([^`]+)`/g)) toks.add(m[1].toLowerCase());
    for (const m of a.matchAll(/'([^']{2,})'/g)) toks.add(m[1].toLowerCase());
    for (const m of a.matchAll(/\b\d+(?:\.\d+)*\b/g)) if (m[0].length > 1) toks.add(m[0]);
  }
  toks.delete(sectionName.toLowerCase()); // the section's own name is not a value from the answer
  return [...toks];
}

async function lineageFor(result, chunkId) {
  result.lineages = result.lineages || {};
  if (result.lineages[chunkId]) return result.lineages[chunkId];
  const c = await api(`/chunks/${chunkId}`);
  if (c.status !== 200) return null;
  const l = await api(`/lineages/${c.body.lineage_id}`);
  if (l.status !== 200) return null;
  result.lineages[chunkId] = { ...l.body, source_path: c.body.source_path, section_path: c.body.section_path };
  return result.lineages[chunkId];
}

/** One history for the section: the selected version's lineage merged with the lineages of every
 *  other cited version of the same section (a section can move between files), so the versions both
 *  systems cited sit on one log. */
async function mergedHistory(result, item, items) {
  const name = section(item.s.section_path);
  const related = items.filter((i) => section(i.s.section_path) === name);
  const versions = new Map();
  for (const i of related) {
    const lin = await lineageFor(result, i.s.chunk_id);
    if (!lin) continue;
    for (const v of lin.versions) if (!versions.has(v.id)) versions.set(v.id, { ...v, path: lin.source_path });
  }
  const citers = new Map(related.map((i) => [i.s.chunk_id, i]));
  return { versions: [...versions.values()].sort((a, b) => (a.valid_from || "").localeCompare(b.valid_from || "")), citers };
}

async function showSource(result, item, items) {
  const ref = refDate(result);
  const s = item.s;
  const { versions, citers } = await mergedHistory(result, item, items);
  const shown = versions.find((v) => v.id === selected.versionId) || { ...s, id: s.chunk_id, path: s.source_path };
  const shownItem = citers.get(shown.id);
  const toks = hitTokens(shownItem ? shownItem.answers : item.answers, section(s.section_path));
  const text = shown.text || s.text || "";

  let hits = 0;
  const body = text.split("\n").map((line, i) => {
    const low = line.toLowerCase();
    const hit = toks.some((t) => low.includes(t)) && line.trim() !== "";
    if (hit) hits += 1;
    return `<span class="ln${hit ? " hit" : ""}"><span class="n">${i + 1}</span><span class="t">${esc(line) || " "}</span></span>`;
  }).join("");
  const label = shownItem ? `Cited by ${shownItem.by.map((b) => `${b.kind} ${b.label}`).join(", ")}` : "Version";
  els.doc.innerHTML = `<div class="doc-head"><span class="doc-path">${esc(shown.path || s.source_path)} › ${esc(section(s.section_path))}</span>
    <span class="doc-ver">${esc(label)} · <b>${esc(span(shown))}</b></span></div>
    <pre class="doc" tabindex="0" aria-label="Section text">${body}</pre>
    <p class="doc-note">${hits ? "Highlighted: lines containing values from the answer." : "No line matches a value from the answer."}</p>`;

  if (!versions.length) { els.log.innerHTML = '<li><span class="meta">History unavailable right now.</span></li>'; return; }
  const rows = [];
  const askedRow = `<li class="asked-row"><span class="log-k">Date asked</span> <b>${esc(ref)}</b></li>`;
  let askedPlaced = !ref;
  let prevPath = null;
  versions.forEach((v, idx) => {
    const from = day(v.valid_from) || FIRST;
    if (!askedPlaced && ref < from) { rows.push(askedRow); askedPlaced = true; }
    const c = citers.get(v.id);
    const cls = c ? (validity(c.s, ref).cls === "bad" ? "bad" : "ok") : "";
    const tags = c ? citedBy(c, cls) : "";
    const moved = prevPath && v.path !== prevPath ? `<span class="meta">moved to <code>${esc(file(v.path))}</code></span>` : "";
    prevPath = v.path;
    rows.push(`<li class="${v.id === shown.id ? "cur" : ""} ${cls}"><button type="button" data-version="${v.id}" aria-pressed="${v.id === shown.id}">
      <span class="when">${esc(span(v))}</span>${tags ? `<span class="tags">${tags}</span>` : ""}${moved}
      <span class="meta">${v.introduced_commit ? `commit <code>${esc(v.introduced_commit.slice(0, 10))}</code>` : "initial version"}</span></button></li>`);
    const last = idx === versions.length - 1;
    if (last && v.valid_until) {
      if (!askedPlaced && ref >= day(v.valid_until)) { rows.push(askedRow); askedPlaced = true; }
      rows.push(`<li class="end"><span class="meta">After ${esc(day(v.valid_until))}: the section was renamed or moved; its later versions are tracked separately.</span></li>`);
    }
  });
  if (!askedPlaced) rows.push(askedRow);
  els.log.innerHTML = rows.join("");
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
  els.evidence.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
});

/* ---------- examples and the form ---------- */
function showExample(i) {
  const ex = examples[i];
  els.ex.value = String(i);
  els.q.value = ex.question;
  els.fromQ.checked = !ex.as_of;
  els.date.disabled = !ex.as_of;
  if (ex.as_of) els.date.value = ex.as_of;
  current = { q: ex.question, trace: { status: 200, body: ex.trace }, plain: { status: 200, body: ex.plain }, lineages: ex.lineages || {} };
  selected = null;
  els.verdict.setAttribute("aria-busy", "false");
  renderVerdict(current);
}
els.ex.addEventListener("change", () => {
  if (els.ex.value !== "") showExample(Number(els.ex.value));
});
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
    const valid = /^\d{4}-\d{2}-\d{2}$/.test(d) && !Number.isNaN(Date.parse(d));
    if (!valid || d < FIRST || d > LAST) {
      els.msg.textContent = `Enter a date as YYYY-MM-DD, between ${FIRST} and ${LAST}.`;
      els.msg.hidden = false;
      els.date.focus();
      return;
    }
    asOf = `${d}T23:59:59+00:00`;
  }
  const my = ++seq;
  els.ex.value = "";
  showLoading(q);
  els.go.disabled = true;
  els.go.textContent = "Asking…";
  const variant = els.verify.checked ? "temporal_verified" : "temporal";
  const [trace, plain] = await Promise.all([ask(q, variant, asOf), ask(q, "plain", null)]);
  if (my !== seq) return;
  els.go.disabled = false;
  els.go.textContent = "Ask";
  els.verdict.setAttribute("aria-busy", "false");
  current = { q, trace, plain, lineages: {} };
  selected = null;
  renderVerdict(current);
});

/* ---------- start ---------- */
(async function start() {
  try {
    const r = await fetch("examples.json", { cache: "no-cache" });
    if (r.ok) examples = await r.json();
  } catch { examples = []; }
  els.ex.insertAdjacentHTML("beforeend", examples.map((ex, i) =>
    `<option value="${i}" title="${esc(ex.question)}">${esc(ex.label || ex.question)}${ex.as_of ? ` · ${esc(ex.as_of)}` : ""}</option>`).join(""));
  if (examples.length) {
    showExample(0);
  } else {
    els.q.value = "What port does vite preview use by default?";
    els.form.requestSubmit();
  }
})();
