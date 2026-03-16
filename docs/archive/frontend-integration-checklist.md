# 前端集成准备清单

**更新时间**：2026-03-13
**目标**：为前端集成做好准备，确保后端接口清晰、事件完整

---

## 📡 Tauri 命令接口设计

### 1. Agent Loop 相关命令

#### `run_agent_loop`
```rust
#[tauri::command]
async fn run_agent_loop(
    goal: String,
    permission_mode: String,
    enable_todo: bool,
    enable_context_management: bool,
) -> Result<AgentLoopResult, String>
```

**返回**：
```json
{
  "run_id": "abc123",
  "success": true,
  "iterations": 5,
  "final_message": "Task completed",
  "todo_stats": {"total": 3, "completed": 3},
  "context_stats": {
    "message_count": 20,
    "token_count": 5000,
    "compact_count": 2
  }
}
```

#### `get_run_status`
```rust
#[tauri::command]
async fn get_run_status(run_id: String) -> Result<RunStatus, String>
```

#### `stop_agent_loop`
```rust
#[tauri::command]
async fn stop_agent_loop(run_id: String) -> Result<(), String>
```

---

### 2. Context 相关命令

#### `get_context_stats`
```rust
#[tauri::command]
async fn get_context_stats(run_id: String) -> Result<ContextStats, String>
```

**返回**：
```json
{
  "message_count": 20,
  "token_count": 5000,
  "tool_result_count": 8,
  "compact_count": 2,
  "last_compact_iteration": 15
}
```

#### `get_transcript`
```rust
#[tauri::command]
async fn get_transcript(run_id: String) -> Result<Vec<Message>, String>
```

#### `trigger_manual_compact`
```rust
#[tauri::command]
async fn trigger_manual_compact(run_id: String) -> Result<CompactResult, String>
```

---

### 3. Todo 相关命令

#### `get_todo_list`
```rust
#[tauri::command]
async fn get_todo_list(run_id: String) -> Result<Vec<TodoItem>, String>
```

**返回**：
```json
[
  {
    "step_id": "s1",
    "title": "Read files",
    "description": "Find and read target files",
    "status": "completed"
  },
  {
    "step_id": "s2",
    "title": "Analyze content",
    "status": "in_progress"
  }
]
```

---

## 📢 事件推送设计

### 1. Agent Loop 事件

#### `agent:loop_started`
```json
{
  "run_id": "abc123",
  "goal": "User task",
  "timestamp": "2026-03-13T10:00:00Z"
}
```

#### `agent:loop_iteration`
```json
{
  "run_id": "abc123",
  "iteration": 5,
  "message_count": 20,
  "timestamp": "2026-03-13T10:00:05Z"
}
```

#### `agent:loop_completed`
```json
{
  "run_id": "abc123",
  "success": true,
  "iterations": 10,
  "final_message": "Task completed",
  "timestamp": "2026-03-13T10:00:30Z"
}
```

---

### 2. Context 事件

#### `context:micro_compact`
```json
{
  "run_id": "abc123",
  "iteration": 5,
  "before_count": 20,
  "after_count": 15,
  "saved_tokens": 1500,
  "timestamp": "2026-03-13T10:00:05Z"
}
```

#### `context:auto_compact`
```json
{
  "run_id": "abc123",
  "iteration": 15,
  "token_count_before": 55000,
  "token_count_after": 5000,
  "threshold": 50000,
  "saved_tokens": 50000,
  "summary_length": 500,
  "timestamp": "2026-03-13T10:00:15Z"
}
```

#### `context:warning`
```json
{
  "run_id": "abc123",
  "token_count": 48000,
  "threshold": 50000,
  "warning": "Approaching token limit",
  "timestamp": "2026-03-13T10:00:14Z"
}
```

---

### 3. Todo 事件

#### `todo:initialized`
```json
{
  "run_id": "abc123",
  "total": 3,
  "timestamp": "2026-03-13T10:00:00Z"
}
```

#### `todo:updated`
```json
{
  "run_id": "abc123",
  "iteration": 5,
  "stats": {
    "total": 3,
    "pending": 1,
    "in_progress": 1,
    "completed": 1
  },
  "timestamp": "2026-03-13T10:00:05Z"
}
```

---

### 4. Tool 事件

#### `tool:call`
```json
{
  "run_id": "abc123",
  "call_id": "call_123",
  "tool_name": "fs_read_file",
  "args": {"path": "README.md"},
  "timestamp": "2026-03-13T10:00:03Z"
}
```

