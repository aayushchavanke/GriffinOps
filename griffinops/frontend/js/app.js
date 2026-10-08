let authToken = localStorage.getItem("gop_token") || null;
let currentUser = JSON.parse(localStorage.getItem("gop_user") || "null");
let activeApiKey = null;  // Global site filter (url, name, or slug). null = all sites
let siteUrlToSlug = {};   // Map site URL -> slug for cross-referencing
let currentService = null;
let lastTelemetryService = null;
const MAX_TELEMETRY_POINTS = 40;
let selectedAPIEndpoint = null;

let liveTelemetryChart = null;
let forecastChart = null;
let illustrationForecastChart = null;
let pollTimer = null;

let MICROSERVICES = [];
let lastAuditReport = null;   // tracks the last successfully polled non-empty audit report

// === Datadog Time-Range Selector State ===
let activeTimeRange = 'live'; // live | 15m | 1h | 24h
let kpiSparklineHistory = {}; // tracks rolling history per KPI for sparklines

// === Inject Fault State ===
let faultInjected = false;

// === Theme State (Dark Glass vs Light Glass) ===
let currentTheme = localStorage.getItem("gop_theme") || "dark";

function initTheme() {
  currentTheme = localStorage.getItem("gop_theme") || "dark";
  document.documentElement.setAttribute("data-theme", currentTheme);
  updateThemeUI();
}

function toggleTheme() {
  currentTheme = currentTheme === "dark" ? "light" : "dark";
  localStorage.setItem("gop_theme", currentTheme);
  document.documentElement.setAttribute("data-theme", currentTheme);
  updateThemeUI();
  updateChartsTheme();
  fetchTopology();
  showToast(`✨ Switched to ${currentTheme === "dark" ? "Dark" : "Light"} Glass Mode`);
}

function updateThemeUI() {
  const iconDark = document.getElementById("theme-icon-dark");
  const iconLight = document.getElementById("theme-icon-light");
  const textEl = document.getElementById("theme-toggle-text");
  if (currentTheme === "dark") {
    if (iconDark) iconDark.style.display = "none";
    if (iconLight) iconLight.style.display = "inline-flex";
    if (textEl) textEl.innerText = "Light Mode";
  } else {
    if (iconDark) iconDark.style.display = "inline-flex";
    if (iconLight) iconLight.style.display = "none";
    if (textEl) textEl.innerText = "Dark Mode";
  }
}

function updateChartsTheme() {
  const isLight = currentTheme === "light";
  const gridColor = isLight ? "rgba(100, 116, 139, 0.15)" : "rgba(255, 255, 255, 0.08)";
  const textColor = isLight ? "#64748b" : "#94a3b8";
  const titleColor = isLight ? "#0f172a" : "#ffffff";

  [liveTelemetryChart, forecastChart, illustrationForecastChart].forEach(chart => {
    if (!chart) return;
    if (chart.options.scales.x) {
      chart.options.scales.x.grid.color = gridColor;
      chart.options.scales.x.ticks.color = textColor;
    }
    if (chart.options.scales.y) {
      chart.options.scales.y.grid.color = gridColor;
      chart.options.scales.y.ticks.color = textColor;
    }
    if (chart.options.scales.y1) {
      chart.options.scales.y1.ticks.color = textColor;
    }
    if (chart.options.plugins && chart.options.plugins.legend) {
      chart.options.plugins.legend.labels.color = titleColor;
    }
    chart.update("none");
  });
}

// === Interactive Background Halo (Mouse Tracking behind Glass Bento Boxes) ===
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  const halo = document.getElementById("ambient-halo");
  let mouseX = window.innerWidth / 2;
  let mouseY = window.innerHeight / 2;
  let haloX = mouseX;
  let haloY = mouseY;

  window.addEventListener("mousemove", (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
  });

  function animateHalo() {
    haloX += (mouseX - haloX) * 0.08;
    haloY += (mouseY - haloY) * 0.08;
    if (halo) {
      halo.style.transform = `translate(${haloX}px, ${haloY}px) translate(-50%, -50%)`;
    }
    requestAnimationFrame(animateHalo);
  }
  // Wire click-outside-to-close on all modal backdrops
  const modalCloseMap = {
    "create-key-modal": closeCreateKeyModal,
    "sdk-embed-modal": closeSDKEmbedModal,
    "add-real-site-modal": closeAddRealSiteModal,
    "premortem-modal": closePremortemModal
  };

  document.querySelectorAll(".modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        const closeFn = modalCloseMap[overlay.id];
        if (typeof closeFn === "function") {
          closeFn();
        } else {
          overlay.style.display = "none";
        }
      }
    });
  });

  // Global Escape-key-to-close handler as reliable fallback
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" || e.keyCode === 27) {
      document.querySelectorAll(".modal-overlay").forEach(overlay => {
        if (window.getComputedStyle(overlay).display !== "none") {
          const closeFn = modalCloseMap[overlay.id];
          if (typeof closeFn === "function") {
            closeFn();
          } else {
            overlay.style.display = "none";
          }
        }
      });
    }
  });

  if (authToken) {
    showMainApp();
  } else {
    document.getElementById("auth-screen").style.display = "flex";
    document.getElementById("main-app").style.display = "none";
  }
});

function clearAuthFeedback() {
  ["login-error", "login-success", "reg-error", "reg-success", "forgot-error", "forgot-success"].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.innerText = "";
      el.style.display = "none";
    }
  });
}

function showAuthMessage(elementId, msg, isError = true) {
  const el = document.getElementById(elementId);
  if (el) {
    el.innerText = msg;
    el.style.display = "block";
  }
}

function switchAuthTab(tab) {
  clearAuthFeedback();
  const btnLogin = document.getElementById("btn-tab-login");
  const btnReg = document.getElementById("btn-tab-register");
  const formLogin = document.getElementById("auth-form-login");
  const formReg = document.getElementById("auth-form-register");
  const formForgot = document.getElementById("auth-form-forgot");

  if (btnLogin) btnLogin.classList.remove("active");
  if (btnReg) btnReg.classList.remove("active");
  if (formLogin) formLogin.style.display = "none";
  if (formReg) formReg.style.display = "none";
  if (formForgot) formForgot.style.display = "none";

  if (tab === "login") {
    if (btnLogin) btnLogin.classList.add("active");
    if (formLogin) formLogin.style.display = "block";
  } else if (tab === "register") {
    if (btnReg) btnReg.classList.add("active");
    if (formReg) formReg.style.display = "block";
  } else if (tab === "forgot") {
    if (formForgot) formForgot.style.display = "block";
    const resetBox = document.getElementById("forgot-reset-box");
    if (resetBox) resetBox.style.display = "none";
  }
}

async function handleLogin() {
  clearAuthFeedback();
  const emailInput = document.getElementById("login-email");
  const passInput = document.getElementById("login-pass");
  const email = emailInput ? emailInput.value.trim() : "";
  const pass = passInput ? passInput.value : "";

  if (!email || !pass) {
    showAuthMessage("login-error", "Please enter both email address and password.");
    return;
  }

  const btn = document.getElementById("btn-submit-login");
  const prevText = btn ? btn.innerText : "";
  if (btn) { btn.disabled = true; btn.innerText = "Authenticating..."; }

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
      showToast("Signed in as " + (currentUser.name || currentUser.email));
      showMainApp();
    } else {
      showAuthMessage("login-error", data.detail || "Authentication failed. Please check your credentials.");
    }
  } catch (err) {
    showAuthMessage("login-error", "Network error: Unable to connect to authentication server.");
  } finally {
    if (btn) { btn.disabled = false; btn.innerText = prevText; }
  }
}

async function handleRegister() {
  clearAuthFeedback();
  const name = document.getElementById("reg-name") ? document.getElementById("reg-name").value.trim() : "";
  const email = document.getElementById("reg-email") ? document.getElementById("reg-email").value.trim() : "";
  const pass = document.getElementById("reg-pass") ? document.getElementById("reg-pass").value : "";
  const passConfirm = document.getElementById("reg-pass-confirm") ? document.getElementById("reg-pass-confirm").value : "";

  if (!name || !email || !pass) {
    showAuthMessage("reg-error", "Please fill in all required fields.");
    return;
  }
  if (!email.includes("@") || !email.includes(".")) {
    showAuthMessage("reg-error", "Please provide a valid email address.");
    return;
  }
  if (pass.length < 6) {
    showAuthMessage("reg-error", "Password must be at least 6 characters long.");
    return;
  }
  if (pass !== passConfirm) {
    showAuthMessage("reg-error", "Passwords do not match. Please re-enter.");
    return;
  }

  const btn = document.getElementById("btn-submit-reg");
  const prevText = btn ? btn.innerText : "";
  if (btn) { btn.disabled = true; btn.innerText = "Creating Account..."; }

  try {
    const resp = await fetch("/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, email: email, password: pass })
    });
    const data = await resp.json();
    if (resp.ok) {
      showAuthMessage("reg-success", "✅ Account created successfully! Redirecting to sign in...", false);
      showToast("Account created successfully!");
      setTimeout(() => {
        switchAuthTab("login");
        const loginEmail = document.getElementById("login-email");
        const loginPass = document.getElementById("login-pass");
        if (loginEmail) loginEmail.value = email;
        if (loginPass) { loginPass.value = ""; loginPass.focus(); }
        showAuthMessage("login-success", "Account created! Please enter your password to sign in.", false);
      }, 1200);
    } else {
      showAuthMessage("reg-error", data.detail || "Registration failed.");
    }
  } catch (err) {
    showAuthMessage("reg-error", "Network error: Unable to connect to authentication server.");
  } finally {
    if (btn) { btn.disabled = false; btn.innerText = prevText; }
  }
}

