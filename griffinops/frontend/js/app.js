let authToken = localStorage.getItem("gop_token") || null;
let currentUser = JSON.parse(localStorage.getItem("gop_user") || "null");
let currentService = null;
let selectedAPIEndpoint = null;

let liveTelemetryChart = null;
let forecastChart = null;
let illustrationForecastChart = null;
let pollTimer = null;

let MICROSERVICES = [];

document.addEventListener("DOMContentLoaded", () => {
  if (authToken) {
    showMainApp();
  } else {
    document.getElementById("auth-screen").style.display = "flex";
    document.getElementById("main-app").style.display = "none";
  }
});

function switchAuthTab(tab) {
  document.getElementById("btn-tab-login").classList.remove("active");
  document.getElementById("btn-tab-register").classList.remove("active");
  document.getElementById("auth-form-login").style.display = "none";
  document.getElementById("auth-form-register").style.display = "none";

  if (tab === "login") {
    document.getElementById("btn-tab-login").classList.add("active");
    document.getElementById("auth-form-login").style.display = "block";
  } else {
    document.getElementById("btn-tab-register").classList.add("active");
    document.getElementById("auth-form-register").style.display = "block";
  }
}

async function handleLogin() {
  const email = document.getElementById("login-email").value;
  const pass = document.getElementById("login-pass").value;
  const errDiv = document.getElementById("login-error");
  errDiv.innerText = "";

  try {
    const resp = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, password: pass })
    });
    const data = await resp.json();
    if (resp.ok) {
      authToken = data.access_token;
      currentUser = data.user;
      localStorage.setItem("gop_token", authToken);
      localStorage.setItem("gop_user", JSON.stringify(currentUser));
      showMainApp();
    } else {
      errDiv.innerText = data.detail || "Authentication failed.";
    }
  } catch (err) {
    errDiv.innerText = "Server connection error.";
  }
}

async function handleRegister() {
  const name = document.getElementById("reg-name").value;
  const email = document.getElementById("reg-email").value;
  const pass = document.getElementById("reg-pass").value;
  const errDiv = document.getElementById("reg-error");
  errDiv.innerText = "";

  if (!name || !email || !pass) {
    errDiv.innerText = "Please fill out all fields.";
    return;
  }

  try {
    const resp = await fetch("/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, email: email, password: pass })
    });
    const data = await resp.json();
    if (resp.ok) {
      showToast("Account created via Supabase Auth! Signing in...");
      document.getElementById("login-email").value = email;
      document.getElementById("login-pass").value = pass;
      handleLogin();
    } else {
      errDiv.innerText = data.detail || "Registration failed.";
    }
  } catch (err) {
    errDiv.innerText = "Server connection error.";
  }
}

function handleLogout() {
  authToken = null;
  currentUser = null;
  localStorage.removeItem("gop_token");
  localStorage.removeItem("gop_user");
  if (pollTimer) clearInterval(pollTimer);
  document.getElementById("auth-screen").style.display = "flex";
  document.getElementById("main-app").style.display = "none";
}

function showMainApp() {
  document.getElementById("auth-screen").style.display = "none";
  document.getElementById("main-app").style.display = "flex";
  
  if (currentUser) {
    const initials = currentUser.name ? currentUser.name.split(" ").map(n => n[0]).join("").toUpperCase() : "SL";
    document.getElementById("user-avatar-tag").innerText = initials;
    document.getElementById("profile-avatar-big").innerText = initials;
    document.getElementById("user-display-name").innerText = currentUser.name;
    document.getElementById("user-display-role").innerText = currentUser.role || "DEVELOPER";
    
    document.getElementById("profile-name").innerText = currentUser.name;
    document.getElementById("profile-email").innerText = currentUser.email;
    document.getElementById("profile-role").innerText = currentUser.role || "DEVELOPER";
  }

  initServiceTabs();
  initTelemetryChart();
  initForecastChart();
  initIllustrationChart();
  
  fetchUserProfile();
  fetchTopology();
  fetchAPIKeys();
  fetchMonitoredAPIs();
  fetchRealWebsites();
  fetchWatchdogHistory();
  fetchAPIIllustrations(selectedAPIEndpoint);

  pollData();
  pollTimer = setInterval(pollData, 3000);
}

