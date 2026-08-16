/**
 * 🦅 GriffinOps Real-Time Telemetry & Predictive Observability SDK
 * Single-line Embed Script for Hosted Websites & Microservices
 *
 * Usage:
 * <script src="http://localhost:8000/static/js/griffinops-sdk.js" data-api-key="gop_live_YOUR_KEY"></script>
 */
(function() {
  const currentScript = document.currentScript || Array.from(document.querySelectorAll('script')).pop();
  const apiKey = currentScript ? currentScript.getAttribute('data-api-key') : 'gop_live_default';
  const serverUrl = currentScript && currentScript.src ? new URL(currentScript.src).origin : window.location.origin;

  console.log(`[GriffinOps SDK] Initializing Real-Time Monitoring with API Key: ${apiKey}`);

  // Auto-collect page load latency & error telemetry
  window.addEventListener('load', function() {
    setTimeout(sendTelemetry, 1000);
  });

  // Track unhandled errors
  window.addEventListener('error', function(event) {
    sendTelemetry({ error: event.message, filename: event.filename, lineno: event.lineno });
  });

  function sendTelemetry(extraData) {
    const navEntries = performance.getEntriesByType('navigation');
    const loadTimeMs = navEntries.length > 0 ? Math.round(navEntries[0].duration) : 120;
    
    const payload = {
      api_key: apiKey,
      site_url: window.location.href,
      page_title: document.title,
      latency_ms: loadTimeMs,
      timestamp: Math.floor(Date.now() / 1000),
      user_agent: navigator.userAgent,
      status_code: 200,
      extra: extraData || null
    };

    fetch(`${serverUrl}/api/v1/real-monitor/add-site`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-GriffinOps-API-Key': apiKey
      },
      body: JSON.stringify({
        name: document.title || 'Hosted Web Application',
        url: window.location.href,
        site_type: 'Hosted Web App'
      })
    }).catch(() => {});
  }

  // Periodic heartbeat every 15s
  setInterval(sendTelemetry, 15000);
})();