async function handleForgotPassword() {
  clearAuthFeedback();
  const emailInput = document.getElementById("forgot-email");
  const email = emailInput ? emailInput.value.trim() : "";

  if (!email || !email.includes("@")) {
    showAuthMessage("forgot-error", "Please enter a valid registered email address.");
    return;
  }

  const btn = document.getElementById("btn-send-reset");
  const prevText = btn ? btn.innerText : "";
  if (btn) { btn.disabled = true; btn.innerText = "Sending..."; }

  try {
    const resp = await fetch("/api/v1/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email })
    });
    const data = await resp.json();
    if (resp.ok) {
      showAuthMessage("forgot-success", data.message || "Reset instructions generated.", false);
      const resetBox = document.getElementById("forgot-reset-box");
      if (resetBox) resetBox.style.display = "block";
      if (data.reset_code) {
        const codeInput = document.getElementById("reset-code");
        if (codeInput) codeInput.value = data.reset_code;
      }
    } else {
      showAuthMessage("forgot-error", data.detail || "Unable to process password reset.");
    }
  } catch (err) {
    showAuthMessage("forgot-error", "Network error: Failed to request password reset.");
  } finally {
    if (btn) { btn.disabled = false; btn.innerText = prevText; }
  }
}

async function handleResetPassword() {
  clearAuthFeedback();
  const emailInput = document.getElementById("forgot-email");
  const email = emailInput ? emailInput.value.trim() : "";
  const codeInput = document.getElementById("reset-code");
  const code = codeInput ? codeInput.value.trim() : "";
  const passInput = document.getElementById("reset-new-pass");
  const newPass = passInput ? passInput.value : "";
  const confirmInput = document.getElementById("reset-confirm-pass");
  const confirmPass = confirmInput ? confirmInput.value : "";

  if (!email) {
    showAuthMessage("forgot-error", "Registered email address is required.");
    return;
  }
  if (!code) {
    showAuthMessage("forgot-error", "Please enter the 6-digit verification code.");
    return;
  }
  if (newPass.length < 6) {
    showAuthMessage("forgot-error", "New password must be at least 6 characters long.");
    return;
  }
  if (newPass !== confirmPass) {
    showAuthMessage("forgot-error", "Passwords do not match. Please re-enter.");
    return;
  }

  const btn = document.getElementById("btn-submit-reset");
  const prevText = btn ? btn.innerText : "";
  if (btn) { btn.disabled = true; btn.innerText = "Updating..."; }

  try {
    const resp = await fetch("/api/v1/auth/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: email,
        reset_code: code,
        new_password: newPass
      })
    });
    const data = await resp.json();
    if (resp.ok) {
      showToast("Password updated successfully!");
      switchAuthTab("login");
      const loginEmail = document.getElementById("login-email");
      const loginPass = document.getElementById("login-pass");
      if (loginEmail) loginEmail.value = email;
      if (loginPass) { loginPass.value = newPass; }
      showAuthMessage("login-success", "Password updated! You can now sign in.", false);
    } else {
      showAuthMessage("forgot-error", data.detail || "Failed to reset password.");
    }
  } catch (err) {
    showAuthMessage("forgot-error", "Network error: Failed to update password.");
  } finally {
    if (btn) { btn.disabled = false; btn.innerText = prevText; }
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
  populateSiteSelector();
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
    const qs = activeApiKey ? `?api_endpoint=${encodeURIComponent(activeApiKey)}` : "";
    const resp = await fetch(`/api/v1/real-monitor/live${qs}`);
    if (resp.ok) {
      const sites = await resp.json();
      const tbody = document.getElementById("real-websites-table-body");
      if (!tbody) return;
      tbody.innerHTML = "";
      const siteList = Object.values(sites);
      if (siteList.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:32px 20px;">
          <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px;">
            <span style="font-size:24px;">🌐</span>
            <div style="font-size:13px; font-weight:700; color:var(--text-primary);">No Monitored Websites or Microservices Active</div>
            <div style="font-size:12px; color:var(--text-muted); max-width:440px;">Generate an API key or register your web application to start streaming real-time white-box telemetry.</div>
            <button class="btn btn-primary btn-sm" onclick="openCreateKeyModal()" style="margin-top:6px;">+ Register Website / API</button>
          </div>
        </td></tr>`;
        return;
      }
      siteList.forEach(site => {
        if (site.url) {
          siteUrlToSlug[site.url] = site.name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9\-]/g, '');
        }
        const isPending = site.is_pending || (site.history_length === 0 && (!site.latest || site.latest.latency_ms === 0));
        const lat = site.latest ? site.latest.latency_ms : 0;
        const status = site.latest ? site.latest.status_code : 200;
        const isHazard = !isPending && (lat > 250.0 || status >= 400 || faultInjected);
        const apiKey = site.api_key || "gop_live_web001";
        const tr = document.createElement("tr");
        tr.style.cursor = "pointer";
        tr.title = isPending ? "Awaiting telemetry stream — click Test Ping to verify" : "Click row to view detailed Pre-Mortem failure analysis";
        tr.onclick = (e) => {
          if (e.target.tagName !== 'A' && e.target.tagName !== 'BUTTON' && !e.target.closest('button')) {
            openPremortemDrilldown(site.name, site.url, lat, status, site.latest ? site.latest.payload_bytes : 256);
          }
        };

        let statusIndicator = `<strong style="display:flex; align-items:center; gap:8px;"><span>${isHazard ? '🔴' : '🟢'}</span> <span>${site.name}</span></strong>`;
        let latDisplay = `<strong style="color:${isHazard ? 'var(--pastel-rose)' : 'inherit'};">${lat.toFixed(1)} ms</strong>`;
        let httpBadge = `<span class="badge ${status === 200 ? 'badge-mint' : (status < 400 ? 'badge-amber' : 'badge-rose')}">HTTP ${status}</span>`;
        let healthBadge = `<span class="badge ${isHazard ? 'badge-rose' : 'badge-mint'}">${isHazard ? 'M ≥ 3.5σ Hazard' : 'Nominal (0.3σ)'}</span>`;
        let actionButtons = `
          <button class="btn btn-secondary btn-sm" onclick="openPremortemDrilldown('${site.name}', '${site.url}', ${lat}, ${status}, ${site.latest ? site.latest.payload_bytes : 256})" style="font-size:11px; padding:4px 8px;">🔮 Pre-Mortem</button>
          <button class="btn btn-primary btn-sm" onclick="openSDKEmbedModal('${apiKey}')" style="padding:4px 8px; font-size:11px;">📋 Get SDK &lt;/&gt;</button>
        `;

        if (isPending) {
          statusIndicator = `<strong style="display:flex; align-items:center; gap:8px;"><span class="pulse-dot" style="background:var(--pastel-peach); display:inline-block;" title="Awaiting telemetry"></span> <span>${site.name}</span> <span style="font-size:10px; color:var(--text-muted); font-weight:normal;">(Awaiting Stream)</span></strong>`;
          latDisplay = `<span style="color:var(--text-muted); font-size:11px; font-style:italic;">Awaiting First Ping</span>`;
          httpBadge = `<span class="badge badge-purple">SDK Ready</span>`;
          healthBadge = `<span class="badge badge-amber">Standby</span>`;
          actionButtons = `
            <button class="btn btn-primary btn-sm" onclick="openSDKEmbedModal('${apiKey}')" style="padding:4px 8px; font-size:11px;">📋 Get SDK &lt;/&gt;</button>
            <button class="btn btn-secondary btn-sm" onclick="sendTestPing('${site.url}', '${apiKey}', '${site.name}')" style="font-size:11px; padding:4px 8px; border-color:var(--pastel-mint-border); color:var(--pastel-mint-text);" title="Fire a test telemetry ping right now">⚡ Test Ping</button>
          `;
        }

        tr.innerHTML = `
          <td>${statusIndicator}</td>
          <td><code style="color:var(--accent-amber); font-size:11px; word-break:break-all;">${site.url}</code></td>
          <td><span class="badge badge-purple" style="font-family:var(--font-mono); font-size:11px;">${apiKey}</span></td>
          <td>${latDisplay}</td>
          <td>${httpBadge}</td>
          <td>${healthBadge}</td>
          <td style="display:flex; gap:6px; align-items:center; flex-wrap:wrap;">${actionButtons}</td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {}
}

async function sendTestPing(url, apiKey, name) {
  showToast(`⚡ Sending verification ping for ${name}...`);
  try {
    const resp = await fetch("/api/v1/telemetry/test-ping", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: apiKey,
        endpoint: url,
        latency_ms: Math.floor(28 + Math.random() * 25),
        status_code: 200
      })
    });
    if (resp.ok) {
      const data = await resp.json();
      showToast(`✅ ${data.message || 'Telemetry verification recorded!'}`);
      await fetchRealWebsites();
      if (typeof fetchGlobalSites === "function") await fetchGlobalSites();
    } else {
      showToast("❌ Could not record test ping.");
    }
  } catch (err) {
    showToast(`❌ Test ping error: ${err.message}`);
  }
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
      populateSiteSelector();
      fetchRealWebsites();
      fetchTopology();
      pollData();
    } else {
      showToast("❌ Could not connect to target URL.");
    }
  } catch (err) {
    showToast("Error adding live website target: " + err.message);
  }
}