function switchTab(tabId) {
  document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));

  const targetTab = document.getElementById(`tab-${tabId}`);
  if (targetTab) targetTab.classList.add("active");

  const navBtn = document.querySelector(`.nav-item[onclick*="${tabId}"]`);
  if (navBtn) navBtn.classList.add("active");

  const titles = {
    "profile": "User Profile & Email Alert Settings",
    "api-portal": "Generated API Keys & Monitored Targets Portal",
    "telemetry": "Real Live Website Telemetry & PyTorch TCN Forecaster",
    "illustrations": "AI Visual Illustrations & API Code Suggestions"
  };
  document.getElementById("page-title-display").innerText = titles[tabId] || "GriffinOps Portal";

  if (tabId === "telemetry") {
    fetchRealWebsites();
  } else if (tabId === "api-portal") {
    fetchAPIKeys();
    fetchMonitoredAPIs();
  } else if (tabId === "illustrations") {
    fetchAPIIllustrations(selectedAPIEndpoint);
  } else if (tabId === "reports") {
    fetchWatchdogHistory();
  }
}

async function fetchRealWebsites() {
  try {
    const resp = await fetch("/api/v1/real-monitor/live");
    if (resp.ok) {
      const sites = await resp.json();
      const tbody = document.getElementById("real-websites-table-body");
      if (!tbody) return;
      tbody.innerHTML = "";
      const siteList = Object.values(sites);
      if (siteList.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:20px;">🌐 No active monitored target URLs yet. Generate an API Key in Tab 2 or click <strong>+ Monitor Custom Website</strong> above!</td></tr>`;
        return;
      }
      siteList.forEach(site => {
        const lat = site.latest.latency_ms;
        const status = site.latest.status_code;
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${site.name}</strong></td>
          <td><code style="color:var(--accent-amber);">${site.url}</code></td>
          <td><span class="badge badge-purple">${site.type}</span></td>
          <td><strong>${lat} ms</strong></td>
          <td><span class="badge ${status === 200 ? 'badge-amber' : 'badge-rose'}">HTTP ${status}</span></td>
          <td>${site.latest.payload_bytes.toLocaleString()} bytes</td>
          <td>
            <a href="${site.url}" target="_blank" class="btn btn-primary" style="padding:4px 10px; font-size:11px; text-decoration:none;">🌐 Visit Monitored Site ↗</a>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {}
}

function openAddRealSiteModal() { document.getElementById("add-real-site-modal").style.display = "flex"; }
function closeAddRealSiteModal() { document.getElementById("add-real-site-modal").style.display = "none"; }

async function submitAddRealSite() {
  const name = document.getElementById("real-site-name").value;
  const url = document.getElementById("real-site-url").value;
  const siteType = document.getElementById("real-site-type").value;

  try {
    const resp = await fetch("/api/v1/real-monitor/add-site", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, url: url, site_type: siteType })
    });
    if (resp.ok) {
      showToast(`🌐 Started monitoring real site: ${url}`);
      closeAddRealSiteModal();
      fetchRealWebsites();
    }
  } catch (err) {}
}

async function fetchUserProfile() {
  try {
    const resp = await fetch("/api/v1/user/profile");
    if (resp.ok) {
      const p = await resp.json();
      document.getElementById("pref-dev-emails").value = p.developer_emails ? p.developer_emails.join(", ") : "";
      document.getElementById("pref-alerts-enabled").checked = p.email_alerts_enabled;

      const config = p.email_config || {};
      if (document.getElementById("smtp-host-input")) document.getElementById("smtp-host-input").value = config.smtp_host || "";
      if (document.getElementById("smtp-port-input")) document.getElementById("smtp-port-input").value = config.smtp_port || 587;
      if (document.getElementById("smtp-user-input")) document.getElementById("smtp-user-input").value = config.smtp_user || "";

      const badge = document.getElementById("email-config-status-badge");
      if (badge) {
        const isReal = config.active_provider && config.active_provider !== "LOCAL_HTML_PREVIEW";
        badge.innerText = `Active Provider: ${config.active_provider || 'LOCAL_HTML_PREVIEW'}`;
        badge.className = isReal ? "badge badge-purple" : "badge badge-amber";
      }
    }
  } catch (err) {}
}

async function saveProfileSettings() {
  const emailsRaw = document.getElementById("pref-dev-emails").value;
  const emails = emailsRaw.split(",").map(e => e.trim()).filter(e => e.length > 0);
  const enabled = document.getElementById("pref-alerts-enabled").checked;

  try {
    const resp = await fetch("/api/v1/user/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: currentUser ? currentUser.name : "SRE Lead Engineer",
        email: currentUser ? currentUser.email : "admin@griffinops.io",
        organization: "SIES GST AI & Data Science Team",
        developer_emails: emails,
        email_alerts_enabled: enabled
      })
    });
    if (resp.ok) {
      showToast("✅ Profile notification preferences updated.");
    }
  } catch (err) {
    showToast("Error updating preferences.");
  }
}

