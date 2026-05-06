import json
import os

from dotenv import load_dotenv
from groq import Groq

from src.memory.incidentMemory import format_incident_memory, retrieve_similar_incidents
from src.state.stateManager import StateManager
from src.types.index import AnomalyBundle, LLMDecision

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def build_prompt(bundle: AnomalyBundle, state_manager: StateManager, memory_db_path=None) -> str:
    state = state_manager.get_or_create(bundle.workflow_id)
    triggered = [s for s in bundle.signals if s.triggered]
    history_types = [e.event_type for e in state.events[-10:]]
    signals_text = "\n".join(
        f"- [{s.detector}] severity={s.severity:.2f}: {s.message}" for s in triggered
    )
    similar_incidents = retrieve_similar_incidents(bundle, db_path=memory_db_path) if memory_db_path else retrieve_similar_incidents(bundle)
    incident_memory = format_incident_memory(similar_incidents)

    return f"""You are an AI workflow exception handler. Respond ONLY with a JSON object, no markdown, no extra text.

WORKFLOW ID: {bundle.workflow_id}
SEVERITY: {bundle.overall_severity}/10
HISTORY: {history_types}
ANOMALIES:
{signals_text}

SIMILAR PAST INCIDENTS:
{incident_memory}

Use similar past incidents as guidance, but do not copy them blindly. Prefer actions that worked for comparable detector patterns.

Respond ONLY with this exact JSON:
{{
  "root_cause": "one sentence root cause",
  "confidence": 0.85,
  "suggested_action": "retry",
  "explanation": "2-3 sentence explanation",
  "corrective_steps": ["step 1", "step 2", "step 3"]
}}
suggested_action must be one of: retry, escalate, compensate, skip"""


def get_llm_decision(bundle: AnomalyBundle, state_manager: StateManager) -> LLMDecision:
    if bundle.overall_severity < 3.0:
        return LLMDecision(
            root_cause="Minor anomaly",
            confidence=1.0,
            suggested_action="skip",
            explanation="Severity below threshold.",
            corrective_steps=["Monitor and continue"],
        )
    try:
        prompt = build_prompt(bundle, state_manager)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        data = json.loads(raw)
        return LLMDecision(**data)
    except Exception as e:
        print(f"  [LLM ERROR] {e}")
        return LLMDecision(
            root_cause="LLM error",
            confidence=0.5,
            suggested_action="escalate",
            explanation=f"Error: {e}",
            corrective_steps=["Manually review"],
        )

