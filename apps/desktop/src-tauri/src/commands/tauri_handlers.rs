use crate::commands::common::{
    now_millis_str, path_is_sensitive, resolve_repo_scoped_path, safe_join_repo_path,
    session_repo_path, sha256_hex, utc_now_iso,
};
use crate::commands::context_manager::build_session_context_debug_snapshot;
use crate::commands::memory::{
    is_safe_memory_label, normalize_memory_scope, read_all_memory_blocks,
    read_memory_block_from_file, write_memory_block_to_file,
};
use crate::commands::patching::persist_patch_artifacts;
use crate::commands::policy::{
    approval_mode_for_persist, execute_approval_request_inner, push_trace_event,
    update_approval_request,
};
use crate::commands::repo::{
    list_repo_tree_inner, read_repo_file_inner, search_repo_inner, write_repo_file_atomic_inner,
};
use crate::commands::session_runtime::{
    create_session_run, finish_session_run, upsert_session_preflight_item,
};
use crate::commands::turn_manager::{
    approval_turn_item, artifact_turn_item, complete_session_turn, diff_turn_item, error_turn_item,
    phase_turn_item, upsert_turn_item,
};
use crate::error_taxonomy::{classify_error, ErrorContext};
use crate::state::{
    AppSettings, AppState, ApprovalMeta, ApprovalRequest, ApprovalStatus, ArtifactItem, DiffFile,
    LogItem, MemoryBlock, PluginItem, RepoFileContent, RepoItem, RepoTreeEntry, RiskLevel,
    RunStatus, SecurityPolicies, SessionItem, TimelineStatus, ToolCallItem,
};
use serde_json::json;
use std::fs;
use tauri::State;

fn turn_id_for_run(
    data: &crate::state::AppData,
    session_id: &str,
    run_id: Option<&str>,
) -> Option<String> {
    let run_id = run_id?;
    data.session_runs
        .get(session_id)
        .and_then(|runs| runs.iter().find(|run| run.id == run_id))
        .map(|run| run.turn_id.clone())
}

#[tauri::command]
pub fn list_repos(state: State<'_, AppState>) -> Result<Vec<RepoItem>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data.repos.clone())
}

#[tauri::command]
pub fn list_sessions(
    repo_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<SessionItem>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data
        .sessions
        .iter()
        .filter(|s| s.repo_id == repo_id)
        .cloned()
        .collect())
}

#[tauri::command]
pub fn get_diff_files(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<DiffFile>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data.diffs.get(&session_id).cloned().unwrap_or_default())
}

#[tauri::command]
pub fn get_tool_calls(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<ToolCallItem>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data.tools.get(&session_id).cloned().unwrap_or_default())
}

#[tauri::command]
pub fn get_logs(session_id: String, state: State<'_, AppState>) -> Result<Vec<LogItem>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data.logs.get(&session_id).cloned().unwrap_or_default())
}

#[tauri::command]
pub fn get_artifacts(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<ArtifactItem>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data.artifacts.get(&session_id).cloned().unwrap_or_default())
}

#[tauri::command]
pub fn get_approval_meta(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<ApprovalMeta, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    let diffs = data.diffs.get(&session_id).cloned().unwrap_or_default();
    let file_count = diffs.len() as i32;
    let additions = diffs.iter().map(|d| d.additions).sum::<i32>();
    let deletions = diffs.iter().map(|d| d.deletions).sum::<i32>();
    let risk = if additions + deletions > 40 {
        RiskLevel::High
    } else if additions + deletions > 20 {
        RiskLevel::Medium
    } else {
        RiskLevel::Low
    };

    let repo_name = data
        .sessions
        .iter()
        .find(|s| s.id == session_id)
        .and_then(|s| data.repos.iter().find(|r| r.id == s.repo_id))
        .map(|r| r.name.clone())
        .unwrap_or_else(|| "unknown-repo".into());

    Ok(ApprovalMeta {
        file_count,
        additions,
        deletions,
        risk,
        repo_name,
        branch: "main".into(),
    })
}

