# CodingGirl Session & Context V2 Spec

> Goal: make session/context **Codex-grade** in 4 dimensions: **observable, compactable, recoverable, extensible (for multi-agent)**.

---

## 1) Product Goal (User-Experience First)

Sandbox is baseline safety. The primary product value for CodingGirl is:

1. **Conversation continuity**: user can keep long-running threads without context collapse.
2. **Workflow visibility**: every turn/tool/approval/patch is visible in one timeline.
3. **Deterministic recovery**: sessions can resume/fork/rollback from persisted history.
4. **Future multi-agent readiness**: event protocol supports supervisor/worker orchestration.

This spec prioritizes UX + context lifecycle first, while sandbox hardening proceeds in parallel.

---

## 2) Architecture Principle

### One Engine, One Timeline, One Source of Truth

- **Single execution authority**: one backend engine owns model turn execution, tool invocation, approvals, compaction, and persistence.
- **Desktop/CLI are clients**: UI renders event stream; does not own independent orchestration logic.
- **Unified event schema**: all views (chat, timeline, approvals, artifacts, logs) derive from `SessionEvent`.

---

## 3) SessionEvent V2 Protocol (Canonical)

All session behavior is represented as append-only events.

## Event envelope

```json
{
  "event_id": "evt_...",
  "session_id": "ses_...",
  "turn_id": "turn_...",
  "run_id": "run_...",
  "correlation_id": "corr_...",
  "agent_id": "agent_main",
  "parent_agent_id": null,
  "kind": "turn.started",
  "ts": "2026-03-08T12:34:56.789Z",
  "payload": {},
  "seq": 1024
}
```

Fields:
- `seq` is monotonic per session (strict ordering).
- `turn_id` groups a single user turn lifecycle.
- `run_id` groups one end-user send action.
- `correlation_id` links tool/approval/artifact sub-events.
- `agent_id` reserved for future multi-agent.

## Required event kinds (V2)

### Turn lifecycle
- `turn.started`
- `turn.context_budget`
- `turn.compaction.started`
- `turn.compaction.completed`
- `turn.compaction.failed`
- `turn.completed`
- `turn.failed`

### Model lifecycle
- `model.request.started`
- `model.request.completed`
- `model.stream.chunk`
- `model.stream.completed`

### Tool lifecycle
- `tool.call.started`
- `tool.call.awaiting_approval`
- `tool.call.approved`
- `tool.call.rejected`
- `tool.call.completed`
- `tool.call.failed`

### Artifact / patch / rollback
- `artifact.created`
- `artifact.rollback.started`
- `artifact.rollback.completed`
- `artifact.rollback.failed`

### Memory/context changes
- `context.reference.updated`
- `context.settings.diff.injected`
- `memory.block.updated`

### Multi-agent reserved
- `agent.spawned`
- `agent.handoff`
- `agent.joined`
- `agent.failed`

---

## 4) ContextManager V2 (Codex-like behavior)

Implement a dedicated context lifecycle manager with these responsibilities.

## 4.1 History normalization invariants

Before prompt assembly:

1. Every tool/function call must have an output record.
2. Orphan outputs are removed (or converted to explicit error item).
3. Unsupported modalities are normalized (e.g., image placeholders).
4. Context history remains model-visible consistent.

Reference behavior to mirror: codex `context_manager/history + normalize` style.

## 4.2 Token budget tracking

For each turn, emit:

- total estimated tokens in visible context
- newly added tokens since last successful response
- context window limit
- compaction trigger reason

Event:
- `turn.context_budget` payload includes
  - `estimated_total_tokens`
  - `window_tokens`
  - `threshold`
  - `will_compact` (bool)

## 4.3 Compaction strategy

Two modes:

1. **Manual compact** (`/compact` / UI action)
2. **Auto compact** (token threshold reached)

Compaction contract:

- emit `turn.compaction.started`
- produce summary item with prefix marker
- replace old context slice with compacted summary + required anchors
- emit `turn.compaction.completed` with before/after token estimates

On failure:

- emit `turn.compaction.failed`
- fallback to no-compaction turn execution (unless over hard limit)

## 4.4 Turn-context diff injection

When runtime settings changed between turns, inject only diffs, not full re-injection:

- cwd/env changes
- approval policy changes
- sandbox policy changes
- collaboration/mode changes

Event:
- `context.settings.diff.injected` with changed keys.

