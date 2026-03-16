# CodingGirl

**可观测、可控的 AI 编程助手**

CodingGirl 是一个专注于**可视化工作流与超级 Trace** 的 Coding Agent 项目。不同于传统 AI 编程工具，我们的核心目标是让 AI 的工作过程**可监督、可回放、可恢复**，帮助开发者更好地理解和控制 AI 的决策。

在能力较强的模型加持下（GPT-5+、Claude、Gemini、GLM-5+、Qwen-3+ 等），CodingGirl 已经可以胜任中型项目的开发任务。

---

## ✨ 核心特性

- **🔍 超级 Trace**：完整记录 AI 的每一步决策，支持回放和审计
- **📊 工作流可视化**：实时展示任务分解、执行进度和上下文状态
- **⚡ 并行执行**：多 Agent 并行处理复杂任务，显著提升效率
- **🎯 智能上下文管理**：自适应压缩，保持关键信息不丢失
- **🔧 Skills 系统**：按需加载领域知识，避免 prompt 膨胀
- **🖥️ 多模态支持**：Desktop UI + CLI + Bot，适配不同使用场景

---

## 📊 项目规模

```text
模块                    文件数  代码行数
智能体核心                 74    12774
测试验证                   18     2591
前端界面                   45     9373
桌面后端                   23    12084
文档                       20     5543
```

生成命令：`py scripts/loc.py`

---

## 🏗️ 架构概览

```text
apps/desktop/        React + Tauri 桌面应用（主要产品形态）
codinggirl/          Python Agent 核心（工具、运行时、索引）
docs/                文档站点（GitHub Pages）
tests/               测试套件
skills/              内置技能库
```

**两条实现线**：
- **Desktop UI**：当前最重要的产品面和实验场
- **Python Core**：底层能力（workspace、工具、patch 应用等）

---

## 🚀 快速开始

### 1. Python 核心

**要求**：Python >= 3.11

```bash
# 安装依赖
py -m pip install -e .[dev]

# 运行测试
py -m pytest

# 初始化
py -m codinggirl init

# 索引代码库
py -m codinggirl index --repo . --index-dir .codinggirl/index --max-lines 160
```

### 2. 桌面应用（推荐）

**要求**：Node.js + Rust toolchain

```bash
cd apps/desktop

# 安装依赖
npm install

# 开发模式
npm run desktop

# 构建发布版
npm run build
npm run tauri build
```

### 3. Web 开发模式

```bash
cd apps/desktop
npm install
npm run dev
```

---

## 📖 文档

- **[文档首页](./docs/index.html)** - 项目定位和阅读指南
- **[快速上手](./docs/getting-started.html)** - 最短启动路径
- **[架构说明](./docs/architecture.html)** - 核心对象和工具边界
- **[使用指南](./docs/roadmap.html)** - 工作流和用户路径
- **[论文参考](./docs/papers.html)** - 相关研究和对标资料

---

## 🎯 发展路线

### P0 - 稳定性（当前阶段）
- ✅ 统一 runtime grammar 和事件模型
- ✅ 完善错误分类和重试机制
- ✅ 实现上下文智能压缩
- ✅ 并行 Agent 系统

### P1 - 智能化（进行中）
- 🔄 Search-replace 编辑模式
- 🔄 自动测试运行和验证
- 🔄 语义搜索和代码索引
- 🔄 智能回滚和错误恢复

### P2 - 产品化
- ⏳ Resume / Fork / Rollback 语义
- ⏳ 长期任务监控
- ⏳ 项目级知识库

### P3 - 生态化
- ⏳ 插件市场
- ⏳ 多人协作
- ⏳ 自定义工作流编排

---

## 🤝 贡献指南

欢迎贡献代码或观点！无论是手工制作还是 AI 产出，**有效的就是最好的**。

### 优先级建议

1. **提升成功率**：工具参数校验、失败恢复、可回放证据链
2. **增强可解释性**：事件语义单一、UI 投影清晰、失败可定位
3. **同步前端适配**：新能力要有 UI 入口，避免"后端很强但用户用不到"

### 开发约束

- 单文件不超过 800 行，达到 1000 行必须拆分
- 前后端同步推进，不能只改后端不适配前端
- 优先减少状态漂移、隐式行为和语义不一致

---

## 🔬 技术亮点

### 可观测性
- 30+ 事件类型的完整 Trace 系统
- Timeline 投影和事件流重建
- 实时上下文统计和健康度监控

### 并行能力
- 真并行多 Agent 执行
- LLM 驱动的任务自动分解
- 拓扑排序处理任务依赖

### 上下文管理
- 滑动窗口 + 重要性采样
- 自适应压缩阈值
- 结构化摘要（无需 LLM 调用）

---

## 📜 许可证

MIT

---

## 🙏 致谢

本项目部分实现参考了 [ShareAI](https://learn.shareai.run/en/) 的教程和最佳实践。
