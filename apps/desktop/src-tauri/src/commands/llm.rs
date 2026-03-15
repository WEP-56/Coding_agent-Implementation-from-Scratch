use crate::commands::context_manager::assemble_session_context;
use crate::commands::intent_router::SessionIntentRoute;
use crate::commands::llm_support::{
    assistant_tool_call_message, build_tool_specs, call_openai_compatible, describe_tool_request,
    describe_tool_result, run_tool_call_inner, ChatCompletionResponse,
};
use crate::commands::policy::{push_trace_event_for_run, push_turn_event_for_run};
use crate::commands::repo::build_repo_context;
use crate::commands::turn_manager::{
    compaction_turn_item, reasoning_turn_item, tool_turn_item, upsert_turn_item,
};
use crate::runtime_events::save_and_emit_session;
use crate::state::{AppSettings, AppState, ChatTurn, TimelineStatus, ToolCallItem};
use serde_json::json;
use tauri::{AppHandle, State};

fn has_complete_openai_config(settings: &AppSettings) -> bool {
    !settings.model.base_url.trim().is_empty()
        && !settings.model.api_key.trim().is_empty()
        && !settings.model.model.trim().is_empty()
}

fn use_openai_provider(settings: &AppSettings) -> Result<bool, String> {
    if settings.model.provider == crate::state::Provider::OpenaiCompatible {
        if !has_complete_openai_config(settings) {
            return Err(
                "openai-compatible provider selected but Base URL / API Key / Model is incomplete"
                    .into(),
            );
        }
        return Ok(true);
    }
    Ok(false)
}

fn clip_text(input: &str, max_chars: usize) -> String {
    let clipped = input.chars().take(max_chars).collect::<String>();
    if input.chars().count() > max_chars {
        format!("{}...", clipped)
    } else {
        clipped
    }
}

fn summarize_model_message(msg: &crate::commands::llm_support::ChatCompletionMessage) -> String {
    let content = msg.content.as_deref().unwrap_or("").trim();
    let tool_summaries = msg
        .tool_calls
        .iter()
        .take(3)
        .map(|tc| {
            let args = serde_json::from_str(&tc.function.arguments).unwrap_or_default();
            format!("- {}", describe_tool_request(&tc.function.name, &args))
        })
        .collect::<Vec<_>>();

    if !content.is_empty() && tool_summaries.is_empty() {
        return clip_text(content, 240);
    }
    if !content.is_empty() && !tool_summaries.is_empty() {
        return format!(
            "{}\n\n接下来准备：\n{}",
            clip_text(content, 200),
            tool_summaries.join("\n")
        );
    }
    if !tool_summaries.is_empty() {
        return format!("接下来准备：\n{}", tool_summaries.join("\n"));
    }
    "模型已返回响应。".into()
}

fn tool_failure_guard_message(tool_events: &[(String, String, String, String, bool)]) -> String {
    let failed = tool_events
        .iter()
        .rev()
        .filter(|item| !item.4)
        .take(3)
        .map(|(_, name, _, result, _)| format!("- {}: {}", name, clip_text(result, 180)))
        .collect::<Vec<_>>()
        .join("\n");
    format!(
        "当前模型在工具调用上连续失败，我已提前停止本轮，避免继续空转或触发提供商限流。\n\n最近失败的调用：\n{}\n\n建议切换更强的模型，或把任务范围缩小到具体文件/目录后再继续。",
        if failed.is_empty() {
            "- 暂无可展示的失败工具结果".to_string()
        } else {
            failed
        }
    )
}

fn looks_like_rate_limit(error: &str) -> bool {
    let lower = error.to_ascii_lowercase();
    lower.contains(" 429 ")
        || lower.contains("429 too many requests")
        || lower.contains("rate limit")
        || lower.contains("too many requests")
}

