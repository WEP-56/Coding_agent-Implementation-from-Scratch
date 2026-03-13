# TODO - 架构重构路线图

**更新时间**：2026-03-13（阶段 1-2 已完成）
**核心判断**：~~当前架构缺少 agent loop 核心~~ → **已建立自主循环架构** ✅

**参考**：https://learn-claude-agents.vercel.app/en/s01/
**标记**：`[x]` 已完成 / `[~]` 部分完成 / `[ ]` 待办 / `[!]` 架构关键

---

## 阶段 0：现状快照与架构诊断

### 已有的好基础
- [x] 工具系统：ToolRegistry + ToolRunner + hooks + schema validation + permission gating
- [x] 工具集：fs_read/write/replace/insert、search_rg、fs_glob、patch_apply、index_*、cmd_run
- [x] 存储层：SQLiteStore + event/tool_call 持久化 + replay_only 模式
- [x] 前端：React + Tauri + workflow cards + trace panel + approval panel

### 架构缺失（对比教程）→ 已完成部分
- [x] ~~**缺少 Agent Loop**~~ → **已实现** ✅
- [x] ~~**缺少 Message History**~~ → **已实现** ✅
- [x] ~~**缺少 TodoWrite 协调**~~ → **已实现** ✅
- [ ] **缺少 Context Management**：没有 micro-compact / auto-compact / manual compact
- [ ] **缺少 Subagent 机制**：没有 task tool 与子 agent 隔离
- [ ] **缺少 Task Graph**：没有依赖管理与并行任务协调
- [ ] **缺少 Background Execution**：cmd_run 是同步的，没有后台任务管理
- [ ] **缺少 Worktree Isolation**：没有任务隔离与并行工作防冲突

---

## 阶段 1：建立 Agent Loop 核心（s01-s02）✅ 已完成

**目标**：把 orchestrator 从"硬编码流程"改造为"自主循环"

### 1.1 实现基础 Agent Loop
- [x] 创建 `AgentLoop` 类：`while stop_reason == "tool_use"` 循环
- [x] 集成 LLM adapter：支持 tool_use 的消息格式（OpenAI/Anthropic）
- [x] Message History 管理：累积 user/assistant/tool_result 消息
- [x] 工具调度：从 LLM response 提取 tool_use blocks → ToolRunner.call() → 结果追加到 messages
- [x] 真实场景测试：成功完成"统计 Python 文件"任务（2 轮迭代，找到 52 个文件）

### 1.2 工具系统适配
- [x] 工具已有 dispatch map（ToolRegistry）
- [x] 工具已有 schema + handler 分离
- [x] 修复 OpenAI adapter URL 构建问题
- [x] 修复 tool result 消息格式（支持 tool_call_id）
- [x] 修复 assistant 消息包含 tool_calls

### 1.3 已创建的文件
- [x] `codinggirl/core/agent_loop.py` (262 行) - 核心 Agent Loop
- [x] `codinggirl/runtime/llm_adapter/anthropic_provider.py` (152 行) - Claude 支持
- [x] `codinggirl/core/agent_loop_cli.py` (120 行) - CLI 测试入口
- [x] `tests/test_agent_loop.py` (4 个测试全部通过)

**里程碑**：✅ 能跑通"用户问题 → LLM 自主调用工具 → 返回答案"的完整循环

---

## 阶段 2：任务规划与进度追踪（s03）✅ 已完成

**目标**：让 agent 能分解任务、追踪进度、避免漂移

### 2.1 实现 TodoWrite 机制
- [x] 创建 `TodoManager` 类：管理 pending/in_progress/completed 状态
- [x] 注册 `todo_update` 工具：agent 可调用更新任务列表
- [x] 实现 nag reminder：3 轮未更新 todo 则注入提醒
- [x] 在 message history 中渲染 todo 列表（让 agent 看到自己的进度）
- [x] 支持 step_id 和 title 双重匹配（容错）

### 2.2 集成到 Agent Loop
- [x] 在 loop 开始时注入初始 todo（从 Plan 生成）
- [x] 每轮检查 todo 更新频率，触发 nag
- [x] 自动注册 todo_update 工具
- [x] 追踪 todo 更新事件到数据库
- [ ] 在 UI 展示 todo 列表（实时同步）← 待前端集成

