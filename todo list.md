# CodingGirl Coding Agent — Implementation TODO List (Phased)

> 目标：从 0 实现一个“轻量、模型无关、可长期维护”的 Coding Agent Core，并逐步接入 CLI → Telegram → Desktop/Live2D。
> 当前工作区只有设计文档（`project-CodingGirl.md`），因此计划按 Greenfield 执行。

---

## Phase 0 — 工程骨架与硬约束（先把地基打牢）

### 0.1 建仓与工程结构
- [ ] 创建目录结构（建议）：
  - `core/`（纯逻辑）
  - `runtime/`（IO：workspace/indexer/patch/tools/storage）
  - `adapters/cli/`
  - `docs/`（可选）
- [ ] 初始化 Python 项目（Python 3.11+）：`pyproject.toml` + 依赖管理（uv/poetry/pip 均可）
- [ ] 约定运行入口：`python -m codinggirl` 或 `python main.py`

### 0.2 数据契约（Contracts）先行（模型无关的落点）
- [ ] 定义数据结构（建议用 `dataclasses` / `pydantic` 二选一）：
  - `Task`（goal/repo_root/mode/adapter/session_id）
  - `Plan`（steps/assumptions/exit_criteria）
  - `PatchSet`（unified diff + files[]）
  - `ToolCall` / `ToolResult`（timeout/risk_level/artifacts/stdout/stderr）
  - `ArtifactRef`（uri/type/hash）
- [ ] 所有对象必须 JSON 可序列化（落盘与 replay 的基础）

### 0.3 Storage（SQLite）与可复现日志
- [ ] 建立 SQLite schema：`run/step/tool_call/event`（参考文档的最小表）
- [ ] 实现 `EventLog.append()` 与 `ToolCallRecorder`（记录输入/输出/错误）
- [ ] 实现“replay 模式”开关：
  - replay 时禁止真实执行工具，只从历史 `tool_call` 输出读取

**验收（Phase 0）**
- [ ] 能启动一个空 run，并写入 event/tool_call 记录到 SQLite
- [ ] 断进程重启后能从 SQLite 恢复 run 基本信息（至少能继续打印进度）

---

## Phase 1 — Runtime 基础设施（Workspace / Tools / Patch）

### 1.1 RepoWorkspace（路径沙箱）
- [ ] 实现 `RepoWorkspace(root)`：
  - 路径 canonicalize（realpath）
  - deny `..`/符号链接逃逸
  - 统一文本读取（编码/换行兼容）

### 1.2 Tools（最小工具集 + 安全策略）
- [ ] Tool Registry：工具名 → handler（含 JSON schema）
- [ ] 实现最小只读工具：
  - `fs_list_dir`
  - `fs_read_file`
  - `search_rg`（优先调用 `rg`，没有则 fallback）
- [ ] 实现写入工具（仍受控）：
  - `patch_apply_unified_diff`（唯一写入方式）
- [ ] ToolRunner 安全门禁：
  - allowlist/denylist
  - timeout
  - 输出截断
  - 风险等级（low/medium/high）

### 1.3 PatchEngine（unified diff）
- [ ] 选择 patch 应用策略：
  - MVP：fail-on-conflict（遇到上下文不匹配直接失败）
- [ ] Patch 校验：
  - 文件存在性
  - 最大变更行数
  - 禁止敏感文件（.env/密钥）
- [ ] Patch 应用失败必须可解释（输出“失败原因”给模型/用户）
- [ ] 支持回滚：
  - 应用前读取原内容并作为 artifact 保存（或 git worktree/临时副本）

**验收（Phase 1）**
- [ ] 在一个小仓库中：能读取文件、rg 搜索、并应用一个简单 patch（添加/修改 5~20 行）
- [ ] Patch 不可应用时能输出清晰的失败原因（上下文不匹配/文件不存在/触及敏感文件等）

---

## Phase 2 — Repo Index / Repo Map（先 tree-sitter，embedding 后置）

### 2.1 文件清单（manifest）
- [ ] 扫描 repo 生成 `manifest.json`：path/lang/size/mtime/hash
- [ ] 增量更新策略（基于 mtime/hash）

