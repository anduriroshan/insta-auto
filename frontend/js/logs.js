// Logs Controller
let currentFilter = "";
let eventSource = null;

async function fetchLogs() {
    const url = currentFilter 
        ? `/api/logs?event_type=${currentFilter}&limit=100` 
        : `/api/logs?limit=100`;

    try {
        const logs = await apiFetch(url);
        renderLogsTable(logs);
    } catch (err) {
        showToast(err.message, "error");
    }
}

function renderLogRow(log) {
    const tr = document.createElement("tr");

    let typeBadge = "badge-info";
    let icon = "💬";
    if (log.event_type === "dm_sent") { typeBadge = "badge-success"; icon = "📤"; }
    else if (log.event_type === "private_reply_sent") { typeBadge = "badge-success"; icon = "💬"; }
    else if (log.event_type === "follow_gate_blocked") { typeBadge = "badge-warning"; icon = "🚪"; }
    else if (log.event_type === "story_mention") { typeBadge = "badge-info"; icon = "📖"; }
    else if (log.event_type === "queued_released") { typeBadge = "badge-success"; icon = "🔓"; }
    else if (log.event_type === "error") { typeBadge = "badge-danger"; icon = "❌"; }

    let statusBadge = "badge-success";
    if (log.status === "blocked") statusBadge = "badge-warning";
    if (log.status === "failed") statusBadge = "badge-danger";
    if (log.status === "info") statusBadge = "badge-info";

    const timeStr = log.timestamp ? new Date(log.timestamp).toLocaleString() : "N/A";
    const userDisplay = log.sender_username ? `@${log.sender_username}` : log.sender_id;

    tr.innerHTML = `
        <td style="font-size: 0.82rem; color: var(--text-muted); white-space: nowrap;">${timeStr}</td>
        <td>
            <span class="badge ${typeBadge}">${icon} ${log.event_type}</span>
        </td>
        <td>
            <strong style="color: #fff;">${userDisplay}</strong>
        </td>
        <td>
            <span style="color: var(--accent-cyan); font-size: 0.85rem;">${log.rule_name || '-'}</span>
        </td>
        <td>
            <span class="badge ${statusBadge}">${log.status}</span>
        </td>
        <td style="font-size: 0.85rem; color: var(--text-secondary); max-width: 350px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
            ${log.details || '-'}
        </td>
    `;
    return tr;
}

function renderLogsTable(logs) {
    const tbody = document.getElementById("logs-table-body");
    if (!logs || logs.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 50px;">
                    No activity logs found for this filter.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = "";
    logs.forEach(log => {
        tbody.appendChild(renderLogRow(log));
    });
}

function initSSELogsStream() {
    if (eventSource) eventSource.close();

    eventSource = new EventSource("/api/logs/stream");

    eventSource.addEventListener("connected", () => {
        document.getElementById("sse-status-label").textContent = "Stream Connected";
    });

    eventSource.addEventListener("log", (e) => {
        try {
            const log = JSON.parse(e.data);
            if (!currentFilter || log.event_type === currentFilter) {
                const tbody = document.getElementById("logs-table-body");
                if (tbody.children.length === 1 && tbody.children[0].innerText.includes("No activity")) {
                    tbody.innerHTML = "";
                }
                const tr = renderLogRow(log);
                tr.style.animation = "fadeIn 0.3s ease-out";
                tbody.insertBefore(tr, tbody.firstChild);
            }
        } catch (err) {
            console.error(err);
        }
    });

    eventSource.onerror = () => {
        document.getElementById("sse-status-label").textContent = "Reconnecting...";
    };
}

// Clear logs
document.getElementById("btn-clear-logs").addEventListener("click", async () => {
    if (!confirm("Are you sure you want to clear all activity logs?")) return;
    try {
        await apiFetch("/api/logs", { method: "DELETE" });
        showToast("All logs cleared", "info");
        fetchLogs();
    } catch (err) {
        showToast(err.message, "error");
    }
});

// Refresh button
document.getElementById("btn-refresh-logs").addEventListener("click", () => {
    fetchLogs();
    showToast("Logs refreshed", "info");
});

// Filter pills
document.querySelectorAll(".filter-pill").forEach(pill => {
    pill.addEventListener("click", () => {
        document.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        currentFilter = pill.getAttribute("data-filter");
        fetchLogs();
    });
});

document.addEventListener("DOMContentLoaded", () => {
    fetchLogs();
    initSSELogsStream();
});
