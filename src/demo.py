import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
from src.types.index import WorkflowEvent
from src.pipeline.index import ExceptionHandlerPipeline

pipeline = ExceptionHandlerPipeline()
print("\n=== AI Workflow Exception Handler - Demo ===")
time.sleep(2)

pipeline.process(WorkflowEvent(
    event_id="e-001", event_type="order.created", workflow_id="wf-123",
    timestamp=datetime.utcnow(),
    payload={"order_id": "ORD-1", "customer_id": "C-99", "amount": 250},
    step_name="order_create", duration_ms=120))

time.sleep(2)

pipeline.process(WorkflowEvent(
    event_id="e-002", event_type="payment.processed", workflow_id="wf-123",
    timestamp=datetime.utcnow(),
    payload={"order_id": "ORD-1"},
    step_name="payment_process", duration_ms=4500))

time.sleep(2)

pipeline.process(WorkflowEvent(
    event_id="e-003", event_type="shipment.dispatched", workflow_id="wf-123",
    timestamp=datetime.utcnow(),
    payload={"order_id": "ORD-1", "tracking_id": "TRK-55", "carrier": "FedEx"},
    step_name="shipment_dispatch", duration_ms=800))

print("\n✅ Demo complete! Dashboard staying alive - refresh your browser!")
print("Press CTRL+C to stop.")
while True:
    time.sleep(1)
