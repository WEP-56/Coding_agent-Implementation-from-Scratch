use crate::state::{AppData, AppSettings, Provider, RunStatus};
use reqwest::header::{AUTHORIZATION, CONTENT_TYPE};
use serde::{Deserialize, Serialize};
use serde_json::json;

const INTENT_ROUTER_TIMEOUT_SECS: u64 = 8;

const CASUAL_PHRASES: &[&str] = &[
    "hello",
    "hi",
    "hey",
    "thanks",
    "thank you",
    "你好",
    "谢谢",
    "在吗",
    "聊聊",
    "早上好",
    "晚上好",
];

const CONVERSATION_TERMS: &[&str] = &[
    "remember",
    "memory",
    "context",
    "summary",
    "conversation",
    "记忆",
    "上下文",
    "总结",
    "摘要",
    "对话",
];

const REPO_NOUNS: &[&str] = &[
    "repo",
    "repository",
    "project",
    "workspace",
    "code",
    "file",
    "folder",
    "directory",
    "function",
    "class",
    "component",
    "module",
    "test",
    "build",
    "diff",
    "patch",
    "bug",
    "error",
    "stack",
    "trace",
    "session",
    "仓库",
    "项目",
    "代码",
    "文件",
    "目录",
    "函数",
    "类",
    "组件",
    "模块",
    "测试",
    "构建",
    "补丁",
    "报错",
    "错误",
    "前端",
    "后端",
    "页面",
    "样式",
    "界面",
    "软件",
    "应用",
    "程序",
    "计算器",
    "ui",
    "ux",
    "screen",
    "page",
    "style",
    "frontend",
    "backend",
    "app",
    "calculator",
    "desktop",
];

const READ_ONLY_VERBS: &[&str] = &[
    "read",
    "inspect",
    "explain",
    "understand",
    "search",
    "find",
    "show",
    "list",
    "trace",
    "analyze",
    "diagnose",
    "review",
    "browse",
    "locate",
    "check",
    "看看",
    "分析",
    "阅读",
    "解释",
    "搜索",
    "查找",
    "定位",
    "检查",
    "排查",
    "浏览",
];

const MUTATION_VERBS: &[&str] = &[
    "fix",
    "change",
    "update",
    "modify",
    "edit",
    "write",
    "implement",
    "create",
    "add",
    "remove",
    "delete",
    "rename",
    "refactor",
    "patch",
    "apply",
    "run",
    "execute",
    "install",
    "upgrade",
    "build",
    "compile",
    "test",
    "beautify",
    "polish",
    "improve",
    "support",
    "style",
    "修复",
    "修改",
    "更新",
    "编辑",
    "实现",
    "创建",
    "新增",
    "增加",
    "添加",
    "删除",
    "重命名",
    "重构",
    "运行",
    "执行",
    "安装",
    "升级",
    "构建",
    "编译",
    "测试",
    "美化",
    "优化",
    "改进",
    "完善",
    "支持",
    "调整",
    "补上",
];

const TASK_REQUEST_TERMS: &[&str] = &[
    "please",
    "can you",
    "could you",
    "help me",
    "need you to",
    "for my",
    "for this",
    "帮我",
    "麻烦",
    "请",
    "希望你",
    "给我",
    "为我",
    "这个",
    "我的",
    "顺便",
];

const RETRY_PHRASES: &[&str] = &[
    "retry",
    "rerun",
    "re-run",
    "try again",
    "重试",
    "再试",
    "重新运行",
    "重新执行",
    "再跑一次",
];

const PREVIOUS_REFERENCES: &[&str] = &[
    "last",
    "previous",
    "above",
    "before",
    "earlier",
    "that",
    "上一轮",
    "上次",
    "刚才",
    "刚刚",
    "前面",
    "那个",
];

const SOURCE_EXTENSIONS: &[&str] = &[
    ".rs", ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".java", ".json", ".toml", ".md", ".yaml",
    ".yml",
];

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub(crate) enum SessionIntentRoute {
    ChatOnly,
    RepoReadOnly,
    ToolExecution,
}

impl SessionIntentRoute {
    pub(crate) fn as_str(&self) -> &'static str {
        match self {
            Self::ChatOnly => "chat_only",
            Self::RepoReadOnly => "repo_read_only",
            Self::ToolExecution => "tool_execution",
        }
    }

    pub(crate) fn allows_mutation(&self) -> bool {
        matches!(self, Self::ToolExecution)
    }
}

