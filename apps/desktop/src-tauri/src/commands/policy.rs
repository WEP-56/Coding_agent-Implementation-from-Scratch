use crate::commands::common::{now_millis_str, utc_now_iso};
use crate::commands::memory::memory_set_inner;
use crate::commands::patching::{
    apply_codex_style_patch_inner, apply_unified_diff_inner, build_direct_write_diff,
};
use crate::commands::repo::write_repo_file_atomic_inner;
use crate::commands::turn_manager::{
    command_turn_item, context_turn_item, model_turn_item, phase_turn_item, upsert_turn_item,
    validation_turn_item,
};
use crate::state::{
    project_timeline_from_events, ApprovalRequest, ApprovalStatus, SessionEvent, TimelineStatus,
    TimelineStep,
};
use serde_json::json;
use std::fs;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum PolicyDecision {
    Allow,
    Ask,
    Deny,
}

pub(crate) fn create_approval_request(
    data: &mut crate::state::AppData,
    session_id: &str,
    run_id: Option<&str>,
    tool_name: &str,
    action: &str,
    path: Option<String>,
    args_json: &str,
) -> ApprovalRequest {
    let id = format!("appr-{}", now_millis_str());
    let correlation_id = Some(format!("corr-{}", now_millis_str()));
    let req = ApprovalRequest {
        id,
        session_id: session_id.to_string(),
        run_id: run_id.map(|x| x.to_string()),
        tool_name: tool_name.to_string(),
        action: action.to_string(),
        path,
        args_json: args_json.to_string(),
        created_at: now_millis_str(),
        status: ApprovalStatus::Pending,
        decision_note: None,
        result_json: None,
        allow_session: false,
        correlation_id,
    };
    data.pending_approvals
        .entry(session_id.to_string())
        .or_default()
        .insert(0, req.clone());
    req
}

pub(crate) fn get_tool_action_path(
    tool_name: &str,
    args: &serde_json::Value,
) -> (String, Option<String>) {
    match tool_name {
        "repo_write_file_atomic" => (
            "write".into(),
            args.get("path")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
        ),
        "apply_patch" | "repo_apply_unified_diff" => ("patch".into(), None),
        "memory_set" => (
            "memory".into(),
            args.get("label")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
        ),
        "repo_read_file" => (
            "read".into(),
            args.get("path")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
        ),
        "repo_search" => ("search".into(), None),
        _ => ("execute".into(), None),
    }
}

pub(crate) fn has_session_permission(
    data: &crate::state::AppData,
    session_id: &str,
    tool_name: &str,
    action: &str,
    path: Option<&str>,
) -> bool {
    data.session_permissions.iter().any(|p| {
        p.session_id == session_id
            && p.tool_name == tool_name
            && p.action == action
            && (p.path.is_none() || p.path.as_deref() == path)
    })
}

fn resolve_turn_id_for_run(
    data: &crate::state::AppData,
    session_id: &str,
    run_id: Option<&str>,
    turn_id: Option<&str>,
) -> Option<String> {
    if let Some(turn_id) = turn_id {
        return Some(turn_id.to_string());
    }
    let run_id = run_id?;
    data.session_runs
        .get(session_id)
        .and_then(|runs| runs.iter().find(|run| run.id == run_id))
        .map(|run| run.turn_id.clone())
}

fn slug_fragment(input: &str) -> String {
    let mut out = String::new();
    let mut last_dash = false;
    for ch in input.chars() {
        if ch.is_ascii_alphanumeric() {
            out.push(ch.to_ascii_lowercase());
            last_dash = false;
        } else if !last_dash {
            out.push('-');
            last_dash = true;
        }
    }
    let trimmed = out.trim_matches('-');
    if trimmed.is_empty() {
        "item".into()
    } else {
        trimmed.to_string()
    }
}

