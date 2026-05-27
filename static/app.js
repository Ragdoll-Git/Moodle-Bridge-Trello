/**
 * MoodleAPI-Bridge — Monitoring UI Logic
 *
 * Handles API communication, status updates, and UI rendering.
 * Auto-refreshes status every 30 seconds.
 */

// ============================================================
// State
// ============================================================

const state = {
    authenticated: false,
    courses: [],
    refreshInterval: null,
};

// ============================================================
// API calls
// ============================================================

async function apiCall(method, path, body = null) {
    const opts = {
        method,
        headers: { "Content-Type": "application/json" },
    };
    if (body) opts.body = JSON.stringify(body);

    try {
        const res = await fetch(path, opts);
        const data = await res.json();
        return data;
    } catch (err) {
        logEvent("error", `Error de red: ${err.message}`);
        return null;
    }
}

// ============================================================
// Status
// ============================================================

async function refreshStatus() {
    const data = await apiCall("GET", "/api/health");
    if (!data) {
        setConnectionStatus("error", "Sin conexión");
        return;
    }

    setConnectionStatus("connected", "Conectado");

    // Moodle card
    const moodleCard = document.getElementById("card-moodle");
    const moodleStatus = document.getElementById("moodle-status");
    const moodleDetail = document.getElementById("moodle-detail");

    if (data.moodle_connected) {
        moodleCard.className = "card card--service card--connected";
        moodleStatus.textContent = "Conectado";
        moodleDetail.textContent = "Autenticado ✓";
        state.authenticated = true;
        document.getElementById("btn-courses").disabled = false;
        document.getElementById("btn-auth").textContent = "Re-autenticar";
    } else if (data.moodle_configured) {
        moodleCard.className = "card card--service card--error";
        moodleStatus.textContent = "Configurado";
        moodleDetail.textContent = "No autenticado";
    } else {
        moodleCard.className = "card card--service card--pending";
        moodleStatus.textContent = "Sin configurar";
        moodleDetail.textContent = "Falta .env";
    }

    // Google card
    const googleStatus = document.getElementById("google-status");
    if (data.google_configured) {
        googleStatus.textContent = "Configurado";
    }

    // Trello card
    const trelloCard = document.getElementById("card-trello");
    const trelloStatus = document.getElementById("trello-status");
    const trelloDetail = document.getElementById("trello-detail");

    if (data.trello_connected) {
        trelloCard.className = "card card--service card--connected";
        trelloStatus.textContent = "Conectado";
        trelloDetail.textContent = "Listo para sincronizar ✓";
    } else if (data.trello_configured) {
        trelloCard.className = "card card--service card--error";
        trelloStatus.textContent = "Configurado";
        trelloDetail.textContent = "Error de conexión";
    } else {
        trelloCard.className = "card card--service card--pending";
        trelloStatus.textContent = "Sin configurar";
        trelloDetail.textContent = "Falta .env";
    }

    // Toggle Trello sync button based on connection of both Moodle and Trello
    const btnSyncTrello = document.getElementById("btn-sync-trello");
    if (data.moodle_connected && data.trello_connected) {
        btnSyncTrello.disabled = false;
    } else {
        btnSyncTrello.disabled = true;
    }

    // Uptime
    const uptimeValue = document.getElementById("uptime-value");
    if (data.uptime_seconds != null) {
        uptimeValue.textContent = formatUptime(data.uptime_seconds);
    }
}

function setConnectionStatus(status, text) {
    const dot = document.querySelector("#connection-status .status-dot");
    const label = document.getElementById("status-text");

    dot.className = `status-dot status-dot--${status}`;
    label.textContent = text;
}

// ============================================================
// Authentication
// ============================================================

