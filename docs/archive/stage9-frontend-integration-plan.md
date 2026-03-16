# Stage 9: 前后端打通 - 实施计划

**目标**：将后端的 7 个核心功能展示到前端 UI，提供实时可视化和交互

---

## 一、架构设计

### 1.1 事件流架构

```
Agent Loop (Python)
    ↓ 事件生成
Event Bus (Python)
    ↓ 序列化
Tauri Event Bridge
    ↓ IPC
Frontend (React)
    ↓ 渲染
UI Components
```

### 1.2 事件类型

#### Context Management 事件
- `context:micro_compact` - Micro-compact 执行
- `context:auto_compact` - Auto-compact 执行
- `context_stats_update` - 上下文统计更新

#### Todo 事件
- `todo:initialized` - Todo 列表初始化
- `todo:updated` - Todo 状态更新
- `todo:stats_update` - Todo 统计更新

#### Task Graph 事件
- `task:created` - 任务创建
- `task:updated` - 任务状态更新
- `task:unlocked` - 任务解锁
- `task:stats_update` - 任务图统计更新

#### Background Tasks 事件
- `background:started` - 后台任务启动
- `background:completed` - 后台任务完成
- `background:failed` - 后台任务失败
- `background:stats_update` - 后台任务统计更新

#### Subagent 事件
- `subagent:started` - 子 agent 启动
- `subagent:completed` - 子 agent 完成
- `subagent:tool_call` - 子 agent 工具调用

#### Skills 事件
- `skill:loaded` - 技能加载
- `skill:list_update` - 技能列表更新

#### Agent Loop 事件
- `loop:iteration` - 循环迭代
- `loop:tool_call` - 工具调用
- `loop:llm_response` - LLM 响应
- `loop:complete` - 循环完成

---

## 二、后端实现

### 2.1 事件系统核心

**文件**：`codinggirl/core/event_bus.py`

```python
@dataclass
class Event:
    event_type: str
    timestamp: str
    run_id: str
    payload: dict[str, Any]

class EventBus:
    def __init__(self):
        self.listeners: dict[str, list[callable]] = {}
        self.event_queue: queue.Queue = queue.Queue()

    def emit(self, event: Event):
        """发送事件"""

    def subscribe(self, event_type: str, callback: callable):
        """订阅事件"""

    def get_events(self, since: float) -> list[Event]:
        """获取事件（用于轮询）"""
```

### 2.2 Tauri Commands

**文件**：`src-tauri/src/commands/agent.rs`

```rust
#[tauri::command]
async fn get_agent_events(since: f64) -> Result<Vec<Event>, String> {
    // 从 Python 获取事件
}

#[tauri::command]
async fn get_context_stats(run_id: String) -> Result<ContextStats, String> {
    // 获取上下文统计
}

#[tauri::command]
async fn get_todo_list(run_id: String) -> Result<TodoList, String> {
    // 获取 Todo 列表
}

#[tauri::command]
async fn get_task_graph(run_id: String) -> Result<TaskGraph, String> {
    // 获取任务图
}

#[tauri::command]
async fn get_background_tasks() -> Result<Vec<BackgroundTask>, String> {
    // 获取后台任务列表
}
```

### 2.3 事件注入点

在现有代码中注入事件发送：

1. **AgentLoopWithSubagent** - 在关键点发送事件
2. **ContextManager** - compact 时发送事件
3. **TodoManager** - 更新时发送事件
4. **TaskGraph** - 状态变更时发送事件
5. **BackgroundManager** - 任务状态变更时发送事件
6. **SubagentRunner** - 启动/完成时发送事件

---

## 三、前端实现

### 3.1 UI 组件清单

#### 3.1.1 Context Stats Panel
**位置**：右侧边栏
**功能**：
- 显示当前 message 数量
- 显示 token 估算
- 显示 tool result 数量
- 显示 compact 次数
- 显示节省的 tokens

**数据源**：`context_stats_update` 事件

#### 3.1.2 Todo List Panel
**位置**：右侧边栏
**功能**：
- 显示任务列表（pending/in_progress/completed）
- 实时更新任务状态
- 显示当前正在执行的任务
- 显示完成进度条

**数据源**：`todo:updated` 事件

#### 3.1.3 Task Graph Visualization
**位置**：独立面板（可展开）
**功能**：
- 可视化任务依赖关系（DAG）
- 显示任务状态（颜色编码）
- 显示阻塞关系
- 高亮可执行任务

**技术栈**：React Flow 或 D3.js

**数据源**：`task:*` 事件

#### 3.1.4 Background Tasks Monitor
**位置**：底部状态栏
**功能**：
- 显示正在运行的后台任务
- 显示任务进度（如果可用）
- 点击查看任务详情（stdout/stderr）
- 显示完成通知

**数据源**：`background:*` 事件