fn runtime_turn_item_from_event(
    data: &crate::state::AppData,
    session_id: &str,
    run_id: Option<&str>,
    title: &str,
    status: TimelineStatus,
    detail: Option<&str>,
    trace_type: &str,
    correlation_id: Option<&str>,
    event_kind: &str,
    turn_id: Option<&str>,
    item_id: Option<&str>,
    item_type: Option<&str>,
    sequence: i64,
) -> Option<crate::state::SessionTurnItem> {
    let resolved_turn_id = resolve_turn_id_for_run(data, session_id, run_id, turn_id)?;
    let detail_owned = detail.map(str::to_string);
    let correlation_id_owned = correlation_id.map(str::to_string);
    let payload = json!({
        "source": "session_event",
        "eventKind": event_kind,
        "traceTitle": title,
        "traceType": trace_type,
        "itemType": item_type,
        "sequence": sequence,
    })
    .to_string();

    if event_kind.starts_with("turn.") {
        let summary = match event_kind {
            "turn.started" => Some("本轮工作流已启动".to_string()),
            "turn.completed" => Some("本轮工作流已完成".to_string()),
            "turn.failed" => Some("本轮工作流以失败结束".to_string()),
            _ => detail_owned.clone().or_else(|| Some(title.to_string())),
        };
        return Some(phase_turn_item(
            &resolved_turn_id,
            run_id,
            &format!("{resolved_turn_id}-turn-lifecycle"),
            "turn.lifecycle",
            status,
            summary,
            detail_owned,
            correlation_id_owned,
            Some(payload),
        ));
    }

    if matches!(event_kind, "item.started" | "item.completed") && item_type == Some("model_request")
    {
        let summary = detail_owned.clone().or_else(|| {
            Some(match status {
                TimelineStatus::Running => "正在请求模型生成下一步动作".to_string(),
                TimelineStatus::Success => "模型已返回下一步动作".to_string(),
                TimelineStatus::Failed => "模型请求失败".to_string(),
                TimelineStatus::Pending => "模型请求待处理".to_string(),
            })
        });
        return Some(model_turn_item(
            &resolved_turn_id,
            run_id,
            item_id.unwrap_or("model-request"),
            status,
            summary,
            detail_owned,
            correlation_id_owned,
            Some(payload),
        ));
    }

    if matches!(event_kind, "item.started" | "item.completed")
        && (trace_type == "command"
            || item_type == Some("command")
            || item_type == Some("terminal_command"))
    {
        return Some(command_turn_item(
            &resolved_turn_id,
            run_id,
            item_id.unwrap_or("command"),
            "terminal.command",
            status,
            detail_owned.clone().or_else(|| Some(title.to_string())),
            detail_owned,
            None,
            correlation_id_owned,
            Some(payload),
            None,
        ));
    }

    if event_kind != "trace.event" {
        return None;
    }

    if title.starts_with("trace.phase.") || title.starts_with("trace.intent.") {
        return Some(phase_turn_item(
            &resolved_turn_id,
            run_id,
            &format!("{resolved_turn_id}-phase-{sequence}"),
            title,
            status,
            detail_owned.clone().or_else(|| Some(title.to_string())),
            detail_owned,
            correlation_id_owned,
            Some(payload),
        ));
    }

    if title.starts_with("trace.context.") {
        return Some(context_turn_item(
            &resolved_turn_id,
            run_id,
            &format!("{resolved_turn_id}-context-{sequence}"),
            title,
            status,
            detail_owned.clone().or_else(|| Some(title.to_string())),
            detail_owned,
            correlation_id_owned,
            Some(payload),
        ));
    }

    if title.starts_with("trace.guard.") {
        return Some(validation_turn_item(
            &resolved_turn_id,
            run_id,
            &format!(
                "{resolved_turn_id}-validation-{}-{sequence}",
                slug_fragment(title)
            ),
            title,
            status,
            detail_owned.clone().or_else(|| Some(title.to_string())),
            detail_owned,
            correlation_id_owned,
            Some(payload),
        ));
    }

    None
}

