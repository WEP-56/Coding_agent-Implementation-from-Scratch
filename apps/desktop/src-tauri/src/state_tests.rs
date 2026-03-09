use super::*;

fn make_event(seq: i64, title: &str) -> SessionEvent {
    SessionEvent {
        event_id: format!("evt-{seq}"),
        session_id: "s1".into(),
        turn_id: Some("turn-1".into()),
        run_id: Some("run-1".into()),
        correlation_id: None,
        agent_id: Some("agent_main".into()),
        parent_agent_id: None,
        kind: "trace.event".into(),
        title: title.into(),
        status: TimelineStatus::Success,
        detail: None,
        trace_type: Some("session".into()),
        item_id: None,
        item_type: None,
        ts: format!("2026-03-08T00:00:0{seq}Z"),
        seq,
    }
}

#[test]
fn project_timeline_from_events_keeps_newest_first() {
    let items = project_timeline_from_events(&[make_event(1, "older"), make_event(2, "newer")]);
    assert_eq!(items.len(), 2);
    assert_eq!(items[0].title, "newer");
    assert_eq!(items[0].sequence, Some(2));
    assert_eq!(items[1].title, "older");
}

#[test]
fn timeline_for_session_prefers_session_turns_over_events() {
    let mut data = AppData::default();
    data.session_events
        .insert("s1".into(), vec![make_event(7, "canonical-event")]);

    let timeline = data.timeline_for_session("s1");
    assert_eq!(timeline[0].title, "codinggirl/core/orchestrator.py");
    assert_eq!(timeline[0].item_id.as_deref(), Some("d1"));
}

#[test]
fn timeline_for_session_falls_back_to_events_when_turn_projection_is_empty() {
    let mut data = AppData::default();
    data.session_turns.insert(
        "s3".into(),
        vec![SessionTurn {
            id: "turn-empty".into(),
            session_id: "s3".into(),
            run_id: Some("run-empty".into()),
            mode: "build".into(),
            route: Some("tool_execution".into()),
            route_source: None,
            route_reason: None,
            route_signals: vec![],
            user_text: Some("hello".into()),
            status: RunStatus::Success,
            items: vec![SessionTurnItem {
                id: "turn-empty-user".into(),
                turn_id: "turn-empty".into(),
                run_id: Some("run-empty".into()),
                kind: SessionTurnItemKind::UserMessage,
                status: TimelineStatus::Success,
                title: "用户任务".into(),
                summary: Some("hello".into()),
                detail: Some("hello".into()),
                tool_name: None,
                path: None,
                correlation_id: None,
                data_json: None,
                error_category: None,
                error_code: None,
                retryable: None,
                retry_hint: None,
                fallback_hint: None,
                created_at: "1".into(),
                updated_at: "1".into(),
            }],
            created_at: "1".into(),
            updated_at: "1".into(),
            completed_at: Some("1".into()),
        }],
    );
    data.session_events
        .insert("s3".into(), vec![make_event(7, "canonical-event")]);

    let timeline = data.timeline_for_session("s3");
    assert_eq!(timeline[0].title, "canonical-event");
    assert_eq!(timeline[0].sequence, Some(7));
}

#[test]
fn runs_for_session_returns_latest_backend_runs() {
    let data = AppData::default();
    let runs = data.runs_for_session("s1");
    assert_eq!(runs.len(), 1);
    assert_eq!(runs[0].id, "run-demo-1");
    assert_eq!(runs[0].turn_id, "turn-demo-1");
}

#[test]
fn turns_for_session_returns_canonical_turns() {
    let data = AppData::default();
    let turns = data.turns_for_session("s1");
    assert_eq!(turns.len(), 1);
    assert_eq!(turns[0].id, "turn-demo-1");
    assert_eq!(turns[0].items.len(), 4);
}
