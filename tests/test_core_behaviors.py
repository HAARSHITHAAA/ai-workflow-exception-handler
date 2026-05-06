from datetime import datetime

import pytest

from src.actions.actionEngine import ActionEngine
from src.scoring.correlator import correlate
from src.state.deduplication import DeduplicationLayer
from src.state.stateManager import StateManager
from src.types.index import AnomalySignal, LLMDecision, WorkflowEvent, WorkflowStatus


def make_event(event_id="event-1", event_type="order.created", workflow_id="wf-test"):
    return WorkflowEvent(
        event_id=event_id,
        event_type=event_type,
        workflow_id=workflow_id,
        timestamp=datetime(2026, 1, 1, 12, 0, 0),
        payload={"order_id": "ORD-1", "customer_id": "C-1", "amount": 250},
        step_name="order_create",
        duration_ms=100,
    )


def make_decision(action="retry"):
    return LLMDecision(
        root_cause="Payment latency spike",
        confidence=0.86,
        suggested_action=action,
        explanation="The workflow slowed during payment processing.",
        corrective_steps=["Retry failed payment step", "Monitor downstream events"],
    )


def test_correlator_returns_zero_when_no_signals_triggered():
    event = make_event()
    signals = [
        AnomalySignal(detector="schema_validator", triggered=False, severity=0.0, message="OK"),
        AnomalySignal(detector="latency_profiler", triggered=False, severity=0.0, message="OK"),
    ]

    bundle = correlate(event, signals)

    assert bundle.workflow_id == event.workflow_id
    assert bundle.overall_severity == 0.0
    assert bundle.signals == signals


def test_correlator_uses_weighted_triggered_signal_average():
    event = make_event()
    signals = [
        AnomalySignal(detector="schema_validator", triggered=True, severity=0.9, message="Missing"),
        AnomalySignal(detector="latency_profiler", triggered=True, severity=1.0, message="Slow"),
        AnomalySignal(detector="volume_monitor", triggered=False, severity=1.0, message="Ignored"),
    ]

    bundle = correlate(event, signals)

    expected = round(((0.9 * 1.0) + (1.0 * 0.6)) / (1.0 + 0.6) * 10, 2)
    assert bundle.overall_severity == pytest.approx(expected)


def test_state_manager_records_events_and_timings():
    state_manager = StateManager()
    event = make_event()

    state = state_manager.record_event(event)

    assert state.workflow_id == "wf-test"
    assert state.events == [event]
    assert state.event_counts["order.created"] == 1
    assert state.step_timings["order_create"] == 100


def test_deduplication_layer_drops_same_workflow_event_type_and_second():
    dedup = DeduplicationLayer()
    first = make_event(event_id="event-1")
    duplicate = make_event(event_id="event-2")

    assert dedup.is_duplicate(first) is False
    assert dedup.is_duplicate(duplicate) is True


def test_action_engine_retry_sets_workflow_running():
    state_manager = StateManager()
    engine = ActionEngine(state_manager)

    result = engine.execute("wf-test", make_decision("retry"))

    assert result.action_taken == "retry"
    assert result.success is True
    assert state_manager.get_or_create("wf-test").status == WorkflowStatus.RUNNING
    assert "Retry triggered" in result.message


def test_action_engine_escalate_pauses_workflow():
    state_manager = StateManager()
    engine = ActionEngine(state_manager)

    result = engine.execute("wf-test", make_decision("escalate"))

    assert result.action_taken == "escalate"
    assert state_manager.get_or_create("wf-test").status == WorkflowStatus.PAUSED
    assert "Escalated" in result.message