#[tauri::command]
pub fn create_session(
    repo_id: String,
    title: String,
    mode: String,
    state: State<'_, AppState>,
) -> Result<SessionItem, String> {
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    // Keep repo/session linkage valid even with stale frontend state.
    let resolved_repo_id = if data.repos.iter().any(|r| r.id == repo_id) {
        repo_id
    } else if let Some(first_repo) = data.repos.first() {
        first_repo.id.clone()
    } else {
        return Err("no repository available for session".into());
    };
    let ts = now_millis_str();
    let item = SessionItem {
        id: format!("s-{}", ts),
        repo_id: resolved_repo_id,
        title,
        mode,
        created_at: ts.clone(),
        updated_at: ts,
    };
    data.sessions.insert(0, item.clone());
    state.save_locked(&data)?;
    Ok(item)
}

#[tauri::command]
pub fn delete_session(session_id: String, state: State<'_, AppState>) -> Result<(), String> {
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    data.sessions.retain(|s| s.id != session_id);
    data.session_events.remove(&session_id);
    data.session_runs.remove(&session_id);
    data.session_turns.remove(&session_id);
    data.timelines.remove(&session_id);
    data.diffs.remove(&session_id);
    data.tools.remove(&session_id);
    data.logs.remove(&session_id);
    data.artifacts.remove(&session_id);
    state.save_locked(&data)
}

#[tauri::command]
pub fn update_session_mode(
    session_id: String,
    mode: String,
    state: State<'_, AppState>,
) -> Result<(), String> {
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    let ts = now_millis_str();
    for s in data.sessions.iter_mut() {
        if s.id == session_id {
            s.mode = mode.clone();
            s.updated_at = ts.clone();
        }
    }
    state.save_locked(&data)
}

#[tauri::command]
pub fn add_repo(path: String, state: State<'_, AppState>) -> Result<RepoItem, String> {
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    let clean_path = path.trim().replace('\\', "/");
    if clean_path.is_empty() {
        return Err("repo path is empty".into());
    }

    if let Some(existing) = data.repos.iter().find(|r| r.path == clean_path) {
        return Ok(existing.clone());
    }

    let name = clean_path
        .split('/')
        .filter(|s| !s.is_empty())
        .last()
        .unwrap_or("new-repo")
        .to_string();
    let repo = RepoItem {
        id: format!("r-{}", now_millis_str()),
        name,
        path: clean_path,
        pinned: false,
    };
    data.repos.insert(0, repo.clone());
    state.save_locked(&data)?;
    Ok(repo)
}

#[tauri::command]
pub fn remove_repo(repo_id: String, state: State<'_, AppState>) -> Result<(), String> {
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    data.repos.retain(|r| r.id != repo_id);
    data.sessions.retain(|s| s.repo_id != repo_id);
    state.save_locked(&data)
}

#[tauri::command]
pub fn toggle_repo_pin(repo_id: String, state: State<'_, AppState>) -> Result<(), String> {
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    for r in data.repos.iter_mut() {
        if r.id == repo_id {
            r.pinned = !r.pinned;
        }
    }
    data.repos.sort_by(|a, b| b.pinned.cmp(&a.pinned));
    state.save_locked(&data)
}

#[tauri::command]
pub fn get_settings(state: State<'_, AppState>) -> Result<AppSettings, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data.settings.clone())
}

#[tauri::command]
pub fn save_settings(settings: AppSettings, state: State<'_, AppState>) -> Result<(), String> {
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    data.settings = settings;
    state.save_locked(&data)
}

#[tauri::command]
pub fn get_security_policies(state: State<'_, AppState>) -> Result<SecurityPolicies, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data.security.clone())
}

#[tauri::command]
pub fn save_security_policies(
    policies: SecurityPolicies,
    state: State<'_, AppState>,
) -> Result<(), String> {
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    data.security = policies;
    state.save_locked(&data)
}

#[tauri::command]
pub fn list_plugins(state: State<'_, AppState>) -> Result<Vec<PluginItem>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data.plugins.clone())
}

#[tauri::command]
pub fn import_plugin(path: String, state: State<'_, AppState>) -> Result<PluginItem, String> {
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    let clean_path = path.trim().replace('\\', "/");
    if clean_path.is_empty() {
        return Err("plugin path is empty".into());
    }
    if let Some(existing) = data.plugins.iter().find(|p| p.source_path == clean_path) {
        return Ok(existing.clone());
    }
    let ts = now_millis_str();
    let item = PluginItem {
        id: format!("plugin-{}", ts),
        name: clean_path
            .split('/')
            .filter(|s| !s.is_empty())
            .last()
            .unwrap_or("plugin")
            .to_string(),
        source_path: clean_path,
        enabled: true,
        imported_at: ts,
    };
    data.plugins.insert(0, item.clone());
    state.save_locked(&data)?;
    Ok(item)
}

