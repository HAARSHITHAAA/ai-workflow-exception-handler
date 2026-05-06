from datetime import datetime


def init_dashboard():
    print("  Streamlit dashboard: run python -m streamlit run src\\streamlit_dashboard.py")


def log_event(event_type, payload):
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    print(f"  [{timestamp}] {event_type}: {payload}")