#[derive(Debug, Clone, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct IntentScoreCard {
    pub chat_only: i32,
    pub repo_read_only: i32,
    pub tool_execution: i32,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub(crate) enum IntentDecisionSource {
    Heuristic,
    Model,
    ModelFallback,
}

impl IntentDecisionSource {
    pub(crate) fn as_str(&self) -> &'static str {
        match self {
            Self::Heuristic => "heuristic",
            Self::Model => "model",
            Self::ModelFallback => "model_fallback",
        }
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct IntentDecision {
    pub route: SessionIntentRoute,
    pub retry_text: Option<String>,
    pub scores: IntentScoreCard,
    pub signals: Vec<String>,
    pub source: IntentDecisionSource,
    pub reasoning: Option<String>,
}

impl IntentDecision {
    pub(crate) fn trace_detail(&self) -> String {
        format!(
            "source={} route={} chat={} read={} tool={} signals={}{}",
            self.source.as_str(),
            self.route.as_str(),
            self.scores.chat_only,
            self.scores.repo_read_only,
            self.scores.tool_execution,
            if self.signals.is_empty() {
                "none".to_string()
            } else {
                self.signals.join(", ")
            },
            self.reasoning
                .as_ref()
                .map(|reason| format!(" reason={}", reason))
                .unwrap_or_default()
        )
    }
}

#[derive(Debug, Clone)]
pub(crate) struct IntentRouterContext {
    pub repo_name: Option<String>,
    pub session_title: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ModelIntentResponse {
    route: String,
    #[serde(default)]
    reason: Option<String>,
}

fn contains_any(text: &str, terms: &[&str]) -> bool {
    terms.iter().any(|term| text.contains(term))
}

fn contains_file_reference(raw: &str, lower: &str) -> bool {
    raw.contains('`')
        || lower.contains('/')
        || lower.contains('\\')
        || SOURCE_EXTENSIONS.iter().any(|ext| lower.contains(ext))
}

fn is_retry_request(lower: &str) -> bool {
    let trimmed = lower.trim();
    RETRY_PHRASES
        .iter()
        .any(|item| trimmed == *item || trimmed.starts_with(&format!("{item} ")))
}

fn apply_signal(
    scores: &mut IntentScoreCard,
    signals: &mut Vec<String>,
    label: &str,
    chat_delta: i32,
    read_delta: i32,
    tool_delta: i32,
) {
    scores.chat_only += chat_delta;
    scores.repo_read_only += read_delta;
    scores.tool_execution += tool_delta;
    signals.push(format!(
        "{label}[chat{chat_delta:+},read{read_delta:+},tool{tool_delta:+}]"
    ));
}

fn choose_route(
    scores: &IntentScoreCard,
    has_repo_signal: bool,
    strong_tool_signal: bool,
) -> SessionIntentRoute {
    if strong_tool_signal && scores.tool_execution >= scores.repo_read_only {
        return SessionIntentRoute::ToolExecution;
    }
    if !has_repo_signal
        && scores.chat_only >= scores.repo_read_only
        && scores.chat_only >= scores.tool_execution
    {
        return SessionIntentRoute::ChatOnly;
    }
    if scores.tool_execution >= scores.repo_read_only + 2
        && scores.tool_execution >= scores.chat_only
    {
        return SessionIntentRoute::ToolExecution;
    }
    if scores.repo_read_only > 0 && scores.repo_read_only >= scores.chat_only {
        return SessionIntentRoute::RepoReadOnly;
    }
    if has_repo_signal {
        return SessionIntentRoute::RepoReadOnly;
    }
    SessionIntentRoute::ChatOnly
}

fn is_pure_small_talk(trimmed: &str, lower: &str, has_task_request: bool) -> bool {
    if has_task_request {
        return false;
    }
    let short_form = trimmed.chars().count() <= 16;
    short_form && contains_any(lower, CASUAL_PHRASES)
}

fn extract_first_json_object(raw: &str) -> Option<&str> {
    let start = raw.find('{')?;
    let end = raw.rfind('}')?;
    (end > start).then_some(&raw[start..=end])
}

fn has_complete_openai_router_config(settings: &AppSettings) -> bool {
    settings.model.provider == Provider::OpenaiCompatible
        && !settings.model.base_url.trim().is_empty()
        && !settings.model.api_key.trim().is_empty()
        && !settings.model.model.trim().is_empty()
}

fn should_use_model_router(text: &str, decision: &IntentDecision) -> bool {
    let top = decision
        .scores
        .chat_only
        .max(decision.scores.repo_read_only)
        .max(decision.scores.tool_execution);
    let mut ordered = [
        decision.scores.chat_only,
        decision.scores.repo_read_only,
        decision.scores.tool_execution,
    ];
    ordered.sort_unstable();
    let margin = ordered[2] - ordered[1];
    let lower = text.to_lowercase();
    let has_task_request = contains_any(&lower, TASK_REQUEST_TERMS);
    let has_mutation_verb = contains_any(&lower, MUTATION_VERBS);
    let has_repo_noun = contains_any(&lower, REPO_NOUNS);

    margin <= 2
        || (decision.route == SessionIntentRoute::ChatOnly && (has_task_request || has_repo_noun))
        || (decision.route == SessionIntentRoute::RepoReadOnly && has_mutation_verb)
        || (top <= 6 && (has_task_request || has_mutation_verb))
}

async fn classify_with_model(
    settings: &AppSettings,
    context: &IntentRouterContext,
    text: &str,
) -> Result<ModelIntentResponse, String> {
    let root = settings.model.base_url.trim_end_matches('/');
    let endpoint = if root.ends_with("/v1") {
        format!("{}/chat/completions", root)
    } else {
        format!("{}/v1/chat/completions", root)
    };

    let repo_name = context.repo_name.as_deref().unwrap_or("unknown");
    let session_title = context.session_title.as_deref().unwrap_or("untitled");
    let payload = json!({
        "model": settings.model.model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": "You are an intent router for a desktop coding agent attached to a repository workspace.\nChoose exactly one route and return JSON only with no markdown fences.\nRoutes:\n- chat_only: casual conversation, clarification about general topics, no repository inspection or mutation.\n- repo_read_only: inspect the repository, explain code, analyze files, answer project questions, but do not modify files.\n- tool_execution: implement features, beautify UI, fix bugs, change files, run tests/builds, or anything that should produce a workflow run with tool usage.\nReturn: {\"route\":\"chat_only|repo_read_only|tool_execution\",\"reason\":\"short reason\"}"
            },
            {
                "role": "user",
                "content": format!("Session title: {}\nRepo: {}\nUser message: {}", session_title, repo_name, text)
            }
        ]
    });

