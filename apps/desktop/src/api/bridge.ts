import { invoke } from "@tauri-apps/api/core";

import type {
  ApprovalMeta,
  ArtifactItem,
  DiffFile,
  LogItem,
  RepoItem,
  RunSessionResult,
  AppSettings,
  SecurityPolicies,
  PluginItem,
  SessionItem,
  SessionStateChangedEvent,
  SessionWorkflowSnapshotEvent,
  RepoTreeEntry,
  RepoFileContent,
  SessionRun,
  SessionTurn,
  SessionContextDebugSnapshot,
  TerminalCommandResult,
  TimelineStep,
  SessionEvent,
  ToolCallItem,
  TraceBundle,
} from "../types/models";
import { isTauriRuntime } from "../lib/platform";
import * as mock from "./mock";

const SETTINGS_KEY = "codinggirl.settings";
const SECURITY_KEY = "codinggirl.security.policies";
const PLUGINS_KEY = "codinggirl.plugins";

async function invokeCompat<T>(
  command: string,
  primaryArgs?: Record<string, unknown>,
  fallbackArgs?: Record<string, unknown>,
): Promise<T> {
  const isArgError = (err: unknown): boolean => {
    const message =
      typeof err === "string"
        ? err
        : err instanceof Error
          ? err.message
          : String(err);
    return /invalid args|missing required key|unknown field|unexpected key/i.test(
      message,
    );
  };

  try {
    return await invoke<T>(command, primaryArgs);
  } catch (primaryError) {
    if (!fallbackArgs || !isArgError(primaryError)) throw primaryError;
    try {
      return await invoke<T>(command, fallbackArgs);
    } catch {
      throw primaryError;
    }
  }
}

function normalizeTimelineStatus(v: string): TimelineStep["status"] {
  return v === "pending" || v === "running" || v === "success" || v === "failed"
    ? v
    : "pending";
}

function normalizeTimelineItem(x: TimelineStep): TimelineStep {
  return {
    ...x,
    status: normalizeTimelineStatus(String(x.status)),
  };
}

function normalizeToolStatus(v: string): ToolCallItem["status"] {
  return v === "success" || v === "failed" || v === "running" ? v : "running";
}

function normalizeLogLevel(v: string): LogItem["level"] {
  return v === "info" || v === "warn" || v === "error" || v === "debug"
    ? v
    : "info";
}

function normalizeArtifactKind(v: string): ArtifactItem["kind"] {
  return v === "patch" || v === "report" || v === "index" || v === "trace"
    ? v
    : "report";
}

function normalizeRisk(v: string): ApprovalMeta["risk"] {
  return v === "low" || v === "medium" || v === "high" ? v : "medium";
}

function normalizeProvider(v: string): AppSettings["model"]["provider"] {
  return v === "mock" || v === "openai-compatible" ? v : "mock";
}

function normalizeTimeoutSec(v: unknown): number {
  const num = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(num)) return 180;
  return Math.max(10, Math.min(900, Math.trunc(num)));
}

export async function listRepos(): Promise<RepoItem[]> {
  if (!isTauriRuntime()) return mock.listRepos();
  return invoke<RepoItem[]>("list_repos");
}

export async function listSessions(repoId: string): Promise<SessionItem[]> {
  if (!isTauriRuntime()) return mock.listSessions(repoId);
  return invokeCompat<SessionItem[]>(
    "list_sessions",
    { repoId },
    { repo_id: repoId },
  );
}

export async function getTimeline(sessionId: string): Promise<TimelineStep[]> {
  if (!isTauriRuntime()) return mock.getTimeline(sessionId);
  const items = await invokeCompat<TimelineStep[]>(
    "get_timeline",
    { sessionId },
    { session_id: sessionId },
  );
  return items.map(normalizeTimelineItem);
}

export async function getSessionEvents(
  sessionId: string,
): Promise<SessionEvent[]> {
  if (!isTauriRuntime()) return [];
  return invokeCompat<SessionEvent[]>(
    "get_session_events",
    { sessionId },
    { session_id: sessionId },
  );
}

