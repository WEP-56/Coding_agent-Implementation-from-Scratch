这是一个轻量的、模型无关的、可长期维护的 Coding Agent 架构。

---

# 零、可行性评估（现状 / 风险 / 更优技术选型）



## 0.1 可行性结论（简版）

- **可行**：核心 Agent Runtime + Tools + Repo Map + Diff Editing 可以在 1~3 周做出可用 MVP（单人），后续逐步加强。
- **最大风险**不在模型，而在 **执行安全 / 可复现 / 索引质量 / 工具协议稳定性**。
- **更优落地策略**：先做“可复现的工具执行 + 结构化索引（tree-sitter）+ 小步补丁编辑（unified diff）”，向量库/复杂多代理/Live2D 可后置。

## 0.2 技术选型建议（更优解）

### 语言与运行时

- **核心 Runtime 推荐：Python 3.11+**
  - 生态：tree-sitter、git 操作、CLI、HTTP/WebSocket、SQLite、测试工具成熟。
  - 工程目标：核心“Agent OS”尽量小、易调试、易分发。
- UI（桌面 + Live2D）建议与核心解耦：
  - **核心作为本地服务（HTTP/WebSocket）**，UI/Telegram/CLI 都是“前端适配器”。
  - 桌面端：**Tauri** 优先（体积小、资源占用更低）；若 Live2D SDK/生态强依赖 Web/Node，则 Electron 也可。

### Tool 调用协议（模型无关 + 可测试）

- 内部协议统一为：
  - `Action`（意图）/ `ToolCall`（可执行）/ `Observation`（结果）/ `Artifact`（产物）
  - 全部 **JSON 可序列化**，可落盘，支持回放（replay）。
- 对外（模型层）优先兼容 **OpenAI-compatible tools(JSON Schema)**：
  - 这让你可以接 OpenAI/DeepSeek/Qwen/多数兼容网关。
- **预留 MCP（Model Context Protocol）适配层**：
  - MCP 适合做“外部工具生态/插件化”，但 MVP 阶段可先不引入复杂度；先把内部 Tool Registry 做扎实。

### Repo Index / Repo Map（优先 tree-sitter，向量后置）

- 参考 Aider 的 Repo Map 思路：
  - 维护一个“仓库全局符号地图”，每次请求把有限 token 的“关键符号与签名”塞给模型。
  - Aider 公开文档：Repo map 与 tree-sitter 构建方法（见：https://aider.chat/docs/repomap.html 和 https://aider.chat/2023/10/22/repomap.html）。

> Aider 还会对 Repo Map 做“token 预算内的裁剪”，通过依赖图排序/重要性筛选，将最相关的符号优先提供给模型。
> 见：https://aider.chat/docs/repomap.html（Optimizing the map）
- 分阶段：
  1) 文件树 + ripgrep（关键字/路径）
  2) tree-sitter 符号索引（函数/类/方法/导入）+ 引用计数（重要性排序）
  3) 可选：Embedding 向量检索（在“定位失败率”成为瓶颈后再加）

### Diff Editing（统一 diff，强约束输出）

- 统一使用 **unified diff** 作为“编辑指令语言”，并在工具侧严格校验：
  - patch 可应用、上下文匹配、变更范围可控。
  - 失败可回滚，且能生成失败原因反馈给模型。

### 安全与可复现（必须前置）

- 工具执行必须具备：
  - 工作目录沙箱（workspace root）
  - 路径 allowlist / denylist（禁止系统路径、凭证文件）
  - 命令 allowlist（MVP 至少限制 rm/format disk 级别危险命令）
  - 超时、输出截断、日志落盘
- 每一次 ToolCall 与输出都写入 SQLite：这是 debug 与长期维护的生命线。

---

# 一、系统目标

此 Coding Agent 要实现这些能力：

### 核心能力

* 自动阅读代码仓库
* 修改代码
* 运行命令 / 测试
* 自动修复 bug
* 生成 PR

### 边界与非目标（MVP 必须明确）

**系统边界**（本项目负责）：

- 从自然语言任务 → 形成可执行计划（Plan）
- 读取/检索仓库上下文 → 生成小步可审计变更（PatchSet）
- 在受控工具与沙箱内验证（测试/构建/静态检查）
- 应用或回滚变更，并生成可追溯日志与工件（Artifacts）

