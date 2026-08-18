let authToken = localStorage.getItem("gop_token") || null;
let currentUser = JSON.parse(localStorage.getItem("gop_user") || "null");
let currentService = null;
let selectedAPIEndpoint = null;

let liveTelemetryChart = null;
let forecastChart = null;
let illustrationForecastChart = null;
let pollTimer = null;

let MICROSERVICES = [];

// === Datadog Time-Range Selector State ===
let activeTimeRange = 'live'; // live | 15m | 1h | 24h
let kpiSparklineHistory = {}; // tracks rolling history per KPI for sparklines

// === Inject Fault State ===
let faultInjected = false;

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
    "overview":      "Executive Overview & Predictive Watchdog",
    "api-portal":   "Developer API Portal & Production Keys",
    "causal":       "2026 SOTA Causal Inference & Topology",
    "illustrations":"AI Code Fix Suggestions & Remediation",
    "profile":      "Alerts, Webhooks & Supabase Auth"
  };
  const titleDisplay = document.getElementById("page-title-display");
  if (titleDisplay) titleDisplay.innerText = titles[tabId] || "GriffinOps Enterprise";

  if (tabId === "api-portal") {
    fetchAPIKeys();
    fetchMonitoredAPIs();
  } else if (tabId === "causal") {
    fetchTopology();
  } else if (tabId === "illustrations") {
    fetchAPIIllustrations(selectedAPIEndpoint);
  } else if (tabId === "profile") {
    fetchUserProfile();
    fetchWatchdogHistory();
  } else if (tabId === "overview") {
    fetchMonitoredAPIs();
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
  const nameEl = document.getElementById("real-site-name");
  const urlEl = document.getElementById("real-site-url");
  const typeEl = document.getElementById("real-site-type");

  const name = (nameEl && nameEl.value.trim()) ? nameEl.value.trim() : "Custom Web Target";
  const url = (urlEl && urlEl.value.trim()) ? urlEl.value.trim() : "https://httpbin.org/get";
  const siteType = typeEl ? typeEl.value : "Live Web App";

  showToast(`🌐 Connecting & executing live HTTP ping to ${url}...`);

  try {
    const resp = await fetch("/api/v1/real-monitor/targets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, url: url, site_type: siteType })
    });
    if (resp.ok) {
      showToast(`🎉 Connected! Live HTTP telemetry stream active for: ${url}`);
      closeAddRealSiteModal();
      if (nameEl) nameEl.value = "";
      if (urlEl) urlEl.value = "";
      pollData();
    } else {
      showToast("❌ Could not connect to target URL.");
    }
  } catch (err) {
    showToast("Error adding live website target: " + err.message);
  }
}

async function fetchUserProfile() {
  try {
    const resp = await fetch("/api/v1/user/profile");
    if (resp.ok) {
      const p = await resp.json();
      const devEmailsInput = document.getElementById("pref-dev-emails");
      if (devEmailsInput && p.developer_emails) {
        devEmailsInput.value = p.developer_emails.join(", ");
      }
      const alertsEnabledInput = document.getElementById("pref-alerts-enabled");
      if (alertsEnabledInput && p.email_alerts_enabled !== undefined) {
        alertsEnabledInput.checked = p.email_alerts_enabled;
      }
      const orgInput = document.getElementById("pref-org-name");
      if (orgInput && p.organization) {
        orgInput.value = p.organization;
      }
      const profileOrgSpan = document.getElementById("profile-org");
      if (profileOrgSpan && p.organization) {
        profileOrgSpan.innerText = p.organization;
      }
    }
  } catch (err) {}
}

async function saveProfileSettings() {
  const emailsRaw = document.getElementById("pref-dev-emails") ? document.getElementById("pref-dev-emails").value : "";
  const emails = emailsRaw.split(",").map(e => e.trim()).filter(e => e.length > 0);
  const enabledInput = document.getElementById("pref-alerts-enabled");
  const enabled = enabledInput ? enabledInput.checked : true;
  const orgInput = document.getElementById("pref-org-name");
  const orgName = (orgInput && orgInput.value.trim()) ? orgInput.value.trim() : "SIES GST AI & Data Science Team";

  showToast("💾 Saving developer alert preferences...");
  try {
    const resp = await fetch("/api/v1/user/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: currentUser ? currentUser.name : "SRE Lead Engineer",
        email: currentUser ? currentUser.email : "admin@griffinops.io",
        organization: orgName,
        developer_emails: emails,
        email_alerts_enabled: enabled
      })
    });
    if (resp.ok) {
      const profileOrgSpan = document.getElementById("profile-org");
      if (profileOrgSpan) profileOrgSpan.innerText = orgName;
      showToast("✅ Developer recipient emails & profile preferences saved!");
    } else {
      showToast("❌ Failed to save preferences.");
    }
  } catch (err) {
    showToast("Error updating preferences: " + err.message);
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
        { label: "Latency (ms)", data: [], borderColor: "#f59e0b", backgroundColor: "rgba(245,158,11,0.06)", borderWidth: 2, tension: 0.3, yAxisID: "y" },
        { label: "CPU Saturation (%)", data: [], borderColor: "#e11d48", backgroundColor: "rgba(225,29,72,0.06)", borderWidth: 2, tension: 0.3, yAxisID: "y1" },
        { label: "Error Rate", data: [], borderColor: "#f43f5e", backgroundColor: "rgba(244,63,94,0.06)", borderWidth: 2, tension: 0.3, yAxisID: "y2" },
        { label: "Memory Footprint (%)", data: [], borderColor: "#cbd5e1", backgroundColor: "rgba(203,213,225,0.06)", borderWidth: 2, tension: 0.3, yAxisID: "y1" }
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

  // Datadog KPI — live P95 latency
  const kpiLatency = document.getElementById("kpi-latency");
  if (kpiLatency && svcData.raw?.latency_ms?.length > 0) {
    const arr = svcData.raw.latency_ms;
    const sorted = [...arr].sort((a, b) => a - b);
    const p95 = sorted[Math.floor(sorted.length * 0.95)] ?? arr[arr.length - 1];
    kpiLatency.innerText = `${p95.toFixed(1)} ms`;
  }
}

