// Trip Trailers — frontend logic: submit, live stage progress, history, export.

const form = document.getElementById("trip-form");
const submitBtn = document.getElementById("submit-btn");
const formStatus = document.getElementById("form-status");
const resultEmpty = document.getElementById("result-empty");
const progress = document.getElementById("progress");
const stageList = document.getElementById("stage-list");
const resultWrap = document.getElementById("result-wrap");
const resultEl = document.getElementById("result");
const resultMeta = document.getElementById("result-meta");
const interestsInput = document.getElementById("interests-input");
const historyList = document.getElementById("history-list");
const historySearch = document.getElementById("history-search");
const elapsedEl = document.getElementById("elapsed");
const refineForm = document.getElementById("refine-form");
const refineInput = document.getElementById("refine-input");
const refineBtn = document.getElementById("refine-btn");
const refineStatus = document.getElementById("refine-status");

let currentJobId = null;
let currentJob = null;
let allPlans = [];
let elapsedTimer = null;

// --- Interest chips ---
document.getElementById("interest-chips").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  const set = parseInterests();
  const v = chip.dataset.v;
  if (set.has(v)) { set.delete(v); chip.classList.remove("active"); }
  else { set.add(v); chip.classList.add("active"); }
  interestsInput.value = [...set].join(", ");
});

function parseInterests() {
  return new Set(
    interestsInput.value.split(",").map((s) => s.trim()).filter(Boolean)
  );
}

// --- Submit ---
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(form);

  const payload = {
    destination: (fd.get("destination") || "").trim(),
    origin: (fd.get("origin") || "").trim() || null,
    duration_days: parseInt(fd.get("duration_days"), 10) || 1,
    travelers: parseInt(fd.get("travelers"), 10) || 1,
    budget: (fd.get("budget") || "").trim() || null,
    start_date: (fd.get("start_date") || "").trim() || null,
    interests: [...parseInterests()],
    pace: fd.get("pace") || "balanced",
    notes: (fd.get("notes") || "").trim() || null,
  };

  setBusy(true);
  formStatus.textContent = "";
  try {
    const res = await fetch("/api/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${res.status})`);
    }
    const { job_id } = await res.json();
    currentJobId = job_id;
    showProgress();
    pollJob(job_id);
  } catch (err) {
    setBusy(false);
    formStatus.textContent = err.message;
  }
});

function setBusy(busy) {
  submitBtn.disabled = busy;
  submitBtn.textContent = busy ? "Planning…" : "Plan my trip";
}

function showProgress() {
  resultEmpty.hidden = true;
  resultWrap.hidden = true;
  progress.hidden = false;
  stageList.innerHTML = "";
  startElapsed();
}

function startElapsed() {
  const t0 = Date.now();
  const tick = () => {
    const s = Math.floor((Date.now() - t0) / 1000);
    const m = Math.floor(s / 60);
    elapsedEl.textContent = m
      ? `· ${m}m ${String(s % 60).padStart(2, "0")}s elapsed`
      : `· ${s}s elapsed`;
  };
  stopElapsed();
  tick();
  elapsedTimer = setInterval(tick, 1000);
}

function stopElapsed() {
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
}

function renderStages(stages) {
  if (!stages || !stages.length) return;
  stageList.innerHTML = stages
    .map((s) => {
      const icon = s.status === "done" ? "✓" : "";
      return `<li class="${s.status}"><span class="dot">${icon}</span>${s.label}</li>`;
    })
    .join("");
}

async function pollJob(jobId) {
  try {
    const res = await fetch(`/api/plan/${jobId}`);
    if (!res.ok) throw new Error(`Lost the job (${res.status})`);
    const job = await res.json();
    renderStages(job.progress);

    if (job.status === "completed") {
      finish(job);
      loadHistory();
    } else if (job.status === "failed") {
      fail(job.error || "Planning failed.");
      loadHistory();
    } else {
      setTimeout(() => pollJob(jobId), 3000);
    }
  } catch (err) {
    fail(err.message);
  }
}

function finish(job) {
  stopElapsed();
  currentJobId = job.job_id;
  currentJob = job;
  progress.hidden = true;
  resultEmpty.hidden = true;
  resultEl.innerHTML = renderMarkdown(job.result_markdown || "_No plan produced._");
  const r = job.request;
  resultMeta.textContent =
    `${r.destination} · ${r.duration_days} days · ${r.travelers} traveler(s)`;
  resultWrap.hidden = false;
  refineStatus.textContent = "";
  refineInput.value = "";
  setBusy(false);
  formStatus.textContent = "Done — happy travels! ✦";
}

