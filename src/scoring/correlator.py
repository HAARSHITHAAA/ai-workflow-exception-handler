
from datetime import datetime
from typing import List
from src.types.index import AnomalySignal, AnomalyBundle, WorkflowEvent

WEIGHTS = {"schema_validator": 1.0, "sequence_checker": 0.9, "heartbeat_tracker": 0.7, "latency_profiler": 0.6, "volume_monitor": 0.5}

def correlate(event: WorkflowEvent, signals: List[AnomalySignal]) -> AnomalyBundle:
    triggered = [s for s in signals if s.triggered]
    if not triggered:
        overall = 0.0
    else:
        weighted_sum = sum(s.severity * WEIGHTS.get(s.detector, 0.5) for s in triggered)
        weight_total = sum(WEIGHTS.get(s.detector, 0.5) for s in triggered)
        overall = min(10.0, (weighted_sum / weight_total) * 10)
    return AnomalyBundle(workflow_id=event.workflow_id, event=event, signals=signals,
        overall_severity=round(overall, 2), timestamp=datetime.utcnow())
