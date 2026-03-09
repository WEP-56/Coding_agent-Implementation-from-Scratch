# CodingGirl 前端 UI/UX 设计文档（MVP）

> 角色视角：UI/UX 设计师（偏工程产品）  
> 目标用户：独立开发者（Windows 首发）  
> 技术落地约束：Tauri + React + Tailwind + shadcn/ui  
> 语言策略：首发简体中文，预留 i18n 结构

---

## 1. 设计目标与原则

### 1.1 MVP 目标

构建一个**面向开发者的桌面工作台**，将「仓库管理 → 会话执行 → 变更审阅 → 应用/回滚」闭环可视化。

### 1.2 设计原则

1. **Repo-first**：先定仓库，再做会话与执行。
2. **执行可见性优先**：时间线、状态徽章、关键通知。
3. **安全可控**：按会话模式控制自动应用与敏感操作确认。
4. **低干扰高密度**：工程工具风格，低饱和单强调色。
5. **可演进**：MVP 先可用，GitHub OAuth/市场在线能力后置。

---

## 2. 参考项目与可复用模式（严肃参考）

以下结论仅基于可核验公开资料：

### 2.1 OpenCode（参考点）

- 明确有 **TUI / Web / Desktop** 多入口与客户端/服务端架构倾向（README）。
- 使用 **Build/Plan 等不同权限代理模式**（Agents 文档）用于控制编辑与命令风险。

参考：
- https://github.com/anomalyco/opencode/blob/dev/README.md
- https://opencode.ai/docs/agents

### 2.2 OpenClaw（参考点）

- 明确强调 **Gateway 控制平面 + 多端客户端**（README）。
- 强调 **安全默认策略**（如 DM pairing、权限门槛），以及引导式 setup 思路。
- 强调 **Control UI + WebChat + 会话/事件** 视角，适合迁移到 CodingGirl 的执行工作台。

参考：
- https://github.com/openclaw/openclaw/blob/main/README.md

### 2.3 对 CodingGirl 的映射结论

1. 采用「**控制平面思维**」：前端是可视化编排与审阅层，不把复杂逻辑塞进 UI。  
2. 采用「**模式化权限**」：Plan / Build / Auto 三种会话模式。  
3. 采用「**多入口一致数据模型**」：未来 Telegram/Web 复用同一 session/run/artifact 结构。

---

## 3. 已确认产品决策（来自需求问答）

- 平台：**桌面优先（Tauri），Windows 首发**。
- IA：**Repo-first 主导航**，全局会话流作为次级视图。
- 布局：**三栏布局**。
- 主区：**会话对话 + 执行时间线**。
- 右栏：`Diff → Tools → Logs → Artifacts`。
- Diff：默认 **Split**，可切 Unified。
- 变更策略：**按会话模式**（Plan/Build/Auto）决定审批行为。
- Auto：默认允许全自动 Apply（配强防线）。
- 敏感操作：默认 Ask，可记住选择。
- 视觉：双主题并重，低饱和 + 单强调色。
- Live2D：首版移除。
- 交互：鼠标主导，保留执行控制快捷键。
- 可访问性：WCAG AA 关键项。
- MVP 页面：工作台 + 仓库管理 + 设置 + 插件市场占位（含本地插件导入）。
- Onboarding：不做首开向导，直接进工作台。

---

## 4. 信息架构（IA）

## 4.1 一级导航

1. **工作台**（默认）
2. **仓库管理**
3. **设置**
4. **插件市场（占位）**

## 4.2 工作台三栏结构

### 左栏（导航）
- 仓库切换器（当前仓库）
- 会话列表（当前仓库）
- 次级入口：全局会话视图（跨仓库）

### 中栏（主工作区）
- 会话消息流（用户输入/系统输出）
- 执行时间线（step-by-step）
- 顶部运行状态条（模式、分支、当前任务）

### 右栏（详情）
- Tab1: Diff（默认）
- Tab2: Tools（工具调用详情）
- Tab3: Logs（日志）
- Tab4: Artifacts（产物）

---

## 5. 关键交互设计

## 5.1 仓库接入

MVP：
- 支持本地目录导入（主流程）
- GitHub HTTPS / 私有 OAuth 先占位（todo 尾部）
- 浅克隆策略（未来接入时默认 depth=1）

## 5.2 会话模式

### Plan
- 只读分析，不应用变更
- 敏感操作默认拒绝（或仅只读工具）

### Build
- 生成变更后需人工审批（默认）
- 敏感操作 Ask

### Auto
- 自动执行并自动 Apply（你已明确）
- 敏感操作 Ask（可记住）
- 强防线：
  - 一键回滚本次变更
  - 变更批次标识
  - 敏感路径黑名单（如 `.env`）

## 5.3 执行时间线（中心反馈）

每个 step 状态：
- `等待中` / `运行中` / `成功` / `失败`

失败后固定三动作：
1. 重试本步
2. 回滚本次变更
3. 查看诊断

## 5.4 Diff 审阅

- 默认 Split
- 切换 Unified
- 文件树 + hunk 导航
- Apply / Reject / 回滚

## 5.5 通知策略

仅关键事件通知：
- 执行完成
- 执行失败
- 需要审批

---

## 6. 视觉与设计系统（MVP）

## 6.1 主题
- `dark` / `light` 双主题首发

## 6.2 色彩
- 低饱和中性色为底
- 单强调色（建议蓝青系）
- 状态色：成功/警告/错误

## 6.3 排版
- UI 字体：系统默认（Windows）
- 代码/日志：等宽字体

## 6.4 组件规范（首批）
- SessionList
- TimelineStep
- DiffPanel
- ToolCallCard
- LogViewer
- ApprovalBar
- StatusBadge

---

## 7. 无障碍与可用性标准（AA关键项）

至少满足：
- 文本/关键控件对比度达 AA
- 焦点可见（键盘导航）
- 主要操作可键盘触达（执行控制）
- 支持字号缩放

---

## 8. 状态与数据模型（前端）

核心实体：
- `Repo`
- `Session`
- `Run`
- `Step`
- `PatchSet`
- `ToolCall`
- `Artifact`

前端状态分层：
1. 全局应用状态（theme、currentRepo）
2. 会话域状态（currentSession、mode）
3. 运行态（timeline、diff、logs）

---

## 9. 风险与防线

### 风险
- Auto 模式全自动 Apply 可能误改代码
- 无 Onboarding 可能导致初次用户迷失

### 防线
- Auto 模式强制显示“最近变更批次 + 一键回滚”
- 空态页给 3 个首步动作（导入仓库 / 新建会话 / 查看示例命令）

---

## 10. 非目标（MVP 不做）

- Live2D/Avatar 视觉模块
- 完整插件市场在线安装与评分
- GitHub OAuth 私有仓库拉取（仅占位）
- 高级快捷键与复杂工作区布局自定义

---

## 11. 设计验收标准（Design Definition of Done）

1. 三栏 IA 与交互链路无断点（Repo → Session → Run → Review）。
2. Plan/Build/Auto 模式在 UI 中可感知且行为一致。
3. 时间线与右栏四 Tab 数据联动正确。
4. 关键事件通知与失败三动作可用。
5. 双主题切换完整，AA 关键项通过检查。