function fail(message) {
  stopElapsed();
  progress.hidden = true;
  resultEmpty.hidden = false;
  resultWrap.hidden = true;
  setBusy(false);
  formStatus.textContent = `Error: ${message}`;
}

// --- Export ---
document.getElementById("download-btn").addEventListener("click", () => {
  if (currentJobId) window.location = `/api/plan/${currentJobId}/download`;
});
document.getElementById("print-btn").addEventListener("click", () => window.print());

// Copy the plan's Markdown to the clipboard.
document.getElementById("copy-btn").addEventListener("click", async (e) => {
  const md = currentJob && currentJob.result_markdown;
  if (!md) return;
  const btn = e.currentTarget;
  const original = btn.textContent;
  try {
    await navigator.clipboard.writeText(md);
    btn.textContent = "✓ Copied";
  } catch {
    btn.textContent = "Copy failed";
  }
  setTimeout(() => { btn.textContent = original; }, 1600);
});

// Download a self-contained, styled HTML file built from the rendered plan.
document.getElementById("html-btn").addEventListener("click", () => {
  if (!currentJob) return;
  const title = (currentJob.request.destination || "Trip") + " — Trip Trailers";
  const doc = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${escapeHtml(title)}</title>
<style>
  body { font: 16px/1.6 -apple-system, Segoe UI, Roboto, sans-serif; max-width: 760px;
    margin: 2.5rem auto; padding: 0 1.25rem; color: #1c2530; }
  h1,h2,h3 { font-family: Georgia, serif; line-height: 1.25; margin-top: 1.6em; }
  h1 { font-size: 1.9rem; } h2 { font-size: 1.4rem; } h3 { font-size: 1.15rem; }
  table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
  th,td { border: 1px solid #d9dee5; padding: .5rem .7rem; text-align: left; }
  th { background: #f4f6f9; }
  code { background: #f4f6f9; padding: .1em .35em; border-radius: 4px; }
  blockquote { border-left: 3px solid #c7d0db; margin: 1em 0; padding-left: 1em; color: #5a6573; }
  a { color: #2563a8; }
  hr { border: 0; border-top: 1px solid #e3e8ee; margin: 2em 0; }
  footer { margin-top: 3rem; font-size: .85rem; color: #8a93a0; }
</style></head><body>
${resultEl.innerHTML}
<footer>Generated by Trip Trailers · a crew of AI travel specialists.</footer>
</body></html>`;
  const blob = new Blob([doc], { type: "text/html;charset=utf-8" });
  const slug = (currentJob.request.destination || "trip")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "trip";
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `trip-trailers-${slug}.html`;
  a.click();
  URL.revokeObjectURL(a.href);
});

// --- Refine (conversational follow-up edit) ---
refineForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const instruction = refineInput.value.trim();
  if (!instruction || !currentJobId) return;
  refineBtn.disabled = true;
  refineBtn.textContent = "Refining…";
  refineStatus.textContent = "Your concierge is revising the plan…";
  try {
    const res = await fetch(`/api/plan/${currentJobId}/refine`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Refine failed (${res.status})`);
    }
    const job = await res.json();
    currentJob = job;
    resultEl.innerHTML = renderMarkdown(job.result_markdown || "");
    refineInput.value = "";
    refineStatus.textContent = "Updated ✓";
    resultEl.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    refineStatus.textContent = `Error: ${err.message}`;
  } finally {
    refineBtn.disabled = false;
    refineBtn.textContent = "Refine ✦";
  }
});

// --- History ---
document.getElementById("refresh-history").addEventListener("click", loadHistory);

async function loadHistory() {
  try {
    const res = await fetch("/api/plans");
    if (!res.ok) return;
    allPlans = await res.json();
    renderHistory();
  } catch { /* ignore */ }
}

function renderHistory() {
  const q = (historySearch.value || "").trim().toLowerCase();
  const plans = q
    ? allPlans.filter((p) => p.destination.toLowerCase().includes(q))
    : allPlans;

  if (!plans.length) {
    historyList.innerHTML = `<li class="history-empty">${
      q ? "No matches." : "No trips yet."
    }</li>`;
    return;
  }
  historyList.innerHTML = plans
    .map((p) => {
      const date = new Date(p.created_at * 1000).toLocaleDateString();
      return `<li class="history-item" data-id="${p.job_id}">
        <div class="hi-body">
          <div class="hi-dest">${escapeHtml(p.destination)}</div>
          <div class="hi-meta">${p.duration_days}d · ${date}
            <span class="badge ${p.status}">${p.status}</span></div>
        </div>
        <div class="hi-actions">
          <button class="hi-icon" data-replan="${p.job_id}" title="Re-plan with these settings">↻</button>
          <button class="hi-icon hi-del" data-del="${p.job_id}" title="Delete">✕</button>
        </div>
      </li>`;
    })
    .join("");
}

historySearch.addEventListener("input", renderHistory);

historyList.addEventListener("click", async (e) => {
  const del = e.target.closest("[data-del]");
  if (del) {
    e.stopPropagation();
    await fetch(`/api/plan/${del.dataset.del}`, { method: "DELETE" });
    loadHistory();
    return;
  }
  const replan = e.target.closest("[data-replan]");
  if (replan) {
    e.stopPropagation();
    prefillFromJob(replan.dataset.replan);
    return;
  }
  const item = e.target.closest(".history-item");
  if (item) openPlan(item.dataset.id);
});

// --- Re-plan: load a past trip's settings back into the form ---
async function prefillFromJob(jobId) {
  const res = await fetch(`/api/plan/${jobId}`);
  if (!res.ok) return;
  const job = await res.json();
  const r = job.request;
  form.destination.value = r.destination || "";
  form.origin.value = r.origin || "";
  form.duration_days.value = r.duration_days || 1;
  form.travelers.value = r.travelers || 1;
  form.budget.value = r.budget || "";
  form.start_date.value = /^\d{4}-\d{2}-\d{2}$/.test(r.start_date || "") ? r.start_date : "";
  form.pace.value = r.pace || "balanced";
  form.notes.value = r.notes || "";
  interestsInput.value = (r.interests || []).join(", ");
  // Re-sync the interest chips with the loaded values.
  const set = parseInterests();
  document.querySelectorAll("#interest-chips .chip").forEach((chip) => {
    chip.classList.toggle("active", set.has(chip.dataset.v));
  });
  form.scrollIntoView({ behavior: "smooth", block: "start" });
  form.destination.focus();
  formStatus.textContent = "Loaded settings — tweak and re-plan.";
}

async function openPlan(jobId) {
  formStatus.textContent = "";
  const res = await fetch(`/api/plan/${jobId}`);
  if (!res.ok) return;
  const job = await res.json();
  if (job.status === "completed") {
    finish(job);
  } else if (job.status === "failed") {
    fail(job.error || "This trip failed to generate.");
  } else {
    currentJobId = jobId;
    showProgress();
    pollJob(jobId);
  }
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

loadHistory();

// --- Minimal, dependency-free Markdown renderer ---
function renderMarkdown(md) {
  const esc = (s) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const inline = (s) =>
    esc(s)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let i = 0;
  let listType = null;

  const closeList = () => {
    if (listType) { out.push(`</${listType}>`); listType = null; }
  };

  while (i < lines.length) {
    let line = lines[i];

    // Tables
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length &&
        /^\s*\|?[\s:-]+\|[\s:|-]*$/.test(lines[i + 1])) {
      closeList();
      const header = splitRow(line);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
        rows.push(splitRow(lines[i]));
        i++;
      }
      out.push("<table><thead><tr>" +
        header.map((c) => `<th>${inline(c)}</th>`).join("") +
        "</tr></thead><tbody>" +
        rows.map((r) => "<tr>" + r.map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>").join("") +
        "</tbody></table>");
      continue;
    }

    // Headings
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      closeList();
      const level = Math.min(h[1].length, 3);
      out.push(`<h${level}>${inline(h[2])}</h${level}>`);
      i++; continue;
    }

    // Horizontal rule
    if (/^\s*([-*_])\1\1+\s*$/.test(line)) {
      closeList(); out.push("<hr />"); i++; continue;
    }

    // Blockquote
    if (/^\s*>\s?/.test(line)) {
      closeList();
      out.push(`<blockquote>${inline(line.replace(/^\s*>\s?/, ""))}</blockquote>`);
      i++; continue;
    }

    // Lists
    const ul = line.match(/^\s*[-*+]\s+(.*)$/);
    const ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (ul || ol) {
      const want = ul ? "ul" : "ol";
      if (listType && listType !== want) closeList();
      if (!listType) { listType = want; out.push(`<${want}>`); }
      out.push(`<li>${inline((ul || ol)[1])}</li>`);
      i++; continue;
    }

    // Blank line
    if (/^\s*$/.test(line)) { closeList(); i++; continue; }

    // Paragraph
    closeList();
    out.push(`<p>${inline(line)}</p>`);
    i++;
  }
  closeList();
  return out.join("\n");
}

function splitRow(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}
