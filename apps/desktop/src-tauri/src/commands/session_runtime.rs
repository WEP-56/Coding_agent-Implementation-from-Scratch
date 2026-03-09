use crate::commands::common::{
    ensure_session_repo_link, now_millis_str, session_repo_path, utc_now_iso,
};
use crate::commands::intent_router::{resolve_session_intent, SessionIntentRoute};
use crate::commands::llm::{
    append_assistant_turn, append_failure_turn, append_user_turn, run_model_tool_loop,
    run_plain_chat_reply,
};
use crate::commands::policy::push_trace_event_for_run;
use crate::commands::turn_manager::{
    complete_session_turn, create_session_turn, error_turn_item, phase_turn_item,
    update_session_turn_route, upsert_turn_item,
};
use crate::error_taxonomy::{classify_error, ErrorContext};
use crate::runtime_events::save_and_emit_session;
use crate::state::{
    AppState, ApprovalStatus, ArtifactItem, RunSessionResult, RunStatus, SessionEvent, SessionRun,
    SessionTurn, SessionTurnItem, SessionTurnItemKind, TimelineStatus, TimelineStep, ToolCallItem,
};
use serde_json::json;
use std::fs;
use tauri::{AppHandle, State};

pub(crate) fn create_session_run(
    data: &mut crate::state::AppData,
    session_id: &str,
    mode: &str,
    route: &str,
    user_text: &str,
) -> (SessionRun, SessionTurn) {
    let now = utc_now_iso();
    let run = SessionRun {
        id: format!("run-{}", now_millis_str()),
        session_id: session_id.to_string(),
        turn_id: format!("turn-{}", now_millis_str()),
        mode: mode.to_string(),
        user_text: user_text.to_string(),
        assistant_message: None,
        error_text: None,
        status: RunStatus::Running,
        created_at: now.clone(),
        updated_at: now,
        completed_at: None,
    };
    let list = data.session_runs.entry(session_id.to_string()).or_default();
    list.insert(0, run.clone());
    if list.len() > 50 {
        list.truncate(50);
    }
    let turn = create_session_turn(
        data,
        session_id,
        &run.turn_id,
        Some(&run.id),
        mode,
        Some(route),
        user_text,
    );
    (run, turn)
}

pub(crate) fn finish_session_run(
    data: &mut crate::state::AppData,
    session_id: &str,
    run_id: &str,
    status: RunStatus,
    assistant_message: Option<String>,
    error_text: Option<String>,
) {
    let now = utc_now_iso();
    if let Some(list) = data.session_runs.get_mut(session_id) {
        if let Some(run) = list.iter_mut().find(|run| run.id == run_id) {
            run.status = status;
            run.assistant_message = assistant_message;
            run.error_text = error_text;
            run.updated_at = now.clone();
            run.completed_at = Some(now);
        }
    }
}

pub(crate) fn upsert_session_preflight_item(
    data: &mut crate::state::AppData,
    session_id: &str,
    turn_id: &str,
    run_id: Option<&str>,
    mode: &str,
    route: &str,
) -> Result<(), String> {
    let session = data
        .sessions
        .iter()
        .find(|session| session.id == session_id)
        .ok_or_else(|| "session not found".to_string())?;
    let session_title = session.title.clone();
    let repo = data.repos.iter().find(|repo| repo.id == session.repo_id);
    let repo_root = session_repo_path(data, session_id)?;
    let repo_name = repo
        .map(|repo| repo.name.clone())
        .unwrap_or_else(|| "unknown".to_string());
    let session_permissions = data
        .session_permissions
        .iter()
        .filter(|permission| permission.session_id == session_id)
        .map(|permission| {
            json!({
                "toolName": permission.tool_name,
                "action": permission.action,
                "path": permission.path,
                "grantedAt": permission.granted_at,
            })
        })
        .collect::<Vec<_>>();
    let repo_policies = data
        .security
        .policies_by_repo
        .get(&session.repo_id)
        .cloned()
        .unwrap_or_default();
    let summary = format!(
        "{} · route={} · session permissions={} · repo policies={}",
        repo_name,
        route,
        session_permissions.len(),
        repo_policies.len()
    );
    let detail = format!(
        "repo_root: {}\nrepo_name: {}\nsession_title: {}\nmode: {}\nroute: {}\npermission_context: session_grants={} repo_policies={}",
        repo_root,
        repo_name,
        session_title,
        mode,
        route,
        session_permissions.len(),
        repo_policies.len()
    );
    let payload = json!({
        "sessionId": session_id,
        "turnId": turn_id,
        "runId": run_id,
        "repoRoot": repo_root,
        "repoName": repo_name,
        "sessionTitle": session_title,
        "mode": mode,
        "route": route,
        "permissionContext": {
            "sessionGrants": session_permissions,
            "repoPolicies": repo_policies,
        }
    });
    upsert_turn_item(
        data,
        session_id,
        turn_id,
        phase_turn_item(
            turn_id,
            run_id,
            &format!("{turn_id}-preflight"),
            "session.preflight",
            TimelineStatus::Success,
            Some(summary),
            Some(detail),
            None,
            Some(payload.to_string()),
        ),
    );
    Ok(())
}

