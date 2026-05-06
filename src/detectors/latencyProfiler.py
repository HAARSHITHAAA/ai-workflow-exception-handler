
from src.types.index import WorkflowEvent, AnomalySignal

THRESHOLDS = {"order_create": 500, "payment_process": 2000, "inventory_check": 1000, "shipment_dispatch": 3000, "default": 1500}

def check_latency(event: WorkflowEvent) -> AnomalySignal:
    if event.duration_ms is None:
        return AnomalySignal(detector="latency_profiler", triggered=False, severity=0.0, message="No duration")
    step = event.step_name or "default"
    threshold = THRESHOLDS.get(step, THRESHOLDS["default"])
    if event.duration_ms > threshold:
        return AnomalySignal(detector="latency_profiler", triggered=True,
            severity=min(1.0, (event.duration_ms - threshold) / threshold),
            message=f"Spike: {event.duration_ms}ms on '{step}' (limit {threshold}ms)")
    return AnomalySignal(detector="latency_profiler", triggered=False, severity=0.0, message=f"Latency OK: {event.duration_ms}ms")