export async function listenSessionStateChanged(
  handler: (event: SessionStateChangedEvent) => void,
): Promise<() => void> {
  if (!isTauriRuntime()) return () => undefined;
  const eventApi = await import("@tauri-apps/api/event");
  const unlisten = await eventApi.listen<SessionStateChangedEvent>(
    "session-state-changed",
    (event) => handler(event.payload),
  );
  return unlisten;
}

export async function listenSessionWorkflowSnapshot(
  handler: (event: SessionWorkflowSnapshotEvent) => void,
): Promise<() => void> {
  if (!isTauriRuntime()) return () => undefined;
  const eventApi = await import("@tauri-apps/api/event");
  const unlisten = await eventApi.listen<SessionWorkflowSnapshotEvent>(
    "session-workflow-snapshot",
    (event) => {
      const payload = event.payload;
      handler({
        ...payload,
        timeline: (payload.timeline ?? []).map(normalizeTimelineItem),
        toolCalls: (payload.toolCalls ?? []).map((x) => ({
          ...x,
          status: normalizeToolStatus(String(x.status)),
        })),
        logs: (payload.logs ?? []).map((x) => ({
          ...x,
          level: normalizeLogLevel(String(x.level)),
        })),
        artifacts: (payload.artifacts ?? []).map((x) => ({
          ...x,
          kind: normalizeArtifactKind(String(x.kind)),
        })),
      });
    },
  );
  return unlisten;
}

export async function listSessionRuns(
  sessionId: string,
): Promise<SessionRun[]> {
  if (!isTauriRuntime()) return [];
  return invokeCompat<SessionRun[]>(
    "list_session_runs",
    { sessionId },
    { session_id: sessionId },
  );
}

export async function listSessionTurns(
  sessionId: string,
): Promise<SessionTurn[]> {
  if (!isTauriRuntime()) return [];
  return invokeCompat<SessionTurn[]>(
    "list_session_turns",
    { sessionId },
    { session_id: sessionId },
  );
}

export async function getDiffFiles(sessionId: string): Promise<DiffFile[]> {
  if (!isTauriRuntime()) return mock.getDiffFiles(sessionId);
  return invokeCompat<DiffFile[]>(
    "get_diff_files",
    { sessionId },
    { session_id: sessionId },
  );
}

export async function getToolCalls(sessionId: string): Promise<ToolCallItem[]> {
  if (!isTauriRuntime()) return mock.getToolCalls(sessionId);
  const items = await invokeCompat<ToolCallItem[]>(
    "get_tool_calls",
    { sessionId },
    { session_id: sessionId },
  );
  return items.map((x) => ({
    ...x,
    status: normalizeToolStatus(String(x.status)),
  }));
}

export async function getLogs(sessionId: string): Promise<LogItem[]> {
  if (!isTauriRuntime()) return mock.getLogs(sessionId);
  const items = await invokeCompat<LogItem[]>(
    "get_logs",
    { sessionId },
    { session_id: sessionId },
  );
  return items.map((x) => ({
    ...x,
    level: normalizeLogLevel(String(x.level)),
  }));
}

export async function getArtifacts(sessionId: string): Promise<ArtifactItem[]> {
  if (!isTauriRuntime()) return mock.getArtifacts(sessionId);
  const items = await invokeCompat<ArtifactItem[]>(
    "get_artifacts",
    { sessionId },
    { session_id: sessionId },
  );
  return items.map((x) => ({
    ...x,
    kind: normalizeArtifactKind(String(x.kind)),
  }));
}

export async function getApprovalMeta(
  sessionId: string,
): Promise<ApprovalMeta> {
  if (!isTauriRuntime()) return mock.getApprovalMeta(sessionId);
  const meta = await invokeCompat<ApprovalMeta>(
    "get_approval_meta",
    { sessionId },
    { session_id: sessionId },
  );
  return { ...meta, risk: normalizeRisk(String(meta.risk)) };
}