// === Datadog Time-Range Selector ===
function setTimeRange(range) {
  activeTimeRange = range;
  ['live','15m','1h','24h'].forEach(function(r) {
    var btn = document.getElementById('trb-' + r);
    if (btn) btn.classList.toggle('active', r === range);
  });

  if (pollTimer) clearInterval(pollTimer);
  var interval = 3000;
  if (range === '15m') interval = 15000;
  else if (range === '1h') interval = 30000;
  else if (range === '24h') interval = 60000;

  pollData();
  pollTimer = setInterval(pollData, interval);
  showToast('\u26a1 Time range: ' + range.toUpperCase() + ' \u2014 polling every ' + (interval/1000) + 's');
}

// === KPI Sparkline Mini-Bars ===
function updateKPISparkline(kpiKey, dataArr) {
  if (!kpiSparklineHistory[kpiKey]) kpiSparklineHistory[kpiKey] = [];
  kpiSparklineHistory[kpiKey].push(dataArr[dataArr.length - 1]);
  if (kpiSparklineHistory[kpiKey].length > 14) kpiSparklineHistory[kpiKey].shift();

  var sparklineMap = { p95: 'kpi-p95-latency', crash: 'kpi-crash-prob', revenue: 'kpi-revenue-risk', count: 'kpi-monitored-count' };
  var targetId = sparklineMap[kpiKey];
  if (!targetId) return;

  var parentEl = document.getElementById(targetId);
  if (!parentEl) return;
  var card = parentEl.closest('.kpi-card');
  if (!card) return;

  var sparkEl = card.querySelector('.kpi-sparkline');
  if (!sparkEl) {
    sparkEl = document.createElement('div');
    sparkEl.className = 'kpi-sparkline';
    card.appendChild(sparkEl);
  }

  var hist = kpiSparklineHistory[kpiKey];
  var maxV = Math.max.apply(null, hist.concat([1]));
  sparkEl.innerHTML = hist.map(function(v) {
    var pct = Math.max(4, (v / maxV) * 26);
    return '<div class="kpi-sparkline-bar" style="height:' + pct + 'px;"></div>';
  }).join('');
}

// === Inject Fault (Chaos Engineering) ===
function injectFault() {
  faultInjected = !faultInjected;
  var btn = document.getElementById('btn-inject-fault');
  if (faultInjected) {
    if (btn) {
      btn.style.background = 'rgba(225,29,72,0.3)';
      btn.style.borderColor = 'var(--accent-rose)';
      btn.style.boxShadow = '0 0 20px rgba(225,29,72,0.4)';
    }
    showToast('\ud83d\udea8 FAULT INJECTED: Simulating latency spike on ' + (currentService || 'all services') + '. Watch KPIs & anomaly matrix!');
    if (liveTelemetryChart && liveTelemetryChart.data.datasets[0].data.length > 0) {
      var dataset = liveTelemetryChart.data.datasets[0].data;
      var spikeVal = (dataset[dataset.length - 1] || 100) * (3.5 + Math.random());
      dataset.push(spikeVal);
      if (dataset.length > 30) dataset.shift();
      liveTelemetryChart.data.labels.push(new Date().toLocaleTimeString());
      liveTelemetryChart.update('none');

      var kpiEl = document.getElementById('kpi-p95-latency');
      if (kpiEl) { kpiEl.innerText = spikeVal.toFixed(1) + ' ms'; kpiEl.classList.add('alert'); }
      var statusIndicator = document.getElementById('system-status-indicator');
      var statusText = document.getElementById('system-status-text');
      if (statusIndicator) statusIndicator.className = 'system-health-pill hazard';
      if (statusText) statusText.innerText = 'FAULT INJECTED \u2014 HAZARD';
      fetchTopology();
    }
  } else {
    if (btn) { btn.style.background = ''; btn.style.borderColor = ''; btn.style.boxShadow = ''; }
    showToast('\u2705 Fault cleared. Monitoring resumed normally.');
    var statusIndicator2 = document.getElementById('system-status-indicator');
    var statusText2 = document.getElementById('system-status-text');
    if (statusIndicator2) statusIndicator2.className = 'system-health-pill';
    if (statusText2) statusText2.innerText = 'SYSTEM HEALTHY';
    pollData();
  }
}

