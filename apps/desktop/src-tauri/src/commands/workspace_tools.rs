use crate::commands::common::{resolve_repo_scoped_path, session_repo_path};
use crate::commands::policy::push_turn_event_for_run;
use crate::commands::session_runtime::{
    create_session_run, finish_session_run, upsert_session_preflight_item,
};
use crate::commands::turn_manager::{command_turn_item, complete_session_turn, upsert_turn_item};
use crate::error_taxonomy::{classify_error, ErrorContext};
use crate::state::AppState;
use serde::Serialize;
use serde_json::json;
use std::path::{Path, PathBuf};
use std::process::Command;
use tauri::async_runtime::spawn_blocking;
use tauri::State;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TerminalCommandResult {
    pub command: String,
    pub cwd: String,
    pub stdout: String,
    pub stderr: String,
    pub exit_code: i32,
    pub success: bool,
    #[serde(rename = "runId")]
    pub run_id: Option<String>,
    #[serde(rename = "turnId")]
    pub turn_id: Option<String>,
}

fn canonical_repo_root(repo_root: &str) -> Result<PathBuf, String> {
    PathBuf::from(repo_root)
        .canonicalize()
        .map_err(|e| format!("repo root inaccessible: {}", e))
}

fn normalize_terminal_cwd(repo_root: &str, cwd: Option<&str>) -> Result<PathBuf, String> {
    match cwd.map(str::trim).filter(|value| !value.is_empty()) {
        Some(value) => resolve_repo_scoped_path(repo_root, value),
        None => canonical_repo_root(repo_root),
    }
}

fn parse_cd_target(command: &str) -> Option<String> {
    let trimmed = command.trim();
    if trimmed.eq_ignore_ascii_case("cd") {
        return Some(String::new());
    }
    let lower = trimmed.to_ascii_lowercase();
    if lower.starts_with("cd /d ") {
        return Some(trimmed[6..].trim().to_string());
    }
    if lower.starts_with("cd ") {
        return Some(trimmed[3..].trim().to_string());
    }
    None
}

fn resolve_cd_target(
    repo_root: &str,
    current_dir: &Path,
    raw_target: &str,
) -> Result<PathBuf, String> {
    let target = raw_target.trim().trim_matches('"');
    if target.is_empty() {
        return Ok(current_dir.to_path_buf());
    }

    let repo_root = canonical_repo_root(repo_root)?;
    let candidate = PathBuf::from(target);
    let resolved = if candidate.is_absolute() {
        resolve_repo_scoped_path(repo_root.to_string_lossy().as_ref(), target)?
    } else {
        current_dir
            .join(candidate)
            .canonicalize()
            .map_err(|e| format!("cannot change directory: {}", e))?
    };

    if !resolved.starts_with(&repo_root) {
        return Err("terminal cwd cannot escape repository root".into());
    }
    Ok(resolved)
}

fn powershell_command_payload(command: &str) -> String {
    format!(
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; {}",
        command
    )
}

fn try_spawn_vscode(path: &Path) -> Result<(), String> {
    let path_arg = path.to_string_lossy().to_string();
    let mut candidates = vec!["code".to_string(), "code.cmd".to_string()];

    if let Ok(local_app_data) = std::env::var("LOCALAPPDATA") {
        candidates.push(format!(
            "{}\\Programs\\Microsoft VS Code\\Code.exe",
            local_app_data
        ));
    }
    if let Ok(program_files) = std::env::var("ProgramFiles") {
        candidates.push(format!("{}\\Microsoft VS Code\\Code.exe", program_files));
    }
    if let Ok(program_files_x86) = std::env::var("ProgramFiles(x86)") {
        candidates.push(format!(
            "{}\\Microsoft VS Code\\Code.exe",
            program_files_x86
        ));
    }

    let mut last_error = None;
    for candidate in candidates {
        let mut process = Command::new(&candidate);
        process.arg("-n").arg(&path_arg);
        match process.spawn() {
            Ok(_) => return Ok(()),
            Err(err) => {
                last_error = Some(format!("{}: {}", candidate, err));
            }
        }
    }

    Err(format!(
        "failed to launch VS Code. Ensure the `code` command or Code.exe is available. {}",
        last_error.unwrap_or_default()
    ))
}

fn explorer_target(path: &Path) -> Result<String, String> {
    let canonical = path
        .canonicalize()
        .map_err(|e| format!("path inaccessible: {}", e))?;
    Ok(canonical.to_string_lossy().replace('/', "\\"))
}

