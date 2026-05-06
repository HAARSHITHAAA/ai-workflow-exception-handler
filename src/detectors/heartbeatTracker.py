
from datetime import datetime
from typing import Dict
from src.types.index import WorkflowEvent, AnomalySignal

class HeartbeatTracker:
    def __init__(self, timeout_seconds=30):
        self.timeout_seconds = timeout_seconds
        self._last_seen: Dict[str, datetime] = {}

    def check(self, event: WorkflowEvent) -> AnomalySignal:
        now = datetime.utcnow()
        last = self._last_seen.get(event.workflow_id)
        self._last_seen[event.workflow_id] = now
        if last is None:
            return AnomalySignal(detector="heartbeat_tracker", triggered=False, severity=0.0, message="First event")
        gap = (now - last).total_seconds()
        if gap > self.timeout_seconds:
            return AnomalySignal(detector="heartbeat_tracker", triggered=True,
                severity=min(1.0, gap / (self.timeout_seconds * 3)),
                message=f"Gap: {gap:.1f}s (limit {self.timeout_seconds}s)")
        return AnomalySignal(detector="heartbeat_tracker", triggered=False, severity=0.0, message=f"Heartbeat OK")
