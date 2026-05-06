from datetime import datetime

import pytest

from src.detectors.latencyProfiler import check_latency
from src.detectors.schemaValidator import validate_schema
from src.detectors.sequenceChecker import check_sequence
from src.detectors.volumeMonitor import VolumeMonitor
from src.state.stateManager import StateManager
from src.types.index import WorkflowEvent


def make_event(event_type="order.created", workflow_id="wf-test", payload=None, step_name=None, duration_ms=None):
    return WorkflowEvent(
        event_id=f"event-{event_type}",
        event_type=event_type,
        workflow_id=workflow_id,
        timestamp=datetime(2026, 1, 1, 12, 0, 0),
        payload=payload or {},
        step_name=step_name,
        duration_ms=duration_ms,
    )


def test_schema_validator_accepts_valid_event():
    event = make_event(
        payload={"order_id": "ORD-1", "customer_id": "C-1", "amount": 250}
    )

    signal = validate_schema(event)

    assert signal.detector == "schema_validator"
    assert signal.triggered is False
    assert signal.severity == 0.0


def test_schema_validator_flags_missing_required_fields():
    event = make_event(event_type="payment.processed", payload={"order_id": "ORD-1"})

    signal = validate_schema(event)

    assert signal.triggered is True
    assert signal.severity == 0.9
    assert signal.details["missing_fields"] == ["payment_id", "amount", "status"]
    assert "Missing fields" in signal.message


def test_latency_profiler_flags_slow_step():
    event = make_event(step_name="payment_process", duration_ms=4500)

    signal = check_latency(event)

    assert signal.detector == "latency_profiler"
    assert signal.triggered is True
    assert signal.severity == pytest.approx(1.0)
    assert "payment_process" in signal.message


def test_latency_profiler_accepts_fast_step():
    event = make_event(step_name="order_create", duration_ms=120)

    signal = check_latency(event)

    assert signal.triggered is False
    assert signal.message == "Latency OK: 120.0ms"


def test_volume_monitor_flags_events_above_threshold():
    monitor = VolumeMonitor(window_seconds=60, max_events=2)
    event = make_event(payload={"order_id": "ORD-1", "customer_id": "C-1", "amount": 250})

    assert monitor.check(event).triggered is False
    assert monitor.check(event).triggered is False
    signal = monitor.check(event)

    assert signal.detector == "volume_monitor"
    assert signal.triggered is True
    assert signal.severity == pytest.approx(0.5)
    assert "Volume surge" in signal.message


def test_sequence_checker_accepts_valid_transition():
    state = StateManager()
    first = make_event(payload={"order_id": "ORD-1", "customer_id": "C-1", "amount": 250})
    second = make_event(
        event_type="payment.processed",
        payload={"order_id": "ORD-1", "payment_id": "P-1", "amount": 250, "status": "paid"},
    )

    state.record_event(first)
    state.record_event(second)
    signal = check_sequence(second, state)

    assert signal.triggered is False
    assert signal.message == "Sequence valid"


def test_sequence_checker_flags_invalid_transition():
    state = StateManager()
    first = make_event(payload={"order_id": "ORD-1", "customer_id": "C-1", "amount": 250})
    second = make_event(
        event_type="shipment.dispatched",
        payload={"order_id": "ORD-1", "tracking_id": "TRK-1", "carrier": "FedEx"},
    )

    state.record_event(first)
    state.record_event(second)
    signal = check_sequence(second, state)

    assert signal.detector == "sequence_checker"
    assert signal.triggered is True
    assert signal.severity == 0.8
    assert signal.details["expected"] == ["inventory.checked", "payment.processed"]
    assert signal.details["got"] == "shipment.dispatched"