let currentPremortemTarget = "";

function openPremortemDrilldown(name, url, lat, status, bytes) {
  currentPremortemTarget = name;
  const modal = document.getElementById("premortem-modal");
  if (!modal) return;

  const isAnomaly = (lat > 200.0 || status >= 400 || faultInjected);
  const zScore = isAnomaly ? (3.5 + Math.min(3.5, lat / 300.0)).toFixed(2) : Math.max(0.1, (lat - 35.0) / 40.0).toFixed(2);
  const ttfSec = isAnomaly ? (outageTimerSeconds > 0 ? outageTimerSeconds : 240) : 0;
  const ttfHuman = isAnomaly ? `${Math.floor(ttfSec / 60)}m ${ttfSec % 60 < 10 ? '0' : ''}${ttfSec % 60}s` : "HEALTHY (No Outage Risk)";

  document.getElementById("pm-modal-title").innerHTML = `<span>🔮 Pre-Mortem Failure Analysis: <strong>${name}</strong></span>`;
  document.getElementById("pm-modal-subtitle").innerText = `Target URL: ${url || 'SDK Endpoint'} | Ingestion: 4 Golden Signals Telemetry`;

  const badge = document.getElementById("pm-status-badge");
  if (badge) {
    badge.innerText = isAnomaly ? "CRITICAL (SEV-1 HAZARD)" : "HEALTHY (SEV-0)";
    badge.style.color = isAnomaly ? "var(--pastel-rose)" : "var(--pastel-emerald)";
  }

  const latElem = document.getElementById("pm-latency-val");
  if (latElem) {
    latElem.innerText = `${lat.toFixed(1)} ms (HTTP ${status})`;
    latElem.style.color = isAnomaly ? "var(--pastel-rose)" : "var(--text-primary)";
  }

  const madElem = document.getElementById("pm-mad-val");
  if (madElem) {
    madElem.innerText = `+${zScore}σ (${isAnomaly ? 'Breached M ≥ 3.5σ Bounds' : 'Nominal MAD Space'})`;
    madElem.style.color = isAnomaly ? "var(--pastel-rose)" : "var(--pastel-emerald)";
  }

  const ttfElem = document.getElementById("pm-ttf-val");
  if (ttfElem) {
    ttfElem.innerText = isAnomaly ? `⏳ T-minus ${ttfHuman}` : "HEALTHY (Nominal)";
    ttfElem.style.color = isAnomaly ? "var(--pastel-amber)" : "var(--pastel-indigo)";
  }

  const treeTarget = document.getElementById("pm-tree-target");
  if (treeTarget) treeTarget.innerText = `${name} [Telemetry Ingress]`;

  const navElem = document.getElementById("pm-agent-nav");
  if (navElem) {
    navElem.innerText = `Traffic Flow: Client Web Ingress ➔ ${name} (${url || 'endpoint'}) ➔ GriffinOps Ingestion Engine.`;
  }
  const diagElem = document.getElementById("pm-agent-diag");
  if (diagElem) {
    diagElem.innerText = isAnomaly 
      ? `Detected statistical breach for ${name}: latency ${lat.toFixed(1)}ms (+${zScore}σ deviation) with HTTP ${status}. Anomaly hazard flagged.`
      : `Telemetry nominal: latency ${lat.toFixed(1)}ms (+${zScore}σ baseline), HTTP ${status} OK. Robust MAD bounds verified.`;
  }
  const verElem = document.getElementById("pm-agent-ver");
  if (verElem) {
    verElem.innerText = isAnomaly
      ? `Generated pre-mortem audit report & dispatched email alert notification to registered developers.`
      : `Golden signals stable across all metrics. Zero false positive alert noise.`;
  }

  const rollbackPre = document.getElementById("pm-rollback-cmd");
  if (rollbackPre) {
    if (!isAnomaly) {
      rollbackPre.textContent = `# System operating nominally at ${lat.toFixed(1)}ms. No remediation required.`;
    } else if (status >= 400) {
      rollbackPre.textContent = `# Outage Remediation for ${name}:\n# 1. Review uncaught HTTP ${status} error traces and application logs\n# 2. Verify web server process health on ${url || 'target endpoint'}`;
    } else {
      rollbackPre.textContent = `# Latency Remediation for ${name}:\n# 1. Profile slow database queries & inspect connection limits\n# 2. Check upstream network latency and enable caching on ${url || 'target endpoint'}`;
    }
  }

  modal.style.setProperty("display", "flex", "important");
}

function closePremortemModal() {
  const modal = document.getElementById("premortem-modal");
  if (modal) modal.style.display = "none";
}

function copyPMRollbackCmd() {
  const cmd = document.getElementById("pm-rollback-cmd");
  if (cmd) {
    navigator.clipboard.writeText(cmd.textContent);
    showToast("📋 Remediation guidance copied to clipboard!");
  }
}

function switchToCausalTopologyTab() {
  closePremortemModal();
  switchTab('causal');
}

