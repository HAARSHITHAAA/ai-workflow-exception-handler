
from src.types.index import WorkflowEvent, AnomalySignal

REQUIRED_FIELDS = {
    "order.created":       ["order_id", "customer_id", "amount"],
    "payment.processed":   ["order_id", "payment_id", "amount", "status"],
    "inventory.checked":   ["order_id", "items"],
    "shipment.dispatched": ["order_id", "tracking_id", "carrier"],
    "order.completed":     ["order_id"],
    "workflow.failed":     ["order_id", "reason"],
}

def validate_schema(event: WorkflowEvent) -> AnomalySignal:
    required = REQUIRED_FIELDS.get(event.event_type, [])
    missing = [f for f in required if f not in event.payload]
    if missing:
        return AnomalySignal(detector="schema_validator", triggered=True, severity=0.9,
            message=f"Missing fields: {missing}", details={"missing_fields": missing})
    return AnomalySignal(detector="schema_validator", triggered=False, severity=0.0, message="Schema valid")