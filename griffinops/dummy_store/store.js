const PRODUCTS = [
  { id: "p1", icon: "💻", name: "AI SRE Workstation Pro", price: 2499.00, desc: "Liquid-cooled PyTorch acceleration node with 64GB VRAM." },
  { id: "p2", icon: "📡", name: "OpenTelemetry Sensor Node", price: 149.00, desc: "Hardware metrics collector node for SigNoz & Jaeger streams." },
  { id: "p3", icon: "🦅", name: "GriffinOps Copilot License", price: 499.00, desc: "Enterprise predictive observability & RCAEval causal diagnostic engine." },
  { id: "p4", icon: "🧠", name: "Neural TCN Accelerator Card", price: 899.00, desc: "Dedicated FPGA card for real-time 1D dilated convolutions." }
];

let cart = [];

document.addEventListener("DOMContentLoaded", () => {
  renderProducts();
});

function renderProducts() {
  const container = document.getElementById("products-container");
  if (!container) return;
  container.innerHTML = "";
  PRODUCTS.forEach(p => {
    const div = document.createElement("div");
    div.className = "product-card";
    div.innerHTML = `
      <div class="product-img">${p.icon}</div>
      <div class="product-title">${p.name}</div>
      <div class="product-desc">${p.desc}</div>
      <div class="product-price">$${p.price.toFixed(2)}</div>
      <button class="btn-add-cart" onclick="addToCart('${p.id}')">Add to Cart</button>
    `;
    container.appendChild(div);
  });
}

function addToCart(productId) {
  const item = PRODUCTS.find(p => p.id === productId);
  if (item) {
    cart.push(item);
    updateCartUI();
    showStoreToast(`🛒 Added ${item.name} to cart`);
  }
}

function updateCartUI() {
  document.getElementById("cart-count").innerText = cart.length;
  const total = cart.reduce((sum, item) => sum + item.price, 0);
  document.getElementById("cart-total").innerText = total.toFixed(2);
  
  const body = document.getElementById("cart-body");
  if (cart.length === 0) {
    body.innerHTML = `<p class="empty-msg">Your shopping cart is empty.</p>`;
  } else {
    body.innerHTML = cart.map(i => `<div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:13px;"><span>${i.name}</span><strong>$${i.price.toFixed(2)}</strong></div>`).join("");
  }
}

function openCart() { document.getElementById("cart-modal").style.display = "flex"; }
function closeCart() { document.getElementById("cart-modal").style.display = "none"; }

function proceedToCheckout() {
  if (cart.length === 0) {
    showStoreToast("Your cart is empty!");
    return;
  }
  closeCart();
  document.getElementById("checkout-modal").style.display = "flex";
  document.getElementById("checkout-status-msg").innerText = "";
}

function closeCheckout() { document.getElementById("checkout-modal").style.display = "none"; }

async function executePayment() {
  const btn = document.getElementById("btn-pay-now");
  const statusDiv = document.getElementById("checkout-status-msg");
  btn.disabled = true;
  statusDiv.innerHTML = `<span style="color:#58a6ff;">Connecting to <code>/api/checkout</code> & <code>/api/payment</code>...</span>`;

  try {
    const chkResp = await fetch("/dummy-store/checkout", { method: "POST" });
    const chkData = await chkResp.json();
    
    const payResp = await fetch("/dummy-store/payment", { method: "POST" });
    const payData = await payResp.json();

    statusDiv.innerHTML = `<span style="color:#3fb950;">✅ Transaction Complete! Order ID: ${chkData.order_id}</span>`;
    cart = [];
    updateCartUI();
    setTimeout(closeCheckout, 2000);
  } catch (err) {
    statusDiv.innerHTML = `<span style="color:#f85149;">❌ Transaction Failure: Microservice Timeout / Error Cascade!</span>`;
  } finally {
    btn.disabled = false;
  }
}

async function injectStoreFault(scenarioKey) {
  try {
    const resp = await fetch("/api/v1/fault/inject", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario_key: scenarioKey })
    });
    const data = await resp.json();
    showStoreToast(`⚡ SRE Fault Injected: ${scenarioKey}`);
  } catch (err) {
    showStoreToast("Fault injection error");
  }
}

async function resetStoreFault() {
  try {
    const resp = await fetch("/api/v1/fault/reset", { method: "POST" });
    showStoreToast("🟢 Telemetry baseline restored.");
  } catch (err) {
    showStoreToast("Reset error");
  }
}

function showStoreToast(msg) {
  const toast = document.getElementById("store-toast");
  if (!toast) return;
  toast.innerText = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3000);
}