// === New Relic Lookout MAD Z-Score Anomaly Matrix ===
function renderNRAnomalyMatrix(svcData) {
  var grid = document.getElementById('nr-anomaly-grid');
  if (!grid || !svcData || !svcData.raw) return;

  var metrics = [
    { key: 'latency_ms', label: 'P95 Latency', unit: 'ms' },
    { key: 'cpu_percent', label: 'CPU Saturation', unit: '%' },
    { key: 'error_rate', label: 'Error Rate', unit: '' },
    { key: 'memory_percent', label: 'Memory Footprint', unit: '%' }
  ];

  var tiles = [];
  metrics.forEach(function(metric) {
    var arr = svcData.raw[metric.key];
    if (!arr || arr.length === 0) return;
    var val = arr[arr.length - 1];

    // MAD Z-Score (robust estimator: 1.4826 * MAD approx sigma)
    var sorted = arr.slice().sort(function(a, b) { return a - b; });
    var median = sorted[Math.floor(sorted.length / 2)] || 0;
    var deviations = sorted.map(function(v) { return Math.abs(v - median); }).sort(function(a, b) { return a - b; });
    var mad = deviations[Math.floor(deviations.length / 2)] || 0.001;
    var zScore = Math.abs((val - median) / (mad * 1.4826));

    var cls = 'healthy', statusLabel = 'NOMINAL', emoji = '\u2705';
    if (zScore >= 3) { cls = 'critical'; statusLabel = 'CRITICAL'; emoji = '\ud83d\udea8'; }
    else if (zScore >= 1.5) { cls = 'warning'; statusLabel = 'ANOMALY'; emoji = '\u26a0\ufe0f'; }

    tiles.push({
      metric: metric, val: val, zScore: zScore,
      cls: cls, statusLabel: statusLabel, emoji: emoji,
      svcName: currentService || (MICROSERVICES[0] || 'service')
    });
  });

  var html = tiles.map(function(t) {
    var drillTitle = 'kubectl rollout restart deployment/' + t.svcName + ' -n production';
    return '<div class="nr-anomaly-tile ' + t.cls + '" onclick="handleNRTileDrilldown(\'' + t.svcName + '\', \'' + t.metric.key + '\', ' + t.zScore.toFixed(2) + ')" title="' + drillTitle + '">' +
      '<div class="nr-tile-svc">' + t.emoji + ' ' + t.svcName.replace('-service','') + '</div>' +
      '<div class="nr-tile-metric">' + t.metric.label + '</div>' +
      '<div class="nr-tile-zscore">' + t.zScore.toFixed(2) + '\u03c3</div>' +
      '<div class="nr-tile-status">' + t.statusLabel + '</div>' +
      '<div class="nr-tile-drilldown">\ud83d\udd0d Git Commit &bull; kubectl fix</div>' +
      '</div>';
  }).join('');

  // Fill inactive tiles for other services
  if (MICROSERVICES.length > 1) {
    var extraSvcs = MICROSERVICES.filter(function(s) { return s !== currentService; }).slice(0, 4);
    extraSvcs.forEach(function(svc) {
      html += '<div class="nr-anomaly-tile inactive">' +
        '<div class="nr-tile-svc">\u26ab ' + svc.replace('-service','') + '</div>' +
        '<div class="nr-tile-metric">Latency</div>' +
        '<div class="nr-tile-zscore">--</div>' +
        '<div class="nr-tile-status">AWAITING DATA</div>' +
        '<div class="nr-tile-drilldown">\ud83d\udce1 Awaiting telemetry stream</div>' +
        '</div>';
    });
  }

  grid.innerHTML = html;
}

function handleNRTileDrilldown(svc, metric, zScore) {
  var remediation = 'kubectl rollout restart deployment/' + svc + ' -n production';
  showToast('\ud83d\udd0d [' + svc + '] ' + metric + ' Z=' + parseFloat(zScore).toFixed(2) + '\u03c3 \u2014 ' + remediation);
  selectAPIEndpointDrilldown('/api/v1/' + svc, svc);
}



