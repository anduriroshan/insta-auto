// Core Frontend App Script
const API_BASE = "";

// Auth Helpers
function getToken() {
    return localStorage.getItem("insta_auto_token");
}

function setToken(token) {
    localStorage.setItem("insta_auto_token", token);
}

function removeToken() {
    localStorage.removeItem("insta_auto_token");
}

function checkAuthGuard() {
    const isLoginPage = window.location.pathname.endsWith("index.html") || window.location.pathname === "/" || window.location.pathname.endsWith("/");
    const token = getToken();

    if (!token && !isLoginPage) {
        window.location.href = "/static/index.html";
    } else if (token && isLoginPage) {
        window.location.href = "/static/dashboard.html";
    }
}

// Universal API Fetcher
async function apiFetch(endpoint, options = {}) {
    const token = getToken();
    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {})
    };

    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    try {
        const response = await fetch(endpoint, {
            ...options,
            headers
        });

        if (response.status === 401) {
            removeToken();
            if (!window.location.pathname.endsWith("index.html")) {
                window.location.href = "/static/index.html";
            }
            throw new Error("Session expired. Please log in again.");
        }

        const data = await response.json().catch(() => null);
        if (!response.ok) {
            throw new Error((data && data.detail) || (data && data.message) || `Request failed with status ${response.status}`);
        }

        return data;
    } catch (err) {
        throw err;
    }
}

// Toast Notifications
function showToast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.className = "toast-container";
        document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    
    let icon = "ℹ️";
    if (type === "success") icon = "✅";
    if (type === "error") icon = "❌";

    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        toast.style.transition = "all 0.3s ease";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Logout handler
function setupLogout() {
    const logoutBtn = document.getElementById("btn-logout");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", () => {
            removeToken();
            showToast("Logged out successfully", "info");
            setTimeout(() => {
                window.location.href = "/static/index.html";
            }, 500);
        });
    }
}

// Highlight active sidebar navigation
function highlightActiveNav() {
    const path = window.location.pathname;
    const links = document.querySelectorAll(".nav-link");
    links.forEach(link => {
        const href = link.getAttribute("href");
        if (href && path.includes(href.replace("/static/", ""))) {
            link.classList.add("active");
        } else {
            link.classList.remove("active");
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    checkAuthGuard();
    setupLogout();
    highlightActiveNav();
});
