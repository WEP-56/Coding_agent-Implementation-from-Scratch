use crate::commands::common::{now_millis_str, session_repo_path};
use crate::commands::policy::push_trace_event_for_run;
use crate::commands::session_runtime::{create_session_run, finish_session_run, upsert_session_preflight_item};
use crate::commands::turn_manager::complete_session_turn;
use crate::runtime_events::save_and_emit_session;
use crate::state::{AppSettings, AppState, RunSessionResult, RunStatus, TimelineStatus, ToolCallItem, ToolStatus};
use serde::Deserialize;
use serde_json::json;
use std::io::{BufRead, BufReader, Read};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{
    atomic::{AtomicBool, AtomicU64, Ordering},
    Arc, Mutex,
};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::async_runtime::spawn_blocking;
use tauri::{AppHandle, Manager, State};

fn now_ms_u64() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "type")]
enum StreamLine {
    #[serde(rename = "run_started")]
    RunStarted {
        #[serde(rename = "runId")]
        run_id: String,
        #[serde(rename = "createdAt")]
        created_at: Option<String>,
        status: Option<String>,
        #[serde(rename = "parentRunId")]
        parent_run_id: Option<String>,
        #[serde(default)]
        metadata: serde_json::Value,
    },
    #[serde(rename = "event")]
    Event {
        #[serde(rename = "runId")]
        run_id: String,
        kind: String,
        ts: String,
        #[serde(rename = "stepId")]
        step_id: Option<String>,
        #[serde(default)]
        payload: serde_json::Value,
    },
    #[serde(rename = "tool_call_started")]
    ToolCallStarted {
        #[serde(rename = "callId")]
        call_id: Option<String>,
        #[serde(rename = "runId")]
        run_id: Option<String>,
        #[serde(rename = "stepId")]
        step_id: Option<String>,
        #[serde(rename = "toolName")]
        tool_name: Option<String>,
        #[serde(rename = "createdAt")]
        created_at: Option<String>,
        #[serde(default)]
        input: serde_json::Value,
    },
    #[serde(rename = "tool_call_finished")]
    ToolCallFinished {
        #[serde(rename = "callId")]
        call_id: Option<String>,
        #[serde(rename = "completedAt")]
        completed_at: Option<String>,
        ok: Option<bool>,
        #[serde(default)]
        output: serde_json::Value,
        #[serde(default)]
        error: serde_json::Value,
    },
    #[serde(rename = "run_finished")]
    RunFinished {
        #[serde(rename = "runId")]
        run_id: Option<String>,
        success: bool,
        iterations: Option<i32>,
        #[serde(rename = "finalMessage")]
        final_message: Option<String>,
        #[serde(rename = "todoStats")]
        todo_stats: Option<serde_json::Value>,
        #[serde(rename = "contextStats")]
        context_stats: Option<serde_json::Value>,
        #[serde(rename = "subagentStats")]
        subagent_stats: Option<serde_json::Value>,
        error: Option<String>,
    },
}

fn normalize_provider(settings: &AppSettings) -> String {
    match settings.model.provider {
        crate::state::Provider::Mock => "mock".to_string(),
        crate::state::Provider::OpenaiCompatible => "openai-compatible".to_string(),
    }
}

fn status_for_kind(kind: &str) -> TimelineStatus {
    if kind.ends_with("_error") || kind == "loop_error" || kind.ends_with("_failed") {
        TimelineStatus::Failed
    } else {
        TimelineStatus::Success
    }
}