export async function runSessionMessage(
  sessionId: string,
  mode: string,
  text: string,
): Promise<RunSessionResult> {
  if (!isTauriRuntime()) {
    return {
      runId: `mock-run-${Date.now()}`,
      turnId: `mock-turn-${Date.now()}`,
      status: "success",
      assistantMessage: `我已收到你的任务（${mode} 模式）：${text}`,
      timeline: await mock.getTimeline(sessionId),
    };
  }
  return invokeCompat<RunSessionResult>(
    "run_session_message",
    { sessionId, mode, text },
    { session_id: sessionId, mode, text },
  );
}

export async function runPythonAgentMessage(
  sessionId: string,
  mode: string,
  text: string,
): Promise<RunSessionResult> {
  if (!isTauriRuntime()) {
    return {
      runId: `mock-py-run-${Date.now()}`,
      turnId: `mock-py-turn-${Date.now()}`,
      status: "success",
      assistantMessage: `（mock）python agent 收到任务（${mode} 模式）：${text}`,
      timeline: await mock.getTimeline(sessionId),
    };
  }
  return invokeCompat<RunSessionResult>(
    "run_python_agent_message",
    { sessionId, mode, text },
    { session_id: sessionId, mode, text },
  );
}

export async function cancelPythonAgentRun(sessionId: string): Promise<boolean> {
  if (!isTauriRuntime()) return false;
  return invokeCompat<boolean>(
    "cancel_python_agent_run",
    { sessionId },
    { session_id: sessionId },
  );
}

