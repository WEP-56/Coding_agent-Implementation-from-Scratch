use crate::state::{SessionEvent, SessionTurn, SessionTurnItem, SessionTurnItemKind, TimelineStep};
use std::cmp::Ordering;

fn compare_timestamps(lhs: &str, rhs: &str) -> Ordering {
    match (lhs.parse::<i128>(), rhs.parse::<i128>()) {
        (Ok(lhs), Ok(rhs)) => lhs.cmp(&rhs),
        _ => lhs.cmp(rhs),
    }
}

fn turn_item_trace_type(item: &SessionTurnItem) -> Option<&'static str> {
    match item.kind {
        SessionTurnItemKind::UserMessage | SessionTurnItemKind::AssistantMessage => None,
        SessionTurnItemKind::Phase => Some("session"),
        SessionTurnItemKind::Context => Some("context"),
        SessionTurnItemKind::ModelRequest => Some("model"),
        SessionTurnItemKind::Validation => Some("validation"),
        SessionTurnItemKind::Command => Some("command"),
        SessionTurnItemKind::ToolCall => Some("tool"),
        SessionTurnItemKind::Diff => Some("artifact"),
        SessionTurnItemKind::Approval => Some("approval"),
        SessionTurnItemKind::Artifact => Some("artifact"),
        SessionTurnItemKind::Error => Some("error"),
    }
}

fn turn_item_type(item: &SessionTurnItem) -> Option<String> {
    match item.kind {
        SessionTurnItemKind::UserMessage | SessionTurnItemKind::AssistantMessage => None,
        SessionTurnItemKind::Phase => Some(if item.title == "session.preflight" {
            "preflight".into()
        } else {
            "phase".into()
        }),
        SessionTurnItemKind::Context => Some("context".into()),
        SessionTurnItemKind::ModelRequest => Some("model_request".into()),
        SessionTurnItemKind::Validation => Some("validation".into()),
        SessionTurnItemKind::Command => Some("command".into()),
        SessionTurnItemKind::ToolCall => {
            item.tool_name.clone().or_else(|| Some("tool_call".into()))
        }
        SessionTurnItemKind::Diff => Some("diff".into()),
        SessionTurnItemKind::Approval => Some("approval".into()),
        SessionTurnItemKind::Artifact => Some("artifact".into()),
        SessionTurnItemKind::Error => Some("error".into()),
    }
}

pub fn project_timeline_from_events(events: &[SessionEvent]) -> Vec<TimelineStep> {
    let mut out = events
        .iter()
        .rev()
        .map(|event| TimelineStep {
            id: event.event_id.clone(),
            title: event.title.clone(),
            status: event.status.clone(),
            detail: event.detail.clone(),
            trace_type: event.trace_type.clone(),
            ts: Some(event.ts.clone()),
            correlation_id: event.correlation_id.clone(),
            event_kind: Some(event.kind.clone()),
            turn_id: event.turn_id.clone(),
            run_id: event.run_id.clone(),
            item_id: event.item_id.clone(),
            item_type: event.item_type.clone(),
            sequence: Some(event.seq),
            agent_id: event.agent_id.clone(),
            parent_agent_id: event.parent_agent_id.clone(),
        })
        .collect::<Vec<_>>();
    if out.len() > 400 {
        out.truncate(400);
    }
    out
}

pub fn project_timeline_from_turns(turns: &[SessionTurn]) -> Vec<TimelineStep> {
    let mut projected = turns
        .iter()
        .flat_map(|turn| {
            turn.items.iter().filter_map(move |item| {
                let trace_type = turn_item_trace_type(item)?;
                Some((
                    item.updated_at.clone(),
                    TimelineStep {
                        id: format!("turn-item-{}", item.id),
                        title: item.title.clone(),
                        status: item.status.clone(),
                        detail: item.detail.clone().or_else(|| item.summary.clone()),
                        trace_type: Some(trace_type.into()),
                        ts: Some(item.updated_at.clone()),
                        correlation_id: item.correlation_id.clone(),
                        event_kind: Some("canonical.turn_item".into()),
                        turn_id: Some(turn.id.clone()),
                        run_id: item.run_id.clone().or_else(|| turn.run_id.clone()),
                        item_id: Some(item.id.clone()),
                        item_type: turn_item_type(item),
                        sequence: None,
                        agent_id: Some("agent_main".into()),
                        parent_agent_id: None,
                    },
                ))
            })
        })
        .collect::<Vec<_>>();

    projected.sort_by(|(lhs_ts, lhs_step), (rhs_ts, rhs_step)| {
        compare_timestamps(lhs_ts, rhs_ts).then_with(|| lhs_step.id.cmp(&rhs_step.id))
    });

    let mut out = projected
        .into_iter()
        .enumerate()
        .map(|(index, (_, mut step))| {
            step.sequence = Some(index as i64 + 1);
            step
        })
        .collect::<Vec<_>>();
    out.reverse();
    if out.len() > 400 {
        out.truncate(400);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::{RunStatus, SessionTurnItem, TimelineStatus};

    fn make_turn_item(
        id: &str,
        kind: SessionTurnItemKind,
        title: &str,
        status: TimelineStatus,
        updated_at: &str,
    ) -> SessionTurnItem {
        let tool_name = if kind == SessionTurnItemKind::ToolCall {
            Some("repo_read_file".into())
        } else {
            None
        };
        SessionTurnItem {
            id: id.into(),
            turn_id: "turn-1".into(),
            run_id: Some("run-1".into()),
            kind,
            status,
            title: title.into(),
            summary: None,
            detail: Some(title.into()),
            tool_name,
            path: None,
            correlation_id: None,
            data_json: None,
            error_category: None,
            error_code: None,
            retryable: None,
            created_at: updated_at.into(),
            updated_at: updated_at.into(),
        }
    }

    #[test]
    fn project_timeline_from_turns_orders_items_and_skips_messages() {
        let turn = SessionTurn {
            id: "turn-1".into(),
            session_id: "s1".into(),
            run_id: Some("run-1".into()),
            mode: "build".into(),
            route: Some("tool_execution".into()),
            user_text: Some("fix login".into()),
            status: RunStatus::Success,
            items: vec![
                make_turn_item(
                    "user",
                    SessionTurnItemKind::UserMessage,
                    "user",
                    TimelineStatus::Success,
                    "1",
                ),
                make_turn_item(
                    "phase",
                    SessionTurnItemKind::Phase,
                    "trace.phase.plan",
                    TimelineStatus::Success,
                    "2",
                ),
                make_turn_item(
                    "tool",
                    SessionTurnItemKind::ToolCall,
                    "repo_read_file",
                    TimelineStatus::Success,
                    "3",
                ),
            ],
            created_at: "1".into(),
            updated_at: "3".into(),
            completed_at: Some("3".into()),
        };

        let timeline = project_timeline_from_turns(&[turn]);
        assert_eq!(timeline.len(), 2);
        assert_eq!(timeline[0].item_id.as_deref(), Some("tool"));
        assert_eq!(timeline[0].trace_type.as_deref(), Some("tool"));
        assert_eq!(timeline[1].item_id.as_deref(), Some("phase"));
        assert_eq!(timeline[1].sequence, Some(1));
        assert_eq!(timeline[0].sequence, Some(2));
    }
}
