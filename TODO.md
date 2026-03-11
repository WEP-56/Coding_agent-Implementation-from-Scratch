# TODO（对齐：深度调研-实用性跃迁.md / tools强化.md）

更新时间：2026-03-11  
目标：把“已落地/进行中/待做”收敛到一份清单，避免后续任务安排混乱。

标记说明：`[x]` 已完成 / `[~]` 已部分完成 / `[ ]` 待办

---

## 0) 现状快照（关键能力）

- [x] 工具边界参数校验（tool input_schema 验证 + 更少 handler 异常噪音）
- [x] 大文件分段读取（fs_read_range 不再被 512KB 上限卡死）
- [x] scoped search / glob / list_files / read_many_files（仓库导航与批量读取可用）
- [x] patch dry-run + 冲突结构化输出 + git diff 头兼容 + rename-only
- [x] 换行风格保留（CRLF/LF）贯通 write/replace/insert/patch
- [x] symbols 索引扩展到 TS/JS（轻量 regex 版）
- [x] index_build / index_query_repo_map / index_query_imports（索引生成与查询闭环）
- [x] ToolRunner：hooks 骨架 + replay_only 可重放（含失败）+ capability gating（read/write/exec）+ cmd_run(exec)

---

## 1) P0（跑稳）剩余收尾

### 1.1 工具层“读/搜/改”闭环
- [x] fs_read_range / search_rg / fs_glob / fs_replace_text / fs_insert_at_line / fs_write_file
- [~] 工具统一的 “read-many → edit → verify” 最小范式（当前工具已齐，但 orchestrator 仍偏单路径）
- [ ] 为常见失败提供自动 fallback（缩小 edit scope / replace_text fallback / 再失败才上报）

### 1.2 失败可恢复边界（P1.3/P1.4 也依赖）
- [ ] session 级 checkpoint / restore（可回滚“本轮改过的文件集”）
- [ ] mutation 失败后的恢复策略与证据链（失败原因结构化 + 可行动提示）

---

## 2) P1（降低 patch/edit 失败率）剩余收尾

- [~] patch applier 的冲突信息补全（当前已结构化 expected/actual，但缺“上下文片段差异/更精细分类”）
- [x] newline preservation（已做）
- [ ] patch dry-run + structured conflict 输出的“稳定格式约定”（供 UI/日志/回放一致消费）

---

## 3) P2（导航真实仓库）收尾项

### 3.1 ignore/trust 分层（当前只做了 ignore）
- [~] ignore：发现/搜索/索引默认 ignore 已统一（可通过参数关闭）
- [ ] trust folders（项目/用户/系统分层，allow/deny/ask_user 的策略落点）

### 3.2 索引质量与查询语义
- [~] TS/JS symbols：regex MVP 已可用
- [ ] TS/JS symbols 精度升级（更稳的 export/default/namespace/类型声明、line_end、import/require 解析）
- [~] repo map query：按 path/kind 分组 + 可选 snippet 已有
- [ ] repo map 查询“面向问题”的语义（按 symbol/path/kind/focus 更强组合、结果聚合与去重策略）
- [~] imports 查询：index_query_imports 已有
- [ ] imports 的“可解释视图”（入/出度、热点模块、按 focus_terms 过滤的摘要）

### 3.3 让索引能力真正进入“用户可用闭环”
- [ ] 让 orchestrator / agent 在执行前自动跑 index_build（或检测索引过期并提示）
- [ ] 把 repo map / imports / search hits 作为 context 注入的固定策略（减少盲搜与重复读）

---

## 4) P3（product-grade runtime）并行推进

### 4.1 approvals / capabilities / sandbox 分层
- [~] capability gating（required_permission + PermissionPolicy）已落地
- [~] cmd_run(exec) 已有（作为 approvals/sandbox 的落点）
- [ ] approvals policy engine（allow/deny/ask_user；默认策略；可配置分层：系统→用户→项目→CLI）
- [ ] sandbox/network/redaction 模型（至少能表达：技术能力 vs 是否需要审批 vs 是否允许联网）

### 4.2 hooks 与结构化事件（供 UI/trace/replay）
- [~] Tool hooks + hook_error 事件已落地
- [ ] hooks 扩展到更高层生命周期（run/turn/verification/rollback 等）
- [~] tool_call/tool_result 事件已结构化（含 risk/permission）
- [ ] 事件模型“单一事实源”收敛：UI 只从 canonical events 做投影（禁止双轨状态）
- [ ] polling → SSE/WebSocket（至少 approval/trace/workflow 关键路径）

### 4.3 工程化门禁与可观测（对应深度调研 P2）
- [ ] 统一验证脚本：pytest + npm build + tauri/cargo test（本地与 CI 对齐）
- [ ] 关键 KPI 与回放一致性：事件重放一致性、审批延迟、失败 TopN、回滚原因

---

## 5) 前后端适配任务（记录，避免“后端能力不可用”）

### 5.1 后端（Desktop/Tauri/Bridge）
- [ ] bridge 层暴露新工具：fs_list_files/fs_glob(ignore)/search_rg(use_default_ignore)/index_build/index_query_repo_map/index_query_imports/cmd_run
- [ ] 将 ToolRunner events 以流式通道推送给前端（替代轮询；支持 replay）
- [ ] 将 required_permission/risk_level/permission_mode 与 approval UI 打通（exec/write 触发 ask_user）

### 5.2 前端（apps/desktop）
- [ ] 新增“Repo Map/Imports”面板或入口（可按 focus_terms 查询；点选跳转到文件+行号；展示 snippet）
- [ ] tools-panel/trace-panel 补齐新字段展示（conflict 结构化、dry_run、permission gating、hook_error）
- [ ] approval-panel 从 polling 迁移到事件订阅（SSE/WebSocket/tauri event）
- [ ] 设置页补“ignore/trust/approval policy”配置入口（系统/用户/项目分层的 UI 承载）

