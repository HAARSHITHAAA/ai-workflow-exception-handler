import hashlib
from typing import Set
from src.types.index import WorkflowEvent

class DeduplicationLayer:
    def __init__(self):
        self._seen_keys: Set[str] = set()

    def _make_key(self, event: WorkflowEvent) -> str:
        raw = f"{event.workflow_id}:{event.event_type}:{event.timestamp.strftime('%Y%m%d%H%M%S')}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def is_duplicate(self, event: WorkflowEvent) -> bool:
        key = self._make_key(event)
        if key in self._seen_keys:
            print(f"  [DEDUP] Duplicate dropped: {event.event_id}")
            return True
        self._seen_keys.add(key)
        return False