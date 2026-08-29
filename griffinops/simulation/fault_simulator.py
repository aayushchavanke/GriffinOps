import time
from typing import Optional, Dict

class FaultSimulatorManager:
    """
    Manages live fault injection into active GriffinOps target telemetry streams
    for testing pre-mortem alerts.
    """
    def __init__(self):
        self.active_fault: Optional[dict] = None
        self.fault_start_time: Optional[float] = None

    def inject_fault(self, target_service: str = "default-service", fault_type: str = "LATENCY_SPIKE") -> dict:
        scenario = {
            "name": f"Simulated Latency Spike on {target_service}",
            "target_service": target_service,
            "fault_type": fault_type,
            "description": f"Simulates latency degradation and HTTP error rate breach on {target_service}.",
            "affected_signals": ["latency_ms", "error_rate"]
        }
        self.active_fault = scenario
        self.fault_start_time = time.time()
        
        return {
            "status": "FAULT_INJECTED",
            "message": f"Successfully injected fault scenario on '{target_service}'.",
            "active_fault": scenario
        }

    def reset_fault(self) -> dict:
        previous = self.active_fault
        self.active_fault = None
        self.fault_start_time = None
        return {
            "status": "SYSTEM_RESET",
            "message": "All fault injections cleared. System telemetry restored to baseline operation.",
            "cleared_fault": previous
        }

    def get_status(self) -> dict:
        if not self.active_fault:
            return {"active": False, "fault": None}
            
        elapsed = round(time.time() - (self.fault_start_time or time.time()), 1)
        return {
            "active": True,
            "elapsed_seconds": elapsed,
            "fault": self.active_fault
        }