fn map_kind_to_trace_title(kind: &str) -> (&'static str, &'static str) {
    match kind {
        // Core loop
        "loop_iteration" => ("trace.phase.explore", "session"),
        "llm_response" => ("trace.phase.plan", "session"),
        "loop_complete" => ("trace.phase.finalize", "session"),
        "loop_error" => ("trace.phase.finalize", "session"),
        "loop_max_iterations" => ("trace.phase.finalize", "session"),

        // Todo / context (shown as canonical context items)
        "todo_initialized" => ("trace.context.todo_initialized", "session"),
        "todo_updated" => ("trace.context.todo_updated", "session"),
        "context_micro_compact" => ("trace.context.micro_compact", "session"),
        "context_auto_compact" => ("trace.context.compacted", "session"),

        // Subagent (shown as canonical phase items)
        "subagent_start" => ("trace.phase.subagent.started", "session"),
        "subagent_complete" => ("trace.phase.subagent.completed", "session"),
        "subagent_error" => ("trace.phase.subagent.failed", "session"),
        "subagent_max_iterations" => ("trace.phase.subagent.max_iterations", "session"),

        _ => ("trace.event", "session"),
    }
}

fn should_emit_snapshot(kind: &str) -> bool {
    // Key nodes only.
    matches!(
        kind,
        "todo_initialized"
            | "todo_updated"
            | "context_auto_compact"
            | "subagent_start"
            | "subagent_complete"
            | "subagent_error"
            | "subagent_max_iterations"
            | "loop_complete"
            | "loop_error"
            | "loop_max_iterations"
    )
}

fn summarize_json(value: &serde_json::Value, max_len: usize) -> String {
    let raw = value.to_string();
    let clipped = raw.chars().take(max_len).collect::<String>();
    if raw.chars().count() > max_len {
        format!("{}...", clipped)
    } else {
        clipped
    }
}