#[tauri::command]
pub fn toggle_plugin_enabled(plugin_id: String, state: State<'_, AppState>) -> Result<(), String> {
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    for p in data.plugins.iter_mut() {
        if p.id == plugin_id {
            p.enabled = !p.enabled;
        }
    }
    state.save_locked(&data)
}

#[tauri::command]
pub fn remove_plugin(plugin_id: String, state: State<'_, AppState>) -> Result<(), String> {
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    data.plugins.retain(|p| p.id != plugin_id);
    state.save_locked(&data)
}

#[tauri::command]
pub fn list_repo_tree(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<RepoTreeEntry>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    let repo_path = session_repo_path(&data, &session_id)?;
    drop(data);
    list_repo_tree_inner(&repo_path)
}

#[tauri::command]
pub fn read_repo_file(
    session_id: String,
    path: String,
    state: State<'_, AppState>,
) -> Result<RepoFileContent, String> {
    if path_is_sensitive(&path) {
        return Err("敏感文件已被策略阻止读取。".into());
    }
    let data = state.data.lock().map_err(|e| e.to_string())?;
    let repo_path = session_repo_path(&data, &session_id)?;
    drop(data);
    read_repo_file_inner(&repo_path, &path)
}

#[tauri::command]
pub fn get_chat_history(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<crate::state::ChatTurn>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data
        .chat_history
        .get(&session_id)
        .cloned()
        .unwrap_or_default())
}

#[tauri::command]
pub fn get_chat_summary(session_id: String, state: State<'_, AppState>) -> Result<String, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data
        .chat_summary
        .get(&session_id)
        .cloned()
        .unwrap_or_default())
}

#[tauri::command]
pub fn get_session_context_debug(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<crate::commands::context_manager::SessionContextDebugSnapshot, String> {
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    let repo_path = session_repo_path(&data, &session_id)?;
    build_session_context_debug_snapshot(&mut data, &session_id, &repo_path)
}

#[tauri::command]
pub fn list_memory_blocks(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<MemoryBlock>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    let repo_path = session_repo_path(&data, &session_id)?;
    drop(data);
    read_all_memory_blocks(&repo_path)
}

#[tauri::command]
pub fn set_memory_block(
    session_id: String,
    scope: String,
    label: String,
    content: String,
    description: Option<String>,
    read_only: Option<bool>,
    limit: Option<usize>,
    state: State<'_, AppState>,
) -> Result<MemoryBlock, String> {
    let scope = normalize_memory_scope(&scope).ok_or_else(|| "invalid scope".to_string())?;
    let label = label.trim().to_string();
    if !is_safe_memory_label(&label) {
        return Err("invalid label".into());
    }
    if content.chars().count() > 120_000 {
        return Err("memory content too large".into());
    }

    let data = state.data.lock().map_err(|e| e.to_string())?;
    let repo_path = session_repo_path(&data, &session_id)?;
    drop(data);

    let mut block =
        read_memory_block_from_file(&repo_path, &scope, &label).unwrap_or(MemoryBlock {
            label: label.clone(),
            scope: scope.clone(),
            description: None,
            limit: 2000,
            read_only: false,
            content: "".into(),
            updated_at: utc_now_iso(),
        });

    if block.read_only {
        return Err("memory block is read-only".into());
    }

    block.description = description.or(block.description);
    if let Some(v) = read_only {
        block.read_only = v;
    }
    if let Some(lim) = limit {
        if (200..=50_000).contains(&lim) {
            block.limit = lim;
        }
    }
    let trimmed = if content.chars().count() > block.limit {
        content.chars().take(block.limit).collect::<String>()
    } else {
        content
    };
    block.content = trimmed;
    block.updated_at = utc_now_iso();

    write_memory_block_to_file(&repo_path, &block)?;
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    let key = format!("{}:{}", session_id, scope);
    let existing = data.memories.entry(key).or_default();
    if let Some(idx) = existing.iter().position(|b| b.label == block.label) {
        existing[idx] = block.clone();
    } else {
        existing.push(block.clone());
    }
    state.save_locked(&data)?;

    Ok(block)
}

#[tauri::command]
pub fn write_repo_file(
    session_id: String,
    path: String,
    content: String,
    state: State<'_, AppState>,
) -> Result<(), String> {
    if path_is_sensitive(&path) {
        return Err("敏感文件已被策略阻止写入。".into());
    }
    if content.chars().count() > 200_000 {
        return Err("写入内容过大，已拒绝。".into());
    }
    let data = state.data.lock().map_err(|e| e.to_string())?;
    let repo_path = session_repo_path(&data, &session_id)?;
    drop(data);

    let file = safe_join_repo_path(&repo_path, &path)?;
    fs::write(&file, content).map_err(|e| format!("write file failed: {}", e))
}

#[tauri::command]
pub fn write_repo_file_atomic(
    session_id: String,
    path: String,
    content: String,
    if_match_sha256: Option<String>,
    state: State<'_, AppState>,
) -> Result<String, String> {
    if path_is_sensitive(&path) {
        return Err("敏感文件已被策略阻止写入。".into());
    }
    if content.chars().count() > 200_000 {
        return Err("写入内容过大，已拒绝。".into());
    }
    let data = state.data.lock().map_err(|e| e.to_string())?;
    let repo_path = session_repo_path(&data, &session_id)?;
    drop(data);

    let file = safe_join_repo_path(&repo_path, &path)?;
    let before = fs::read_to_string(&file).unwrap_or_default();
    if let Some(expected) = if_match_sha256 {
        if sha256_hex(&before) != expected {
            return Err("写入失败：文件已变更（sha256 mismatch）".into());
        }
    }

    let tmp = file.with_extension("tmp.codinggirl");
    fs::write(&tmp, &content).map_err(|e| format!("write temp failed: {}", e))?;
    fs::rename(&tmp, &file).map_err(|e| format!("rename temp failed: {}", e))?;
    Ok(sha256_hex(&content))
}

#[tauri::command]
pub fn search_repo(
    session_id: String,
    pattern: String,
    max_results: Option<usize>,
    state: State<'_, AppState>,
) -> Result<Vec<String>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    let repo_path = session_repo_path(&data, &session_id)?;
    drop(data);
    search_repo_inner(&repo_path, &pattern, max_results.unwrap_or(50).min(200))
}