async function doAuth() {
    const btn = document.getElementById("btn-auth");
    btn.classList.add("btn--loading");
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Autenticando...`;

    logEvent("info", "Enviando credenciales a Moodle...");

    const data = await apiCall("POST", "/api/moodle/auth");

    btn.classList.remove("btn--loading");

    if (data && data.success) {
        logEvent("success", `Autenticado como ${data.site_info?.fullname || "usuario"} (ID: ${data.site_info?.userid})`);
        logEvent("info", `Sitio: ${data.site_info?.sitename || "N/A"}`);
        state.authenticated = true;
        document.getElementById("btn-courses").disabled = false;

        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> Re-autenticar`;
    } else {
        logEvent("error", `Autenticación fallida: ${data?.error || "Error desconocido"}`);

        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> Reintentar`;
    }

    await refreshStatus();
}

// ============================================================
// Courses
// ============================================================

async function loadCourses() {
    const btn = document.getElementById("btn-courses");
    btn.classList.add("btn--loading");

    logEvent("info", "Consultando cursos matriculados...");

    const data = await apiCall("GET", "/api/moodle/courses");

    btn.classList.remove("btn--loading");

    if (data && data.success) {
        state.courses = data.courses;
        renderCourses(data.courses);
        logEvent("success", `Se encontraron ${data.total_courses} cursos`);
    } else {
        logEvent("error", `Error al obtener cursos: ${data?.error || "Error desconocido"}`);
    }
}

function renderCourses(courses) {
    const section = document.getElementById("courses-section");
    const tbody = document.getElementById("courses-tbody");
    const count = document.getElementById("courses-count");

    section.style.display = "block";
    count.textContent = courses.length;

    tbody.innerHTML = courses
        .map(
            (c) => `
        <tr>
            <td>${c.id}</td>
            <td>${escapeHtml(c.fullname || c.displayname || c.shortname)}</td>
            <td>${escapeHtml(c.shortname)}</td>
            <td>${c.visible ? "✓" : "✗"}</td>
        </tr>
    `
        )
        .join("");

    // Smooth reveal
    section.style.animation = "fadeIn 0.3s ease";
}

// ============================================================
// Trello Sync
// ============================================================

async function syncTrello() {
    const btn = document.getElementById("btn-sync-trello");
    btn.classList.add("btn--loading");
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Sincronizando...`;

    logEvent("info", "Iniciando sincronización Moodle → Trello...");

    const data = await apiCall("POST", "/api/trello/sync");

    btn.classList.remove("btn--loading");
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 2.1l4 4-4 4"/><path d="M3 12.2v-2a4 4 0 0 1 4-4h14"/><path d="M7 21.9l-4-4 4-4"/><path d="M21 11.8v2a4 4 0 0 1-4 4H3"/></svg> Sincronizar Trello`;

    if (data && data.success) {
        const created = data.created || 0;
        const updated = data.updated || 0;
        const skipped = data.skipped || 0;
        logEvent("success", `Sincronización completada con éxito.`);
        logEvent("info", `Detalle Trello: ${created} creadas, ${updated} actualizadas, ${skipped} omitidas (archivadas)`);
        if (data.board_name) {
            logEvent("info", `Board: ${data.board_name}`);
        }
    } else {
        logEvent("error", `Sincronización fallida: ${data?.error || data?.message || "Error desconocido"}`);
    }

    await refreshStatus();
}

// ============================================================
// Event Log
// ============================================================

function logEvent(level, message) {
    const log = document.getElementById("event-log");
    const now = new Date();
    const time = now.toLocaleTimeString("es-AR", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });

    const entry = document.createElement("div");
    entry.className = `log__entry log__entry--${level}`;
    entry.innerHTML = `
        <span class="log__time">${time}</span>
        <span class="log__msg">${escapeHtml(message)}</span>
    `;

    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;

    // Keep only last 100 entries
    while (log.children.length > 100) {
        log.removeChild(log.firstChild);
    }
}

// ============================================================
// Helpers
// ============================================================

function formatUptime(seconds) {
    if (seconds < 60) return `${Math.floor(seconds)}s`;
    if (seconds < 3600) {
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}m ${s}s`;
    }
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
}

function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================
// Init
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
    // Initial status check
    refreshStatus();

    // Auto-refresh every 30s
    state.refreshInterval = setInterval(refreshStatus, 30000);

    logEvent("info", "Monitor inicializado");
});

// CSS animation for fade-in
const styleSheet = document.createElement("style");
styleSheet.textContent = `
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
`;
document.head.appendChild(styleSheet);
