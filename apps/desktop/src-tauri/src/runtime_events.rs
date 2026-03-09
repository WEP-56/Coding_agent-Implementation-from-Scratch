use crate::state::{AppData, AppState};
use serde::Serialize;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::{AppHandle, Emitter};

pub const SESSION_STATE_CHANGED_EVENT: &str = "session-state-changed";

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionStateChangedEvent {
    pub session_id: String,
    pub reason: String,
    pub run_id: Option<String>,
    pub turn_id: Option<String>,
    pub changed_at: String,
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
    emit_session_state_changed(app, session_id, reason, run_id, turn_id)
}
