use crate::commands::common::utc_now_iso;
use crate::error_taxonomy::{ErrorCategory, RuntimeErrorInfo};
use crate::state::{
    AppData, ApprovalRequest, ArtifactItem, DiffFile, RunStatus, SessionTurn, SessionTurnItem,
    SessionTurnItemKind, TimelineStatus,
};
use serde_json::json;

fn touch_turn(turn: &mut SessionTurn) {
    turn.updated_at = utc_now_iso();
}

fn with_error_info(
    mut item: SessionTurnItem,
    error_info: Option<&RuntimeErrorInfo>,
) -> SessionTurnItem {
    if let Some(info) = error_info {
        item.error_category = Some(info.category.clone());
        item.error_code = Some(info.code.to_string());
        item.retryable = Some(info.retryable);
        item.retry_hint = info.retry_hint.map(str::to_string);
        item.fallback_hint = info.fallback_hint.map(str::to_string);
        if item.summary.is_none() {
            item.summary = Some(info.user_message.to_string());
        }
    }
    item
}

pub(crate) fn create_session_turn(
    data: &mut AppData,
    session_id: &str,
    turn_id: &str,
    run_id: Option<&str>,
    mode: &str,
    route: Option<&str>,
    user_text: &str,
) -> SessionTurn {
    let now = utc_now_iso();
    let turn = SessionTurn {
        id: turn_id.to_string(),
        session_id: session_id.to_string(),
        run_id: run_id.map(str::to_string),
        mode: mode.to_string(),
        route: route.map(str::to_string),
        route_source: None,
        route_reason: None,
        route_signals: vec![],
        user_text: Some(user_text.to_string()),
        status: RunStatus::Running,
        items: vec![SessionTurnItem {
            id: format!("{turn_id}-user"),
            turn_id: turn_id.to_string(),
            run_id: run_id.map(str::to_string),
            kind: SessionTurnItemKind::UserMessage,
            status: TimelineStatus::Success,
            title: "用户任务".into(),
            summary: Some(user_text.to_string()),
            detail: Some(user_text.to_string()),
            tool_name: None,
            path: None,
            correlation_id: None,
            data_json: None,
            error_category: None,
            error_code: None,
            retryable: None,
            retry_hint: None,
            fallback_hint: None,
            created_at: now.clone(),
            updated_at: now.clone(),
        }],
        created_at: now.clone(),
        updated_at: now,
        completed_at: None,
    };

    let turns = data
        .session_turns
        .entry(session_id.to_string())
        .or_default();
    turns.insert(0, turn.clone());
    if turns.len() > 120 {
        turns.truncate(120);
    }
    let timeline = data.timeline_for_session(session_id);
    data.timelines.insert(session_id.to_string(), timeline);
    turn
}

pub(crate) fn update_session_turn_route(
    data: &mut AppData,
    session_id: &str,
    turn_id: &str,
    route: Option<&str>,
    route_source: Option<&str>,
    route_reason: Option<&str>,
    route_signals: Vec<String>,
) {
    {
        let turns = data
            .session_turns
            .entry(session_id.to_string())
            .or_default();
        let Some(turn) = turns.iter_mut().find(|turn| turn.id == turn_id) else {
            return;
        };
        turn.route = route.map(str::to_string);
        turn.route_source = route_source.map(str::to_string);
        turn.route_reason = route_reason.map(str::to_string);
        turn.route_signals = route_signals;
        touch_turn(turn);
    }
    let timeline = data.timeline_for_session(session_id);
    data.timelines.insert(session_id.to_string(), timeline);
}

pub(crate) fn upsert_turn_item(
    data: &mut AppData,
    session_id: &str,
    turn_id: &str,
    mut item: SessionTurnItem,
) {
    {
        let turns = data
            .session_turns
            .entry(session_id.to_string())
            .or_default();
        let Some(turn) = turns.iter_mut().find(|turn| turn.id == turn_id) else {
            return;
        };
        if let Some(index) = turn.items.iter().position(|current| current.id == item.id) {
            item.created_at = turn.items[index].created_at.clone();
            turn.items[index] = item;
        } else {
            turn.items.push(item);
        }
        touch_turn(turn);
    }
    let timeline = data.timeline_for_session(session_id);
    data.timelines.insert(session_id.to_string(), timeline);
}

