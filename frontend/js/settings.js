// Settings Controller
async function loadSettings() {
    try {
        const s = await apiFetch("/api/settings");
        document.getElementById("meta-app-id").value = s.meta_app_id || "";
        document.getElementById("webhook-verify-token").value = s.meta_verify_token || "";
        document.getElementById("instagram-account-id").value = s.instagram_account_id || "";
        document.getElementById("webhook-base-url").value = s.webhook_base_url || "";
        document.getElementById("token-status-help").textContent = `Current Token: ${s.page_access_token_masked}`;
    } catch (err) {
        showToast(err.message, "error");
    }
}

// Save settings form
document.getElementById("settings-form").addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
        meta_app_id: document.getElementById("meta-app-id").value.trim(),
        meta_app_secret: document.getElementById("meta-app-secret").value.trim() || undefined,
        page_access_token: document.getElementById("page-access-token").value.trim() || undefined,
        instagram_account_id: document.getElementById("instagram-account-id").value.trim(),
        meta_verify_token: document.getElementById("webhook-verify-token").value.trim(),
        webhook_base_url: document.getElementById("webhook-base-url").value.trim(),
        dashboard_password: document.getElementById("dashboard-pwd").value.trim() || undefined
    };

    try {
        await apiFetch("/api/settings", {
            method: "POST",
            body: JSON.stringify(payload)
        });
        showToast("Settings saved to .env successfully!", "success");
        loadSettings();
    } catch (err) {
        showToast(err.message, "error");
    }
});

// Test connection button
document.getElementById("btn-test-conn").addEventListener("click", async () => {
    const btn = document.getElementById("btn-test-conn");
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> <span>Testing...</span>`;

    try {
        const res = await apiFetch("/api/settings/test-connection", { method: "POST" });
        if (res.status === "connected") {
            showToast(`Connected to Page "${res.page_name}"!`, "success");
        } else if (res.status === "unconfigured") {
            showToast("PAGE_ACCESS_TOKEN is not configured yet.", "error");
        } else {
            showToast(`Meta Error: ${res.message}`, "error");
        }
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<span>🔌</span> <span>Test Meta Connection</span>`;
    }
});

// Save Ice Breakers
document.getElementById("btn-save-icebreakers").addEventListener("click", async () => {
    const qInputs = document.querySelectorAll(".ice-q");
    const pInputs = document.querySelectorAll(".ice-p");

    const ice_breakers = [];
    for (let i = 0; i < qInputs.length; i++) {
        const question = qInputs[i].value.trim();
        const payload = pInputs[i].value.trim();
        if (question && payload) {
            ice_breakers.push({ question, payload });
        }
    }

    if (ice_breakers.length === 0) {
        showToast("Please enter at least one Ice Breaker question & payload", "error");
        return;
    }

    try {
        const res = await apiFetch("/api/settings/ice-breakers", {
            method: "POST",
            body: JSON.stringify({ ice_breakers })
        });
        if (res.result === "success" || !res.error) {
            showToast("Ice Breakers published to Instagram inbox!", "success");
        } else {
            showToast(res.error ? res.error.message : "Failed to publish", "error");
        }
    } catch (err) {
        showToast(err.message, "error");
    }
});

// Setup accordion toggles
document.querySelectorAll(".accordion-header").forEach(header => {
    header.addEventListener("click", () => {
        const item = header.parentElement;
        item.classList.toggle("active");
        const arrow = header.querySelector("span:last-child");
        if (arrow) {
            arrow.textContent = item.classList.contains("active") ? "▲" : "▼";
        }
    });
});

document.addEventListener("DOMContentLoaded", () => {
    loadSettings();
});
