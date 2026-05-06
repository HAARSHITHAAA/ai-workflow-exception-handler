import json
import sqlite3
from datetime import datetime

from src.llm.decisionLayer import build_prompt
from src.memory.incidentMemory import format_incident_memory, retrieve_similar_incidents
from src.scoring.correlator import correlate
from src.state.stateManager import StateManager
from src.types.index import AnomalySignal, WorkflowEvent


def make_event():
    return WorkflowEvent(
        event_id="event-1",
        event_type="payment.processed",
        workflow_id="wf-current",
        timestamp=datetime(2026, 1, 1, 12, 0, 0),
        payload={"order_id": "ORD-1"},
        step_name="payment_process",
        duration_ms=4500,
    )


def make_bundle():
    event = make_event()
    signals = [
        AnomalySignal(
            detector="schema_validator",
            triggered=True,
            severity=0.9,
            message="Missing fields: ['payment_id', 'amount', 'status']",
        ),
        AnomalySignal(
            detector="latency_profiler",
            triggered=True,
            severity=1.0,
            message="Spike: 4500ms on 'payment_process' (limit 2000ms)",
        ),
    ]
    return correlate(event, signals)


def create_incident_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT,
                timestamp TEXT,
                severity REAL,
                detectors_fired TEXT,
                warnings TEXT,
                root_cause TEXT,
                action_taken TEXT,
                confidence REAL,
                corrective_steps TEXT,
                action_result TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO incidents VALUES (NULL,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "wf-old",
                "2026-01-01T11:00:00",
                9.2,
                json.dumps(["schema_validator", "latency_profiler"]),
                json.dumps([
                    "Missing fields: ['payment_id', 'amount', 'status']",
                    "Spike: 4100ms on payment_process",
                ]),
                "Payment event was missing required fields and payment processing was slow.",
                "retry",
                0.88,
                json.dumps(["Retry payment step", "Verify payment payload"]),
                "Retry triggered successfully",
            ),
        )
        conn.execute(
            """
            INSERT INTO incidents VALUES (NULL,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "wf-other",
                "2026-01-01T10:00:00",
                4.1,
                json.dumps(["volume_monitor"]),
                json.dumps(["Volume surge in inventory events"]),
                "Inventory volume increased.",
                "skip",
                0.7,
                json.dumps(["Monitor traffic"]),
                "Skipped",
            ),
        )
        conn.commit()


def test_retrieve_similar_incidents_returns_best_matches(tmp_path):
    db_path = tmp_path / "incidents.db"
    create_incident_db(db_path)

    incidents = retrieve_similar_incidents(make_bundle(), limit=1, db_path=str(db_path))

    assert len(incidents) == 1
    assert incidents[0].workflow_id == "wf-old"
    assert incidents[0].action_taken == "retry"
    assert incidents[0].similarity > 0


def test_format_incident_memory_includes_operational_context(tmp_path):
    db_path = tmp_path / "incidents.db"
    create_incident_db(db_path)
    incidents = retrieve_similar_incidents(make_bundle(), limit=1, db_path=str(db_path))

    memory_text = format_incident_memory(incidents)

    assert "incident #1" in memory_text
    assert "action=retry" in memory_text
    assert "Retry triggered successfully" in memory_text


def test_build_prompt_includes_similar_incident_memory(tmp_path):
    db_path = tmp_path / "incidents.db"
    create_incident_db(db_path)

    state_manager = StateManager()
    state_manager.record_event(make_event())
    prompt = build_prompt(make_bundle(), state_manager, memory_db_path=str(db_path))

    assert "SIMILAR PAST INCIDENTS" in prompt
    assert "incident #1" in prompt
    assert "action=retry" in prompt