export async function createSession(
  repoId: string,
  title: string,
  mode: string,
): Promise<SessionItem> {
  if (!isTauriRuntime()) {
    const id = `s-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const now = new Date().toISOString();
    return {
      id,
      repoId,
      title,
      mode: mode as SessionItem["mode"],
      createdAt: now,
      updatedAt: now,
    };
  }
  return invokeCompat<SessionItem>(
    "create_session",
    { repoId, title, mode },
    { repo_id: repoId, title, mode },
  );
}

export async function deleteSession(sessionId: string): Promise<void> {
  if (!isTauriRuntime()) return;
  await invokeCompat<void>(
    "delete_session",
    { sessionId },
    { session_id: sessionId },
  );
}

export async function updateSessionMode(
  sessionId: string,
  mode: string,
): Promise<void> {
  if (!isTauriRuntime()) return;
  await invokeCompat<void>(
    "update_session_mode",
    { sessionId, mode },
    { session_id: sessionId, mode },
  );
}

export async function addRepo(path: string): Promise<RepoItem> {
  if (!isTauriRuntime()) {
    const p = path.trim();
    const name =
      p.replace(/\\/g, "/").replace(/\/$/, "").split("/").pop() || "new-repo";
    return { id: `repo-${Date.now()}`, name, path: p, pinned: false };
  }
  return invoke<RepoItem>("add_repo", { path });
}

export async function removeRepo(repoId: string): Promise<void> {
  if (!isTauriRuntime()) return;
  await invokeCompat<void>("remove_repo", { repoId }, { repo_id: repoId });
}

export async function toggleRepoPin(repoId: string): Promise<void> {
  if (!isTauriRuntime()) return;
  await invokeCompat<void>("toggle_repo_pin", { repoId }, { repo_id: repoId });
}

export async function getSettings(): Promise<AppSettings> {
  if (!isTauriRuntime()) {
    try {
      const raw = window.localStorage.getItem(SETTINGS_KEY);
      if (!raw) {
        return {
          notificationsEnabled: true,
          defaultSessionMode: "build",
          defaultTheme: "dark",
          model: {
            provider: "mock",
            model: "mock-1",
            baseUrl: "",
            apiKey: "",
            timeoutSec: 180,
          },
          rulesByRepo: {},
        };
      }
      return JSON.parse(raw) as AppSettings;
    } catch {
      return {
        notificationsEnabled: true,
        defaultSessionMode: "build",
        defaultTheme: "dark",
        model: {
          provider: "mock",
          model: "mock-1",
          baseUrl: "",
          apiKey: "",
          timeoutSec: 180,
        },
        rulesByRepo: {},
      };
    }
  }
  const settings = await invoke<AppSettings>("get_settings");
  return {
    ...settings,
    model: {
      ...settings.model,
      provider: normalizeProvider(String(settings.model.provider)),
      timeoutSec: normalizeTimeoutSec((settings.model as { timeoutSec?: unknown }).timeoutSec),
    },
  };
}

export async function saveSettings(settings: AppSettings): Promise<void> {
  if (!isTauriRuntime()) {
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    return;
  }
  await invoke("save_settings", { settings });
}

export async function getSecurityPolicies(): Promise<SecurityPolicies> {
  if (!isTauriRuntime()) {
    try {
      const raw = window.localStorage.getItem(SECURITY_KEY);
      return {
        policiesByRepo: raw
          ? (JSON.parse(raw) as SecurityPolicies["policiesByRepo"])
          : {},
      };
    } catch {
      return { policiesByRepo: {} };
    }
  }
  return invoke<SecurityPolicies>("get_security_policies");
}

export async function saveSecurityPolicies(
  policies: SecurityPolicies,
): Promise<void> {
  if (!isTauriRuntime()) {
    window.localStorage.setItem(
      SECURITY_KEY,
      JSON.stringify(policies.policiesByRepo),
    );
    return;
  }
  await invoke("save_security_policies", { policies });
}

export async function listPlugins(): Promise<PluginItem[]> {
  if (!isTauriRuntime()) {
    try {
      const raw = window.localStorage.getItem(PLUGINS_KEY);
      return raw ? (JSON.parse(raw) as PluginItem[]) : [];
    } catch {
      return [];
    }
  }
  return invoke<PluginItem[]>("list_plugins");
}

export async function importPlugin(path: string): Promise<PluginItem> {
  if (!isTauriRuntime()) {
    const p = path.trim();
    const item: PluginItem = {
      id: `plugin-${Date.now()}`,
      name:
        p.replace(/\\/g, "/").replace(/\/$/, "").split("/").pop() || "plugin",
      sourcePath: p,
      enabled: true,
      importedAt: new Date().toISOString(),
    };
    const current = await listPlugins();
    const next = [item, ...current.filter((x) => x.sourcePath !== p)];
    window.localStorage.setItem(PLUGINS_KEY, JSON.stringify(next));
    return item;
  }
  return invoke<PluginItem>("import_plugin", { path });
}

export async function togglePluginEnabled(pluginId: string): Promise<void> {
  if (!isTauriRuntime()) {
    const current = await listPlugins();
    const next = current.map((p) =>
      p.id === pluginId ? { ...p, enabled: !p.enabled } : p,
    );
    window.localStorage.setItem(PLUGINS_KEY, JSON.stringify(next));
    return;
  }
  await invokeCompat<void>(
    "toggle_plugin_enabled",
    { pluginId },
    { plugin_id: pluginId },
  );
}

export async function removePlugin(pluginId: string): Promise<void> {
  if (!isTauriRuntime()) {
    const current = await listPlugins();
    const next = current.filter((p) => p.id !== pluginId);
    window.localStorage.setItem(PLUGINS_KEY, JSON.stringify(next));
    return;
  }
  await invokeCompat<void>("remove_plugin", { pluginId }, { plugin_id: pluginId });
}

export async function listRepoTree(
  sessionId: string,
): Promise<RepoTreeEntry[]> {
  if (!isTauriRuntime()) return [];
  return invokeCompat<RepoTreeEntry[]>(
    "list_repo_tree",
    { sessionId },
    { session_id: sessionId },
  );
}

export async function readRepoFile(
  sessionId: string,
  path: string,
): Promise<RepoFileContent> {
  if (!isTauriRuntime()) {
    return { path, content: "web 模式下不可读取本地文件。", truncated: false };
  }
  return invokeCompat<RepoFileContent>(
    "read_repo_file",
    { sessionId, path },
    { session_id: sessionId, path },
  );
}

export async function writeRepoFile(
  sessionId: string,
  path: string,
  content: string,
): Promise<void> {
  if (!isTauriRuntime()) return;
  await invokeCompat<void>(
    "write_repo_file",
    { sessionId, path, content },
    { session_id: sessionId, path, content },
  );
}

export async function writeRepoFileAtomic(
  sessionId: string,
  path: string,
  content: string,
  ifMatchSha256?: string,
): Promise<string> {
  if (!isTauriRuntime()) return "";
  return invokeCompat<string>(
    "write_repo_file_atomic",
    { sessionId, path, content, ifMatchSha256 },
    { session_id: sessionId, path, content, if_match_sha256: ifMatchSha256 },
  );
}

export async function rollbackPatchArtifact(
  sessionId: string,
  rollbackMetaPath: string,
): Promise<void> {
  if (!isTauriRuntime()) return;
  await invokeCompat<void>(
    "rollback_patch_artifact",
    { sessionId, rollbackMetaPath },
    { session_id: sessionId, rollback_meta_path: rollbackMetaPath },
  );
}

export async function searchRepo(
  sessionId: string,
  pattern: string,
  maxResults?: number,
): Promise<string[]> {
  if (!isTauriRuntime()) return [];
  return invokeCompat<string[]>(
    "search_repo",
    { sessionId, pattern, maxResults },
    { session_id: sessionId, pattern, max_results: maxResults },
  );
}

export async function getChatHistory(
  sessionId: string,
): Promise<{ role: string; content: string }[]> {
  if (!isTauriRuntime()) return [];
  return invokeCompat<{ role: string; content: string }[]>(
    "get_chat_history",
    { sessionId },
    { session_id: sessionId },
  );
}

export async function getChatSummary(sessionId: string): Promise<string> {
  if (!isTauriRuntime()) return "";
  return invokeCompat<string>(
    "get_chat_summary",
    { sessionId },
    { session_id: sessionId },
  );
}

export async function getSessionContextDebug(
  sessionId: string,
): Promise<SessionContextDebugSnapshot | null> {
  if (!isTauriRuntime()) return null;
  return invokeCompat<SessionContextDebugSnapshot>(
    "get_session_context_debug",
    { sessionId },
    { session_id: sessionId },
  );
}

export async function runTerminalCommand(
  sessionId: string,
  command: string,
  cwd?: string,
): Promise<TerminalCommandResult> {
  if (!isTauriRuntime()) {
    throw new Error("Terminal is only available in desktop runtime.");
  }
  return invokeCompat<TerminalCommandResult>(
    "run_terminal_command",
    { sessionId, command, cwd },
    { session_id: sessionId, command, cwd },
  );
}

export async function openPathInExplorer(path: string): Promise<void> {
  if (!isTauriRuntime()) {
    throw new Error(
      "Explorer integration is only available in desktop runtime.",
    );
  }
  await invoke("open_path_in_explorer", { path });
}

export async function openPathInVscode(path: string): Promise<void> {
  if (!isTauriRuntime()) {
    throw new Error(
      "VS Code integration is only available in desktop runtime.",
    );
  }
  await invoke("open_path_in_vscode", { path });
}

export interface MemoryBlock {
  label: string;
  scope: string;
  description?: string | null;
  limit: number;
  readOnly: boolean;
  content: string;
  updatedAt: string;
}

export interface ApprovalRequest {
  id: string;
  sessionId: string;
  runId?: string;
  toolName: string;
  action: string;
  path?: string;
  argsJson: string;
  createdAt: string;
  status: "pending" | "approved" | "rejected" | "failed";
  decisionNote?: string;
  resultJson?: string;
  allowSession?: boolean;
}

export async function listPendingApprovals(
  sessionId: string,
): Promise<ApprovalRequest[]> {
  if (!isTauriRuntime()) return [];
  return invokeCompat<ApprovalRequest[]>(
    "list_pending_approvals",
    { sessionId },
    { session_id: sessionId },
  );
}

export async function approveRequest(
  sessionId: string,
  approvalId: string,
  note?: string,
  allowSession?: boolean,
): Promise<ApprovalRequest> {
  if (!isTauriRuntime()) {
    return {
      id: approvalId,
      sessionId,
      runId: undefined,
      toolName: "",
      action: "",
      path: "",
      argsJson: "{}",
      createdAt: new Date().toISOString(),
      status: "approved",
      decisionNote: note,
      resultJson: "{}",
      allowSession,
    };
  }
  return invokeCompat<ApprovalRequest>(
    "approve_request",
    { sessionId, approvalId, note, allowSession },
    {
      session_id: sessionId,
      approval_id: approvalId,
      note,
      allow_session: allowSession,
    },
  );
}

export async function rejectRequest(
  sessionId: string,
  approvalId: string,
  note?: string,
): Promise<ApprovalRequest> {
  if (!isTauriRuntime()) {
    return {
      id: approvalId,
      sessionId,
      runId: undefined,
      toolName: "",
      action: "",
      path: "",
      argsJson: "{}",
      createdAt: new Date().toISOString(),
      status: "rejected",
      decisionNote: note,
      resultJson: "{}",
      allowSession: false,
    };
  }
  return invokeCompat<ApprovalRequest>(
    "reject_request",
    { sessionId, approvalId, note },
    { session_id: sessionId, approval_id: approvalId, note },
  );
}

export async function listSessionPermissions(
  sessionId: string,
): Promise<
  Array<{
    sessionId: string;
    toolName: string;
    action: string;
    path?: string;
    grantedAt: string;
  }>
> {
  if (!isTauriRuntime()) return [];
  return invokeCompat<
    Array<{
      sessionId: string;
      toolName: string;
      action: string;
      path?: string;
      grantedAt: string;
    }>
  >("list_session_permissions", { sessionId }, { session_id: sessionId });
}

export async function exportTraceBundle(
  sessionId: string,
): Promise<{ filePath: string; bundle: TraceBundle }> {
  if (!isTauriRuntime()) {
    return {
      filePath: `trace-${sessionId}.json`,
      bundle: {
        sessionId,
        exportedAt: new Date().toISOString(),
        sessionRuns: [],
        sessionEvents: [],
        timeline: [],
        toolCalls: [],
        approvals: [],
        artifacts: [],
        sessionPermissions: [],
      },
    };
  }
  return invokeCompat<{ filePath: string; bundle: TraceBundle }>(
    "export_trace_bundle",
    { sessionId },
    { session_id: sessionId },
  );
}

export async function listMemoryBlocks(
  sessionId: string,
): Promise<MemoryBlock[]> {
  if (!isTauriRuntime()) return [];
  return invokeCompat<MemoryBlock[]>(
    "list_memory_blocks",
    { sessionId },
    { session_id: sessionId },
  );
}

export async function setMemoryBlock(input: {
  sessionId: string;
  scope: "global" | "project";
  label: string;
  content: string;
  description?: string;
  readOnly?: boolean;
  limit?: number;
}): Promise<MemoryBlock> {
  if (!isTauriRuntime()) {
    return {
      label: input.label,
      scope: input.scope,
      description: input.description ?? null,
      limit: input.limit ?? 2000,
      readOnly: input.readOnly ?? false,
      content: input.content,
      updatedAt: new Date().toISOString(),
    };
  }
  return invokeCompat<MemoryBlock>(
    "set_memory_block",
    {
      sessionId: input.sessionId,
      scope: input.scope,
      label: input.label,
      content: input.content,
      description: input.description,
      readOnly: input.readOnly,
      limit: input.limit,
    },
    {
      session_id: input.sessionId,
      scope: input.scope,
      label: input.label,
      content: input.content,
      description: input.description,
      read_only: input.readOnly,
      limit: input.limit,
    },
  );
}
