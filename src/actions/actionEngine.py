
from datetime import datetime
from src.types.index import LLMDecision, ActionResult, WorkflowStatus
from src.state.stateManager import StateManager

class ActionEngine:
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager

    def execute(self, workflow_id: str, decision: LLMDecision) -> ActionResult:
        action = decision.suggested_action.lower()
        if action == "retry":
            self.state_manager.update_status(workflow_id, WorkflowStatus.RUNNING)
            msg = f"Retry triggered. Cause: {decision.root_cause}"
        elif action == "escalate":
            self.state_manager.update_status(workflow_id, WorkflowStatus.PAUSED)
            msg = f"Escalated to team. Cause: {decision.root_cause}"
        elif action == "compensate":
            self.state_manager.update_status(workflow_id, WorkflowStatus.PAUSED)
            msg = f"Compensating transaction run. Steps: {decision.corrective_steps}"
        else:
            msg = f"Skipped. Note: {decision.explanation}"
        print(f"  [ACTION] {action.upper()} -> {msg}")
        return ActionResult(action_taken=action, success=True, message=msg, timestamp=datetime.utcnow())