async function saveEmailCredentials() {
  const smtpHost = document.getElementById("smtp-host-input").value.trim();
  const smtpPort = parseInt(document.getElementById("smtp-port-input").value) || 587;
  const smtpUser = document.getElementById("smtp-user-input").value.trim();
  const smtpPass = document.getElementById("smtp-pass-input").value.trim();
  const brevoKey = document.getElementById("brevo-key-input").value.trim();
  const resendKey = document.getElementById("resend-key-input").value.trim();

  showToast("💾 Saving email credentials & activating server...");
  try {
    const resp = await fetch("/api/v1/user/email-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        smtp_host: smtpHost || null,
        smtp_port: smtpPort,
        smtp_user: smtpUser || null,
        smtp_pass: smtpPass || null,
        brevo_api_key: brevoKey || null,
        resend_api_key: resendKey || null
      })
    });
    if (resp.ok) {
      const data = await resp.json();
      showToast(`✅ ${data.message}`);
      fetchUserProfile();
    }
  } catch (err) {
    showToast("Error saving email credentials.");
  }
}

async function sendTestAlertEmail() {
  const emailsRaw = document.getElementById("pref-dev-emails").value;
  const emails = emailsRaw.split(",").map(e => e.trim()).filter(e => e.length > 0);
  const targetEmail = emails[0] || "sre-dev@sies.edu";

  showToast(`📧 Dispatching test alert email to ${targetEmail}...`);
  try {
    const resp = await fetch("/api/v1/alerts/email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recipient_email: targetEmail })
    });
    if (resp.ok) {
      const res = await resp.json();
      if (res.status === "DELIVERED") {
        showToast(`🎉 DELIVERED! Email alert sent to ${targetEmail} via ${res.provider}! Check your inbox!`);
      } else {
        showToast(`⚠️ Stored in local preview folder (no SMTP key configured). Enter your Gmail/SMTP credentials below to receive emails directly in your inbox!`);
      }
      fetchWatchdogHistory();
    }
  } catch (err) {
    showToast("Error sending email alert.");
  }
}

function initServiceTabs() {
  const container = document.getElementById("services-selector");
  if (!container) return;
  container.innerHTML = "";
  if (MICROSERVICES.length === 0) {
    container.innerHTML = `<span style="font-size:12px; color:var(--text-muted);">No active target services. Generate an API Key in Tab 2 or add a website URL.</span>`;
    return;
  }
  MICROSERVICES.forEach(svc => {
    const btn = document.createElement("button");
    btn.className = `svc-tab ${svc === currentService ? 'active' : ''}`;
    btn.innerText = svc;
    btn.onclick = () => {
      currentService = svc;
      document.querySelectorAll(".svc-tab").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      pollData();
    };
    container.appendChild(btn);
  });
}

function initTelemetryChart() {
  const ctx = document.getElementById("telemetryChart").getContext("2d");
  liveTelemetryChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        { label: "Latency (ms)", data: [], borderColor: "#f59e0b", backgroundColor: "rgba(245,158,11,0.05)", borderWidth: 2, tension: 0.3, yAxisID: "y" },
        { label: "CPU Saturation (%)", data: [], borderColor: "#e11d48", backgroundColor: "rgba(225,29,72,0.05)", borderWidth: 2, tension: 0.3, yAxisID: "y1" },
        { label: "Error Rate", data: [], borderColor: "#8b5cf6", backgroundColor: "rgba(139,92,246,0.05)", borderWidth: 2, tension: 0.3, yAxisID: "y2" },
        { label: "Memory (%)", data: [], borderColor: "#6366f1", backgroundColor: "rgba(99,102,241,0.05)", borderWidth: 2, tension: 0.3, yAxisID: "y1" }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94a3b8" } },
        y: { type: "linear", display: true, position: "left", title: { display: true, text: "Latency (ms)", color: "#f59e0b" }, grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94a3b8" } },
        y1: { type: "linear", display: true, position: "right", title: { display: true, text: "Resource (%)", color: "#e11d48" }, grid: { drawOnChartArea: false }, ticks: { color: "#94a3b8" } },
        y2: { type: "linear", display: false, min: 0, max: 1 }
      },
      plugins: { legend: { labels: { color: "#f8fafc" } } }
    }
  });
}

function initForecastChart() {
  const ctx = document.getElementById("forecastChart").getContext("2d");
  forecastChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: ["T-0", "T+30s", "T+1m", "T+1.5m", "T+2m", "T+2.5m", "T+3m", "T+3.5m", "T+4m", "T+4.5m"],
      datasets: [
        { label: "Forecasted Z-Score", data: [], borderColor: "#f59e0b", backgroundColor: "rgba(245,158,11,0.15)", fill: true, borderWidth: 2, tension: 0.3 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94a3b8" } },
        y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94a3b8" }, title: { display: true, text: "Standard Deviations (σ)", color: "#f59e0b" } }
      },
      plugins: { legend: { display: false } }
    }
  });
}