pub(crate) fn push_trace_event(
    data: &mut crate::state::AppData,
    session_id: &str,
    title: String,
    status: TimelineStatus,
    detail: Option<String>,
    trace_type: &str,
    correlation_id: Option<String>,
) {
    push_trace_event_for_run(
        data,
        session_id,
        None,
        title,
        status,
        detail,
        trace_type,
        correlation_id,
    );
}

pub(crate) fn push_trace_event_for_run(
    data: &mut crate::state::AppData,
    session_id: &str,
    run_id: Option<&str>,
    title: String,
    status: TimelineStatus,
    detail: Option<String>,
    trace_type: &str,
    correlation_id: Option<String>,
) {
    push_turn_event_for_run(
        data,
        session_id,
        run_id,
        title,
        status,
        detail,
        trace_type,
        correlation_id,
        "trace.event",
        None,
        None,
        None,
    );
}

#[allow(dead_code)]
pub(crate) fn push_turn_event(
    data: &mut crate::state::AppData,
    session_id: &str,
    title: String,
    status: TimelineStatus,
    detail: Option<String>,
    trace_type: &str,
    correlation_id: Option<String>,
    event_kind: &str,
    turn_id: Option<String>,
    item_id: Option<String>,
    item_type: Option<String>,
) {
    push_turn_event_for_run(
        data,
        session_id,
        None,
        title,
        status,
        detail,
        trace_type,
        correlation_id,
        event_kind,
        turn_id,
        item_id,
        item_type,
    );
}

pub(crate) fn push_turn_event_for_run(
    data: &mut crate::state::AppData,
    session_id: &str,
    run_id: Option<&str>,
    title: String,
    status: TimelineStatus,
    detail: Option<String>,
    trace_type: &str,
    correlation_id: Option<String>,
    event_kind: &str,
    turn_id: Option<String>,
    item_id: Option<String>,
    item_type: Option<String>,
) {
    let sequence = next_session_sequence(data, session_id);
    let session_id_owned = session_id.to_string();
    let canonical_item = runtime_turn_item_from_event(
        data,
        session_id,
        run_id,
        &title,
        status.clone(),
        detail.as_deref(),
        trace_type,
        correlation_id.as_deref(),
        event_kind,
        turn_id.as_deref(),
        item_id.as_deref(),
        item_type.as_deref(),
        sequence,
    );
    let event = SessionEvent {
        event_id: format!("evt-{}-{}", session_id, sequence),
        session_id: session_id_owned.clone(),
        turn_id,
        run_id: run_id.map(|x| x.to_string()),
        correlation_id,
        agent_id: Some("agent_main".into()),
        parent_agent_id: None,
        kind: event_kind.to_string(),
        title,
        status,
        detail,
        trace_type: Some(trace_type.to_string()),
        item_id,
        item_type,
        ts: utc_now_iso(),
        seq: sequence,
    };
    let projected = {
        let events = data
            .session_events
            .entry(session_id_owned.clone())
            .or_default();
        events.push(event);
        if events.len() > 2_000 {
            let drop_count = events.len() - 2_000;
            events.drain(0..drop_count);
        }
        project_timeline_from_events(events)
    };
    data.timelines.insert(session_id_owned.clone(), projected);
    if let Some(item) = canonical_item {
        let turn_id = item.turn_id.clone();
        upsert_turn_item(data, &session_id_owned, &turn_id, item);
    }
}

pub(crate) fn update_approval_request(
    data: &mut crate::state::AppData,
    session_id: &str,
    approval_id: &str,
    status: ApprovalStatus,
    note: Option<String>,
    result_json: Option<String>,
    allow_session: Option<bool>,
) -> Option<ApprovalRequest> {
    let list = data.pending_approvals.get_mut(session_id)?;
    let idx = list.iter().position(|r| r.id == approval_id)?;
    list[idx].status = status;
    list[idx].decision_note = note;
    list[idx].result_json = result_json;
    if let Some(v) = allow_session {
        list[idx].allow_session = v;
    }
    Some(list[idx].clone())
}

