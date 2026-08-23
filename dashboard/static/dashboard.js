const state = { approvers: [], selected: null, adminKey: null, ledgerFilter: "" };

const esc = (value) => String(value ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
const ago = (value) => { if (!value) return "—"; const seconds = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000); if (seconds < 60) return `${Math.floor(seconds)}s ago`; if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`; return `${Math.floor(seconds / 3600)}h ago`; };
const shortId = id => String(id).length > 12 ? `${String(id).slice(0, 8)}…${String(id).slice(-4)}` : id;
const api = async path => { const response = await fetch(path); if (!response.ok) throw new Error(`${response.status} ${path}`); return response.json(); };
const approverName = id => state.approvers.find(x => x.approver_id === id)?.name || shortId(id || "");
const pressureFraction = state_ => ({ normal: .33, elevated: .66, critical: 1 }[state_] || .05);

function showView(name) {
  document.querySelectorAll(".view").forEach(el => el.classList.toggle("active", el.dataset.view === name));
  document.querySelectorAll(".nav-item").forEach(el => el.classList.toggle("active", el.dataset.view === name));
}
document.querySelectorAll(".nav-item").forEach(btn => btn.addEventListener("click", () => showView(btn.dataset.view)));

function setHealth(live) { const el = document.querySelector("#system-health"); el.className = live ? "live" : "degraded"; el.textContent = live ? "live" : "degraded"; document.querySelector("#health-checked").textContent = new Date().toLocaleTimeString(); }

async function refreshHealth() {
  try { await api("/healthz"); setHealth(true); } catch { setHealth(false); }
  const ready = document.querySelector("#ready-status");
  try { await api("/readyz"); ready.textContent = "ready"; ready.className = "ok"; } catch { ready.textContent = "not ready"; ready.className = "down"; }
}

async function refreshApprovers() {
  try {
    const list = await api("/v1/approvers");
    const cards = await Promise.all(list.approvers.map(async item => ({...item, ...(await api(`/v1/approvers/${item.approver_id}/status`))})));
    state.approvers = cards;
    if (!state.selected || !cards.some(x => x.approver_id === state.selected)) state.selected = cards[0]?.approver_id;

    document.querySelector("#approver-rows").innerHTML = cards.length ? cards.map(item => `<tr class="approver-row ${item.approver_id === state.selected ? "selected" : ""}" data-id="${esc(item.approver_id)}"><td class="name">${esc(item.name || item.email)}</td><td class="state ${esc(item.pressure_state)}">${esc(item.pressure_state)}</td><td>${esc(item.latency_p50_ms)} ms</td><td>${esc(item.queue_depth)}</td><td>${esc(ago(item.state_since))}</td></tr>`).join("") : `<tr><td colspan="5" class="empty">No approvers seeded.</td></tr>`;
    document.querySelectorAll(".approver-row").forEach(row => row.addEventListener("click", () => { state.selected = row.dataset.id; refreshApprovers(); refreshQueue(); showView("queue"); }));

    document.querySelector("#pairs-body").innerHTML = cards.length ? cards.map(item => `<tr><td>${esc(item.name)}</td><td>${item.backup_approver_id ? esc(approverName(item.backup_approver_id)) : "— none configured"}</td></tr>`).join("") : `<tr><td colspan="2" class="empty">No approvers seeded.</td></tr>`;

    const ledgerSelect = document.querySelector("#ledger-filter");
    const prevLedger = ledgerSelect.value;
    ledgerSelect.innerHTML = `<option value="">All approvers</option>` + cards.map(item => `<option value="${esc(item.approver_id)}">${esc(item.name)}</option>`).join("");
    ledgerSelect.value = prevLedger;

    const queueSelect = document.querySelector("#queue-approver-select");
    queueSelect.innerHTML = cards.map(item => `<option value="${esc(item.approver_id)}">${esc(item.name)} — ${esc(item.pressure_state)}</option>`).join("");
    queueSelect.value = state.selected || "";

    document.querySelector("#stat-approvers").textContent = cards.length;
    document.querySelector("#stat-pressure").textContent = cards.filter(x => x.pressure_state !== "normal").length;
    document.querySelector("#stat-queued").textContent = cards.reduce((sum, x) => sum + (x.queue_depth || 0), 0);
    const worstLatency = cards.reduce((max, x) => Math.max(max, x.latency_p50_ms || 0), 0);
    document.querySelector("#stat-latency").textContent = `${worstLatency} ms`;

    document.querySelector("#pressure-bars").innerHTML = cards.length ? cards.map(item => `<div class="pbar-row"><span class="pbar-name">${esc(item.name)}</span><div class="pbar-track"><div class="pbar-fill ${esc(item.pressure_state)}" style="width:${Math.round(pressureFraction(item.pressure_state) * 100)}%"></div></div><span class="pbar-meta">${esc(item.pressure_state)} · q${esc(item.queue_depth)}</span></div>`).join("") : `<div class="empty">No approvers seeded.</div>`;

    refreshQueue();
  } catch { setHealth(false); }
}

async function refreshQueue() {
  if (!state.selected) return;
  try {
    const data = await api(`/v1/approvers/${state.selected}/queue`);
    document.querySelector("#queue-count").textContent = `${data.queue.length} request${data.queue.length === 1 ? "" : "s"}`;
    document.querySelector("#queue-body").innerHTML = data.queue.length ? data.queue.map(row => { const late = new Date(row.deadline).getTime() <= Date.now(); return `<tr class="${late ? "late" : ""}"><td class="short-id" title="${esc(row.request_id)}">${esc(shortId(row.request_id))}</td><td>${esc(row.source_system)}</td><td>${esc(row.request_class)}</td><td>${esc(ago(row.submitted_at))}</td><td class="deadline ${late ? "late" : ""}" data-deadline="${esc(row.deadline)}">${formatCountdown(row.deadline)}</td><td><button data-action="approve" data-id="${esc(row.request_id)}">Force Approve</button><button class="danger" data-action="reassign" data-id="${esc(row.request_id)}">Force Reassign</button></td></tr>`; }).join("") : `<tr><td colspan="6" class="empty">Queue is clear.</td></tr>`;
    document.querySelectorAll("[data-action]").forEach(button => button.addEventListener("click", () => override(button.dataset.id, button.dataset.action)));
  } catch { document.querySelector("#queue-body").innerHTML = `<tr><td colspan="6" class="empty">Queue unavailable.</td></tr>`; }
}
document.querySelector("#queue-approver-select").addEventListener("change", event => { state.selected = event.target.value; refreshApprovers(); refreshQueue(); });

function formatCountdown(deadline) { const seconds = Math.round((new Date(deadline).getTime() - Date.now()) / 1000); if (seconds <= 0) return `OVERDUE ${Math.abs(seconds)}s`; if (seconds < 60) return `${seconds}s`; return `${Math.floor(seconds / 60)}m ${seconds % 60}s`; }
function tickCountdowns() { document.querySelectorAll("[data-deadline]").forEach(cell => { const late = new Date(cell.dataset.deadline).getTime() <= Date.now(); cell.textContent = formatCountdown(cell.dataset.deadline); cell.classList.toggle("late", late); cell.parentElement.classList.toggle("late", late); }); }

async function override(id, action) {
  if (!state.adminKey) state.adminKey = prompt("Admin API key:");
  if (!state.adminKey) return;
  const target = action === "reassign" ? prompt("Target approver ID:") : null;
  if (action === "reassign" && !target) return;
  const response = await fetch(`/v1/decisions/${encodeURIComponent(id)}/override`, { method: "POST", headers: { "Content-Type": "application/json", "X-Admin-Key": state.adminKey }, body: JSON.stringify({ action: action === "approve" ? "force_approve" : "force_reassign", target_approver_id: target, reason: "dashboard manual override" }) });
  if (!response.ok) { alert(`Override failed (${response.status})`); if (response.status === 401) state.adminKey = null; return; }
  await Promise.all([refreshQueue(), refreshLedger()]);
}

async function refreshPolicy() {
  try {
    const data = await api("/v1/config/policy");
    document.querySelector("#policy-body").innerHTML = data.request_classes.length ? data.request_classes.map(item => `<tr><td>${esc(item.name)}</td><td>${esc(item.max_wait_seconds)}s</td><td>${item.auto_approve_threshold != null ? esc(item.auto_approve_threshold) : "disabled"}</td><td>${esc(item.risk_tier)}</td></tr>`).join("") : `<tr><td colspan="4" class="empty">No request classes configured.</td></tr>`;
  } catch { document.querySelector("#policy-body").innerHTML = `<tr><td colspan="4" class="empty">Policy unavailable.</td></tr>`; }
}

async function refreshLedger() {
  try {
    const params = new URLSearchParams({ limit: "200" });
    if (state.ledgerFilter) params.set("approver_id", state.ledgerFilter);
    const data = await api(`/v1/decisions/recent?${params}`);

    document.querySelector("#ledger-count").textContent = `${data.items.length} entries`;
    document.querySelector("#outcome-window").textContent = `window: ${data.items.length}`;
    document.querySelector("#stat-decisions").textContent = data.items.length;

    document.querySelector("#ledger-body").innerHTML = data.items.length ? data.items.map(item => `<tr class="${esc(item.outcome)}"><td>${esc(new Date(item.created_at).toLocaleString())}</td><td class="outcome ${esc(item.outcome)}">${esc(item.outcome)}</td><td>${esc(approverName(item.approver_id))}</td><td class="short-id">${esc(shortId(item.request_id))}</td><td class="ledger-reason">${esc(item.reason)}${item.agent_reasoning ? `<details class="reasoning"><summary>agent reasoning</summary><p>${esc(item.agent_reasoning)}</p></details>` : ""}</td></tr>`).join("") : `<tr><td colspan="5" class="empty">No decisions recorded yet.</td></tr>`;

    const counts = {};
    data.items.forEach(item => { counts[item.outcome] = (counts[item.outcome] || 0) + 1; });
    const outcomes = Object.keys(counts).sort((a, b) => counts[b] - counts[a]);
    document.querySelector("#outcome-strip").innerHTML = outcomes.length ? outcomes.map(outcome => `<div class="kpi"><span class="kpi-label">${esc(outcome)}</span><span class="kpi-value outcome ${esc(outcome)}">${counts[outcome]}</span></div>`).join("") : `<div class="kpi"><span class="kpi-label">no data</span><span class="kpi-value">0</span></div>`;
  } catch {
    document.querySelector("#ledger-body").innerHTML = `<tr><td colspan="5" class="empty">Ledger unavailable.</td></tr>`;
    document.querySelector("#outcome-strip").innerHTML = `<div class="kpi"><span class="kpi-label">ledger unavailable</span><span class="kpi-value">—</span></div>`;
  }
}
document.querySelector("#ledger-filter").addEventListener("change", event => { state.ledgerFilter = event.target.value; refreshLedger(); });

async function refresh() { await refreshHealth(); await refreshApprovers(); await refreshPolicy(); await refreshLedger(); }
refresh(); setInterval(refresh, 2000); setInterval(tickCountdowns, 1000);
