use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCategory {
    Transport,
    Provider,
    Model,
    Routing,
    Tool,
    Approval,
    Validation,
    Rollback,
    Command,
    Unknown,
}

#[derive(Debug, Clone)]
pub(crate) struct RuntimeErrorInfo {
    pub category: ErrorCategory,
    pub code: &'static str,
    pub retryable: bool,
    pub retry_hint: Option<&'static str>,
    pub fallback_hint: Option<&'static str>,
    pub user_message: &'static str,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ErrorContext {
    SessionRun,
    Command,
    Approval,
    Rollback,
}

fn contains_any(haystack: &str, needles: &[&str]) -> bool {
    needles.iter().any(|needle| haystack.contains(needle))
}

pub(crate) fn classify_error(message: &str, context: ErrorContext) -> RuntimeErrorInfo {
    let lower = message.trim().to_ascii_lowercase();
    match context {
        ErrorContext::Command => RuntimeErrorInfo {
            category: ErrorCategory::Command,
            code: if contains_any(&lower, &["failed to start", "task join failed"]) {
                "command_runtime_failure"
            } else if contains_any(
                &lower,
                &["cannot change directory", "path escapes repository root"],
            ) {
                "command_cwd_invalid"
            } else {
                "command_failed"
            },
            retryable: contains_any(&lower, &["failed to start", "task join failed"]),
            retry_hint: Some("检查命令和工作目录后重试"),
            fallback_hint: Some("优先改用 repo tool 或更小的命令范围"),
            user_message: "命令执行失败，建议先检查命令和工作目录。",
        },
        ErrorContext::Approval => RuntimeErrorInfo {
            category: ErrorCategory::Approval,
            code: if contains_any(&lower, &["approval not found", "approval update failed"]) {
                "approval_state_invalid"
            } else if lower.contains("unsupported approval tool") {
                "approval_tool_unsupported"
            } else {
                "approval_failed"
            },
            retryable: false,
            retry_hint: None,
            fallback_hint: Some("调整变更范围或改用更简单的写入方式"),
            user_message: "审批执行失败，需要重新确认本次变更方式。",
        },
        ErrorContext::Rollback => RuntimeErrorInfo {
            category: ErrorCategory::Rollback,
            code: if contains_any(
                &lower,
                &["invalid rollback metadata", "rollback metadata missing"],
            ) {
                "rollback_metadata_invalid"
            } else if lower.contains("rollback remove failed") {
                "rollback_remove_failed"
            } else {
                "rollback_failed"
            },
            retryable: contains_any(
                &lower,
                &["read rollback metadata failed", "rollback remove failed"],
            ),
            retry_hint: Some("确认 rollback metadata 和文件状态后重试"),
            fallback_hint: Some("必要时手动恢复受影响文件"),
            user_message: "回滚失败，需要检查 rollback metadata 和文件状态。",
        },
        ErrorContext::SessionRun => {
            if contains_any(
                &lower,
                &[
                    "openai-compatible provider selected",
                    "model client init failed",
                    "base url / api key / model is incomplete",
                ],
            ) {
                return RuntimeErrorInfo {
                    category: ErrorCategory::Provider,
                    code: "provider_config_invalid",
                    retryable: false,
                    retry_hint: None,
                    fallback_hint: Some("修正 provider 配置，或切换到 mock / 更稳定的模型"),
                    user_message: "模型提供商配置无效，需要先修正配置。",
                };
            }
            if contains_any(
                &lower,
                &[
                    "intent router client init failed",
                    "intent router request failed",
                    "invalid intent router response",
                    "invalid intent router json",
                ],
            ) {
                return RuntimeErrorInfo {
                    category: ErrorCategory::Routing,
                    code: "routing_failed",
                    retryable: true,
                    retry_hint: Some("可以直接重试当前任务"),
                    fallback_hint: Some("必要时退回规则路由或显式指定任务类型"),
                    user_message: "路由判断失败，本轮可退回更保守的任务分派方式。",
                };
            }
            if contains_any(
                &lower,
                &[
                    "local model endpoint is unavailable",
                    "model request timed out",
                    "attempt 1 transport error",
                    "attempt 2 transport error",
                    "attempt 3 transport error",
                    "model request exhausted retries without a response",
                ],
            ) {
                return RuntimeErrorInfo {
                    category: ErrorCategory::Transport,
                    code: "transport_failed",
                    retryable: true,
                    retry_hint: Some("稍后重试，或降低并发后重试"),
                    fallback_hint: Some("必要时切换更稳定的 provider / endpoint"),
                    user_message: "模型请求出现网络或限流问题，建议稍后重试。",
                };
            }
            if contains_any(
                &lower,
                &[
                    "model response not ok",
                    "invalid model response",
                    "invalid chat completion response",
                    "model returned no choices",
                    "model returned empty content",
                ],
            ) {
                return RuntimeErrorInfo {
                    category: ErrorCategory::Model,
                    code: if contains_any(
                        &lower,
                        &["model returned no choices", "model returned empty content"],
                    ) {
                        "model_response_invalid"
                    } else {
                        "model_failed"
                    },
                    retryable: !contains_any(
                        &lower,
                        &["model returned no choices", "model returned empty content"],
                    ),
                    retry_hint: Some("重试当前任务，或收窄目标范围"),
                    fallback_hint: Some("切换更强模型，或把任务拆成更小步骤"),
                    user_message: "模型返回无效或不稳定结果，建议缩小范围或更换模型。",
                };
            }
            if contains_any(
                &lower,
                &[
                    "read-before-write guard",
                    "repeat guard blocked tool",
                    "patch touches sensitive path",
                    "path escapes repository root",
                    "sensitive file",
                ],
            ) {
                return RuntimeErrorInfo {
                    category: ErrorCategory::Validation,
                    code: "validation_failed",
                    retryable: false,
                    retry_hint: None,
                    fallback_hint: Some("先读仓库上下文，再执行修改"),
                    user_message: "本轮被安全或校验规则阻止，需要调整执行方式。",
                };
            }
            if contains_any(
                &lower,
                &["approval", "unsupported approval tool", "approval missing"],
            ) {
                return RuntimeErrorInfo {
                    category: ErrorCategory::Approval,
                    code: "approval_failed",
                    retryable: false,
                    retry_hint: None,
                    fallback_hint: Some("重新生成审批动作或缩小变更范围"),
                    user_message: "审批链路失败，需要重新生成或调整变更。",
                };
            }
            if contains_any(&lower, &["rollback"]) {
                return RuntimeErrorInfo {
                    category: ErrorCategory::Rollback,
                    code: "rollback_failed",
                    retryable: false,
                    retry_hint: Some("检查 rollback metadata 后重试"),
                    fallback_hint: Some("必要时手动恢复文件"),
                    user_message: "回滚链路失败，需要检查回滚元数据。",
                };
            }
            if contains_any(
                &lower,
                &[
                    "unknown tool",
                    "tool",
                    "patch apply is not allowed",
                    "read file failed",
                    "write file failed",
                    "invalid regex",
                ],
            ) {
                return RuntimeErrorInfo {
                    category: ErrorCategory::Tool,
                    code: "tool_failed",
                    retryable: false,
                    retry_hint: Some("缩小到具体文件或目录后重试"),
                    fallback_hint: Some("切换更强模型，或分解为更小的 repo 操作"),
                    user_message: "工具执行失败，建议缩小范围或分解任务。",
                };
            }
            RuntimeErrorInfo {
                category: ErrorCategory::Unknown,
                code: "unknown_failed",
                retryable: false,
                retry_hint: Some("可以重试一次确认是否为瞬时问题"),
                fallback_hint: Some("收窄任务范围并保留当前上下文"),
                user_message: "本轮出现未知错误，建议先重试或缩小范围。",
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn classify_provider_error() {
        let info = classify_error(
            "openai-compatible provider selected but Base URL / API Key / Model is incomplete",
            ErrorContext::SessionRun,
        );
        assert_eq!(info.category, ErrorCategory::Provider);
        assert_eq!(info.code, "provider_config_invalid");
        assert!(!info.retryable);
        assert!(info.fallback_hint.is_some());
    }

    #[test]
    fn classify_transport_error() {
        let info = classify_error(
            "model request timed out after 3 attempts: /v1/chat/completions",
            ErrorContext::SessionRun,
        );
        assert_eq!(info.category, ErrorCategory::Transport);
        assert!(info.retryable);
        assert!(info.retry_hint.is_some());
    }

    #[test]
    fn classify_command_error() {
        let info = classify_error("terminal task join failed: panic", ErrorContext::Command);
        assert_eq!(info.category, ErrorCategory::Command);
        assert_eq!(info.code, "command_runtime_failure");
        assert!(info.retryable);
        assert!(info.user_message.contains("命令执行失败"));
    }
}