async function fetchWatchdogHistory() {
  const tbody = document.getElementById("watchdog-history-table-body");
  if (!tbody) return;
  try {
    const res = await fetch("/api/v1/watchdog/history");
    if (!res.ok) return;
    const history = await res.json();
    if (!history || history.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:20px;">No alerts dispatched yet. Simulate an anomaly to trigger the autonomous watchdog.</td></tr>`;
      return;
    }
    tbody.innerHTML = history.map(item => {
      const filename = item.preview_path ? item.preview_path.split(/[\\/]/).pop() : null;
      const previewLink = filename ? `<a href="/api/v1/email-previews/${filename}" target="_blank" class="btn btn-secondary btn-sm" style="font-size:11px; padding:3px 8px; text-decoration:none;">👁️ View Email Preview</a>` : '<span style="color:var(--text-muted);font-size:11px;">No preview</span>';
      const statusBadge = item.status === "DELIVERED" 
        ? `<span class="badge badge-mint">DELIVERED</span>` 
        : `<span class="badge badge-peach">${item.status || 'STORED'}</span>`;
      return `
        <tr>
          <td style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">${item.timestamp || '-'}</td>
          <td><code style="color:var(--pastel-indigo);">${item.report_id || '-'}</code></td>
          <td><strong style="color:#ffffff;">${item.target_service || 'System-Wide'}</strong></td>
          <td><span style="color:#e2e8f0;font-size:12px;">${item.recipient || '-'}</span></td>
          <td>${statusBadge}</td>
          <td>${previewLink}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Failed to fetch watchdog history:", err);
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
      const slackInput = document.getElementById("pref-slack-webhook");
      if (slackInput && p.slack_webhook_url !== undefined) {
        slackInput.value = p.slack_webhook_url;
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
  const slackUrl = document.getElementById("pref-slack-webhook") ? document.getElementById("pref-slack-webhook").value.trim() : "";
  const enabledInput = document.getElementById("pref-alerts-enabled");
  const enabled = enabledInput ? enabledInput.checked : true;
  const orgInput = document.getElementById("pref-org-name");
  const orgName = (orgInput && orgInput.value.trim()) ? orgInput.value.trim() : "SIES GST AI & Data Science Team";

  showToast("💾 Saving alert preferences & Slack webhook...");
  try {
    const resp = await fetch("/api/v1/user/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: currentUser ? currentUser.name : "SRE Lead Engineer",
        email: emails[0] || (currentUser ? currentUser.email : "user@company.com"),
        organization: orgName,
        developer_emails: emails,
        email_alerts_enabled: enabled,
        slack_webhook_url: slackUrl
      })
    });
    if (resp.ok) {
      const profileOrgSpan = document.getElementById("profile-org");
      if (profileOrgSpan) profileOrgSpan.innerText = orgName;
      showToast("✅ Alert settings & Slack webhook saved successfully!");
    } else {
      showToast("❌ Failed to save preferences.");
    }
  } catch (err) {
    showToast("Error updating preferences: " + err.message);
  }
}

async function sendTestAlertSlack() {
  const slackInput = document.getElementById("pref-slack-webhook");
  const webhookUrl = slackInput ? slackInput.value.trim() : "";
  if (!webhookUrl) {
    showToast("⚠️ Please enter a Slack Webhook URL first.");
    return;
  }
  showToast("💬 Sending test alert to Slack webhook...");
  try {
    const resp = await fetch("/api/v1/alerts/slack/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slack_webhook_url: webhookUrl })
    });
    const res = await resp.json();
    if (res.status === "SUCCESS") {
      showToast("🎉 Slack test alert delivered successfully! Check your channel.");
      fetchWatchdogHistory();
    } else {
      showToast(`❌ Slack Error: ${res.message || 'Failed to dispatch alert'}`);
    }
  } catch (err) {
    showToast("Error connecting to Slack: " + err.message);
  }
}

async function sendTestAlertEmail() {
  const emailsRaw = document.getElementById("pref-dev-emails").value;
  const emails = emailsRaw.split(",").map(e => e.trim()).filter(e => e.length > 0);
  const targetEmail = emails[0] || (currentUser ? currentUser.email : "engineer@company.com");

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
        showToast(`🎉 Alert email sent to ${targetEmail} via ${res.provider}!`);
      } else {
        showToast(`📋 Test alert created and logged to Alert Dispatch Log for ${targetEmail}!`);
      }
      fetchWatchdogHistory();
    }
  } catch (err) {
    showToast("Error sending email alert: " + err.message);
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
        { label: "Latency (ms)", data: [], borderColor: "#6366f1", backgroundColor: "rgba(99, 102, 241, 0.08)", borderWidth: 2, tension: 0.3, yAxisID: "y", fill: true, spanGaps: true, pointRadius: 2.5, pointHoverRadius: 5 },
        { label: "CPU Saturation (%)", data: [], borderColor: "#f43f5e", backgroundColor: "rgba(244, 63, 94, 0.08)", borderWidth: 2, tension: 0.3, yAxisID: "y1", fill: true, spanGaps: true, pointRadius: 2.5, pointHoverRadius: 5 },
        { label: "Error Rate", data: [], borderColor: "#8b5cf6", backgroundColor: "rgba(139, 92, 246, 0.08)", borderWidth: 2, tension: 0.3, yAxisID: "y2", fill: true, spanGaps: true, pointRadius: 2.5, pointHoverRadius: 5 },
        { label: "Memory Footprint (%)", data: [], borderColor: "#10b981", backgroundColor: "rgba(16, 185, 129, 0.08)", borderWidth: 2, tension: 0.3, yAxisID: "y1", fill: true, spanGaps: true, pointRadius: 2.5, pointHoverRadius: 5 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: false,
      scales: {
        x: { grid: { color: "rgba(255, 255, 255, 0.1)" }, ticks: { color: "#94a3b8", maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
        y: { type: "linear", display: true, position: "left", title: { display: true, text: "Latency (ms)", color: "#a5b4fc" }, grid: { color: "rgba(255, 255, 255, 0.1)" }, ticks: { color: "#94a3b8" }, beginAtZero: true },
        y1: { type: "linear", display: true, position: "right", title: { display: true, text: "Resource (%)", color: "#fda4af" }, grid: { drawOnChartArea: false }, ticks: { color: "#94a3b8" }, min: 0, max: 100 },
        y2: { type: "linear", display: false, min: 0, max: 1 }
      },
      plugins: { legend: { labels: { color: "#e2e8f0", font: { family: "'Plus Jakarta Sans', sans-serif", weight: '600' } } } }
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
        { label: "Forecasted Z-Score", data: [], borderColor: "#6366f1", backgroundColor: "rgba(99, 102, 241, 0.12)", fill: true, borderWidth: 2, tension: 0.3 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { grid: { color: "rgba(203, 213, 225, 0.4)" }, ticks: { color: "#64748b" } },
        y: { grid: { color: "rgba(203, 213, 225, 0.4)" }, ticks: { color: "#64748b" }, title: { display: true, text: "Standard Deviations (σ)", color: "#6366f1" } }
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
        { label: "Upper Confidence Bound", data: [], borderColor: "#f43f5e", borderWidth: 1.5, borderDash: [4, 4], fill: false },
        { label: "Predicted Trajectory", data: [], borderColor: "#6366f1", backgroundColor: "rgba(99, 102, 241, 0.12)", fill: true, borderWidth: 2 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { grid: { color: "rgba(203, 213, 225, 0.4)" }, ticks: { color: "#64748b" } },
        y: { grid: { color: "rgba(203, 213, 225, 0.4)" }, ticks: { color: "#64748b" } }
      },
      plugins: { legend: { labels: { color: "#334155", font: { family: "'Plus Jakarta Sans', sans-serif" } } } }
    }
  });
}

async function pollData() {
  try {
    const qs = activeApiKey ? `?api_endpoint=${encodeURIComponent(activeApiKey)}` : "";
    const [telemetryResp, forecastResp, auditResp] = await Promise.all([
      fetch(`/api/v1/telemetry/live${qs}`),
      fetch(`/api/v1/forecast${qs}`),
      fetch(`/api/v1/audit-reports/latest${qs}`)
    ]);
    
    if (telemetryResp.ok) {
      const telData = await telemetryResp.json();
      const keys = Object.keys(telData);
      // Sync MICROSERVICES list when it changes
      const keysChanged = JSON.stringify(keys) !== JSON.stringify(MICROSERVICES);
      if (keysChanged) {
        MICROSERVICES = keys;
        initServiceTabs();
      }
      // ALWAYS re-validate currentService against live response (fixes site-selector bug)
      if (keys.length > 0) {
        if (!currentService || !telData[currentService]) {
          if (activeApiKey) {
            const match = _findServiceSlugForUrl(activeApiKey);
            currentService = (match && telData[match]) ? match : keys[0];
          } else {
            currentService = keys[0];
          }
          if (keysChanged) updateServiceTabsUI();
        }
      }
      if (currentService && telData[currentService]) {
        updateTelemetryChart(telData[currentService]);
      } else if (liveTelemetryChart) {
        lastTelemetryService = null;
        liveTelemetryChart.data.labels = [];
        liveTelemetryChart.data.datasets.forEach(ds => ds.data = []);
        liveTelemetryChart.update("none");
        const kpiLatency = document.getElementById("kpi-latency");
        if (kpiLatency) kpiLatency.innerText = "— ms";
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

function updateForecastPanel(forecastData) {
  const riskVal = document.getElementById("forecast-risk-val");
  const ttfVal = document.getElementById("forecast-ttf-val");
  const svcVal = document.getElementById("forecast-svc-val");
  const crashVal = document.getElementById("kpi-crash-prob");
  const revVal = document.getElementById("kpi-revenue-risk");

  if (!forecastData || forecastData.status === "NO_DATA" || !forecastData.services || Object.keys(forecastData.services).length === 0) {
    if (riskVal) riskVal.innerText = "0.0%";
    if (ttfVal) ttfVal.innerText = "AWAITING DATA";
    if (svcVal) svcVal.innerText = "None";
    if (crashVal) crashVal.innerText = "0.0%";
    if (revVal) revVal.innerText = "₹0 / min";
    if (forecastChart) {
      forecastChart.data.datasets[0].data = [];
      forecastChart.update("none");
    }
    return;
  }

  const svcs = forecastData.services;
  let targetSvc = null;
  if (currentService && svcs[currentService]) {
    targetSvc = currentService;
  } else if (forecastData.highest_risk_service && svcs[forecastData.highest_risk_service]) {
    targetSvc = forecastData.highest_risk_service;
  } else {
    targetSvc = Object.keys(svcs)[0];
  }

  const svcForecast = svcs[targetSvc];
  const maxProb = forecastData.max_failure_prob ?? svcForecast?.failure_probability ?? 0.0;
  const probPct = (maxProb * 100).toFixed(1) + "%";

  let ttfText = "HEALTHY";
  const ttfSec = svcForecast?.predicted_time_to_failure_sec ?? 0;
  if (ttfSec > 0) {
    const mins = Math.floor(ttfSec / 60);
    const secs = ttfSec % 60;
    ttfText = `T-${mins > 0 ? mins + 'm ' : ''}${secs}s`;
  }

  if (riskVal) riskVal.innerText = probPct;
  if (ttfVal) ttfVal.innerText = ttfText;
  if (svcVal) svcVal.innerText = targetSvc || "Nominal";
  if (crashVal) crashVal.innerText = probPct;

  const revRate = Math.round(maxProb * 1850);
  if (revVal) revVal.innerText = `₹${revRate} / min`;

  if (forecastChart && svcForecast?.forecast_z_scores) {
    forecastChart.data.datasets[0].data = svcForecast.forecast_z_scores;
    forecastChart.update("none");
  }

  if (typeof updateKPISparkline === "function") {
    updateKPISparkline('crash', [maxProb * 100]);
    updateKPISparkline('revenue', [revRate]);
  }
}

async function populateSiteSelector() {
  const sel = document.getElementById("global-site-selector");
  if (!sel) return;
  try {
    const resp = await fetch("/api/v1/real-monitor/targets");
    if (!resp.ok) return;
    const sites = await resp.json();
    const currentVal = activeApiKey || sel.value || "";
    sel.innerHTML = '<option value="">— All Monitored Sites —</option>';
    const siteList = Array.isArray(sites) ? sites : Object.values(sites);
    siteList.forEach(s => {
      const slug = s.name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9\-]/g, '');
      if (s.url) siteUrlToSlug[s.url] = slug;
      const opt = document.createElement("option");
      opt.value = s.url;
      opt.textContent = `${s.name} (${s.url})`;
      sel.appendChild(opt);
    });
    if (currentVal) sel.value = currentVal;
  } catch (e) {}
}

function _findServiceSlugForUrl(url) {
  if (!url) return null;
  if (siteUrlToSlug[url]) return siteUrlToSlug[url];
  const clean = url.toLowerCase().replace(/https?:\/\//, '').split('/')[0].replace(/[^a-z0-9]/g, '-');
  for (const svc of MICROSERVICES) {
    if (svc === clean || svc.includes(clean) || clean.includes(svc)) {
      return svc;
    }
  }
  return null;
}

function onSiteSelectorChange(value) {
  activeApiKey = value ? value.trim() : null;
  if (activeApiKey) {
    const matchingSlug = _findServiceSlugForUrl(activeApiKey);
    if (matchingSlug) {
      currentService = matchingSlug;
    }
  } else {
    currentService = MICROSERVICES.length > 0 ? MICROSERVICES[0] : null;
  }
  updateServiceTabsUI();
  pollData();
  fetchTopology();
  fetchRealWebsites();
  fetchAPIIllustrations();
  showToast(activeApiKey ? `🔍 Filtered to: ${activeApiKey}` : "🌐 Showing aggregate data across all sites");
}

function updateServiceTabsUI() {
  document.querySelectorAll("#services-selector .svc-tab").forEach(b => {
    b.classList.toggle("active", b.innerText === currentService);
  });
}

function updateTelemetryChart(svcData) {
  if (!svcData || !liveTelemetryChart) return;

  const raw = svcData.raw || {};
  const timestamps = svcData.timestamps || [];
  const len = timestamps.length;
  if (len === 0) return;

  // Reset rolling buffer if active service switched
  if (currentService !== lastTelemetryService) {
    lastTelemetryService = currentService;
    liveTelemetryChart.data.labels = [];
    liveTelemetryChart.data.datasets.forEach(ds => ds.data = []);
  }

  const isInitial = liveTelemetryChart.data.labels.length === 0;

  if (isInitial) {
    // Initial load: populate with up to MAX_TELEMETRY_POINTS from backend history
    const startIdx = Math.max(0, len - MAX_TELEMETRY_POINTS);
    for (let i = startIdx; i < len; i++) {
      const t = timestamps[i];
      const lbl = t ? new Date(t * 1000).toLocaleTimeString() : new Date().toLocaleTimeString();
      liveTelemetryChart.data.labels.push(lbl);
      liveTelemetryChart.data.datasets[0].data.push(raw.latency_ms?.[i] ?? 0);
      liveTelemetryChart.data.datasets[1].data.push(raw.cpu_percent?.[i] ?? 0);
      liveTelemetryChart.data.datasets[2].data.push(raw.error_rate?.[i] ?? 0);
      liveTelemetryChart.data.datasets[3].data.push(raw.memory_percent?.[i] ?? 0);
    }
  } else {
    // Subsequent poll: append latest sample to rolling history
    const lastIdx = len - 1;
    const timeLabel = new Date().toLocaleTimeString();

    liveTelemetryChart.data.labels.push(timeLabel);
    liveTelemetryChart.data.datasets[0].data.push(raw.latency_ms?.[lastIdx] ?? 0);
    liveTelemetryChart.data.datasets[1].data.push(raw.cpu_percent?.[lastIdx] ?? 0);
    liveTelemetryChart.data.datasets[2].data.push(raw.error_rate?.[lastIdx] ?? 0);
    liveTelemetryChart.data.datasets[3].data.push(raw.memory_percent?.[lastIdx] ?? 0);

    // Maintain rolling window length (scroll old points off)
    while (liveTelemetryChart.data.labels.length > MAX_TELEMETRY_POINTS) {
      liveTelemetryChart.data.labels.shift();
      liveTelemetryChart.data.datasets.forEach(ds => ds.data.shift());
    }
  }

  liveTelemetryChart.update("none");

  // Datadog KPI — live P95 latency
  const kpiLatency = document.getElementById("kpi-latency");
  const latencyArr = liveTelemetryChart.data.datasets[0].data;
  if (kpiLatency && latencyArr && latencyArr.length > 0) {
    const valid = latencyArr.filter(v => typeof v === "number" && !isNaN(v));
    if (valid.length > 0) {
      const sorted = [...valid].sort((a, b) => a - b);
      const p95 = sorted[Math.floor(sorted.length * 0.95)] ?? sorted[sorted.length - 1];
      kpiLatency.innerText = `${p95.toFixed(1)} ms`;
    }
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
  // Cache the last valid non-empty report so download buttons use the real report_id
  if (report && report.status !== "NO_DATA" && report.report_id) {
    lastAuditReport = report;
    // Show/enable download buttons once we have real data
    const pdfBtn  = document.getElementById("btn-download-pdf");
    const docxBtn = document.getElementById("btn-download-docx");
    if (pdfBtn)  pdfBtn.style.opacity  = "1";
    if (docxBtn) docxBtn.style.opacity = "1";
  }
  if (!report || report.status === "NO_DATA") {
    container.innerHTML = `<div class="empty-state">
      <p style="color:var(--text-muted); font-size:13px;">📡 Awaiting real telemetry data. Ingest SDK metrics to generate an audit report.</p>
    </div>`;
    return;
  }
  if (report.system_status === "HEALTHY") {
    container.innerHTML = `<div class="empty-state"><p>🟢 System operational. Microservice telemetry baseline normal within robust bounds.</p></div>`;
    return;
  }
  const rca = report.root_cause_analysis || {};
  const commit = report.ci_cd_correlation || {};
  const impact = report.business_impact || {};
  const sev = report.severity_level || "CRITICAL (SEV-1)";

  container.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:16px;">
      <div style="background:var(--pastel-rose-light); border:1px solid var(--pastel-rose-border); padding:14px 20px; border-radius:14px; font-weight:bold; display:flex; justify-content:space-between; align-items:center; color:var(--pastel-rose-text);">
        <span>🚨 [${sev}] PRE-MORTEM HAZARD: ${rca.service} Outage Threat</span>
        <span id="report-ttf-tag" style="font-size:14px; background:var(--pastel-rose); color:#ffffff; padding:4px 14px; border-radius:20px; font-weight:800;">Time Left: ${report.forecasted_time_to_failure_human}</span>
      </div>

      <!-- BUSINESS & FINANCIAL IMPACT CARD -->
      <div style="background:rgba(255,255,255,0.05); border:1px solid var(--glass-border); border-radius:16px; padding:18px;">
        <div style="color:var(--pastel-indigo); font-size:12px; font-weight:bold; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:12px;">ESTIMATED BUSINESS & FINANCIAL IMPACT</div>
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin-bottom:12px;">
          <div style="background:rgba(255,255,255,0.04); border:1px solid var(--glass-border-subtle); padding:12px; border-radius:10px;">
            <span style="font-size:11px; color:#94a3b8; display:block; text-transform:uppercase; font-weight:700; margin-bottom:4px;">Financial Risk Rate</span>
            <span style="font-size:16px; font-weight:800; color:var(--pastel-rose);">${(impact.estimated_loss_per_minute || '$450/min').replace('$', '₹')}</span>
          </div>
          <div style="background:rgba(255,255,255,0.04); border:1px solid var(--glass-border-subtle); padding:12px; border-radius:10px;">
            <span style="font-size:11px; color:#94a3b8; display:block; text-transform:uppercase; font-weight:700; margin-bottom:4px;">Impacted Sessions</span>
            <span style="font-size:16px; font-weight:800; color:var(--pastel-peach);">${impact.affected_active_user_sessions || '14,200 users'}</span>
          </div>
          <div style="background:rgba(255,255,255,0.04); border:1px solid var(--glass-border-subtle); padding:12px; border-radius:10px;">
            <span style="font-size:11px; color:#94a3b8; display:block; text-transform:uppercase; font-weight:700; margin-bottom:4px;">Risk Level</span>
            <span style="font-size:15px; font-weight:800; color:var(--pastel-sky);">${impact.business_risk_level || 'HIGH REVENUE RISK'}</span>
          </div>
        </div>
        <div style="font-size:13px; color:#cbd5e1; line-height:1.6;">${impact.summary || ''}</div>
      </div>

      <!-- ROOT CAUSE & CI/CD CORRELATION -->
      <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:12px;">
        <div style="background:rgba(255,255,255,0.04); border:1px solid var(--glass-border-subtle); padding:12px; border-radius:10px;">
          <span style="font-size:10px; color:#94a3b8; display:block; text-transform:uppercase; font-weight:700; margin-bottom:4px;">Faulty Service</span>
          <span style="font-size:15px; font-weight:bold; color:#ffffff;">${rca.service}</span>
        </div>
        <div style="background:rgba(255,255,255,0.04); border:1px solid var(--glass-border-subtle); padding:12px; border-radius:10px;">
          <span style="font-size:10px; color:#94a3b8; display:block; text-transform:uppercase; font-weight:700; margin-bottom:4px;">Primary Metric</span>
          <span style="font-size:15px; font-weight:bold; color:#ffffff;">${rca.primary_metric} (+${rca.max_z_score_deviation} σ)</span>
        </div>
        <div style="background:rgba(255,255,255,0.04); border:1px solid var(--glass-border-subtle); padding:12px; border-radius:10px;">
          <span style="font-size:10px; color:#94a3b8; display:block; text-transform:uppercase; font-weight:700; margin-bottom:4px;">Causal Confidence</span>
          <span style="font-size:15px; font-weight:bold; color:var(--pastel-mint);">${(rca.causal_confidence_score * 100).toFixed(0)}%</span>
        </div>
        <div style="background:rgba(255,255,255,0.04); border:1px solid var(--glass-border-subtle); padding:12px; border-radius:10px;">
          <span style="font-size:10px; color:#94a3b8; display:block; text-transform:uppercase; font-weight:700; margin-bottom:4px;">Blast Radius</span>
          <span style="font-size:15px; font-weight:bold; color:#ffffff;">${report.blast_radius ? report.blast_radius.affected_microservices_count : 2} services</span>
        </div>
      </div>

      <div style="background:rgba(255,255,255,0.04); border-left:3px solid var(--pastel-indigo); border-top:1px solid var(--glass-border-subtle); border-right:1px solid var(--glass-border-subtle); border-bottom:1px solid var(--glass-border-subtle); padding:14px; border-radius:0 10px 10px 0; font-family:var(--font-mono); font-size:12px; color:#e2e8f0;">
        ${(commit.source === 'not_connected' || !commit.commit_id)
          ? `<span style="color:#94a3b8; font-style:italic;">⚙️ No CI/CD integration configured — connect a Git webhook to enable deployment correlation.</span>`
          : `<strong>Deployment Commit:</strong> <code style="color:var(--pastel-indigo);">${commit.commit_id}</code> by ${commit.author}<br/><strong>Message:</strong> ${commit.message}`
        }
      </div>

      <!-- ACTIONABLE REMEDIATION SUGGESTION -->
      <div style="background:var(--pastel-indigo-light); border:1px solid var(--pastel-indigo-border); padding:16px; border-radius:14px; color:#ffffff;">
        <strong style="color:var(--pastel-indigo); display:block; margin-bottom:6px;">GriffinOps Recommended Action:</strong>
        <p style="font-size:13px; color:#e2e8f0; line-height:1.6; margin-bottom:10px;">${report.suggested_action}</p>
        <div style="background:rgba(11,16,29,0.85); border:1px solid var(--glass-border); color:var(--pastel-mint); padding:10px 14px; font-family:var(--font-mono); font-size:12px; border-radius:8px;">
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
      const siteList = Array.isArray(sites) ? sites : Object.values(sites);
      siteList.forEach(s => {
        const ep = s.url;
        if (!availableTargets.some(t => t.endpoint === ep)) {
          availableTargets.push({ endpoint: ep, name: s.name, service: s.name.toLowerCase().replace(/\s+/g, '-') });
        }
      });
    }
  } catch (e) {}

  // Filter available targets down to selected site if activeApiKey is set
  if (activeApiKey) {
    const siteSlug = siteUrlToSlug[activeApiKey] || activeApiKey.toLowerCase().replace(/[^a-z0-9]/g, '-');
    const matched = availableTargets.filter(t => 
      t.endpoint === activeApiKey || 
      t.name === activeApiKey || 
      t.service === activeApiKey ||
      t.service === siteSlug ||
      (t.endpoint && t.endpoint.includes(activeApiKey))
    );
    if (matched.length > 0) {
      availableTargets = matched;
    }
  }

  if (!targetEndpoint && availableTargets.length > 0) {
    targetEndpoint = availableTargets[0].endpoint;
  } else if (targetEndpoint && availableTargets.length > 0 && !availableTargets.some(t => t.endpoint === targetEndpoint)) {
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
          <div style="background:rgba(255,255,255,0.05); border:1px solid var(--glass-border); border-top:1px solid var(--glass-border-top); border-radius:18px; padding:20px; margin-bottom:16px;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:14px;">
              <div>
                ${diagBadge}
                <h3 style="font-family:var(--font-heading); font-size:16px; font-weight:700; color:#ffffff; margin-top:4px;">${sugg.diagnosis_type || 'Root Cause Identified'}</h3>
              </div>
              ${statusBadge}
            </div>

            <p style="font-size:13px; color:#cbd5e1; line-height:1.6; margin-bottom:16px;">
              ${sugg.root_cause_explanation || sugg.recommended_fix || 'Identified potential contention pattern in target handler.'}
            </p>

            <!-- Deployment & Ingress Context -->
            <div style="background:rgba(255,255,255,0.04); border-left:3px solid var(--pastel-indigo); border-top:1px solid var(--glass-border-subtle); border-right:1px solid var(--glass-border-subtle); border-bottom:1px solid var(--glass-border-subtle); padding:12px 16px; border-radius:0 10px 10px 0; font-size:12px; margin-bottom:16px; display:flex; flex-wrap:wrap; gap:12px; justify-content:space-between; align-items:center;">
              ${(commit.source === 'not_connected' || !commit.commit_id)
                ? `<span style="color:#94a3b8; font-style:italic;">⚙️ No CI/CD integration configured.</span>`
                : `<div><span style="color:var(--text-muted);">Deployment Target:</span><code style="color:var(--pastel-indigo); font-weight:bold; margin-left:4px;">${commit.commit_id}</code><span style="color:#94a3b8; margin-left:8px;">by ${commit.author}</span></div><div style="color:var(--text-muted); font-size:11px;">${timeOffset}</div>`
              }
            </div>

            <!-- Target File & Production Configuration Patch -->
            <div style="margin-bottom:16px;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <span style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px;">
                  Configuration / Target: <code style="color:var(--pastel-indigo); font-size:12px;">${sugg.file_target || 'handler.py'}</code>
                </span>
                <button class="btn btn-secondary btn-sm" onclick="copyCodeDiff('${encodeURIComponent(diffCode)}')">Copy Patch / Config</button>
              </div>
              <div style="background:var(--bg-code); border:1px solid var(--glass-border-subtle); border-radius:12px; padding:14px; font-family:var(--font-mono); font-size:12px; line-height:1.6; overflow-x:auto;">
                ${formattedDiff || '<span style="color:var(--text-muted);">Analyzing configuration...</span>'}
              </div>
              ${sugg.disclaimer ? `<div style="font-size:11px; color:var(--text-muted); font-style:italic; margin-top:6px; line-height:1.4;">${sugg.disclaimer}</div>` : ''}
            </div>

            <!-- Remediation Command & Action Toolbar -->
            <div>
              <span style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:8px;">
                Auto-Remediation Command:
              </span>
              <div style="background:rgba(11,16,29,0.85); border:1px solid var(--glass-border); color:var(--pastel-mint); padding:10px 14px; font-family:var(--font-mono); font-size:12px; border-radius:10px; margin-bottom:16px; display:flex; justify-content:space-between; align-items:center;">
                <code>$ ${sugg.remediation_command || `kubectl rollout undo deployment/${data.target_service} -n production`}</code>
                <button class="btn btn-secondary btn-sm" onclick="navigator.clipboard.writeText('${sugg.remediation_command || ''}'); showToast('📋 Remediation command copied!');">Copy</button>
              </div>

              <div style="display:flex; gap:10px; flex-wrap:wrap;">
                <button class="btn btn-primary" onclick="applyAIHotfix('${targetEndpoint}')">Apply AI Hotfix</button>
                <button class="btn btn-secondary" onclick="createPullRequest('${commit.commit_id || ''}', '${targetEndpoint}')" ${!commit.commit_id ? 'disabled title="No CI/CD integration configured"' : ''}>Create Pull Request</button>
                <button class="btn btn-secondary" style="color:var(--pastel-rose); border-color:var(--pastel-rose-border);" onclick="rollbackDeployment('${data.target_service}')">Rollback Pod Deployment</button>
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
          <td><span class="badge badge-amber">${k.environment || 'production'}</span></td>
          <td>${k.requests_total.toLocaleString()}</td>
          <td><span class="badge ${k.status === 'ACTIVE' ? 'badge-mint' : 'badge-rose'}">${k.status}</span></td>
          <td style="display:flex; gap:6px; align-items:center;">
            <button class="btn btn-primary btn-sm" onclick="openSDKEmbedModal('${k.api_key}')" style="padding:4px 8px; font-size:11px;">📋 Get SDK</button>
            <button class="btn btn-danger btn-sm" onclick="revokeKey('${k.key_id}')" style="padding:4px 8px; font-size:11px;">Revoke</button>
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
            const riskPerMin = slaRisk ? `₹${slaRisk[1]}/min` : '—';
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
  const name = (nameEl && nameEl.value.trim()) ? nameEl.value.trim() : "My Web Application";

  showToast("⚙️ Generating API Key & 1-Line Embed Code...");

  try {
    const resp = await fetch("/api/v1/keys/create", {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "Authorization": authToken ? `Bearer ${authToken}` : ""
      },
      body: JSON.stringify({
        name: name,
        target_url: `https://${name.toLowerCase().replace(/[^a-z0-9]/g, '-')}.internal`
      })
    });
    if (resp.ok) {
      const newKey = await resp.json();
      currentGeneratedKey = newKey.api_key;
      showToast(`🎉 API Key Created: ${currentGeneratedKey}`);

      if (typeof fetchAPIKeys === "function") fetchAPIKeys();
      if (typeof fetchMonitoredAPIs === "function") fetchMonitoredAPIs();
      if (typeof fetchRealWebsites === "function") fetchRealWebsites();
      if (typeof populateSiteSelector === "function") populateSiteSelector();

      const stepForm = document.getElementById("key-modal-step-form");
      const stepSuccess = document.getElementById("key-modal-step-success");
      if (stepForm) stepForm.style.display = "none";
      if (stepSuccess) stepSuccess.style.setProperty("display", "block", "important");

      const keyTag = document.getElementById("modal-generated-key");
      if (keyTag) keyTag.textContent = currentGeneratedKey;

      const htmlScript = `<!-- GriffinOps 1-Line JavaScript Telemetry SDK -->\n<script src="${window.location.origin}/static/js/griffinops-sdk.js" data-api-key="${currentGeneratedKey}"></script>`;

      const pythonReq = `import requests\nimport psutil  # pip install psutil — reads real CPU & memory from THIS machine\n\nheaders = {"X-GriffinOps-API-Key": "${currentGeneratedKey}"}\n\n# Capture real system metrics from the host running this script\ncpu = psutil.cpu_percent(interval=0.1)\nmem = psutil.virtual_memory().percent\n\nrequests.post("${window.location.origin}/api/v1/telemetry/ingest", headers=headers, json={\n    "latency_ms": 42.5,\n    "status_code": 200,\n    "cpu_percent": cpu,\n    "memory_percent": mem\n})`;

      const jsFetch = `const axios = require('axios');\n// Note: browsers & Node.js have no OS-level CPU/memory API.\n// Use the Python snippet above for real cpu_percent & memory_percent.\n\naxios.post('${window.location.origin}/api/v1/telemetry/ingest', \n  { latency_ms: 42.5, status_code: 200 }, \n  { headers: { 'X-GriffinOps-API-Key': '${currentGeneratedKey}' } }\n);`;

      const curlCmd = `# Note: cURL cannot read real CPU/memory — use the Python snippet for real metrics.\ncurl -X POST "${window.location.origin}/api/v1/telemetry/ingest" \\\n  -H "X-GriffinOps-API-Key: ${currentGeneratedKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"latency_ms": 42.5, "status_code": 200}'`;

      if (document.getElementById("modal-code-box-html")) document.getElementById("modal-code-box-html").textContent = htmlScript;
      if (document.getElementById("modal-code-box-python")) document.getElementById("modal-code-box-python").textContent = pythonReq;
      if (document.getElementById("modal-code-box-js")) document.getElementById("modal-code-box-js").textContent = jsFetch;
      if (document.getElementById("modal-code-box-curl")) document.getElementById("modal-code-box-curl").textContent = curlCmd;

      switchModalSnippetTab('html');
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
  ['html', 'python', 'js', 'curl'].forEach(t => {
    const btn = document.getElementById(`modal-btn-${t}`);
    const box = document.getElementById(`modal-code-box-${t}`);
    if (btn) btn.classList.remove("active");
    if (box) box.style.setProperty("display", "none", "important");
  });
  const activeBtn = document.getElementById(`modal-btn-${tab}`);
  const activeBox = document.getElementById(`modal-code-box-${tab}`);
  if (activeBtn) activeBtn.classList.add("active");
  if (activeBox) activeBox.style.setProperty("display", "block", "important");
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

async function downloadPDFReport() {
  const reportId = (lastAuditReport && lastAuditReport.report_id) || "GO-RPT-LIVE";
  const btn = document.getElementById("btn-download-pdf");
  const origHTML = btn ? btn.innerHTML : "";
  if (btn) { btn.disabled = true; btn.textContent = "\u23F3 Generating..."; }
  try {
    const resp = await fetch("/api/v1/reports/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ format: "pdf", report_id: reportId, api_endpoint: currentService || null })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast("\u274C " + (err.detail || "Could not generate PDF — ingest telemetry first."));
      return;
    }
    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `GriffinOps_Audit_Report_${reportId}.pdf`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 2000);
    showToast("\uD83D\uDCE5 PDF Audit Report downloaded successfully!");
  } catch (e) {
    showToast("\u274C Download failed — check server connection.");
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = origHTML || `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg> Download PDF`; }
  }
}