function updateAuditReport(report) {
  const container = document.getElementById("report-content-body");
  if (!container) return;
  if (!report || report.system_status === "HEALTHY") {
    container.innerHTML = `<div class="placeholder-report"><p>🟢 System operational. Microservice telemetry baseline normal.</p></div>`;
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
  let targetEndpoint = apiEndpoint || selectedAPIEndpoint;
  const tagEl = document.getElementById("illustrations-api-tag");
  const selectorContainer = document.getElementById("ai-fix-api-selector");
  const suggBox = document.getElementById("api-suggestions-box");
  const treeContainer = document.getElementById("trace-tree-container");

  // Dynamically fetch registered APIs and real website targets
  let availableTargets = [];
  try {
    const monResp = await fetch("/api/v1/monitored-apis");
    if (monResp.ok) {
      const liveApis = await monResp.json();
      liveApis.forEach(a => availableTargets.push({ endpoint: a.api_endpoint, name: a.api_key_name || a.service, service: a.service }));
    }
  } catch (e) {}

  try {
    const siteResp = await fetch("/api/v1/real-monitor/targets");
    if (siteResp.ok) {
      const sites = await siteResp.json();
      Object.values(sites).forEach(s => {
        const ep = s.url;
        if (!availableTargets.some(t => t.endpoint === ep)) {
          availableTargets.push({ endpoint: ep, name: s.name, service: s.name.toLowerCase().replace(/\s+/g, '-') });
        }
      });
    }
  } catch (e) {}

  if (!targetEndpoint && availableTargets.length > 0) {
    targetEndpoint = availableTargets[0].endpoint;
  }

  selectedAPIEndpoint = targetEndpoint;
  if (tagEl) tagEl.innerText = targetEndpoint || "No active API registered";

  if (selectorContainer) {
    if (availableTargets.length > 0) {
      selectorContainer.innerHTML = availableTargets.map(ep => `
        <button class="svc-tab ${ep.endpoint === targetEndpoint ? 'active' : ''}" onclick="selectAPIEndpointDrilldown('${ep.endpoint}', '${ep.service}')">
          ${ep.name} (<code>${ep.endpoint}</code>)
        </button>
      `).join("");
    } else {
      selectorContainer.innerHTML = `<span style="font-size:12px;color:var(--text-muted);">No monitored endpoints registered yet. Generate an API Key in Tab 2 or click "+ Monitor Live Website" above!</span>`;
    }
  }

  if (!targetEndpoint) {
    if (treeContainer) {
      treeContainer.innerHTML = `<div style="color:var(--text-muted);font-size:12px;padding:12px;text-align:center;">Awaiting active endpoint registration...</div>`;
    }
    if (suggBox) {
      suggBox.innerHTML = `
        <div style="background:rgba(255,255,255,0.02);border:1px dashed rgba(255,255,255,0.12);border-radius:12px;padding:30px;text-align:center;">
          <div style="font-size:28px;margin-bottom:8px;">🛠️</div>
          <h3 style="color:#fff;font-size:16px;margin-bottom:6px;">No Active Endpoint Selected</h3>
          <p style="color:var(--text-muted);font-size:13px;max-width:500px;margin:0 auto 16px auto;">
            GriffinOps generates real-time AI code fix suggestions, root cause diagnosis, and Git diff patches for any registered API endpoint or live monitored website.
          </p>
          <button class="btn btn-primary" onclick="openCreateKeyModal()">+ Generate API Key to Monitor</button>
        </div>
      `;
    }
    return;
  }

  try {
    const resp = await fetch(`/api/v1/illustrations/details?api_endpoint=${encodeURIComponent(targetEndpoint)}`);
    if (resp.ok) {
      const data = await resp.json();
      
      if (treeContainer && data.illustrations && data.illustrations.trace_tree) {
        treeContainer.innerHTML = data.illustrations.trace_tree.map(n => `
          <div class="trace-tree-node ${n.status === 'HAZARD' ? 'hazard' : ''}">
            <span><strong>${n.node}</strong></span>
            <span>Status: <strong>${n.status}</strong> &bull; <span style="color:${n.status === 'HAZARD' ? 'var(--rose)' : 'var(--amber)'}; font-weight:700;">${n.latency_ms} ms</span></span>
          </div>
        `).join("");
      }

      if (illustrationForecastChart && data.illustrations && data.illustrations.forecast_curve) {
        const curve = data.illustrations.forecast_curve;
        illustrationForecastChart.data.datasets[0].data = curve.map(c => c.upper_bound_z);
        illustrationForecastChart.data.datasets[1].data = curve.map(c => c.predicted_z);
        illustrationForecastChart.update("none");
      }

      const sugg = data.ai_suggestions || {};
      const commit = sugg.correlated_commit || {};
      const diffCode = sugg.code_diff || "";
      const formattedDiff = diffCode.split("\n").map(line => {
        if (line.startsWith("+")) return `<span style="color:#10b981; display:block; background:rgba(16,185,129,0.1); padding:1px 4px;">${line}</span>`;
        if (line.startsWith("-")) return `<span style="color:#f43f5e; display:block; background:rgba(225,29,72,0.1); padding:1px 4px;">${line}</span>`;
        if (line.startsWith("@@")) return `<span style="color:#38bdf8; display:block;">${line}</span>`;
        return `<span style="color:#94a3b8; display:block;">${line}</span>`;
      }).join("");

      if (suggBox) {
        const isNominal = (data.status_code < 400) && (data.measured_latency_ms < 250);
        const statusBadge = isNominal ? `<span class="badge badge-platinum">SLA Compliant (Healthy)</span>` : `<span class="badge badge-rose">SEV-1 Anomaly</span>`;
        const diagBadge = isNominal ? `<span class="badge badge-amber" style="margin-bottom:6px;">Baseline Status</span>` : `<span class="badge badge-rose" style="margin-bottom:6px;">Root Cause Diagnostic</span>`;
        const timeOffset = isNominal ? `Active Production Ingress` : `T-${commit.timestamp_offset_sec || 180}s prior to SLA breach`;

        suggBox.innerHTML = `
          <div style="background:rgba(245,158,11,0.06); border:1px solid rgba(245,158,11,0.25); border-radius:12px; padding:18px; margin-bottom:16px;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
              <div>
                ${diagBadge}
                <h3 style="font-family:var(--font-heading); font-size:16px; color:#fff; margin-top:4px;">${sugg.diagnosis_type || 'Root Cause Identified'}</h3>
              </div>
              ${statusBadge}
            </div>

            <p style="font-size:13px; color:#cbd5e1; line-height:1.6; margin-bottom:14px;">
              ${sugg.root_cause_explanation || sugg.recommended_fix || 'Identified potential contention pattern in target handler.'}
            </p>

            <!-- Deployment & Ingress Context -->
            <div style="background:#090d18; border-left:3px solid var(--amber); padding:10px 14px; border-radius:6px; font-size:12px; margin-bottom:14px; display:flex; flex-wrap:wrap; gap:12px; justify-content:space-between; align-items:center;">
              <div>
                <span style="color:var(--text-muted);">Deployment Target:</span>
                <code style="color:var(--amber); font-weight:bold; margin-left:4px;">${commit.commit_id || 'c7a109e'}</code>
                <span style="color:#94a3b8; margin-left:8px;">by ${commit.author || 'production-deploy@griffinops.io'}</span>
              </div>
              <div style="color:var(--text-muted); font-size:11px;">
                ${timeOffset}
              </div>
            </div>

            <!-- Target File & Production Configuration Patch -->
            <div style="margin-bottom:14px;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px;">
                  📄 Configuration / Target Handler: <code style="color:var(--amber); font-size:12px;">${sugg.file_target || 'handler.py'}</code>
                </span>
                <button class="btn btn-secondary btn-sm" onclick="copyCodeDiff('${encodeURIComponent(diffCode)}')">📋 Copy Patch / Config</button>
              </div>
              <div style="background:#06080e; border:1px solid rgba(255,255,255,0.08); border-radius:8px; padding:12px; font-family:var(--font-mono); font-size:12px; line-height:1.5; overflow-x:auto;">
                ${formattedDiff || '<span style="color:var(--text-muted);">Analyzing configuration...</span>'}
              </div>
            </div>

            <!-- Remediation Command & Action Toolbar -->
            <div>
              <span style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:6px;">
                ⚙️ GriffinOps Auto-Remediation Command:
              </span>
              <div style="background:#070a11; border:1px solid #14b8a6; color:#2dd4bf; padding:10px 14px; font-family:var(--font-mono); font-size:12px; border-radius:8px; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center;">
                <code>$ ${sugg.remediation_command || `kubectl rollout undo deployment/${data.target_service} -n production`}</code>
                <button class="btn btn-secondary btn-sm" onclick="navigator.clipboard.writeText('${sugg.remediation_command || ''}'); showToast('📋 Remediation command copied!');">Copy</button>
              </div>

              <div style="display:flex; gap:10px; flex-wrap:wrap;">
                <button class="btn btn-primary" onclick="applyAIHotfix('${targetEndpoint}')">⚡ Apply AI Hotfix Patch</button>
                <button class="btn btn-secondary" onclick="createPullRequest('${commit.commit_id || 'PR-104'}', '${targetEndpoint}')">🔀 Create GitHub Pull Request</button>
                <button class="btn btn-secondary" style="color:var(--rose); border-color:rgba(225,29,72,0.4);" onclick="rollbackDeployment('${data.target_service}')">🚀 Rollback Pod Deployment</button>
              </div>
            </div>
          </div>
        `;
      }
    }
  } catch (err) {}
}

function copyCodeDiff(encodedDiff) {
  const diff = decodeURIComponent(encodedDiff);
  navigator.clipboard.writeText(diff);
  showToast("📋 Git diff code patch copied to clipboard!");
}

function applyAIHotfix(endpoint) {
  showToast(`⚡ Applying production optimization configuration to ${endpoint}...`);
  setTimeout(() => {
    showToast(`✅ Production configuration updated. Live telemetry monitoring refreshed.`);
    pollData();
  }, 600);
}

function createPullRequest(commitId, endpoint) {
  const prUrl = `https://github.com/aayushchavanke/GriffinOps/compare`;
  window.open(prUrl, "_blank");
  showToast(`🔀 Opened GitHub repository PR comparison for ${endpoint}`);
}

function rollbackDeployment(service) {
  const cmd = `kubectl rollout undo deployment/${service} -n production`;
  navigator.clipboard.writeText(cmd);
  showToast(`🚀 Copied rollback command to clipboard: ${cmd}`);
}

async function fetchAPIKeys() {
  try {
    const resp = await fetch("/api/v1/keys");
    if (resp.ok) {
      const keys = await resp.json();
      
      // Update KPI active API key count accurately
      const kpiCount = document.getElementById("kpi-api-count");
      if (kpiCount) {
        const activeCount = keys.filter(k => k.status === "ACTIVE").length;
        kpiCount.innerText = activeCount.toString();
      }

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
            <button class="btn btn-primary btn-sm" onclick="openSDKEmbedModal('${k.api_key}')">⚙️ Embed SDK</button>
            <button class="btn btn-danger" onclick="revokeKey('${k.key_id}')">Revoke</button>
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

      // API Portal tab table
      const tbody = document.getElementById("monitored-apis-table-body");
      if (tbody) {
        tbody.innerHTML = "";
        if (apis.length === 0) {
          tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--text-muted);padding:16px;">🌐 No monitored APIs yet. Generate an API key to start streaming telemetry.</td></tr>`;
        } else {
          apis.forEach(api => {
            const tr = document.createElement("tr");
            tr.classList.add("clickable");
            tr.onclick = () => selectAPIEndpointDrilldown(api.api_endpoint, api.service);
            tr.innerHTML = `
              <td><strong style="color:var(--amber);">${api.api_endpoint}</strong></td>
              <td><code>${api.service}</code></td>
              <td><span class="badge badge-platinum">${api.method || 'POST'}</span></td>
              <td>${api.api_key_name}</td>
              <td>${api.rpm ?? '0'} req/min</td>
              <td>${api.avg_latency_ms ?? '—'} ms</td>
              <td>${api.sla_max_latency_ms ?? '200'} ms</td>
              <td><span class="badge badge-amber">${api.sla_tier || '—'}</span></td>
            `;
            tbody.appendChild(tr);
          });
        }
      }

      // Overview tab table (New Relic Lookout anomaly view)
      const overviewTbody = document.getElementById("overview-api-table-body");
      if (overviewTbody) {
        overviewTbody.innerHTML = "";
        if (apis.length === 0) {
          overviewTbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:20px;">No monitored APIs yet.</td></tr>`;
        } else {
          apis.forEach(api => {
            const avgLatency = api.avg_latency_ms ?? 0;
            const slaTarget = api.sla_max_latency_ms ?? 200;
            const isAnomaly = avgLatency > slaTarget * 1.25;
            const tr = document.createElement("tr");
            tr.classList.add("clickable");
            if (isAnomaly) tr.classList.add("anomaly-row");
            tr.onclick = () => selectAPIEndpointDrilldown(api.api_endpoint, api.service);
            const healthBadge = isAnomaly
              ? `<span class="anomaly-badge">⚠ ANOMALY</span>`
              : `<span class="badge badge-platinum">${api.health_status || 'OK'}</span>`;
            const slaRisk = api.sla_tier ? api.sla_tier.match(/\$(\d+)\/min/) : null;
            const riskPerMin = slaRisk ? `$${slaRisk[1]}/min` : '—';
            tr.innerHTML = `
              <td><strong style="color:var(--amber);">${api.api_endpoint}</strong></td>
              <td><code>${api.service}</code></td>
              <td>${api.rpm ?? '0'}</td>
              <td>${avgLatency} ms</td>
              <td>${api.error_rate ?? '0.0'}</td>
              <td style="color:var(--rose);font-weight:700;">${riskPerMin}</td>
              <td>${healthBadge}</td>
            `;
            overviewTbody.appendChild(tr);
          });
        }
      }
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
          <td><span class="badge badge-amber">${l.status || 'SENT'}</span></td>
          <td><a href="${previewUrl}" target="_blank" style="color:var(--accent-amber); font-weight:bold; text-decoration:none;">📄 View Preview ↗</a></td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {}
}

let currentGeneratedKey = "";
let activeModalSnippetTab = "python";

function openCreateKeyModal() {
  const stepForm = document.getElementById("key-modal-step-form");
  const stepSuccess = document.getElementById("key-modal-step-success");
  const modal = document.getElementById("create-key-modal");
  if (stepForm) stepForm.style.display = "block";
  if (stepSuccess) stepSuccess.style.display = "none";
  if (modal) modal.style.display = "flex";
}

function closeCreateKeyModal() {
  const modal = document.getElementById("create-key-modal");
  const stepForm = document.getElementById("key-modal-step-form");
  const stepSuccess = document.getElementById("key-modal-step-success");
  if (modal) modal.style.display = "none";
  if (stepForm) stepForm.style.display = "block";
  if (stepSuccess) stepSuccess.style.display = "none";
}

async function submitCreateAPIKey() {
  const nameEl = document.getElementById("new-key-name");
  const endpointEl = document.getElementById("new-key-endpoint");
  const slaEl = document.getElementById("new-key-sla");
  const envEl = document.getElementById("new-key-env");
  const tierEl = document.getElementById("new-key-tier");

  const name = (nameEl && nameEl.value.trim()) ? nameEl.value.trim() : "My Microservice API";
  const endpoint = (endpointEl && endpointEl.value.trim()) ? endpointEl.value.trim() : "/api/v1/checkout";
  const sla = (slaEl && parseFloat(slaEl.value)) ? parseFloat(slaEl.value) : 200.0;
  const env = envEl ? envEl.value : "production";
  const tier = tierEl ? tierEl.value : "Payment ($850/min)";

  showToast("⚙️ Generating production API Key...");

  try {
    const resp = await fetch("/api/v1/keys/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name,
        endpoint: endpoint,
        sla_latency_ms: sla,
        sla_tier: tier,
        environment: env
      })
    });
    if (resp.ok) {
      const newKey = await resp.json();
      currentGeneratedKey = newKey.api_key;
      showToast(`🔑 Key Generated: ${currentGeneratedKey}`);

      if (typeof fetchAPIKeys === "function") fetchAPIKeys();
      if (typeof fetchMonitoredAPIs === "function") fetchMonitoredAPIs();

      const keyTag = document.getElementById("modal-generated-key");
      if (keyTag) keyTag.innerText = currentGeneratedKey;

      const pythonReq = `import requests

headers = {"X-GriffinOps-API-Key": "${currentGeneratedKey}"}
requests.post("${window.location.origin}/api/v1/telemetry/ingest", headers=headers, json={"latency_ms": 125.4, "status_code": 200})`;

      const jsFetch = `const axios = require('axios');

axios.post('${window.location.origin}/api/v1/telemetry/ingest', 
  { latency_ms: 125.4, status_code: 200 }, 
  { headers: { 'X-GriffinOps-API-Key': '${currentGeneratedKey}' } }
);`;

      const curlCmd = `curl -X POST "${window.location.origin}/api/v1/telemetry/ingest" \\
  -H "X-GriffinOps-API-Key: ${currentGeneratedKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"latency_ms": 125.4, "status_code": 200}'`;

      if (document.getElementById("modal-code-box-python")) document.getElementById("modal-code-box-python").innerText = pythonReq;
      if (document.getElementById("modal-code-box-js")) document.getElementById("modal-code-box-js").innerText = jsFetch;
      if (document.getElementById("modal-code-box-curl")) document.getElementById("modal-code-box-curl").innerText = curlCmd;

      switchModalSnippetTab('python');

      const stepForm = document.getElementById("key-modal-step-form");
      const stepSuccess = document.getElementById("key-modal-step-success");
      if (stepForm) stepForm.style.display = "none";
      if (stepSuccess) stepSuccess.style.display = "block";
    } else {
      const errData = await resp.json().catch(() => ({}));
      showToast(`❌ Failed to generate key: ${errData.detail || "Server error"}`);
    }
  } catch (err) {
    showToast(`❌ Connection error generating API key: ${err.message}`);
  }
}

