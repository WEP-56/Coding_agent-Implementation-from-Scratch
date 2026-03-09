# Coding Agent Docs

这个目录现在是仓库对外展示的文档入口，也是 GitHub Pages 的静态站点源目录。
This directory is now the public documentation entry for the repository and the static source for GitHub Pages.

## 页面结构 / Site map

- [指引 / Guide](./index.html)
  主页导航，解释项目定位、真实边界、阅读顺序和 Pages 部署方式。
  The landing page explains the project scope, reality check, reading order, and GitHub Pages deployment model.
- [使用教程 / Tutorial](./roadmap.html)
  说明如何按正确顺序体验 Python core 和桌面端。
  Shows how to exercise the Python core and the desktop path in the right order.
- [快速开始 / Quick Start](./getting-started.html)
  保留最短命令链，适合先跑通仓库。
  Keeps the shortest useful command path for getting the repository running.
- [从零开始 / From Scratch](./architecture.html)
  从对象模型、运行时、前端和具体实现层面拆解系统。
  Breaks the system down through objects, runtime design, frontend structure, and concrete implementation.
- [论文 / Papers](./papers.html)
  当前只占位，后续再补论文与参考资料。
  Currently a placeholder for future papers and references.

## 兼容入口 / Legacy entry

- [旧的 codex-alignment 入口](./codex-alignment.html)
  现在会跳转到论文页，避免旧链接直接失效。
  This now redirects to the papers page so older links do not break immediately.

## 仍然保留的内部资料 / Internal references still kept

- [`coding-standards.md`](./coding-standards.md)
- [`roadmap/`](./roadmap/)

这些文件仍然有参考价值，但不再承担 GitHub Pages 主导航角色。
These files still have reference value, but they are no longer the main public navigation surface.

## 发布方式 / Publishing

`docs/` 使用纯静态 HTML + CSS + 少量原生 JavaScript。
`docs/` uses plain HTML + CSS + a small amount of vanilla JavaScript.

GitHub Pages 只需要把 source 指到当前分支的 `/docs` 目录即可。
For GitHub Pages, point the source to the `/docs` directory on the current branch.
