# CodingGirl vs Codex/OpenCode Roadmap (P0-P3)

> This is the execution todo list for closing implementation gaps.

## P0 — Core capability parity (must-have)

- [x] Persistent chat context + memory blocks injected into model context
- [x] Repo file read/search/write toolchain with sandbox guards
- [x] Codex-style `apply_patch` support with move/EOF/multi-chunk matching
- [x] Approval queue for mutating tools (approve/reject)
- [x] Per-tool allow/ask/deny policy UI in settings

## P1 — OpenCode-grade approval granularity

- [x] Approval request model includes `toolName + action + path`
- [x] `allow_session` support (approve for this session)
- [x] Session permission cache and matcher `(session, tool, action, path)`
- [x] Approval UI shows action/path and supports allow_session
- [ ] Optional: separate global auto-approve session mode for non-interactive run

## P2 — Artifact + rollback traceability

- [x] Persist patch artifacts to disk under `.codinggirl/artifacts/<session>/<ts>/`
- [x] Save rollback metadata (JSON) for each patch operation
- [x] Surface patch artifacts in existing Artifacts panel
- [x] Add one-click rollback command based on rollback metadata
- [ ] Add artifact integrity hash + provenance fields

## P3 — Trace/event observability parity

- [x] Emit trace-like timeline events for session/tool/approval/artifact stages
- [x] Persist trace events through existing timeline storage
- [ ] Add dedicated Trace panel (filter by type: session/tool/approval/artifact)
- [x] Add event correlation IDs between timeline, tool calls, approvals, artifacts
- [ ] Export trace bundle (JSON) for debugging/replay

## Gap matrix (current snapshot)

| Capability | Codex | OpenCode | CodingGirl (now) | Gap level |
|---|---|---|---|---|
| apply_patch engine (move/EOF/chunks) | Strong | Strong | Strong | Low |
| Unified diff compatibility | Medium | Strong | Medium | Medium |
| Approval granularity (tool/action/path) | Medium | Strong | Strong | Low |
| allow_session semantics | Medium | Strong | Strong | Low |
| Patch artifact persistence | Medium | Medium | Strong | Low |
| Rollback execution pipeline | Medium | Medium | Partial | Medium |
| Timeline trace fidelity | Strong | Medium | Medium | Medium |
| Trace correlation + export | Strong | Medium | Weak | High |

## Execution order (next)

1. P3: add Trace panel + traceType/correlation filters
2. P3: trace export bundle
3. P2: artifact integrity hash + provenance fields
4. P1(optional): global session auto-approve mode
