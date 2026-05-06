import json
import sqlite3
from datetime import datetime

DB_PATH = "incidents.db"
EXTRA_COLUMNS = {
    "recovery_status": "TEXT DEFAULT 'unknown'",
    "recovery_confidence": "REAL DEFAULT 0",
    "recovery_message": "TEXT DEFAULT ''",
    "triage_status": "TEXT DEFAULT 'open'",
    "triage_note": "TEXT DEFAULT ''",
    "manual_action": "TEXT DEFAULT ''",
    "triage_updated_at": "TEXT DEFAULT ''",
}


def init_firestore(verbose=True):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
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
            action_result TEXT,
            recovery_status TEXT DEFAULT 'unknown',
            recovery_confidence REAL DEFAULT 0,
            recovery_message TEXT DEFAULT '',
            triage_status TEXT DEFAULT 'open',
            triage_note TEXT DEFAULT '',
            manual_action TEXT DEFAULT '',
            triage_updated_at TEXT DEFAULT ''
        )
    """)
    ensure_incident_columns(conn)
    conn.commit()
    conn.close()
    if verbose:
        print("  Storage connected! (SQLite local DB)")


def log_incident(bundle, decision, result, recovery=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        ensure_incident_columns(conn)
        recovery_status = recovery.status if recovery else "unknown"
        recovery_confidence = recovery.confidence if recovery else 0
        recovery_message = recovery.message if recovery else "Recovery verification was not run."
        conn.execute("""
            INSERT INTO incidents (
                workflow_id, timestamp, severity, detectors_fired, warnings,
                root_cause, action_taken, confidence, corrective_steps, action_result,
                recovery_status, recovery_confidence, recovery_message,
                triage_status, triage_note, manual_action, triage_updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            bundle.workflow_id,
            datetime.utcnow().isoformat(),
            bundle.overall_severity,
            json.dumps([s.detector for s in bundle.signals if s.triggered]),
            json.dumps([s.message for s in bundle.signals if s.triggered]),
            decision.root_cause,
            decision.suggested_action,
            decision.confidence,
            json.dumps(decision.corrective_steps),
            result.message,
            recovery_status,
            recovery_confidence,
            recovery_message,
            "open",
            "",
            "",
            "",
        ))
        conn.commit()
        conn.close()
        print("  Incident saved to local database!")
    except Exception as e:
        print(f"  [DB ERROR] {e}")


def update_incident_triage(incident_id, triage_status, triage_note, manual_action):
    with sqlite3.connect(DB_PATH) as conn:
        ensure_incident_columns(conn)
        conn.execute(
            """
            UPDATE incidents
            SET triage_status = ?, triage_note = ?, manual_action = ?, triage_updated_at = ?
            WHERE id = ?
            """,
            (
                triage_status,
                triage_note,
                manual_action,
                datetime.utcnow().isoformat(timespec="seconds"),
                incident_id,
            ),
        )
        conn.commit()


def ensure_incident_columns(conn):
    existing = {row[1] for row in conn.execute("PRAGMA table_info(incidents)").fetchall()}
    for column, definition in EXTRA_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE incidents ADD COLUMN {column} {definition}")