pub(crate) async fn run_model_tool_loop(
    session_id: &str,
    mode: &str,
    route: &SessionIntentRoute,
    text: &str,
    run_id: &str,
    turn_id: &str,
    app: &AppHandle,
    state: &State<'_, AppState>,
) -> Result<String, String> {
    let (settings, repo_context, repo_path, context) = {
        let mut data = state.data.lock().map_err(|e| e.to_string())?;
        let repo_context = build_repo_context(&data, session_id);
        let repo_path = crate::commands::common::session_repo_path(&data, session_id)?;
        let context = assemble_session_context(&mut data, session_id, &repo_path)?;
        (data.settings.clone(), repo_context, repo_path, context)
    };

    let should_use_openai = use_openai_provider(&settings)?;

    if !should_use_openai {
        return Ok(format!(
            "当前使用 mock 回退（请在设置页配置 openai-compatible 的 Base URL / API Key / Model）：{}",
            text
        ));
    }

    let mut messages = context.messages.clone();

    {
        let mut data = state.data.lock().map_err(|e| e.to_string())?;
        push_trace_event_for_run(
            &mut data,
            session_id,
            Some(run_id),
            "trace.phase.intake".into(),
            TimelineStatus::Success,
            Some("已接收任务，正在整理对话上下文和仓库摘要".into()),
            "session",
            None,
        );
        push_trace_event_for_run(
            &mut data,
            session_id,
            Some(run_id),
            "trace.phase.explore".into(),
            TimelineStatus::Running,
            Some("正在浏览仓库，定位接下来要读取和修改的位置".into()),
            "session",
            None,
        );
        push_trace_event_for_run(
            &mut data,
            session_id,
            Some(run_id),
            if context.compaction.applied {
                "trace.context.compacted".into()
            } else {
                "trace.context.ready".into()
            },
            TimelineStatus::Success,
            Some(format!(
                "estimated_tokens={} visible_turns={} memory_blocks={} dropped_turns={}",
                context.estimated_tokens,
                context.budget.visible_turns,
                context.memory_blocks.len(),
                context.compaction.dropped_turns
            )),
            "session",
            None,
        );
        if context.compaction.would_apply {
            upsert_turn_item(
                &mut data,
                session_id,
                turn_id,
                compaction_turn_item(
                    turn_id,
                    Some(run_id),
                    &format!("{turn_id}-compaction"),
                    if context.compaction.applied {
                        TimelineStatus::Success
                    } else {
                        TimelineStatus::Pending
                    },
                    Some(format!(
                        "dropped_turns={} kept_recent={} summary_entries_added={}",
                        context.compaction.dropped_turns,
                        context.compaction.kept_recent,
                        context.compaction.summary_entries_added
                    )),
                    Some(
                        serde_json::to_string(&context.compaction)
                            .unwrap_or_else(|_| "compaction".into()),
                    ),
                    None,
                    serde_json::to_string(&context.compaction).ok(),
                ),
            );
        }
        save_and_emit_session(
            state,
            app,
            &data,
            session_id,
            "run-runtime-updated",
            Some(run_id),
            Some(turn_id),
        )?;
    }

    let memory_context = context.memory_context.clone();
    let tool_specs = build_tool_specs(route);
    let mut tool_events: Vec<(String, String, String, String, bool)> = Vec::new();
    let mut final_content: Option<String> = None;
    let mut last_tool_sig: Option<String> = None;
    let mut consecutive_same_sig = 0usize;
    let mut _consecutive_failed_tools = 0usize;
    let mut _rounds_without_success = 0usize;
    let mut has_read_tool = false;
    let mut has_mutation_tool = false;
    let mut model_request_index = 0usize;

    {
        let mut data = state.data.lock().map_err(|e| e.to_string())?;
        push_turn_event_for_run(
            &mut data,
            session_id,
            Some(run_id),
            "turn.started".into(),
            TimelineStatus::Running,
            Some("tool loop started".into()),
            "session",
            None,
            "turn.started",
            Some(turn_id.to_string()),
            None,
            None,
        );
        save_and_emit_session(
            state,
            app,
            &data,
            session_id,
            "run-runtime-updated",
            Some(run_id),
            Some(turn_id),
        )?;
    }

    loop {
        model_request_index += 1;
        let model_item_id = format!("item-model-{}-{}", turn_id, model_request_index);
        {
            let mut data = state.data.lock().map_err(|e| e.to_string())?;
            push_turn_event_for_run(
                &mut data,
                session_id,
                Some(run_id),
                "item.started:model.request".into(),
                TimelineStatus::Running,
                Some("正在请求模型生成下一步动作".into()),
                "model",
                Some(format!("corr-{}", model_item_id)),
                "item.started",
                Some(turn_id.to_string()),
                Some(model_item_id.clone()),
                Some("model_request".into()),
            );
            push_trace_event_for_run(
                &mut data,
                session_id,
                Some(run_id),
                "trace.model.request".into(),
                TimelineStatus::Running,
                Some("正在请求模型生成下一步动作".into()),
                "model",
                None,
            );
            save_and_emit_session(
                state,
                app,
                &data,
                session_id,
                "run-runtime-updated",
                Some(run_id),
                Some(turn_id),
            )?;
        }

        let body = match call_openai_compatible(
            &settings.model.base_url,
            &settings.model.api_key,
            &settings.model.model,
            mode,
            route,
            &repo_context,
            &memory_context,
            messages.clone(),
            Some(tool_specs.clone()),
        )
        .await
        {
            Ok(body) => body,
            Err(err) => {
                if !tool_events.is_empty() && looks_like_rate_limit(&err) {
                    let mut data = state.data.lock().map_err(|e| e.to_string())?;
                    push_trace_event_for_run(
                        &mut data,
                        session_id,
                        Some(run_id),
                        "trace.guard.provider-rate-limit".into(),
                        TimelineStatus::Failed,
                        Some(err.clone()),
                        "session",
                        Some(format!("corr-{}", model_item_id)),
                    );
                    push_turn_event_for_run(
                        &mut data,
                        session_id,
                        Some(run_id),
                        "item.completed:model.request".into(),
                        TimelineStatus::Failed,
                        Some(err.clone()),
                        "model",
                        Some(format!("corr-{}", model_item_id)),
                        "item.completed",
                        Some(turn_id.to_string()),
                        Some(model_item_id),
                        Some("model_request".into()),
                    );
                    save_and_emit_session(
                        state,
                        app,
                        &data,
                        session_id,
                        "run-runtime-updated",
                        Some(run_id),
                        Some(turn_id),
                    )?;
                    final_content = Some(tool_failure_guard_message(&tool_events));
                    break;
                }
                return Err(err);
            }
        };

        let parsed: ChatCompletionResponse = match serde_json::from_value(body) {
            Ok(parsed) => parsed,
            Err(error) => {
                let err = format!("invalid chat completion response: {}", error);
                let mut data = state.data.lock().map_err(|e| e.to_string())?;
                push_turn_event_for_run(
                    &mut data,
                    session_id,
                    Some(run_id),
                    "item.completed:model.request".into(),
                    TimelineStatus::Failed,
                    Some(err.clone()),
                    "model",
                    Some(format!("corr-{}", model_item_id)),
                    "item.completed",
                    Some(turn_id.to_string()),
                    Some(model_item_id),
                    Some("model_request".into()),
                );
                push_trace_event_for_run(
                    &mut data,
                    session_id,
                    Some(run_id),
                    "trace.model.response".into(),
                    TimelineStatus::Failed,
                    Some(err.clone()),
                    "model",
                    None,
                );
                save_and_emit_session(
                    state,
                    app,
                    &data,
                    session_id,
                    "run-runtime-updated",
                    Some(run_id),
                    Some(turn_id),
                )?;
                return Err(err);
            }
        };
        let Some(choice) = parsed.choices.into_iter().next() else {
            let err = "model returned no choices".to_string();
            let mut data = state.data.lock().map_err(|e| e.to_string())?;
            push_turn_event_for_run(
                &mut data,
                session_id,
                Some(run_id),
                "item.completed:model.request".into(),
                TimelineStatus::Failed,
                Some(err.clone()),
                "model",
                Some(format!("corr-{}", model_item_id)),
                "item.completed",
                Some(turn_id.to_string()),
                Some(model_item_id),
                Some("model_request".into()),
            );
            push_trace_event_for_run(
                &mut data,
                session_id,
                Some(run_id),
                "trace.model.response".into(),
                TimelineStatus::Failed,
                Some(err.clone()),
                "model",
                None,
            );
            save_and_emit_session(
                state,
                app,
                &data,
                session_id,
                "run-runtime-updated",
                Some(run_id),
                Some(turn_id),
            )?;
            return Err(err);
        };
        let msg = choice.message;
        let model_summary = summarize_model_message(&msg);
        {
            let mut data = state.data.lock().map_err(|e| e.to_string())?;
            push_turn_event_for_run(
                &mut data,
                session_id,
                Some(run_id),
                "item.completed:model.request".into(),
                TimelineStatus::Success,
                Some(model_summary.clone()),
                "model",
                Some(format!("corr-{}", model_item_id)),
                "item.completed",
                Some(turn_id.to_string()),
                Some(model_item_id.clone()),
                Some("model_request".into()),
            );
            push_trace_event_for_run(
                &mut data,
                session_id,
                Some(run_id),
                "trace.model.response".into(),
                TimelineStatus::Success,
                Some(model_summary.clone()),
                "model",
                None,
            );
            if !msg.tool_calls.is_empty() {
                upsert_turn_item(
                    &mut data,
                    session_id,
                    turn_id,
                    reasoning_turn_item(
                        turn_id,
                        Some(run_id),
                        &format!("{model_item_id}-reasoning"),
                        Some(model_summary.clone()),
                        Some(model_summary.clone()),
                        Some(format!("corr-{}", model_item_id)),
                        Some(
                            json!({
                                "source": "model_response",
                                "toolCalls": msg.tool_calls.iter().map(|tc| tc.function.name.clone()).collect::<Vec<_>>(),
                            })
                            .to_string(),
                        ),
                    ),
                );
            }
            save_and_emit_session(
                state,
                app,
                &data,
                session_id,
                "run-runtime-updated",
                Some(run_id),
                Some(turn_id),
            )?;
        }

        if msg.tool_calls.is_empty() {
            let content = msg.content.unwrap_or_default();
            let content = content.trim().to_string();
            if content.is_empty() {
                return Err("model returned empty content".into());
            }
            final_content = Some(content);
            break;
        }

        messages.push(assistant_tool_call_message(&msg.tool_calls));
        let mut round_had_success = false;
        let mut _round_failed_tools = 0usize;

        {
            let mut data = state.data.lock().map_err(|e| e.to_string())?;
            push_trace_event_for_run(
                &mut data,
                session_id,
                Some(run_id),
                "trace.phase.plan".into(),
                TimelineStatus::Success,
                Some("已生成执行计划，准备调用工具".into()),
                "session",
                None,
            );
            save_and_emit_session(
                state,
                app,
                &data,
                session_id,
                "run-runtime-updated",
                Some(run_id),
                Some(turn_id),
            )?;
        }

        for tc in msg.tool_calls {
            let sig = format!("{}:{}", tc.function.name, tc.function.arguments);
            if last_tool_sig.as_deref() == Some(sig.as_str()) {
                consecutive_same_sig += 1;
            } else {
                consecutive_same_sig = 1;
                last_tool_sig = Some(sig);
            }
            // NOTE: long/multi-task runs should not be constrained by repeated-tool-call guards.
            // We still track consecutive signatures for potential diagnostics, but we do not stop the loop.
            let _is_readonly_tool = matches!(
                tc.function.name.as_str(),
                "repo_read_file" | "repo_search" | "repo_list_tree" | "memory_list"
            );
            let _ = consecutive_same_sig;
            {
                let mut data = state.data.lock().map_err(|e| e.to_string())?;
                let tool_corr = format!("corr-tool-{}", tc.id);
                push_turn_event_for_run(
                    &mut data,
                    session_id,
                    Some(run_id),
                    format!("item.started:tool.{}", tc.function.name),
                    TimelineStatus::Running,
                    Some(describe_tool_request(
                        &tc.function.name,
                        &serde_json::from_str(&tc.function.arguments).unwrap_or_default(),
                    )),
                    "tool",
                    Some(tool_corr.clone()),
                    "item.started",
                    Some(turn_id.to_string()),
                    Some(tc.id.clone()),
                    Some(tc.function.name.clone()),
                );
                push_trace_event_for_run(
                    &mut data,
                    session_id,
                    Some(run_id),
                    format!("trace.tool.request.{}", tc.function.name),
                    TimelineStatus::Running,
                    Some(describe_tool_request(
                        &tc.function.name,
                        &serde_json::from_str(&tc.function.arguments).unwrap_or_default(),
                    )),
                    "tool",
                    Some(tool_corr.clone()),
                );
                upsert_turn_item(
                    &mut data,
                    session_id,
                    turn_id,
                    tool_turn_item(
                        turn_id,
                        run_id,
                        &tc.id,
                        &tc.function.name,
                        TimelineStatus::Running,
                        describe_tool_request(
                            &tc.function.name,
                            &serde_json::from_str(&tc.function.arguments).unwrap_or_default(),
                        ),
                        Some(tc.function.arguments.clone()),
                        serde_json::from_str::<serde_json::Value>(&tc.function.arguments)
                            .ok()
                            .and_then(|args| {
                                args.get("path")
                                    .and_then(|value| value.as_str())
                                    .map(str::to_string)
                            }),
                        Some(tool_corr.clone()),
                        None,
                    ),
                );
                if matches!(
                    tc.function.name.as_str(),
                    "repo_read_file" | "repo_search" | "repo_list_tree" | "memory_list"
                ) {
                    has_read_tool = true;
                }
                if matches!(
                    tc.function.name.as_str(),
                    "repo_write_file_atomic"
                        | "repo_apply_unified_diff"
                        | "apply_patch"
                        | "memory_set"
                ) {
                    has_mutation_tool = true;
                }
                if has_mutation_tool && !has_read_tool {
                    push_trace_event_for_run(
                        &mut data,
                        session_id,
                        Some(run_id),
                        "trace.guard.read-before-write".into(),
                        TimelineStatus::Failed,
                        Some("mutation attempted before any read/search. ask model to inspect code first".into()),
                        "session",
                        Some(tool_corr.clone()),
                    );
                    push_turn_event_for_run(
                        &mut data,
                        session_id,
                        Some(run_id),
                        "item.completed:tool.guard".into(),
                        TimelineStatus::Failed,
                        Some("read-before-write guard blocked mutation".into()),
                        "tool",
                        Some(tool_corr.clone()),
                        "item.completed",
                        Some(turn_id.to_string()),
                        Some(tc.id.clone()),
                        Some(tc.function.name.clone()),
                    );
                    upsert_turn_item(
                        &mut data,
                        session_id,
                        turn_id,
                        tool_turn_item(
                            turn_id,
                            run_id,
                            &tc.id,
                            &tc.function.name,
                            TimelineStatus::Failed,
                            "read-before-write guard blocked mutation".into(),
                            Some(tc.function.arguments.clone()),
                            serde_json::from_str::<serde_json::Value>(&tc.function.arguments)
                                .ok()
                                .and_then(|args| {
                                    args.get("path")
                                        .and_then(|value| value.as_str())
                                        .map(str::to_string)
                                }),
                            Some(tool_corr.clone()),
                            Some("{\"error\":\"read-before-write guard blocked mutation\"}".into()),
                        ),
                    );
                    final_content = Some("我检测到模型试图直接修改代码而未先阅读上下文。为保证像 Codex 一样稳健，我已阻止本轮修改。请重试，我会先执行 read/search 再 edit。".into());
                    break;
                }
                save_and_emit_session(
                    state,
                    app,
                    &data,
                    session_id,
                    "run-runtime-updated",
                    Some(run_id),
                    Some(turn_id),
                )?;
            }
            if final_content.is_some() {
                break;
            }
            let tool_msg = run_tool_call_inner(
                session_id, &repo_path, mode, route, run_id, turn_id, &tc, state,
            );
            let ok = !tool_msg
                .get("content")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .contains("\"error\"");
            let tool_summary = describe_tool_result(&tc.function.name, &tool_msg, ok);
            let tool_msg_text = tool_msg.to_string();
            tool_events.push((
                tc.id.clone(),
                tc.function.name.clone(),
                tc.function.arguments.clone(),
                tool_msg_text.clone(),
                ok,
            ));
            if ok {
                _consecutive_failed_tools = 0;
                round_had_success = true;
            } else {
                _consecutive_failed_tools += 1;
                _round_failed_tools += 1;
            }
            messages.push(tool_msg.clone());
            {
                let mut data = state.data.lock().map_err(|e| e.to_string())?;
                let tool_corr = format!("corr-tool-{}", tc.id);
                push_turn_event_for_run(
                    &mut data,
                    session_id,
                    Some(run_id),
                    format!("item.completed:tool.{}", tc.function.name),
                    if ok {
                        TimelineStatus::Success
                    } else {
                        TimelineStatus::Failed
                    },
                    Some(tool_summary.clone()),
                    "tool",
                    Some(tool_corr.clone()),
                    "item.completed",
                    Some(turn_id.to_string()),
                    Some(tc.id.clone()),
                    Some(tc.function.name.clone()),
                );
                push_trace_event_for_run(
                    &mut data,
                    session_id,
                    Some(run_id),
                    format!("trace.tool.result.{}", tc.function.name),
                    if ok {
                        TimelineStatus::Success
                    } else {
                        TimelineStatus::Failed
                    },
                    Some(tool_summary.clone()),
                    "tool",
                    Some(tool_corr),
                );
                upsert_turn_item(
                    &mut data,
                    session_id,
                    turn_id,
                    tool_turn_item(
                        turn_id,
                        run_id,
                        &tc.id,
                        &tc.function.name,
                        if ok {
                            TimelineStatus::Success
                        } else {
                            TimelineStatus::Failed
                        },
                        tool_summary.clone(),
                        Some(tool_msg_text.clone()),
                        serde_json::from_str::<serde_json::Value>(&tc.function.arguments)
                            .ok()
                            .and_then(|args| {
                                args.get("path")
                                    .and_then(|value| value.as_str())
                                    .map(str::to_string)
                            }),
                        Some(format!("corr-tool-{}", tc.id)),
                        Some(tool_msg_text),
                    ),
                );
                save_and_emit_session(
                    state,
                    app,
                    &data,
                    session_id,
                    "run-runtime-updated",
                    Some(run_id),
                    Some(turn_id),
                )?;
            }
            // NOTE: long/multi-task runs should not be constrained by tool failure storm guards.
            // Failures are still recorded in tool_events and will be reflected in verify/finalize.
        }
        if final_content.is_some() {
            break;
        }
        if round_had_success {
            _rounds_without_success = 0;
        } else {
            _rounds_without_success += 1;
        }
        // NOTE: long/multi-task runs should not be constrained by no-progress guards.
    }

    {
        let mut data = state.data.lock().map_err(|e| e.to_string())?;
        let verify_status = if tool_events.iter().any(|x| !x.4) {
            TimelineStatus::Failed
        } else {
            TimelineStatus::Success
        };
        push_trace_event_for_run(
            &mut data,
            session_id,
            Some(run_id),
            "trace.phase.verify".into(),
            verify_status,
            Some("正在检查本轮工具结果和代码改动是否完整".into()),
            "session",
            None,
        );
        push_trace_event_for_run(
            &mut data,
            session_id,
            Some(run_id),
            "trace.phase.finalize".into(),
            if final_content.is_some() {
                TimelineStatus::Success
            } else {
                TimelineStatus::Failed
            },
            Some("正在整理最终回复内容".into()),
            "session",
            None,
        );
        push_turn_event_for_run(
            &mut data,
            session_id,
            Some(run_id),
            if final_content.is_some() {
                "turn.completed".into()
            } else {
                "turn.failed".into()
            },
            if final_content.is_some() {
                TimelineStatus::Success
            } else {
                TimelineStatus::Failed
            },
            Some("本轮状态机已到达结束节点".into()),
            "session",
            None,
            if final_content.is_some() {
                "turn.completed"
            } else {
                "turn.failed"
            },
            Some(turn_id.to_string()),
            None,
            None,
        );
        state.save_locked(&data)?;
    }

    let assistant_message = if let Some(content) = final_content {
        content
    } else {
        let recent = tool_events
            .iter()
            .rev()
            .take(3)
            .map(|(_, name, _, result, ok)| {
                format!(
                    "- {}: {}",
                    name,
                    if *ok {
                        result.chars().take(180).collect::<String>()
                    } else {
                        format!("failed: {}", result.chars().take(180).collect::<String>())
                    }
                )
            })
            .collect::<Vec<_>>()
            .join("\n");
        if !recent.is_empty() {
            format!(
                "本轮未形成最终文本回复，但已完成这些关键步骤：\n{}\n\n请补充更明确的范围（例如具体目录或文件）后我继续。",
                recent
            )
        } else {
            "模型未返回有效文本结果，请重试。".to_string()
        }
    };

    {
        let mut data = state.data.lock().map_err(|e| e.to_string())?;
        let list = data.tools.entry(session_id.to_string()).or_default();
        for (id, name, args_json, result_json, ok) in tool_events {
            list.insert(
                0,
                ToolCallItem {
                    id: id.clone(),
                    name,
                    run_id: Some(run_id.to_string()),
                    status: if ok {
                        crate::state::ToolStatus::Success
                    } else {
                        crate::state::ToolStatus::Failed
                    },
                    duration_ms: 0,
                    args_json,
                    result_json,
                    correlation_id: Some(format!("corr-tool-{}", id)),
                },
            );
        }
    }

    Ok(assistant_message)
}

