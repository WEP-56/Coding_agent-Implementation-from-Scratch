# 多 Agent 并行系统 - 前端集成方案

## 📊 概述

本文档描述如何在前端（Desktop/Web UI）中集成和可视化多 Agent 并行系统。

---

## 🎨 UI 设计方案

### 1. 并行任务面板（主要 UI）

```
┌─────────────────────────────────────────────────────────┐
│  🔄 Parallel Tasks (3 running, 1 completed)            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 🟢 Task 1: Analyze frontend                     │  │
│  │ ████████████████░░░░░░░░░░ 65%                  │  │
│  │ Status: Reading src/renderer/App.tsx             │  │
│  │ Time: 8.2s                                       │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 🟢 Task 2: Analyze backend                      │  │
│  │ ████████████████████░░░░░░ 80%                  │  │
│  │ Status: Analyzing API endpoints                  │  │
│  │ Time: 10.5s                                      │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 🟡 Task 3: Check security                       │  │
│  │ ██████░░░░░░░░░░░░░░░░░░░░ 25%                  │  │
│  │ Status: Scanning for vulnerabilities            │  │
│  │ Time: 3.1s                                       │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │ ✅ Task 4: Build code index                     │  │
│  │ ████████████████████████████ 100%               │  │
│  │ Status: Completed                                │  │
│  │ Time: 12.8s                                      │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
│  📊 Overall: 3/4 completed • Total time: 34.6s       │
│  ⚡ Speedup: 2.7x (vs 93.4s sequential)              │
└─────────────────────────────────────────────────────────┘
```

### 2. 任务分解可视化

当使用自动分解时，显示分解过程：

```
┌─────────────────────────────────────────────────────────┐
│  🧩 Task Decomposition                                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Original Task:                                         │
│  "Analyze entire codebase for code quality"            │
│                                                         │
│  ↓ Auto-decomposed into 4 parallel tasks:              │
│                                                         │
│  1. 📁 Analyze frontend code structure                 │
│  2. 📁 Analyze backend API design                      │
│  3. 🔒 Check security vulnerabilities                  │
│  4. ⚡ Identify performance bottlenecks                │
│                                                         │
│  [Start Parallel Execution]                            │
└─────────────────────────────────────────────────────────┘
```

### 3. 结果综合可视化

```
┌─────────────────────────────────────────────────────────┐
│  📝 Synthesizing Results...                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Combining insights from 4 parallel tasks:             │
│                                                         │
│  ✅ Frontend analysis (12.3s)                          │
│  ✅ Backend analysis (10.8s)                           │
│  ✅ Security scan (15.2s)                              │
│  ✅ Performance analysis (9.5s)                        │
│                                                         │
│  🤖 Generating unified summary...                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4. 设置面板

在设置中添加并行配置：

```
┌─────────────────────────────────────────────────────────┐
│  ⚙️ Parallel Agent Settings                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Enable Parallel Agents                                │
│  [✓] Allow agent to use parallel execution             │
│                                                         │
│  Max Parallel Agents                                   │
│  [====|====] 4                                         │
│  (1 - 8 agents)                                        │
│                                                         │
│  Auto Task Decomposition                               │
│  [✓] Automatically decompose complex tasks             │
│                                                         │
│  Result Synthesis                                      │
│  [✓] Synthesize results into unified summary           │
│                                                         │
│  Performance Mode                                      │
│  ○ Conservative (2 parallel)                           │
│  ● Balanced (4 parallel)                               │
│  ○ Aggressive (8 parallel)                             │
│                                                         │
│  [Save Settings]                                       │
└─────────────────────────────────────────────────────────┘
```

---

## 📡 事件流设计

### 事件序列

```
1. parallel_agents_start
   ↓
2. task_decomposed (如果使用自动分解)
   ↓
3. parallel_task_start (每个任务)
   ↓
4. parallel_task_progress (实时更新)
   ↓
5. parallel_task_complete / parallel_task_error
   ↓
6. result_synthesis_start
   ↓
7. result_synthesis_complete
   ↓