function initIllustrationChart() {
  const ctx = document.getElementById("illustrationForecastChart").getContext("2d");
  illustrationForecastChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: ["T-0", "T+30s", "T+1m", "T+1.5m", "T+2m", "T+2.5m", "T+3m", "T+3.5m", "T+4m", "T+4.5m"],
      datasets: [
        { label: "Upper Confidence Bound", data: [], borderColor: "#e11d48", borderWidth: 1, borderDash: [4, 4], fill: false },
        { label: "Predicted Trajectory", data: [], borderColor: "#f59e0b", backgroundColor: "rgba(245,158,11,0.15)", fill: true, borderWidth: 2 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94a3b8" } },
        y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94a3b8" } }
      },
      plugins: { legend: { labels: { color: "#94a3b8" } } }
    }
  });
}

async function pollData() {
  try {
    const [telemetryResp, forecastResp, auditResp] = await Promise.all([
      fetch("/api/v1/telemetry/live"),
      fetch("/api/v1/forecast"),
      fetch("/api/v1/audit-reports/latest")
    ]);
    
    if (telemetryResp.ok) {
      const telData = await telemetryResp.json();
      const keys = Object.keys(telData);
      if (JSON.stringify(keys) !== JSON.stringify(MICROSERVICES)) {
        MICROSERVICES = keys;
        if (MICROSERVICES.length > 0 && (!currentService || !MICROSERVICES.includes(currentService))) {
          currentService = MICROSERVICES[0];
        }
        initServiceTabs();
      }
      if (currentService && telData[currentService]) {
        updateTelemetryChart(telData[currentService]);
      }
    }
    
    if (forecastResp.ok) {
      const forecastData = await forecastResp.json();
      updateForecastPanel(forecastData);
    }
    
    if (auditResp.ok) {
      const auditData = await auditResp.json();
      updateAuditReport(auditData);
    }
  } catch (err) {}
}

function updateTelemetryChart(svcData) {
  if (!svcData || !liveTelemetryChart) return;
  const labels = svcData.timestamps.map(t => new Date(t * 1000).toLocaleTimeString());
  liveTelemetryChart.data.labels = labels;
  liveTelemetryChart.data.datasets[0].data = svcData.raw.latency_ms;
  liveTelemetryChart.data.datasets[1].data = svcData.raw.cpu_percent;
  liveTelemetryChart.data.datasets[2].data = svcData.raw.error_rate;
  liveTelemetryChart.data.datasets[3].data = svcData.raw.memory_percent;
  liveTelemetryChart.update("none");
}

function updateForecastPanel(forecastData) {
  const prob = (forecastData.max_failure_prob * 100).toFixed(1);
  document.getElementById("forecast-risk-val").innerText = `${prob}%`;
  document.getElementById("forecast-svc-val").innerText = forecastData.highest_risk_service || "None";
  
  const isAnomaly = forecastData.system_anomaly_detected;
  const statusIndicator = document.getElementById("system-status-indicator");
  const statusText = document.getElementById("system-status-text");

  if (isAnomaly) {
    statusIndicator.className = "system-health-pill hazard";
    statusText.innerText = "PREDICTED OUTAGE HAZARD";
    if (!countdownInterval) startDynamicCountdown(240);
  } else {
    statusIndicator.className = "system-health-pill";
    statusText.innerText = "SYSTEM HEALTHY";
    document.getElementById("forecast-ttf-val").innerText = "HEALTHY";
    if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
  }

  const svcInfo = forecastData.services[currentService];
  if (svcInfo && forecastChart) {
    const zMatrix = svcInfo.forecast_z_scores;
    const maxZs = [];
    for (let col = 0; col < 10; col++) {
      let maxVal = 0;
      for (let row = 0; row < 5; row++) {
        maxVal = Math.max(maxVal, Math.abs(zMatrix[row][col]));
      }
      maxZs.push(maxVal.toFixed(2));
    }
    forecastChart.data.datasets[0].data = maxZs;
    forecastChart.update("none");
  }
}

