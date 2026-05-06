
from src.types.index import WorkflowEvent, AnomalySignal
from src.state.stateManager import StateManager

VALID_TRANSITIONS = {
    None:                  ["order.created"],
    "order.created":       ["inventory.checked", "payment.processed"],
    "inventory.checked":   ["payment.processed"],
    "payment.processed":   ["shipment.dispatched", "workflow.failed"],
    "shipment.dispatched": ["order.completed"],
    "order.completed":     [],
    "workflow.failed":     [],
}

def check_sequence(event: WorkflowEvent, state_manager: StateManager) -> AnomalySignal:
    history = state_manager.get_event_history(event.workflow_id)
    last = history[-2].event_type if len(history) >= 2 else None
    allowed = VALID_TRANSITIONS.get(last, [])
    if allowed and event.event_type not in allowed:
        return AnomalySignal(detector="sequence_checker", triggered=True, severity=0.8,
            message=f"Bad sequence: '{event.event_type}' after '{last}'",
            details={"expected": allowed, "got": event.event_type})
    return AnomalySignal(detector="sequence_checker", triggered=False, severity=0.0, message="Sequence valid")