8. parallel_agents_complete
```

### 事件 Payload 定义

#### 1. `parallel_agents_start`
```typescript
{
  kind: "parallel_agents_start",
  payload: {
    task_count: 4,
    max_parallel: 4,
    tasks: [
      {
        task_id: "task_0",
        description: "Analyze frontend",
        priority: 1
      },
      // ...
    ]
  }
}
```

#### 2. `task_decomposed`
```typescript
{
  kind: "task_decomposed",
  payload: {
    original_task: "Analyze entire codebase",
    subtask_count: 4,
    subtasks: [
      "Analyze frontend code structure",
      "Analyze backend API design",
      // ...
    ]
  }
}
```

#### 3. `parallel_task_start`
```typescript
{
  kind: "parallel_task_start",
  payload: {
    task_id: "task_0",
    description: "Analyze frontend"
  }
}
```

#### 4. `parallel_task_progress`
```typescript
{
  kind: "parallel_task_progress",
  payload: {
    task_id: "task_0",
    progress: 0.65,  // 0-1
    status: "Reading src/renderer/App.tsx"
  }
}
```

#### 5. `parallel_task_complete`
```typescript
{
  kind: "parallel_task_complete",
  payload: {
    task_id: "task_0",
    success: true,
    execution_time_sec: 12.3,
    retry_count: 0
  }
}
```

#### 6. `parallel_task_error`
```typescript
{
  kind: "parallel_task_error",
  payload: {
    task_id: "task_2",
    error: "Timeout after 300s",
    retry_count: 1
  }
}
```

#### 7. `result_synthesis_start`
```typescript
{
  kind: "result_synthesis_start",
  payload: {
    task_count: 4,
    success_count: 3
  }
}
```

#### 8. `result_synthesis_complete`
```typescript
{
  kind: "result_synthesis_complete",
  payload: {
    summary: "Synthesized summary text...",
    synthesis_time_sec: 2.5
  }
}
```

#### 9. `parallel_agents_complete`
```typescript
{
  kind: "parallel_agents_complete",
  payload: {
    task_count: 4,
    success_count: 3,
    failed_count: 1,
    total_time_sec: 34.6,
    avg_time_sec: 8.65,
    speedup: 2.7  // vs sequential
  }
}
```

---

## 💻 前端实现示例（React/TypeScript）

### 1. 状态管理

```typescript
// types.ts
interface ParallelTask {
  task_id: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  progress: number;  // 0-1
  statusText: string;
  executionTime: number;
  error?: string;
}

interface ParallelAgentState {
  isActive: boolean;
  tasks: ParallelTask[];
  totalTasks: number;
  completedTasks: number;
  totalTime: number;
  speedup?: number;
}

// store.ts (Zustand/Redux)
const useParallelAgentStore = create<ParallelAgentState>((set) => ({
  isActive: false,
  tasks: [],
  totalTasks: 0,
  completedTasks: 0,
  totalTime: 0,
  speedup: undefined,

  // Actions
  startParallelExecution: (payload) => set({
    isActive: true,
    tasks: payload.tasks.map(t => ({
      task_id: t.task_id,
      description: t.description,
      status: 'pending',
      progress: 0,
      statusText: 'Waiting...',
      executionTime: 0,
    })),
    totalTasks: payload.task_count,
    completedTasks: 0,
  }),

  updateTaskProgress: (task_id, progress, statusText) => set((state) => ({
    tasks: state.tasks.map(t =>
      t.task_id === task_id
        ? { ...t, status: 'running', progress, statusText }
        : t
    ),
  })),

  completeTask: (task_id, executionTime) => set((state) => ({
    tasks: state.tasks.map(t =>
      t.task_id === task_id
        ? { ...t, status: 'completed', progress: 1, executionTime }
        : t
    ),
    completedTasks: state.completedTasks + 1,
  })),

  // ...
}));
```

### 2. 事件监听

```typescript
// useParallelAgentEvents.ts
import { useEffect } from 'react';
import { useParallelAgentStore } from './store';

