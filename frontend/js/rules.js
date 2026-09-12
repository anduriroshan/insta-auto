// Rules Management Script
let cachedRules = [];
let cachedMedia = null; // null = not fetched yet, [] = fetched but empty

function escapeHtml(str) {
    return String(str || "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
}

function mediaTypeLabel(mediaType) {
    if (mediaType === "VIDEO") return "REEL";
    if (mediaType === "CAROUSEL_ALBUM") return "ALBUM";
    if (mediaType === "IMAGE") return "IMAGE";
    return mediaType || "POST";
}

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
                <td colspan="9" class="empty-state">
                    No automation rules created yet. Click "+ Create Rule" to set up your first keyword trigger!
                </td>
            </tr>
        `;
        return;
    }

    const typeLabels = { all: "⚡ All", dm: "💬 DM", comment: "🗨️ Comment", story: "📖 Story" };

    tbody.innerHTML = "";
    rules.forEach(r => {
        const tr = document.createElement("tr");

        const keywordsHtml = r.keywords.map(k => `<span class="keyword-tag">${escapeHtml(k)}</span>`).join(" ");

        const scopeCell = r.target_media_id
            ? `<span class="badge badge-accent" style="max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; display:inline-block; vertical-align:middle;" title="${escapeHtml(r.target_media_permalink || '')}">Scoped: ${escapeHtml(r.target_media_permalink || 'reel')}</span>`
            : `<span class="badge badge-info">All posts</span>`;

        const publicReplyBadge = r.public_reply_enabled
            ? `<span class="badge badge-success">On</span>`
            : `<span class="badge badge-info">Off</span>`;

        const followGateBadge = r.follow_gate_enabled
            ? `<span class="badge badge-warning">Required</span>`
            : `<span class="badge badge-info">Open</span>`;

        tr.innerHTML = `
            <td>
                <label class="switch">
                    <input type="checkbox" ${r.is_active ? 'checked' : ''} onchange="toggleRuleActive(${r.id})">
                    <span class="slider"></span>
                </label>
            </td>
            <td>
                <strong style="color: var(--text-primary); font-size: 0.95rem;">${escapeHtml(r.name)}</strong>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;">
                    Cooldown: ${r.cooldown_minutes}m
                </div>
            </td>
            <td>${keywordsHtml}</td>
            <td style="white-space:nowrap;">${typeLabels[r.rule_type] || r.rule_type}</td>
            <td>${scopeCell}</td>
            <td>${publicReplyBadge}</td>
            <td>${followGateBadge}</td>
            <td style="text-align:right"><strong style="color: var(--text-primary);">${r.trigger_count}</strong></td>
            <td>
                <div style="display: flex; gap: 8px; justify-content: flex-end;">
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
const publicReplyCheckbox = document.getElementById("rule-public-reply");
const publicReplyOptions = document.getElementById("public-reply-options");
const targetMediaIdInput = document.getElementById("rule-target-media-id");
const targetMediaPermalinkInput = document.getElementById("rule-target-media-permalink");
const mediaScopeToolbar = document.getElementById("media-scope-toolbar");
const mediaPickerGrid = document.getElementById("media-picker-grid");
const mediaScopeHint = document.getElementById("media-scope-hint");

followGateCheckbox.addEventListener("change", () => {
    followGateOptions.style.display = followGateCheckbox.checked ? "block" : "none";
});

publicReplyCheckbox.addEventListener("change", () => {
    publicReplyOptions.style.display = publicReplyCheckbox.checked ? "block" : "none";
});

// ---------- Media scope picker ----------
async function ensureMediaLoaded() {
    if (cachedMedia !== null) return;
    mediaPickerGrid.innerHTML = `<div class="media-picker-empty">Loading recent media…</div>`;
    try {
        const media = await apiFetch("/api/instagram/media");
        cachedMedia = media || [];
    } catch (err) {
        cachedMedia = [];
        mediaPickerGrid.innerHTML = `<div class="media-picker-empty">Couldn't load media: ${escapeHtml(err.message)}. Check your Instagram connection in Settings.</div>`;
        return;
    }
    renderMediaGrid();
}

function renderMediaGrid() {
    if (!cachedMedia || cachedMedia.length === 0) {
        mediaPickerGrid.innerHTML = `<div class="media-picker-empty">No recent posts found. Make sure your Instagram account is connected in Settings.</div>`;
        return;
    }
    const selectedId = targetMediaIdInput.value;
    mediaPickerGrid.innerHTML = cachedMedia.map(m => {
        const isSelected = selectedId && String(m.id) === String(selectedId);
        const caption = (m.caption || "Untitled post").slice(0, 60);
        return `
            <div class="media-tile ${isSelected ? 'selected' : ''}"
                 style="background-image:url('${escapeHtml(m.thumbnail_url || '')}')"
                 onclick="selectMediaTile('${m.id}')">
                <span class="media-type-tag">${mediaTypeLabel(m.media_type)}</span>
                ${isSelected ? '<div class="media-check">✓</div>' : ''}
                <div class="media-caption">${escapeHtml(caption)}</div>
            </div>
        `;
    }).join("");
}

function selectMediaTile(id) {
    const media = (cachedMedia || []).find(m => String(m.id) === String(id));
    if (!media) return;
    targetMediaIdInput.value = media.id;
    targetMediaPermalinkInput.value = media.caption ? media.caption.slice(0, 80) : (media.permalink || `Post ${media.id}`);
    renderMediaGrid();
    updateScopeHint();
}

function updateScopeHint() {
    if (targetMediaIdInput.value) {
        mediaScopeHint.style.display = "block";
        mediaScopeHint.innerHTML = `Scoped to <strong>${escapeHtml(targetMediaPermalinkInput.value)}</strong> · media id <strong>${escapeHtml(targetMediaIdInput.value)}</strong>`;
    } else {
        mediaScopeHint.style.display = "none";
        mediaScopeHint.innerHTML = "";
    }
}

function setMediaScopeMode(mode) {
    mediaScopeToolbar.querySelectorAll("button").forEach(b => {
        b.classList.toggle("active", b.dataset.scope === mode);
    });
    if (mode === "all") {
        mediaPickerGrid.style.display = "none";
        mediaScopeHint.style.display = "none";
        targetMediaIdInput.value = "";
        targetMediaPermalinkInput.value = "";
    } else {
        mediaPickerGrid.style.display = "grid";
        ensureMediaLoaded().then(() => renderMediaGrid());
        updateScopeHint();
    }
}

mediaScopeToolbar.querySelectorAll("button").forEach(btn => {
    btn.addEventListener("click", () => setMediaScopeMode(btn.dataset.scope));
});

function openAddModal() {
    document.getElementById("modal-title").textContent = "Create Automation Rule";
    document.getElementById("rule-id").value = "";
    ruleForm.reset();
    followGateCheckbox.checked = false;
    followGateOptions.style.display = "none";
    publicReplyCheckbox.checked = false;
    publicReplyOptions.style.display = "none";
    document.getElementById("rule-cooldown").value = "1440";
    setMediaScopeMode("all");
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

    publicReplyCheckbox.checked = !!rule.public_reply_enabled;
    publicReplyOptions.style.display = rule.public_reply_enabled ? "block" : "none";
    document.getElementById("rule-public-reply-text").value = rule.public_reply_text || "";

    document.getElementById("rule-cooldown").value = rule.cooldown_minutes;

    targetMediaIdInput.value = rule.target_media_id || "";
    targetMediaPermalinkInput.value = rule.target_media_permalink || "";
    setMediaScopeMode(rule.target_media_id ? "specific" : "all");

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
    const publicReplyEnabled = publicReplyCheckbox.checked;
    const publicReplyText = document.getElementById("rule-public-reply-text").value;
    const cooldown = parseInt(document.getElementById("rule-cooldown").value, 10) || 0;
    const targetMediaId = targetMediaIdInput.value || null;
    const targetMediaPermalink = targetMediaPermalinkInput.value || null;

    const keywords = rawKeywords.split(",").map(k => k.trim().toLowerCase()).filter(k => k.length > 0);

    const payload = {
        name,
        keywords,
        rule_type: ruleType,
        match_type: matchType,
        response_text: responseText,
        target_media_id: targetMediaId,
        target_media_permalink: targetMediaPermalink,
        public_reply_enabled: publicReplyEnabled,
        public_reply_text: publicReplyText,
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
            <div style="color: var(--success); font-weight: 700; margin-bottom: 8px;">
                ✅ MATCH FOUND: "${escapeHtml(matched.name)}"
            </div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 6px;">
                <strong>Keywords:</strong> ${matched.keywords.map(escapeHtml).join(", ")}
            </div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 6px;">
                <strong>Scope:</strong> ${matched.target_media_id ? escapeHtml(matched.target_media_permalink || 'Specific post') : 'All posts'}
            </div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 6px;">
                <strong>Follow Gate:</strong> ${matched.follow_gate_enabled ? 'Active (checks follow status first)' : 'Disabled'}
            </div>
            <div style="font-size: 0.85rem; background: var(--bg); border: 1px solid var(--border); padding: 10px; border-radius: var(--radius-sm); color: var(--text-primary); margin-top: 8px;">
                <strong>DM Delivered:</strong> "${escapeHtml(matched.response_text)}"
            </div>
        `;
    } else {
        resultsBox.innerHTML = `
            <div style="color: var(--error); font-weight: 700;">
                ❌ NO MATCH
            </div>
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 4px;">
                None of your active rules for channel '${escapeHtml(channel)}' matched this message text.
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
