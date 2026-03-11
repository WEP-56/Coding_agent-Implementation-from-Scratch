## P0：先把日常 coding task 跑稳
这是必须马上做的，直接影响读取/修改成功率。
- P0.1 分段读取工具
  - 新增 fs_read_range 或升级 fs_read_file
  - 支持 start_line、end_line、offset/limit、max_lines
  - 返回 total_lines、truncated、encoding
  - 目标：解决大文件读不动、上下文太粗的问题
- P0.2 Scoped search
  - 升级 search_rg
  - 增加 path、include、exclude、literal、case_sensitive、context_before、context_after
  - 最好再补一个 glob 工具，别让 agent 用内容搜索替代文件发现
  - 目标：提升定位精度，减少无效扫描和 token 浪费
- P0.3 结构化编辑工具
  - 不要只靠 unified diff
  - 先加：
    - fs_replace_text
    - fs_insert_at_line
    - fs_write_file
  - replace_text 要支持 expected_occurrences / must_contain
  - 目标：让简单编辑不必先合成一段脆弱 patch
- P0.4 Tool 参数校验
  - 在 ToolRunner 层对 ToolSpec.input_schema 做真正验证
  - 目标：降低 handler 级报错和异常噪音，让 tool call 更稳定
这个阶段最值得直接参考：
- Codex 的 constrained patch 思路
- Gemini 的 read_many_files / scoped search / glob
- Claude 的“explore first, implement later”工作方式
## P1：降低 patch/edit 失败率
P0 做完后，下一步就是补“为什么修改还会失败”。
- P1.1 Harden unified diff applier
  - 显式兼容 diff --git、index、new file mode、deleted file mode、rename from/to
  - 增加 dry-run
  - 返回结构化冲突信息：哪个文件、哪个 hunk、期望上下文和实际上下文差异
- P1.2 保留原文件换行风格
  - 现在写回统一 LF，真实 Windows/CRLF 仓库容易制造脏 diff
  - 应该按原文件 newline style 写回
- P1.3 引入 backup + checkpoint
  - 不只是 patch backup
  - 要有 session 级 checkpoint，能回滚“这一步 agent 改过的文件”
  - 更接近 Gemini / Claude 的 rewind / restore 思路
- P1.4 失败恢复策略
  - patch 失败后，不要直接结束
  - 自动走 fallback：
    1. 重新 read context
    2. 缩小 edit scope
    3. 改用 replace_text
    4. 再失败才上报
  - 这是现代 coding agent 成功率高的关键差异之一
## P2：让工具层从“能跑”升级到“能导航真实仓库”
这一层才是从 MVP 到现代 coding agent 的跃迁。
- P2.1 文件发现与递归列举
  - 增加 fs_glob / fs_list_files
  - 支持 glob pattern、递归、metadata、ignore 规则
- P2.2 统一 ignore/trust 规则
  - 搜索、索引、读取、glob 应共享 ignore policy
  - 参考 Gemini trusted folders + policy layering 的思路
- P2.3 indexer 扩展到 TS/JS
  - 当前 symbols.py 基本只覆盖 Python AST
  - 至少补一版 JS/TS declaration extraction
  - 哪怕先用轻量 regex/tree-sitter-lite，也比没有强太多
- P2.4 query-oriented repo map
  - 不只是 flat ranking
  - 要支持按 symbol/path/kind/focus 查询
  - 返回 grouped results + ranges/snippets
- P2.5 多文件读取聚合
  - 类似 Gemini 的 read_many_files
  - 搜索 hit 后能一次性打包相关切片，而不是 agent 自己循环读十几次
## P3：进入 product-grade runtime
这层不是第一优先，但做完会非常接近 Codex/Claude/Gemini 的成熟度。
- P3.1 approvals 与 capabilities 解耦
  - 学 Codex
  - “技术上能不能做” 和 “需不需要审批” 分开建模
  - 比如 sandbox_mode 与 approval_policy 独立
