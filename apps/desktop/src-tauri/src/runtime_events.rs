use crate::state::{
    ApprovalRequest, AppData, AppState, ArtifactItem, DiffFile, LogItem, PythonTodoState,
    PythonContextStatsState, SessionRun, SessionTurn, TimelineStep, ToolCallItem,
};
use serde::Serialize;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::{AppHandle, Emitter};

pub const SESSION_STATE_CHANGED_EVENT: &str = "session-state-changed";
pub const SESSION_WORKFLOW_SNAPSHOT_EVENT: &str = "session-workflow-snapshot";

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionStateChangedEvent {
    pub session_id: String,
    pub reason: String,
    pub run_id: Option<String>,
    pub turn_id: Option<String>,
    pub changed_at: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionWorkflowSnapshotEvent {
    pub session_id: String,
    pub reason: String,
    pub run_id: Option<String>,
    pub turn_id: Option<String>,
    pub changed_at: String,
    pub timeline: Vec<TimelineStep>,
    pub diff_files: Vec<DiffFile>,
    pub tool_calls: Vec<ToolCallItem>,
    pub logs: Vec<LogItem>,
    pub artifacts: Vec<ArtifactItem>,
    pub session_runs: Vec<SessionRun>,
    pub session_turns: Vec<SessionTurn>,
    pub pending_approvals: Vec<ApprovalRequest>,
    #[serde(default)]
    pub python_todo: Option<PythonTodoState>,
    #[serde(default)]
    pub python_context: Option<PythonContextStatsState>,
}

fn event_timestamp() -> String {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format!("{}", now)
}

pub fn emit_session_state_changed(
    app: &AppHandle,
    session_id: &str,
    reason: &str,
    run_id: Option<&str>,
    turn_id: Option<&str>,
) -> Result<(), String> {
    app.emit(
        SESSION_STATE_CHANGED_EVENT,
        SessionStateChangedEvent {
            session_id: session_id.to_string(),
            reason: reason.to_string(),
            run_id: run_id.map(str::to_string),
            turn_id: turn_id.map(str::to_string),
            changed_at: event_timestamp(),
        },
    )
    .map_err(|e| format!("emit session event failed: {}", e))
}

pub fn emit_session_workflow_snapshot(
    app: &AppHandle,
    data: &AppData,
    session_id: &str,
    reason: &str,
    run_id: Option<&str>,
    turn_id: Option<&str>,
) -> Result<(), String> {
    let timeline = data.timeline_for_session(session_id);
    let diff_files = data
        .diffs
        .get(session_id)
        .cloned()
        .unwrap_or_default();
    let tool_calls = data
        .tools
        .get(session_id)
        .cloned()
        .unwrap_or_default();
    let logs = data.logs.get(session_id).cloned().unwrap_or_default();
    let artifacts = data
        .artifacts
        .get(session_id)
        .cloned()
        .unwrap_or_default();
    let session_runs = data.runs_for_session(session_id);
    let session_turns = data.turns_for_session(session_id);
    let pending_approvals = data
        .pending_approvals
        .get(session_id)
        .cloned()
        .unwrap_or_default();

    let python_todo = data.python_todos.get(session_id).cloned();
    let python_context = data.python_context_stats.get(session_id).cloned();

    app.emit(
        SESSION_WORKFLOW_SNAPSHOT_EVENT,
        SessionWorkflowSnapshotEvent {
            session_id: session_id.to_string(),
            reason: reason.to_string(),
            run_id: run_id.map(str::to_string),
            turn_id: turn_id.map(str::to_string),
            changed_at: event_timestamp(),
            timeline,
            diff_files,
            tool_calls,
            logs,
            artifacts,
            session_runs,
            session_turns,
            pending_approvals,
            python_todo,
            python_context,
        },
    )
    .map_err(|e| format!("emit session workflow snapshot failed: {}", e))
}

pub fn save_and_emit_session(
    state: &AppState,
    app: &AppHandle,
    data: &AppData,
    session_id: &str,
    reason: &str,
    run_id: Option<&str>,
    turn_id: Option<&str>,
) -> Result<(), String> {
    state.save_locked(data)?;
    emit_session_state_changed(app, session_id, reason, run_id, turn_id)?;
    emit_session_workflow_snapshot(app, data, session_id, reason, run_id, turn_id)
}
