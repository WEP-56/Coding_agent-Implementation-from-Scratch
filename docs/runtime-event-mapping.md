# Runtime Event Mapping（Python JSONL ↔ Desktop Trace）

更新时间：2026-03-15

目的：将 **Python agent** 输出的 JSONL `kind`（来源：`codinggirl/runtime/storage_sqlite.py` 记录事件、`codinggirl/core/desktop_agent_stream_cli.py` 流式输出）
与 **Desktop（Tauri/Rust）** 的 canonical trace/timeline 展示语义对齐。

> 这是 P0-2（事件语义收敛）的单一事实源。任何新增/修改事件，必须先改这里。

---

## 1. 事件源

### 1.1 Python 事件（JSONL）
- `type=event` 且包含：`{ kind, ts, payload, stepId? }`
- 主要 kind：
  - `loop_iteration`, `loop_complete`, `loop_error`, `loop_max_iterations`
  - `llm_request`, `llm_response`, `llm_error`
  - `todo_initialized`, `todo_updated`
  - `context_micro_compact`, `context_auto_compact`
  - `subagent_start`, `subagent_complete`, `subagent_error`, `subagent_max_iterations`
  - （未来）background/task graph 类事件

### 1.2 Desktop Trace
- Rust 侧使用 `push_trace_event_for_run(...)` 写入 `SessionEvent`/`SessionTurnItem` 体系
- UI 侧使用 title（如 `trace.phase.*`, `trace.context.*`）做 humanize 映射

---

## 2. 映射表（kind → trace title/type/status）

| Python kind | Desktop trace title | traceType | status 规则 | detail 建议 |
|---|---|---|---|---|
| loop_iteration | trace.phase.explore | session | running | iteration/message_count |
| llm_request | trace.phase.plan | session | running | message_count/tools_count |
| llm_response | trace.phase.plan | session | success | finish_reason/tool_calls_count |
| llm_error | trace.phase.plan | session | failed | error |
| context_micro_compact | trace.context.micro_compact | session | success | compact_stats |
| context_auto_compact | trace.context.compacted | session | success | compact_stats |
| todo_initialized | trace.context.todo_initialized | session | success | todo stats + rendered |
| todo_updated | trace.context.todo_updated | session | success | todo stats + rendered |
| subagent_start | trace.phase.subagent.started | session | success | subagent_id/task |
| subagent_complete | trace.phase.subagent.completed | session | success | iterations/tool_calls_count |
| subagent_error | trace.phase.subagent.failed | session | failed | error |
| subagent_max_iterations | trace.phase.subagent.max_iterations | session | failed | iterations |
| loop_complete | trace.phase.finalize | session | success | reason |
| loop_error | trace.phase.finalize | session | failed | error |
| loop_max_iterations | trace.phase.finalize | session | failed | iterations |

说明：
- `status` 统一映射到 UI 允许的：pending/running/success/failed。
- 目前 `python_agent.rs` 里已有 `map_kind_to_trace_title` + `status_for_kind`，本表用于校准与补齐。

---

## 3. 后续扩展（Background/TaskGraph）

当 Python core 侧引入 background/task graph 的 store.append_event 时，建议沿用：
- background：`background_started/background_completed/background_failed`
- task graph：`task_created/task_updated/task_unlocked`

并映射到 Desktop title：
- `trace.phase.background.*`
- `trace.task.*`

---

## 4. 落地检查清单（P0-2 验收）

- [ ] Desktop UI（workflow/trace）能看到 todo/context/subagent 事件（非 tool call）
- [ ] 导出 trace bundle 包含上述事件，并可按 kind/title 回放
- [ ] 事件命名在 Python/Rust/UI 三端一致（改名必须同步）
