import json
import sqlite3
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.cloud.firestoreLogger import init_firestore, update_incident_triage


DB_PATH = "incidents.db"
SEVERITY_LABELS = {
    "Low": (0, 3),
    "Medium": (4, 6),
    "Critical": (7, 10),
}
RECOVERY_STATUS_COLORS = {
    "recovered": "#2f9e73",
    "needs_human_review": "#d97706",
    "still_failing": "#dc2626",
    "not_attempted": "#64748b",
    "unknown": "#94a3b8",
}
PLOT_THEME = {
    "paper_bgcolor": "#ffffff",
    "plot_bgcolor": "#ffffff",
    "font_color": "#1f2937",
    "margin": dict(l=12, r=12, t=28, b=12),
}


st.set_page_config(
    page_title="AI Workflow Exception Handler",
    page_icon="🔥",
    layout="wide",
)

st.markdown(
    """
<style>
    .stApp { background: #f7fbff; color: #1f2937; }
    .block-container { padding-top: 3rem; }
    h1, h2, h3, h4, h5, h6, p, label, div, span { color: #1f2937; }
    [data-testid="stSidebar"] {
        background: #eef7f4;
        border-right: 1px solid #cfe6df;
    }
    [data-testid="stSidebar"] * { color: #1f2937; }
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #ffffff 0%, #f0f7ff 100%);
        border: 1px solid #cfe0f5;
        border-radius: 8px;
        padding: 14px;
        box-shadow: 0 8px 24px rgba(69, 88, 115, .08);
    }
    [data-testid="stMetricValue"] { color: #172033; font-size: 1.65rem; }
    [data-testid="stMetricLabel"] { color: #526173; }
    [data-testid="stMetricDelta"] { color: #177245; }
    div[data-testid="stExpander"] {
        background: #ffffff;
        border: 1px solid #d7e4f2;
        border-radius: 8px;
    }
    div[data-testid="stDataFrame"], div[data-testid="stPlotlyChart"] {
        background: #ffffff;
        border: 1px solid #d7e4f2;
        border-radius: 8px;
        padding: 8px;
        box-shadow: 0 8px 24px rgba(69, 88, 115, .07);
    }
    .stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid #d7e4f2; }
    .stTabs [data-baseweb="tab"] { color: #526173; }
    .stTabs [aria-selected="true"] { color: #0f766e; }
    .status-pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        font-weight: 700;
        font-size: .78rem;
        border: 1px solid rgba(31,41,55,.12);
    }
    .pill-critical { background: #ffe1e1; color: #9f1239; }
    .pill-medium { background: #fff1c7; color: #92400e; }
    .pill-low { background: #dcfce7; color: #166534; }
    .detail-box {
        border: 1px solid #d7e4f2;
        border-radius: 8px;
        padding: 14px;
        background: #ffffff;
        min-height: 112px;
        box-shadow: 0 8px 24px rgba(69, 88, 115, .07);
    }
    button[kind="primary"], .stDownloadButton button, .stButton button {
        border-radius: 8px;
        border: 1px solid #b9d9ed;
        background: #e8f6ff;
        color: #164e63;
    }
</style>
""",
    unsafe_allow_html=True,
)


def parse_json_list(value):
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [str(value)]
    return parsed if isinstance(parsed, list) else [parsed]


def get_severity_band(severity):
    if severity >= 7:
        return "Critical"
    if severity >= 4:
        return "Medium"
    return "Low"


