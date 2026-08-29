/**
 * GriffinOps Real-Time Telemetry & Predictive Observability SDK
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
    const loadTimeMs = navEntries.length > 0 ? Math.max(1.0, Math.round(navEntries[0].duration)) : 42.0;
    const cleanUrl = window.location.href.split('#')[0];
    
    // 1. Auto-register site target in GriffinOps
    fetch(`${serverUrl}/api/v1/real-monitor/add-site`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-GriffinOps-API-Key': apiKey
      },
      body: JSON.stringify({
        name: document.title || 'Hosted Web Application',
        url: cleanUrl,
        site_type: window.location.protocol === 'file:' ? 'Local Web Document' : 'Hosted Web App'
      })
    }).catch(() => {});

    // 2. Ingest real measured browser latency into GriffinOps
    fetch(`${serverUrl}/api/v1/telemetry/ingest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-GriffinOps-API-Key': apiKey
      },
      body: JSON.stringify({
        api_key: apiKey,
        endpoint: cleanUrl,
        latency_ms: loadTimeMs,
        status_code: 200,
        payload_bytes: 4096
      })
    }).catch(() => {});
  }

  // Periodic heartbeat every 15s
  setInterval(sendTelemetry, 15000);
})();