    let client = reqwest::Client::builder()
        .connect_timeout(std::time::Duration::from_secs(3))
        .timeout(std::time::Duration::from_secs(INTENT_ROUTER_TIMEOUT_SECS))
        .build()
        .map_err(|e| format!("intent router client init failed: {}", e))?;

    let response = client
        .post(endpoint)
        .header(CONTENT_TYPE, "application/json")
        .header(AUTHORIZATION, format!("Bearer {}", settings.model.api_key))
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("intent router request failed: {}", e))?;

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(format!(
            "intent router response not ok: {} {}",
            status, body
        ));
    }

    let value: serde_json::Value = response
        .json()
        .await
        .map_err(|e| format!("invalid intent router response: {}", e))?;
    let content = value
        .get("choices")
        .and_then(|choices| choices.as_array())
        .and_then(|choices| choices.first())
        .and_then(|choice| choice.get("message"))
        .and_then(|message| message.get("content"))
        .and_then(|content| content.as_str())
        .ok_or_else(|| "intent router returned empty content".to_string())?;
    let json_str = extract_first_json_object(content)
        .ok_or_else(|| "intent router did not return JSON object".to_string())?;
    serde_json::from_str::<ModelIntentResponse>(json_str)
        .map_err(|e| format!("invalid intent router JSON: {}", e))
}

