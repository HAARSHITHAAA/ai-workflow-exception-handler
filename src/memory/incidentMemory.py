import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Iterable, List, Set

from src.cloud.firestoreLogger import DB_PATH
from src.types.index import AnomalyBundle


@dataclass
class SimilarIncident:
    incident_id: int
    workflow_id: str
    timestamp: str
    severity: float
    detectors_fired: List[str]
    warnings: List[str]
    root_cause: str
    action_taken: str
    corrective_steps: List[str]
    action_result: str
    similarity: float


def retrieve_similar_incidents(bundle: AnomalyBundle, limit: int = 3, db_path: str = DB_PATH) -> List[SimilarIncident]:
    query_tokens = _bundle_tokens(bundle)
    if not query_tokens:
        return []

    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, workflow_id, timestamp, severity, detectors_fired, warnings,
                       root_cause, action_taken, corrective_steps, action_result
                FROM incidents
                ORDER BY id DESC
                LIMIT 100
                """
            ).fetchall()
    except sqlite3.Error:
        return []

    scored = []
    for row in rows:
        incident = _row_to_incident(row)
        incident_tokens = _incident_tokens(incident)
        similarity = _jaccard_similarity(query_tokens, incident_tokens)
        if similarity > 0:
            incident.similarity = round(similarity, 3)
            scored.append(incident)

    scored.sort(key=lambda item: (item.similarity, item.severity), reverse=True)
    return scored[:limit]


def format_incident_memory(incidents: Iterable[SimilarIncident]) -> str:
    lines = []
    for incident in incidents:
        lines.append(
            "- "
            f"incident #{incident.incident_id} "
            f"similarity={incident.similarity:.2f}, "
            f"severity={incident.severity}/10, "
            f"detectors={incident.detectors_fired}, "
            f"root_cause={incident.root_cause}, "
            f"action={incident.action_taken}, "
            f"result={incident.action_result}"
        )
    return "\n".join(lines) if lines else "No similar incidents found."


def _bundle_tokens(bundle: AnomalyBundle) -> Set[str]:
    triggered = [signal for signal in bundle.signals if signal.triggered]
    parts = [
        bundle.workflow_id,
        bundle.event.event_type,
        bundle.event.step_name or "",
        *[signal.detector for signal in triggered],
        *[signal.message for signal in triggered],
    ]
    return _tokenize(" ".join(parts))


def _incident_tokens(incident: SimilarIncident) -> Set[str]:
    parts = [
        incident.workflow_id,
        incident.root_cause,
        incident.action_taken,
        incident.action_result,
        *incident.detectors_fired,
        *incident.warnings,
        *incident.corrective_steps,
    ]
    return _tokenize(" ".join(parts))


def _jaccard_similarity(left: Set[str], right: Set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _row_to_incident(row) -> SimilarIncident:
    return SimilarIncident(
        incident_id=row[0],
        workflow_id=row[1],
        timestamp=row[2],
        severity=float(row[3] or 0),
        detectors_fired=_parse_json_list(row[4]),
        warnings=_parse_json_list(row[5]),
        root_cause=row[6] or "",
        action_taken=row[7] or "",
        corrective_steps=_parse_json_list(row[8]),
        action_result=row[9] or "",
        similarity=0.0,
    )


def _parse_json_list(value) -> List[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [str(value)]
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return [str(parsed)]


def _tokenize(text: str) -> Set[str]:
    stop_words = {
        "the", "and", "for", "with", "that", "this", "from", "into", "after",
        "before", "event", "events", "workflow", "severity", "limit", "found",
    }
    tokens = set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))
    return {token for token in tokens if len(token) > 2 and token not in stop_words}