@st.cache_data(ttl=3)
def load_incidents():
    base_columns = [
        "id",
        "workflow_id",
        "timestamp",
        "severity",
        "detectors_fired",
        "warnings",
        "root_cause",
        "action_taken",
        "confidence",
        "corrective_steps",
        "action_result",
        "recovery_status",
        "recovery_confidence",
        "recovery_message",
        "triage_status",
        "triage_note",
        "manual_action",
        "triage_updated_at",
    ]
    try:
        init_firestore(verbose=False)
        with sqlite3.connect(DB_PATH) as conn:
            table_info = conn.execute("PRAGMA table_info(incidents)").fetchall()
            existing_columns = [row[1] for row in table_info]
            rows = conn.execute("SELECT * FROM incidents ORDER BY id DESC").fetchall()
    except sqlite3.Error:
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=existing_columns)
    for column in base_columns:
        if column not in df:
            df[column] = default_column_value(column)
    df = df[base_columns]

    for column in ["detectors_fired", "warnings", "corrective_steps"]:
        df[column] = df[column].apply(parse_json_list)

    df["timestamp_dt"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["severity_band"] = df["severity"].apply(get_severity_band)
    df["detector_count"] = df["detectors_fired"].apply(len)
    df["warning_count"] = df["warnings"].apply(len)
    df["confidence_num"] = pd.to_numeric(df["confidence"], errors="coerce")
    df["recovery_confidence"] = pd.to_numeric(df["recovery_confidence"], errors="coerce").fillna(0)
    df["recovery_status"] = df["recovery_status"].fillna("unknown").replace("", "unknown")
    df["triage_status"] = df["triage_status"].fillna("open").replace("", "open")
    df["triage_note"] = df["triage_note"].fillna("")
    df["manual_action"] = df["manual_action"].fillna("")
    df["triage_updated_at"] = df["triage_updated_at"].fillna("")
    return df


def default_column_value(column):
    defaults = {
        "recovery_status": "unknown",
        "recovery_confidence": 0,
        "recovery_message": "Recovery verification was not recorded for this incident.",
        "triage_status": "open",
        "triage_note": "",
        "manual_action": "",
        "triage_updated_at": "",
    }
    return defaults.get(column, "")

def pill(label):
    class_name = {
        "Critical": "pill-critical",
        "Medium": "pill-medium",
        "Low": "pill-low",
    }.get(label, "pill-low")
    st.markdown(
        f'<span class="status-pill {class_name}">{label}</span>',
        unsafe_allow_html=True,
    )


def flatten_for_export(dataframe):
    export = dataframe.drop(columns=["timestamp_dt"], errors="ignore").copy()
    for column in ["detectors_fired", "warnings", "corrective_steps"]:
        if column in export:
            export[column] = export[column].apply(lambda values: " | ".join(map(str, values)))
    return export


def apply_filters(dataframe):
    filtered = dataframe.copy()

    with st.sidebar:
        st.header("Controls")
        auto_refresh = st.toggle("Auto refresh", value=True)
        refresh_seconds = st.slider("Refresh interval", 2, 20, 3, disabled=not auto_refresh)

        if st.button("Refresh now", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.divider()
        st.subheader("Filters")

        selected_bands = st.multiselect(
            "Severity band",
            list(SEVERITY_LABELS.keys()),
            default=list(SEVERITY_LABELS.keys()),
        )
        selected_actions = st.multiselect(
            "Action",
            sorted(filtered["action_taken"].dropna().unique()),
            default=sorted(filtered["action_taken"].dropna().unique()),
        )
        selected_workflows = st.multiselect(
            "Workflow",
            sorted(filtered["workflow_id"].dropna().unique()),
            default=sorted(filtered["workflow_id"].dropna().unique()),
        )
        selected_recovery = st.multiselect(
            "Recovery status",
            sorted(filtered["recovery_status"].dropna().unique()),
            default=sorted(filtered["recovery_status"].dropna().unique()),
        )
        selected_triage = st.multiselect(
            "Triage status",
            sorted(filtered["triage_status"].dropna().unique()),
            default=sorted(filtered["triage_status"].dropna().unique()),
        )
        severity_range = st.slider("Severity range", 0, 10, (0, 10))
        query = st.text_input("Search root cause, warning, detector")

    if selected_bands:
        filtered = filtered[filtered["severity_band"].isin(selected_bands)]
    if selected_actions:
        filtered = filtered[filtered["action_taken"].isin(selected_actions)]
    if selected_workflows:
        filtered = filtered[filtered["workflow_id"].isin(selected_workflows)]
    if selected_recovery:
        filtered = filtered[filtered["recovery_status"].isin(selected_recovery)]
    if selected_triage:
        filtered = filtered[filtered["triage_status"].isin(selected_triage)]

    filtered = filtered[
        filtered["severity"].between(severity_range[0], severity_range[1], inclusive="both")
    ]

    if query:
        haystack = filtered.apply(
            lambda row: " ".join(
                [
                    str(row["workflow_id"]),
                    str(row["root_cause"]),
                    " ".join(map(str, row["warnings"])),
                    " ".join(map(str, row["detectors_fired"])),
                    str(row["action_result"]),
                    str(row["recovery_status"]),
                    str(row["recovery_message"]),
                    str(row["triage_status"]),
                    str(row["triage_note"]),
                    str(row["manual_action"]),
                ]
            ).lower(),
            axis=1,
        )
        filtered = filtered[haystack.str.contains(query.lower(), regex=False)]

    return filtered, auto_refresh, refresh_seconds


def render_metric_row(dataframe, filtered):
    critical = len(filtered[filtered["severity"] >= 7]) if not filtered.empty else 0
    retries = len(filtered[filtered["action_taken"] == "retry"]) if not filtered.empty else 0
    avg_sev = round(filtered["severity"].mean(), 2) if not filtered.empty else 0
    recovered = len(filtered[filtered["recovery_status"] == "recovered"]) if not filtered.empty else 0
    latest = filtered["timestamp_dt"].max()
    latest_label = latest.strftime("%H:%M:%S") if pd.notna(latest) else "None"

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Visible Incidents", len(filtered), delta=f"{len(dataframe)} total")
    col2.metric("Avg Severity", f"{avg_sev}/10")
    col3.metric("Critical", critical)
    col4.metric("Auto Retries", retries)
    col5.metric("Recovered", recovered)
    col6.metric("Latest Event", latest_label)


def render_overview(filtered):
    chart_left, chart_right = st.columns([1.35, 1])

    with chart_left:
        st.subheader("Severity Timeline")
        timeline = filtered.sort_values("timestamp_dt")
        fig = px.line(
            timeline,
            x="timestamp_dt",
            y="severity",
            markers=True,
            color="severity_band",
            hover_data=["workflow_id", "action_taken", "root_cause"],
            color_discrete_map={
                "Critical": "#ef6f6c",
                "Medium": "#e9a928",
                "Low": "#3fbf8f",
            },
        )
        fig.update_layout(**PLOT_THEME)
        fig.update_xaxes(gridcolor="#d7e4f2", title=None)
        fig.update_yaxes(gridcolor="#d7e4f2", range=[0, 10], title="Severity")
        fig.add_hline(y=7, line_dash="dash", line_color="#ef6f6c", annotation_text="Critical")
        st.plotly_chart(fig, use_container_width=True)

    with chart_right:
        st.subheader("Action Mix")
        action_counts = filtered["action_taken"].value_counts().reset_index()
        action_counts.columns = ["action", "count"]
        fig2 = px.pie(
            action_counts,
            names="action",
            values="count",
            color_discrete_sequence=["#72c7e7", "#8bd8b7", "#ef9a9a", "#f7d774", "#b9a7ea"],
            hole=0.48,
        )
        fig2.update_layout(**PLOT_THEME)
        st.plotly_chart(fig2, use_container_width=True)

    lower_left, lower_right = st.columns(2)
    with lower_left:
        st.subheader("Detector Frequency")
        detector_counts = (
            filtered.explode("detectors_fired")["detectors_fired"]
            .dropna()
            .value_counts()
            .reset_index()
        )
        detector_counts.columns = ["detector", "count"]
        if detector_counts.empty:
            st.info("No detectors match the current filters.")
        else:
            fig3 = px.bar(
                detector_counts,
                x="count",
                y="detector",
                orientation="h",
                color="count",
                color_continuous_scale=["#b7ead4", "#8fd3ee", "#ef9a9a"],
            )
            fig3.update_layout(**PLOT_THEME, showlegend=False, coloraxis_showscale=False)
            fig3.update_xaxes(gridcolor="#d7e4f2", title="Count")
            fig3.update_yaxes(title=None)
            st.plotly_chart(fig3, use_container_width=True)

    with lower_right:
        st.subheader("Workflow Heatmap")
        heatmap_data = pd.crosstab(filtered["workflow_id"], filtered["severity_band"])
        for label in SEVERITY_LABELS:
            if label not in heatmap_data:
                heatmap_data[label] = 0
        heatmap_data = heatmap_data[list(SEVERITY_LABELS.keys())]
        fig4 = go.Figure(
            data=go.Heatmap(
                z=heatmap_data.values,
                x=heatmap_data.columns,
                y=heatmap_data.index,
                colorscale=[[0, "#f7fbff"], [0.5, "#9bd8ee"], [1, "#ef9a9a"]],
                hoverongaps=False,
            )
        )
        fig4.update_layout(**PLOT_THEME)
        st.plotly_chart(fig4, use_container_width=True)


def format_incident_option(dataframe, incident_id):
    row = dataframe[dataframe["id"] == incident_id].iloc[0]
    return (
        f"#{row['id']} · {row['workflow_id']} · "
        f"{row['severity_band']} {row['severity']}/10 · {row['action_taken']}"
    )


def incident_tokens(row):
    parts = [
        str(row["workflow_id"]),
        str(row["root_cause"]),
        str(row["action_taken"]),
        str(row["action_result"]),
        str(row["recovery_status"]),
        " ".join(map(str, row["detectors_fired"])),
        " ".join(map(str, row["warnings"])),
        " ".join(map(str, row["corrective_steps"])),
    ]
    stop_words = {"the", "and", "for", "with", "that", "this", "from", "into", "event", "workflow"}
    tokens = set()
    for part in parts:
        tokens.update(token for token in part.lower().replace("_", " ").split() if len(token) > 2)
    return tokens - stop_words


def find_similar_rows(dataframe, selected_id, limit=5):
    selected = dataframe[dataframe["id"] == selected_id].iloc[0]
    selected_tokens = incident_tokens(selected)
    matches = []
    for _, candidate in dataframe[dataframe["id"] != selected_id].iterrows():
        candidate_tokens = incident_tokens(candidate)
        if not selected_tokens or not candidate_tokens:
            similarity = 0
        else:
            similarity = len(selected_tokens & candidate_tokens) / len(selected_tokens | candidate_tokens)
        if similarity > 0:
            item = candidate.copy()
            item["similarity"] = round(similarity, 3)
            matches.append(item)
    matches.sort(key=lambda row: (row["similarity"], row["severity"]), reverse=True)
    return matches[:limit]


def render_memory_tab(filtered):
    st.subheader("Incident Memory")
    selected_id = st.selectbox(
        "Compare incident",
        filtered["id"].tolist(),
        format_func=lambda incident_id: format_incident_option(filtered, incident_id),
        key="memory-selected-incident",
    )
    selected = filtered[filtered["id"] == selected_id].iloc[0]
    similar_rows = find_similar_rows(filtered, selected_id)

    summary_left, summary_right = st.columns([1, 2])
    with summary_left:
        st.metric("Selected Severity", f"{selected['severity']}/10")
        st.metric("Similar Matches", len(similar_rows))
        st.metric("Detectors", selected["detector_count"])
    with summary_right:
        st.markdown('<div class="detail-box">', unsafe_allow_html=True)
        st.markdown(f"**Root Cause:** {selected['root_cause']}")
        st.markdown(f"**Detectors:** {', '.join(selected['detectors_fired']) or 'None'}")
        st.markdown(f"**Action:** `{selected['action_taken']}`")
        st.markdown(f"**Recovery:** `{selected['recovery_status']}`")
        st.markdown("</div>", unsafe_allow_html=True)

    if not similar_rows:
        st.info("No similar incidents match the current filters yet. Run more demo events or widen the filters.")
        return

    memory_table = pd.DataFrame(
        [
            {
                "id": row["id"],
                "similarity": row["similarity"],
                "workflow_id": row["workflow_id"],
                "severity": row["severity"],
                "root_cause": row["root_cause"],
                "action_taken": row["action_taken"],
                "recovery_status": row["recovery_status"],
                "action_result": row["action_result"],
            }
            for row in similar_rows
        ]
    )
    st.dataframe(
        memory_table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "similarity": st.column_config.ProgressColumn(
                "Similarity",
                min_value=0,
                max_value=1,
                format="%.2f",
            ),
            "root_cause": st.column_config.TextColumn("Root Cause", width="large"),
            "action_result": st.column_config.TextColumn("Action Result", width="large"),
        },
    )


def render_recovery_tab(filtered):
    st.subheader("Recovery Analytics")
    status_counts = filtered["recovery_status"].value_counts().reset_index()
    status_counts.columns = ["recovery_status", "count"]
    review_count = len(filtered[filtered["recovery_status"] == "needs_human_review"])
    failing_count = len(filtered[filtered["recovery_status"] == "still_failing"])
    avg_confidence = round(filtered["recovery_confidence"].mean(), 2) if not filtered.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Recovered", len(filtered[filtered["recovery_status"] == "recovered"]))
    col2.metric("Needs Review", review_count)
    col3.metric("Still Failing", failing_count)
    col4.metric("Avg Recovery Confidence", avg_confidence)

    chart_left, chart_right = st.columns(2)
    with chart_left:
        fig = px.bar(
            status_counts,
            x="recovery_status",
            y="count",
            color="recovery_status",
            color_discrete_map=RECOVERY_STATUS_COLORS,
        )
        fig.update_layout(**PLOT_THEME, showlegend=False)
        fig.update_xaxes(title=None, gridcolor="#d7e4f2")
        fig.update_yaxes(title="Incidents", gridcolor="#d7e4f2")
        st.plotly_chart(fig, use_container_width=True)

    with chart_right:
        fig2 = px.scatter(
            filtered.sort_values("timestamp_dt"),
            x="timestamp_dt",
            y="recovery_confidence",
            size="severity",
            color="recovery_status",
            hover_data=["workflow_id", "action_taken", "recovery_message"],
            color_discrete_map=RECOVERY_STATUS_COLORS,
        )
        fig2.update_layout(**PLOT_THEME)
        fig2.update_xaxes(title=None, gridcolor="#d7e4f2")
        fig2.update_yaxes(title="Confidence", range=[0, 1], gridcolor="#d7e4f2")
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Recovery Worklist")
    worklist = filtered[filtered["recovery_status"].isin(["needs_human_review", "still_failing", "unknown"])]
    if worklist.empty:
        st.success("No incidents currently need recovery follow-up.")
    else:
        st.dataframe(
            worklist[
                [
                    "id",
                    "workflow_id",
                    "severity",
                    "action_taken",
                    "recovery_status",
                    "recovery_confidence",
                    "recovery_message",
                    "triage_status",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )


def render_incident_workbench(filtered):
    st.subheader("Incident Workbench")
    incident_options = filtered["id"].tolist()
    selected_id = st.selectbox(
        "Select incident",
        incident_options,
        format_func=lambda incident_id: format_incident_option(filtered, incident_id),
    )
    incident = filtered[filtered["id"] == selected_id].iloc[0]

    top_left, top_right = st.columns([1, 2])
    with top_left:
        pill(incident["severity_band"])
        st.metric("Severity", f"{incident['severity']}/10")
        st.metric("Confidence", incident["confidence"])
        st.metric("Warnings", incident["warning_count"])

    with top_right:
        st.markdown('<div class="detail-box">', unsafe_allow_html=True)
        st.markdown(f"**Workflow:** {incident['workflow_id']}")
        st.markdown(f"**Timestamp:** {incident['timestamp']}")
        st.markdown(f"**Action Taken:** `{incident['action_taken']}`")
        st.markdown(f"**Action Result:** {incident['action_result'] or 'No result recorded'}")
        st.markdown(f"**Recovery:** `{incident['recovery_status']}` ({incident['recovery_confidence']:.2f})")
        st.markdown(f"**Recovery Note:** {incident['recovery_message'] or 'No recovery note recorded'}")
        st.markdown(f"**Triage:** `{incident['triage_status']}`")
        if incident["manual_action"]:
            st.markdown(f"**Manual Action:** `{incident['manual_action']}`")
        st.markdown("</div>", unsafe_allow_html=True)

    details, playbook, triage = st.tabs(["Root Cause", "Remediation", "Triage"])
    with details:
        st.markdown(f"**Root Cause**\n\n{incident['root_cause']}")
        st.markdown("**Detectors Fired**")
        st.write(incident["detectors_fired"] or ["No detectors recorded"])
        st.markdown("**Warnings**")
        st.write(incident["warnings"] or ["No warnings recorded"])

    with playbook:
        st.markdown("**Corrective Steps**")
        for index, step in enumerate(incident["corrective_steps"], start=1):
            done = st.checkbox(step, key=f"step-{selected_id}-{index}")
            if done:
                st.caption(f"Step {index} marked done")

        if not incident["corrective_steps"]:
            st.info("No corrective steps were recorded for this incident.")

        action_cols = st.columns(4)
        action_buttons = {
            "retry": action_cols[0],
            "rollback": action_cols[1],
            "escalate": action_cols[2],
            "ignore": action_cols[3],
        }
        for action, column in action_buttons.items():
            if column.button(action.title(), key=f"action-{selected_id}-{action}", use_container_width=True):
                st.session_state.setdefault("triage_actions", {})[selected_id] = {
                    "action": action,
                    "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                st.toast(f"Marked incident {selected_id} for {action}.")

    with triage:
        status_options = ["open", "investigating", "resolved", "needs_follow_up"]
        current_status = incident["triage_status"] if incident["triage_status"] in status_options else "open"
        selected_status = st.selectbox(
            "Triage status",
            status_options,
            index=status_options.index(current_status),
            key=f"triage-status-{selected_id}",
        )
        note = st.text_area(
            "Triage notes",
            value=incident["triage_note"],
            key=f"note-{selected_id}",
            height=140,
        )
        manual_options = ["", "retry", "rollback", "escalate", "ignore"]
        manual_action = st.selectbox(
            "Manual action",
            manual_options,
            index=manual_options.index(incident["manual_action"])
            if incident["manual_action"] in manual_options
            else 0,
            key=f"manual-action-{selected_id}",
        )
        if st.button("Save triage", key=f"save-triage-{selected_id}", use_container_width=True):
            update_incident_triage(int(selected_id), selected_status, note, manual_action)
            st.cache_data.clear()
            st.success("Triage saved to incidents.db")
            st.rerun()
        if incident["triage_updated_at"]:
            st.caption(f"Last updated: {incident['triage_updated_at']}")


def render_incident_table(filtered):
    st.subheader("Incident Log")
    table = filtered[
        [
            "id",
            "timestamp",
            "workflow_id",
            "severity",
            "severity_band",
            "action_taken",
            "confidence",
            "recovery_status",
            "recovery_confidence",
            "triage_status",
            "manual_action",
            "root_cause",
            "action_result",
        ]
    ].copy()
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "severity": st.column_config.ProgressColumn(
                "Severity",
                min_value=0,
                max_value=10,
                format="%d/10",
            ),
            "root_cause": st.column_config.TextColumn("Root Cause", width="large"),
        },
    )

    csv = flatten_for_export(filtered).to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered incidents",
        csv,
        "filtered_incidents.csv",
        "text/csv",
        use_container_width=True,
    )


st.title("🔥 AI Workflow Exception Handler")
st.caption("Real-time anomaly detection · LLM root cause analysis · Auto remediation")

df = load_incidents()

if df.empty:
    st.info("No incidents yet - run demo.py to generate data.")
else:
    filtered_df, auto_refresh, refresh_seconds = apply_filters(df)
    render_metric_row(df, filtered_df)
    st.divider()

    if filtered_df.empty:
        st.warning("No incidents match the current filters.")
    else:
        overview_tab, memory_tab, recovery_tab, workbench_tab, log_tab = st.tabs(
            ["Overview", "Memory", "Recovery", "Incident Workbench", "Log & Export"]
        )
        with overview_tab:
            render_overview(filtered_df)
        with memory_tab:
            render_memory_tab(filtered_df)
        with recovery_tab:
            render_recovery_tab(filtered_df)
        with workbench_tab:
            render_incident_workbench(filtered_df)
        with log_tab:
            render_incident_table(filtered_df)

    if auto_refresh:
        time.sleep(refresh_seconds)
        st.cache_data.clear()
        st.rerun()