pub(crate) fn complete_session_turn(
    data: &mut AppData,
    session_id: &str,
    turn_id: &str,
    status: RunStatus,
) {
    {
        let turns = data
            .session_turns
            .entry(session_id.to_string())
            .or_default();
        let Some(turn) = turns.iter_mut().find(|turn| turn.id == turn_id) else {
            return;
        };
        turn.status = status;
        touch_turn(turn);
        turn.completed_at = Some(turn.updated_at.clone());
    }
    let timeline = data.timeline_for_session(session_id);
    data.timelines.insert(session_id.to_string(), timeline);
}

pub(crate) fn tool_turn_item(
    turn_id: &str,
    run_id: &str,
    item_id: &str,
    tool_name: &str,
    status: TimelineStatus,
    summary: String,
    detail: Option<String>,
    path: Option<String>,
    correlation_id: Option<String>,
    data_json: Option<String>,
) -> SessionTurnItem {
    let now = utc_now_iso();
    with_error_info(
        SessionTurnItem {
            id: item_id.to_string(),
            turn_id: turn_id.to_string(),
            run_id: Some(run_id.to_string()),
            kind: SessionTurnItemKind::ToolCall,
            status: status.clone(),
            title: tool_name.to_string(),
            summary: Some(summary),
            detail,
            tool_name: Some(tool_name.to_string()),
            path,
            correlation_id,
            data_json,
            error_category: None,
            error_code: None,
            retryable: None,
            retry_hint: None,
            fallback_hint: None,
            created_at: now.clone(),
            updated_at: now,
        },
        if status == TimelineStatus::Failed {
            Some(&RuntimeErrorInfo {
                category: ErrorCategory::Tool,
                code: "tool_failed",
                retryable: false,
                retry_hint: Some("缩小到具体文件或目录后重试"),
                fallback_hint: Some("改用更小的 repo 操作或更强模型"),
                user_message: "工具执行失败，建议缩小范围或分解任务。",
            })
        } else {
            None
        },
    )
}

fn runtime_turn_item(
    turn_id: &str,
    run_id: Option<&str>,
    item_id: &str,
    kind: SessionTurnItemKind,
    title: &str,
    status: TimelineStatus,
    summary: Option<String>,
    detail: Option<String>,
    correlation_id: Option<String>,
    data_json: Option<String>,
) -> SessionTurnItem {
    let now = utc_now_iso();
    SessionTurnItem {
        id: item_id.to_string(),
        turn_id: turn_id.to_string(),
        run_id: run_id.map(str::to_string),
        kind,
        status,
        title: title.to_string(),
        summary,
        detail,
        tool_name: None,
        path: None,
        correlation_id,
        data_json,
        error_category: None,
        error_code: None,
        retryable: None,
        retry_hint: None,
        fallback_hint: None,
        created_at: now.clone(),
        updated_at: now,
    }
}

pub(crate) fn phase_turn_item(
    turn_id: &str,
    run_id: Option<&str>,
    item_id: &str,
    title: &str,
    status: TimelineStatus,
    summary: Option<String>,
    detail: Option<String>,
    correlation_id: Option<String>,
    data_json: Option<String>,
) -> SessionTurnItem {
    runtime_turn_item(
        turn_id,
        run_id,
        item_id,
        SessionTurnItemKind::Phase,
        title,
        status,
        summary,
        detail,
        correlation_id,
        data_json,
    )
}

pub(crate) fn context_turn_item(
    turn_id: &str,
    run_id: Option<&str>,
    item_id: &str,
    title: &str,
    status: TimelineStatus,
    summary: Option<String>,
    detail: Option<String>,
    correlation_id: Option<String>,
    data_json: Option<String>,
) -> SessionTurnItem {
    runtime_turn_item(
        turn_id,
        run_id,
        item_id,
        SessionTurnItemKind::Context,
        title,
        status,
        summary,
        detail,
        correlation_id,
        data_json,
    )
}

