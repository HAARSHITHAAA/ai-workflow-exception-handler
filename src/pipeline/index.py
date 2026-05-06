from src.types.index import WorkflowEvent
from src.state.stateManager import StateManager
from src.state.deduplication import DeduplicationLayer
from src.detectors.schemaValidator import validate_schema
from src.detectors.volumeMonitor import VolumeMonitor
from src.detectors.sequenceChecker import check_sequence
from src.detectors.heartbeatTracker import HeartbeatTracker
from src.detectors.latencyProfiler import check_latency
from src.scoring.correlator import correlate
from src.llm.decisionLayer import get_llm_decision
from src.actions.actionEngine import ActionEngine
from src.actions.recoveryVerifier import verify_recovery
from src.dashboard.server import log_event, init_dashboard
from src.cloud.firestoreLogger import init_firestore, log_incident

class ExceptionHandlerPipeline:
    def __init__(self):
        self.state_manager  = StateManager()
        self.dedup          = DeduplicationLayer()
        self.volume_monitor = VolumeMonitor(window_seconds=60, max_events=50)
        self.heartbeat      = HeartbeatTracker(timeout_seconds=30)
        self.action_engine  = ActionEngine(self.state_manager)
        init_dashboard()
        init_firestore()
        print("  Dashboard: http://localhost:8501")

    def process(self, event: WorkflowEvent):
        print(f"\n{'='*60}")
        print(f"EVENT: {event.event_type} | workflow: {event.workflow_id}")
        print(f"{'='*60}")

        if self.dedup.is_duplicate(event):
            return None

        self.state_manager.record_event(event)

        signals = [
            validate_schema(event),
            self.volume_monitor.check(event),
            check_sequence(event, self.state_manager),
            self.heartbeat.check(event),
            check_latency(event),
        ]

        triggered = [s for s in signals if s.triggered]
        print(f"  Detectors fired: {len(triggered)}/{len(signals)}")
        for s in triggered:
            print(f"    WARNING {s.detector}: {s.message}")

        bundle = correlate(event, signals)
        print(f"  Overall severity: {bundle.overall_severity}/10")

        log_event("event", {
            "event_type": event.event_type,
            "workflow_id": event.workflow_id,
            "anomalies_found": len(triggered) > 0,
            "detectors_fired": len(triggered),
            "overall_severity": bundle.overall_severity,
            "warnings": [s.message for s in triggered]
        })

        if triggered:
            self.state_manager.increment_anomaly(event.workflow_id)
            decision = get_llm_decision(bundle, self.state_manager)
            print(f"\n  LLM Root Cause:  {decision.root_cause}")
            print(f"  LLM Action:      {decision.suggested_action} (confidence: {decision.confidence})")
            print(f"  LLM Explanation: {decision.explanation}")

            log_event("llm", {
                "root_cause": decision.root_cause,
                "suggested_action": decision.suggested_action,
                "confidence": decision.confidence,
                "explanation": decision.explanation,
                "corrective_steps": decision.corrective_steps
            })

            result = self.action_engine.execute(event.workflow_id, decision)
            print(f"\n  Action Result: {result.action_taken} -> {result.message}")

            recovery = verify_recovery(bundle, decision, result)
            print(f"  Recovery Status: {recovery.status} ({recovery.confidence:.2f}) -> {recovery.message}")

            log_event("action", {
                "action_taken": result.action_taken,
                "success": result.success,
                "message": result.message,
                "recovery_status": recovery.status,
                "recovery_confidence": recovery.confidence,
                "recovery_message": recovery.message
            })

            log_incident(bundle, decision, result, recovery)

            return {"bundle": bundle, "decision": decision, "result": result, "recovery": recovery}

        print("  OK No anomalies detected")
        return None



