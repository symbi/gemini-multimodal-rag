/* Multimodal RAG GUI glue */
"use strict";

const $ = (id) => document.getElementById(id);

let pollTimer = null;

/* ---------- upload ---------- */

function setupUpload() {
  const dz = $("dropzone");
  const input = $("file-input");

  dz.addEventListener("click", () => input.click());
  dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("dragover"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
  dz.addEventListener("drop", (e) => {
    e.preventDefault();
    dz.classList.remove("dragover");
    uploadFiles([...e.dataTransfer.files]);
  });
  input.addEventListener("change", () => { uploadFiles([...input.files]); input.value = ""; });
}

async function uploadFiles(files) {
  if (!files.length) return;
  const status = $("upload-status");
  status.hidden = false;
  status.className = "status-line";
  status.textContent = `Uploading ${files.length} file(s)…`;

  const fd = new FormData();
  files.forEach((f) => fd.append("files", f, f.name));
  try {
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    status.className = "status-line ok";
    status.textContent = `Uploaded ${data.documents.length} file(s). Embedding started.`;
    refreshDocs(true);
  } catch (err) {
    status.className = "status-line error";
    status.textContent = `Upload failed: ${err.message}`;
  }
}

/* ---------- documents table ---------- */

async function refreshDocs(keepPolling = false) {
  const tbody = $("docs-tbody");
  try {
    const res = await fetch("/api/documents");
    const data = await res.json();
    const docs = data.documents || [];
    $("doc-count").textContent = docs.length ? `(${docs.length})` : "";

    if (!docs.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty">No documents yet — upload some above.</td></tr>`;
      stopPolling();
      return;
    }

    tbody.innerHTML = "";
    for (const d of docs) {
      const tr = document.createElement("tr");
      const err = d.error ? ` title="${escapeHtml(d.error)}"` : "";
      tr.innerHTML = `
        <td class="fname"><a href="/api/media/${d.id}" target="_blank" rel="noopener">${escapeHtml(d.filename)}</a></td>
        <td><span class="badge ${d.modality}">${d.modality}</span></td>
        <td><span class="status ${d.status}"${err}>${d.status}</span></td>
        <td>${d.chunk_count ?? 0}</td>
        <td class="hint">${fmtSize(d.size_bytes)}</td>
        <td>
          <button class="danger" data-act="reembed" data-id="${d.id}">Re-embed</button>
          <button class="danger" data-act="delete" data-id="${d.id}">Delete</button>
        </td>`;
      tbody.appendChild(tr);
    }

    const busy = docs.some((d) => d.status === "pending" || d.status === "processing");
    if (busy && keepPolling !== false) {
      startPolling();
    } else {
      stopPolling();
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty">Failed to load documents: ${escapeHtml(err.message)}</td></tr>`;
    stopPolling();
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(() => refreshDocs(true), 2000);
}
function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

async function embedPending() {
  // Re-trigger embedding for anything not yet embedded
  const res = await fetch("/api/documents");
  const data = await res.json();
  const pending = (data.documents || []).filter((d) => d.status !== "embedded");
  if (!pending.length) { alert("Nothing pending — everything is embedded."); return; }
  for (const d of pending) {
    await fetch(`/api/reembed/${d.id}`, { method: "POST" });
  }
  refreshDocs(true);
}

/* ---------- query ---------- */

async function askQuestion(ev) {
  ev.preventDefault();
  const q = $("question-input").value.trim();
  if (!q) return;
  const modality = $("modality-filter").value || null;
  const topK = parseInt($("topk-select").value, 10);

  $("ask-btn").disabled = true;
  $("query-status").hidden = false;
  $("query-status").className = "status-line";
  $("query-status").textContent = "Searching & reasoning…";
  $("answer-panel").hidden = true;
  $("results-panel").hidden = true;

  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, top_k: topK, modality }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    renderAnswer(data);
    renderChunks(data.chunks || [], data.citations || []);
  } catch (err) {
    $("query-status").className = "status-line error";
    $("query-status").textContent = `Query failed: ${err.message}`;
  } finally {
    $("ask-btn").disabled = false;
  }
}

function renderAnswer(data) {
  $("query-status").hidden = true;
  $("answer-panel").hidden = false;
  // highlight [n] citations in the answer
  const html = escapeHtml(data.answer || "(no answer)")
    .replace(/\[(\d{1,2})\]/g, '<span class="cited">[$1]</span>');
  $("answer-body").innerHTML = html.replace(/\n/g, "<br>");
}

function renderChunks(chunks, citations) {
  const wrap = $("results-body");
  wrap.innerHTML = "";
  if (!chunks.length) {
    wrap.innerHTML = '<p class="hint">No chunks retrieved.</p>';
    $("results-panel").hidden = false;
    return;
  }
  const citedSet = new Set(citations);
  chunks.forEach((ch, i) => {
    const n = i + 1;
    const card = document.createElement("div");
    card.className = "chunk-card" + (citedSet.has(n) ? " used" : "");
    const sim = typeof ch.similarity === "number" ? ch.similarity.toFixed(3) : "?";
    const head = `
      <div class="chunk-head">
        <span class="chunk-num">${n}</span>
        <span class="badge ${ch.modality}">${ch.modality}</span>
        <span class="chunk-title">${escapeHtml(ch.filename || "?")}</span>
        <span class="score-chip">sim ${sim}</span>
      </div>`;
    let mediaHtml = "";
    if (ch.modality === "image" && ch.document_id) {
      mediaHtml = `<div class="chunk-thumb"><a href="/api/media/${ch.document_id}" target="_blank" rel="noopener">
        <img src="/api/media/${ch.document_id}" alt="${escapeHtml(ch.filename || "image")}" loading="lazy"></a></div>`;
    } else if (ch.modality === "video" && ch.document_id) {
      mediaHtml = `<div class="chunk-thumb"><video src="/api/media/${ch.document_id}" controls preload="metadata"></video></div>`;
    } else if (ch.modality === "audio" && ch.document_id) {
      mediaHtml = `<div class="chunk-thumb"><audio src="/api/media/${ch.document_id}" controls preload="metadata"></audio></div>`;
    }
    card.innerHTML = head + mediaHtml + `
      <div class="chunk-text">${escapeHtml(ch.content_text || "")}</div>`;
    wrap.appendChild(card);
  });
  $("results-panel").hidden = false;
}

/* ---------- helpers ---------- */

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function fmtSize(bytes) {
  if (bytes == null) return "?";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/* ---------- wire up ---------- */

document.addEventListener("DOMContentLoaded", () => {
  setupUpload();
  $("refresh-btn").addEventListener("click", () => refreshDocs(true));
  $("embed-pending-btn").addEventListener("click", embedPending);
  $("query-form").addEventListener("submit", askQuestion);
  $("docs-tbody").addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const id = btn.dataset.id;
    if (btn.dataset.act === "delete") {
      if (!confirm("Delete this document, its chunks, and the local file?")) return;
      await fetch(`/api/documents/${id}`, { method: "DELETE" });
      refreshDocs(true);
    } else if (btn.dataset.act === "reembed") {
      await fetch(`/api/reembed/${id}`, { method: "POST" });
      refreshDocs(true);
    }
  });
  refreshDocs(true);
  loadInfo();
});

async function loadInfo() {
  try {
    const res = await fetch("/api/info");
    const info = await res.json();
    const el = $("codex-model-label");
    if (el) el.textContent = info.codex_model || "codex";
  } catch { /* footer label is cosmetic */ }
}
