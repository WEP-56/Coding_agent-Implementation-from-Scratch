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

export async function listRepos(): Promise<RepoItem[]> {
  if (!isTauriRuntime()) return mock.listRepos();
  return invoke<RepoItem[]>("list_repos");
}

export async function listSessions(repoId: string): Promise<SessionItem[]> {
  if (!isTauriRuntime()) return mock.listSessions(repoId);
  return invoke<SessionItem[]>("list_sessions", { repoId });
}

export async function getTimeline(sessionId: string): Promise<TimelineStep[]> {
  if (!isTauriRuntime()) return mock.getTimeline(sessionId);
  const items = await invoke<TimelineStep[]>("get_timeline", { sessionId });
  return items.map(normalizeTimelineItem);
}

export async function getSessionEvents(
  sessionId: string,
): Promise<SessionEvent[]> {
  if (!isTauriRuntime()) return [];
  return invoke<SessionEvent[]>("get_session_events", { sessionId });
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

export async function listSessionRuns(
  sessionId: string,
): Promise<SessionRun[]> {
  if (!isTauriRuntime()) return [];
  return invoke<SessionRun[]>("list_session_runs", { sessionId });
}

export async function listSessionTurns(
  sessionId: string,
): Promise<SessionTurn[]> {
  if (!isTauriRuntime()) return [];
  return invoke<SessionTurn[]>("list_session_turns", { sessionId });
}

export async function getDiffFiles(sessionId: string): Promise<DiffFile[]> {
  if (!isTauriRuntime()) return mock.getDiffFiles(sessionId);
  return invoke<DiffFile[]>("get_diff_files", { sessionId });
}

export async function getToolCalls(sessionId: string): Promise<ToolCallItem[]> {
  if (!isTauriRuntime()) return mock.getToolCalls(sessionId);
  const items = await invoke<ToolCallItem[]>("get_tool_calls", { sessionId });
  return items.map((x) => ({
    ...x,
    status: normalizeToolStatus(String(x.status)),
  }));
}

export async function getLogs(sessionId: string): Promise<LogItem[]> {
  if (!isTauriRuntime()) return mock.getLogs(sessionId);
  const items = await invoke<LogItem[]>("get_logs", { sessionId });
  return items.map((x) => ({
    ...x,
    level: normalizeLogLevel(String(x.level)),
  }));
}

export async function getArtifacts(sessionId: string): Promise<ArtifactItem[]> {
  if (!isTauriRuntime()) return mock.getArtifacts(sessionId);
  const items = await invoke<ArtifactItem[]>("get_artifacts", { sessionId });
  return items.map((x) => ({
    ...x,
    kind: normalizeArtifactKind(String(x.kind)),
  }));
}

export async function getApprovalMeta(
  sessionId: string,
): Promise<ApprovalMeta> {
  if (!isTauriRuntime()) return mock.getApprovalMeta(sessionId);
  const meta = await invoke<ApprovalMeta>("get_approval_meta", { sessionId });
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
  return invoke<RunSessionResult>("run_session_message", {
    sessionId,
    mode,
    text,
  });
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
  return invoke<SessionItem>("create_session", { repoId, title, mode });
}

export async function deleteSession(sessionId: string): Promise<void> {
  if (!isTauriRuntime()) return;
  await invoke("delete_session", { sessionId });
}

export async function updateSessionMode(
  sessionId: string,
  mode: string,
): Promise<void> {
  if (!isTauriRuntime()) return;
  await invoke("update_session_mode", { sessionId, mode });
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
  await invoke("remove_repo", { repoId });
}

export async function toggleRepoPin(repoId: string): Promise<void> {
  if (!isTauriRuntime()) return;
  await invoke("toggle_repo_pin", { repoId });
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
          model: { provider: "mock", model: "mock-1", baseUrl: "", apiKey: "" },
          rulesByRepo: {},
        };
      }
      return JSON.parse(raw) as AppSettings;
    } catch {
      return {
        notificationsEnabled: true,
        defaultSessionMode: "build",
        defaultTheme: "dark",
        model: { provider: "mock", model: "mock-1", baseUrl: "", apiKey: "" },
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
  await invoke("toggle_plugin_enabled", { pluginId });
}

export async function removePlugin(pluginId: string): Promise<void> {
  if (!isTauriRuntime()) {
    const current = await listPlugins();
    const next = current.filter((p) => p.id !== pluginId);
    window.localStorage.setItem(PLUGINS_KEY, JSON.stringify(next));
    return;
  }
  await invoke("remove_plugin", { pluginId });
}

export async function listRepoTree(
  sessionId: string,
): Promise<RepoTreeEntry[]> {
  if (!isTauriRuntime()) return [];
  return invoke<RepoTreeEntry[]>("list_repo_tree", { sessionId });
}

export async function readRepoFile(
  sessionId: string,
  path: string,
): Promise<RepoFileContent> {
  if (!isTauriRuntime()) {
    return { path, content: "web 模式下不可读取本地文件。", truncated: false };
  }
  return invoke<RepoFileContent>("read_repo_file", { sessionId, path });
}

export async function writeRepoFile(
  sessionId: string,
  path: string,
  content: string,
): Promise<void> {
  if (!isTauriRuntime()) return;
  await invoke("write_repo_file", { sessionId, path, content });
}

export async function writeRepoFileAtomic(
  sessionId: string,
  path: string,
  content: string,
  ifMatchSha256?: string,
): Promise<string> {
  if (!isTauriRuntime()) return "";
  return invoke<string>("write_repo_file_atomic", {
    sessionId,
    path,
    content,
    ifMatchSha256,
  });
}

export async function rollbackPatchArtifact(
  sessionId: string,
  rollbackMetaPath: string,
): Promise<void> {
  if (!isTauriRuntime()) return;
  await invoke("rollback_patch_artifact", { sessionId, rollbackMetaPath });
}

export async function searchRepo(
  sessionId: string,
  pattern: string,
  maxResults?: number,
): Promise<string[]> {
  if (!isTauriRuntime()) return [];
  return invoke<string[]>("search_repo", { sessionId, pattern, maxResults });
}

export async function getChatHistory(
  sessionId: string,
): Promise<{ role: string; content: string }[]> {
  if (!isTauriRuntime()) return [];
  return invoke<{ role: string; content: string }[]>("get_chat_history", {
    sessionId,
  });
}

export async function getChatSummary(sessionId: string): Promise<string> {
  if (!isTauriRuntime()) return "";
  return invoke<string>("get_chat_summary", { sessionId });
}

export async function getSessionContextDebug(
  sessionId: string,
): Promise<SessionContextDebugSnapshot | null> {
  if (!isTauriRuntime()) return null;
  return invoke<SessionContextDebugSnapshot>("get_session_context_debug", {
    sessionId,
  });
}

export async function runTerminalCommand(
  sessionId: string,
  command: string,
  cwd?: string,
): Promise<TerminalCommandResult> {
  if (!isTauriRuntime()) {
    throw new Error("Terminal is only available in desktop runtime.");
  }
  return invoke<TerminalCommandResult>("run_terminal_command", {
    sessionId,
    command,
    cwd,
  });
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
  return invoke<ApprovalRequest[]>("list_pending_approvals", { sessionId });
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
  return invoke<ApprovalRequest>("approve_request", {
    sessionId,
    approvalId,
    note,
    allowSession,
  });
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
  return invoke<ApprovalRequest>("reject_request", {
    sessionId,
    approvalId,
    note,
  });
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
  return invoke<
    Array<{
      sessionId: string;
      toolName: string;
      action: string;
      path?: string;
      grantedAt: string;
    }>
  >("list_session_permissions", { sessionId });
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
  return invoke<{ filePath: string; bundle: TraceBundle }>(
    "export_trace_bundle",
    { sessionId },
  );
}

export async function listMemoryBlocks(
  sessionId: string,
): Promise<MemoryBlock[]> {
  if (!isTauriRuntime()) return [];
  return invoke<MemoryBlock[]>("list_memory_blocks", { sessionId });
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
  return invoke<MemoryBlock>("set_memory_block", {
    sessionId: input.sessionId,
    scope: input.scope,
    label: input.label,
    content: input.content,
    description: input.description,
    readOnly: input.readOnly,
    limit: input.limit,
  });
}