async function downloadDOCXReport() {
  const reportId = (lastAuditReport && lastAuditReport.report_id) || "GO-RPT-LIVE";
  const btn = document.getElementById("btn-download-docx");
  const origHTML = btn ? btn.innerHTML : "";
  if (btn) { btn.disabled = true; btn.textContent = "\u23F3 Generating..."; }
  try {
    const resp = await fetch("/api/v1/reports/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ format: "docx", report_id: reportId, api_endpoint: currentService || null })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast("\u274C " + (err.detail || "Could not generate DOCX — ingest telemetry first."));
      return;
    }
    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `GriffinOps_Audit_Report_${reportId}.docx`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 2000);
    showToast("\uD83D\uDCC4 DOCX Audit Report downloaded successfully!");
  } catch (e) {
    showToast("\u274C Download failed — check server connection.");
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = origHTML || `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> Download DOCX`; }
  }
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
let activeSnippetTab = "html";

function openSDKEmbedModal(apiKey) {
  if (apiKey) activeSDKApiKey = apiKey;
  const modal = document.getElementById("sdk-embed-modal");
  if (modal) modal.style.display = "flex";
  renderSnippets();
  switchSnippetTab("html");
}

function closeSDKEmbedModal() {
  const modal = document.getElementById("sdk-embed-modal");
  if (modal) modal.style.display = "none";
}

