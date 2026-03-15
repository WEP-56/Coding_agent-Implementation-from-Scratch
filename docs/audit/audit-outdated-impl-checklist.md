# 全仓“过时/不佳实现”审计清单（初版）

更新时间：2026-03-15

目标：列出当前仓库里 **可能过时、重复、实现不佳、或语义不一致** 的点，并给出建议的处理动作（保留/重构/删除/合并）。

> 说明：本清单基于当前代码扫描 + 我们近期改动的上下文（ContextStats、侧边栏职责收敛、Python JSONL events）。

---

## A. P0 必修：语义分裂 / 单一事实源问题

### A1) 事件体系分裂：`event_types.py`（colon 风格） vs runtime JSONL `kind`（underscore 风格）
- 现象：
  - `codinggirl/core/event_types.py` 定义了如 `context:stats_update`、`todo:initialized`、`loop:iteration` 这类 **colon 风格 event_type**。
  - 但实际 Python runtime 持久化/桌面流（SQLiteStore/JSONL）使用的关键字段是 `kind="loop_iteration" / "context_stats_update" / "todo_updated" ...` 这种 **underscore 风格 kind**。
  - `codinggirl/core/event_bus.py` 这套 EventBus（event_type/publish-subscribe）目前几乎没有被 runtime 主链路使用。
- 风险：
  - 同一概念存在两套命名体系，后续必然出现“UI监听 A，Python emit B”的漂移。
  - 文档（如 `docs/stage9-phase1-implementation-guide.md`）引用了 `event_types` 常量，会误导后续实现。
- 建议动作：
  1) 明确 **canonical runtime grammar**：以 JSONL `kind` 为准（因为已落到 DB + Desktop ingest）。
  2) `event_types.py` 要么：
     - (a) 直接改为导出 underscore kinds（并把 colon 作为兼容 alias），要么
     - (b) 标记为 legacy，逐步删除（但需先清掉 docs 引用）。
  3) `event_bus.py`：如果不用（目前看基本未用），建议标记 legacy 或移至 experiments。

### A2) ContextStats 的“两个数据通路”风险
- 现象：
  - 目前 UI 的用量圈优先读 `pythonContext`（来自 Rust state 的 `python_context_stats`），fallback 到 `pythonTodo.stats.contextTokens`。
- 风险：
  - fallback 通路可能导致数据来源不一致（todo 不更新时 token 不变）。
- 建议动作：
  - 下一阶段彻底把 `contextTokens` 从 todo stats 去掉（或仅用于 debug），强制 UI 只读 `pythonContext`。

---

## B. P1 建议：重复实现 / UI 入口混乱

### B1) Workspace 页面双轨：`workspace-page.tsx` vs `workspace-page-v3.tsx`
- 现象：
  - Desktop 有两套 workspace 页面（v1/v3），容易导致“改了但用户在看另一个页面”。
- 风险：
  - 后续迭代成本翻倍、bug 修复遗漏。
- 建议动作：
  - 明确 v3 为主入口后：逐步移除 v1（或在 UI 明显标注“legacy”），避免误用。

### B2) 右侧栏职责容易膨胀（历史上已发生）
- 现象：
  - 右侧栏曾承载 Memory/Context/Todo，已按用户偏好收敛为文件树。
- 建议动作：
  - 在代码层加注释/约束：RightSidebar = files only，其他面板改为“临时弹层/顶部按钮”。

---

## C. P1/P2 建议：实现不佳但可接受（需要逐步替换）

### C1) token 估算方式（字符数/4）
- 现象：
  - `codinggirl/core/context_manager.py` 使用 chars/4 的粗估。
- 风险：
  - 对 CJK、tool JSON、长路径等误差较大，可能导致压缩时机偏移。
- 建议动作：
  - 短期：保留粗估 + 用户可调阈值（已实现）。
  - 中期：引入更准确 tokenizer（按 provider/model 可切换），或至少针对 tool/json 做惩罚系数。

### C2) Event JSON schema 缺少显式版本
- 现象：
  - JSONL event payload 结构靠约定，没有 `schemaVersion`。
- 风险：
  - UI/后端升级时难做兼容。
- 建议动作：
  - 给 Python JSONL events 加 `schemaVersion: 1` 或 `v` 字段，并在 Rust ingest 做兼容。

---

## D. “可删除/可归档”候选

### D1) `codinggirl/core/event_bus.py`（如果确认不走 publish-subscribe）
- 现象：
  - 当前 `emit_event` 在 repo 内无调用（仅定义）。
- 建议动作：
  - 若未来不准备采用 event bus：移动到 `experiments/` 或删除。
  - 若准备采用：必须把它接入 Desktop ingest（目前不是）。

---

## E. 下一步建议（基于本审计清单的行动顺序）

1) **事件语义收敛**（A1）：统一事件命名体系（underscore kinds）并修正文档引用。
2) **清理 UI 双轨**（B1）：将 v1 标记 legacy 或移除入口。
3) **Todo 系统可用化**：在统一事件体系后，增强 todo 与 context/subagent/taskgraph 的联动。
