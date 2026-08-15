import time
from typing import Optional, Dict

FAULT_SCENARIOS = {
    "CHECKOUT_LATENCY_CASCADE": {
        "name": "Checkout DB Connection Pool Exhaustion",
        "target_service": "checkoutservice",
        "fault_type": "CHECKOUT_LATENCY_CASCADE",
        "description": "Simulates database connection pool bottleneck in checkoutservice causing latency cascade.",
        "affected_signals": ["latency_ms", "cpu_percent"]
    },
    "PAYMENT_CPU_SATURATION": {
        "name": "Payment Service Crypto Hash Lock",
        "target_service": "paymentservice",
        "fault_type": "PAYMENT_CPU_SATURATION",
        "description": "Simulates CPU 100% saturation loop in payment processing.",
        "affected_signals": ["cpu_percent", "latency_ms"]
    },
    "RECOMMENDATION_MEMORY_LEAK": {
        "name": "Recommendation Unbounded Cache Heap Leak",
        "target_service": "recommendationservice",
        "fault_type": "RECOMMENDATION_MEMORY_LEAK",
        "description": "Simulates progressive RAM heap exhaustion in recommendationservice.",
        "affected_signals": ["memory_percent", "latency_ms"]
    },
    "CART_REDIS_ERROR_STORM": {
        "name": "Cart Service Redis Timeout Cascade",
        "target_service": "cartservice",
        "fault_type": "CART_REDIS_ERROR_STORM",
        "description": "Simulates Redis socket connection timeouts triggering 25% error rate storm.",
        "affected_signals": ["error_rate", "latency_ms"]
    }
}

class FaultSimulatorManager:
    """
    Manages live fault injection into GriffinOps microservice telemetry streams
    for panel demonstrations, testing, and pre-mortem verification.
    """
    def __init__(self):
        self.active_fault: Optional[dict] = None
        self.fault_start_time: Optional[float] = None

    def inject_fault(self, scenario_key: str) -> dict:
        if scenario_key not in FAULT_SCENARIOS:
            raise ValueError(f"Unknown fault scenario: {scenario_key}. Choose from {list(FAULT_SCENARIOS.keys())}")
            
        scenario = FAULT_SCENARIOS[scenario_key].copy()
        self.active_fault = scenario
        self.fault_start_time = time.time()
        
        return {
            "status": "FAULT_INJECTED",
            "message": f"Successfully injected fault scenario '{scenario['name']}' into service '{scenario['target_service']}'.",
            "active_fault": scenario
        }

    def reset_fault(self) -> dict:
        previous = self.active_fault
        self.active_fault = None
        self.fault_start_time = None
        return {
            "status": "SYSTEM_RESET",
            "message": "All synthetic fault injections cleared. System telemetry restored to baseline healthy operation.",
            "cleared_fault": previous
        }

    def get_status(self) -> dict:
        if not self.active_fault:
            return {"active": False, "fault": None}
            
        elapsed = round(time.time() - self.fault_start_time, 1)
        return {
            "active": True,
            "elapsed_seconds": elapsed,
            "fault": self.active_fault
        }