#[tauri::command]
pub async fn run_python_agent_message(
    session_id: String,
    mode: String,
    text: String,
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<RunSessionResult, String> {
    let (repo_root, settings, run_id, turn_id) = {
        let mut data = state.data.lock().map_err(|e| e.to_string())?;
        let repo_root = session_repo_path(&data, &session_id)?;
        let (run, _turn) = create_session_run(
            &mut data,
            &session_id,
            &mode,
            "python_agent",
            &text,
        );
        upsert_session_preflight_item(
            &mut data,
            &session_id,
            &run.turn_id,
            Some(&run.id),
            &mode,
            "python_agent",
        )?;
        push_trace_event_for_run(
            &mut data,
            &session_id,
            Some(&run.id),
            "trace.session.start".into(),
            TimelineStatus::Running,
            Some("python agent run started".into()),
            "session",
            None,
        );
        save_and_emit_session(
            &state,
            &app,
            &data,
            &session_id,
            "python-run-started",
            Some(&run.id),
            Some(&run.turn_id),
        )?;
        (repo_root, data.settings.clone(), run.id, run.turn_id)
    };

    let app2 = app.clone();
    let session_id2 = session_id.clone();
    let mode2 = mode.clone();
    let text2 = text.clone();
    let run_id2 = run_id.clone();
    let turn_id2 = turn_id.clone();

    let (assistant_message, success) = spawn_blocking(move || {
        let state = app2.state::<AppState>();
        let state_ref: &AppState = state.inner();

        let finalize_failure = |err: String| -> Result<(String, bool), String> {
            let mut data = state_ref.data.lock().map_err(|e| e.to_string())?;
            finish_session_run(
                &mut data,
                &session_id2,
                &run_id2,
                RunStatus::Failed,
                None,
                Some(err.clone()),
            );
            complete_session_turn(&mut data, &session_id2, &turn_id2, RunStatus::Failed);
            push_trace_event_for_run(
                &mut data,
                &session_id2,
                Some(&run_id2),
                "trace.phase.finalize".into(),
                TimelineStatus::Failed,
                Some(err.clone()),
                "session",
                None,
            );
            save_and_emit_session(
                state_ref,
                &app2,
                &data,
                &session_id2,
                "python-run-failed",
                Some(&run_id2),
                Some(&turn_id2),
            )?;
            Ok((err, false))
        };

        let execution: Result<(String, bool), String> = (|| {
            let provider = normalize_provider(&settings);

            let mut cmd = Command::new("python");

            // Ensure the workspace root (which contains the `codinggirl/` package) is importable.
            // The `repo_root` can be a sub-project (e.g. .../apps/desktop), so walking upward is safer.
            let mut python_path = std::env::var("PYTHONPATH").unwrap_or_default();

            fn find_codinggirl_root_from(mut cur: PathBuf) -> Option<String> {
                loop {
                    let marker = cur.join("codinggirl").join("__init__.py");
                    if marker.exists() {
                        return Some(cur.to_string_lossy().to_string());
                    }
                    if !cur.pop() {
                        return None;
                    }
                }
            }

            // Prefer locating the monorepo root from the running executable / current dir.
            // The session repo_root may point to an arbitrary user repo and may not contain `codinggirl/`.
            let mut roots: Vec<String> = Vec::new();

            if let Ok(exe) = std::env::current_exe() {
                if let Some(p) = exe.parent() {
                    if let Some(r) = find_codinggirl_root_from(p.to_path_buf()) {
                        roots.push(r);
                    }
                }
            }

            if let Ok(cwd) = std::env::current_dir() {
                if let Some(r) = find_codinggirl_root_from(cwd) {
                    if !roots.iter().any(|x| x == &r) {
                        roots.push(r);
                    }
                }
            }

            if let Some(r) = find_codinggirl_root_from(PathBuf::from(&repo_root)) {
                if !roots.iter().any(|x| x == &r) {
                    roots.push(r);
                }
            }

            // Always include at least the repo_root as a fallback.
            if roots.is_empty() {
                roots.push(repo_root.clone());
            }

            let workspace_root = roots[0].clone();

            if python_path.is_empty() {
                python_path = roots.join(";");
            } else {
                for r in roots.into_iter().rev() {
                    if !python_path.split(';').any(|p| p == r) {
                        python_path = format!("{};{}", r, python_path);
                    }
                }
            }

            cmd.env("PYTHONPATH", python_path.clone());

            // Emit environment info to help diagnose import issues.
            {
                let mut data = state_ref.data.lock().map_err(|e| e.to_string())?;
                push_trace_event_for_run(
                    &mut data,
                    &session_id2,
                    Some(&run_id2),
                    "trace.python.env".into(),
                    TimelineStatus::Success,
                    Some(format!(
                        "repo_root={} workspace_root={} provider={} model={} base_url={} PYTHONPATH={}",
                        repo_root,
                        workspace_root,
                        provider,
                        settings.model.model,
                        settings.model.base_url,
                        python_path
                    )),
                    "session",
                    None,
                );
                // Key-node snapshot here is ok (start of python run) and helps debugging.
                save_and_emit_session(
                    state_ref,
                    &app2,
                    &data,
                    &session_id2,
                    "python-env",
                    Some(&run_id2),
                    Some(&turn_id2),
                )?;
            }

            // Force UTF-8 stdio so we can reliably parse JSONL on Windows.
            cmd.env("PYTHONUTF8", "1");
            cmd.env("PYTHONIOENCODING", "utf-8");

            cmd.arg("-X")
                .arg("utf8")
                .arg("-m")
                .arg("codinggirl.core.desktop_agent_stream_cli")
                .arg("--goal")
                .arg(&text2)
                .arg("--repo")
                .arg(&repo_root)
                .arg("--provider")
                .arg(provider)
                .arg("--model")
                .arg(settings.model.model.clone())
                .arg("--base-url")
                .arg(settings.model.base_url.clone())
                .arg("--api-key")
                .arg(settings.model.api_key.clone())
                .arg("--run-id")
                .arg(run_id2.clone())
                .arg("--max-iterations")
                .arg("400")
                .arg("--keep-recent")
                .arg("8");

            let perm = match mode2.as_str() {
                "plan" => "readonly",
                "auto" => "exec",
                _ => "write",
            };
            cmd.arg("--permission").arg(perm);

            cmd.stdout(Stdio::piped());
            cmd.stderr(Stdio::piped());

            let mut child = cmd.spawn().map_err(|e| format!("spawn python failed: {}", e))?;
            let stdout = child
                .stdout
                .take()
                .ok_or_else(|| "python stdout missing".to_string())?;
            let stderr = child
                .stderr
                .take()
                .ok_or_else(|| "python stderr missing".to_string())?;

            let child: Arc<Mutex<Child>> = Arc::new(Mutex::new(child));
            let last_activity_ms: Arc<AtomicU64> = Arc::new(AtomicU64::new(now_ms_u64()));
            let did_timeout: Arc<AtomicBool> = Arc::new(AtomicBool::new(false));
            {
                let child_killer = child.clone();
                let last_activity_ms = last_activity_ms.clone();
                let did_timeout = did_timeout.clone();
                thread::spawn(move || {
                    let idle_timeout = Duration::from_secs(120);
                    loop {
                        thread::sleep(Duration::from_millis(750));
                        let last = last_activity_ms.load(Ordering::Relaxed);
                        if now_ms_u64().saturating_sub(last) < idle_timeout.as_millis() as u64 {
                            continue;
                        }
                        did_timeout.store(true, Ordering::Relaxed);
                        if let Ok(mut guard) = child_killer.lock() {
                            let _ = guard.kill();
                        }
                        break;
                    }
                });
            }

            let mut stderr_reader = BufReader::new(stderr);
            let mut stderr_buf = String::new();

            let mut stdout_reader = BufReader::new(stdout);
            let mut last_final_message: Option<String> = None;
            let mut last_success: Option<bool> = None;
            let mut saw_run_finished = false;

            loop {
                let mut buf: Vec<u8> = Vec::new();
                let n = stdout_reader
                    .read_until(b'\n', &mut buf)
                    .map_err(|e| format!("read python stdout failed: {}", e))?;
                if n == 0 {
                    break;
                }
                last_activity_ms.store(now_ms_u64(), Ordering::Relaxed);

                while buf.last() == Some(&b'\n') || buf.last() == Some(&b'\r') {
                    buf.pop();
                }
                if buf.is_empty() {
                    continue;
                }

                let line = match String::from_utf8(buf) {
                    Ok(s) => s,
                    Err(e) => {
                        let bytes = e.into_bytes();
                        let preview = bytes.iter().take(120).map(|b| format!("{:02x}", b)).collect::<Vec<_>>().join(" ");
                        // include one stderr line to help correlate
                        let _ = stderr_reader.read_line(&mut stderr_buf);
                        return Err(format!(
                            "python stdout produced non-UTF8 bytes; hex_preview={}\nstderr={} ",
                            preview,
                            stderr_buf.chars().take(400).collect::<String>()
                        ));
                    }
                };

                let trimmed = line.trim();
                if trimmed.is_empty() {
                    continue;
                }

                let parsed: StreamLine = match serde_json::from_str(trimmed) {
                    Ok(v) => v,
                    Err(err) => {
                        let _ = stderr_reader.read_line(&mut stderr_buf);
                        return Err(format!(
                            "invalid python jsonl line: {}\nline={}\nstderr={} ",
                            err,
                            trimmed,
                            stderr_buf.chars().take(400).collect::<String>()
                        ));
                    }
                };

                match parsed {
                    StreamLine::RunStarted { run_id: py_run_id, .. } => {
                        let mut data = state_ref.data.lock().map_err(|e| e.to_string())?;
                        push_trace_event_for_run(
                            &mut data,
                            &session_id2,
                            Some(&run_id2),
                            "trace.python.run_started".into(),
                            TimelineStatus::Success,
                            Some(format!("py_run_id={}", py_run_id)),
                            "session",
                            None,
                        );
                        save_and_emit_session(
                            state_ref,
                            &app2,
                            &data,
                            &session_id2,
                            "python-run-progress",
                            Some(&run_id2),
                            Some(&turn_id2),
                        )?;
                    }
                    StreamLine::Event { kind, ts, payload, .. } => {
                        let (title, trace_type) = map_kind_to_trace_title(&kind);
                        let status = status_for_kind(&kind);
                        let detail = Some(format!(
                            "kind={} ts={} payload={}",
                            kind,
                            ts,
                            summarize_json(&payload, 420)
                        ));

                        let mut data = state_ref.data.lock().map_err(|e| e.to_string())?;

                        // Capture structured Python todo state for the UI drawer.
                        if kind == "todo_initialized" || kind == "todo_updated" {
                            if let Some(stats) = payload.get("stats") {
                                let items = payload
                                    .get("items")
                                    .and_then(|v| v.as_array())
                                    .cloned()
                                    .unwrap_or_default();

                                let todo_state = crate::state::PythonTodoState {
                                    updated_at: ts.clone(),
                                    stats: serde_json::from_value(stats.clone()).unwrap_or(
                                        crate::state::PythonTodoStats {
                                            total: 0,
                                            pending: 0,
                                            in_progress: 0,
                                            completed: 0,
                                        },
                                    ),
                                    items: items
                                        .into_iter()
                                        .filter_map(|v| serde_json::from_value::<crate::state::PythonTodoItem>(v).ok())
                                        .collect(),
                                    rendered: payload
                                        .get("rendered")
                                        .and_then(|v| v.as_str())
                                        .map(|s| s.to_string()),
                                    run_id: Some(run_id2.clone()),
                                    turn_id: Some(turn_id2.clone()),
                                };

                                data.python_todos.insert(session_id2.clone(), todo_state);
                            }
                        }

                        push_trace_event_for_run(
                            &mut data,
                            &session_id2,
                            Some(&run_id2),
                            title.into(),
                            status,
                            detail,
                            trace_type,
                            None,
                        );
                        if should_emit_snapshot(&kind) {
                            save_and_emit_session(
                                state_ref,
                                &app2,
                                &data,
                                &session_id2,
                                "python-run-progress",
                                Some(&run_id2),
                                Some(&turn_id2),
                            )?;
                        } else {
                            state_ref.save_locked(&data)?;
                        }
                    }
                    StreamLine::ToolCallStarted { call_id, tool_name, input, .. } => {
                        let call_id = call_id.unwrap_or_else(|| format!("py-tc-{}", now_millis_str()));
                        let tool_name = tool_name.unwrap_or_else(|| "unknown".into());

                        let mut data = state_ref.data.lock().map_err(|e| e.to_string())?;
                        let list = data.tools.entry(session_id2.clone()).or_default();
                        list.insert(
                            0,
                            ToolCallItem {
                                id: call_id.clone(),
                                name: tool_name.clone(),
                                run_id: Some(run_id2.clone()),
                                status: ToolStatus::Running,
                                duration_ms: 0,
                                args_json: input.to_string(),
                                result_json: "".into(),
                                correlation_id: Some(format!("corr-tool-{}", call_id)),
                            },
                        );

                        // Do not emit snapshot here (could be high-frequency). Persist only.
                        state_ref.save_locked(&data)?;
                    }
                    StreamLine::ToolCallFinished { call_id, ok, output, error, .. } => {
                        let call_id = call_id.unwrap_or_else(|| "unknown".into());
                        let ok = ok.unwrap_or(false);

                        let mut data = state_ref.data.lock().map_err(|e| e.to_string())?;
                        if let Some(list) = data.tools.get_mut(&session_id2) {
                            if let Some(item) = list.iter_mut().find(|x| x.id == call_id) {
                                item.status = if ok {
                                    ToolStatus::Success
                                } else {
                                    ToolStatus::Failed
                                };
                                item.result_json = if ok {
                                    output.to_string()
                                } else {
                                    json!({"error": error}).to_string()
                                };
                            }
                        }

                        // Tool results are important; emit snapshot.
                        push_trace_event_for_run(
                            &mut data,
                            &session_id2,
                            Some(&run_id2),
                            "trace.tool.finished".into(),
                            if ok { TimelineStatus::Success } else { TimelineStatus::Failed },
                            Some(format!(
                                "call_id={} ok={} result={}",
                                call_id,
                                ok,
                                if ok {
                                    summarize_json(&output, 260)
                                } else {
                                    summarize_json(&error, 260)
                                }
                            )),
                            "tool",
                            Some(format!("corr-tool-{}", call_id)),
                        );

                        save_and_emit_session(
                            state_ref,
                            &app2,
                            &data,
                            &session_id2,
                            "python-run-progress",
                            Some(&run_id2),
                            Some(&turn_id2),
                        )?;
                    }
                    StreamLine::RunFinished { success, final_message, error, todo_stats, context_stats, subagent_stats, .. } => {
                        saw_run_finished = true;
                        last_final_message = final_message.clone();
                        last_success = Some(success);

                        let detail = json!({
                            "success": success,
                            "todoStats": todo_stats,
                            "contextStats": context_stats,
                            "subagentStats": subagent_stats,
                            "error": error,
                        });

                        let mut data = state_ref.data.lock().map_err(|e| e.to_string())?;
                        finish_session_run(
                            &mut data,
                            &session_id2,
                            &run_id2,
                            if success { RunStatus::Success } else { RunStatus::Failed },
                            last_final_message.clone(),
                            error.clone(),
                        );
                        complete_session_turn(
                            &mut data,
                            &session_id2,
                            &turn_id2,
                            if success { RunStatus::Success } else { RunStatus::Failed },
                        );
                        push_trace_event_for_run(
                            &mut data,
                            &session_id2,
                            Some(&run_id2),
                            "trace.phase.finalize".into(),
                            if success { TimelineStatus::Success } else { TimelineStatus::Failed },
                            Some(format!("python run finished: {}", summarize_json(&detail, 520))),
                            "session",
                            None,
                        );
                        save_and_emit_session(
                            state_ref,
                            &app2,
                            &data,
                            &session_id2,
                            "python-run-finished",
                            Some(&run_id2),
                            Some(&turn_id2),
                        )?;
                    }
                }
            }

            let status = child
                .lock()
                .map_err(|e| e.to_string())?
                .wait()
                .map_err(|e| format!("wait python failed: {}", e))?;

            let mut remaining_err = String::new();
            let _ = stderr_reader.read_to_string(&mut remaining_err);

            if did_timeout.load(Ordering::Relaxed) {
                return Err(format!(
                    "python agent stalled: no stdout for 120s (likely LLM/network hang). stderr={} ",
                    remaining_err.chars().take(1200).collect::<String>()
                ));
            }

            if !status.success() {
                let code = status.code().unwrap_or(-1);
                // Treat exit code 1 as non-fatal if we already received a structured run_finished line.
                // The Python CLI exits 1 for success=false (e.g. max-iterations reached), which should be represented as a failed run,
                // not as a process-level crash.
                if !(saw_run_finished && code == 1) {
                    return Err(format!(
                        "python exited with code {}\nstderr={} ",
                        code,
                        remaining_err.chars().take(1200).collect::<String>()
                    ));
                }
            }

            let final_message = last_final_message.unwrap_or_else(|| "python run finished".into());
            let success = last_success.unwrap_or(true);
            Ok((final_message, success))
        })();

        match execution {
            Ok(v) => Ok(v),
            Err(err) => finalize_failure(err),
        }
    })
    .await
    .map_err(|e| format!("python task join failed: {}", e))??;

    let timeline = {
        let data = state.data.lock().map_err(|e| e.to_string())?;
        data.timeline_for_session(&session_id)
    };

    Ok(RunSessionResult {
        run_id,
        turn_id,
        status: if success { RunStatus::Success } else { RunStatus::Failed },
        assistant_message: assistant_message.clone(),
        timeline,
    })
}
