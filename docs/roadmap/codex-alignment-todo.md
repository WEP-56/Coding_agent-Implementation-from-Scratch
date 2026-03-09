# Codex 对标改造 TODO

更新日期：2026-03-09

这份清单保留为内部执行版；对外公开说明已经重构到 [`../architecture.html`](../architecture.html) 与 [`../papers.html`](../papers.html)。原则是：

- 先补 runtime grammar，再补 feedback grammar，最后才做 polish。
- 每完成一个条目，都要检查它是否真的改善了 `稳定性 / repo anchoring / 首帧反馈 / diff provenance / 恢复语义`。
- 不引入云端并行 agent 作为前置条件。

## P0

- [ ] 统一 `TurnItem` schema，覆盖 `user_message / assistant_message / reasoning / tool / command / diff / approval / compaction / validation / error`
      当前已落地 `phase / context / model_request / validation / command / tool / diff / approval / artifact / error`；`reasoning / compaction` 仍待补齐。
- [ ] 让 timeline、workflow card、trace export 全部从 canonical turn items 投影，而不是各自维护状态
      当前 workflow card 主视图与 timeline 已优先从 `SessionTurn.items` 投影；trace export 仍保留双轨数据，旧 `session_events` 还没完全退成 projection。
- [ ] 用流式事件替代轮询，至少先做到本地 Tauri session 事件推送
- [ ] 发送消息后立刻创建 optimistic run shell，并在同一 run 上持续填充状态
- [x] 做 session preflight：每轮执行前明确 `repo_root / repo_name / session_title / mode / route / permission context`
- [ ] 强化 repo anchoring，杜绝“进入项目会话后模型像没站在 repo 里”这一类错位
      当前 preflight 已固定 repo identity / route / permission context，但所有入口的一致性和人工回归还没完全收口。
- [ ] 统一所有 mutation 的 diff provenance：`apply_patch / unified diff / direct write / approval replay / rollback`
      当前 `apply_patch / unified diff / direct write / approval replay` 已接入 structured provenance；rollback 已接入真实 backend 流程，但 rollback 变更视图仍待继续收口。
- [ ] 所有 mutation 统一生成 `runId` 归属的 artifact 和 rollback metadata
      当前 patch / direct write / approval replay 已统一带 `runId / artifact_group_id / rollback_meta_path`；旧字符串 provenance 还需继续清理。
- [x] 拆分错误类型：`transport / provider / model / routing / tool / approval / validation / rollback`
- [ ] 为每类错误定义明确的 retry / fallback / user-facing message
      当前 `transport / provider / model / command` 已有初步收口；`tool / routing / rollback / approval` 仍需继续系统化。

## P1

- [ ] 把 intent router 升级成“模型判定优先、规则兜底、结果可解释”的正式能力
- [ ] 在 UI 中展示当前回合的 route、route 来源、fallback 原因
- [ ] 做 Context Engine v2：history normalization、summary policy、memory policy、tool-output prune
- [ ] 为 context 加 token breakdown 与 compaction lifecycle 可视化
- [ ] 把 `Build / Plan / Explore / Review / General` 做成明确的 agent 语义，而不是只改按钮或提示词
- [ ] 引入 hidden internal agents，用于 explore、compaction、summary、review 等内部任务
- [ ] 把 terminal 升级为 workspace-scoped、多 tab、可恢复 buffer
- [ ] 让 terminal 与 run / tool / file changes 建立更强关联
      当前 terminal 已进入 canonical `run / turn / command item`，但多 tab、buffer 恢复、文件变化关联还没完成。

## P2

- [ ] 定义 `resume / fork / rollback` 的统一 session semantics
- [ ] 让 rollback 成为 turn graph 中的一等事件，而不是单独的文件回写动作
- [ ] 将 lint / test / build / code review 统一纳入 turn items 与 workflow card
- [ ] 引入 watcher 与 ignore patterns，减少无意义目录噪音
- [ ] 增强长期任务 supervision：允许多阶段执行、暂停、恢复、继续验证
- [ ] 建立更强的 run verification 阶段，而不是“模型自己说完成了”就算完成

## P3

- [ ] 设计 skills / reusable workflows / project recipes
- [ ] 评估 desktop / CLI / future IDE 的 shared session continuity
- [ ] 补 provider-native adapters 和 team config
- [ ] 做 automation 之前，先确认 runtime、context、permission 已经足够稳定

## 每轮开发后的验证清单

- [x] `cargo test`
- [x] `npm run build`
- [ ] 至少一次真实会话人工回归：确认 repo anchoring 正常
- [ ] 至少一次 mutation 回归：确认工作流卡片、Diff、Tools、Artifacts、Rollback 都归属到正确 run
- [ ] 至少一次错误路径回归：确认失败信息可解释且不会导致“整轮失忆”

## 暂不做

- [ ] 云端并行 agents
- [ ] 纯表面 UI 仿 Codex
- [ ] 在 runtime 未稳定前继续堆新入口或社交化功能
