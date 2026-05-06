from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime

class WorkflowStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETED = "completed"

class WorkflowEvent(BaseModel):
    event_id: str
    event_type: str
    workflow_id: str
    timestamp: datetime
    payload: Dict[str, Any]
    step_name: Optional[str] = None
    duration_ms: Optional[float] = None

class AnomalySignal(BaseModel):
    detector: str
    triggered: bool
    severity: float
    message: str
    details: Dict[str, Any] = {}

class AnomalyBundle(BaseModel):
    workflow_id: str
    event: WorkflowEvent
    signals: List[AnomalySignal]
    overall_severity: float
    timestamp: datetime

class LLMDecision(BaseModel):
    root_cause: str
    confidence: float
    suggested_action: str
    explanation: str
    corrective_steps: List[str]

class ActionResult(BaseModel):
    action_taken: str
    success: bool
    message: str
    timestamp: datetime