fn is_mutating_tool(tool_name: &str) -> bool {
    matches!(
        tool_name,
        "repo_write_file_atomic" | "repo_apply_unified_diff" | "memory_set" | "apply_patch"
    )
}

fn next_session_sequence(data: &crate::state::AppData, session_id: &str) -> i64 {
    data.session_events
        .get(session_id)
        .and_then(|items| items.iter().map(|x| x.seq).max())
        .or_else(|| {
            data.timelines
                .get(session_id)
                .and_then(|items| items.iter().filter_map(|x| x.sequence).max())
        })
        .unwrap_or(0)
        + 1
}

fn resolve_tool_policy(
    data: &crate::state::AppData,
    session_id: &str,
    tool_name: &str,
) -> PolicyDecision {
    let default = match tool_name {
        "repo_list_tree" | "repo_read_file" | "repo_search" | "memory_list" => {
            PolicyDecision::Allow
        }
        "repo_write_file_atomic" | "repo_apply_unified_diff" | "memory_set" | "apply_patch" => {
            PolicyDecision::Ask
        }
        _ => PolicyDecision::Deny,
    };

    let Some(session) = data.sessions.iter().find(|s| s.id == session_id) else {
        return default;
    };
    let Some(repo_policies) = data.security.policies_by_repo.get(&session.repo_id) else {
        return default;
    };
    let raw = repo_policies.get(tool_name).or_else(|| {
        let fallback = match tool_name {
            "apply_patch" | "repo_apply_unified_diff" | "repo_write_file_atomic" => "run_shell",
            _ => return None,
        };
        repo_policies.get(fallback)
    });
    let Some(raw) = raw else {
        return default;
    };
    match raw.as_str() {
        "allow" => PolicyDecision::Allow,
        "ask" => PolicyDecision::Ask,
        "deny" => PolicyDecision::Deny,
        _ => default,
    }
}

pub(crate) fn decide_tool_execution_policy(
    data: &crate::state::AppData,
    session_id: &str,
    mode: &str,
    tool_name: &str,
) -> PolicyDecision {
    let configured = resolve_tool_policy(data, session_id, tool_name);
    if !is_mutating_tool(tool_name) {
        return configured;
    }

    let mode = mode.trim().to_ascii_lowercase();
    if mode == "plan" {
        return PolicyDecision::Deny;
    }
    if mode == "build" {
        return if configured == PolicyDecision::Deny {
            PolicyDecision::Deny
        } else {
            PolicyDecision::Ask
        };
    }
    if mode == "auto" {
        return if configured == PolicyDecision::Deny {
            PolicyDecision::Deny
        } else {
            PolicyDecision::Allow
        };
    }
    configured
}

pub(crate) fn execute_approval_request_inner(
    repo_root: &str,
    req: &ApprovalRequest,
) -> Result<(String, Option<Vec<crate::state::DiffFile>>), String> {
    let args: serde_json::Value = serde_json::from_str(&req.args_json)
        .map_err(|e| format!("invalid approval args_json: {}", e))?;
    match req.tool_name.as_str() {
        "apply_patch" => {
            let patch_text = args
                .get("patch")
                .and_then(|v| v.as_str())
                .ok_or_else(|| "approval missing patch".to_string())?;
            let files = apply_codex_style_patch_inner(repo_root, patch_text, "auto")?;
            Ok((json!({"files": files}).to_string(), Some(files)))
        }
        "repo_write_file_atomic" => {
            let path = args
                .get("path")
                .and_then(|v| v.as_str())
                .ok_or_else(|| "approval missing path".to_string())?;
            let content = args
                .get("content")
                .and_then(|v| v.as_str())
                .ok_or_else(|| "approval missing content".to_string())?;
            let if_match = args
                .get("if_match_sha256")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string());
            let before = crate::commands::common::safe_join_repo_path(repo_root, path)
                .ok()
                .and_then(|abs| fs::read_to_string(abs).ok())
                .unwrap_or_default();
            let sha = write_repo_file_atomic_inner(repo_root, path, content, if_match)?;
            let diff = build_direct_write_diff(path, &before, content);
            Ok((
                json!({"sha256": sha, "files": [diff.clone()]}).to_string(),
                Some(vec![diff]),
            ))
        }
        "memory_set" => {
            let scope = args
                .get("scope")
                .and_then(|v| v.as_str())
                .ok_or_else(|| "approval missing scope".to_string())?;
            let label = args
                .get("label")
                .and_then(|v| v.as_str())
                .ok_or_else(|| "approval missing label".to_string())?;
            let content = args
                .get("content")
                .and_then(|v| v.as_str())
                .ok_or_else(|| "approval missing content".to_string())?;
            let description = args
                .get("description")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string());
            let block = memory_set_inner(repo_root, scope, label, content, description)?;
            Ok((json!({"block": block}).to_string(), None))
        }
        "repo_apply_unified_diff" => {
            let diff_text = args
                .get("diff")
                .and_then(|v| v.as_str())
                .ok_or_else(|| "approval missing diff".to_string())?;
            let files = apply_unified_diff_inner(repo_root, diff_text, "auto")?;
            Ok((json!({"files": files}).to_string(), Some(files)))
        }
        _ => Err("unsupported approval tool".into()),
    }
}