### 2.3 真实场景验证
- [x] 单元测试通过：`{'total': 3, 'pending': 1, 'in_progress': 1, 'completed': 1}`
- [x] 真实模型测试：Agent **主动调用了 todo_update 工具**（第 1 轮和第 3 轮）
- [x] 从数据库日志验证：Agent 理解并使用了任务追踪机制

### 2.4 已创建的文件
- [x] `codinggirl/core/todo_manager.py` (145 行) - TodoManager 核心
- [x] `codinggirl/core/todo_tool.py` (73 行) - todo_update 工具
- [x] `codinggirl/core/agent_loop_with_todo.py` (327 行) - 集成版 Agent Loop
- [x] `codinggirl/core/agent_loop_with_todo_cli.py` (180 行) - CLI 入口
- [x] `tests/test_todo_write.py` (测试通过)

**里程碑**：✅ agent 能自主分解多步任务，并在执行中保持焦点

---

## 阶段 3：上下文管理与压缩（s06）✅ 已完成

**目标**：支持大型代码库工作，避免 context overflow

### 3.1 三层压缩策略
- [x] **Layer 1 - Micro-compact**：每轮自动替换旧工具结果为占位符（保留最近 3 个）
- [x] **Layer 2 - Auto-compact**：token 超过阈值时，LLM 生成摘要，替换 messages
- [ ] **Layer 3 - Manual compact**：注册 `compact` 工具，用户/agent 可主动触发

### 3.2 集成到 Agent Loop
- [x] 创建 `ContextManager` 类：管理三层压缩策略
- [x] 实现 token 估算：字符数 / 4（简单有效）
- [x] 实现 micro_compact：保留最近 N 个工具结果，替换旧结果为占位符
- [x] 实现 auto_compact：超过阈值时调用 LLM 生成摘要
- [x] 集成到 `AgentLoopWithContext`：每轮自动检查并压缩
- [x] 记录压缩事件到数据库：context_micro_compact / context_auto_compact

### 3.3 真实场景验证
- [x] 单元测试通过：micro-compact 和 auto-compact 都正常工作
- [x] Token 估算测试：验证字符数 / 4 的准确性
- [x] 压缩统计测试：验证 saved_tokens 计算正确
- [ ] 真实模型测试：100+ 文件读取场景 ← 待测试

### 3.4 已创建的文件
- [x] `codinggirl/core/context_manager.py` (255 行) - ContextManager 核心
- [x] `codinggirl/core/agent_loop_with_context.py` (374 行) - 集成版 Agent Loop
- [x] `tests/test_context_manager.py` (测试通过)
- [x] `docs/stage3-context-management-plan.md` - 实施计划文档
- [x] `docs/frontend-integration-checklist.md` - 前端集成清单

### 3.5 待完成项
- [x] 创建 CLI 入口：`agent_loop_with_context_cli.py` ✅
- [ ] Transcript 持久化：扩展 SQLiteStore 保存完整 message history
- [x] Manual compact 工具：`compact_tool.py` 已创建 ✅
- [ ] 前端集成：Context Stats Panel、事件推送

**里程碑**：✅ 核心压缩机制已实现，能在单个 session 中处理大量工具调用

---

## 阶段 4：子 Agent 与任务委托（s04）✅ 已完成

**目标**：探索性任务委托给子 agent，保持父 agent 上下文清洁

### 4.1 实现 Subagent 机制
- [x] 创建 `SubagentRunner` 类：独立 message history + agent loop
- [x] 注册 `task` 工具：父 agent 可委托子任务
- [x] 子 agent 工具限制：只能用只读工具（fs_read/fs_glob/search_rg/index_*），不能再创建子 agent
- [x] 结果汇总：子 agent 返回摘要给父 agent（自动截取前 500 字符）
- [x] 事件追踪：subagent_start / subagent_complete / subagent_error

### 4.2 集成到 Agent Loop
- [x] 创建 `AgentLoopWithSubagent`：集成 TodoWrite + Context Management + Subagent
- [x] 在 system prompt 注入 task 工具使用指南
- [x] 统计 subagent 调用次数
- [x] 所有测试通过（5 个测试用例）