**非目标**（MVP 阶段不做，避免拖慢闭环）：

- 不做无人值守的全权限 Shell（默认禁用危险命令）
- 不做“必须依赖向量数据库”的索引（embedding 后置）
- 不把 Live2D 作为核心依赖（UI 故障不影响 Core）

### 交互方式

* 桌面 UI + Live2D（tauri或electron）
* Telegram Bot
* CLI

### AI能力

* 多模型支持
* Tool use
* Repo indexing
* 多 Agent 协作

---

# 二、整体系统架构

完整架构：

```
                        ┌───────────────────┐
                        │      Telegram     │
                        │       Bot         │
                        └─────────┬─────────┘
                                  │
                                  │
                     ┌────────────▼────────────┐
                     │      API Gateway        │
                     │  (HTTP / WebSocket)     │
                     └────────────┬────────────┘
                                  │
                     ┌────────────▼────────────┐
                     │      Agent Runtime      │
                     │                         │
                     │ Planner Agent           │
                     │ Coding Agent            │
                     │ Review Agent            │
                     │ Tool Executor           │
                     │ Memory Manager          │
                     └────────────┬────────────┘
                                  │
       ┌──────────────────────────┼─────────────────────────┐
       │                          │                         │
       ▼                          ▼                         ▼

 Repo Indexer             Tool System              Avatar Controller
 (Code Search)            (System Actions)         (Live2D UI)

       │                          │                         │
       ▼                          ▼                         ▼

  Vector DB                Shell / Git / FS           Live2D Model

                                  │
                                  ▼
                         LLM Provider Layer
              (OpenAI / Claude / Qwen / DeepSeek)
```

补充说明（落地推荐）：

- **入口（Adapters）**：只负责接入与会话管理（CLI/Telegram/Desktop/Live2D），不包含决策逻辑。
- **核心（Core）**：只负责决策与状态机（Plan/Patch/Review），不直接执行 IO。
- **基础设施（Runtime）**：负责 repo/workspace、索引、补丁应用、工具执行、安全策略、持久化。

这样能避免“UI/集成层”拖慢核心闭环，也更容易做到：先 CLI MVP → 再接 Telegram → 最后桌面与 Live2D。

---

# 三、核心模块设计

系统可以拆成 **7个核心模块**：

```
core/
 ├ agent_runtime
 ├ planner
 ├ tools
 ├ repo_index
 ├ memory
 ├ llm_adapter
 └ event_bus
```

> 更推荐的落地方式是“**分层 + 单向依赖**”（Adapters → Core → Runtime）。
> 原先 7 模块可视为概念分类，但代码结构建议按职责分层，以减少耦合并降低 UI/集成对核心闭环的干扰。

---

# 三点必须前置的工程契约（否则会很难调试）

## 1) 数据契约（Contracts）

“模型无关”不是口号，必须落到 **统一 JSON 可序列化的数据契约**。

最少定义以下对象（建议全部可落盘，便于回放/replay）：

- `Task`：一次用户任务的唯一标识与元数据（repo_root、权限、入口来源等）
- `Plan`：步骤列表 + 退出条件（exit criteria）
- `PatchSet`：唯一允许写入代码的方式（建议 unified diff）
- `ToolCall` / `ToolResult`：工具调用与结果（包含超时、风险等级、工件路径）
- `Artifact`：Plan/Patch/Review/Logs/IndexSnapshot 等产物定位（URI）

## 2) 任务生命周期（State Machine）

建议最小状态机（可重试点清晰）：

`NEW → PLANNED → PATCHED → VERIFIED → APPLIED → DONE`

异常分支：

- `PATCH_FAILED`（补丁不可应用/冲突）
- `VERIFY_FAILED`（测试/构建失败）
- `ABORTED`（策略拒绝或用户取消）

## 3) 可复现与审计（Event Log + Tool Trace）

每次 ToolCall 的输入/输出必须落盘（SQLite），并写入 append-only 的事件日志（Event Log）。

这让你具备：

- 崩溃恢复（从事件恢复任务进度）
- 重放（replay：不再真正执行工具，而是读取历史 ToolResult）
- 调试（定位是哪一步/哪个工具输出导致失败）

