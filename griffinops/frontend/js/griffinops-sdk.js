/**
 * GriffinOps Autonomous Predictive Observability & AI SRE Copilot SDK
 * Single-line Embed Script for Monitored Websites & Web Applications
 *
 * Usage:
 * <script src="http://localhost:8000/static/js/griffinops-sdk.js" data-api-key="gop_live_YOUR_KEY"></script>
 */
(function() {
  const currentScript = document.currentScript || Array.from(document.querySelectorAll('script')).pop();
  const apiKey = (currentScript && currentScript.getAttribute('data-api-key')) || 'gop_live_default';
  const serverUrl = (currentScript && currentScript.getAttribute('data-server')) || ((currentScript && currentScript.src) ? new URL(currentScript.src).origin : window.location.origin);

  console.log(`[GriffinOps SDK] Initialized for API Key: ${apiKey} (Server: ${serverUrl})`);

  function sendTelemetry(opts) {
    opts = opts || {};
    const navEntries = performance.getEntriesByType ? performance.getEntriesByType('navigation') : [];
    let loadTimeMs = 42.0;
    if (navEntries.length > 0 && navEntries[0].duration) {
      loadTimeMs = Math.max(2.0, Math.round(navEntries[0].duration));
    }
    if (opts.latency_ms) {
      loadTimeMs = opts.latency_ms;
    }

    const cleanUrl = window.location.href.split('#')[0];
    const payload = {
      api_key: apiKey,
      endpoint: opts.endpoint || cleanUrl,
      latency_ms: loadTimeMs,
      status_code: opts.status_code || 200,
      payload_bytes: opts.payload_bytes || (document.documentElement.innerHTML.length || 2048)
    };

    fetch(`${serverUrl}/api/v1/telemetry/ingest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-GriffinOps-API-Key': apiKey
      },
      body: JSON.stringify(payload)
    }).catch(function() {});
  }

  // 1. Send page load telemetry
  if (document.readyState === 'complete') {
    setTimeout(sendTelemetry, 500);
  } else {
    window.addEventListener('load', function() {
      setTimeout(sendTelemetry, 500);
    });
  }

  // 2. Capture Uncaught JavaScript Errors
  window.addEventListener('error', function(event) {
    sendTelemetry({
      status_code: 500,
      latency_ms: 120.0
    });
  });

  // 3. Periodic streaming heartbeat every 10 seconds
  setInterval(function() {
    sendTelemetry();
  }, 10000);

  // Global helper on window
  window.GriffinOps = {
    apiKey: apiKey,
    sendMetric: sendTelemetry
  };
})();
