from datetime import datetime
from typing import Dict, List
from src.types.index import WorkflowEvent, WorkflowStatus

class WorkflowState:
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.status = WorkflowStatus.RUNNING
        self.events: List[WorkflowEvent] = []
        self.step_timings: Dict[str, float] = {}
        self.event_counts: Dict[str, int] = {}
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.anomaly_count = 0

class StateManager:
    def __init__(self):
        self._store: Dict[str, WorkflowState] = {}

    def get_or_create(self, workflow_id: str) -> WorkflowState:
        if workflow_id not in self._store:
            self._store[workflow_id] = WorkflowState(workflow_id)
        return self._store[workflow_id]

    def record_event(self, event: WorkflowEvent) -> WorkflowState:
        state = self.get_or_create(event.workflow_id)
        state.events.append(event)
        state.updated_at = datetime.utcnow()
        state.event_counts[event.event_type] = state.event_counts.get(event.event_type, 0) + 1
        if event.step_name and event.duration_ms:
            state.step_timings[event.step_name] = event.duration_ms
        return state

    def update_status(self, workflow_id: str, status: WorkflowStatus):
        state = self.get_or_create(workflow_id)
        state.status = status
        state.updated_at = datetime.utcnow()

    def increment_anomaly(self, workflow_id: str):
        self.get_or_create(workflow_id).anomaly_count += 1

    def get_event_history(self, workflow_id: str) -> List[WorkflowEvent]:
        return self.get_or_create(workflow_id).events