---

# 四、Agent Runtime（大脑）

Agent Runtime 是系统核心。

职责：

```
用户请求
  ↓
Planner
  ↓
Task拆分
  ↓
调用Coding Agent
  ↓
执行Tools
  ↓
返回结果
```

核心循环：

```python
while True:

    plan = planner.plan(task)

    action = coding_agent.step(plan)

    if action.type == "tool":
        result = tool_executor.run(action)

    elif action.type == "finish":
        return action.output
```

这个循环就是 **Agent OS**。

---

# 五、多 Agent 协作（生产级关键）

生产级 Coding Agent 通常不是一个 Agent。

而是：

```
Planner Agent
     ↓
Coding Agent
     ↓
Review Agent
```

### Planner

负责：

```
理解任务
拆分步骤
```

示例：

```
任务:
修复登录bug

Plan:
1 阅读 auth.py
2 找出错误
3 修改逻辑
4 运行测试
```

---

### Coding Agent

负责：

```
读取代码
修改代码
运行命令
```

---

### Review Agent

负责：

```
代码质量检查
发现新bug
```

很多 AI IDE 都用这个结构。

---

# 六、Repo Index（代码理解核心）

Coding Agent 必须有 **代码索引系统**。

> 建议采用“分层索引”，先保证稳定可用，再逐步增强：
>
> 1) 文件树 + ripgrep（关键词/路径）
> 2) tree-sitter 符号索引 → 生成 Repo Map（关键符号与签名）
> 3) 可选：Embedding（在定位失败率成为瓶颈后再加）
>
> 业界可参考：Aider 的 repo map（使用 tree-sitter 抽取符号，并做 token 预算与重要性筛选）：
> - https://aider.chat/docs/repomap.html
> - https://aider.chat/2023/10/22/repomap.html

结构（建议落地的数据结构，不强依赖向量库）：

```
repo_index/
 ├ manifest.json       # 文件清单（path/lang/size/mtime/hash）
 ├ symbols.sqlite      # 符号表（name/kind/file/range/signature）
 ├ repo_map.txt        # 供模型读取的“全仓库摘要地图”（可按 token 预算裁剪）
 └ embeddings.sqlite   # 可选：chunk → embedding
```

实现：

### 1 文件索引

```
repo/
  src/
  tests/
  docs/
```

生成：

```
project_tree.json

也建议额外生成 `manifest.json`（便于增量更新与缓存失效）。
```

---

### 2 代码符号

解析：

```
class
function
imports

实现建议：优先使用 tree-sitter（多语言一致性更好），并在需要“语义精度”的语言上 **可选接入 LSP**。
```

例如：

```
Auth.login()
Auth.logout()
```

---

### 3 向量搜索

使用（可选，后置）：

```
embedding

是否启用 embedding 建议采用 feature flag（例如 env 开关），避免把向量库变成 MVP 阶段的硬依赖。
```

搜索：

```
login logic
```

返回：

```
auth.py:123
```

---

# 七、Tool System（系统操作）

Coding Agent 的能力来自 Tools。

## 工具安全与用户授权（必须写进系统）

工具系统天生涉及“任意数据访问与代码执行”，必须前置安全设计：

- 明确用户授权（用户应能审阅并授权每次工具调用）
- 数据隐私（共享哪些资源、共享给谁）
- 工具安全（把工具描述当作不可信输入，除非来自可信源）

MCP 规范给出了清晰的安全与信任建议，可作为落地参考：

- MCP Specification — Security and Trust & Safety：https://modelcontextprotocol.io/specification/2025-11-25

> 工具系统是“生产级可用”的关键，MVP 阶段建议遵守：
>
> - **默认拒绝（deny by default）**：没有明确 allowlist 的工具/命令不允许执行
> - **路径沙箱（workspace root）**：所有 FS 操作必须在 repo_root 下，禁止符号链接逃逸
> - **结构化输入/输出**：ToolCall/ToolResult 必须可序列化并落盘
> - **审计与回放**：每次调用记录输入/输出，用于 debug 与 replay

工具系统结构：

```
tools/
 ├ filesystem
 ├ code_edit
 ├ git
 ├ shell
 └ web
```