fn trim_history(history: &mut Vec<ChatTurn>) {
    if history.len() > 200 {
        let drain = history.len() - 200;
        history.drain(0..drain);
    }
}

fn append_summary_entry(
    data: &mut crate::state::AppData,
    session_id: &str,
    role_label: &str,
    content: &str,
) {
    let entry = data.chat_summary.entry(session_id.to_string()).or_default();
    if entry.len() >= 4000 {
        return;
    }
    let clip = content.chars().take(360).collect::<String>();
    let line = format!("- {}: {}\n", role_label, clip);
    entry.push_str(&line);
}

pub(crate) fn append_user_turn(
    data: &mut crate::state::AppData,
    session_id: &str,
    user_text: &str,
) {
    let history = data.chat_history.entry(session_id.to_string()).or_default();
    history.push(ChatTurn {
        role: "user".into(),
        content: user_text.to_string(),
    });
    trim_history(history);
    append_summary_entry(data, session_id, "user", user_text);
}

pub(crate) fn append_assistant_turn(
    data: &mut crate::state::AppData,
    session_id: &str,
    assistant_message: &str,
) {
    let history = data.chat_history.entry(session_id.to_string()).or_default();
    history.push(ChatTurn {
        role: "assistant".into(),
        content: assistant_message.to_string(),
    });
    trim_history(history);
    append_summary_entry(data, session_id, "assistant", assistant_message);
}