### 4.3 已创建的文件
- [x] `codinggirl/core/subagent_runner.py` (300+ 行) - SubagentRunner 核心
- [x] `codinggirl/core/task_tool.py` (80 行) - task 工具
- [x] `codinggirl/core/agent_loop_with_subagent.py` (450+ 行) - 集成版 Agent Loop
- [x] `codinggirl/core/compact_tool.py` (90 行) - manual compact 工具
- [x] `tests/test_subagent.py` (测试通过)

### 4.4 测试覆盖
- [x] 基本执行流程：子 agent 完成任务并返回摘要
- [x] 工具调用：子 agent 可以调用允许的工具
- [x] 工具限制：尝试调用不允许的工具会收到错误
- [x] 最大迭代次数：达到上限时返回部分结果
- [x] 上下文传递：父 agent 可以传递上下文给子 agent

### 4.5 典型场景
- [x] "这个项目用什么测试框架？" → 子 agent 探索多个文件 → 返回答案
- [x] "找出所有 API 端点" → 子 agent 搜索+读取 → 返回列表

**里程碑**：✅ 父 agent 能委托探索任务，自己的 context 保持简洁

---

## 阶段 5：技能系统与知识加载（s05）✅ 已完成

**目标**：按需加载领域知识，避免 system prompt 膨胀

### 5.1 实现 Skills 系统
- [x] 创建 `SkillLoader` 类：扫描 `skills/` 目录
- [x] Skill 格式：YAML frontmatter（name/description/tags/auto_load）+ markdown body
- [x] 注册 `load_skill` 工具：agent 可按需加载技能
- [x] System prompt 包含技能摘要（~100 tokens/skill）
- [x] 支持自动加载高频技能（auto_load: true）

### 5.2 内置技能
- [x] `git-workflow.md`：commit/branch/PR 最佳实践
- [x] `code-review.md`：review checklist（安全、性能、质量）
- [x] `testing.md`：测试策略与工具选择（pytest/jest/vitest）
- [x] `debugging.md`：常见问题诊断流程（print/logging/debugger）

### 5.3 已创建的文件
- [x] `codinggirl/core/skill_loader.py` (150+ 行) - SkillLoader 核心
- [x] `codinggirl/core/load_skill_tool.py` (70 行) - load_skill 工具
- [x] `skills/git-workflow.md` (200+ 行) - Git 最佳实践
- [x] `skills/testing.md` (300+ 行) - 测试策略
- [x] `skills/debugging.md` (300+ 行) - 调试技巧
- [x] `skills/code-review.md` (400+ 行) - Code review checklist
- [x] `tests/test_skill_loader.py` (测试通过)

### 5.4 测试覆盖
- [x] 扫描目录并解析技能文件
- [x] 解析 YAML frontmatter
- [x] 处理没有 frontmatter 的文件
- [x] 列出技能摘要
- [x] 获取自动加载的技能
- [x] 检查技能是否存在
- [x] 验证真实 skills 目录

**里程碑**：✅ Agent 能根据任务类型自主加载相关技能，节省 system prompt tokens

---

## 阶段 6：任务图与依赖管理（s07）✅ 已完成

**目标**：支持复杂任务的依赖协调与并行执行

### 6.1 实现 Task Graph
- [x] 创建 `TaskGraph` 类：文件持久化（`.tasks/` 目录，JSON 格式）
- [x] Task 状态：pending → in_progress → completed / failed / cancelled
- [x] 依赖字段：`blocked_by` / `blocks`
- [x] 自动解锁：任务完成时移除依赖者的 `blocked_by`
- [x] DAG 验证：检测循环依赖
- [x] 任务链查询：获取任务的完整依赖链

### 6.2 工具集成
- [x] 注册 `task_create` 工具：创建任务并指定依赖
- [x] 注册 `task_update` 工具：更新任务状态
- [x] 注册 `task_list_ready` 工具：查询可执行任务
- [x] 注册 `task_list` 工具：列出所有任务（可按状态过滤）
- [x] 注册 `task_get` 工具：获取任务详情
- [ ] 在 UI 展示任务图（依赖关系可视化）← 待前端集成