### 2.2 tree-sitter 符号索引
- [ ] 选型：
  - Python：`tree-sitter` + `tree_sitter_languages`（类似 Aider 的路线）
- [ ] 抽取符号：function/class/method/import
- [ ] 存储到 `symbols.sqlite`

### 2.3 Repo Map 生成（token 预算）
- [ ] 生成 `repo_map.txt`（按重要性排序，控制最大 token）
- [ ] 重要性排序：
  - MVP：基于引用计数/导入关系的简单 ranking

**验收（Phase 2）**
- [ ] 给定一个中等规模 repo：能生成 `repo_map.txt` 且内容包含关键符号与签名
- [ ] 对同一个 repo，repo_map 在小改动后可增量更新（不必全量重建）

---

## Phase 3 — Core：Planner/Coder/Reviewer 回路 + 状态机

### 3.1 Orchestrator（Agent OS）
- [ ] 实现状态机：`NEW → PLANNED → PATCHED → VERIFIED → APPLIED → DONE` + 异常分支
- [ ] 每个状态迁移都写 event log

### 3.2 Planner
- [ ] 输入：用户任务 + repo_map
- [ ] 输出：Plan（原子步骤、每步预期工具/文件、exit criteria）

### 3.3 Coder
- [ ] 输入：Plan step + 必要文件片段
- [ ] 输出：PatchSet（unified diff）或 ToolCall（如需要读取更多上下文）

### 3.4 Reviewer
- [ ] 对 PatchSet 做静态审查：
  - 变更范围/风险
  - 是否可能引入 bug
  - 是否触及敏感文件
- [ ] 产出 Review 结论（artifact）

**验收（Phase 3）**
- [ ] 端到端：用户提出一个小需求（例如改一处字符串/修一处逻辑），系统能生成 patch → 校验 → 应用 → 记录完整 trace

---

## Phase 4 — LLM Adapter（多模型）

### 4.1 OpenAI-compatible 模型接入
- [ ] 统一 client：
  - 支持 messages
  - 支持 tools(JSON Schema)
  - 支持 tool call outputs
- [ ] 失败处理：
  - 超时/限流重试策略
  - 输出格式不合法时的修复回合

### 4.2 适配 Anthropic（可选）
- [ ] 将 Tool schema 映射到 `input_schema`
- [ ] 支持 `tool_use_id` / `tool_result`
- [ ] 可选支持 programmatic tool calling（后置：需要 code execution 容器能力）

**验收（Phase 4）**
- [ ] 同一套内部 Contracts + ToolRunner，能切换至少 2 个 provider 跑通 Phase 3 的端到端流程

---

## Phase 5 — Adapters：CLI → Telegram → Desktop/Live2D

### 5.1 CLI Adapter（先做）
- [ ] 命令：
  - `codinggirl run --repo <path> --goal "..."`
- [ ] 输出：
  - Plan、Patch diff、验证结果
  - artifacts 路径

### 5.2 Telegram Adapter
- [ ] chat_id → run/workspace 隔离
- [ ] 权限策略（默认只读；显式授权写入/执行）

### 5.3 Desktop + Live2D（最后接）
- [ ] Desktop 只做可视化：任务列表、diff 预览、按钮式 apply/rollback/run tests
- [ ] Live2D 只绑定状态（idle/thinking/error），不进入 Core 依赖链

**验收（Phase 5）**
- [ ] 同一 Core/Runtime，能被 CLI 与 Telegram 两种入口驱动（Desktop 后置）

---

## Phase 6 — 质量与发布（持续）

- [ ] 单元测试：PatchEngine、Workspace sandbox、ToolRunner allowlist
- [ ] 回归测试：端到端 golden traces（固定输入 + replay）
- [ ] 文档：更新 `project-CodingGirl.md` 与运行指南
- [ ] 安全：默认禁用危险工具；敏感文件检测

---

## 开始实现的推荐顺序（最短路径）

1) Contracts + SQLite Trace（可复现）
2) Workspace + fs tools + rg search
3) PatchEngine（unified diff）
4) CLI Adapter（打通闭环）
5) Repo Map（tree-sitter）
6) Planner/Coder/Reviewer 完整回路
7) Telegram → Desktop/Live2D
