# CodingGirl 前端体验差距分析（对标 Cursor / OpenCode / Codex）

> 目标：将当前原型从“功能可用”推进到“产品可用”。  
> 范围：前端体验（信息架构、执行反馈、审阅信任、恢复效率、配置心智）。  
> 方法：基于可核验公开资料 + 当前项目实装状态评估。

---

## 1) 对标基线（可核验）

## 1.1 Cursor（可核验）

已验证信息（来自官网/文档可见内容）：
- 强调 Agent 工作流、审阅与多表面协同（IDE/GitHub/Slack/Terminal）
- 强调自主执行但保留人类决策位置
- 强调模型选择、上下文理解（索引/语义）

参考：
- https://cursor.com
- https://cursor.com/features
- https://cursor.com/docs/get-started/quickstart
- https://cursor.com/docs/rules

## 1.2 OpenCode（可核验）

已验证信息：
- Web/TUI/CLI 多入口，且会话可共享状态
- 显式权限模型（allow / ask / deny）
- `AGENTS.md` / Rules / Sessions / Undo/Redo 等“工程化可逆”能力

参考：
- https://opencode.ai/docs
- https://opencode.ai/docs/web
- https://opencode.ai/docs/tui
- https://opencode.ai/docs/agents
- https://opencode.ai/docs/permissions

## 1.3 Codex App（说明）

本轮抓取中，OpenAI 部分公开页面存在 403（工具访问限制），故不做未经证实的 UI 细节断言。  
保留“Codex 作为成熟基准之一”的方向，但本分析中的具体对标结论主要由 Cursor/OpenCode 的可核验资料支撑。

---

## 2) 当前项目前端现状（截至本轮）

已实现（A~G + 中间区打磨）：
- Repo-first + 三栏工作台
- 中间会话对话区（可发送/系统回复/时间线联动）
- 右栏 Diff/Tools/Logs/Artifacts 实体面板
- Plan/Build/Auto 模式与审批策略（Build 批次审批、Auto 自动应用）
- 敏感操作策略（ask/allow/deny，按仓库存储）
- 仓库管理与插件本地导入
- 设置页（基础/安全/模型）

结论：**已具备“可运行原型”能力，但产品化体验仍存在关键差距。**

---

## 3) 核心体验差距（Gap）

## G1. 任务“起手心智”仍不够清晰

现状：会话区可发送，但“下一步该做什么”缺少强引导顺序。  
对标启示：Cursor/OpenCode 都强调清晰的 mode/plan/execute 语义。

影响：新用户能用，但不够稳；老用户切换成本偏高。

---

## G2. 可逆操作入口显性不足（Undo/Redo 没有产品级主入口）

现状：已有回滚动作，但“安全感锚点”未形成统一心智。

用户已拍板：
- Undo/Redo 主入口放 **右栏 Diff 工具条**。

---

## G3. 执行反馈虽有时间线，但“失败恢复路径”还不够一眼可用

现状：失败三动作已存在，但主次强调、默认聚焦策略、会话摘要回访还可加强。

用户已拍板：
- 发送后默认展开 **时间线步骤**
- 失败主按钮 = **重试本步**
- 会话列表显示 **可恢复摘要（如：失败于运行测试）**

---

## G4. 规则层（Rules/AGENTS 心智）还没前端可见化

现状：后端已有策略与会话模式，但“项目规则”缺统一编辑入口。

用户已拍板：
- 规则入口放 **设置页独立模块**（而非右栏 Tab）

---

## G5. “减少占位”仍需继续推进

现状：中间区已从占位升级，但右栏动作与部分信息仍偏 mock。  
产品化方向：动作总线统一、结果可追溯、复盘信息更结构化。

---

## 4) 取其精华，去其糟粕（策略）

## 4.1 取其精华（吸收）

1. **模式清晰化**（Cursor/OpenCode）
   - 保留并强化 Plan/Build/Auto 的可见状态与行为差异。

2. **权限可解释**（OpenCode）
   - Ask/Allow/Deny 的提示文案与“记住本仓库”延续。

3. **会话与执行并行可见**（两者共同特征）
   - 中栏对话 + 时间线，右栏细节四分层。

4. **可逆与可追溯**
   - Undo/Redo 显性化；失败恢复路径一键直达。

## 4.2 去其糟粕（避免）

1. 不堆砌过多“表面入口”（首发 Windows 桌面优先）。
2. 不做过度炫技动效（维持工程工具效率第一）。
3. 不把“高级配置”前置到首屏（减少认知负担）。
4. 不在 MVP 引入复杂会话恢复面板（你已明确不做）。

---

## 5) 产品化改版 PRD（本轮定稿）

## 5.1 目标

在不改变当前三栏结构的前提下，把“能用”提升到“顺手、可信、可恢复”。

## 5.2 用户已确认的关键决策（本轮问答）

- 首屏主动作：**导入本地仓库**
- 空态语气：**简短工程风**
- 首屏恢复：**只展示最近仓库（不做最近任务）**
- Undo/Redo 入口：**右栏 Diff 工具条**
- Plan/Build 策略：**默认 Build，可一键切 Plan**
- 审批策略：**Auto 无审批 / Build 批次审批**
- 发送后默认展开：**时间线**
- 失败主按钮：**重试本步**
- 会话列表：**显示简短恢复摘要**
- 规则入口：**设置页独立模块**
- 会话恢复面板：**本轮不加入**

## 5.3 交互规范（新增）

### A. 空态
- 无仓库：主 CTA = 导入本地仓库
- 无会话：主 CTA = 新建会话（默认 Build）

### B. Diff 工具条
- 固定：Apply / Reject / Rollback / Undo / Redo
- 模式联动：
  - Plan：Apply 禁用
  - Build：Apply 触发批次审批
  - Auto：Apply 自动

### C. 失败恢复
- 主按钮：重试本步（强调色）
- 次按钮：查看诊断、回滚

### D. 会话列表
- 结构：标题 + 模式 + 最后状态摘要（如“失败：运行测试”）

### E. 设置页 Rules 模块
- 项目级规则文本（MVP 可本地存储）
- 作用域提示：当前仓库生效

---

## 6) 验收标准（UX DoD）

1. 新用户在 30 秒内完成“导入仓库→新建会话→发送任务”。
2. 用户能在 3 秒内找到 Undo/Redo（Diff 工具条可见）。
3. 失败后 1 步内触发“重试本步”。
4. 会话列表可一眼识别“哪条会话需要恢复”。
5. 设置页可编辑并保存项目规则。

---

## 7) 参考链接（本轮）

- Cursor: https://cursor.com
- Cursor Features: https://cursor.com/features
- OpenCode Docs: https://opencode.ai/docs
- OpenCode Web: https://opencode.ai/docs/web
- OpenCode TUI: https://opencode.ai/docs/tui
- OpenCode Agents: https://opencode.ai/docs/agents
- OpenCode Permissions: https://opencode.ai/docs/permissions
