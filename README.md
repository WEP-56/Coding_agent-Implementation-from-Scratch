# CodingGirl

CodingGirl 是一个正在持续向 Codex / OpenCode 方向推进的 coding agent 项目。

这个仓库当前不是“做很多表面功能”的阶段，重点在把 runtime、context lifecycle、feedback grammar、diff provenance、approval、rollback 这些底层能力收紧成一个稳定系统。

## 它现在是什么

仓库里有两条实现线：

- `apps/desktop/`
  React + Tauri 桌面端。
  这是当前最重要的产品面和 runtime 实验场。
- `codinggirl/`
  Python agent core。
  保留 contracts、workspace sandbox、CLI、patch 应用等底层能力。

当前状态可以概括成一句话：

> 已经是一个可实际使用的原型，但还在从“功能拼接”往“canonical runtime”收敛。

## 进化路线


1. `P0`（当前阶段）
   先把系统跑稳。
   统一 canonical turn/item、runtime grammar、mutation provenance、rollback metadata、error taxonomy。
2. `P1`
   再把系统跑聪明。
   强化 intent router、context engine、tool-output prune、route explanation。
3. `P2`
   让它接近产品级。
   补 resume / fork / rollback semantics、verification、watcher、长期任务 supervision。
4. `P3`
   最后补长期效率层。
   再考虑 skills、shared continuity、team config、automation。


## 文档入口


- [文档首页](./docs/index.html)
- [快速上手](./docs/getting-started.html)
- [架构说明](./docs/architecture.html)
- [路线图](./docs/roadmap.html)
- [Papers / 对标资料入口](./docs/papers.html)
- [文档索引](./docs/README.md)
- [内部执行清单](./docs/roadmap/codex-alignment-todo.md)



## 当前仓库结构

```text
apps/desktop/        React + Tauri 桌面端原型
codinggirl/          Python agent core
docs/                当前主文档入口
tests/               Python 测试
tmp/                 上游参考源码区（不要改）
.codinggirl/         本地状态、memory、trace、artifacts、index
pyproject.toml       Python 包与 CLI 配置
```

## 快速开始

### 1. Python Core

要求：

- Python `>= 3.11`

安装与测试：

```bash
py -m pip install -e .[dev]
py -m pytest
```

初始化与运行：

```bash
py -m codinggirl init
py -m codinggirl index --repo . --index-dir .codinggirl/index --max-lines 160
py -m codinggirl orchestrate --repo . --db .codinggirl/codinggirl.sqlite3 --goal "replace [old] with [new] in [README.md]"
```

### 2. Desktop Web Shell

要求：

- Node.js
- npm

运行：

```bash
cd apps/desktop
npm install
npm run dev
```

### 3. Desktop Tauri Shell

要求：

- Rust toolchain
- Tauri 所需本地依赖

运行桌面壳：

```bash
cd apps/desktop
npm run desktop
```

构建：

```bash
cd apps/desktop
npm run build
npm run tauri build
```

## 常用验证命令

```bash
py -m pytest
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
cd apps/desktop && npm run build
```

如果你正在推进 runtime 主线，这三个通常都应该过。

## 开发约束

- `docs/` 是主文档入口。
- 前后端要同步推进，不能只改后端不适配前端。
- 单文件尽量不要超过 `800` 行；超过 `1000` 行必须拆分。
- 优先拉近本项目与 Codex / OpenCode 在 runtime / context / feedback 上的距离。
- 不要在 runtime 还没稳定时继续堆表面功能。

## 现在已经有的方向性成果

最近这条主线已经完成了几件关键事：

- canonical `SessionTurn / SessionTurnItem` 已经落地，并开始作为 workflow card 的主数据源
- `phase / context / model_request / validation / command / tool / diff / approval / artifact / error` 已经逐步进入同一套 runtime grammar
- terminal command 已经进入 canonical run/turn，而不再是旁路能力
- rollback 已经接入真实 backend 流程
- mutation provenance / rollback metadata 已开始结构化
- error taxonomy 已经从字符串提示推进到显式类别

## 重要提醒

- 这个仓库目前仍处在快速演进阶段。
- 它已经不是“只能演示”的玩具，但还不是可以直接对外发布的产品。
- 继续开发守则：最有价值的工作通常不是“再加一个按钮”，而是继续减少状态漂移、减少隐式行为、减少前后端语义不一致。

## 许可证

MIT
