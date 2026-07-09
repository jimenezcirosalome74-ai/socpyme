/* ==========================================================================
   SOC-PYME · dashboard.js
   - Sidebar colapsable (móvil)
   - Campanita de notificaciones + polling
   - KPIs, gráficos Chart.js y últimos eventos en tiempo real
   ========================================================================== */
(function () {
  "use strict";

  const CSRF = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const POLL_MS = 10000; // 10 segundos

  // --- Sidebar móvil ------------------------------------------------------
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("overlay");
  const toggle = document.getElementById("sidebar-toggle");
  if (toggle && sidebar) {
    const open = () => { sidebar.classList.add("open"); overlay.classList.add("open"); };
    const close = () => { sidebar.classList.remove("open"); overlay.classList.remove("open"); };
    toggle.addEventListener("click", () => sidebar.classList.contains("open") ? close() : open());
    overlay?.addEventListener("click", close);
  }

  // --- Campanita ----------------------------------------------------------
  const bellBtn = document.getElementById("bell-btn");
  const bellDropdown = document.getElementById("bell-dropdown");
  const bellCount = document.getElementById("bell-count");
  const bellList = document.getElementById("bell-list");
  const markAll = document.getElementById("mark-all-read");

  if (bellBtn && bellDropdown) {
    bellBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      bellDropdown.classList.toggle("open");
    });
    document.addEventListener("click", (e) => {
      if (!bellDropdown.contains(e.target) && e.target !== bellBtn) {
        bellDropdown.classList.remove("open");
      }
    });
  }

  if (markAll) {
    markAll.addEventListener("click", async () => {
      await fetch("/api/notifications/read-all", {
        method: "POST",
        headers: { "X-CSRFToken": CSRF },
      });
      refresh();
    });
  }

  function renderNotifications(data) {
    if (!bellCount) return;
    const unread = data.notifications.unread;
    bellCount.textContent = unread;
    bellCount.classList.toggle("hidden", unread === 0);

    if (bellList) {
      const items = data.notifications.items;
      if (!items.length) {
        bellList.innerHTML = '<div class="bell-empty">No hay notificaciones nuevas.</div>';
      } else {
        bellList.innerHTML = items
          .map((n) => {
            const t = new Date(n.created_at);
            const stamp = t.toLocaleString("es-CO", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
            const ic = n.kind === "alerta" ? "⚠️" : "ℹ️";
            return `<div class="bell-item"><span class="bi-ic">${ic}</span><div>${escapeHtml(n.message)}<time>${stamp}</time></div></div>`;
          })
          .join("");
      }
    }
  }

  // --- Dashboard en vivo (solo en la página del dashboard) ----------------
  const dash = document.getElementById("dashboard-root");
  let bar7Chart = null;
  let donutChart = null;

  function initCharts() {
    if (typeof Chart === "undefined") return;

    const barCtx = document.getElementById("chart7d");
    if (barCtx) {
      bar7Chart = new Chart(barCtx, {
        type: "bar",
        data: {
          labels: [],
          datasets: [{
            label: "Eventos",
            data: [],
            backgroundColor: "#2EC4B6",
            borderRadius: 6,
            maxBarThickness: 46,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, ticks: { precision: 0, color: "#94A3B8" }, grid: { color: "#EDF2F7" } },
            x: { ticks: { color: "#94A3B8" }, grid: { display: false } },
          },
        },
      });
    }

    const donutCtx = document.getElementById("chartSeverity");
    if (donutCtx) {
      donutChart = new Chart(donutCtx, {
        type: "doughnut",
        data: {
          labels: ["Crítico", "Aviso", "Info"],
          datasets: [{
            data: [0, 0, 0],
            backgroundColor: ["#EF4444", "#F59E0B", "#10B981"],
            borderWidth: 0,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false, cutout: "62%",
          plugins: { legend: { position: "bottom", labels: { color: "#475569", padding: 16, usePointStyle: true } } },
        },
      });
    }
  }

  function updateDashboard(data) {
    // KPIs
    setText("kpi-events", data.kpis.events_today);
    setText("kpi-critical", data.kpis.critical_today);
    setText("kpi-resolved", data.kpis.resolved_today);
    setText("kpi-rate", data.kpis.resolution_rate + "%");
    setText("kpi-open-incidents", data.kpis.open_incidents);

    // Gráfico 7 días
    if (bar7Chart) {
      bar7Chart.data.labels = data.chart_7d.labels;
      bar7Chart.data.datasets[0].data = data.chart_7d.data;
      bar7Chart.update();
    }
    // Dona por severidad
    if (donutChart) {
      donutChart.data.datasets[0].data = [
        data.by_severity.critico, data.by_severity.aviso, data.by_severity.info,
      ];
      donutChart.update();
    }

    // Últimos eventos
    const tbody = document.getElementById("recent-events-body");
    if (tbody && data.recent_events) {
      tbody.innerHTML = data.recent_events
        .map((e) => {
          const t = new Date(e.timestamp);
          const stamp = t.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
          return `<tr class="clickable" onclick="location.href='/eventos/${e.id}'">
            <td><span class="badge sev-${e.severity}">${e.severity_label}</span></td>
            <td>${escapeHtml(e.type)}</td>
            <td class="mono hide-sm">${escapeHtml(e.source_ip || "—")}</td>
            <td class="mono">${stamp}</td>
          </tr>`;
        })
        .join("");
    }
  }

  // --- Polling compartido -------------------------------------------------
  async function refresh() {
    try {
      const res = await fetch("/api/dashboard", { headers: { "Accept": "application/json" } });
      if (!res.ok) return;
      const data = await res.json();
      renderNotifications(data);
      if (dash) updateDashboard(data);
    } catch (err) {
      /* silencioso: reintenta en el próximo ciclo */
    }
  }

  // --- Helpers ------------------------------------------------------------
  function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  // --- Init ---------------------------------------------------------------
  if (dash) initCharts();
  refresh();                 // primera carga inmediata
  setInterval(refresh, POLL_MS);
})();