pub(crate) fn compaction_turn_item(
    turn_id: &str,
    run_id: Option<&str>,
    item_id: &str,
    status: TimelineStatus,
    summary: Option<String>,
    detail: Option<String>,
    correlation_id: Option<String>,
    data_json: Option<String>,
) -> SessionTurnItem {
    runtime_turn_item(
        turn_id,
        run_id,
        item_id,
        SessionTurnItemKind::Compaction,
        "context.compaction",
        status,
        summary,
        detail,
        correlation_id,
        data_json,
    )
}

pub(crate) fn model_turn_item(
    turn_id: &str,
    run_id: Option<&str>,
    item_id: &str,
    status: TimelineStatus,
    summary: Option<String>,
    detail: Option<String>,
    correlation_id: Option<String>,
    data_json: Option<String>,
) -> SessionTurnItem {
    runtime_turn_item(
        turn_id,
        run_id,
        item_id,
        SessionTurnItemKind::ModelRequest,
        "model.request",
        status,
        summary,
        detail,
        correlation_id,
        data_json,
    )
}

pub(crate) fn reasoning_turn_item(
    turn_id: &str,
    run_id: Option<&str>,
    item_id: &str,
    summary: Option<String>,
    detail: Option<String>,
    correlation_id: Option<String>,
    data_json: Option<String>,
) -> SessionTurnItem {
    runtime_turn_item(
        turn_id,
        run_id,
        item_id,
        SessionTurnItemKind::Reasoning,
        "model.reasoning",
        TimelineStatus::Success,
        summary,
        detail,
        correlation_id,
        data_json,
    )
}

pub(crate) fn command_turn_item(
    turn_id: &str,
    run_id: Option<&str>,
    item_id: &str,
    title: &str,
    status: TimelineStatus,
    summary: Option<String>,
    detail: Option<String>,
    path: Option<String>,
    correlation_id: Option<String>,
    data_json: Option<String>,
    error_info: Option<&RuntimeErrorInfo>,
) -> SessionTurnItem {
    let now = utc_now_iso();
    with_error_info(
        SessionTurnItem {
            id: item_id.to_string(),
            turn_id: turn_id.to_string(),
            run_id: run_id.map(str::to_string),
            kind: SessionTurnItemKind::Command,
            status,
            title: title.to_string(),
            summary,
            detail,
            tool_name: None,
            path,
            correlation_id,
            data_json,
            error_category: None,
            error_code: None,
            retryable: None,
            retry_hint: None,
            fallback_hint: None,
            created_at: now.clone(),
            updated_at: now,
        },
        error_info,
    )
}

pub(crate) fn validation_turn_item(
    turn_id: &str,
    run_id: Option<&str>,
    item_id: &str,
    title: &str,
    status: TimelineStatus,
    summary: Option<String>,
    detail: Option<String>,
    correlation_id: Option<String>,
    data_json: Option<String>,
) -> SessionTurnItem {
    with_error_info(
        runtime_turn_item(
            turn_id,
            run_id,
            item_id,
            SessionTurnItemKind::Validation,
            title,
            status.clone(),
            summary,
            detail,
            correlation_id,
            data_json,
        ),
        if status == TimelineStatus::Failed {
            Some(&RuntimeErrorInfo {
                category: ErrorCategory::Validation,
                code: "validation_failed",
                retryable: false,
                retry_hint: None,
                fallback_hint: Some("先检查上下文和权限，再重新执行"),
                user_message: "本轮被校验规则阻止，需要调整执行方式。",
            })
        } else {
            None
        },
    )
}

