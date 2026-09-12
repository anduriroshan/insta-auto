// Dashboard Logic
let eventSource = null;

async function loadStats() {
    try {
        const stats = await apiFetch("/api/stats");
        document.getElementById("stat-active-rules").textContent = stats.active_rules;
        document.getElementById("stat-total-rules").textContent = `Total rules: ${stats.total_rules}`;
        document.getElementById("stat-dms-today").textContent = stats.dms_today;
        document.getElementById("stat-follow-gates").textContent = stats.follow_gates_triggered;
        document.getElementById("stat-total-triggers").textContent = stats.total_triggers;
        document.getElementById("stat-pending-queued").textContent = `${stats.pending_queued} pending delivery`;
    } catch (err) {
        console.error("Error loading stats:", err);
    }
}

async function loadWebhookSettings() {
    try {
        const s = await apiFetch("/api/settings");
        const fullWebhook = s.webhook_base_url 
            ? `${s.webhook_base_url.replace(/\/+$/, "")}/webhook`
            : `${window.location.origin}/webhook`;

        document.getElementById("webhook-url-display").textContent = fullWebhook;
        document.getElementById("webhook-token-display").textContent = s.meta_verify_token;
        document.getElementById("badge-api-version").textContent = `Meta API ${s.api_version}`;

        const copyBtn = document.getElementById("btn-copy-webhook");
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(fullWebhook);
            showToast("Webhook URL copied to clipboard!", "success");
        };
    } catch (err) {
        console.error("Error loading settings:", err);
    }
}

function renderActivityItem(log) {
    const item = document.createElement("div");
    item.style.padding = "12px 14px";
    item.style.borderRadius = "var(--radius-md)";
    item.style.background = "rgba(255, 255, 255, 0.03)";
    item.style.border = "1px solid var(--border-glass)";
    item.style.display = "flex";
    item.style.alignItems = "center";
    item.style.justifyContent = "space-between";
    item.style.animation = "fadeIn 0.3s ease-out";

    let icon = "💬";
    let badgeClass = "badge-info";
    if (log.event_type === "dm_sent") { icon = "📤"; badgeClass = "badge-success"; }
    else if (log.event_type === "private_reply_sent") { icon = "💬"; badgeClass = "badge-success"; }
    else if (log.event_type === "follow_gate_blocked") { icon = "🚪"; badgeClass = "badge-warning"; }
    else if (log.event_type === "story_mention") { icon = "📖"; badgeClass = "badge-info"; }
    else if (log.event_type === "queued_released") { icon = "🔓"; badgeClass = "badge-success"; }
    else if (log.status === "failed") { icon = "❌"; badgeClass = "badge-danger"; }

    const timeAgo = log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : "";

    item.innerHTML = `
        <div style="display: flex; align-items: center; gap: 12px; min-width: 0;">
            <div style="font-size: 1.25rem;">${icon}</div>
            <div style="overflow: hidden;">
                <div style="font-weight: 600; font-size: 0.88rem; color: #fff; text-overflow: ellipsis; white-space: nowrap; overflow: hidden;">
                    ${log.sender_username ? '@' + log.sender_username : (log.sender_id || 'Instagram User')}
                </div>
                <div style="font-size: 0.78rem; color: var(--text-secondary); text-overflow: ellipsis; white-space: nowrap; overflow: hidden;">
                    ${log.details || log.event_type}
                </div>
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 8px; flex-shrink: 0; margin-left: 12px;">
            <span class="badge ${badgeClass}">${log.status}</span>
            <span style="font-size: 0.75rem; color: var(--text-muted);">${timeAgo}</span>
        </div>
    `;

    return item;
}

async function loadRecentLogs() {
    try {
        const logs = await apiFetch("/api/logs?limit=6");
        const container = document.getElementById("live-activity-list");
        if (logs.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; color: var(--text-muted); padding: 40px;">
                    No events recorded yet. Send a test DM or comment to see events here live!
                </div>
            `;
            return;
        }

        container.innerHTML = "";
        logs.forEach(log => {
            container.appendChild(renderActivityItem(log));
        });
    } catch (err) {
        console.error("Error loading logs:", err);
    }
}

async function loadQuickRules() {
    try {
        const rules = await apiFetch("/api/rules");
        const container = document.getElementById("quick-rules-list");
        const activeRules = rules.filter(r => r.is_active);

        if (activeRules.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; color: var(--text-muted); padding: 30px;">
                    No active rules found. <a href="/static/rules.html?action=new" style="color: var(--accent-cyan);">Create one now</a>
                </div>
            `;
            return;
        }

        container.innerHTML = "";
        activeRules.slice(0, 5).forEach(rule => {
            const card = document.createElement("div");
            card.style.padding = "12px 14px";
            card.style.background = "rgba(255, 255, 255, 0.02)";
            card.style.border = "1px solid var(--border-glass)";
            card.style.borderRadius = "var(--radius-sm)";
            card.style.display = "flex";
            card.style.justifyContent = "space-between";
            card.style.alignItems = "center";

            const keywordsHtml = rule.keywords.map(k => `<span class="keyword-tag">${k}</span>`).join(" ");

            card.innerHTML = `
                <div>
                    <div style="font-weight: 600; font-size: 0.88rem; color: #fff; margin-bottom: 4px;">${rule.name}</div>
                    <div>${keywordsHtml}</div>
                </div>
                <div style="text-align: right;">
                    <span class="badge ${rule.follow_gate_enabled ? 'badge-warning' : 'badge-info'}" style="font-size: 0.7rem;">
                        ${rule.follow_gate_enabled ? 'Gate ON' : 'Direct'}
                    </span>
                    <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 4px;">
                        ${rule.trigger_count} triggers
                    </div>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        console.error("Error loading rules:", err);
    }
}

function initSSELiveStream() {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource("/api/logs/stream");

    eventSource.addEventListener("log", (e) => {
        try {
            const logData = JSON.parse(e.data);
            const container = document.getElementById("live-activity-list");

            // Remove placeholder if present
            if (container.children.length === 1 && container.children[0].innerText.includes("No events")) {
                container.innerHTML = "";
            }

            const item = renderActivityItem(logData);
            container.insertBefore(item, container.firstChild);

            // Keep max 8 items
            while (container.children.length > 8) {
                container.removeChild(container.lastChild);
            }

            // Refresh stats on new events
            loadStats();
        } catch (err) {
            console.error("Error parsing SSE log event:", err);
        }
    });

    eventSource.onerror = () => {
        // SSE auto-reconnects
    };
}

document.addEventListener("DOMContentLoaded", () => {
    loadStats();
    loadWebhookSettings();
    loadRecentLogs();
    loadQuickRules();
    initSSELiveStream();

    document.getElementById("btn-refresh-stats").addEventListener("click", () => {
        loadStats();
        loadRecentLogs();
        loadQuickRules();
        showToast("Stats refreshed", "info");
    });
});