#[tauri::command]
pub async fn run_terminal_command(
    session_id: String,
    command: String,
    cwd: Option<String>,
    state: State<'_, AppState>,
) -> Result<TerminalCommandResult, String> {
    let command = command.trim().to_string();
    if command.is_empty() {
        return Err("terminal command is empty".into());
    }
    let (repo_root, initial_cwd, run_id, turn_id, command_item_id, command_corr) = {
        let mut data = state.data.lock().map_err(|e| e.to_string())?;
        let repo_root = session_repo_path(&data, &session_id)?;
        let initial_cwd = normalize_terminal_cwd(&repo_root, cwd.as_deref())?;
        let (run, _) = create_session_run(
            &mut data,
            &session_id,
            "terminal",
            "terminal_command",
            &command,
        );
        upsert_session_preflight_item(
            &mut data,
            &session_id,
            &run.turn_id,
            Some(&run.id),
            "terminal",
            "terminal_command",
        )?;
        let command_item_id = format!("cmd-{}", run.id);
        let command_corr = format!("corr-{}", command_item_id);
        push_turn_event_for_run(
            &mut data,
            &session_id,
            Some(&run.id),
            "turn.started".into(),
            crate::state::TimelineStatus::Running,
            Some("terminal command started".into()),
            "session",
            None,
            "turn.started",
            Some(run.turn_id.clone()),
            None,
            None,
        );
        push_turn_event_for_run(
            &mut data,
            &session_id,
            Some(&run.id),
            "item.started:command.terminal".into(),
            crate::state::TimelineStatus::Running,
            Some(format!("running terminal command: {}", command)),
            "command",
            Some(command_corr.clone()),
            "item.started",
            Some(run.turn_id.clone()),
            Some(command_item_id.clone()),
            Some("command".into()),
        );
        upsert_turn_item(
            &mut data,
            &session_id,
            &run.turn_id,
            command_turn_item(
                &run.turn_id,
                Some(&run.id),
                &command_item_id,
                "terminal.command",
                crate::state::TimelineStatus::Running,
                Some(command.clone()),
                Some(format!(
                    "cwd: {}\n\ncommand:\n{}",
                    initial_cwd.to_string_lossy(),
                    command
                )),
                Some(initial_cwd.to_string_lossy().to_string()),
                Some(command_corr.clone()),
                Some(
                    json!({
                        "command": command.clone(),
                        "cwd": initial_cwd.to_string_lossy().to_string(),
                        "phase": "started",
                    })
                    .to_string(),
                ),
                None,
            ),
        );
        state.save_locked(&data)?;
        (
            repo_root,
            initial_cwd,
            run.id,
            run.turn_id,
            command_item_id,
            command_corr,
        )
    };
    let command_text = command.clone();
    let initial_cwd_text = initial_cwd.to_string_lossy().to_string();

    let execution: Result<TerminalCommandResult, String> = match spawn_blocking(move || {
        if let Some(target) = parse_cd_target(&command) {
            let next_dir = resolve_cd_target(&repo_root, &initial_cwd, &target)?;
            return Ok(TerminalCommandResult {
                command,
                cwd: next_dir.to_string_lossy().to_string(),
                stdout: String::new(),
                stderr: String::new(),
                exit_code: 0,
                success: true,
                run_id: None,
                turn_id: None,
            });
        }

        let output = Command::new("powershell")
            .args([
                "-NoLogo",
                "-NoProfile",
                "-Command",
                &powershell_command_payload(&command),
            ])
            .current_dir(&initial_cwd)
            .output()
            .map_err(|e| format!("terminal command failed to start: {}", e))?;

        Ok(TerminalCommandResult {
            command,
            cwd: initial_cwd.to_string_lossy().to_string(),
            stdout: String::from_utf8_lossy(&output.stdout).to_string(),
            stderr: String::from_utf8_lossy(&output.stderr).to_string(),
            exit_code: output.status.code().unwrap_or(-1),
            success: output.status.success(),
            run_id: None,
            turn_id: None,
        })
    })
    .await
    {
        Ok(execution) => execution,
        Err(err) => {
            let err = format!("terminal task join failed: {}", err);
            let mut data = state.data.lock().map_err(|e| e.to_string())?;
            push_turn_event_for_run(
                &mut data,
                &session_id,
                Some(&run_id),
                "item.completed:command.terminal".into(),
                crate::state::TimelineStatus::Failed,
                Some(err.clone()),
                "command",
                Some(command_corr.clone()),
                "item.completed",
                Some(turn_id.clone()),
                Some(command_item_id.clone()),
                Some("command".into()),
            );
            upsert_turn_item(&mut data, &session_id, &turn_id, {
                let error_info = classify_error(&err, ErrorContext::Command);
                command_turn_item(
                    &turn_id,
                    Some(&run_id),
                    &command_item_id,
                    "terminal.command",
                    crate::state::TimelineStatus::Failed,
                    Some(format!("{} · failed", command_text)),
                    Some(format!(
                        "cwd: {}\n\ncommand:\n{}\n\nerror:\n{}",
                        initial_cwd_text, command_text, err
                    )),
                    Some(initial_cwd_text.clone()),
                    Some(command_corr.clone()),
                    Some(
                        json!({
                            "command": command_text.clone(),
                            "cwd": initial_cwd_text.clone(),
                            "error": err.clone(),
                            "success": false,
                        })
                        .to_string(),
                    ),
                    Some(&error_info),
                )
            });
            finish_session_run(
                &mut data,
                &session_id,
                &run_id,
                crate::state::RunStatus::Failed,
                None,
                Some(err.clone()),
            );
            complete_session_turn(
                &mut data,
                &session_id,
                &turn_id,
                crate::state::RunStatus::Failed,
            );
            push_turn_event_for_run(
                &mut data,
                &session_id,
                Some(&run_id),
                "turn.failed".into(),
                crate::state::TimelineStatus::Failed,
                Some("terminal command failed before producing a result".into()),
                "session",
                None,
                "turn.failed",
                Some(turn_id.clone()),
                None,
                None,
            );
            state.save_locked(&data)?;
            return Err(err);
        }
    };

    let result = match execution {
        Ok(result) => result,
        Err(err) => {
            let mut data = state.data.lock().map_err(|e| e.to_string())?;
            push_turn_event_for_run(
                &mut data,
                &session_id,
                Some(&run_id),
                "item.completed:command.terminal".into(),
                crate::state::TimelineStatus::Failed,
                Some(err.clone()),
                "command",
                Some(command_corr.clone()),
                "item.completed",
                Some(turn_id.clone()),
                Some(command_item_id.clone()),
                Some("command".into()),
            );
            upsert_turn_item(&mut data, &session_id, &turn_id, {
                let error_info = classify_error(&err, ErrorContext::Command);
                command_turn_item(
                    &turn_id,
                    Some(&run_id),
                    &command_item_id,
                    "terminal.command",
                    crate::state::TimelineStatus::Failed,
                    Some(format!("{} · failed", command_text)),
                    Some(format!(
                        "cwd: {}\n\ncommand:\n{}\n\nerror:\n{}",
                        initial_cwd_text, command_text, err
                    )),
                    Some(initial_cwd_text.clone()),
                    Some(command_corr.clone()),
                    Some(
                        json!({
                            "command": command_text.clone(),
                            "cwd": initial_cwd_text.clone(),
                            "error": err.clone(),
                            "success": false,
                        })
                        .to_string(),
                    ),
                    Some(&error_info),
                )
            });
            finish_session_run(
                &mut data,
                &session_id,
                &run_id,
                crate::state::RunStatus::Failed,
                None,
                Some(err.clone()),
            );
            complete_session_turn(
                &mut data,
                &session_id,
                &turn_id,
                crate::state::RunStatus::Failed,
            );
            push_turn_event_for_run(
                &mut data,
                &session_id,
                Some(&run_id),
                "turn.failed".into(),
                crate::state::TimelineStatus::Failed,
                Some("terminal command failed before producing a result".into()),
                "session",
                None,
                "turn.failed",
                Some(turn_id.clone()),
                None,
                None,
            );
            state.save_locked(&data)?;
            return Err(err);
        }
    };

    {
        let mut data = state.data.lock().map_err(|e| e.to_string())?;
        push_turn_event_for_run(
            &mut data,
            &session_id,
            Some(&run_id),
            "item.completed:command.terminal".into(),
            if result.success {
                crate::state::TimelineStatus::Success
            } else {
                crate::state::TimelineStatus::Failed
            },
            Some(format!(
                "terminal command finished with exit code {}",
                result.exit_code
            )),
            "command",
            Some(command_corr.clone()),
            "item.completed",
            Some(turn_id.clone()),
            Some(command_item_id.clone()),
            Some("command".into()),
        );
        upsert_turn_item(&mut data, &session_id, &turn_id, {
            let error_info = (!result.success).then(|| {
                classify_error(
                    &format!(
                        "{}\n{}",
                        result.stderr,
                        if result.stdout.trim().is_empty() {
                            format!("exit code {}", result.exit_code)
                        } else {
                            result.stdout.clone()
                        }
                    ),
                    ErrorContext::Command,
                )
            });
            command_turn_item(
                &turn_id,
                Some(&run_id),
                &command_item_id,
                "terminal.command",
                if result.success {
                    crate::state::TimelineStatus::Success
                } else {
                    crate::state::TimelineStatus::Failed
                },
                Some(format!("{} · exit {}", result.command, result.exit_code)),
                Some(format!(
                    "cwd: {}\n\ncommand:\n{}\n\nstdout:\n{}\n\nstderr:\n{}",
                    result.cwd,
                    result.command,
                    if result.stdout.trim().is_empty() {
                        "<empty>"
                    } else {
                        result.stdout.trim_end()
                    },
                    if result.stderr.trim().is_empty() {
                        "<empty>"
                    } else {
                        result.stderr.trim_end()
                    }
                )),
                Some(result.cwd.clone()),
                Some(command_corr),
                Some(
                    json!({
                        "command": result.command.clone(),
                        "cwd": result.cwd.clone(),
                        "stdout": result.stdout.clone(),
                        "stderr": result.stderr.clone(),
                        "exitCode": result.exit_code,
                        "success": result.success,
                    })
                    .to_string(),
                ),
                error_info.as_ref(),
            )
        });
        finish_session_run(
            &mut data,
            &session_id,
            &run_id,
            if result.success {
                crate::state::RunStatus::Success
            } else {
                crate::state::RunStatus::Failed
            },
            Some(format!(
                "terminal command finished with exit code {}",
                result.exit_code
            )),
            if result.success {
                None
            } else {
                Some(result.stderr.clone())
            },
        );
        complete_session_turn(
            &mut data,
            &session_id,
            &turn_id,
            if result.success {
                crate::state::RunStatus::Success
            } else {
                crate::state::RunStatus::Failed
            },
        );
        push_turn_event_for_run(
            &mut data,
            &session_id,
            Some(&run_id),
            if result.success {
                "turn.completed".into()
            } else {
                "turn.failed".into()
            },
            if result.success {
                crate::state::TimelineStatus::Success
            } else {
                crate::state::TimelineStatus::Failed
            },
            Some("terminal command finished".into()),
            "session",
            None,
            if result.success {
                "turn.completed"
            } else {
                "turn.failed"
            },
            Some(turn_id.clone()),
            None,
            None,
        );
        state.save_locked(&data)?;
    }

    Ok(TerminalCommandResult {
        run_id: Some(run_id),
        turn_id: Some(turn_id),
        ..result
    })
}

#[tauri::command]
pub fn open_path_in_explorer(path: String) -> Result<(), String> {
    let target = PathBuf::from(path.trim());
    if !target.exists() {
        return Err("path does not exist".into());
    }
    Command::new("explorer.exe")
        .arg(explorer_target(&target)?)
        .spawn()
        .map_err(|e| format!("failed to open explorer: {}", e))?;
    Ok(())
}

#[tauri::command]
pub fn open_path_in_vscode(path: String) -> Result<(), String> {
    let target = PathBuf::from(path.trim());
    if !target.exists() {
        return Err("path does not exist".into());
    }
    try_spawn_vscode(&target)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn parse_cd_target_supports_basic_forms() {
        assert_eq!(parse_cd_target("cd foo").as_deref(), Some("foo"));
        assert_eq!(parse_cd_target("cd /d bar").as_deref(), Some("bar"));
        assert_eq!(parse_cd_target("pwd"), None);
    }

    #[test]
    fn explorer_target_uses_windows_separators() {
        let temp =
            std::env::temp_dir().join(format!("coding-agent-explorer-{}", std::process::id()));
        let _ = fs::create_dir_all(&temp);
        let target = explorer_target(&temp).expect("target should resolve");
        assert!(!target.contains('/'));
    }
}