---

## File tools

```
read_file
write_file
list_dir
search_code
```

---

## Code edit tools

关键工具：

```
apply_patch
replace_block
insert_code
delete_code
```

---

## Git tools

```
git_diff
git_commit
git_branch
```

---

## Shell tools

```
run_shell
install_package
run_tests

建议把 `run_shell` 按风险拆分：

- `run_command_safe`：仅允许 allowlist 命令（例如 `pytest`, `npm test`, `go test`）
- `run_command_dangerous`：需要显式用户确认/策略许可（并带更严格的日志与超时）
```

---

# 八、Repo Edit Workflow（Cursor核心逻辑）

修改代码流程：

```
用户任务
   ↓
Planner
   ↓
读取相关文件
   ↓
生成Patch
   ↓
apply_patch
   ↓
运行测试
   ↓
修复错误
```

类似：

```
Cursor diff edit
```

---

# 九、Memory系统

Agent需要三层记忆：

### 1 Conversation Memory

```
chat history
```

---

### 2 Task Memory

保存：

```
当前任务步骤
```

---

### 3 Knowledge Memory

保存：

```
用户习惯
项目结构
```

可以用：

```
SQLite

---

## 建议的“可复现记忆”落地方式（强烈推荐）

仅仅把“记忆”理解为对话摘要会让系统非常难 debug。更稳妥的方式是引入 **事件日志（Event Log）+ 工具调用追踪（Tool Trace）**：

- 将每次 ToolCall 的输入/输出写入 SQLite（可回放、可审计）
- 将每轮决策/阶段变化写入 append-only Event Log（可恢复、可追责）

这一思路类似 Temporal 的 Event History（append-only 事件日志，用于恢复与审计），并可在事件过长时用 Continue-As-New 思路切分执行链：

- Event History：append-only 日志，支持恢复与调试：https://docs.temporal.io/workflow-execution/event
- Continue-As-New：checkpoint 状态并启动新执行链，避免历史过大：https://docs.temporal.io/workflow-execution/continue-as-new

### SQLite 最小表（建议）

```sql
CREATE TABLE run (
  run_id TEXT PRIMARY KEY,
  parent_run_id TEXT,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL,
  metadata_json TEXT
);

CREATE TABLE step (
  step_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  inputs_json TEXT,
  outputs_json TEXT,
  started_at TEXT,
  completed_at TEXT,
  error_json TEXT
);

CREATE TABLE tool_call (
  call_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  step_id TEXT,
  tool_name TEXT NOT NULL,
  input_json TEXT NOT NULL,
  output_json TEXT,
  status TEXT NOT NULL,
  error_json TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE event (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  step_id TEXT,
  kind TEXT NOT NULL,
  ts TEXT NOT NULL,
  payload_json TEXT
);
```

> 目标：任何一次失败都能回答“哪一步、调用了什么工具、输入输出是什么、为什么失败、如何重试”。
```

---

# 十、LLM Adapter（模型无关）

设计统一接口：

```
llm/
 ├ openai
 ├ anthropic
 ├ qwen
 └ deepseek
```

统一调用：

```
llm.chat(messages,tools)
```

推荐策略：

1) **推理层（Model API）**：优先支持 OpenAI-compatible API（便于接 OpenAI / DeepSeek / Qwen / 本地网关等）。
2) **工具层（Tool calling）**：内部统一 JSON Schema（函数参数），再做 provider 适配。
3) **工具传输层（可选）**：预留 MCP（Model Context Protocol）作为“外部工具/插件”的标准协议。

参考资料：

- OpenAI Function/Tool calling（JSON Schema + tool call/output 流程）：https://developers.openai.com/api/docs/guides/function-calling/
- Anthropic Programmatic tool calling（工具可在 code execution 容器内被程序化调用）：https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling
- MCP 规范（JSON-RPC + 工具/资源/提示词 + 安全与用户授权原则）：https://modelcontextprotocol.io/specification/2025-11-25

> 注意：所谓“OpenAI compatible API”主要解决的是 **模型推理接口兼容**；
> 工具系统的“安全、审计、回放、权限”需要在你的 ToolRunner/Policy 层实现，不能指望兼容 API 自动解决。

---

# 十一、Live2D UI（简化版）