pub(crate) fn classify_session_intent(
    data: &AppData,
    session_id: &str,
    text: &str,
) -> IntentDecision {
    let trimmed = text.trim();
    let lower = trimmed.to_lowercase();
    let short_form = trimmed.chars().count() <= 28;
    let question_like = trimmed.contains('?') || trimmed.contains('？');
    let multiline = trimmed.contains('\n');
    let session_is_repo_bound = data.sessions.iter().any(|session| session.id == session_id);
    let has_casual_phrase = contains_any(&lower, CASUAL_PHRASES);
    let has_conversation_focus = contains_any(&lower, CONVERSATION_TERMS);
    let has_repo_noun = contains_any(&lower, REPO_NOUNS);
    let has_read_only_verb = contains_any(&lower, READ_ONLY_VERBS);
    let has_mutation_verb = contains_any(&lower, MUTATION_VERBS);
    let has_task_request = contains_any(&lower, TASK_REQUEST_TERMS);
    let has_path = contains_file_reference(trimmed, &lower);
    let references_previous_turn = contains_any(&lower, PREVIOUS_REFERENCES);
    let retry_requested = is_retry_request(&lower);
    let runs = data.runs_for_session(session_id);
    let last_failed = runs.iter().find(|run| run.status == RunStatus::Failed);
    let pure_small_talk = is_pure_small_talk(trimmed, &lower, has_task_request || has_repo_noun);
    let has_repo_signal = has_repo_noun
        || has_read_only_verb
        || has_mutation_verb
        || has_task_request
        || has_path
        || multiline;

    let mut scores = IntentScoreCard::default();
    let mut signals = Vec::new();
    let mut retry_text = None;

    if has_casual_phrase && !has_repo_signal && !has_mutation_verb {
        apply_signal(&mut scores, &mut signals, "casual_phrase", 4, 0, 0);
    }
    if has_conversation_focus && !has_repo_signal {
        apply_signal(&mut scores, &mut signals, "conversation_focus", 4, 0, 0);
    }
    if short_form && !has_repo_signal && !retry_requested && !has_task_request {
        apply_signal(&mut scores, &mut signals, "short_form", 2, 0, 0);
    }
    if !has_repo_signal && question_like {
        apply_signal(&mut scores, &mut signals, "general_question", 1, 0, 0);
    }
    if has_path {
        apply_signal(&mut scores, &mut signals, "file_reference", 0, 4, 3);
    }
    if has_repo_noun {
        apply_signal(&mut scores, &mut signals, "repo_noun", 0, 3, 2);
    }
    if has_read_only_verb {
        apply_signal(&mut scores, &mut signals, "inspection_verb", 0, 4, 1);
    }
    if has_mutation_verb {
        apply_signal(&mut scores, &mut signals, "mutation_verb", 0, 1, 6);
    }
    if has_task_request {
        apply_signal(&mut scores, &mut signals, "task_request", 0, 2, 4);
    }
    if session_is_repo_bound && has_task_request && !pure_small_talk {
        apply_signal(&mut scores, &mut signals, "workspace_bound_task", 0, 2, 3);
    }
    if question_like && has_repo_signal && !has_mutation_verb {
        apply_signal(&mut scores, &mut signals, "repo_question", 0, 2, 0);
    }
    if multiline && has_repo_signal {
        apply_signal(&mut scores, &mut signals, "multi_line_task", 0, 2, 3);
    }

    if retry_requested {
        if let Some(run) = last_failed {
            retry_text = Some(run.user_text.clone());
            apply_signal(&mut scores, &mut signals, "retry_last_failed", 0, 0, 8);
        } else {
            apply_signal(&mut scores, &mut signals, "retry_request", 0, 1, 5);
        }
    }

    if references_previous_turn {
        if has_repo_signal || retry_text.is_some() {
            apply_signal(
                &mut scores,
                &mut signals,
                "previous_turn_reference",
                0,
                2,
                2,
            );
        } else if !runs.is_empty() {
            apply_signal(&mut scores, &mut signals, "previous_turn_chat", 2, 0, 0);
        }
    }

    if !has_repo_signal && !retry_requested {
        apply_signal(&mut scores, &mut signals, "no_repo_signal", 2, 0, 0);
    }
    if pure_small_talk {
        apply_signal(&mut scores, &mut signals, "pure_small_talk", 2, 0, 0);
    }

    let strong_tool_signal = has_mutation_verb || retry_text.is_some();
    let route = choose_route(&scores, has_repo_signal, strong_tool_signal);

    IntentDecision {
        route,
        retry_text,
        scores,
        signals,
        source: IntentDecisionSource::Heuristic,
        reasoning: None,
    }
}