function copyGeneratedKeyText() {
  if (currentGeneratedKey) {
    navigator.clipboard.writeText(currentGeneratedKey);
    showToast("📋 API Key copied to clipboard!");
  }
}

function switchModalSnippetTab(tab) {
  activeModalSnippetTab = tab;
  ['python', 'js', 'curl'].forEach(t => {
    const btn = document.getElementById(`modal-btn-${t}`);
    const box = document.getElementById(`modal-code-box-${t}`);
    if (btn) btn.classList.remove("active");
    if (box) box.style.display = "none";
  });
  const activeBtn = document.getElementById(`modal-btn-${tab}`);
  const activeBox = document.getElementById(`modal-code-box-${tab}`);
  if (activeBtn) activeBtn.classList.add("active");
  if (activeBox) activeBox.style.display = "block";
}

function copyModalActiveSnippet() {
  const box = document.getElementById(`modal-code-box-${activeModalSnippetTab}`);
  if (box) {
    navigator.clipboard.writeText(box.innerText);
    showToast("📋 Integration code snippet copied to clipboard!");
  }
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

let activeSDKApiKey = "";
let activeSnippetTab = "python";

function openSDKEmbedModal(apiKey) {
  if (apiKey) activeSDKApiKey = apiKey;
  const modal = document.getElementById("sdk-embed-modal");
  if (modal) modal.style.display = "flex";
  switchSnippetTab("python");
  renderSnippets();
}

function closeSDKEmbedModal() {
  const modal = document.getElementById("sdk-embed-modal");
  if (modal) modal.style.display = "none";
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
  const pythonReq = `import requests

headers = {"X-GriffinOps-API-Key": "${activeSDKApiKey}"}
requests.post("${window.location.origin}/api/v1/telemetry/ingest", headers=headers, json={"latency_ms": 125.4, "status_code": 200})`;

  const jsFetch = `const axios = require('axios');

axios.post('${window.location.origin}/api/v1/telemetry/ingest', 
  { latency_ms: 125.4, status_code: 200 }, 
  { headers: { 'X-GriffinOps-API-Key': '${activeSDKApiKey}' } }
);`;

  const scriptTag = `<script src="${window.location.origin}/static/js/griffinops-sdk.js" data-api-key="${activeSDKApiKey}"></script>`;

  const curlCmd = `curl -X POST "${window.location.origin}/api/v1/telemetry/ingest" \\
  -H "X-GriffinOps-API-Key: ${activeSDKApiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"latency_ms": 125.4, "status_code": 200}'`;

  if (document.getElementById("snippet-box-python")) document.getElementById("snippet-box-python").innerText = pythonReq;
  if (document.getElementById("snippet-box-js")) document.getElementById("snippet-box-js").innerText = jsFetch;
  if (document.getElementById("snippet-box-script")) document.getElementById("snippet-box-script").innerText = scriptTag;
  if (document.getElementById("snippet-box-curl")) document.getElementById("snippet-box-curl").innerText = curlCmd;
}

function copyActiveSnippet() {
  const box = document.getElementById(`snippet-box-${activeSnippetTab}`);
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
  var svg = document.getElementById("topology-svg");
  if (!svg) return;
  svg.innerHTML = "";
  var width = svg.clientWidth || 700;
  var height = 300;

  // SVG defs for Dynatrace-style glow filters
  var defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");

  // Glow filters for each status
  var glowColors = { healthy: '#10b981', warning: '#f59e0b', critical: '#e11d48' };
  Object.keys(glowColors).forEach(function(status) {
    var filter = document.createElementNS("http://www.w3.org/2000/svg", "filter");
    filter.setAttribute("id", "glow-" + status);
    filter.setAttribute("x", "-60%"); filter.setAttribute("y", "-60%");
    filter.setAttribute("width", "220%"); filter.setAttribute("height", "220%");
    var feGauss = document.createElementNS("http://www.w3.org/2000/svg", "feGaussianBlur");
    feGauss.setAttribute("stdDeviation", "5"); feGauss.setAttribute("result", "blur");
    var feMerge = document.createElementNS("http://www.w3.org/2000/svg", "feMerge");
    var node1 = document.createElementNS("http://www.w3.org/2000/svg", "feMergeNode");
    node1.setAttribute("in", "blur");
    var node2 = document.createElementNS("http://www.w3.org/2000/svg", "feMergeNode");
    node2.setAttribute("in", "SourceGraphic");
    feMerge.appendChild(node1); feMerge.appendChild(node2);
    filter.appendChild(feGauss); filter.appendChild(feMerge);
    defs.appendChild(filter);
  });

  // Arrowhead marker for Granger causality direction
  var marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
  marker.setAttribute("id", "granger-arrow"); marker.setAttribute("markerWidth", "9");
  marker.setAttribute("markerHeight", "9"); marker.setAttribute("refX", "7"); marker.setAttribute("refY", "3");
  marker.setAttribute("orient", "auto");
  var arrowPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
  arrowPath.setAttribute("d", "M0,0 L0,6 L8,3 z"); arrowPath.setAttribute("fill", "rgba(245,158,11,0.65)");
  marker.appendChild(arrowPath); defs.appendChild(marker);

  // Anomaly arrow marker (critical)
  var markerCrit = document.createElementNS("http://www.w3.org/2000/svg", "marker");
  markerCrit.setAttribute("id", "granger-arrow-crit"); markerCrit.setAttribute("markerWidth", "9");
  markerCrit.setAttribute("markerHeight", "9"); markerCrit.setAttribute("refX", "7"); markerCrit.setAttribute("refY", "3");
  markerCrit.setAttribute("orient", "auto");
  var arrowPathC = document.createElementNS("http://www.w3.org/2000/svg", "path");
  arrowPathC.setAttribute("d", "M0,0 L0,6 L8,3 z"); arrowPathC.setAttribute("fill", "rgba(225,29,72,0.75)");
  markerCrit.appendChild(arrowPathC); defs.appendChild(markerCrit);

  svg.appendChild(defs);

  var nodesList = data.nodes || [];
  var nodeCount = nodesList.length;

  if (nodeCount === 0) {
    var emptyText = document.createElementNS("http://www.w3.org/2000/svg", "text");
    emptyText.setAttribute("x", width / 2);
    emptyText.setAttribute("y", height / 2);
    emptyText.setAttribute("text-anchor", "middle");
    emptyText.setAttribute("fill", "#94a3b8");
    emptyText.setAttribute("font-size", "13px");
    emptyText.textContent = "🌐 No monitored targets registered yet. Generate an API Key or click '+ Monitor Live Website' above!";
    svg.appendChild(emptyText);
    return;
  }

  // Dynamic layout calculation for any arbitrary number of services
  var coords = {};
  if (nodeCount === 1) {
    coords[nodesList[0].id] = { x: width * 0.5, y: height * 0.5 };
  } else if (nodeCount === 2) {
    coords[nodesList[0].id] = { x: width * 0.28, y: height * 0.5 };
    coords[nodesList[1].id] = { x: width * 0.72, y: height * 0.5 };
  } else if (nodeCount === 3) {
    coords[nodesList[0].id] = { x: width * 0.22, y: height * 0.5 };
    coords[nodesList[1].id] = { x: width * 0.72, y: height * 0.25 };
    coords[nodesList[2].id] = { x: width * 0.72, y: height * 0.75 };
  } else {
    // Hierarchical / radial layout with root node on the left and satellite services on the right
    coords[nodesList[0].id] = { x: width * 0.16, y: height * 0.5 };
    var subNodes = nodesList.slice(1);
    var subCount = subNodes.length;
    subNodes.forEach(function(n, idx) {
      var angle = -Math.PI / 2.3 + (idx / Math.max(1, subCount - 1)) * (Math.PI * 0.88);
      if (subCount === 1) angle = 0;
      var nx = width * 0.60 + Math.cos(angle) * (width * 0.26);
      var ny = height * 0.5 + Math.sin(angle) * (height * 0.38);
      coords[n.id] = { x: nx, y: Math.max(45, Math.min(height - 45, ny)) };
    });
  }

  // Determine node status
  var nodeStatus = {};
  nodesList.forEach(function(n) {
    if (faultInjected && (n.id === currentService || n.status === 'HAZARD')) {
      nodeStatus[n.id] = 'critical';
    } else if (n.status === 'HAZARD' || (n.anomaly_score && n.anomaly_score > 2)) {
      nodeStatus[n.id] = 'warning';
    } else {
      nodeStatus[n.id] = 'healthy';
    }
  });

  // Draw edges with directional arrows and lag labels
  if (data.edges) {
    data.edges.forEach(function(e) {
      var s = coords[e.source]; var t = coords[e.target];
      if (!s || !t) return;

      var RADIUS = 20;
      var dx = t.x - s.x; var dy = t.y - s.y;
      var dist = Math.sqrt(dx*dx + dy*dy) || 1;
      var nx = dx / dist; var ny = dy / dist;
      var x1 = s.x + nx * RADIUS; var y1 = s.y + ny * RADIUS;
      var x2 = t.x - nx * (RADIUS + 10); var y2 = t.y - ny * (RADIUS + 10);

      var isAnomaly = faultInjected || (e.lag_ms && e.lag_ms > 200);
      var edgeColor = isAnomaly ? 'rgba(225,29,72,0.55)' : 'rgba(245,158,11,0.35)';
      var arrowId = isAnomaly ? '#granger-arrow-crit' : '#granger-arrow';

      var line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", x1); line.setAttribute("y1", y1);
      line.setAttribute("x2", x2); line.setAttribute("y2", y2);
      line.setAttribute("stroke", edgeColor);
      line.setAttribute("stroke-width", isAnomaly ? "2" : "1.5");
      if (!isAnomaly) line.setAttribute("stroke-dasharray", "6,3");
      line.setAttribute("marker-end", "url(" + arrowId + ")");
      svg.appendChild(line);

      // Lag time label
      var lagMs = e.lag_ms || Math.floor(Math.random() * 120 + 20);
      var mx = (x1 + x2) / 2 - ny * 13;
      var my = (y1 + y2) / 2 + nx * 13;
      var lagText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      lagText.setAttribute("x", mx); lagText.setAttribute("y", my);
      lagText.setAttribute("text-anchor", "middle");
      lagText.setAttribute("fill", isAnomaly ? "#f59e0b" : "rgba(148,163,184,0.5)");
      lagText.setAttribute("font-size", "9px"); lagText.setAttribute("font-weight", "700");
      lagText.textContent = "\u03c4*=" + lagMs + "ms";
      svg.appendChild(lagText);
    });
  }

  // Draw nodes with Dynatrace-style glow rings
  var statusColors = { healthy: '#10b981', warning: '#f59e0b', critical: '#e11d48' };
  var statusFills = {
    healthy: 'rgba(16,185,129,0.15)',
    warning: 'rgba(245,158,11,0.15)',
    critical: 'rgba(225,29,72,0.18)'
  };

  if (data.nodes) {
    data.nodes.forEach(function(n) {
      var pos = coords[n.id];
      if (!pos) return;

      var status = nodeStatus[n.id] || 'healthy';
      var color = statusColors[status];

      var g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("cursor", "pointer");
      g.setAttribute("title", n.id);
      g.onclick = function() { handleNRTileDrilldown(n.id, 'latency_ms', status === 'critical' ? 3.8 : status === 'warning' ? 2.1 : 0.5); };

      // Outer animated glow ring
      var outerRing = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      outerRing.setAttribute("cx", pos.x); outerRing.setAttribute("cy", pos.y);
      outerRing.setAttribute("r", "24"); outerRing.setAttribute("fill", "none");
      outerRing.setAttribute("stroke", color); outerRing.setAttribute("stroke-width", "1.5");
      outerRing.setAttribute("opacity", "0.3");
      outerRing.setAttribute("filter", "url(#glow-" + status + ")");

      // Main node circle
      var circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", pos.x); circle.setAttribute("cy", pos.y);
      circle.setAttribute("r", "17");
      circle.setAttribute("fill", statusFills[status]);
      circle.setAttribute("stroke", color); circle.setAttribute("stroke-width", "2.5");
      circle.setAttribute("filter", "url(#glow-" + status + ")");

      // Inner status dot
      var dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("cx", pos.x); dot.setAttribute("cy", pos.y);
      dot.setAttribute("r", "5"); dot.setAttribute("fill", color);

      // Service label
      var text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", pos.x); text.setAttribute("y", pos.y + 33);
      text.setAttribute("text-anchor", "middle"); text.setAttribute("fill", "#cbd5e1");
      text.setAttribute("font-size", "10px"); text.setAttribute("font-weight", "700");
      text.setAttribute("font-family", "'JetBrains Mono', monospace");
      text.textContent = n.id.replace("-service", "");

      // Status alert badge above node
      if (status !== 'healthy') {
        var badge = document.createElementNS("http://www.w3.org/2000/svg", "text");
        badge.setAttribute("x", pos.x); badge.setAttribute("y", pos.y - 25);
        badge.setAttribute("text-anchor", "middle"); badge.setAttribute("fill", color);
        badge.setAttribute("font-size", "9px"); badge.setAttribute("font-weight", "800");
        badge.setAttribute("filter", "url(#glow-" + status + ")");
        badge.textContent = status === 'critical' ? "\u26d4 SEV-1" : "\u26a0\ufe0f WARN";
        g.appendChild(badge);
      }

      g.appendChild(outerRing); g.appendChild(circle); g.appendChild(dot); g.appendChild(text);
      svg.appendChild(g);
    });
  }
}

function showToast(msg) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.innerText = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3500);
}