你只需要一个 **Avatar Controller**。

结构：

```
avatar/
 └ live2d_controller.py
```

功能：

```
emotion
idle animation
text bubble
```

Agent 回复时：

```
avatar.set_emotion("happy")
avatar.show_text(reply)
```

Live2D只负责：

```
视觉反馈
```

不参与 AI逻辑。

---

# 十二、Telegram 接口

Telegram 只作为输入渠道。

结构：

```
integrations/
 └ telegram_bot.py
```

流程：

```
Telegram Message
       ↓
Agent Runtime
       ↓
Reply
```

---

# 十三、事件系统（生产级关键）

生产级系统需要 **Event Bus**。

例如：

```
events/
 ├ message
 ├ tool_call
 ├ task_start
 └ task_finish
```

作用：

```
解耦系统模块
```

例如：

```
task_finish
   ↓
avatar animation
```

---

# 十四、项目完整结构

完整目录建议：

```
coding-agent/

core/
 ├ agent_runtime
 ├ planner
 ├ coding_agent
 ├ review_agent

repo_index/
 ├ indexer
 ├ embeddings
 ├ symbol_parser

tools/
 ├ filesystem
 ├ code_edit
 ├ git
 ├ shell

memory/
 ├ conversation
 ├ task
 ├ knowledge

llm/
 ├ adapter
 └ providers

integrations/
 ├ telegram
 └ cli

avatar/
 └ live2d

api/
 └ server

main.py
```

总代码规模：

```
core runtime     800 lines
tools            600 lines
repo index       500 lines
integrations     200 lines
avatar           100 lines
```

总计：

**≈ 2200 行核心代码**

属于：

```
轻量生产级
```

---

# 十五、未来可升级方向

系统成熟后可以加：

### 自动 PR

```
git push
create pull request
```

---

### 多模型协作

```
planner → Claude
coder → DeepSeek
review → GPT
```

---

### 自我学习

保存：

```
bug patterns
fix history
```

---

# 十六、最终形态

你的项目会变成：

```
Live2D Coding Agent
```

功能：

```
AI写代码
AI改项目
Telegram远程控制
Live2D桌面助手
```

相当于：

```
Cursor
+
Claude Desktop
+
VTuber assistant
```

---

三个较为关键的东西：

1️⃣ **Repo Map（代码理解核心算法）**
2️⃣ **Diff Editing（AI改代码正确率暴涨）**
3️⃣ **Task Graph（复杂任务自动拆解）**

这三个技术其实决定了：

> AI 是写玩具代码，还是能维护整个项目。

## 详解

这三个东西其实是**AI 编程系统能不能从“玩具”升级成“工程工具”的分水岭**。很多项目只做到了“让模型写点代码”，但真正像 Cursor、OpenHands 这种能维护大型项目的工具，都会实现这三层能力。

我给你拆开讲，并且顺便告诉你 **怎么在你的 Coding Agent 里落地实现**。

---

# 1️⃣ Repo Map（代码理解核心算法）

## 为什么需要 Repo Map

LLM 最大问题是：

**上下文太小。**

假设你的项目：

```
500 files
100k lines
```

模型不可能全部读完。

如果只是简单做：

```
search_code
read_file
```

Agent 会出现：

* 找错文件
* 不知道函数在哪
* 重复读很多代码

所以真正的 coding agent 都会先构建：

**Repo Map**

---

## Repo Map 是什么

Repo Map 本质是：

```
项目结构图 + 代码符号索引
```

例如：

```
project
 ├ api
 │   └ auth.py
 │        login()
 │        logout()
 │
 ├ db
 │   └ user.py
 │        UserModel
```

Agent 就能快速知道：

```
login logic → auth.py
user data → user.py
```

---

## Repo Map 数据结构

建议结构：

```
repo_map/
  files.json
  symbols.json
  imports.json
```

### files.json

```
{
 "auth.py": {
  "functions": ["login","logout"],
  "classes": []
 }
}
```

---

### symbols.json

```
{
 "login": "auth.py:20",
 "UserModel": "user.py:5"
}
```

---

### imports.json

```
{
 "auth.py": ["user.py"]
}
```

这样 Agent 可以：