#### `tool:result`
```json
{
  "run_id": "abc123",
  "call_id": "call_123",
  "tool_name": "fs_read_file",
  "ok": true,
  "duration_ms": 50,
  "timestamp": "2026-03-13T10:00:03Z"
}
```

---

## 🎨 UI 组件需求

### 1. Context Stats Panel（优先级：高）

**位置**：右侧边栏或工作流卡片内

**显示内容**：
- [ ] Token 使用率进度条
  - 当前 token 数 / 阈值
  - 颜色：绿色（< 70%）、黄色（70-90%）、红色（> 90%）
- [ ] Message 数量
- [ ] Tool result 数量
- [ ] Compact 次数

**交互**：
- [ ] 点击查看详细统计
- [ ] 手动触发 compact 按钮

---

### 2. Compact History Timeline（优先级：中）

**位置**：Trace 面板内

**显示内容**：
- [ ] Compact 事件时间线
- [ ] 每次 compact 的类型（micro/auto）
- [ ] 节省的 token 数
- [ ] 压缩前后对比

**交互**：
- [ ] 点击查看压缩详情
- [ ] 查看压缩前后的 messages

---

### 3. Todo List Panel（优先级：高）

**位置**：工作流卡片内或独立面板

**显示内容**：
- [ ] 任务列表（pending/in_progress/completed）
- [ ] 进度条（completed / total）
- [ ] 当前正在进行的任务高亮

**交互**：
- [ ] 实时更新状态
- [ ] 点击查看任务详情

---

### 4. Transcript Viewer（优先级：低）

**位置**：独立弹窗或面板

**显示内容**：
- [ ] 完整对话历史
- [ ] 高亮被压缩的部分
- [ ] 显示 token 数

**交互**：
- [ ] 搜索消息
- [ ] 导出为 JSON
- [ ] 查看压缩前的原始内容

---

## 🔌 事件流实现方案

### 方案 1：Tauri Event（推荐）

**优点**：
- Tauri 原生支持
- 简单易用
- 自动处理序列化

**实现**：
```rust
// Rust 端
app.emit_all("context:micro_compact", payload)?;

// TypeScript 端
import { listen } from '@tauri-apps/api/event';

listen('context:micro_compact', (event) => {
  console.log('Compact event:', event.payload);
});
```

---

### 方案 2：WebSocket（备选）

**优点**：
- 更灵活
- 支持双向通信
- 可以跨平台

**缺点**：
- 需要额外实现
- 复杂度更高

---

## 📊 数据持久化需求

### SQLite 表扩展

#### `transcript` 表（新增）
```sql
CREATE TABLE transcript (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  iteration INTEGER NOT NULL,
  messages_json TEXT NOT NULL,
  token_count INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
```

#### `context_event` 表（新增）
```sql
CREATE TABLE context_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  iteration INTEGER NOT NULL,
  event_type TEXT NOT NULL,  -- 'micro_compact' | 'auto_compact' | 'warning'
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

---

## 🧪 前端集成测试清单

### 端到端测试

- [ ] 启动 agent loop，验证事件推送
- [ ] 触发 micro-compact，验证 UI 更新
- [ ] 触发 auto-compact，验证摘要生成
- [ ] 更新 todo，验证实时同步
- [ ] 查看 transcript，验证完整性

### 性能测试

- [ ] 100+ 消息时的 UI 响应速度
- [ ] 事件推送频率（不应该太频繁）
- [ ] 内存占用（长时间运行）

---

## 🚀 实施优先级

### Phase 1（本周）- 后端准备
1. ✅ Context Manager 实现
2. [ ] 集成到 AgentLoop
3. [ ] 事件记录到数据库
4. [ ] 基础 Tauri 命令

### Phase 2（下周）- 前端集成
1. [ ] Context Stats Panel
2. [ ] Todo List Panel
3. [ ] 事件监听和实时更新

### Phase 3（后续）- 增强功能
1. [ ] Compact History Timeline
2. [ ] Transcript Viewer
3. [ ] 手动 compact 功能

---

## 📝 注意事项

### 性能考虑
- 事件推送不要太频繁（建议每秒最多 10 次）
- 大量消息时考虑分页或虚拟滚动
- Context stats 可以缓存，不需要每次都计算

### 用户体验
- Compact 过程应该对用户透明（不阻塞 UI）
- 提供清晰的进度反馈
- 错误信息要友好

### 安全性
- Transcript 可能包含敏感信息，注意权限控制
- 导出功能要有确认提示