### 6.3 已创建的文件
- [x] `codinggirl/core/task_graph.py` (350+ 行) - TaskGraph 核心
- [x] `codinggirl/core/task_graph_tools.py` (300+ 行) - 任务图工具
- [x] `tests/test_task_graph.py` (12 个测试全部通过)

### 6.4 测试覆盖
- [x] 创建任务（带/不带依赖）
- [x] 更新任务状态
- [x] 自动解锁依赖任务
- [x] 列出可执行的任务
- [x] 列出任务（按状态过滤）
- [x] 获取统计信息
- [x] 持久化到文件系统
- [x] 删除任务（自动移除依赖关系）
- [x] DAG 验证
- [x] 获取任务依赖链
- [x] 并行任务场景（A → (B, C) → D）

### 6.5 典型场景
- [x] 顺序任务：A → B → C（B 等待 A 完成，C 等待 B 完成）
- [x] 并行任务：A → (B, C) → D（B 和 C 可并行执行，D 等待两者完成）
- [x] 复杂依赖：多个任务依赖同一个任务

**里程碑**：✅ Agent 能规划"A 完成后并行执行 B 和 C"的复杂流程

---

## 阶段 7：后台任务执行（s08）✅ 已完成

**目标**：长时间命令不阻塞 agent loop

### 7.1 实现 BackgroundManager
- [x] 创建 `BackgroundManager` 类：线程池执行命令
- [x] 任务队列：thread-safe queue 收集完成通知
- [x] 注册 `run_background` 工具：启动后台任务并返回 task_id
- [x] 注册 `check_background` 工具：查询任务状态
- [x] 注册 `list_background` 工具：列出所有后台任务

### 7.2 自动通知
- [x] `drain_completions()` 方法：获取所有已完成的任务
- [x] Agent loop 可在每轮迭代前检查完成的任务
- [x] 任务完成后自动加入通知队列

### 7.3 任务管理
- [x] 任务状态追踪：pending → running → completed/failed
- [x] 输出大小限制：防止内存溢出（默认 1MB）
- [x] 自动清理：清理旧的已完成任务
- [x] 并发控制：线程池限制并发数（默认 4）
- [x] 自定义任务 ID 支持

### 7.4 已创建的文件
- [x] `codinggirl/core/background_manager.py` (250+ 行) - BackgroundManager 核心
- [x] `codinggirl/core/background_tools.py` (180+ 行) - 后台任务工具
- [x] `tests/test_background_manager.py` (10 个测试全部通过)

### 7.5 测试覆盖
- [x] 启动后台任务并等待完成
- [x] 指定工作目录执行命令
- [x] 失败任务的错误处理
- [x] 完成通知队列机制
- [x] 列出所有任务
- [x] 获取统计信息
- [x] 清理已完成的任务
- [x] 大输出截断
- [x] 并发执行多个任务
- [x] 自定义任务 ID

### 7.6 典型场景
- [x] `npm install` 在后台运行，agent 继续编辑配置文件
- [x] `pytest` 在后台运行，agent 继续写代码
- [x] 多个独立任务并行执行（构建 + 测试 + 安装依赖）

**里程碑**：✅ Agent 能并行处理多个独立任务，长时间命令不阻塞主循环

### 7.2 自动通知
- [ ] 每轮 LLM 调用前，drain 完成队列
- [ ] 将完成通知注入 messages（agent 自动感知）

### 7.3 典型场景
- [ ] `npm install` 在后台运行，agent 继续编辑配置文件
- [ ] `pytest` 在后台运行，agent 继续写代码

**里程碑**：agent 能并行处理多个独立任务

---

## 阶段 8：Worktree 隔离（s12）

**目标**：多任务并行工作时避免文件冲突

### 8.1 实现 Worktree 管理
- [ ] 创建 `WorktreeManager` 类：管理 `.worktrees/` 目录
- [ ] 注册 `worktree_create` 工具：创建隔离工作区 + 绑定 task
- [ ] 注册 `worktree_remove` 工具：清理工作区（keep/remove 选项）
- [ ] 事件流：lifecycle 变更写入 `.worktrees/events.jsonl`

### 8.2 与 Task Graph 集成
- [ ] worktree_create 自动将 task 标记为 in_progress
- [ ] worktree_remove 可选标记 task 为 completed
- [ ] 每个 task 在独立 worktree 中执行，避免冲突