#### 3.1.5 Subagent Trace Panel
**位置**：Trace 面板扩展
**功能**：
- 显示子 agent 调用层级
- 显示子 agent 的工具调用
- 显示子 agent 返回的摘要
- 可折叠/展开

**数据源**：`subagent:*` 事件

#### 3.1.6 Skills Browser
**位置**：侧边栏或独立面板
**功能**：
- 列出所有可用技能
- 显示技能描述和标签
- 显示已加载的技能
- 支持搜索和过滤

**数据源**：`skill:*` 事件

### 3.2 组件层级结构

```
App
├── MainLayout
│   ├── WorkflowPanel (现有)
│   ├── TracePanel (现有，扩展)
│   │   ├── ToolCallTrace (现有)
│   │   └── SubagentTrace (新增)
│   ├── RightSidebar (新增)
│   │   ├── ContextStatsPanel
│   │   ├── TodoListPanel
│   │   └── SkillsBrowser
│   ├── BottomBar (扩展)
│   │   └── BackgroundTasksMonitor
│   └── TaskGraphModal (新增)
│       └── TaskGraphVisualization
```

---

## 四、实施步骤

### Phase 1: 后端事件系统（1-2 天）
1. ✅ 创建 EventBus 类
2. ✅ 定义事件类型和 schema
3. ✅ 在 Agent Loop 中注入事件发送
4. ✅ 在各个 Manager 中注入事件发送
5. ✅ 创建事件序列化和持久化

### Phase 2: Tauri 集成（1 天）
1. ✅ 创建 Tauri commands
2. ✅ 实现 Python-Rust IPC
3. ✅ 实现事件轮询或推送
4. ✅ 测试事件流

### Phase 3: 前端基础组件（2 天）
1. ✅ Context Stats Panel
2. ✅ Todo List Panel
3. ✅ Background Tasks Monitor

### Phase 4: 前端高级组件（2-3 天）
1. ✅ Task Graph Visualization
2. ✅ Subagent Trace Panel
3. ✅ Skills Browser

### Phase 5: 集成测试和优化（1-2 天）
1. ✅ 端到端测试
2. ✅ 性能优化
3. ✅ UI/UX 优化
4. ✅ 文档更新

---

## 五、技术细节

### 5.1 事件推送方案

**方案 A：轮询（简单）**
- 前端定时调用 `get_agent_events(since)`
- 优点：实现简单，无需 WebSocket
- 缺点：延迟较高（1-2 秒）

**方案 B：Tauri Event（推荐）**
- 使用 Tauri 的 event system
- Python 通过 IPC 发送事件到 Tauri
- Tauri emit 到前端
- 优点：实时性好，Tauri 原生支持
- 缺点：需要 Python-Rust 通信

**选择**：先实现方案 A（快速验证），后续优化为方案 B

### 5.2 数据持久化

扩展 SQLiteStore，添加新表：

```sql
-- 事件表
CREATE TABLE event_stream (
    id INTEGER PRIMARY KEY,
    run_id TEXT,
    event_type TEXT,
    timestamp TEXT,
    payload_json TEXT
);

-- 上下文快照表
CREATE TABLE context_snapshot (
    id INTEGER PRIMARY KEY,
    run_id TEXT,
    iteration INTEGER,
    message_count INTEGER,
    token_count INTEGER,
    compact_count INTEGER
);

-- Todo 快照表
CREATE TABLE todo_snapshot (
    id INTEGER PRIMARY KEY,
    run_id TEXT,
    iteration INTEGER,
    todo_json TEXT
);
```

### 5.3 性能优化

1. **事件批处理**：每 100ms 批量发送事件
2. **增量更新**：只发送变更的数据
3. **虚拟滚动**：大列表使用虚拟滚动
4. **懒加载**：Task Graph 按需加载

---

## 六、测试计划

### 6.1 单元测试
- EventBus 测试
- 事件序列化测试
- Tauri commands 测试

### 6.2 集成测试
- 端到端事件流测试
- 多组件同步测试
- 性能测试（1000+ 事件）

### 6.3 UI 测试
- 组件渲染测试
- 交互测试
- 响应式测试

---

## 七、里程碑

- **M1**：事件系统核心完成，能发送和接收事件
- **M2**：Context Stats 和 Todo List 显示正常
- **M3**：Task Graph 可视化完成
- **M4**：所有组件集成完成，端到端测试通过

---

## 八、风险和挑战

1. **Python-Rust 通信**：需要设计稳定的 IPC 机制
2. **事件同步**：确保前后端状态一致
3. **性能**：大量事件可能影响性能
4. **UI 复杂度**：Task Graph 可视化较复杂

---

## 九、后续优化

1. **实时推送**：从轮询升级到 WebSocket/SSE
2. **历史回放**：支持查看历史 run 的事件流
3. **导出功能**：导出 trace、task graph 等
4. **主题定制**：支持自定义 UI 主题