function updateAuditReport(report) {
  const container = document.getElementById("report-content-body");
  if (!report || report.system_status === "HEALTHY") {
    container.innerHTML = `<div class="placeholder-report"><p>🟢 System operational. Microservice telemetry baseline normal. Zero outage hazards detected.</p></div>`;
    return;
  }
  const rca = report.root_cause_analysis || {};
  const commit = report.ci_cd_correlation || {};
  const impact = report.business_impact || {};
  const sev = report.severity_level || "CRITICAL (SEV-1)";

  container.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:16px;">
      <div style="background:var(--accent-rose-glow); border:1px solid var(--accent-rose); padding:14px 20px; border-radius:10px; font-weight:bold; display:flex; justify-content:space-between; align-items:center; color:#ff4d8d;">
        <span>🚨 [${sev}] PRE-MORTEM HAZARD: ${rca.service} Outage Threat</span>
        <span id="report-ttf-tag" style="font-size:16px; background:#e11d48; color:#fff; padding:4px 12px; border-radius:20px;">⏳ Time Left: ${report.forecasted_time_to_failure_human}</span>
      </div>

      <!-- BUSINESS & FINANCIAL IMPACT CARD -->
      <div style="background:linear-gradient(135deg, rgba(245,158,11,0.1), rgba(180,83,9,0.05)); border:1px solid rgba(245,158,11,0.3); border-radius:10px; padding:16px;">
        <div style="color:var(--accent-amber); font-size:12px; font-weight:bold; text-transform:uppercase; letter-spacing:1px; margin-bottom:10px;">📉 ESTIMATED BUSINESS & FINANCIAL IMPACT</div>
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin-bottom:10px;">
          <div style="background:#0b0f19; padding:10px; border-radius:6px;">
            <span style="font-size:11px; color:#94a3b8; display:block;">Financial Risk Rate</span>
            <span style="font-size:15px; font-weight:bold; color:#f43f5e;">${impact.estimated_loss_per_minute || '$450/min'}</span>
          </div>
          <div style="background:#0b0f19; padding:10px; border-radius:6px;">
            <span style="font-size:11px; color:#94a3b8; display:block;">Impacted Customer Sessions</span>
            <span style="font-size:15px; font-weight:bold; color:#fbbf24;">${impact.affected_active_user_sessions || '14,200 users'}</span>
          </div>
          <div style="background:#0b0f19; padding:10px; border-radius:6px;">
            <span style="font-size:11px; color:#94a3b8; display:block;">Business Risk Level</span>
            <span style="font-size:14px; font-weight:bold; color:#38bdf8;">${impact.business_risk_level || 'HIGH REVENUE RISK'}</span>
          </div>
        </div>
        <div style="font-size:12px; color:#e2e8f0;">${impact.summary || ''}</div>
      </div>

      <!-- ROOT CAUSE & CI/CD CORRELATION -->
      <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:12px;">
        <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px;">
          <span style="font-size:11px; color:#94a3b8; display:block;">Faulty Microservice</span>
          <span style="font-size:15px; font-weight:bold; color:#fff;">${rca.service}</span>
        </div>
        <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px;">
          <span style="font-size:11px; color:#94a3b8; display:block;">Primary Metric Breach</span>
          <span style="font-size:15px; font-weight:bold; color:#fff;">${rca.primary_metric} (+${rca.max_z_score_deviation} σ)</span>
        </div>
        <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px;">
          <span style="font-size:11px; color:#94a3b8; display:block;">Causal Confidence</span>
          <span style="font-size:15px; font-weight:bold; color:#fff;">${(rca.causal_confidence_score * 100).toFixed(0)}%</span>
        </div>
        <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px;">
          <span style="font-size:11px; color:#94a3b8; display:block;">Blast Radius</span>
          <span style="font-size:15px; font-weight:bold; color:#fff;">${report.blast_radius ? report.blast_radius.affected_microservices_count : 2} services</span>
        </div>
      </div>

      <div style="background:#0f172a; border-left:4px solid var(--accent-amber); padding:12px; font-family:monospace; font-size:12px; color:#fef3c7;">
        <strong>Correlated CI/CD Deployment Commit:</strong> <code>${commit.commit_id}</code> by ${commit.author}<br/>
        <strong>Message:</strong> ${commit.message}
      </div>

      <!-- ACTIONABLE REMEDIATION SUGGESTION -->
      <div style="background:var(--accent-amber-glow); border:1px solid var(--accent-amber); padding:14px; border-radius:8px; color:#fef3c7;">
        <strong>💡 GriffinOps Recommended Action:</strong><br/>
        ${report.suggested_action}
        <div style="background:#070a11; border:1px solid #14b8a6; color:#2dd4bf; padding:8px 12px; font-family:monospace; font-size:12px; border-radius:6px; margin-top:8px;">
          $ ${report.remediation_command || `kubectl rollout undo deployment/${rca.service} -n production`}
        </div>
      </div>
    </div>
  `;
}

async function fetchAPIIllustrations(apiEndpoint) {
  selectedAPIEndpoint = apiEndpoint;
  document.getElementById("illustrations-api-tag").innerText = apiEndpoint;

  try {
    const resp = await fetch(`/api/v1/illustrations/details?api_endpoint=${encodeURIComponent(apiEndpoint)}`);
    if (resp.ok) {
      const data = await resp.json();
      
      const treeContainer = document.getElementById("trace-tree-container");
      treeContainer.innerHTML = data.illustrations.trace_tree.map(n => `
        <div class="trace-tree-node ${n.status === 'HAZARD' ? 'hazard' : ''}">
          <span><strong>${n.node}</strong></span>
          <span>Status: ${n.status} &bull; ${n.latency_ms}ms</span>
        </div>
      `).join("");

      if (illustrationForecastChart) {
        const curve = data.illustrations.forecast_curve;
        illustrationForecastChart.data.datasets[0].data = curve.map(c => c.upper_bound_z);
        illustrationForecastChart.data.datasets[1].data = curve.map(c => c.predicted_z);
        illustrationForecastChart.update("none");
      }

      const suggBox = document.getElementById("api-suggestions-box");
      const sugg = data.ai_suggestions;
      suggBox.innerHTML = `
        <h3>💡 AI Code Fix & Architectural Recommendation for ${apiEndpoint}:</h3>
        <p style="margin-bottom:12px; font-size:13px; line-height:1.5;">${sugg.recommended_fix}</p>
        <div style="background:#0f172a; padding:10px; border-radius:6px; font-family:monospace; font-size:12px; color:#fef3c7;">
          $ ${sugg.remediation_command}
        </div>
      `;
    }
  } catch (err) {}
}

async function fetchAPIKeys() {
  try {
    const resp = await fetch("/api/v1/keys");
    if (resp.ok) {
      const keys = await resp.json();
      const tbody = document.getElementById("api-keys-table-body");
      if (!tbody) return;
      tbody.innerHTML = "";
      if (keys.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:16px;">🔑 No API keys generated yet. Click <strong>+ Generate New API Key</strong> above to get started.</td></tr>`;
        return;
      }
      keys.forEach(k => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${k.name}</strong></td>
          <td><span class="key-code">${k.api_key}</span></td>
          <td><code>${k.assigned_service}</code></td>
          <td><span class="badge badge-amber">${k.environment}</span></td>
          <td>${k.requests_total.toLocaleString()}</td>
          <td><span class="badge badge-amber">${k.status}</span></td>
          <td>
            <button class="btn btn-primary" style="padding:4px 8px; font-size:11px; margin-right:4px;" onclick="openSDKEmbedModal('${k.api_key}')">⚙️ Embed SDK</button>
            <button class="btn-danger-sm" onclick="revokeKey('${k.key_id}')">Revoke</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {}
}