- P3.2 hooks 体系
  - 学 Claude Code
  - 至少补：
    - PreToolUse
    - PostToolUse
    - PostToolUseFailure
    - TaskCompleted
  - 后续可挂自动 lint/test/format/审计
- P3.3 结构化 runtime events
  - 学 Codex / Gemini headless
  - 发出 tool_use、tool_result、turn.failed、patch.applied、verification.failed
  - 对 IDE UI、trace、replay 都很关键
- P3.4 memory/instruction layering
  - 学 Claude
  - CLAUDE.md / AGENTS.md 式的 instructions 分层
  - 项目级、用户级、本地级配置与记忆分离
- P3.5 MCP / external tools registry
  - 学 Gemini
  - built-in tools、custom tools、MCP tools 统一注册和调度
  - 不然以后工具一多，runtime 会散

# 三家能力对比，按重要性抽取
只看对你最有价值的部分：
- P0 级最值得抄
  - Codex: constrained patch、structured events、严格工具边界
  - Gemini: glob/read-many/scoped search、tool registry、checkpointing
  - Claude: plan/explore 模式、hooks、permissions grammar
- P1 级最值得抄
  - Codex: sandbox 和 approval 解耦、command policy
  - Gemini: trusted folder、shadow history rollback
  - Claude: session restore、subagent isolation、hook-based policy
- P2-P3 级最值得抄
  - Codex: resumability + SQLite state + hierarchical agents
  - Gemini: MCP lifecycle、schema normalization、dynamic tool refresh
  - Claude: skills/memory/hooks/subagents 的统一 runtime 观
## 建议项目的实际强化顺序
 8 步：
1. fs_read_range
2. search_rg scoped filters
3. fs_glob
4. fs_replace_text
5. patch dry-run + structured conflict output
6. newline preservation + tool schema validation
7. read_many_files + checkpoint/restore
8. TS/JS symbol indexing + query repo map
## 对应文件落点
第一轮改造主要会集中在这些文件：
- codinggirl/runtime/workspace.py
- codinggirl/runtime/tools/builtins_fs.py
- codinggirl/runtime/tools/builtins_search.py
- codinggirl/runtime/tools/builtins_patch.py
- codinggirl/runtime/tools/runner.py
- codinggirl/runtime/defaults.py
- codinggirl/runtime/indexer/symbols.py
- codinggirl/runtime/indexer/repo_map.py


# 总览：
1. 落地 P0：fs_read_range + scoped search + fs_glob + fs_replace_text
2.  P1：patch dry-run、冲突结构化、newline preservation、schema validation
3.  P2：indexer 和 repo-map 强化

## 本仓库已落地（截至 2026-03-11）
- P0.4：ToolRunner 边界参数校验（`codinggirl/runtime/tools/schema_validation.py` + `codinggirl/runtime/tools/runner.py`）
- P0.1：`fs_read_range` 支持大文件分段读取（`codinggirl/runtime/workspace.py` 的 `read_text_range` 不再依赖 `read_text` 的 512KB 上限）
- P1.2：写回保留原文件换行风格（CRLF/LF）（`codinggirl/runtime/workspace.py` 的 `write_text`）
- P1.1（部分）：`patch_apply_unified_diff` 支持 `dry_run`，并在冲突时返回结构化 `conflict`（`codinggirl/runtime/tools/builtins_patch.py` + `codinggirl/runtime/defaults.py`）
- P1.1（部分）：`patch_apply_unified_diff` 兼容 git 风格 diff 头（`diff --git` / `index` / `rename from/to` 等），并支持 rename-only patch（`codinggirl/runtime/tools/builtins_patch.py`）
- P0.3（部分）：新增 `fs_write_file` / `fs_insert_at_line`（`codinggirl/runtime/tools/builtins_fs.py` + `codinggirl/runtime/defaults.py`），并在 workspace 层提供流式插入实现（`codinggirl/runtime/workspace.py`）
- P2.5：新增 `fs_read_many_files`，支持一次性读取多文件/多切片（含大文件范围读取与总输出上限）（`codinggirl/runtime/tools/builtins_fs.py` + `codinggirl/runtime/defaults.py`）