pub(crate) fn error_turn_item(
    turn_id: &str,
    run_id: Option<&str>,
    item_id: &str,
    title: &str,
    summary: Option<String>,
    detail: Option<String>,
    data_json: Option<String>,
    error_info: &RuntimeErrorInfo,
) -> SessionTurnItem {
    with_error_info(
        runtime_turn_item(
            turn_id,
            run_id,
            item_id,
            SessionTurnItemKind::Error,
            title,
            TimelineStatus::Failed,
            summary,
            detail,
            None,
            data_json,
        ),
        Some(error_info),
    )
}

pub(crate) fn diff_turn_item(
    turn_id: &str,
    run_id: &str,
    diff: &DiffFile,
    correlation_id: Option<String>,
) -> SessionTurnItem {
    let now = utc_now_iso();
    SessionTurnItem {
        id: diff.id.clone(),
        turn_id: turn_id.to_string(),
        run_id: Some(run_id.to_string()),
        kind: SessionTurnItemKind::Diff,
        status: TimelineStatus::Success,
        title: diff.path.clone(),
        summary: Some(format!("+{} / -{}", diff.additions, diff.deletions)),
        detail: Some(diff.diff.clone()),
        tool_name: None,
        path: Some(diff.path.clone()),
        correlation_id,
        data_json: serde_json::to_string(diff).ok(),
        error_category: None,
        error_code: None,
        retryable: None,
        retry_hint: None,
        fallback_hint: None,
        created_at: now.clone(),
        updated_at: now,
    }
}

pub(crate) fn approval_turn_item(
    turn_id: &str,
    run_id: Option<&str>,
    approval: &ApprovalRequest,
) -> SessionTurnItem {
    let now = utc_now_iso();
    with_error_info(
        SessionTurnItem {
            id: approval.id.clone(),
            turn_id: turn_id.to_string(),
            run_id: run_id.map(str::to_string),
            kind: SessionTurnItemKind::Approval,
            status: match approval.status {
                crate::state::ApprovalStatus::Pending => TimelineStatus::Pending,
                crate::state::ApprovalStatus::Approved => TimelineStatus::Success,
                crate::state::ApprovalStatus::Rejected | crate::state::ApprovalStatus::Failed => {
                    TimelineStatus::Failed
                }
            },
            title: approval.tool_name.clone(),
            summary: Some(format!(
                "{}{}",
                approval.action,
                approval
                    .path
                    .as_ref()
                    .map(|path| format!(" · {}", path))
                    .unwrap_or_default()
            )),
            detail: approval
                .result_json
                .clone()
                .or_else(|| approval.decision_note.clone()),
            tool_name: Some(approval.tool_name.clone()),
            path: approval.path.clone(),
            correlation_id: approval.correlation_id.clone(),
            data_json: serde_json::to_string(approval).ok(),
            error_category: None,
            error_code: None,
            retryable: None,
            retry_hint: None,
            fallback_hint: None,
            created_at: now.clone(),
            updated_at: now,
        },
        match approval.status {
            crate::state::ApprovalStatus::Rejected => Some(&RuntimeErrorInfo {
                category: ErrorCategory::Approval,
                code: "approval_rejected",
                retryable: false,
                retry_hint: None,
                fallback_hint: Some("调整变更范围后重新发起审批"),
                user_message: "审批被拒绝，需要调整变更方案。",
            }),
            crate::state::ApprovalStatus::Failed => Some(&RuntimeErrorInfo {
                category: ErrorCategory::Approval,
                code: "approval_failed",
                retryable: false,
                retry_hint: None,
                fallback_hint: Some("重新生成审批动作或缩小变更范围"),
                user_message: "审批执行失败，需要重新确认本次变更方式。",
            }),
            _ => None,
        },
    )
}

