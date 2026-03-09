use crate::commands::memory::{memory_blocks_to_prompt, read_all_memory_blocks};
use crate::state::{ChatTurn, MemoryBlock};
use serde::Serialize;
use serde_json::json;

const MAX_VISIBLE_HISTORY: usize = 24;
const COMPACT_KEEP_RECENT: usize = 12;
const SUMMARY_MAX_CHARS: usize = 6000;
const FAILURE_PREVIEW_LIMIT: usize = 4;
const MEMORY_PREVIEW_CHARS: usize = 1200;
const TOOL_OUTPUT_PRUNE_CHARS: usize = 1200;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ContextBudgetStats {
    pub history_chars: usize,
    pub summary_chars: usize,
    pub memory_chars: usize,
    pub visible_turns: usize,
    pub max_visible_history: usize,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ContextTokenBreakdown {
    pub history_tokens: usize,
    pub summary_tokens: usize,
    pub memory_tokens: usize,
    pub pruned_tool_output_tokens: usize,
    pub total_tokens: usize,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HistoryNormalizationStats {
    pub total_turns: usize,
    pub kept_turns: usize,
    pub dropped_invalid_roles: usize,
    pub dropped_empty_turns: usize,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ContextCompactionStats {
    pub applied: bool,
    pub would_apply: bool,
    pub dropped_turns: usize,
    pub kept_recent: usize,
    pub summary_entries_added: usize,
    pub pre_compaction_turns: usize,
    pub post_compaction_turns: usize,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ContextDebugTurn {
    pub role: String,
    pub content: String,
    pub chars: usize,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ContextDebugMemoryBlock {
    pub label: String,
    pub scope: String,
    pub description: Option<String>,
    pub limit: usize,
    pub read_only: bool,
    pub updated_at: String,
    pub chars: usize,
    pub content_preview: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionContextDebugSnapshot {
    pub session_id: String,
    pub history_count: usize,
    pub visible_history: Vec<ContextDebugTurn>,
    pub summary: String,
    pub memory_blocks: Vec<ContextDebugMemoryBlock>,
    pub estimated_tokens: usize,
    pub compacted: bool,
    pub budget: ContextBudgetStats,
    pub token_breakdown: ContextTokenBreakdown,
    pub normalization: HistoryNormalizationStats,
    pub compaction: ContextCompactionStats,
    pub prune: ToolOutputPruneStats,
    pub recent_failures: Vec<ContextDebugTurn>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolOutputPruneStats {
    pub applied: bool,
    pub pruned_turns: usize,
    pub chars_removed: usize,
    pub kept_chars: usize,
}

pub(crate) struct ContextAssembly {
    pub messages: Vec<serde_json::Value>,
    pub memory_context: String,
    pub estimated_tokens: usize,
    pub summary: String,
    pub visible_history: Vec<ContextDebugTurn>,
    pub memory_blocks: Vec<ContextDebugMemoryBlock>,
    pub budget: ContextBudgetStats,
    pub token_breakdown: ContextTokenBreakdown,
    pub normalization: HistoryNormalizationStats,
    pub compaction: ContextCompactionStats,
    pub prune: ToolOutputPruneStats,
    pub recent_failures: Vec<ContextDebugTurn>,
}

struct NormalizedHistory {
    turns: Vec<ChatTurn>,
    stats: HistoryNormalizationStats,
}

fn clip_chars(input: &str, max_chars: usize) -> String {
    input.chars().take(max_chars).collect::<String>()
}

fn trim_summary(summary: &mut String) {
    if summary.chars().count() <= SUMMARY_MAX_CHARS {
        return;
    }
    let kept = summary
        .chars()
        .rev()
        .take(SUMMARY_MAX_CHARS)
        .collect::<String>()
        .chars()
        .rev()
        .collect::<String>();
    *summary = kept;
}

fn normalize_content(input: &str) -> Option<String> {
    let normalized = input.replace("\r\n", "\n").trim().to_string();
    if normalized.is_empty() {
        None
    } else {
        Some(normalized)
    }
}

fn normalize_history(history: &[ChatTurn]) -> NormalizedHistory {
    let mut turns = Vec::new();
    let mut dropped_invalid_roles = 0usize;
    let mut dropped_empty_turns = 0usize;

    for turn in history {
        let role = match turn.role.as_str() {
            "user" | "assistant" | "system" => turn.role.clone(),
            _ => {
                dropped_invalid_roles += 1;
                continue;
            }
        };
        let Some(content) = normalize_content(&turn.content) else {
            dropped_empty_turns += 1;
            continue;
        };
        turns.push(ChatTurn { role, content });
    }

    let kept_turns = turns.len();
    NormalizedHistory {
        turns,
        stats: HistoryNormalizationStats {
            total_turns: history.len(),
            kept_turns,
            dropped_invalid_roles,
            dropped_empty_turns,
        },
    }
}

fn compact_history_parts(
    history: &mut Vec<ChatTurn>,
    summary: &mut String,
    mark_applied: bool,
) -> ContextCompactionStats {
    let pre_compaction_turns = history.len();
    if history.len() <= MAX_VISIBLE_HISTORY {
        return ContextCompactionStats {
            applied: false,
            would_apply: false,
            dropped_turns: 0,
            kept_recent: history.len(),
            summary_entries_added: 0,
            pre_compaction_turns,
            post_compaction_turns: history.len(),
        };
    }

    let split_at = history.len().saturating_sub(COMPACT_KEEP_RECENT);
    let older = history.drain(0..split_at).collect::<Vec<_>>();
    let dropped_turns = older.len();
    if older.is_empty() {
        return ContextCompactionStats {
            applied: false,
            would_apply: false,
            dropped_turns: 0,
            kept_recent: history.len(),
            summary_entries_added: 0,
            pre_compaction_turns,
            post_compaction_turns: history.len(),
        };
    }

    summary.push_str("[Compacted History]\n");
    let mut summary_entries_added = 0usize;
    for turn in older {
        let clipped = clip_chars(&turn.content, 220);
        summary.push_str(&format!("- {}: {}\n", turn.role, clipped));
        summary_entries_added += 1;
    }
    trim_summary(summary);

    ContextCompactionStats {
        applied: mark_applied,
        would_apply: true,
        dropped_turns,
        kept_recent: history.len(),
        summary_entries_added,
        pre_compaction_turns,
        post_compaction_turns: history.len(),
    }
}

fn build_visible_history(history: &[ChatTurn]) -> Vec<ContextDebugTurn> {
    let start = history.len().saturating_sub(MAX_VISIBLE_HISTORY);
    history[start..]
        .iter()
        .map(|turn| ContextDebugTurn {
            role: turn.role.clone(),
            chars: turn.content.chars().count(),
            content: turn.content.clone(),
        })
        .collect()
}

fn looks_like_tool_output(turn: &ChatTurn) -> bool {
    if turn.role == "user" {
        return false;
    }
    let content = turn.content.trim();
    let lower = content.to_ascii_lowercase();
    content.chars().count() > TOOL_OUTPUT_PRUNE_CHARS
        || lower.contains("\"files\"")
        || lower.contains("\"matches\"")
        || lower.contains("\"stdout\"")
        || lower.contains("\"stderr\"")
        || content.lines().count() > 40
}

fn prune_tool_output_turns(history: &[ChatTurn]) -> (Vec<ChatTurn>, ToolOutputPruneStats) {
    let mut pruned_turns = 0usize;
    let mut chars_removed = 0usize;
    let mut kept_chars = 0usize;
    let turns = history
        .iter()
        .map(|turn| {
            if !looks_like_tool_output(turn) {
                kept_chars += turn.content.chars().count();
                return turn.clone();
            }
            let original_chars = turn.content.chars().count();
            let clipped = clip_chars(&turn.content, TOOL_OUTPUT_PRUNE_CHARS);
            let content = format!("[Pruned Tool Output]\n{}", clipped);
            pruned_turns += 1;
            chars_removed += original_chars.saturating_sub(content.chars().count());
            kept_chars += content.chars().count();
            ChatTurn {
                role: turn.role.clone(),
                content,
            }
        })
        .collect::<Vec<_>>();
    (
        turns,
        ToolOutputPruneStats {
            applied: pruned_turns > 0,
            pruned_turns,
            chars_removed,
            kept_chars,
        },
    )
}

fn build_visible_messages(
    visible_history: &[ContextDebugTurn],
    summary: &str,
) -> Vec<serde_json::Value> {
    let mut messages = Vec::new();
    if !summary.trim().is_empty() {
        messages.push(json!({
            "role": "system",
            "content": format!("[Session Summary]\n{}", summary)
        }));
    }

    for turn in visible_history {
        messages.push(json!({
            "role": turn.role,
            "content": turn.content
        }));
    }
    messages
}

fn build_memory_debug(blocks: &[MemoryBlock]) -> Vec<ContextDebugMemoryBlock> {
    blocks
        .iter()
        .map(|block| ContextDebugMemoryBlock {
            label: block.label.clone(),
            scope: block.scope.clone(),
            description: block.description.clone(),
            limit: block.limit,
            read_only: block.read_only,
            updated_at: block.updated_at.clone(),
            chars: block.content.chars().count(),
            content_preview: clip_chars(block.content.trim(), MEMORY_PREVIEW_CHARS),
        })
        .collect()
}

fn looks_like_failure_turn(turn: &ChatTurn) -> bool {
    if turn.role != "system" {
        return false;
    }
    let lower = turn.content.to_lowercase();
    lower.contains("failed") || lower.contains("error") || turn.content.contains("失败")
}

fn collect_recent_failures(history: &[ChatTurn]) -> Vec<ContextDebugTurn> {
    history
        .iter()
        .rev()
        .filter(|turn| looks_like_failure_turn(turn))
        .take(FAILURE_PREVIEW_LIMIT)
        .map(|turn| ContextDebugTurn {
            role: turn.role.clone(),
            chars: turn.content.chars().count(),
            content: turn.content.clone(),
        })
        .collect()
}

pub(crate) fn estimate_token_budget(messages: &[serde_json::Value], memory_context: &str) -> usize {
    let mut chars = memory_context.chars().count();
    for message in messages {
        if let Some(content) = message.get("content").and_then(|value| value.as_str()) {
            chars += content.chars().count();
        }
    }
    (chars / 4).max(1)
}

fn estimate_tokens_from_chars(chars: usize) -> usize {
    (chars / 4).max(1)
}

fn build_context_budget(
    visible_history: &[ContextDebugTurn],
    summary: &str,
    memory_context: &str,
) -> ContextBudgetStats {
    ContextBudgetStats {
        history_chars: visible_history.iter().map(|turn| turn.chars).sum(),
        summary_chars: summary.chars().count(),
        memory_chars: memory_context.chars().count(),
        visible_turns: visible_history.len(),
        max_visible_history: MAX_VISIBLE_HISTORY,
    }
}

fn build_context_assembly(
    data: &mut crate::state::AppData,
    session_id: &str,
    repo_root: &str,
    persist_compaction: bool,
) -> ContextAssembly {
    let mut history = data
        .chat_history
        .get(session_id)
        .cloned()
        .unwrap_or_default();
    let mut summary = data
        .chat_summary
        .get(session_id)
        .cloned()
        .unwrap_or_default();
    let compaction = compact_history_parts(&mut history, &mut summary, persist_compaction);

    if persist_compaction && compaction.would_apply {
        data.chat_history
            .insert(session_id.to_string(), history.clone());
        data.chat_summary
            .insert(session_id.to_string(), summary.clone());
    }

    let normalized = normalize_history(&history);
    let (pruned_turns, prune) = prune_tool_output_turns(&normalized.turns);
    let visible_history = build_visible_history(&pruned_turns);
    let messages = build_visible_messages(&visible_history, &summary);
    let memory_blocks = read_all_memory_blocks(repo_root).unwrap_or_default();
    let memory_context = memory_blocks_to_prompt(&memory_blocks);
    let budget = build_context_budget(&visible_history, &summary, &memory_context);
    let estimated_tokens = estimate_token_budget(&messages, &memory_context);
    let token_breakdown = ContextTokenBreakdown {
        history_tokens: estimate_tokens_from_chars(budget.history_chars),
        summary_tokens: estimate_tokens_from_chars(budget.summary_chars),
        memory_tokens: estimate_tokens_from_chars(budget.memory_chars),
        pruned_tool_output_tokens: estimate_tokens_from_chars(prune.chars_removed),
        total_tokens: estimated_tokens,
    };
    let recent_failures = collect_recent_failures(&normalized.turns);

    ContextAssembly {
        messages,
        memory_context,
        estimated_tokens,
        summary,
        visible_history,
        memory_blocks: build_memory_debug(&memory_blocks),
        budget,
        token_breakdown,
        normalization: normalized.stats,
        compaction,
        prune,
        recent_failures,
    }
}

pub(crate) fn assemble_session_context(
    data: &mut crate::state::AppData,
    session_id: &str,
    repo_root: &str,
) -> Result<ContextAssembly, String> {
    Ok(build_context_assembly(data, session_id, repo_root, true))
}

pub(crate) fn build_session_context_debug_snapshot(
    data: &mut crate::state::AppData,
    session_id: &str,
    repo_root: &str,
) -> Result<SessionContextDebugSnapshot, String> {
    let assembly = build_context_assembly(data, session_id, repo_root, false);
    Ok(SessionContextDebugSnapshot {
        session_id: session_id.to_string(),
        history_count: assembly.normalization.kept_turns,
        visible_history: assembly.visible_history,
        summary: assembly.summary,
        memory_blocks: assembly.memory_blocks,
        estimated_tokens: assembly.estimated_tokens,
        compacted: assembly.compaction.applied || assembly.compaction.would_apply,
        budget: assembly.budget,
        token_breakdown: assembly.token_breakdown,
        normalization: assembly.normalization,
        compaction: assembly.compaction,
        prune: assembly.prune,
        recent_failures: assembly.recent_failures,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_repo_root(tag: &str) -> String {
        let root =
            std::env::temp_dir().join(format!("codinggirl-context-{}-{}", tag, std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        root.to_string_lossy().to_string()
    }

    #[test]
    fn compact_history_moves_old_turns_into_summary() {
        let mut data = crate::state::AppData::default();
        let session_id = "s-test";
        let repo_root = temp_repo_root("compact");
        let history = data.chat_history.entry(session_id.into()).or_default();
        for idx in 0..30 {
            history.push(ChatTurn {
                role: if idx % 2 == 0 {
                    "user".into()
                } else {
                    "assistant".into()
                },
                content: format!("message {}", idx),
            });
        }

        let context = assemble_session_context(&mut data, session_id, &repo_root).unwrap();
        assert!(context.compaction.applied);
        assert!(data.chat_history[session_id].len() <= COMPACT_KEEP_RECENT);
        assert!(data.chat_summary[session_id].contains("[Compacted History]"));
    }

    #[test]
    fn debug_snapshot_does_not_mutate_history() {
        let mut data = crate::state::AppData::default();
        let session_id = "s-debug";
        let repo_root = temp_repo_root("debug");
        let history = data.chat_history.entry(session_id.into()).or_default();
        for idx in 0..30 {
            history.push(ChatTurn {
                role: "user".into(),
                content: format!("message {}", idx),
            });
        }

        let snapshot =
            build_session_context_debug_snapshot(&mut data, session_id, &repo_root).unwrap();
        assert!(snapshot.compaction.would_apply);
        assert_eq!(data.chat_history[session_id].len(), 30);
    }

    #[test]
    fn normalization_drops_invalid_and_empty_turns() {
        let history = vec![
            ChatTurn {
                role: "user".into(),
                content: "keep".into(),
            },
            ChatTurn {
                role: "tool".into(),
                content: "drop".into(),
            },
            ChatTurn {
                role: "assistant".into(),
                content: "   ".into(),
            },
        ];

        let normalized = normalize_history(&history);
        assert_eq!(normalized.turns.len(), 1);
        assert_eq!(normalized.stats.dropped_invalid_roles, 1);
        assert_eq!(normalized.stats.dropped_empty_turns, 1);
    }
}