export function useParallelAgentEvents() {
  const store = useParallelAgentStore();

  useEffect(() => {
    // 监听事件（假设通过 EventSource 或 WebSocket）
    const eventSource = new EventSource('/api/events');

    eventSource.addEventListener('parallel_agents_start', (e) => {
      const payload = JSON.parse(e.data);
      store.startParallelExecution(payload);
    });

    eventSource.addEventListener('parallel_task_start', (e) => {
      const payload = JSON.parse(e.data);
      store.updateTaskProgress(payload.task_id, 0, 'Starting...');
    });

    eventSource.addEventListener('parallel_task_progress', (e) => {
      const payload = JSON.parse(e.data);
      store.updateTaskProgress(
        payload.task_id,
        payload.progress,
        payload.status
      );
    });

    eventSource.addEventListener('parallel_task_complete', (e) => {
      const payload = JSON.parse(e.data);
      store.completeTask(payload.task_id, payload.execution_time_sec);
    });

    eventSource.addEventListener('parallel_agents_complete', (e) => {
      const payload = JSON.parse(e.data);
      store.finishParallelExecution(payload);
    });

    return () => eventSource.close();
  }, []);
}
```

### 3. UI 组件

```typescript
// ParallelTasksPanel.tsx
import React from 'react';
import { useParallelAgentStore } from './store';
import { useParallelAgentEvents } from './useParallelAgentEvents';

export function ParallelTasksPanel() {
  useParallelAgentEvents();
  const { isActive, tasks, completedTasks, totalTasks, speedup } =
    useParallelAgentStore();

  if (!isActive) return null;

  return (
    <div className="parallel-tasks-panel">
      <div className="panel-header">
        <h3>🔄 Parallel Tasks</h3>
        <span className="task-count">
          {completedTasks}/{totalTasks} completed
        </span>
      </div>

      <div className="tasks-list">
        {tasks.map((task) => (
          <TaskCard key={task.task_id} task={task} />
        ))}
      </div>

      {speedup && (
        <div className="speedup-indicator">
          ⚡ Speedup: {speedup.toFixed(1)}x
        </div>
      )}
    </div>
  );
}