pub(crate) fn artifact_turn_item(
    turn_id: &str,
    run_id: Option<&str>,
    artifact: &ArtifactItem,
) -> SessionTurnItem {
    let now = utc_now_iso();
    SessionTurnItem {
        id: artifact.id.clone(),
        turn_id: turn_id.to_string(),
        run_id: run_id.map(str::to_string),
        kind: SessionTurnItemKind::Artifact,
        status: TimelineStatus::Success,
        title: artifact.name.clone(),
        summary: Some(format!("{:?} · {} KB", artifact.kind, artifact.size_kb)),
        detail: Some(
            json!({
                "filePath": artifact.file_path,
                "kind": artifact.kind,
                "provenance": artifact.provenance,
                "sha256": artifact.sha256,
            })
            .to_string(),
        ),
        tool_name: None,
        path: Some(artifact.file_path.clone()),
        correlation_id: artifact.correlation_id.clone(),
        data_json: serde_json::to_string(artifact).ok(),
        error_category: None,
        error_code: None,
        retryable: None,
        retry_hint: None,
        fallback_hint: None,
        created_at: now.clone(),
        updated_at: now,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn create_and_upsert_turn_items() {
        let mut data = AppData::default();
        create_session_turn(
            &mut data,
            "s-test",
            "turn-1",
            Some("run-1"),
            "build",
            Some("tool_execution"),
            "fix app",
        );
        upsert_turn_item(
            &mut data,
            "s-test",
            "turn-1",
            SessionTurnItem {
                id: "tool-1".into(),
                turn_id: "turn-1".into(),
                run_id: Some("run-1".into()),
                kind: SessionTurnItemKind::ToolCall,
                status: TimelineStatus::Running,
                title: "读取文件".into(),
                summary: Some("正在读取".into()),
                detail: None,
                tool_name: Some("repo_read_file".into()),
                path: Some("src/main.rs".into()),
                correlation_id: None,
                data_json: None,
                error_category: None,
                error_code: None,
                retryable: None,
                retry_hint: None,
                fallback_hint: None,
                created_at: "1".into(),
                updated_at: "1".into(),
            },
        );
        complete_session_turn(&mut data, "s-test", "turn-1", RunStatus::Success);

        let turns = data.turns_for_session("s-test");
        assert_eq!(turns.len(), 1);
        assert_eq!(turns[0].items.len(), 2);
        assert_eq!(turns[0].status, RunStatus::Success);
    }

    #[test]
    fn upsert_preserves_original_created_at() {
        let mut data = AppData::default();
        create_session_turn(
            &mut data,
            "s-test",
            "turn-2",
            Some("run-2"),
            "build",
            Some("tool_execution"),
            "fix app",
        );
        upsert_turn_item(
            &mut data,
            "s-test",
            "turn-2",
            SessionTurnItem {
                id: "model-1".into(),
                turn_id: "turn-2".into(),
                run_id: Some("run-2".into()),
                kind: SessionTurnItemKind::ModelRequest,
                status: TimelineStatus::Running,
                title: "model.request".into(),
                summary: Some("running".into()),
                detail: None,
                tool_name: None,
                path: None,
                correlation_id: None,
                data_json: None,
                error_category: None,
                error_code: None,
                retryable: None,
                retry_hint: None,
                fallback_hint: None,
                created_at: "created-1".into(),
                updated_at: "updated-1".into(),
            },
        );
        upsert_turn_item(
            &mut data,
            "s-test",
            "turn-2",
            SessionTurnItem {
                id: "model-1".into(),
                turn_id: "turn-2".into(),
                run_id: Some("run-2".into()),
                kind: SessionTurnItemKind::ModelRequest,
                status: TimelineStatus::Success,
                title: "model.request".into(),
                summary: Some("done".into()),
                detail: None,
                tool_name: None,
                path: None,
                correlation_id: None,
                data_json: None,
                error_category: None,
                error_code: None,
                retryable: None,
                retry_hint: None,
                fallback_hint: None,
                created_at: "created-2".into(),
                updated_at: "updated-2".into(),
            },
        );

        let turns = data.turns_for_session("s-test");
        let item = turns[0]
            .items
            .iter()
            .find(|item| item.id == "model-1")
            .expect("model item should exist");
        assert_eq!(item.created_at, "created-1");
        assert_eq!(item.updated_at, "updated-2");
        assert_eq!(item.status, TimelineStatus::Success);
    }
}
