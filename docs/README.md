# CodingGirl Docs

这里是当前仓库的主文档区，也是后续建议部署到 GitHub Pages 的内容源。

## 面向外部的主文档

- [文档首页](./index.html)
- [快速上手](./getting-started.html)
- [架构原理](./architecture.html)
- [现状与路线图](./roadmap.html)
- [Codex 对标改造](./codex-alignment.html)

## 仍然保留的内部资料

- [`coding-standards.md`](./coding-standards.md)：代码规范草案
- [`roadmap/`](./roadmap/)：阶段性规格、缺口记录与事件模型设计
- [`roadmap/codex-alignment-todo.md`](./roadmap/codex-alignment-todo.md)：Codex 对标改造 TODO 清单

## 文档治理约定

- `docs/` 是当前对外说明的主入口。
- 根目录若继续保留规划稿，应视为“历史草稿”而不是事实基线。
- `tmp/` 中的上游源码不是本项目文档的一部分，只能作为参考。
- 如果后续实现发生变化，应优先更新：
  - `docs/getting-started.html`
  - `docs/architecture.html`
  - `docs/roadmap.html`

## GitHub Pages

当前 `docs/` 使用纯静态 HTML + CSS，不依赖 Jekyll 主题，也不需要额外构建步骤。  
将仓库的 GitHub Pages Source 指向 `main` 分支的 `/docs` 目录即可发布。
