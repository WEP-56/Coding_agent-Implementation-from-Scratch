# CodingGirl 进化计划（逐步强化为 AI IDE）

更新时间：2026-03-15

这份文档的目标是把 **CodingGirl（React + Tauri + Rust runtime + Python agent core）** 从“可用原型”推进到“实力强大的 AI IDE”。

**原则：**
- 先把系统跑稳（P0），再跑聪明（P1），最后跑快/可扩展（P2/P3）。
- 每一步都要能落地、可验证（tests / demo script / UI 观测点）。
- 少做“再加一个按钮”，多做“减少隐式状态、收敛语义、把 trace 变成事实源”。

---

## 0. 现状快照（你现在已经有的）

### 0.1 仓库双线结构
- `apps/desktop/`：**主产品面**（React + Tauri），包含 canonical `SessionRun / SessionTurn / SessionTurnItem`、workflow cards、trace panel、approval panel。
- `codinggirl/`：Python agent core（agent loop / todo / context / subagent / task graph / background / tools / sqlite store）。
- `tmp/`：上游参考（Codex / OpenCode / openai-agents-python / smolagents …）。

### 0.2 已经具备的关键能力（非常重要）
- Python 侧：Agent Loop、TodoWrite、Context Management（micro/auto）、Subagent、Task Graph、BackgroundManager、Skills。
- Desktop 侧：workflow / trace / approval / rollback / artifact / error taxonomy、以及 Python agent 的 JSONL 流式接入（`desktop_agent_stream_cli.py` → Rust `python_agent.rs`）。

### 0.3 当前最主要的“阻塞点”
1) **事件/状态语义尚未完全统一**：Rust runtime 与 Python runtime 的事件名、统计、生命周期还没完全收敛成一套“canonical runtime grammar”。
2) **前端对 Python runtime 的高级能力展示不足**：Todo/Context/Background/TaskGraph/Subagent 的 UI 只部分打通。
3) **平台鲁棒性问题**：桌面端启动 Python 的方式需要更健壮（Windows 环境下 `python` 可能不在 PATH，只有 `py`）。

---

## 1. 总体目标（AI IDE 的“强大”指什么）

CodingGirl 的 AI IDE 形态应具备以下闭环：

1) **可观测（Observability）**：每一步模型思考/工具调用/文件变更/审批/回滚都可追溯、可导出。
2) **可控（Control）**：高风险动作强制审批；支持中途停止、重试、分叉（fork）和回滚。
3) **可扩展（Extensibility）**：skills / plugins / policies 可配置；未来支持多 agent 并行、worktree 隔离。
4) **可长期执行（Long-running）**：后台任务 + 断点续跑 + 稳定的 session 状态恢复。

---

## 2. 进化路线（按阶段交付）

### Phase P0（稳定性与语义收敛，优先级最高）
目标：**所有执行路径都可稳定运行 + trace 语义统一**。

交付项：
- P0-1：Windows/Linux/macOS 下 Python agent 启动鲁棒（优先 Windows：`py` fallback）。
- P0-2：Python runtime 关键事件对齐（loop、todo、context、subagent、background、task graph）→ 在 Desktop trace 中能正确聚合、筛选、导出。
- P0-3：错误分类（error taxonomy）覆盖 Python agent：将 Python 侧关键失败映射到 Rust error taxonomy（retryable / hint / fallback）。

验收：
- 能在 Desktop 端稳定跑 20+ 轮 Python agent、包含多次 tool call、出现一次失败并能重试。
- 导出 trace bundle 可完整复现关键链路。


### Phase P1（可视化与交互：把“能力”变成“IDE 面板”）
目标：**把 Python runtime 的能力以 IDE 面板形式呈现**，做到“看得见、点得动、能纠偏”。

