from datetime import datetime

from src.actions.recoveryVerifier import verify_recovery
from src.types.index import ActionResult, AnomalyBundle, AnomalySignal, LLMDecision, WorkflowEvent


def make_bundle(detector="latency_profiler"):
    event = WorkflowEvent(
        event_id="event-1",
        event_type="payment.processed",
        workflow_id="wf-test",
        timestamp=datetime(2026, 1, 1, 12, 0, 0),
        payload={"order_id": "ORD-1"},
        step_name="payment_process",
        duration_ms=4500,
    )
    return AnomalyBundle(
        workflow_id="wf-test",
        event=event,
        signals=[AnomalySignal(detector=detector, triggered=True, severity=1.0, message="Triggered")],
        overall_severity=8.5,
        timestamp=datetime.utcnow(),
    )


def make_decision(action="retry"):
    return LLMDecision(
        root_cause="Transient payment failure",
        confidence=0.85,
        suggested_action=action,
        explanation="Retry should recover the workflow.",
        corrective_steps=["Retry payment step"],
    )


def make_result(action="retry", success=True):
    return ActionResult(
        action_taken=action,
        success=success,
        message="Action completed",
        timestamp=datetime.utcnow(),
    )


def test_retry_recovery_is_marked_recovered_for_transient_detector():
    recovery = verify_recovery(make_bundle(), make_decision("retry"), make_result("retry"))

    assert recovery.status == "recovered"
    assert recovery.confidence >= 0.7
    assert "Retry action completed" in recovery.message


def test_schema_retry_needs_human_payload_review():
    recovery = verify_recovery(
        make_bundle("schema_validator"),
        make_decision("retry"),
        make_result("retry"),
    )

    assert recovery.status == "needs_human_review"
    assert recovery.confidence < 0.7
    assert "payload verification" in recovery.message


def test_failed_action_is_still_failing():
    recovery = verify_recovery(make_bundle(), make_decision("retry"), make_result("retry", success=False))

    assert recovery.status == "still_failing"
    assert recovery.confidence == 0.9


def test_escalation_needs_human_review():
    recovery = verify_recovery(make_bundle(), make_decision("escalate"), make_result("escalate"))

    assert recovery.status == "needs_human_review"
    assert "manual review" in recovery.message