pub(crate) async fn resolve_session_intent(
    data: &AppData,
    session_id: &str,
    text: &str,
) -> IntentDecision {
    let heuristic = classify_session_intent(data, session_id, text);
    if !has_complete_openai_router_config(&data.settings)
        || !should_use_model_router(text, &heuristic)
    {
        return heuristic;
    }

    let context = IntentRouterContext {
        repo_name: data
            .sessions
            .iter()
            .find(|session| session.id == session_id)
            .and_then(|session| data.repos.iter().find(|repo| repo.id == session.repo_id))
            .map(|repo| repo.name.clone()),
        session_title: data
            .sessions
            .iter()
            .find(|session| session.id == session_id)
            .map(|session| session.title.clone()),
    };

    match classify_with_model(&data.settings, &context, text).await {
        Ok(model) => {
            let route = match model.route.trim() {
                "chat_only" => SessionIntentRoute::ChatOnly,
                "repo_read_only" => SessionIntentRoute::RepoReadOnly,
                "tool_execution" => SessionIntentRoute::ToolExecution,
                _ => {
                    let mut fallback = heuristic;
                    fallback.source = IntentDecisionSource::ModelFallback;
                    fallback.reasoning = Some("model returned invalid route".into());
                    return fallback;
                }
            };
            IntentDecision {
                route,
                retry_text: heuristic.retry_text.clone(),
                scores: heuristic.scores,
                signals: heuristic.signals,
                source: IntentDecisionSource::Model,
                reasoning: model.reason,
            }
        }
        Err(error) => {
            let mut fallback = heuristic;
            fallback.source = IntentDecisionSource::ModelFallback;
            fallback.reasoning = Some(error);
            fallback
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::{AppData, RunStatus, SessionRun};

    fn data_with_failed_run() -> AppData {
        let mut data = AppData::default();
        data.session_runs.insert(
            "s-test".into(),
            vec![SessionRun {
                id: "run-1".into(),
                session_id: "s-test".into(),
                turn_id: "turn-1".into(),
                mode: "build".into(),
                user_text: "fix src/main.rs".into(),
                assistant_message: None,
                error_text: Some("boom".into()),
                status: RunStatus::Failed,
                created_at: "2026-03-08T00:00:00Z".into(),
                updated_at: "2026-03-08T00:00:00Z".into(),
                completed_at: Some("2026-03-08T00:00:00Z".into()),
            }],
        );
        data
    }

    #[test]
    fn routes_greeting_to_chat_only() {
        let data = AppData::default();
        let decision = classify_session_intent(&data, "s1", "你好，今天怎么样？");
        assert_eq!(decision.route, SessionIntentRoute::ChatOnly);
    }

    #[test]
    fn routes_feature_request_to_tool_execution() {
        let data = AppData::default();
        let decision =
            classify_session_intent(&data, "s1", "你好，帮我美化一下这个python计算器软件的前端");
        assert_eq!(decision.route, SessionIntentRoute::ToolExecution);
    }

    #[test]
    fn routes_workspace_product_request_to_tool_execution() {
        let data = AppData::default();
        let decision = classify_session_intent(
            &data,
            "s1",
            "为我的这个计算器软件增加一个计算历史功能吧，顺便轻度美化一下前端",
        );
        assert_eq!(decision.route, SessionIntentRoute::ToolExecution);
    }

    #[test]
    fn routes_repo_question_to_read_only() {
        let data = AppData::default();
        let decision = classify_session_intent(
            &data,
            "s1",
            "Explain how context_manager.rs compacts history",
        );
        assert_eq!(decision.route, SessionIntentRoute::RepoReadOnly);
    }

    #[test]
    fn routes_fix_request_to_tool_execution() {
        let data = AppData::default();
        let decision = classify_session_intent(
            &data,
            "s1",
            "Fix the failing build in apps/desktop/src-tauri/src/commands/llm.rs",
        );
        assert_eq!(decision.route, SessionIntentRoute::ToolExecution);
    }

    #[test]
    fn retry_reuses_last_failed_task() {
        let data = data_with_failed_run();
        let decision = classify_session_intent(&data, "s-test", "retry");
        assert_eq!(decision.route, SessionIntentRoute::ToolExecution);
        assert_eq!(decision.retry_text.as_deref(), Some("fix src/main.rs"));
    }
}
