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
                };
            }
            if contains_any(&lower, &["rollback"]) {
                return RuntimeErrorInfo {
                    category: ErrorCategory::Rollback,
                    code: "rollback_failed",
                    retryable: false,
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
                };
            }
            RuntimeErrorInfo {
                category: ErrorCategory::Unknown,
                code: "unknown_failed",
                retryable: false,
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
    }

    #[test]
    fn classify_transport_error() {
        let info = classify_error(
            "model request timed out after 3 attempts: /v1/chat/completions",
            ErrorContext::SessionRun,
        );
        assert_eq!(info.category, ErrorCategory::Transport);
        assert!(info.retryable);
    }

    #[test]
    fn classify_command_error() {
        let info = classify_error("terminal task join failed: panic", ErrorContext::Command);
        assert_eq!(info.category, ErrorCategory::Command);
        assert_eq!(info.code, "command_runtime_failure");
        assert!(info.retryable);
    }
}