```
login
 ↓
auth.py
 ↓
UserModel
 ↓
user.py
```

---

## Repo Map 构建算法

实现其实很简单：

### Step1 扫描文件

```
glob repo/**/*.py
```

---

### Step2 AST解析

Python：

```
ast.parse()
```

提取：

```
FunctionDef
ClassDef
Import
```

---

### Step3 构建索引

```
symbol → file
file → symbols
```

---

## Repo Map 在 Agent 中的作用

当用户说：

```
修复登录bug
```

Agent流程：

```
search symbol "login"
 ↓
auth.py
 ↓
read_file(auth.py)
```

效率会高很多。

---

# 2️⃣ Diff Editing（AI改代码正确率暴涨）

## 为什么不能直接写文件

很多新手做 Agent 会这样：

```
read_file
LLM rewrite file
write_file
```

问题：

* 容易破坏其他代码
* diff巨大
* git冲突
* LLM容易漏代码

正确方法是：

**Diff Editing**

---

## Diff Editing 是什么

AI只生成：

```
patch
```

类似 git diff。

示例：

```
--- auth.py
+++ auth.py

@@
 def login(user):
-   if user.passwd == input:
+   if hash(user.passwd) == input:
```

这样：

* 只改一小段
* 不影响其他代码

---

## Diff Editing Workflow

```
read_file
 ↓
LLM生成patch
 ↓
apply_patch
 ↓
验证
```

---

## Patch 应用算法

可以自己写：

```
apply_patch(file, patch)
```

逻辑：

```
定位diff行
替换代码
写回文件
```

也可以用：

```
unidiff
```

---

## Cursor 的做法

Cursor其实就是：

```
Diff editing
+
AST verify
```

先生成 patch，再检查语法。

---

## 为什么 Diff Editing 成功率更高

原因：

```
LLM上下文更小
改动更明确
失败可回滚
```

成功率通常：

```
rewrite file: 30%
diff edit: 70%+
```

---

# 3️⃣ Task Graph（复杂任务自动拆解）

## 为什么需要 Task Graph

很多用户会说：

```
给项目加一个登录系统
```

如果 Agent 直接写代码：

基本会失败。

因为这个任务其实是：

```
设计数据库
写接口
写验证逻辑
写前端
写测试
```

所以需要：

**Task Graph**

---

## Task Graph 是什么

任务拆成：

```
Graph
```

例如：

```
Add Login System

  │
  ├─ Create UserModel
  │
  ├─ Create AuthAPI
  │
  ├─ Add password hash
  │
  └─ Add tests
```

Agent 按顺序执行。

---

## Task Graph 数据结构

建议结构：

```
tasks = [
 {id:1, action:"create file user.py"},
 {id:2, action:"add login function"},
 {id:3, action:"write tests"}
]
```

---

## Task Graph 生成

由 Planner Agent 完成。

Prompt：

```
Break the task into steps.
Each step must be atomic.
```

示例输出：

```
1 find auth module
2 add login function
3 add password hash
4 run tests
```

---

## Task Graph 执行

Runtime：

```
for task in tasks:

    result = coding_agent(task)

    if fail:
        retry
```

---

## 进阶：动态 Task Graph

更高级的是：

```
执行
 ↓
发现新任务
 ↓
插入Graph
```

例如：

```
run tests
 ↓
发现bug
 ↓
新增task: fix bug
```

---

# 三者组合效果

真正的 Coding Agent workflow：

```
User task
   ↓
Task Graph
   ↓
Repo Map search
   ↓
Diff edit
   ↓
Run tests
   ↓
Fix bugs
```

整体流程：

```
Plan → Locate → Patch → Verify
```

---

# 在你的 Agent 中实现（推荐）

我建议你实现一个轻量版：

### Repo Map

```
≈ 200 行
```

### Diff Editing

```
≈ 150 行
```

### Task Graph

```
≈ 200 行
```

总代码：

```
≈ 550 行
```

但效果会比普通 Agent 强很多。

---

# 最后一个非常重要的建议

Coding Agent 的真正能力排序其实是：

```
1 Repo Map
2 Diff Editing
3 Task Graph
4 模型能力
```

很多人以为：

```
模型 > 一切
```

其实在工程系统里：

**结构 > 模型。**

---