function TaskCard({ task }: { task: ParallelTask }) {
  const statusIcon = {
    pending: '⏳',
    running: '🟢',
    completed: '✅',
    error: '❌',
  }[task.status];

  return (
    <div className={`task-card task-${task.status}`}>
      <div className="task-header">
        <span className="status-icon">{statusIcon}</span>
        <span className="task-description">{task.description}</span>
      </div>

      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${task.progress * 100}%` }}
        />
      </div>

      <div className="task-footer">
        <span className="status-text">{task.statusText}</span>
        <span className="execution-time">
          {task.executionTime.toFixed(1)}s
        </span>
      </div>

      {task.error && (
        <div className="error-message">{task.error}</div>
      )}
    </div>
  );
}
```

### 4. CSS 样式

```css
/* ParallelTasksPanel.css */
.parallel-tasks-panel {
  background: var(--panel-bg);
  border-radius: 8px;
  padding: 16px;
  margin: 16px 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.task-count {
  font-size: 14px;
  color: var(--text-secondary);
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  background: var(--card-bg);
  border-radius: 6px;
  padding: 12px;
  border-left: 4px solid var(--border-color);
  transition: all 0.3s ease;
}

.task-card.task-running {
  border-left-color: #4caf50;
  animation: pulse 2s infinite;
}

.task-card.task-completed {
  border-left-color: #2196f3;
  opacity: 0.8;
}

.task-card.task-error {
  border-left-color: #f44336;
}

.task-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.status-icon {
  font-size: 18px;
}

.task-description {
  font-weight: 500;
  flex: 1;
}

.progress-bar {
  height: 6px;
  background: var(--progress-bg);
  border-radius: 3px;
  overflow: hidden;
  margin: 8px 0;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4caf50, #8bc34a);
  transition: width 0.3s ease;
}

.task-footer {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
}

.speedup-indicator {
  margin-top: 16px;
  padding: 8px;
  background: var(--success-bg);
  border-radius: 4px;
  text-align: center;
  font-weight: 500;
  color: var(--success-color);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.error-message {
  margin-top: 8px;
  padding: 8px;
  background: var(--error-bg);
  border-radius: 4px;
  font-size: 12px;
  color: var(--error-color);
}
```

---

## 🎯 集成步骤

### 步骤 1: 后端添加事件发送

在 `parallel_agent_orchestrator.py` 中已经添加了事件发送，确保所有关键节点都发送事件。

### 步骤 2: 前端添加事件监听

在前端的事件监听器中添加新的事件类型：

```typescript
// 在现有的事件监听代码中添加
const eventHandlers = {
  // ... 现有事件
  'parallel_agents_start': handleParallelAgentsStart,
  'parallel_task_start': handleParallelTaskStart,
  'parallel_task_progress': handleParallelTaskProgress,
  'parallel_task_complete': handleParallelTaskComplete,
  'parallel_task_error': handleParallelTaskError,
  'parallel_agents_complete': handleParallelAgentsComplete,
  'task_decomposed': handleTaskDecomposed,
  'result_synthesis_start': handleResultSynthesisStart,
  'result_synthesis_complete': handleResultSynthesisComplete,
};
```

### 步骤 3: 添加设置项

在设置面板中添加并行配置：

```typescript
// settings.ts
interface ParallelAgentSettings {
  enabled: boolean;
  maxParallelAgents: number;  // 1-8
  autoDecomposition: boolean;
  resultSynthesis: boolean;
  performanceMode: 'conservative' | 'balanced' | 'aggressive';
}

const defaultSettings: ParallelAgentSettings = {
  enabled: true,
  maxParallelAgents: 4,
  autoDecomposition: true,
  resultSynthesis: true,
  performanceMode: 'balanced',
};
```

### 步骤 4: 添加 UI 组件

将 `ParallelTasksPanel` 组件添加到主界面：

```typescript
// App.tsx
import { ParallelTasksPanel } from './components/ParallelTasksPanel';

function App() {
  return (
    <div className="app">
      {/* 现有组件 */}
      <ChatPanel />
      <TodoPanel />

      {/* 新增：并行任务面板 */}
      <ParallelTasksPanel />

      {/* 其他组件 */}
    </div>
  );
}
```

---

## 📊 性能监控

### 在 UI 中显示性能指标

```typescript
// PerformanceMetrics.tsx
function PerformanceMetrics() {
  const { totalTime, speedup, tasks } = useParallelAgentStore();

  const sequentialTime = tasks.reduce((sum, t) => sum + t.executionTime, 0);
  const parallelTime = totalTime;
  const efficiency = (sequentialTime / parallelTime / tasks.length) * 100;

  return (
    <div className="performance-metrics">
      <div className="metric">
        <span className="label">Sequential Time:</span>
        <span className="value">{sequentialTime.toFixed(1)}s</span>
      </div>
      <div className="metric">
        <span className="label">Parallel Time:</span>
        <span className="value">{parallelTime.toFixed(1)}s</span>
      </div>
      <div className="metric">
        <span className="label">Speedup:</span>
        <span className="value highlight">{speedup.toFixed(1)}x</span>
      </div>
      <div className="metric">
        <span className="label">Efficiency:</span>
        <span className="value">{efficiency.toFixed(0)}%</span>
      </div>
    </div>
  );
}
```

---

## 🎨 动画效果建议

### 1. 任务启动动画
- 任务卡片从上方滑入
- 进度条从 0 开始填充

### 2. 进度更新动画
- 进度条平滑过渡
- 状态文本淡入淡出

### 3. 任务完成动画
- 绿色勾选图标弹出
- 卡片轻微缩放

### 4. 并行执行可视化
- 多个任务卡片同时动画
- 强调"并行"的概念

---

## 🔔 通知和提示

### 1. 任务开始通知
```
🔄 Started 4 parallel tasks
Analyzing frontend, backend, security, and performance
```

### 2. 任务完成通知
```
✅ Parallel execution completed
4 tasks finished in 34.6s (2.7x faster)
```

### 3. 任务失败通知
```
⚠️ Task "Security scan" failed
Retrying... (attempt 2/2)
```

---

## 📱 响应式设计

### 桌面端
- 并行任务面板在侧边栏显示
- 每个任务卡片完整显示

### 移动端
- 并行任务面板折叠为摘要
- 点击展开查看详情
- 任务卡片垂直堆叠

---

## 🎯 总结

通过以上设计，前端可以：

1. ✅ **实时显示**并行任务的执行状态
2. ✅ **可视化进度**，让用户了解每个任务的进展
3. ✅ **性能指标**，展示并行带来的加速效果
4. ✅ **配置选项**，让用户控制并行行为
5. ✅ **错误处理**，清晰显示失败的任务

这将大大提升用户体验，让多 Agent 并行系统的优势直观可见！

---

**最后更新**: 2026-03-16
**版本**: v1.0.0
