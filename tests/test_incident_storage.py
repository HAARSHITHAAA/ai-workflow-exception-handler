import sqlite3

import src.cloud.firestoreLogger as logger


def test_init_firestore_adds_triage_columns_to_existing_database(tmp_path, monkeypatch):
    db_path = tmp_path / "incidents.db"
    with sqlite3.connect(db_path) as conn:
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
        conn.commit()

    monkeypatch.setattr(logger, "DB_PATH", str(db_path))
    logger.init_firestore(verbose=False)

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(incidents)").fetchall()}

    assert "triage_status" in columns
    assert "triage_note" in columns
    assert "manual_action" in columns
    assert "triage_updated_at" in columns


def test_update_incident_triage_persists_status_note_and_manual_action(tmp_path, monkeypatch):
    db_path = tmp_path / "incidents.db"
    monkeypatch.setattr(logger, "DB_PATH", str(db_path))
    logger.init_firestore(verbose=False)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO incidents (
                workflow_id, timestamp, severity, detectors_fired, warnings,
                root_cause, action_taken, confidence, corrective_steps, action_result
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "wf-test",
                "2026-01-01T12:00:00",
                8.5,
                "[]",
                "[]",
                "Latency spike",
                "retry",
                0.8,
                "[]",
                "Retry triggered",
            ),
        )
        conn.commit()

    logger.update_incident_triage(1, "investigating", "Checking payment payload", "escalate")

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT triage_status, triage_note, manual_action, triage_updated_at FROM incidents WHERE id = 1"
        ).fetchone()

    assert row[0] == "investigating"
    assert row[1] == "Checking payment payload"
    assert row[2] == "escalate"
    assert row[3]