#[tauri::command]
pub fn get_timeline(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<TimelineStep>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data.timeline_for_session(&session_id))
}

#[tauri::command]
pub fn get_session_events(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<SessionEvent>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    if let Some(turns) = data
        .session_turns
        .get(&session_id)
        .filter(|turns| !turns.is_empty())
    {
        let projected = crate::state::project_session_events_from_turns(&session_id, turns);
        if !projected.is_empty() {
            return Ok(projected);
        }
    }
    Ok(data
        .session_events
        .get(&session_id)
        .cloned()
        .unwrap_or_default())
}

#[tauri::command]
pub fn list_session_runs(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<SessionRun>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data.runs_for_session(&session_id))
}

#[tauri::command]
pub fn list_session_turns(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<crate::state::SessionTurn>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data.turns_for_session(&session_id))
}

#[tauri::command]
pub async fn run_session_message(
    session_id: String,
    mode: String,
    text: String,
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<RunSessionResult, String> {
    let intent = {
        let data = state.data.lock().map_err(|e| e.to_string())?;
        data.clone()
    };
    let intent = resolve_session_intent(&intent, &session_id, &text).await;

    if intent.route == SessionIntentRoute::ChatOnly {
        {
            let mut data = state.data.lock().map_err(|e| e.to_string())?;
            append_user_turn(&mut data, &session_id, &text);
            save_and_emit_session(
                &state,
                &app,
                &data,
                &session_id,
                "chat-user-appended",
                None,
                None,
            )?;
        }
        let assistant_message = match run_plain_chat_reply(&session_id, &state).await {
            Ok(message) => message,
            Err(err) => {
                let mut data = state.data.lock().map_err(|e| e.to_string())?;
                append_failure_turn(&mut data, &session_id, &err);
                save_and_emit_session(&state, &app, &data, &session_id, "chat-failed", None, None)?;
                return Err(err);
            }
        };
        let mut data = state.data.lock().map_err(|e| e.to_string())?;
        append_assistant_turn(&mut data, &session_id, &assistant_message);
        let timeline = data.timeline_for_session(&session_id);
        save_and_emit_session(
            &state,
            &app,
            &data,
            &session_id,
            "chat-assistant-appended",
            None,
            None,
        )?;
        return Ok(RunSessionResult {
            run_id: String::new(),
            turn_id: String::new(),
            status: RunStatus::Success,
            assistant_message,
            timeline,
        });
    }

    let (effective_text, history_user_text) = if let Some(previous_task) = intent.retry_text.clone()
    {
        (
            previous_task.clone(),
            format!("Retry last failed task: {}", previous_task),
        )
    } else {
        (text.clone(), text.clone())
    };

    let run = {
        let mut data = state.data.lock().map_err(|e| e.to_string())?;
        let _ = ensure_session_repo_link(&mut data, &session_id);
        append_user_turn(&mut data, &session_id, &history_user_text);
        let (run, turn) = create_session_run(
            &mut data,
            &session_id,
            &mode,
            intent.route.as_str(),
            &history_user_text,
        );
        update_session_turn_route(
            &mut data,
            &session_id,
            &run.turn_id,
            Some(intent.route.as_str()),
            Some(intent.source.as_str()),
            intent.reasoning.as_deref(),
            intent.signals.clone(),
        );
        upsert_session_preflight_item(
            &mut data,
            &session_id,
            &run.turn_id,
            Some(&run.id),
            &mode,
            intent.route.as_str(),
        )?;
        upsert_turn_item(
            &mut data,
            &session_id,
            &run.turn_id,
            SessionTurnItem {
                id: format!("{}-user", run.turn_id),
                turn_id: run.turn_id.clone(),
                run_id: Some(run.id.clone()),
                kind: SessionTurnItemKind::UserMessage,
                status: TimelineStatus::Success,
                title: "用户任务".into(),
                summary: Some(history_user_text.clone()),
                detail: Some(history_user_text.clone()),
                tool_name: None,
                path: None,
                correlation_id: None,
                data_json: None,
                error_category: None,
                error_code: None,
                retryable: None,
                retry_hint: None,
                fallback_hint: None,
                created_at: turn.created_at.clone(),
                updated_at: utc_now_iso(),
            },
        );
        push_trace_event_for_run(
            &mut data,
            &session_id,
            Some(&run.id),
            "trace.session.start".into(),
            TimelineStatus::Running,
            Some(format!("mode={}", mode)),
            "session",
            None,
        );
        push_trace_event_for_run(
            &mut data,
            &session_id,
            Some(&run.id),
            "trace.intent.routed".into(),
            TimelineStatus::Success,
            Some(intent.trace_detail()),
            "session",
            None,
        );
        save_and_emit_session(
            &state,
            &app,
            &data,
            &session_id,
            "run-started",
            Some(&run.id),
            Some(&run.turn_id),
        )?;
        run
    };

    match run_model_tool_loop(
        &session_id,
        &mode,
        &intent.route,
        &effective_text,
        &run.id,
        &run.turn_id,
        &app,
        &state,
    )
    .await
    {
        Ok(assistant_message) => {
            let mut data = state.data.lock().map_err(|e| e.to_string())?;
            append_assistant_turn(&mut data, &session_id, &assistant_message);
            let pending_approvals = data
                .pending_approvals
                .get(&session_id)
                .map(|items| {
                    items
                        .iter()
                        .filter(|item| item.status == ApprovalStatus::Pending)
                        .count()
                })
                .unwrap_or(0);
            if pending_approvals > 0 {
                push_trace_event_for_run(
                    &mut data,
                    &session_id,
                    Some(&run.id),
                    "trace.approval.pending".into(),
                    TimelineStatus::Pending,
                    Some(format!("pending approvals={}", pending_approvals)),
                    "approval",
                    None,
                );
            }
            push_trace_event_for_run(
                &mut data,
                &session_id,
                Some(&run.id),
                "trace.session.end".into(),
                TimelineStatus::Success,
                Some("run_session_message completed".into()),
                "session",
                None,
            );
            finish_session_run(
                &mut data,
                &session_id,
                &run.id,
                RunStatus::Success,
                Some(assistant_message.clone()),
                None,
            );
            upsert_turn_item(
                &mut data,
                &session_id,
                &run.turn_id,
                SessionTurnItem {
                    id: format!("{}-assistant", run.turn_id),
                    turn_id: run.turn_id.clone(),
                    run_id: Some(run.id.clone()),
                    kind: SessionTurnItemKind::AssistantMessage,
                    status: TimelineStatus::Success,
                    title: "助手回复".into(),
                    summary: Some(assistant_message.chars().take(180).collect::<String>()),
                    detail: Some(assistant_message.clone()),
                    tool_name: None,
                    path: None,
                    correlation_id: None,
                    data_json: None,
                    error_category: None,
                    error_code: None,
                    retryable: None,
                    retry_hint: None,
                    fallback_hint: None,
                    created_at: utc_now_iso(),
                    updated_at: utc_now_iso(),
                },
            );
            complete_session_turn(&mut data, &session_id, &run.turn_id, RunStatus::Success);
            let timeline = data.timeline_for_session(&session_id);
            save_and_emit_session(
                &state,
                &app,
                &data,
                &session_id,
                "run-completed",
                Some(&run.id),
                Some(&run.turn_id),
            )?;

            Ok(RunSessionResult {
                run_id: run.id,
                turn_id: run.turn_id,
                status: RunStatus::Success,
                assistant_message,
                timeline,
            })
        }
        Err(err) => {
            let mut data = state.data.lock().map_err(|e| e.to_string())?;
            append_failure_turn(&mut data, &session_id, &err);
            push_trace_event_for_run(
                &mut data,
                &session_id,
                Some(&run.id),
                "trace.session.end".into(),
                TimelineStatus::Failed,
                Some(err.clone()),
                "session",
                None,
            );
            finish_session_run(
                &mut data,
                &session_id,
                &run.id,
                RunStatus::Failed,
                None,
                Some(err.clone()),
            );
            upsert_turn_item(
                &mut data,
                &session_id,
                &run.turn_id,
                error_turn_item(
                    &run.turn_id,
                    Some(&run.id),
                    &format!("{}-error", run.turn_id),
                    "执行失败",
                    Some(err.chars().take(180).collect::<String>()),
                    Some(err.clone()),
                    Some(
                        json!({
                            "message": err.clone(),
                            "source": "run_session_message",
                        })
                        .to_string(),
                    ),
                    &classify_error(&err, ErrorContext::SessionRun),
                ),
            );
            complete_session_turn(&mut data, &session_id, &run.turn_id, RunStatus::Failed);
            save_and_emit_session(
                &state,
                &app,
                &data,
                &session_id,
                "run-failed",
                Some(&run.id),
                Some(&run.turn_id),
            )?;
            Err(err)
        }
    }
}

#[tauri::command]
pub fn export_trace_bundle(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    let repo_path = session_repo_path(&data, &session_id)?;
    let session_runs = data.runs_for_session(&session_id);
    let session_turns = data.turns_for_session(&session_id);
    let projected_events = if !session_turns.is_empty() {
        crate::state::project_session_events_from_turns(&session_id, &session_turns)
    } else {
        vec![]
    };
    let legacy_session_events = data
        .session_events
        .get(&session_id)
        .cloned()
        .unwrap_or_default();
    let session_events = if !projected_events.is_empty() {
        projected_events.clone()
    } else {
        legacy_session_events.clone()
    };
    let canonical_items = session_turns
        .iter()
        .flat_map(|turn| turn.items.iter().cloned())
        .collect::<Vec<_>>();
    let timeline = data.timeline_for_session(&session_id);
    let timeline_source = if !session_turns.is_empty() {
        "session_turn_items"
    } else if !session_events.is_empty() {
        "session_events"
    } else {
        "cached_timeline"
    };
    let tool_calls: Vec<ToolCallItem> = data.tools.get(&session_id).cloned().unwrap_or_default();
    let approvals = data
        .pending_approvals
        .get(&session_id)
        .cloned()
        .unwrap_or_default();
    let artifacts: Vec<ArtifactItem> = data.artifacts.get(&session_id).cloned().unwrap_or_default();
    let session_permissions = data
        .session_permissions
        .iter()
        .filter(|permission| permission.session_id == session_id)
        .cloned()
        .collect::<Vec<_>>();
    drop(data);

    let bundle = json!({
        "sessionId": session_id,
        "exportedAt": utc_now_iso(),
        "projection": {
            "timelineSource": timeline_source,
            "canonicalTurnCount": session_turns.len(),
            "canonicalItemCount": canonical_items.len(),
            "legacyEventCount": legacy_session_events.len(),
        },
        "sessionRuns": session_runs,
        "sessionTurns": session_turns,
        "canonicalItems": canonical_items,
        "sessionEvents": session_events,
        "legacySessionEvents": legacy_session_events,
        "timeline": timeline,
        "toolCalls": tool_calls,
        "approvals": approvals,
        "artifacts": artifacts,
        "sessionPermissions": session_permissions,
    });

    let base = std::path::PathBuf::from(repo_path)
        .join(".codinggirl")
        .join("traces");
    fs::create_dir_all(&base).map_err(|e| format!("create trace dir failed: {}", e))?;
    let file = base.join(format!("trace_bundle_{}.json", now_millis_str()));
    fs::write(&file, bundle.to_string())
        .map_err(|e| format!("write trace bundle failed: {}", e))?;

    Ok(json!({
        "filePath": file.to_string_lossy().replace('\\', "/"),
        "bundle": bundle,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::SessionTurnItemKind;

    #[test]
    fn preflight_item_captures_repo_route_and_permission_context() {
        let mut data = crate::state::AppData::default();
        data.session_permissions
            .push(crate::state::SessionPermission {
                session_id: "s1".into(),
                tool_name: "apply_patch".into(),
                action: "patch".into(),
                path: None,
                granted_at: "1".into(),
            });
        let (run, _) = create_session_run(&mut data, "s1", "build", "tool_execution", "fix login");

        upsert_session_preflight_item(
            &mut data,
            "s1",
            &run.turn_id,
            Some(&run.id),
            "build",
            "tool_execution",
        )
        .expect("preflight should be recorded");

        let turns = data.turns_for_session("s1");
        let item = turns[0]
            .items
            .iter()
            .find(|item| item.id == format!("{}-preflight", run.turn_id))
            .expect("preflight item should exist");
        assert_eq!(item.kind, SessionTurnItemKind::Phase);
        assert_eq!(item.title, "session.preflight");
        let payload = item
            .data_json
            .as_ref()
            .and_then(|raw| serde_json::from_str::<serde_json::Value>(raw).ok())
            .expect("preflight payload should parse");
        assert_eq!(
            payload.get("mode").and_then(|value| value.as_str()),
            Some("build")
        );
        assert_eq!(
            payload.get("route").and_then(|value| value.as_str()),
            Some("tool_execution")
        );
        assert!(payload
            .get("repoRoot")
            .and_then(|value| value.as_str())
            .is_some());
        assert_eq!(
            payload["permissionContext"]["sessionGrants"]
                .as_array()
                .map(|items| items.len()),
            Some(1)
        );
    }
}