**里程碑**：多个 agent 能并行工作在不同分支，互不干扰

---

## 阶段 9：前后端打通与事件流（对应原 P3/P4）

### 9.1 后端事件流
- [ ] 实现 SSE/WebSocket 推送：tool_call/tool_result/todo_update/task_update
- [ ] Tauri event bridge：后端事件 → 前端监听
- [ ] 替换前端轮询为事件订阅

### 9.2 前端适配
- [ ] Workflow card 展示 todo 列表
- [ ] Trace panel 展示 subagent 调用层级
- [ ] Task graph 可视化面板
- [ ] Background tasks 监控面板
- [ ] Worktree 管理界面

### 9.3 Approval 流程
- [ ] 高风险工具（exec/write）触发 approval 事件
- [ ] 前端弹窗确认 → 后端继续执行
- [ ] 支持"记住此决策"（写入 policy）

---

## 阶段 10：索引与上下文注入（对应原 P2）

### 10.1 自动索引
- [ ] Agent loop 启动时检测索引是否存在/过期
- [ ] 自动调用 `index_build`（或提示用户）

### 10.2 智能上下文注入
- [ ] 在 system prompt 注入 repo map 摘要（top-level 结构）
- [ ] 工具调用前，自动查询相关 symbols/imports
- [ ] 搜索结果聚合：多个 hits → 批量读取 → 合并上下文

### 10.3 前端展示
- [ ] Repo Map 面板：可搜索、可跳转
- [ ] Imports 依赖图：可视化模块关系

---

## 实施优先级建议

### Phase 1（立即开始）- 建立核心循环
1. **阶段 1：Agent Loop**（2-3 天）← 最高优先级
2. **阶段 2：TodoWrite**（1-2 天）
3. 测试：完成一个多步任务（如"重构某模块"）

### Phase 2（核心能力）- 扩展与隔离
4. **阶段 3：Context Management**（2 天）
5. **阶段 4：Subagent**（2 天）
6. **阶段 7：Background Execution**（1-2 天）

### Phase 3（产品化）- 协调与可视化
7. **阶段 6：Task Graph**（2 天）
8. **阶段 8：Worktree Isolation**（2 天）
9. **阶段 9：前后端打通**（3-4 天）

### Phase 4（优化）- 智能化
10. **阶段 5：Skills**（1-2 天）
11. **阶段 10：索引注入**（2 天）

---

## 关键原则（来自教程）

1. **最小内核**：agent loop 是 `while stop_reason == "tool_use"` + message history，其他都是增量
2. **工具优先**：bash 只用于必要场景，专用工具更安全、更可控
3. **上下文即状态**：message history 是单一事实源，UI 是投影
4. **隔离与委托**：子任务用 subagent，并行任务用 worktree
5. **渐进式复杂度**：先跑通简单循环，再逐步加 todo/compact/task graph

---

## 保留的原有优势

- [x] 工具系统设计已经很好（registry/runner/hooks/validation）
- [x] 存储层已经支持 replay 和事件流
- [x] 前端 UI 框架已经完善
- [x] patch/edit 工具已经很健壮（dry-run/conflict/CRLF）

**下一步**：从阶段 1 开始，先建立 Agent Loop，其他能力逐步叠加。

---

## 附录：原有 TODO 保留项（待整合）

以下是原 TODO 中有价值但未在新架构中明确的项目：

### 工具层收尾
- [ ] 为常见失败提供自动 fallback（缩小 edit scope / replace_text fallback）
- [ ] session 级 checkpoint / restore（可回滚"本轮改过的文件集"）
- [ ] mutation 失败后的恢复策略与证据链

### 索引精度提升
- [ ] TS/JS symbols 精度升级（export/default/namespace/类型声明、line_end）
- [ ] repo map 查询"面向问题"的语义（更强组合、结果聚合与去重）
- [ ] imports 的"可解释视图"（入/出度、热点模块）

### 工程化
- [ ] 统一验证脚本：pytest + npm build + tauri/cargo test
- [ ] 关键 KPI：事件重放一致性、审批延迟、失败 TopN

这些项目将在对应阶段实施时整合进去。