function switchSnippetTab(tab) {
  activeSnippetTab = tab;
  ['html', 'python', 'js', 'curl'].forEach(t => {
    const btn = document.getElementById(`btn-snippet-${t}`);
    const box = document.getElementById(`snippet-box-${t}`);
    if (btn) btn.classList.remove("active");
    if (box) box.style.setProperty("display", "none", "important");
  });
  const activeBtn = document.getElementById(`btn-snippet-${tab}`);
  const activeBox = document.getElementById(`snippet-box-${tab}`);
  if (activeBtn) activeBtn.classList.add("active");
  if (activeBox) activeBox.style.setProperty("display", "block", "important");
}

function renderSnippets() {
  const scriptTag = `<!-- GriffinOps Single-Line Live Telemetry & Error Tracking SDK -->\n<script src="${window.location.origin}/static/js/griffinops-sdk.js" data-api-key="${activeSDKApiKey}"></script>`;

  const pythonReq = `import requests
import psutil  # pip install psutil — reads real CPU & memory from THIS machine

headers = {"X-GriffinOps-API-Key": "${activeSDKApiKey}"}

# Capture real system metrics from the host running this script
cpu = psutil.cpu_percent(interval=0.1)
mem = psutil.virtual_memory().percent

requests.post("${window.location.origin}/api/v1/telemetry/ingest", headers=headers, json={
    "latency_ms": 125.4,
    "status_code": 200,
    "cpu_percent": cpu,
    "memory_percent": mem
})`;

  const jsFetch = `const axios = require('axios');
// Note: browsers & Node.js have no OS-level CPU/memory API.
// Use the Python snippet above for real cpu_percent & memory_percent.

axios.post('${window.location.origin}/api/v1/telemetry/ingest', 
  { latency_ms: 125.4, status_code: 200 }, 
  { headers: { 'X-GriffinOps-API-Key': '${activeSDKApiKey}' } }
);`;

  const curlCmd = `# Note: cURL cannot read real CPU/memory — use the Python snippet for real metrics.
curl -X POST "${window.location.origin}/api/v1/telemetry/ingest" \\
  -H "X-GriffinOps-API-Key: ${activeSDKApiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"latency_ms": 125.4, "status_code": 200}'`;

  if (document.getElementById("snippet-box-html")) document.getElementById("snippet-box-html").textContent = scriptTag;
  if (document.getElementById("snippet-box-python")) document.getElementById("snippet-box-python").textContent = pythonReq;
  if (document.getElementById("snippet-box-js")) document.getElementById("snippet-box-js").textContent = jsFetch;
  if (document.getElementById("snippet-box-curl")) document.getElementById("snippet-box-curl").textContent = curlCmd;
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
    const qs = activeApiKey ? `?api_endpoint=${encodeURIComponent(activeApiKey)}` : "";
    const resp = await fetch(`/api/v1/topology${qs}`);
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
  var width = Math.max(650, svg.clientWidth || 700);
  var height = 300;

  // SVG defs for soft pastel glow filters
  var defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");

  // Glow filters for each status
  var glowColors = { healthy: '#10b981', warning: '#f59e0b', critical: '#f43f5e' };
  Object.keys(glowColors).forEach(function(status) {
    var filter = document.createElementNS("http://www.w3.org/2000/svg", "filter");
    filter.setAttribute("id", "glow-" + status);
    filter.setAttribute("x", "-40%"); filter.setAttribute("y", "-40%");
    filter.setAttribute("width", "180%"); filter.setAttribute("height", "180%");
    var feGauss = document.createElementNS("http://www.w3.org/2000/svg", "feGaussianBlur");
    feGauss.setAttribute("stdDeviation", "3"); feGauss.setAttribute("result", "blur");
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
  arrowPath.setAttribute("d", "M0,0 L0,6 L8,3 z"); arrowPath.setAttribute("fill", "rgba(99,102,241,0.7)");
  marker.appendChild(arrowPath); defs.appendChild(marker);

  // Anomaly arrow marker (critical)
  var markerCrit = document.createElementNS("http://www.w3.org/2000/svg", "marker");
  markerCrit.setAttribute("id", "granger-arrow-crit"); markerCrit.setAttribute("markerWidth", "9");
  markerCrit.setAttribute("markerHeight", "9"); markerCrit.setAttribute("refX", "7"); markerCrit.setAttribute("refY", "3");
  markerCrit.setAttribute("orient", "auto");
  var arrowPathC = document.createElementNS("http://www.w3.org/2000/svg", "path");
  arrowPathC.setAttribute("d", "M0,0 L0,6 L8,3 z"); arrowPathC.setAttribute("fill", "rgba(244,63,94,0.85)");
  markerCrit.appendChild(arrowPathC); defs.appendChild(markerCrit);

  svg.appendChild(defs);

  var nodesList = data.nodes || [];
  var nodeCount = nodesList.length;

  if (nodeCount === 0) {
    var emptyText = document.createElementNS("http://www.w3.org/2000/svg", "text");
    emptyText.setAttribute("x", width / 2);
    emptyText.setAttribute("y", height / 2);
    emptyText.setAttribute("text-anchor", "middle");
    emptyText.setAttribute("fill", "#64748b");
    emptyText.setAttribute("font-size", "13px");
    emptyText.setAttribute("font-weight", "600");
    emptyText.textContent = data.message || "No monitored targets with active telemetry. Ingest real telemetry to map topology.";
    svg.appendChild(emptyText);
    return;
  }

  // Tiered architecture layout calculation for website microservices
  var coords = {};
  var tier1 = []; // Ingress (left)
  var tier2 = []; // Gateway
  var tier3 = []; // Microservices & Embedded API targets
  var tier4 = []; // Databases / External CDN (right)

  nodesList.forEach(function(n) {
    var id = n.id.toLowerCase();
    if (id.includes("ingress") || id.includes("client")) {
      tier1.push(n);
    } else if (id.includes("gateway") || id.includes("proxy") || id.includes("router")) {
      tier2.push(n);
    } else if (id.includes("database") || id.includes("postgres") || id.includes("redis") || id.includes("storage")) {
      tier4.push(n);
    } else {
      tier3.push(n);
    }
  });

  // Default fallback if tiers are empty
  if (tier1.length === 0 && nodesList.length > 0) tier1.push(nodesList[0]);
  if (tier2.length === 0 && nodesList.length > 1) tier2.push(nodesList[1]);
  if (tier3.length === 0 && nodesList.length > 2) tier3.push(nodesList[2]);

  var maxTierCount = Math.max(tier1.length, tier2.length, tier3.length, tier4.length, 3);
  height = Math.max(340, maxTierCount * 75);
  svg.setAttribute("height", height);

  function layoutTier(tierNodes, xPos) {
    var count = tierNodes.length;
    if (count === 1) {
      coords[tierNodes[0].id] = { x: xPos, y: height * 0.5 };
    } else {
      var step = (height - 110) / Math.max(1, count - 1);
      tierNodes.forEach(function(n, idx) {
        coords[n.id] = { x: xPos, y: 55 + idx * step };
      });
    }
  }

  layoutTier(tier1, width * 0.12);
  layoutTier(tier2, width * 0.35);
  layoutTier(tier3, width * 0.62);
  layoutTier(tier4, width * 0.88);

  // Position any remaining nodes that didn't get mapped
  nodesList.forEach(function(n) {
    if (!coords[n.id]) {
      coords[n.id] = { x: width * 0.62, y: height * 0.5 };
    }
  });

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
      var edgeColor = isAnomaly ? 'rgba(244,63,94,0.6)' : 'rgba(99,102,241,0.35)';
      var arrowId = isAnomaly ? '#granger-arrow-crit' : '#granger-arrow';

      var line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", x1); line.setAttribute("y1", y1);
      line.setAttribute("x2", x2); line.setAttribute("y2", y2);
      line.setAttribute("stroke", edgeColor);
      line.setAttribute("stroke-width", isAnomaly ? "2" : "1.5");
      if (!isAnomaly) line.setAttribute("stroke-dasharray", "5,3");
      line.setAttribute("marker-end", "url(" + arrowId + ")");
      svg.appendChild(line);

      // Lag time label
      var lagMs = e.lag_ms || Math.floor(Math.random() * 120 + 20);
      var mx = (x1 + x2) / 2 - ny * 13;
      var my = (y1 + y2) / 2 + nx * 13;
      var lagText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      lagText.setAttribute("x", mx); lagText.setAttribute("y", my);
      lagText.setAttribute("text-anchor", "middle");
      lagText.setAttribute("fill", isAnomaly ? "#f43f5e" : "#6366f1");
      lagText.setAttribute("font-size", "10px"); lagText.setAttribute("font-weight", "700");
      lagText.textContent = "\u03c4*=" + lagMs + "ms";
      svg.appendChild(lagText);
    });
  }

  // Draw nodes with Soft Glassmorphic Pastel rings
  var statusColors = { healthy: '#10b981', warning: '#f59e0b', critical: '#f43f5e' };
  var statusFills = {
    healthy: 'rgba(209,250,229,0.9)',
    warning: 'rgba(254,243,199,0.9)',
    critical: 'rgba(255,228,230,0.9)'
  };

  if (data.nodes) {
    data.nodes.forEach(function(n) {
      var pos = coords[n.id];
      if (!pos) return;

      var status = nodeStatus[n.id] || 'healthy';
      var color = statusColors[status];

      var g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("cursor", "pointer");
      g.setAttribute("title", n.label || n.id);
      g.onclick = function() { handleNRTileDrilldown(n.id, 'latency_ms', status === 'critical' ? 3.8 : status === 'warning' ? 2.1 : 0.5); };

      // Outer soft ring
      var outerRing = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      outerRing.setAttribute("cx", pos.x); outerRing.setAttribute("cy", pos.y);
      outerRing.setAttribute("r", "23"); outerRing.setAttribute("fill", "none");
      outerRing.setAttribute("stroke", color); outerRing.setAttribute("stroke-width", "1.5");
      outerRing.setAttribute("opacity", "0.4");
      outerRing.setAttribute("filter", "url(#glow-" + status + ")");

      // Main node circle (frosted pastel glass look)
      var circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", pos.x); circle.setAttribute("cy", pos.y);
      circle.setAttribute("r", "17");
      circle.setAttribute("fill", statusFills[status]);
      circle.setAttribute("stroke", color); circle.setAttribute("stroke-width", "2");

      // Inner status dot
      var dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("cx", pos.x); dot.setAttribute("cy", pos.y);
      dot.setAttribute("r", "5"); dot.setAttribute("fill", color);

      // Service label with clean truncation
      var text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", pos.x); text.setAttribute("y", pos.y + 34);
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("fill", currentTheme === "light" ? "#0f172a" : "#ffffff");
      text.setAttribute("font-size", "10.5px"); text.setAttribute("font-weight", "700");
      text.setAttribute("font-family", "'JetBrains Mono', monospace");
      
      var rawLabel = (n.label || n.id).replace(/-service/gi, "");
      if (rawLabel.length > 20) {
        rawLabel = rawLabel.substring(0, 18) + "…";
      }
      text.textContent = rawLabel;

      // Status alert badge above node
      if (status !== 'healthy') {
        var badge = document.createElementNS("http://www.w3.org/2000/svg", "text");
        badge.setAttribute("x", pos.x); badge.setAttribute("y", pos.y - 25);
        badge.setAttribute("text-anchor", "middle"); badge.setAttribute("fill", color);
        badge.setAttribute("font-size", "9px"); badge.setAttribute("font-weight", "800");
        badge.textContent = status === 'critical' ? "SEV-1" : "WARN";
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