pub(crate) fn append_failure_turn(
    data: &mut crate::state::AppData,
    session_id: &str,
    error_text: &str,
) {
    let history = data.chat_history.entry(session_id.to_string()).or_default();
    history.push(ChatTurn {
        role: "system".into(),
        content: format!("上一轮执行失败：{}", error_text),
    });
    trim_history(history);
    append_summary_entry(
        data,
        session_id,
        "system",
        &format!("上一轮执行失败：{}", error_text),
    );
}

pub(crate) async fn run_plain_chat_reply(
    session_id: &str,
    state: &State<'_, AppState>,
) -> Result<String, String> {
    let (settings, context) = {
        let mut data = state.data.lock().map_err(|e| e.to_string())?;
        let repo_path = crate::commands::common::session_repo_path(&data, session_id)?;
        let context = assemble_session_context(&mut data, session_id, &repo_path)?;
        (data.settings.clone(), context)
    };

    let should_use_openai = use_openai_provider(&settings)?;

    if !should_use_openai {
        return Ok("我在的。虽然这轮没有走代码工作流，但我还是能继续和你对话。".into());
    }

    let messages = context.messages;
    let memory_context = context.memory_context;
    let body = call_openai_compatible(
        &settings.model.base_url,
        &settings.model.api_key,
        &settings.model.model,
        "chat",
        &SessionIntentRoute::ChatOnly,
        "No repository context injected for this conversational turn.",
        &memory_context,
        messages,
        None,
    )
    .await?;

    let parsed: ChatCompletionResponse = serde_json::from_value(body)
        .map_err(|e| format!("invalid chat completion response: {}", e))?;
    let Some(choice) = parsed.choices.into_iter().next() else {
        return Err("model returned no choices".into());
    };
    let content = choice
        .message
        .content
        .unwrap_or_default()
        .trim()
        .to_string();
    if content.is_empty() {
        return Err("model returned empty content".into());
    }
    Ok(content)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mock_provider_does_not_force_openai_when_fields_exist() {
        let mut settings = crate::state::AppSettings {
            notifications_enabled: true,
            default_session_mode: "build".into(),
            default_theme: "dark".into(),
            output_style: None,
            model: crate::state::ModelConfig {
                provider: crate::state::Provider::Mock,
                model: "local-model".into(),
                base_url: "http://localhost:8317".into(),
                api_key: "token".into(),
                timeout_sec: None,
            },
            rules_by_repo: std::collections::HashMap::new(),
        };

        assert!(!use_openai_provider(&settings).unwrap());

        settings.model.provider = crate::state::Provider::OpenaiCompatible;
        assert!(use_openai_provider(&settings).unwrap());
    }
}