async function fetchMonitoredAPIs() {
  try {
    const resp = await fetch("/api/v1/monitored-apis");
    if (resp.ok) {
      const apis = await resp.json();
      const tbody = document.getElementById("monitored-apis-table-body");
      if (!tbody) return;
      tbody.innerHTML = "";
      if (apis.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:16px;">🌐 No monitored API targets registered yet. Generate an API key or register a website URL.</td></tr>`;
        return;
      }
      apis.forEach(api => {
        const tr = document.createElement("tr");
        tr.style.cursor = "pointer";
        tr.onclick = () => selectAPIEndpointDrilldown(api.api_endpoint, api.service);
        tr.innerHTML = `
          <td><strong style="color:var(--accent-amber);">${api.api_endpoint}</strong></td>
          <td><code>${api.service}</code></td>
          <td><span class="badge badge-purple">${api.method}</span></td>
          <td>${api.api_key_name}</td>
          <td>${api.rpm} req/min</td>
          <td>${api.avg_latency_ms} ms</td>
          <td>${api.error_rate}</td>
          <td><span class="badge badge-amber">${api.health_status}</span></td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {}
}

function selectAPIEndpointDrilldown(endpoint, service) {
  currentService = service;
  selectedAPIEndpoint = endpoint;
  
  switchTab("illustrations");
  fetchAPIIllustrations(endpoint);
  showToast(`🔍 Showing AI Illustrations & Code Suggestions for API: ${endpoint}`);
}

async function fetchWatchdogHistory() {
  try {
    const resp = await fetch("/api/v1/watchdog/history");
    if (resp.ok) {
      const logs = await resp.json();
      const tbody = document.getElementById("watchdog-history-table-body");
      if (!tbody) return;
      tbody.innerHTML = "";
      if (logs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#94a3b8;">No background alerts triggered yet. Operate the Standalone Store App to inject faults!</td></tr>`;
        return;
      }
      logs.forEach(l => {
        const tr = document.createElement("tr");
        const filename = l.preview_path ? l.preview_path.split(/[/\\]/).pop() : "";
        const previewUrl = filename ? `/api/v1/email-previews/${filename}` : "#";
        tr.innerHTML = `
          <td>${l.timestamp}</td>
          <td><code>${l.report_id}</code></td>
          <td><code>${l.target_service}</code></td>
          <td><strong>${l.recipient}</strong></td>
          <td><span class="badge badge-purple">${l.status || 'SENT'}</span></td>
          <td><a href="${previewUrl}" target="_blank" style="color:var(--accent-amber); font-weight:bold; text-decoration:none;">📄 View Preview ↗</a></td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {}
}

function openCreateKeyModal() { document.getElementById("create-key-modal").style.display = "flex"; }
function closeCreateKeyModal() { document.getElementById("create-key-modal").style.display = "none"; }

async function submitCreateAPIKey() {
  const name = document.getElementById("new-key-name").value;
  const targetUrl = document.getElementById("new-key-url").value;
  const env = document.getElementById("new-key-env").value;

  try {
    const resp = await fetch("/api/v1/keys/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, target_url: targetUrl, environment: env })
    });
    if (resp.ok) {
      const newKey = await resp.json();
      showToast(`🔑 Generated API Key: ${newKey.api_key}`);
      closeCreateKeyModal();
      fetchAPIKeys();
      fetchMonitoredAPIs();
      openSDKEmbedModal(newKey.api_key);
    }
  } catch (err) {}
}

async function revokeKey(keyId) {
  try {
    const resp = await fetch(`/api/v1/keys/${keyId}`, { method: "DELETE" });
    if (resp.ok) {
      showToast("API Key revoked successfully.");
      fetchAPIKeys();
    }
  } catch (err) {}
}

function downloadPDFReport() {
  const reportId = "GO-RPT-LIVE";
  window.open(`/api/v1/audit-reports/${reportId}/pdf`, "_blank");
  showToast("📥 Downloading Pre-Mortem PDF Audit Report...");
}

function downloadDOCXDoc() {
  window.open("/api/v1/docs/project-report.docx", "_blank");
  showToast("📄 Downloading Master Project Report (.DOCX)...");
}

function downloadProjectReport() {
  window.open("/api/v1/docs/project-report.docx", "_blank");
  showToast("📄 Downloading Master Project Report (.DOCX)...");
}

// --- DYNAMIC COUNTDOWN TIMER FOR PRE-MORTEM OUTAGE HAZARDS ---
let outageTimerSeconds = 240; // 4 minutes
let countdownInterval = null;

function startDynamicCountdown(initialSeconds = 240) {
  if (countdownInterval) clearInterval(countdownInterval);
  outageTimerSeconds = initialSeconds;

  countdownInterval = setInterval(() => {
    if (outageTimerSeconds > 0) {
      outageTimerSeconds--;
      const mins = Math.floor(outageTimerSeconds / 60);
      const secs = outageTimerSeconds % 60;
      const formatted = `${mins}m ${secs < 10 ? '0' : ''}${secs}s`;

      const ttfElem = document.getElementById("forecast-ttf-val");
      if (ttfElem) ttfElem.innerText = `T-minus ${formatted}`;

      const reportTtfTag = document.getElementById("report-ttf-tag");
      if (reportTtfTag) reportTtfTag.innerText = `⏳ Time Left: ${formatted}`;
    } else {
      clearInterval(countdownInterval);
    }
  }, 1000);
}

// --- SDK EMBED CODE SNIPPETS MODAL ---
let activeSDKApiKey = "gop_live_default";
let activeSnippetTab = "script";

function openSDKEmbedModal(apiKey) {
  if (apiKey) activeSDKApiKey = apiKey;
  document.getElementById("sdk-embed-modal").style.display = "flex";
  renderSnippets();
}

function closeSDKEmbedModal() {
  document.getElementById("sdk-embed-modal").style.display = "none";
}

function switchSnippetTab(tab) {
  activeSnippetTab = tab;
  ['script', 'js', 'python', 'curl'].forEach(t => {
    const btn = document.getElementById(`btn-snippet-${t}`);
    const box = document.getElementById(`snippet-box-${t}`);
    if (btn) btn.classList.remove("active");
    if (box) box.style.display = "none";
  });
  const activeBtn = document.getElementById(`btn-snippet-${tab}`);
  const activeBox = document.getElementById(`snippet-box-${tab}`);
  if (activeBtn) activeBtn.classList.add("active");
  if (activeBox) activeBox.style.display = "block";
}

function renderSnippets() {
  const scriptTag = `<script src="${window.location.origin}/static/js/griffinops-sdk.js" data-api-key="${activeSDKApiKey}"></script>`;
  
  const jsFetch = `// JavaScript / Hosted Web App Fetch Snippet
fetch("${window.location.origin}/api/v1/telemetry/live", {
  headers: {
    "X-GriffinOps-API-Key": "${activeSDKApiKey}"
  }
}).then(res => res.json()).then(data => console.log(data));`;

  const pythonReq = `# Python Requests / FastAPI / Flask Snippet
import requests

headers = {"X-GriffinOps-API-Key": "${activeSDKApiKey}"}
response = requests.get("${window.location.origin}/api/v1/health", headers=headers)
print(response.json())`;

  const curlCmd = `# cURL Command Header
curl -X GET "${window.location.origin}/api/v1/health" \\
  -H "X-GriffinOps-API-Key: ${activeSDKApiKey}"`;

  if (document.getElementById("snippet-box-script")) document.getElementById("snippet-box-script").innerText = scriptTag;
  if (document.getElementById("snippet-box-js")) document.getElementById("snippet-box-js").innerText = jsFetch;
  if (document.getElementById("snippet-box-python")) document.getElementById("snippet-box-python").innerText = pythonReq;
  if (document.getElementById("snippet-box-curl")) document.getElementById("snippet-box-curl").innerText = curlCmd;
}

function copyActiveSnippet() {
  const box = document.getElementById(`snippet-box-${activeSnippetTab}`);
  if (box) {
    navigator.clipboard.writeText(box.innerText);
    showToast("📋 Code snippet copied to clipboard!");
  }
}

let activeCardSnippetTab = "script";

function switchCardSnippetTab(tab) {
  activeCardSnippetTab = tab;
  ['script', 'js', 'python', 'curl'].forEach(t => {
    const btn = document.getElementById(`card-btn-snippet-${t}`);
    const box = document.getElementById(`card-snippet-box-${t}`);
    if (btn) btn.classList.remove("active");
    if (box) box.style.display = "none";
  });
  const activeBtn = document.getElementById(`card-btn-snippet-${tab}`);
  const activeBox = document.getElementById(`card-snippet-box-${tab}`);
  if (activeBtn) activeBtn.classList.add("active");
  if (activeBox) activeBox.style.display = "block";
}

function copyCardSnippet() {
  const box = document.getElementById(`card-snippet-box-${activeCardSnippetTab}`);
  if (box) {
    navigator.clipboard.writeText(box.innerText);
    showToast("📋 Code snippet copied to clipboard!");
  }
}

async function fetchTopology() {
  try {
    const resp = await fetch("/api/v1/topology");
    if (resp.ok) {
      const data = await resp.json();
      renderTopologySVG(data);
    }
  } catch (err) {}
}

function renderTopologySVG(data) {
  const svg = document.getElementById("topology-svg");
  if (!svg) return;
  svg.innerHTML = "";
  const width = svg.clientWidth || 400;
  const height = 240;
  
  const coords = {
    "frontend-service": { x: width * 0.15, y: height * 0.5 },
    "cartservice": { x: width * 0.45, y: height * 0.25 },
    "checkoutservice": { x: width * 0.45, y: height * 0.75 },
    "paymentservice": { x: width * 0.80, y: height * 0.85 },
    "recommendationservice": { x: width * 0.80, y: height * 0.45 },
    "adservice": { x: width * 0.80, y: height * 0.15 }
  };

  data.edges.forEach(e => {
    const s = coords[e.source]; const t = coords[e.target];
    if (s && t) {
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", s.x); line.setAttribute("y1", s.y);
      line.setAttribute("x2", t.x); line.setAttribute("y2", t.y);
      line.setAttribute("stroke", "rgba(255,255,255,0.15)");
      line.setAttribute("stroke-width", "2"); line.setAttribute("stroke-dasharray", "4");
      svg.appendChild(line);
    }
  });

  data.nodes.forEach(n => {
    const pos = coords[n.id];
    if (!pos) return;
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", pos.x); circle.setAttribute("cy", pos.y);
    circle.setAttribute("r", "14"); circle.setAttribute("fill", "#f59e0b");
    circle.setAttribute("stroke", "#ffffff"); circle.setAttribute("stroke-width", "2");
    
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", pos.x); text.setAttribute("y", pos.y + 26);
    text.setAttribute("text-anchor", "middle"); text.setAttribute("fill", "#94a3b8");
    text.setAttribute("font-size", "9px"); text.setAttribute("font-weight", "600");
    text.textContent = n.id.replace("-service", "");
    g.appendChild(circle); g.appendChild(text); svg.appendChild(g);
  });
}

function showToast(msg) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.innerText = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3500);
}
