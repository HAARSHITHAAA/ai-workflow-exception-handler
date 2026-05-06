from dataclasses import dataclass
from datetime import datetime

from src.types.index import ActionResult, AnomalyBundle, LLMDecision


@dataclass
class RecoveryVerification:
    status: str
    confidence: float
    checked_at: datetime
    message: str


def verify_recovery(bundle: AnomalyBundle, decision: LLMDecision, result: ActionResult) -> RecoveryVerification:
    action = result.action_taken.lower()
    triggered = [signal for signal in bundle.signals if signal.triggered]
    detector_names = {signal.detector for signal in triggered}

    if not result.success:
        return RecoveryVerification(
            status="still_failing",
            confidence=0.9,
            checked_at=datetime.utcnow(),
            message="Remediation action failed, so the incident still needs intervention.",
        )

    if action == "retry":
        confidence = 0.72
        if "schema_validator" in detector_names:
            confidence = 0.55
        return RecoveryVerification(
            status="recovered" if confidence >= 0.7 else "needs_human_review",
            confidence=confidence,
            checked_at=datetime.utcnow(),
            message=(
                "Retry action completed. Recovery is likely for transient failures."
                if confidence >= 0.7
                else "Retry completed, but schema-related anomalies need payload verification."
            ),
        )

    if action == "compensate":
        return RecoveryVerification(
            status="recovered",
            confidence=0.78,
            checked_at=datetime.utcnow(),
            message="Compensation action completed and workflow state was contained.",
        )

    if action == "escalate":
        return RecoveryVerification(
            status="needs_human_review",
            confidence=0.86,
            checked_at=datetime.utcnow(),
            message="Incident was paused and escalated for manual review.",
        )

    return RecoveryVerification(
        status="not_attempted",
        confidence=1.0,
        checked_at=datetime.utcnow(),
        message=f"No autonomous recovery was attempted for action '{decision.suggested_action}'.",
    )
