const state = { approvers: [], selected: null, adminKey: null };

const esc = (value) => String(value ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
const ago = (value) => { if (!value) return "—"; const seconds = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000); if (seconds < 60) return `${Math.floor(seconds)}s ago`; if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`; return `${Math.floor(seconds / 3600)}h ago`; };
const shortId = id => String(id).length > 12 ? `${String(id).slice(0, 8)}…${String(id).slice(-4)}` : id;
const api = async path => { const response = await fetch(path); if (!response.ok) throw new Error(`${response.status} ${path}`); return response.json(); };

function setHealth(live) { const el = document.querySelector("#system-health"); el.className = `health ${live ? "live" : "degraded"}`; el.querySelector("span").textContent = live ? "live" : "degraded"; }

async function refreshHealth() { try { await Promise.all([api("/healthz"), api("/readyz")]); setHealth(true); } catch { setHealth(false); } }

async function refreshApprovers() {
  try {
    const list = await api("/v1/approvers");
    const cards = await Promise.all(list.approvers.map(async item => ({...item, ...(await api(`/v1/approvers/${item.approver_id}/status`))})));
    state.approvers = cards;
    if (!state.selected || !cards.some(x => x.approver_id === state.selected)) state.selected = cards[0]?.approver_id;
    document.querySelector("#approver-cards").innerHTML = cards.map(item => `<article class="card ${item.approver_id === state.selected ? "selected" : ""}" data-id="${esc(item.approver_id)}"><div class="card-name">${esc(item.name || item.email)}</div><span class="badge ${esc(item.pressure_state)}">${esc(item.pressure_state)}</span><div class="metrics"><div class="metric"><label>latency p50</label><strong>${esc(item.latency_p50_ms)}<small> ms</small></strong></div><div class="metric"><label>queue</label><strong>${esc(item.queue_depth)}</strong></div><div class="metric"><label>state since</label><strong><small>${esc(ago(item.state_since))}</small></strong></div></div></article>`).join("");
    document.querySelectorAll(".card").forEach(card => card.addEventListener("click", () => { state.selected = card.dataset.id; refreshApprovers(); refreshQueue(); }));
    refreshQueue();
  } catch { setHealth(false); }
}

async function refreshQueue() {
  if (!state.selected) return;
  try {
    const data = await api(`/v1/approvers/${state.selected}/queue`);
    const approver = state.approvers.find(x => x.approver_id === state.selected);
    document.querySelector("#queue-title").textContent = `Queue — ${approver?.name || shortId(state.selected)}`;
    document.querySelector("#queue-count").textContent = `${data.queue.length} request${data.queue.length === 1 ? "" : "s"}`;
    document.querySelector("#queue-body").innerHTML = data.queue.length ? data.queue.map(row => { const late = new Date(row.deadline).getTime() <= Date.now(); return `<tr class="${late ? "late" : ""}"><td class="mono short-id" title="${esc(row.request_id)}">${esc(shortId(row.request_id))}</td><td>${esc(row.source_system)}</td><td>${esc(row.request_class)}</td><td class="mono">${esc(ago(row.submitted_at))}</td><td class="mono deadline ${late ? "late" : ""}" data-deadline="${esc(row.deadline)}">${formatCountdown(row.deadline)}</td><td><button data-action="approve" data-id="${esc(row.request_id)}">Force Approve</button><button class="danger" data-action="reassign" data-id="${esc(row.request_id)}">Force Reassign</button></td></tr>`; }).join("") : `<tr><td colspan="6" class="empty">Queue is clear.</td></tr>`;
    document.querySelectorAll("[data-action]").forEach(button => button.addEventListener("click", () => override(button.dataset.id, button.dataset.action)));
  } catch { document.querySelector("#queue-body").innerHTML = `<tr><td colspan="6" class="empty">Queue unavailable.</td></tr>`; }
}

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

async function refreshLedger() {
  try { const data = await api("/v1/decisions/recent?limit=50"); document.querySelector("#ledger-count").textContent = `${data.items.length} entries`; document.querySelector("#ledger").innerHTML = data.items.map(item => `<article class="ledger-entry ${esc(item.outcome)}"><div class="ledger-time">${esc(new Date(item.created_at).toLocaleString())}</div><span class="outcome ${esc(item.outcome)}">${esc(item.outcome)}</span><div class="ledger-reason">${esc(item.reason)} <span class="mono">· ${esc(shortId(item.request_id))}</span></div>${item.agent_reasoning ? `<details class="reasoning"><summary>agent reasoning</summary><p>${esc(item.agent_reasoning)}</p></details>` : ""}</article>`).join("") || `<div class="empty">No decisions recorded yet.</div>`; } catch { document.querySelector("#ledger").innerHTML = `<div class="empty">Ledger unavailable.</div>`; }
}

async function refresh() { await refreshHealth(); await refreshApprovers(); await refreshLedger(); }
refresh(); setInterval(refresh, 2000); setInterval(tickCountdowns, 1000);
