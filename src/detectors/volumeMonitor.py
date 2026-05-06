
from collections import deque
from datetime import datetime, timedelta
from src.types.index import WorkflowEvent, AnomalySignal

class VolumeMonitor:
    def __init__(self, window_seconds=60, max_events=100):
        self.window_seconds = window_seconds
        self.max_events = max_events
        self._timestamps = deque()

    def check(self, event: WorkflowEvent) -> AnomalySignal:
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.window_seconds)
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        self._timestamps.append(now)
        count = len(self._timestamps)
        if count > self.max_events:
            return AnomalySignal(detector="volume_monitor", triggered=True,
                severity=min(1.0, (count - self.max_events) / self.max_events),
                message=f"Volume surge: {count} events in {self.window_seconds}s")
        return AnomalySignal(detector="volume_monitor", triggered=False, severity=0.0, message=f"Volume OK: {count}")