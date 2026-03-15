use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;

use crate::error_taxonomy::ErrorCategory;
pub use crate::timeline_projection::{
    project_session_events_from_turns, project_timeline_from_events, project_timeline_from_turns,
};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryBlock {
    pub label: String,
    pub scope: String,
    pub description: Option<String>,
    pub limit: usize,
    #[serde(rename = "readOnly")]
    pub read_only: bool,
    pub content: String,
    #[serde(rename = "updatedAt")]
    pub updated_at: String,
}
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ApprovalStatus {
    Pending,
    Approved,
    Rejected,
    Failed,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApprovalRequest {
    pub id: String,
    #[serde(rename = "sessionId")]
    pub session_id: String,
    #[serde(rename = "runId")]
    #[serde(default)]
    pub run_id: Option<String>,
    #[serde(rename = "toolName")]
    pub tool_name: String,
    #[serde(default)]
    pub action: String,
    #[serde(default)]
    pub path: Option<String>,
    #[serde(rename = "argsJson")]
    pub args_json: String,
    #[serde(rename = "createdAt")]
    pub created_at: String,
    pub status: ApprovalStatus,
    #[serde(rename = "decisionNote")]
    pub decision_note: Option<String>,
    #[serde(rename = "resultJson")]
    pub result_json: Option<String>,
    #[serde(rename = "allowSession")]
    #[serde(default)]
    pub allow_session: bool,
    #[serde(rename = "correlationId")]
    #[serde(default)]
    pub correlation_id: Option<String>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionPermission {
    #[serde(rename = "sessionId")]
    pub session_id: String,
    #[serde(rename = "toolName")]
    pub tool_name: String,
    pub action: String,
    pub path: Option<String>,
    #[serde(rename = "grantedAt")]
    pub granted_at: String,
}
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum TimelineStatus {
    Pending,
    Running,
    Success,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ToolStatus {
    Success,
    Failed,
    Running,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum LogLevel {
    Info,
    Warn,
    Error,
    Debug,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ArtifactKind {
    Patch,
    Report,
    Index,
    Trace,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MutationSourceKind {
    ApplyPatch,
    UnifiedDiff,
    DirectWrite,
    ApprovalReplay,
    Rollback,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MutationProvenance {
    #[serde(rename = "sourceKind")]
    pub source_kind: MutationSourceKind,
    #[serde(rename = "toolName")]
    pub tool_name: String,
    #[serde(rename = "sessionId")]
    pub session_id: String,
    #[serde(rename = "runId")]
    #[serde(default)]
    pub run_id: Option<String>,
    #[serde(rename = "correlationId")]
    #[serde(default)]
    pub correlation_id: Option<String>,
    #[serde(rename = "artifactGroupId")]
    #[serde(default)]
    pub artifact_group_id: Option<String>,
    #[serde(rename = "rollbackMetaPath")]
    #[serde(default)]
    pub rollback_meta_path: Option<String>,
    #[serde(rename = "approvalId")]
    #[serde(default)]
    pub approval_id: Option<String>,
    #[serde(rename = "createdAt")]
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum RiskLevel {
    Low,
    Medium,
    High,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Provider {
    Mock,
    OpenaiCompatible,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RepoItem {
    pub id: String,
    pub name: String,
    pub path: String,
    pub pinned: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionItem {
    pub id: String,
    #[serde(rename = "repoId")]
    pub repo_id: String,
    pub title: String,
    pub mode: String,
    #[serde(rename = "createdAt")]
    pub created_at: String,
    #[serde(rename = "updatedAt")]
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum RunStatus {
    Running,
    Success,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SessionTurnItemKind {
    UserMessage,
    AssistantMessage,
    Error,
    Reasoning,
    Phase,
    Context,
    Compaction,
    ModelRequest,
    Validation,
    Command,
    ToolCall,
    Diff,
    Approval,
    Artifact,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionTurnItem {
    pub id: String,
    #[serde(rename = "turnId")]
    pub turn_id: String,
    #[serde(rename = "runId")]
    #[serde(default)]
    pub run_id: Option<String>,
    pub kind: SessionTurnItemKind,
    pub status: TimelineStatus,
    pub title: String,
    #[serde(default)]
    pub summary: Option<String>,
    #[serde(default)]
    pub detail: Option<String>,
    #[serde(rename = "toolName")]
    #[serde(default)]
    pub tool_name: Option<String>,
    #[serde(default)]
    pub path: Option<String>,
    #[serde(rename = "correlationId")]
    #[serde(default)]
    pub correlation_id: Option<String>,
    #[serde(rename = "dataJson")]
    #[serde(default)]
    pub data_json: Option<String>,
    #[serde(rename = "errorCategory")]
    #[serde(default)]
    pub error_category: Option<ErrorCategory>,
    #[serde(rename = "errorCode")]
    #[serde(default)]
    pub error_code: Option<String>,
    #[serde(default)]
    pub retryable: Option<bool>,
    #[serde(rename = "retryHint")]
    #[serde(default)]
    pub retry_hint: Option<String>,
    #[serde(rename = "fallbackHint")]
    #[serde(default)]
    pub fallback_hint: Option<String>,
    #[serde(rename = "createdAt")]
    pub created_at: String,
    #[serde(rename = "updatedAt")]
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionTurn {
    pub id: String,
    #[serde(rename = "sessionId")]
    pub session_id: String,
    #[serde(rename = "runId")]
    #[serde(default)]
    pub run_id: Option<String>,
    pub mode: String,
    #[serde(default)]
    pub route: Option<String>,
    #[serde(rename = "routeSource")]
    #[serde(default)]
    pub route_source: Option<String>,
    #[serde(rename = "routeReason")]
    #[serde(default)]
    pub route_reason: Option<String>,
    #[serde(rename = "routeSignals")]
    #[serde(default)]
    pub route_signals: Vec<String>,
    #[serde(rename = "userText")]
    #[serde(default)]
    pub user_text: Option<String>,
    pub status: RunStatus,
    pub items: Vec<SessionTurnItem>,
    #[serde(rename = "createdAt")]
    pub created_at: String,
    #[serde(rename = "updatedAt")]
    pub updated_at: String,
    #[serde(rename = "completedAt")]
    pub completed_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionRun {
    pub id: String,
    #[serde(rename = "sessionId")]
    pub session_id: String,
    #[serde(rename = "turnId")]
    pub turn_id: String,
    pub mode: String,
    #[serde(rename = "userText")]
    pub user_text: String,
    #[serde(rename = "assistantMessage")]
    pub assistant_message: Option<String>,
    #[serde(rename = "errorText")]
    pub error_text: Option<String>,
    pub status: RunStatus,
    #[serde(rename = "createdAt")]
    pub created_at: String,
    #[serde(rename = "updatedAt")]
    pub updated_at: String,
    #[serde(rename = "completedAt")]
    pub completed_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionEvent {
    #[serde(rename = "eventId")]
    pub event_id: String,
    #[serde(rename = "sessionId")]
    pub session_id: String,
    #[serde(rename = "turnId")]
    #[serde(default)]
    pub turn_id: Option<String>,
    #[serde(rename = "runId")]
    #[serde(default)]
    pub run_id: Option<String>,
    #[serde(rename = "correlationId")]
    #[serde(default)]
    pub correlation_id: Option<String>,
    #[serde(rename = "agentId")]
    #[serde(default)]
    pub agent_id: Option<String>,
    #[serde(rename = "parentAgentId")]
    #[serde(default)]
    pub parent_agent_id: Option<String>,
    pub kind: String,
    pub title: String,
    pub status: TimelineStatus,
    pub detail: Option<String>,
    #[serde(rename = "traceType")]
    #[serde(default)]
    pub trace_type: Option<String>,
    #[serde(rename = "itemId")]
    #[serde(default)]
    pub item_id: Option<String>,
    #[serde(rename = "itemType")]
    #[serde(default)]
    pub item_type: Option<String>,
    pub ts: String,
    pub seq: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimelineStep {
    pub id: String,
    pub title: String,
    pub status: TimelineStatus,
    pub detail: Option<String>,
    #[serde(rename = "traceType")]
    #[serde(default)]
    pub trace_type: Option<String>,
    #[serde(default)]
    pub ts: Option<String>,
    #[serde(rename = "correlationId")]
    #[serde(default)]
    pub correlation_id: Option<String>,
    #[serde(rename = "eventKind")]
    #[serde(default)]
    pub event_kind: Option<String>,
    #[serde(rename = "turnId")]
    #[serde(default)]
    pub turn_id: Option<String>,
    #[serde(rename = "runId")]
    #[serde(default)]
    pub run_id: Option<String>,
    #[serde(rename = "itemId")]
    #[serde(default)]
    pub item_id: Option<String>,
    #[serde(rename = "itemType")]
    #[serde(default)]
    pub item_type: Option<String>,
    #[serde(default)]
    pub sequence: Option<i64>,
    #[serde(rename = "agentId")]
    #[serde(default)]
    pub agent_id: Option<String>,
    #[serde(rename = "parentAgentId")]
    #[serde(default)]
    pub parent_agent_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiffFile {
    pub id: String,
    pub path: String,
    #[serde(rename = "runId")]
    #[serde(default)]
    pub run_id: Option<String>,
    pub additions: i32,
    pub deletions: i32,
    #[serde(rename = "oldSnippet")]
    pub old_snippet: String,
    #[serde(rename = "newSnippet")]
    pub new_snippet: String,
    #[serde(rename = "unifiedSnippet")]
    pub unified_snippet: String,
    pub diff: String,
    #[serde(rename = "mutationProvenance")]
    #[serde(default)]
    pub mutation_provenance: Option<MutationProvenance>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCallItem {
    pub id: String,
    pub name: String,
    #[serde(rename = "runId")]
    #[serde(default)]
    pub run_id: Option<String>,
    pub status: ToolStatus,
    #[serde(rename = "durationMs")]
    pub duration_ms: i32,
    #[serde(rename = "argsJson")]
    pub args_json: String,
    #[serde(rename = "resultJson")]
    pub result_json: String,
    #[serde(rename = "correlationId")]
    #[serde(default)]
    pub correlation_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogItem {
    pub id: String,
    #[serde(rename = "runId")]
    #[serde(default)]
    pub run_id: Option<String>,
    pub ts: String,
    pub level: LogLevel,
    pub source: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArtifactItem {
    pub id: String,
    pub name: String,
    pub kind: ArtifactKind,
    #[serde(rename = "runId")]
    #[serde(default)]
    pub run_id: Option<String>,
    #[serde(rename = "filePath")]
    pub file_path: String,
    #[serde(rename = "sizeKb")]
    pub size_kb: i32,
    #[serde(rename = "createdAt")]
    pub created_at: String,
    #[serde(rename = "correlationId")]
    #[serde(default)]
    pub correlation_id: Option<String>,
    #[serde(rename = "sha256")]
    #[serde(default)]
    pub sha256: Option<String>,
    #[serde(default)]
    pub provenance: Option<String>,
    #[serde(rename = "mutationProvenance")]
    #[serde(default)]
    pub mutation_provenance: Option<MutationProvenance>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApprovalMeta {
    #[serde(rename = "fileCount")]
    pub file_count: i32,
    pub additions: i32,
    pub deletions: i32,
    pub risk: RiskLevel,
    #[serde(rename = "repoName")]
    pub repo_name: String,
    pub branch: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunSessionResult {
    #[serde(rename = "runId")]
    pub run_id: String,
    #[serde(rename = "turnId")]
    pub turn_id: String,
    pub status: RunStatus,
    #[serde(rename = "assistantMessage")]
    pub assistant_message: String,
    pub timeline: Vec<TimelineStep>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatTurn {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RepoTreeEntry {
    pub path: String,
    #[serde(rename = "displayName")]
    pub display_name: String,
    #[serde(rename = "isDir")]
    pub is_dir: bool,
    pub size: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RepoFileContent {
    pub path: String,
    pub content: String,
    pub truncated: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelConfig {
    pub provider: Provider,
    pub model: String,
    #[serde(rename = "baseUrl")]
    pub base_url: String,
    #[serde(rename = "apiKey")]
    pub api_key: String,
    #[serde(default, rename = "timeoutSec")]
    pub timeout_sec: Option<u64>,
    #[serde(default, rename = "contextTokenLimit")]
    pub context_token_limit: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuleEntry {
    pub content: String,
    #[serde(rename = "updatedAt")]
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppSettings {
    #[serde(rename = "notificationsEnabled")]
    pub notifications_enabled: bool,
    #[serde(rename = "defaultSessionMode")]
    pub default_session_mode: String,
    #[serde(rename = "defaultTheme")]
    pub default_theme: String,
    #[serde(default, rename = "outputStyle")]
    pub output_style: Option<String>,
    pub model: ModelConfig,
    #[serde(rename = "rulesByRepo")]
    pub rules_by_repo: HashMap<String, RuleEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityPolicies {
    #[serde(rename = "policiesByRepo")]
    pub policies_by_repo: HashMap<String, HashMap<String, String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginItem {
    pub id: String,
    pub name: String,
    #[serde(rename = "sourcePath")]
    pub source_path: String,
    pub enabled: bool,
    #[serde(rename = "importedAt")]
    pub imported_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PythonTodoStats {
    pub total: i64,
    pub pending: i64,
    pub in_progress: i64,
    pub completed: i64,
    #[serde(default, rename = "contextTokens")]
    pub context_tokens: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PythonTodoItem {
    pub step_id: String,
    pub title: String,
    pub status: String,
    #[serde(default)]
    pub active_form: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PythonTodoState {
    pub updated_at: String,
    pub stats: PythonTodoStats,
    pub items: Vec<PythonTodoItem>,
    #[serde(default)]
    pub rendered: Option<String>,
    #[serde(default)]
    pub run_id: Option<String>,
    #[serde(default)]
    pub turn_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppData {
    pub repos: Vec<RepoItem>,
    pub sessions: Vec<SessionItem>,
    #[serde(rename = "sessionRuns")]
    #[serde(default)]
    pub session_runs: HashMap<String, Vec<SessionRun>>,
    #[serde(rename = "sessionEvents")]
    #[serde(default)]
    pub session_events: HashMap<String, Vec<SessionEvent>>,
    #[serde(rename = "sessionTurns")]
    #[serde(default)]
    pub session_turns: HashMap<String, Vec<SessionTurn>>,
    pub timelines: HashMap<String, Vec<TimelineStep>>,
    pub diffs: HashMap<String, Vec<DiffFile>>,
    pub tools: HashMap<String, Vec<ToolCallItem>>,
    pub logs: HashMap<String, Vec<LogItem>>,
    pub artifacts: HashMap<String, Vec<ArtifactItem>>,
    #[serde(rename = "pythonTodos")]
    #[serde(default)]
    pub python_todos: HashMap<String, PythonTodoState>,
    #[serde(rename = "chatHistory")]
    pub chat_history: HashMap<String, Vec<ChatTurn>>,
    #[serde(rename = "chatSummary")]
    pub chat_summary: HashMap<String, String>,
    pub memories: HashMap<String, Vec<MemoryBlock>>,
    #[serde(rename = "pendingApprovals")]
    pub pending_approvals: HashMap<String, Vec<ApprovalRequest>>,
    #[serde(rename = "sessionPermissions")]
    #[serde(default)]
    pub session_permissions: Vec<SessionPermission>,
    pub settings: AppSettings,
    pub security: SecurityPolicies,
    pub plugins: Vec<PluginItem>,
}

impl AppData {
    pub fn refresh_timeline_projection(&mut self) {
        let mut session_ids = self
            .session_events
            .iter()
            .filter(|(_, events)| !events.is_empty())
            .map(|(session_id, _)| session_id.clone())
            .collect::<Vec<_>>();
        session_ids.extend(
            self.session_turns
                .iter()
                .filter(|(_, turns)| !turns.is_empty())
                .map(|(session_id, _)| session_id.clone()),
        );
        session_ids.sort();
        session_ids.dedup();
        for session_id in session_ids {
            let timeline = self.timeline_for_session(&session_id);
            self.timelines.insert(session_id.clone(), timeline);
        }
    }

    pub fn timeline_for_session(&self, session_id: &str) -> Vec<TimelineStep> {
        if let Some(turns) = self
            .session_turns
            .get(session_id)
            .filter(|turns| !turns.is_empty())
        {
            let projected = project_timeline_from_turns(turns);
            if !projected.is_empty() {
                return projected;
            }
        }
        self.session_events
            .get(session_id)
            .filter(|events| !events.is_empty())
            .map(|events| project_timeline_from_events(events))
            .unwrap_or_else(|| self.timelines.get(session_id).cloned().unwrap_or_default())
    }

    pub fn runs_for_session(&self, session_id: &str) -> Vec<SessionRun> {
        self.session_runs
            .get(session_id)
            .cloned()
            .unwrap_or_default()
    }

    pub fn turns_for_session(&self, session_id: &str) -> Vec<SessionTurn> {
        self.session_turns
            .get(session_id)
            .cloned()
            .unwrap_or_default()
    }
}

impl Default for AppData {
    fn default() -> Self {
        let repos = vec![
            RepoItem {
                id: "r1".into(),
                name: "codinggirl".into(),
                path: "E:/coding agent".into(),
                pinned: true,
            },
            RepoItem {
                id: "r2".into(),
                name: "demo-repo".into(),
                path: "D:/demo-repo".into(),
                pinned: false,
            },
        ];

        let sessions = vec![
            SessionItem {
                id: "s1".into(),
                repo_id: "r1".into(),
                title: "修复登录验证错误".into(),
                mode: "build".into(),
                created_at: "2026-03-07T10:00:00+08:00".into(),
                updated_at: "2026-03-07T13:40:00+08:00".into(),
            },
            SessionItem {
                id: "s2".into(),
                repo_id: "r1".into(),
                title: "重构索引模块".into(),
                mode: "plan".into(),
                created_at: "2026-03-07T09:00:00+08:00".into(),
                updated_at: "2026-03-07T13:20:00+08:00".into(),
            },
        ];

        let sample_runs_s1 = vec![SessionRun {
            id: "run-demo-1".into(),
            session_id: "s1".into(),
            turn_id: "turn-demo-1".into(),
            mode: "build".into(),
            user_text: "修复登录验证错误".into(),
            assistant_message: Some("已完成一次示例运行。".into()),
            error_text: None,
            status: RunStatus::Success,
            created_at: "2026-03-07T10:05:00+08:00".into(),
            updated_at: "2026-03-07T10:05:08+08:00".into(),
            completed_at: Some("2026-03-07T10:05:08+08:00".into()),
        }];

        let mut session_runs = HashMap::new();
        session_runs.insert("s1".into(), sample_runs_s1);

        let sample_events_s1 = vec![
            SessionEvent {
                event_id: "evt-s1-1".into(),
                session_id: "s1".into(),
                turn_id: Some("turn-demo-1".into()),
                run_id: Some("run-demo-1".into()),
                correlation_id: None,
                agent_id: Some("agent_main".into()),
                parent_agent_id: None,
                kind: "turn.started".into(),
                title: "分析仓库上下文".into(),
                status: TimelineStatus::Success,
                detail: Some("索引 24 个文件".into()),
                trace_type: Some("session".into()),
                item_id: None,
                item_type: None,
                ts: "2026-03-07T10:05:00+08:00".into(),
                seq: 1,
            },
            SessionEvent {
                event_id: "evt-s1-2".into(),
                session_id: "s1".into(),
                turn_id: Some("turn-demo-1".into()),
                run_id: Some("run-demo-1".into()),
                correlation_id: Some("corr-demo-patch".into()),
                agent_id: Some("agent_main".into()),
                parent_agent_id: None,
                kind: "item.started".into(),
                title: "生成补丁".into(),
                status: TimelineStatus::Running,
                detail: Some("正在生成 unified diff".into()),
                trace_type: Some("artifact".into()),
                item_id: Some("item-demo-patch".into()),
                item_type: Some("patch".into()),
                ts: "2026-03-07T10:05:03+08:00".into(),
                seq: 2,
            },
        ];

        let mut session_events = HashMap::new();
        session_events.insert("s1".into(), sample_events_s1.clone());

        let mut session_turns = HashMap::new();
        session_turns.insert(
            "s1".into(),
            vec![SessionTurn {
                id: "turn-demo-1".into(),
                session_id: "s1".into(),
                run_id: Some("run-demo-1".into()),
                mode: "build".into(),
                route: Some("tool_execution".into()),
                route_source: Some("heuristic".into()),
                route_reason: Some("workspace_bound_task".into()),
                route_signals: vec!["task_request[chat+0,read+2,tool+4]".into()],
                user_text: Some("修复登录验证错误".into()),
                status: RunStatus::Success,
                items: vec![
                    SessionTurnItem {
                        id: "turn-demo-1-user".into(),
                        turn_id: "turn-demo-1".into(),
                        run_id: Some("run-demo-1".into()),
                        kind: SessionTurnItemKind::UserMessage,
                        status: TimelineStatus::Success,
                        title: "用户任务".into(),
                        summary: Some("修复登录验证错误".into()),
                        detail: Some("修复登录验证错误".into()),
                        tool_name: None,
                        path: None,
                        correlation_id: None,
                        data_json: None,
                        error_category: None,
                        error_code: None,
                        retryable: None,
                        retry_hint: None,
                        fallback_hint: None,
                        created_at: "2026-03-07T10:05:00+08:00".into(),
                        updated_at: "2026-03-07T10:05:00+08:00".into(),
                    },
                    SessionTurnItem {
                        id: "tc1".into(),
                        turn_id: "turn-demo-1".into(),
                        run_id: Some("run-demo-1".into()),
                        kind: SessionTurnItemKind::ToolCall,
                        status: TimelineStatus::Success,
                        title: "搜索仓库".into(),
                        summary: Some("找到 4 条匹配".into()),
                        detail: Some("{\"pattern\":\"login\"}".into()),
                        tool_name: Some("search_rg".into()),
                        path: None,
                        correlation_id: None,
                        data_json: Some("{\"results\":4}".into()),
                        error_category: None,
                        error_code: None,
                        retryable: None,
                        retry_hint: None,
                        fallback_hint: None,
                        created_at: "2026-03-07T10:05:01+08:00".into(),
                        updated_at: "2026-03-07T10:05:02+08:00".into(),
                    },
                    SessionTurnItem {
                        id: "d1".into(),
                        turn_id: "turn-demo-1".into(),
                        run_id: Some("run-demo-1".into()),
                        kind: SessionTurnItemKind::Diff,
                        status: TimelineStatus::Success,
                        title: "codinggirl/core/orchestrator.py".into(),
                        summary: Some("+14 / -5".into()),
                        detail: Some("@@ -1,1 +1,1 @@".into()),
                        tool_name: None,
                        path: Some("codinggirl/core/orchestrator.py".into()),
                        correlation_id: None,
                        data_json: None,
                        error_category: None,
                        error_code: None,
                        retryable: None,
                        retry_hint: None,
                        fallback_hint: None,
                        created_at: "2026-03-07T10:05:03+08:00".into(),
                        updated_at: "2026-03-07T10:05:03+08:00".into(),
                    },
                    SessionTurnItem {
                        id: "turn-demo-1-assistant".into(),
                        turn_id: "turn-demo-1".into(),
                        run_id: Some("run-demo-1".into()),
                        kind: SessionTurnItemKind::AssistantMessage,
                        status: TimelineStatus::Success,
                        title: "助手回复".into(),
                        summary: Some("已完成一次示例运行。".into()),
                        detail: Some("已完成一次示例运行。".into()),
                        tool_name: None,
                        path: None,
                        correlation_id: None,
                        data_json: None,
                        error_category: None,
                        error_code: None,
                        retryable: None,
                        retry_hint: None,
                        fallback_hint: None,
                        created_at: "2026-03-07T10:05:08+08:00".into(),
                        updated_at: "2026-03-07T10:05:08+08:00".into(),
                    },
                ],
                created_at: "2026-03-07T10:05:00+08:00".into(),
                updated_at: "2026-03-07T10:05:08+08:00".into(),
                completed_at: Some("2026-03-07T10:05:08+08:00".into()),
            }],
        );

        let mut timelines = HashMap::new();
        timelines.insert("s1".into(), project_timeline_from_events(&sample_events_s1));

        let mut diffs = HashMap::new();
        diffs.insert(
            "s1".into(),
            vec![DiffFile {
                id: "d1".into(),
                path: "codinggirl/core/orchestrator.py".into(),
                run_id: Some("run-demo-1".into()),
                additions: 14,
                deletions: 5,
                old_snippet: "- state.transition(\"PATCHED\")".into(),
                new_snippet: "+ state.transition(\"PATCHED\")".into(),
                unified_snippet: "@@ -1,1 +1,1 @@".into(),
                diff: "@@ -1,1 +1,1 @@".into(),
                mutation_provenance: None,
            }],
        );

        let mut tools = HashMap::new();
        tools.insert(
            "s1".into(),
            vec![ToolCallItem {
                id: "tc1".into(),
                name: "search_rg".into(),
                run_id: Some("run-demo-1".into()),
                status: ToolStatus::Success,
                duration_ms: 82,
                args_json: "{\"pattern\":\"login\"}".into(),
                result_json: "{\"results\":4}".into(),
                correlation_id: None,
            }],
        );

        let mut logs = HashMap::new();
        logs.insert(
            "s1".into(),
            vec![LogItem {
                id: "l1".into(),
                run_id: Some("run-demo-1".into()),
                ts: "2026-03-07 14:10:11".into(),
                level: LogLevel::Info,
                source: "orchestrator".into(),
                message: "Run created and plan generated.".into(),
            }],
        );

        let mut artifacts = HashMap::new();
        artifacts.insert(
            "s1".into(),
            vec![ArtifactItem {
                id: "a1".into(),
                name: "patchset-20260307.diff".into(),
                kind: ArtifactKind::Patch,
                run_id: Some("run-demo-1".into()),
                file_path: "E:/coding agent/.codinggirl/artifacts/patchset-20260307.diff".into(),
                size_kb: 12,
                created_at: "2026-03-07 14:10:15".into(),
                correlation_id: None,
                sha256: None,
                provenance: None,
                mutation_provenance: None,
            }],
        );

        Self {
            repos,
            sessions,
            session_runs,
            session_events,
            session_turns,
            timelines,
            diffs,
            tools,
            logs,
            artifacts,
            python_todos: HashMap::new(),
            chat_history: HashMap::new(),
            chat_summary: HashMap::new(),
            memories: HashMap::new(),
            pending_approvals: HashMap::new(),
            session_permissions: vec![],
            settings: AppSettings {
                notifications_enabled: true,
                default_session_mode: "build".into(),
                default_theme: "dark".into(),
                output_style: Some("default".into()),
                model: ModelConfig {
                    provider: Provider::Mock,
                    model: "mock-1".into(),
                    base_url: "".into(),
                    api_key: "".into(),
                    timeout_sec: Some(180),
                    context_token_limit: None,
                },
                rules_by_repo: HashMap::new(),
            },
            security: SecurityPolicies {
                policies_by_repo: HashMap::new(),
            },
            plugins: vec![],
        }
    }
}

pub struct AppState {
    pub data: Mutex<AppData>,
    pub data_file: PathBuf,
}

impl AppState {
    pub fn load(data_file: PathBuf) -> Self {
        let mut data = fs::read_to_string(&data_file)
            .ok()
            .and_then(|raw| serde_json::from_str::<AppData>(&raw).ok())
            .unwrap_or_default();
        data.refresh_timeline_projection();
        Self {
            data: Mutex::new(data),
            data_file,
        }
    }

    pub fn save_locked(&self, data: &AppData) -> Result<(), String> {
        if let Some(parent) = self.data_file.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let raw = serde_json::to_string_pretty(data).map_err(|e| e.to_string())?;
        fs::write(&self.data_file, raw)
            .map_err(|e| format!("save state failed: {} ({})", self.data_file.display(), e))
    }
}

#[cfg(test)]
#[path = "state_tests.rs"]
mod state_tests;