---

## 5) Recoverability Model (Resume/Fork/Rollback)

Session must support deterministic recovery from persisted data only.

## 5.1 Resume

- Resume from latest committed `turn.completed` boundary.
- Rehydrate context from persisted compacted history + memory blocks + settings snapshot.

## 5.2 Fork

- Fork from any turn boundary (`turn_id`).
- Child session inherits normalized history up to boundary.
- New session emits `session.forked` (optional V2.1) or metadata in `turn.started`.

## 5.3 Rollback

- Rollback always artifact-driven using persisted rollback metadata.
- Must produce rollback lifecycle events.

## 5.4 Persistence requirements

Persist at least:

- append-only `session_events`
- normalized model-visible history snapshots (checkpointed)
- compaction summaries
- approvals decisions
- tool call args/results (with redaction policy)
- artifact metadata + integrity hash

---

## 6) UX Requirements (Desktop/CLI)

## 6.1 Timeline-first UI

UI panels are projections of same event log:

- Chat panel: user/assistant/system messages
- Trace panel: turn/item/tool lifecycle grouped by `turn_id` + `correlation_id`
- Approvals panel: pending + decisions
- Artifacts panel: patches/rollback bundles

No panel should rely on a separate hidden state machine.

## 6.2 Workflow visualization

Required improvements:

1. Turn tree view: each turn expandable into model/tool/approval/artifact nodes.
2. Correlation lanes: group related tool call + approval + artifact.
3. Failure root-cause jump: click failed node opens tool args/result/logs.
4. Replay mode: rebuild timeline from exported trace bundle.

## 6.3 Streaming and responsiveness

- Prefer push stream (SSE/WebSocket/stdio streaming) over polling for primary timeline path.
- If polling kept temporarily, it must read canonical event store only.

---

## 7) Multi-Agent Readiness (Phase-gated)

Do not implement full autonomous swarm yet. First build protocol capability:

1. `agent_id`, `parent_agent_id` on every event.
2. Reserved lifecycle events (`agent.spawned/joined/handoff/failed`).
3. Supervisor arbitration recorded in event payload.

Then phase into execution:

- Phase A: single-worker delegated tool runs.
- Phase B: bounded parallel workers (N<=3) with explicit join.
- Phase C: role-specialized agents with policy guardrails.

---

## 8) Mapping to Current CodingGirl (starting point)

Current strengths to keep:

- Timeline + workflow cards already exist in desktop.
- Approval queue + session-level permission caching already exist.
- Artifact persistence + rollback metadata already exist.
- Python side already has sqlite event/tool_call base.

Primary gaps to close:

1. Duplicate orchestration logic across layers.
2. Context compaction lifecycle is not first-class in timeline.
3. Resume/fork semantics not formalized against normalized history.
4. UI still partly polling/projection-based instead of canonical event-stream-based.

---

## 9) Two-Week Execution Plan

## Week 1 — SessionEvent V2 + timeline unification

Deliverables:

1. Finalize `SessionEvent` schema + event kind enums.
2. Build backend event append API + strict `seq` ordering.
3. Refactor desktop timeline/chat/approval/artifact views to consume canonical event stream.
4. Add turn tree + correlation grouping in trace panel.

Acceptance:

- One user send produces complete turn lifecycle events.
- Trace panel can reconstruct run end-to-end with no extra side channels.

## Week 2 — ContextManager V2 + recovery semantics

Deliverables:

1. Implement normalize + token budget + compact pipeline.
2. Emit context budget and compaction events.
3. Implement resume/fork from persisted boundaries.
4. Add integration tests for compact/resume/fork + rollback replay.

Acceptance:

- Long thread auto-compacts and remains coherent.
- Session can resume after restart with same visible timeline.
- Fork from historical turn generates deterministic child branch.

---

## 10) Non-Goals (for this phase)

- Full distributed multi-agent autonomy.
- Perfect tokenizer-accurate budgeting (estimate is acceptable first).
- Immediate replacement of all transport layers (protocol first, transport can iterate).

---

## 11) Definition of Done (DoD)

V2 is considered done only if:

1. **Observable**: every action appears in timeline with stable ordering + correlation.
2. **Compactable**: context compaction is evented, measurable, and test-covered.
3. **Recoverable**: resume/fork/rollback are deterministic from persisted data.
4. **Extensible**: event schema supports multi-agent without breaking compatibility.
