// Rules Management Script
let cachedRules = [];

async function loadRules() {
    try {
        const rules = await apiFetch("/api/rules");
        cachedRules = rules;
        renderRulesTable(rules);
    } catch (err) {
        showToast(err.message, "error");
    }
}

function renderRulesTable(rules) {
    const tbody = document.getElementById("rules-table-body");
    if (!rules || rules.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 50px;">
                    No automation rules created yet. Click "+ Create Rule" to set up your first keyword trigger!
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = "";
    rules.forEach(r => {
        const tr = document.createElement("tr");

        const keywordsHtml = r.keywords.map(k => `<span class="keyword-tag">${k}</span>`).join(" ");

        let typeBadge = "badge-info";
        if (r.rule_type === "dm") typeBadge = "badge-info";
        else if (r.rule_type === "comment") typeBadge = "badge-warning";
        else if (r.rule_type === "story") typeBadge = "badge-danger";

        tr.innerHTML = `
            <td>
                <label class="switch">
                    <input type="checkbox" ${r.is_active ? 'checked' : ''} onchange="toggleRuleActive(${r.id})">
                    <span class="slider"></span>
                </label>
            </td>
            <td>
                <strong style="color: #fff; font-size: 0.95rem;">${r.name}</strong>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;">
                    Cooldown: ${r.cooldown_minutes}m
                </div>
            </td>
            <td>${keywordsHtml}</td>
            <td><span class="badge ${typeBadge}">${r.rule_type}</span></td>
            <td>
                <span class="badge ${r.follow_gate_enabled ? 'badge-warning' : 'badge-info'}">
                    ${r.follow_gate_enabled ? '🚪 Required' : 'Open'}
                </span>
            </td>
            <td><strong style="color: var(--accent-cyan);">${r.trigger_count}</strong></td>
            <td>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-secondary btn-sm" onclick="editRule(${r.id})">Edit</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteRule(${r.id})">Delete</button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// Modal controls
const modal = document.getElementById("rule-modal");
const ruleForm = document.getElementById("rule-form");
const followGateCheckbox = document.getElementById("rule-follow-gate");
const followGateOptions = document.getElementById("follow-gate-options");

followGateCheckbox.addEventListener("change", () => {
    followGateOptions.style.display = followGateCheckbox.checked ? "block" : "none";
});

function openAddModal() {
    document.getElementById("modal-title").textContent = "Create Automation Rule";
    document.getElementById("rule-id").value = "";
    ruleForm.reset();
    followGateCheckbox.checked = false;
    followGateOptions.style.display = "none";
    document.getElementById("rule-cooldown").value = "1440";
    modal.classList.add("active");
}

function editRule(id) {
    const rule = cachedRules.find(r => r.id === id);
    if (!rule) return;

    document.getElementById("modal-title").textContent = "Edit Automation Rule";
    document.getElementById("rule-id").value = rule.id;
    document.getElementById("rule-name").value = rule.name;
    document.getElementById("rule-keywords").value = rule.keywords.join(", ");
    document.getElementById("rule-type").value = rule.rule_type;
    document.getElementById("rule-match-type").value = rule.match_type;
    document.getElementById("rule-response").value = rule.response_text;
    followGateCheckbox.checked = rule.follow_gate_enabled;
    followGateOptions.style.display = rule.follow_gate_enabled ? "block" : "none";
    document.getElementById("rule-gate-message").value = rule.follow_gate_message || "";
    document.getElementById("rule-cooldown").value = rule.cooldown_minutes;

    modal.classList.add("active");
}

function closeModal() {
    modal.classList.remove("active");
}

document.getElementById("btn-add-rule").addEventListener("click", openAddModal);
document.getElementById("btn-close-modal").addEventListener("click", closeModal);
document.getElementById("btn-cancel-modal").addEventListener("click", closeModal);

// Form submit
ruleForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("rule-id").value;
    const name = document.getElementById("rule-name").value;
    const rawKeywords = document.getElementById("rule-keywords").value;
    const ruleType = document.getElementById("rule-type").value;
    const matchType = document.getElementById("rule-match-type").value;
    const responseText = document.getElementById("rule-response").value;
    const followGateEnabled = followGateCheckbox.checked;
    const gateMessage = document.getElementById("rule-gate-message").value;
    const cooldown = parseInt(document.getElementById("rule-cooldown").value, 10) || 0;

    const keywords = rawKeywords.split(",").map(k => k.trim().toLowerCase()).filter(k => k.length > 0);

    const payload = {
        name,
        keywords,
        rule_type: ruleType,
        match_type: matchType,
        response_text: responseText,
        follow_gate_enabled: followGateEnabled,
        follow_gate_message: gateMessage,
        cooldown_minutes: cooldown,
        is_active: true
    };

    try {
        if (id) {
            await apiFetch(`/api/rules/${id}`, {
                method: "PUT",
                body: JSON.stringify(payload)
            });
            showToast("Rule updated successfully!", "success");
        } else {
            await apiFetch("/api/rules", {
                method: "POST",
                body: JSON.stringify(payload)
            });
            showToast("Rule created successfully!", "success");
        }
        closeModal();
        loadRules();
    } catch (err) {
        showToast(err.message, "error");
    }
});

// Delete rule
async function deleteRule(id) {
    if (!confirm("Are you sure you want to delete this automation rule?")) return;
    try {
        await apiFetch(`/api/rules/${id}`, { method: "DELETE" });
        showToast("Rule deleted", "info");
        loadRules();
    } catch (err) {
        showToast(err.message, "error");
    }
}

// Toggle rule active
async function toggleRuleActive(id) {
    try {
        const res = await apiFetch(`/api/rules/${id}/toggle`, { method: "POST" });
        showToast(`Rule ${res.is_active ? 'activated' : 'disabled'}`, "info");
        const r = cachedRules.find(x => x.id === id);
        if (r) r.is_active = res.is_active;
    } catch (err) {
        showToast(err.message, "error");
        loadRules();
    }
}

// Simulator Logic
const simModal = document.getElementById("simulator-modal");
document.getElementById("btn-open-simulator").addEventListener("click", () => {
    simModal.classList.add("active");
});
document.getElementById("btn-close-sim").addEventListener("click", () => {
    simModal.classList.remove("active");
});

document.getElementById("btn-run-sim").addEventListener("click", () => {
    const text = document.getElementById("sim-input").value.trim().toLowerCase();
    const channel = document.getElementById("sim-channel").value;
    const resultsBox = document.getElementById("sim-results");

    if (!text) {
        showToast("Please enter an input message to simulate", "error");
        return;
    }

    let matched = null;
    for (const r of cachedRules) {
        if (!r.is_active) continue;
        if (r.rule_type !== "all" && r.rule_type !== channel) continue;

        for (const kw of r.keywords) {
            if (r.match_type === "exact" && text === kw) { matched = r; break; }
            if (r.match_type === "contains" && text.includes(kw)) { matched = r; break; }
            if (r.match_type === "regex") {
                try {
                    if (new RegExp(kw, "i").test(text)) { matched = r; break; }
                } catch(e){}
            }
        }
        if (matched) break;
    }

    resultsBox.style.display = "block";
    if (matched) {
        resultsBox.innerHTML = `
            <div style="color: var(--accent-emerald); font-weight: 700; margin-bottom: 8px;">
                ✅ MATCH FOUND: "${matched.name}"
            </div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 6px;">
                <strong>Keywords:</strong> ${matched.keywords.join(", ")}
            </div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 6px;">
                <strong>Follow Gate:</strong> ${matched.follow_gate_enabled ? 'Active (Checks follow status first)' : 'Disabled'}
            </div>
            <div style="font-size: 0.85rem; background: rgba(0,0,0,0.4); padding: 10px; border-radius: 6px; color: #fff; margin-top: 8px;">
                <strong>DM Delivered:</strong> "${matched.response_text}"
            </div>
        `;
    } else {
        resultsBox.innerHTML = `
            <div style="color: #f87171; font-weight: 700;">
                ❌ NO MATCH
            </div>
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 4px;">
                None of your active rules for channel '${channel}' matched this message text.
            </div>
        `;
    }
});

document.addEventListener("DOMContentLoaded", () => {
    loadRules();
    // Check if opened with ?action=new
    const params = new URLSearchParams(window.location.search);
    if (params.get("action") === "new") {
        openAddModal();
    }
});
