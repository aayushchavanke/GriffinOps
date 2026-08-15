import time
import random
import threading
import requests
from typing import Dict, List, Optional

class DummyECommerceApp:
    """
    Real multi-tier E-Commerce Web Application.
    Processes live simulated user transactions and exposes real fault injection hooks.
    """
    def __init__(self):
        self.stats = {
            "checkout_count": 0,
            "payment_count": 0,
            "cart_count": 0,
            "recommendation_count": 0,
            "total_errors": 0
        }
        self.active_fault: Optional[dict] = None
        self.is_traffic_running = False
        self._traffic_thread = None
        self._memory_leak_buffers = []

    def start_background_traffic(self, base_url: str = "http://127.0.0.1:8000"):
        if self.is_traffic_running:
            return
        self.is_traffic_running = True
        self._traffic_thread = threading.Thread(target=self._traffic_loop, args=(base_url,), daemon=True)
        self._traffic_thread.start()

    def stop_background_traffic(self):
        self.is_traffic_running = False

    def _traffic_loop(self, base_url: str):
        endpoints = [
            "/dummy-store/products",
            "/dummy-store/recommendations",
            "/dummy-store/cart",
            "/dummy-store/checkout",
            "/dummy-store/payment"
        ]
        while self.is_traffic_running:
            try:
                ep = random.choice(endpoints)
                url = f"{base_url}{ep}"
                if ep in ["/dummy-store/products", "/dummy-store/recommendations"]:
                    requests.get(url, timeout=5.0)
                else:
                    requests.post(url, json={"user_id": f"usr_{random.randint(100, 999)}", "amount": 99.99}, timeout=5.0)
            except Exception:
                pass
            time.sleep(random.uniform(0.5, 1.5))

    def handle_products_request(self) -> dict:
        return {
            "status": "success",
            "products": [
                {"id": "p1", "name": "AI SRE Workstation Pro", "price": 2499.00},
                {"id": "p2", "name": "OpenTelemetry Sensor Node", "price": 149.00},
                {"id": "p3", "name": "SigNoz Observability License", "price": 499.00}
            ]
        }

    def handle_cart_request(self) -> dict:
        self.stats["cart_count"] += 1
        if self.active_fault and self.active_fault.get("fault_type") == "CART_REDIS_ERROR_STORM":
            self.stats["total_errors"] += 1
            time.sleep(0.4)
            return {"status": "error", "code": 500, "message": "Redis socket read timeout [Connection Refused]"}
        return {"status": "success", "cart_id": "cart_88392", "item_count": 3}

    def handle_checkout_request(self) -> dict:
        self.stats["checkout_count"] += 1
        if self.active_fault and self.active_fault.get("fault_type") == "CHECKOUT_LATENCY_CASCADE":
            # Simulate real DB pool bottleneck latency delay
            time.sleep(random.uniform(1.8, 3.2))
        else:
            time.sleep(random.uniform(0.02, 0.08))
        return {"status": "success", "order_id": f"ORD-{int(time.time())}", "total": 2648.00}

    def handle_payment_request(self) -> dict:
        self.stats["payment_count"] += 1
        if self.active_fault and self.active_fault.get("fault_type") == "PAYMENT_CPU_SATURATION":
            # Simulate CPU spin lock
            start = time.time()
            dummy_hash = 0
            while time.time() - start < 1.2:
                dummy_hash += sum(i * i for i in range(5000))
            time.sleep(0.5)
        else:
            time.sleep(random.uniform(0.04, 0.12))
        return {"status": "success", "transaction_id": f"TXN-{random.randint(10000, 99999)}", "paid": True}

    def handle_recommendation_request(self) -> dict:
        self.stats["recommendation_count"] += 1
        if self.active_fault and self.active_fault.get("fault_type") == "RECOMMENDATION_MEMORY_LEAK":
            # Allocate 5MB buffer in memory
            self._memory_leak_buffers.append(bytearray(5 * 1024 * 1024))
            time.sleep(random.uniform(0.3, 0.8))
        return {
            "status": "success",
            "recommended_item": "PyTorch Neural Copilot License",
            "allocated_heap_mb": len(self._memory_leak_buffers) * 5
        }

    def set_fault(self, fault_dict: Optional[dict]):
        self.active_fault = fault_dict
        if not fault_dict:
            self._memory_leak_buffers.clear()
