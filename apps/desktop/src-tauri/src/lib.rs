mod commands;
mod error_taxonomy;
mod patch_apply;
mod runtime_events;
mod state;
mod timeline_projection;

use std::path::PathBuf;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            commands::list_repos,
            commands::list_sessions,
            commands::get_timeline,
            commands::get_session_events,
            commands::list_session_runs,
            commands::list_session_turns,
            commands::get_diff_files,
            commands::get_tool_calls,
            commands::get_logs,
            commands::get_artifacts,
            commands::get_approval_meta,
            commands::run_session_message,
            commands::run_python_agent_message,
            commands::cancel_python_agent_run,
            commands::create_session,
            commands::delete_session,
            commands::update_session_mode,
            commands::add_repo,
            commands::remove_repo,
            commands::toggle_repo_pin,
            commands::get_settings,
            commands::save_settings,
            commands::get_security_policies,
            commands::save_security_policies,
            commands::list_plugins,
            commands::import_plugin,
            commands::toggle_plugin_enabled,
            commands::remove_plugin,
            commands::list_repo_tree,
            commands::read_repo_file,
            commands::write_repo_file,
            commands::write_repo_file_atomic,
            commands::search_repo,
            commands::list_pending_approvals,
            commands::list_session_permissions,
            commands::approve_request,
            commands::reject_request,
            commands::rollback_patch_artifact,
            commands::export_trace_bundle,
            commands::get_chat_history,
            commands::get_chat_summary,
            commands::get_session_context_debug,
            commands::list_memory_blocks,
            commands::run_terminal_command,
            commands::open_path_in_explorer,
            commands::open_path_in_vscode,
            commands::set_memory_block,
        ])
        .setup(|app| {
            let base_dir = app
                .path()
                .app_data_dir()
                .unwrap_or_else(|_| PathBuf::from(".codinggirl"));
            let data_file = base_dir.join("state.json");
            app.manage(state::AppState::load(data_file));

            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