交付项（按 UI 价值排序）：
- P1-1：右侧 Sidebar 增加 Python Todo 面板（状态统计 + 列表）。
- P1-2：Context Stats 面板（token/compact/tool results/节省量），并能一键导出 context debug。
- P1-3：Background tasks 面板（running/completed、stdout/stderr 可查看、可取消）。
- P1-4：Subagent trace 层级展示（可折叠）。
- P1-5：Task Graph 可视化（先列表/简图，后 DAG）。

验收：
- 在一次真实任务中，用户可以通过 UI 看到 todo 进度 + context 变化 + 背景任务完成，并能定位失败节点。


### Phase P2（并行与隔离：多任务不打架）
目标：**支持多任务并行执行且互不冲突**。

交付项：
- P2-1：Worktree Isolation（每个 task 一个 worktree / branch）
- P2-2：Task Graph + Worktree + Background 的三者联动（ready tasks 自动开始、失败回滚、完成解锁）。

验收：
- 同时发起 2~3 个任务，分别在不同 worktree 中修改不同区域；最终能合并/选择性采纳。


### Phase P3（效率层与生态）
目标：**更聪明、更快、更可扩展**。

交付项（择优）：
- Repo map / symbols 索引注入（更强的上下文检索 + 自动关联）。
- 插件生态：tool pack / skill pack 分发与版本管理。
- 可恢复会话：checkpoint、resume、fork。

---

## 3. 近期执行清单（从今天开始的 1~2 周）

### Week 1：P0-1 + P0-2
1) 修复 Desktop 启动 Python 的鲁棒性（Windows `py` fallback）。
2) 为 Python agent 增加“低噪声但关键”的事件：
   - `context:stats_update` / `todo:stats_update` / `loop:iteration` / `loop:complete`
   - 并在 Rust 侧把这些事件映射为 canonical trace items。
3) 加 1 个端到端 smoke：从 Desktop 发起 python_agent run，产生 todo + context compact + tool call，然后导出 trace bundle。

### Week 2：P1-1 + P1-2
1) 右侧栏新增 Python Todo 面板：读取 `SessionWorkflowSnapshotEvent.pythonTodo`。
2) Context Stats 面板：使用现有 `get_session_context_debug` + 新增统计事件（如有）。

---

## 4. “参考项目”对齐（tmp/）怎么用

`tmp/` 里的上游项目不是要照抄 UI，而是用来校验 **runtime 行为是否 canonical**：
- Codex/OpenCode：更稳定的 tool loop / error handling / approval/rollback 语义。
- openai-agents-python：对 multi-agent / handoff / tracing 的参考。

对齐方式：
- 每引入一个理念，只做一个最小闭环 demo（trace 可见、可验证）。
- 禁止一次性大重写；用 feature flag 或 route 逐步替换。

---

## 5. 文档与实现的绑定规则（很重要）

为了满足“按照文档逐步修改”的要求：
- 每次改动都要在本文件的 **“近期执行清单”** 里勾选/追加，并在对应 PR/commit message 里引用条目编号（例如 `P0-1`）。
- 每次合入至少包含：
  - (a) 一个可运行验证命令（pytest / cargo test / npm build 之一）
  - (b) 一段 UI 可观测点（trace item 或 snapshot）

---

## 6. 当前开始执行的第一步（已完成）

- [x] **P0-1：Windows 下启动 Python 的 fallback（`python` → `py`）**，这是桌面端稳定运行 Python agent 的基础。
  - 实现：Tauri Rust 侧 `run_python_agent_message` 启动命令增加 `py` fallback。
  - 验证：`apps/desktop/src-tauri` 下 `cargo test` 通过。

## 7. 当前开始执行的第二步（进行中 / 下一步）

- [ ] **P0-2：事件语义收敛（Python JSONL kind ↔ Desktop trace title）**
  - 目标：让 Python agent 的关键事件（todo/context/subagent/background/loop）在 Desktop 的 workflow/trace 中呈现为一致的、可筛选的 canonical 项。
  - 方法：先补一份映射表（单一事实源），再按映射表逐个完善 emit 与展示。