#[tauri::command]
pub fn list_pending_approvals(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<ApprovalRequest>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data
        .pending_approvals
        .get(&session_id)
        .cloned()
        .unwrap_or_default())
}

#[tauri::command]
pub fn list_session_permissions(
    session_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<crate::state::SessionPermission>, String> {
    let data = state.data.lock().map_err(|e| e.to_string())?;
    Ok(data
        .session_permissions
        .iter()
        .filter(|p| p.session_id == session_id)
        .cloned()
        .collect())
}

#[tauri::command]
pub fn approve_request(
    session_id: String,
    approval_id: String,
    note: Option<String>,
    allow_session: Option<bool>,
    state: State<'_, AppState>,
) -> Result<ApprovalRequest, String> {
    let repo_path = {
        let data = state.data.lock().map_err(|e| e.to_string())?;
        session_repo_path(&data, &session_id)?
    };

    let req = {
        let data = state.data.lock().map_err(|e| e.to_string())?;
        data.pending_approvals
            .get(&session_id)
            .and_then(|v| v.iter().find(|r| r.id == approval_id).cloned())
            .ok_or_else(|| "approval not found".to_string())?
    };

    let result = execute_approval_request_inner(&repo_path, &req);
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    let persist = approval_mode_for_persist(allow_session);
    match result {
        Ok((result_json, maybe_diffs)) => {
            let updated = update_approval_request(
                &mut data,
                &session_id,
                &approval_id,
                ApprovalStatus::Approved,
                note,
                Some(result_json.clone()),
                Some(persist),
            )
            .ok_or_else(|| "approval update failed".to_string())?;
            if let Some(turn_id) = turn_id_for_run(&data, &session_id, req.run_id.as_deref()) {
                upsert_turn_item(
                    &mut data,
                    &session_id,
                    &turn_id,
                    approval_turn_item(&turn_id, req.run_id.as_deref(), &updated),
                );
            }

            if persist {
                data.session_permissions
                    .push(crate::state::SessionPermission {
                        session_id: session_id.clone(),
                        tool_name: req.tool_name.clone(),
                        action: req.action.clone(),
                        path: req.path.clone(),
                        granted_at: utc_now_iso(),
                    });
            }

            data.tools.entry(session_id.clone()).or_default().insert(
                0,
                ToolCallItem {
                    id: format!("tc-{}", now_millis_str()),
                    name: req.tool_name.clone(),
                    run_id: req.run_id.clone(),
                    status: crate::state::ToolStatus::Success,
                    duration_ms: 0,
                    args_json: req.args_json.clone(),
                    result_json,
                    correlation_id: req.correlation_id.clone(),
                },
            );
            if let Some(diffs) = maybe_diffs {
                let maybe_turn_id = turn_id_for_run(&data, &session_id, req.run_id.as_deref());
                let mut canonical_diffs = Vec::new();
                for mut diff in diffs {
                    diff.run_id = req.run_id.clone();
                    canonical_diffs.push(diff.clone());
                    {
                        let list = data.diffs.entry(session_id.clone()).or_default();
                        if let Some(idx) = list.iter().position(|existing| {
                            existing.path == diff.path && existing.run_id == diff.run_id
                        }) {
                            list[idx] = diff;
                        } else {
                            list.insert(0, diff);
                        }
                    }
                }
                if let Some(turn_id) = maybe_turn_id.as_ref() {
                    for canonical_diff in &canonical_diffs {
                        upsert_turn_item(
                            &mut data,
                            &session_id,
                            turn_id,
                            diff_turn_item(
                                turn_id,
                                req.run_id.as_deref().unwrap_or_default(),
                                canonical_diff,
                                req.correlation_id.clone(),
                            ),
                        );
                    }
                }
                if req.tool_name == "apply_patch" || req.tool_name == "repo_apply_unified_diff" {
                    if let Ok(args) = serde_json::from_str::<serde_json::Value>(&req.args_json) {
                        let patch_text = args
                            .get("patch")
                            .or_else(|| args.get("diff"))
                            .and_then(|v| v.as_str())
                            .unwrap_or("");
                        if !canonical_diffs.is_empty() {
                            if let Ok(persisted) = persist_patch_artifacts(
                                &repo_path,
                                &session_id,
                                &req.tool_name,
                                patch_text,
                                &canonical_diffs,
                                req.run_id.as_deref(),
                                req.correlation_id.clone(),
                                Some(&approval_id),
                            ) {
                                let turn_id =
                                    turn_id_for_run(&data, &session_id, req.run_id.as_deref());
                                for canonical_diff in &persisted.diffs {
                                    if let Some(turn_id) = turn_id.as_ref() {
                                        upsert_turn_item(
                                            &mut data,
                                            &session_id,
                                            turn_id,
                                            diff_turn_item(
                                                turn_id,
                                                req.run_id.as_deref().unwrap_or_default(),
                                                canonical_diff,
                                                req.correlation_id.clone(),
                                            ),
                                        );
                                    }
                                }
                                for a in &persisted.artifacts {
                                    if let Some(turn_id) = turn_id.as_ref() {
                                        upsert_turn_item(
                                            &mut data,
                                            &session_id,
                                            turn_id,
                                            artifact_turn_item(turn_id, req.run_id.as_deref(), a),
                                        );
                                    }
                                }
                                let list = data.artifacts.entry(session_id.clone()).or_default();
                                for a in persisted.artifacts.into_iter().rev() {
                                    list.insert(0, a);
                                }
                            }
                        }
                    }
                }
            }
            push_trace_event(
                &mut data,
                &session_id,
                "trace.approval.approved".into(),
                TimelineStatus::Success,
                Some(format!(
                    "tool={} action={} path={}",
                    req.tool_name,
                    req.action,
                    req.path.clone().unwrap_or_default()
                )),
                "approval",
                req.correlation_id.clone(),
            );
            state.save_locked(&data)?;
            Ok(updated)
        }
        Err(err) => {
            let updated = update_approval_request(
                &mut data,
                &session_id,
                &approval_id,
                ApprovalStatus::Failed,
                Some(err.clone()),
                Some(json!({"error": err}).to_string()),
                Some(false),
            )
            .ok_or_else(|| "approval update failed".to_string())?;
            if let Some(turn_id) = turn_id_for_run(&data, &session_id, req.run_id.as_deref()) {
                let error_info = classify_error(&err, ErrorContext::Approval);
                upsert_turn_item(
                    &mut data,
                    &session_id,
                    &turn_id,
                    approval_turn_item(&turn_id, req.run_id.as_deref(), &updated),
                );
                upsert_turn_item(
                    &mut data,
                    &session_id,
                    &turn_id,
                    error_turn_item(
                        &turn_id,
                        req.run_id.as_deref(),
                        &format!("{}-approval-error", approval_id),
                        "审批执行失败",
                        Some(err.chars().take(180).collect::<String>()),
                        Some(err.clone()),
                        Some(
                            json!({
                                "message": err.clone(),
                                "source": "approve_request",
                                "approvalId": approval_id,
                            })
                            .to_string(),
                        ),
                        &error_info,
                    ),
                );
            }
            data.tools.entry(session_id.clone()).or_default().insert(
                0,
                ToolCallItem {
                    id: format!("tc-{}", now_millis_str()),
                    name: req.tool_name.clone(),
                    run_id: req.run_id.clone(),
                    status: crate::state::ToolStatus::Failed,
                    duration_ms: 0,
                    args_json: req.args_json.clone(),
                    result_json: json!({"error": err}).to_string(),
                    correlation_id: req.correlation_id.clone(),
                },
            );
            push_trace_event(
                &mut data,
                &session_id,
                "trace.approval.failed".into(),
                TimelineStatus::Failed,
                Some(err.clone()),
                "approval",
                req.correlation_id.clone(),
            );
            state.save_locked(&data)?;
            Ok(updated)
        }
    }
}

#[tauri::command]
pub fn reject_request(
    session_id: String,
    approval_id: String,
    note: Option<String>,
    state: State<'_, AppState>,
) -> Result<ApprovalRequest, String> {
    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    let updated = update_approval_request(
        &mut data,
        &session_id,
        &approval_id,
        ApprovalStatus::Rejected,
        note,
        Some(json!({"rejected": true}).to_string()),
        Some(false),
    )
    .ok_or_else(|| "approval not found".to_string())?;
    if let Some(turn_id) = turn_id_for_run(&data, &session_id, updated.run_id.as_deref()) {
        upsert_turn_item(
            &mut data,
            &session_id,
            &turn_id,
            approval_turn_item(&turn_id, updated.run_id.as_deref(), &updated),
        );
    }
    push_trace_event(
        &mut data,
        &session_id,
        "trace.approval.rejected".into(),
        TimelineStatus::Failed,
        Some("user rejected".into()),
        "approval",
        None,
    );
    state.save_locked(&data)?;
    Ok(updated)
}

#[tauri::command]
pub fn rollback_patch_artifact(
    session_id: String,
    rollback_meta_path: String,
    state: State<'_, AppState>,
) -> Result<(), String> {
    let repo_path = {
        let data = state.data.lock().map_err(|e| e.to_string())?;
        session_repo_path(&data, &session_id)?
    };
    let rollback_user_text = format!("rollback {}", rollback_meta_path);
    let (run_id, turn_id) = {
        let mut data = state.data.lock().map_err(|e| e.to_string())?;
        let (run, _) = create_session_run(
            &mut data,
            &session_id,
            "rollback",
            "rollback_patch_artifact",
            &rollback_user_text,
        );
        upsert_session_preflight_item(
            &mut data,
            &session_id,
            &run.turn_id,
            Some(&run.id),
            "rollback",
            "rollback_patch_artifact",
        )?;
        upsert_turn_item(
            &mut data,
            &session_id,
            &run.turn_id,
            phase_turn_item(
                &run.turn_id,
                Some(&run.id),
                &format!("{}-rollback", run.turn_id),
                "rollback.execute",
                TimelineStatus::Running,
                Some(format!("rollback_meta={}", rollback_meta_path)),
                Some(format!("准备回滚补丁元数据：{}", rollback_meta_path)),
                None,
                Some(
                    json!({
                        "rollbackMetaPath": rollback_meta_path.clone(),
                        "phase": "started",
                    })
                    .to_string(),
                ),
            ),
        );
        state.save_locked(&data)?;
        (run.id, run.turn_id)
    };

    let rollback_result = (|| -> Result<(), String> {
        let rollback_file = resolve_repo_scoped_path(&repo_path, &rollback_meta_path)?;
        let raw = fs::read_to_string(&rollback_file)
            .map_err(|e| format!("read rollback metadata failed: {}", e))?;
        let val: serde_json::Value = serde_json::from_str(&raw)
            .map_err(|e| format!("invalid rollback metadata json: {}", e))?;
        let files = val
            .get("files")
            .and_then(|v| v.as_array())
            .ok_or_else(|| "rollback metadata missing files".to_string())?;

        for f in files {
            let path = f
                .get("path")
                .and_then(|v| v.as_str())
                .ok_or_else(|| "rollback item missing path".to_string())?;
            let old_content = f
                .get("old_content")
                .and_then(|v| v.as_str())
                .or_else(|| f.get("old_snippet").and_then(|v| v.as_str()))
                .unwrap_or("");
            let abs = safe_join_repo_path(&repo_path, path)?;
            if old_content.is_empty() {
                if abs.exists() {
                    fs::remove_file(&abs).map_err(|e| format!("rollback remove failed: {}", e))?;
                }
                continue;
            }
            let _ = write_repo_file_atomic_inner(&repo_path, path, old_content, None)?;
        }
        Ok(())
    })();

    let mut data = state.data.lock().map_err(|e| e.to_string())?;
    match rollback_result {
        Ok(()) => {
            upsert_turn_item(
                &mut data,
                &session_id,
                &turn_id,
                phase_turn_item(
                    &turn_id,
                    Some(&run_id),
                    &format!("{}-rollback", turn_id),
                    "rollback.execute",
                    TimelineStatus::Success,
                    Some(format!("rollback_meta={}", rollback_meta_path)),
                    Some(format!("已完成回滚：{}", rollback_meta_path)),
                    None,
                    Some(
                        json!({
                            "rollbackMetaPath": rollback_meta_path.clone(),
                            "phase": "completed",
                        })
                        .to_string(),
                    ),
                ),
            );
            finish_session_run(
                &mut data,
                &session_id,
                &run_id,
                RunStatus::Success,
                Some(format!("rollback completed: {}", rollback_meta_path)),
                None,
            );
            complete_session_turn(&mut data, &session_id, &turn_id, RunStatus::Success);
            push_trace_event(
                &mut data,
                &session_id,
                "trace.rollback.executed".into(),
                TimelineStatus::Success,
                Some(format!("rollback_meta={}", rollback_meta_path)),
                "rollback",
                None,
            );
            state.save_locked(&data)?;
            Ok(())
        }
        Err(err) => {
            let error_info = classify_error(&err, ErrorContext::Rollback);
            upsert_turn_item(
                &mut data,
                &session_id,
                &turn_id,
                phase_turn_item(
                    &turn_id,
                    Some(&run_id),
                    &format!("{}-rollback", turn_id),
                    "rollback.execute",
                    TimelineStatus::Failed,
                    Some(format!("rollback_meta={}", rollback_meta_path)),
                    Some(err.clone()),
                    None,
                    Some(
                        json!({
                            "rollbackMetaPath": rollback_meta_path.clone(),
                            "phase": "failed",
                            "error": err.clone(),
                        })
                        .to_string(),
                    ),
                ),
            );
            upsert_turn_item(
                &mut data,
                &session_id,
                &turn_id,
                error_turn_item(
                    &turn_id,
                    Some(&run_id),
                    &format!("{}-rollback-error", turn_id),
                    "回滚失败",
                    Some(err.chars().take(180).collect::<String>()),
                    Some(err.clone()),
                    Some(
                        json!({
                            "message": err.clone(),
                            "source": "rollback_patch_artifact",
                            "rollbackMetaPath": rollback_meta_path.clone(),
                        })
                        .to_string(),
                    ),
                    &error_info,
                ),
            );
            finish_session_run(
                &mut data,
                &session_id,
                &run_id,
                RunStatus::Failed,
                None,
                Some(err.clone()),
            );
            complete_session_turn(&mut data, &session_id, &turn_id, RunStatus::Failed);
            push_trace_event(
                &mut data,
                &session_id,
                "trace.rollback.failed".into(),
                TimelineStatus::Failed,
                Some(err.clone()),
                "rollback",
                None,
            );
            state.save_locked(&data)?;
            Err(err)
        }
    }
}