pub(crate) fn approval_mode_for_persist(allow_session: Option<bool>) -> bool {
    allow_session.unwrap_or(false)
}

#[allow(dead_code)]
pub(crate) fn build_trace_timeline(
    session_id: &str,
    mode: &str,
    pending_approvals: usize,
) -> Vec<TimelineStep> {
    let mut out = vec![
        TimelineStep {
            id: format!("t-{}-trace-1", session_id),
            title: "trace.session.start".into(),
            status: TimelineStatus::Success,
            detail: Some(format!("mode={}", mode)),
            trace_type: Some("session".into()),
            ts: Some(utc_now_iso()),
            correlation_id: None,
            event_kind: Some("trace.event".into()),
            turn_id: None,
            run_id: None,
            item_id: None,
            item_type: None,
            sequence: Some(1),
            agent_id: Some("agent_main".into()),
            parent_agent_id: None,
        },
        TimelineStep {
            id: format!("t-{}-trace-2", session_id),
            title: "trace.model.response".into(),
            status: TimelineStatus::Success,
            detail: Some("assistant generated response".into()),
            trace_type: Some("model".into()),
            ts: Some(utc_now_iso()),
            correlation_id: None,
            event_kind: Some("trace.event".into()),
            turn_id: None,
            run_id: None,
            item_id: None,
            item_type: None,
            sequence: Some(2),
            agent_id: Some("agent_main".into()),
            parent_agent_id: None,
        },
    ];

    if pending_approvals > 0 {
        out.push(TimelineStep {
            id: format!("t-{}-trace-3", session_id),
            title: "trace.approval.pending".into(),
            status: TimelineStatus::Pending,
            detail: Some(format!("pending approvals={}", pending_approvals)),
            trace_type: Some("approval".into()),
            ts: Some(utc_now_iso()),
            correlation_id: None,
            event_kind: Some("trace.event".into()),
            turn_id: None,
            run_id: None,
            item_id: None,
            item_type: None,
            sequence: Some(3),
            agent_id: Some("agent_main".into()),
            parent_agent_id: None,
        });
    } else if mode == "auto" {
        out.push(TimelineStep {
            id: format!("t-{}-trace-3", session_id),
            title: "trace.apply.auto".into(),
            status: TimelineStatus::Running,
            detail: Some("mutations can be auto-applied".into()),
            trace_type: Some("apply".into()),
            ts: Some(utc_now_iso()),
            correlation_id: None,
            event_kind: Some("trace.event".into()),
            turn_id: None,
            run_id: None,
            item_id: None,
            item_type: None,
            sequence: Some(3),
            agent_id: Some("agent_main".into()),
            parent_agent_id: None,
        });
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::commands::turn_manager::create_session_turn;
    use crate::state::{AppData, RunStatus, SessionTurnItemKind};

    fn seed_run(data: &mut AppData, session_id: &str, run_id: &str, turn_id: &str) {
        create_session_turn(
            data,
            session_id,
            turn_id,
            Some(run_id),
            "build",
            Some("tool_execution"),
            "fix app",
        );
        data.session_runs
            .entry(session_id.to_string())
            .or_default()
            .push(crate::state::SessionRun {
                id: run_id.to_string(),
                session_id: session_id.to_string(),
                turn_id: turn_id.to_string(),
                mode: "build".into(),
                user_text: "fix app".into(),
                assistant_message: None,
                error_text: None,
                status: RunStatus::Running,
                created_at: "1".into(),
                updated_at: "1".into(),
                completed_at: None,
            });
    }

    #[test]
    fn push_trace_event_projects_phase_and_context_items() {
        let mut data = AppData::default();
        seed_run(&mut data, "s-test", "run-1", "turn-1");

        push_trace_event_for_run(
            &mut data,
            "s-test",
            Some("run-1"),
            "trace.phase.intake".into(),
            TimelineStatus::Success,
            Some("intake".into()),
            "session",
            None,
        );
        push_trace_event_for_run(
            &mut data,
            "s-test",
            Some("run-1"),
            "trace.context.ready".into(),
            TimelineStatus::Success,
            Some("estimated_tokens=42".into()),
            "session",
            None,
        );

        let turns = data.turns_for_session("s-test");
        let items = &turns[0].items;
        assert!(items.iter().any(|item| {
            item.kind == SessionTurnItemKind::Phase && item.title == "trace.phase.intake"
        }));
        assert!(items.iter().any(|item| {
            item.kind == SessionTurnItemKind::Context && item.title == "trace.context.ready"
        }));
    }

    #[test]
    fn push_turn_event_projects_model_request_item() {
        let mut data = AppData::default();
        seed_run(&mut data, "s-test", "run-2", "turn-2");

        push_turn_event_for_run(
            &mut data,
            "s-test",
            Some("run-2"),
            "item.started:model.request".into(),
            TimelineStatus::Running,
            Some("waiting".into()),
            "model",
            Some("corr-model-1".into()),
            "item.started",
            Some("turn-2".into()),
            Some("model-1".into()),
            Some("model_request".into()),
        );
        push_turn_event_for_run(
            &mut data,
            "s-test",
            Some("run-2"),
            "item.completed:model.request".into(),
            TimelineStatus::Success,
            Some("done".into()),
            "model",
            Some("corr-model-1".into()),
            "item.completed",
            Some("turn-2".into()),
            Some("model-1".into()),
            Some("model_request".into()),
        );

        let turns = data.turns_for_session("s-test");
        let item = turns[0]
            .items
            .iter()
            .find(|item| item.id == "model-1")
            .expect("model item should exist");
        assert_eq!(item.kind, SessionTurnItemKind::ModelRequest);
        assert_eq!(item.title, "model.request");
        assert_eq!(item.status, TimelineStatus::Success);
    }

    #[test]
    fn push_turn_event_projects_command_item() {
        let mut data = AppData::default();
        seed_run(&mut data, "s-test", "run-3", "turn-3");

        push_turn_event_for_run(
            &mut data,
            "s-test",
            Some("run-3"),
            "item.started:command.terminal".into(),
            TimelineStatus::Running,
            Some("running cargo test".into()),
            "command",
            Some("corr-cmd-1".into()),
            "item.started",
            Some("turn-3".into()),
            Some("cmd-1".into()),
            Some("command".into()),
        );

        let turns = data.turns_for_session("s-test");
        let item = turns[0]
            .items
            .iter()
            .find(|item| item.id == "cmd-1")
            .expect("command item should exist");
        assert_eq!(item.kind, SessionTurnItemKind::Command);
        assert_eq!(item.title, "terminal.command");
        assert_eq!(item.status, TimelineStatus::Running);
    }
}
