# CodingGirl

CodingGirl 是一个仍在快速演进中的 coding agent 原型仓库。它目前同时包含两条实现线：

- `codinggirl/`：Python 编写的 agent core，覆盖 contracts、workspace sandbox、SQLite trace、Repo Index、Patch 应用、CLI 和 Telegram 模拟入口。
- `apps/desktop/`：React + Tauri 编写的桌面端原型，覆盖会话界面、时间线、审批、Artifacts、Trace 导出和本地仓库读写桥接。

截至 2026-03-08，这个项目已经能演示一部分“像 Codex / OpenCode 那样工作”的能力，但还没有统一成一个真正可长期维护、可部署、可面向用户交付的产品。

## 文档入口

新的文档主入口已经整理到 `docs/`，并可直接作为 GitHub Pages 静态站点部署：

- [文档首页](./docs/index.html)
- [快速上手](./docs/getting-started.html)
- [架构原理](./docs/architecture.html)
- [现状与路线图](./docs/roadmap.html)
- [Codex 对标改造](./docs/codex-alignment.html)
- [文档索引](./docs/README.md)

如果你准备继续开发这个项目，请优先以 `docs/` 中的新文档作为当前事实基线。

## 当前仓库结构

```text
codinggirl/          Python agent core
tests/               Python 测试
apps/desktop/        React + Tauri 桌面端
docs/                新的文档站点与内部规格
tmp/                 上游源码参考区（不要改）
.codinggirl/         本地状态、索引、trace、memory
```

## 快速开始

### Python Core

```bash
py -m pip install -e .[dev]
py -m pytest
py -m codinggirl init
py -m codinggirl index --repo . --index-dir .codinggirl/index --max-lines 160
py -m codinggirl orchestrate --repo . --db .codinggirl/codinggirl.sqlite3 --goal "replace [old] with [new] in [README.md]"
```

### Desktop Prototype

```bash
cd apps/desktop
npm install
npm run dev
```

如果需要 Tauri 桌面能力：

```bash
npm run tauri build
```

## 重要说明

- `tmp/` 内包含 Codex、OpenCode 及其他上游参考源码，当前阶段只作为对照和学习材料，不应在这里做项目改动。
- 根目录下的 `project-CodingGirl.md`、`todo list.md`、`frontend-design.md`、`frontend-todo-list.md`、`frontend-product-gap-analysis.md`、`frontend-product-polish-todo.md` 仍保留为历史规划草稿；它们不再是面对用户的主文档。
- 仓库当前不是一个完整的 git 仓库快照；如果要继续工程化推进，建议后续先补齐版本管理、发布流程和 CI。

## 接下来

文档整理完成后，下一阶段工作目标会是：

1. 统一 Python core 与 Desktop runtime 的执行权威。
2. 补齐会话恢复、上下文压缩、trace/event 协议。
3. 把审批、安全策略、验证和 artifact 生命周期做成产品级闭环。
4. 逐步把这个原型推进到真正可用、工程化、产品化。
