export type SessionMode = "plan" | "build" | "auto";
export type SensitiveAction = "install_dependency" | "run_shell";
export type SensitivePolicy = "ask" | "allow" | "deny";

export const TOOL_POLICY_KEYS = [
  "apply_patch",
  "repo_apply_unified_diff",
  "repo_write_file_atomic",
  "repo_read_file",
  "repo_search",
  "repo_list_tree",
  "memory_set",
  "memory_list",
] as const;

export type ToolPolicyKey = (typeof TOOL_POLICY_KEYS)[number];

export interface RepoItem {
  id: string;
  name: string;
  path: string;
  pinned: boolean;
}

export interface SessionItem {
  id: string;
  repoId: string;
  title: string;
  mode: SessionMode;
  createdAt: string;
  updatedAt: string;
  summary?: string;
}

export interface TimelineStep {
  id: string;
  title: string;
  status: "pending" | "running" | "success" | "failed";
  detail?: string;
  traceType?: string;
  ts?: string;
  correlationId?: string;
  eventKind?: string;
  turnId?: string;
  runId?: string;
  itemId?: string;
  itemType?: string;
  sequence?: number;
  agentId?: string;
  parentAgentId?: string;
}

export interface SessionEvent {
  eventId: string;
  sessionId: string;
  turnId?: string;
  runId?: string;
  correlationId?: string;
  agentId?: string;
  parentAgentId?: string;
  kind: string;
  title: string;
  status: "pending" | "running" | "success" | "failed";
  detail?: string;
  traceType?: string;
  itemId?: string;
  itemType?: string;
  ts: string;
  seq: number;
}

export interface SessionStateChangedEvent {
  sessionId: string;
  reason: string;
  runId?: string | null;
  turnId?: string | null;
  changedAt: string;
}

export interface PythonTodoStats {
  total: number;
  pending: number;
  inProgress: number;
  completed: number;
}

export interface PythonTodoItem {
  stepId: string;
  title: string;
  status: "pending" | "in_progress" | "completed";
  activeForm?: string | null;
}

export interface PythonTodoState {
  updatedAt: string;
  stats: PythonTodoStats;
  items: PythonTodoItem[];
  rendered?: string | null;
  runId?: string | null;
  turnId?: string | null;
}

export interface SessionWorkflowSnapshotEvent {
  sessionId: string;
  reason: string;
  runId?: string | null;
  turnId?: string | null;
  changedAt: string;
  timeline: TimelineStep[];
  diffFiles: DiffFile[];
  toolCalls: ToolCallItem[];
  logs: LogItem[];
  artifacts: ArtifactItem[];
  sessionRuns: SessionRun[];
  sessionTurns: SessionTurn[];
  pendingApprovals: ApprovalRequest[];
  pythonTodo?: PythonTodoState | null;
}

export interface ContextBudgetStats {
  historyChars: number;
  summaryChars: number;
  memoryChars: number;
  visibleTurns: number;
  maxVisibleHistory: number;
}

export interface ContextTokenBreakdown {
  historyTokens: number;
  summaryTokens: number;
  memoryTokens: number;
  prunedToolOutputTokens: number;
  totalTokens: number;
}

export interface HistoryNormalizationStats {
  totalTurns: number;
  keptTurns: number;
  droppedInvalidRoles: number;
  droppedEmptyTurns: number;
}

export interface ContextCompactionStats {
  applied: boolean;
  wouldApply: boolean;
  droppedTurns: number;
  keptRecent: number;
  summaryEntriesAdded: number;
  preCompactionTurns: number;
  postCompactionTurns: number;
}

export interface ContextDebugTurn {
  role: "user" | "assistant" | "system";
  content: string;
  chars: number;
}

export interface ContextDebugMemoryBlock {
  label: string;
  scope: string;
  description?: string | null;
  limit: number;
  readOnly: boolean;
  updatedAt: string;
  chars: number;
  contentPreview: string;
}

export interface SessionContextDebugSnapshot {
  sessionId: string;
  historyCount: number;
  visibleHistory: ContextDebugTurn[];
  summary: string;
  memoryBlocks: ContextDebugMemoryBlock[];
  estimatedTokens: number;
  compacted: boolean;
  budget: ContextBudgetStats;
  tokenBreakdown: ContextTokenBreakdown;
  normalization: HistoryNormalizationStats;
  compaction: ContextCompactionStats;
  prune: {
    applied: boolean;
    prunedTurns: number;
    charsRemoved: number;
    keptChars: number;
  };
  recentFailures: ContextDebugTurn[];
}

export interface TerminalCommandResult {
  command: string;
  cwd: string;
  stdout: string;
  stderr: string;
  exitCode: number;
  success: boolean;
  runId?: string;
  turnId?: string;
}

export type DetailTab = "diff" | "tools" | "logs" | "artifacts";

export interface LayoutPreferences {
  leftWidth: number;
  rightWidth: number;
  detailTab: DetailTab;
  leftView: "repo" | "global";
}

export type DiffViewMode = "split" | "unified";

export type MutationSourceKind =
  | "apply_patch"
  | "unified_diff"
  | "direct_write"
  | "approval_replay"
  | "rollback";

export interface MutationProvenance {
  sourceKind: MutationSourceKind;
  toolName: string;
  sessionId: string;
  runId?: string | null;
  correlationId?: string | null;
  artifactGroupId?: string | null;
  rollbackMetaPath?: string | null;
  approvalId?: string | null;
  createdAt: string;
}

export interface DiffFile {
  id: string;
  path: string;
  runId?: string;
  additions: number;
  deletions: number;
  oldSnippet: string;
  newSnippet: string;
  unifiedSnippet: string;
  diff: string;
  mutationProvenance?: MutationProvenance | null;
}

export interface ApprovalMeta {
  fileCount: number;
  additions: number;
  deletions: number;
  risk: "low" | "medium" | "high";
  repoName: string;
  branch: string;
}

export interface RunSessionResult {
  runId: string;
  turnId: string;
  status: "running" | "success" | "failed";
  assistantMessage: string;
  timeline: TimelineStep[];
}

export interface SessionRun {
  id: string;
  sessionId: string;
  turnId: string;
  mode: string;
  userText: string;
  assistantMessage?: string | null;
  errorText?: string | null;
  status: "running" | "success" | "failed";
  createdAt: string;
  updatedAt: string;
  completedAt?: string | null;
}

export type SessionTurnItemKind =
  | "user_message"
  | "assistant_message"
  | "error"
  | "reasoning"
  | "phase"
  | "context"
  | "compaction"
  | "model_request"
  | "validation"
  | "command"
  | "tool_call"
  | "diff"
  | "approval"
  | "artifact";

export type ErrorCategory =
  | "transport"
  | "provider"
  | "model"
  | "routing"
  | "tool"
  | "approval"
  | "validation"
  | "rollback"
  | "command"
  | "unknown";

export interface SessionTurnItem {
  id: string;
  turnId: string;
  runId?: string;
  kind: SessionTurnItemKind;
  status: "pending" | "running" | "success" | "failed";
  title: string;
  summary?: string | null;
  detail?: string | null;
  toolName?: string | null;
  path?: string | null;
  correlationId?: string | null;
  dataJson?: string | null;
  errorCategory?: ErrorCategory | null;
  errorCode?: string | null;
  retryable?: boolean | null;
  retryHint?: string | null;
  fallbackHint?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface SessionTurn {
  id: string;
  sessionId: string;
  runId?: string | null;
  mode: string;
  route?: string | null;
  routeSource?: string | null;
  routeReason?: string | null;
  routeSignals: string[];
  userText?: string | null;
  status: "running" | "success" | "failed";
  items: SessionTurnItem[];
  createdAt: string;
  updatedAt: string;
  completedAt?: string | null;
}

export interface ModelConfig {
  provider: "mock" | "openai-compatible";
  model: string;
  baseUrl: string;
  apiKey: string;
}

export interface AppSettings {
  notificationsEnabled: boolean;
  defaultSessionMode: SessionMode;
  defaultTheme: "light" | "dark";
  model: ModelConfig;
  rulesByRepo: Record<string, { content: string; updatedAt: string }>;
}

export interface SecurityPolicies {
  // Back-compat: old UI only wrote SensitiveAction keys.
  // New UI can also write per-tool keys (e.g., apply_patch, repo_apply_unified_diff).
  policiesByRepo: Record<string, Record<string, SensitivePolicy>>;
}

export interface PluginItem {
  id: string;
  name: string;
  sourcePath: string;
  enabled: boolean;
  importedAt: string;
}

export interface ToolCallItem {
  id: string;
  name: string;
  runId?: string;
  status: "success" | "failed" | "running";
  durationMs: number;
  argsJson: string;
  resultJson: string;
  input?: unknown;
  output?: string;
  correlationId?: string;
}

export type LogLevel = "info" | "warn" | "error" | "debug";

export interface LogItem {
  id: string;
  ts: string;
  level: LogLevel;
  source: string;
  message: string;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  message: string;
}

export interface ArtifactItem {
  id: string;
  name: string;
  kind: "patch" | "report" | "index" | "trace";
  runId?: string;
  filePath: string;
  sizeKb: number;
  createdAt: string;
  correlationId?: string;
  sha256?: string;
  provenance?: string;
  mutationProvenance?: MutationProvenance | null;
}

export interface TraceBundle {
  sessionId: string;
  exportedAt: string;
  projection?: {
    timelineSource: "session_turn_items" | "session_events" | "cached_timeline";
    canonicalTurnCount: number;
    canonicalItemCount: number;
    legacyEventCount: number;
  };
  sessionRuns: SessionRun[];
  sessionTurns?: SessionTurn[];
  canonicalItems?: SessionTurnItem[];
  sessionEvents: SessionEvent[];
  legacySessionEvents?: SessionEvent[];
  timeline: TimelineStep[];
  toolCalls: ToolCallItem[];
  approvals: ApprovalRequest[];
  artifacts: ArtifactItem[];
  sessionPermissions: Array<{
    sessionId: string;
    toolName: string;
    action: string;
    path?: string;
    grantedAt: string;
  }>;
}

export interface ChatMessage {
  id: string;
  sessionId: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: string;
}

export interface WorkflowSnapshot {
  diffFiles: DiffFile[];
  toolCalls: ToolCallItem[];
  logs: LogItem[];
  artifacts: ArtifactItem[];
}

export interface WorkflowRunCard {
  id: string;
  sessionId: string;
  userText: string;
  assistantText?: string;
  createdAt: string;
  timeline: TimelineStep[];
  diffFiles: DiffFile[];
  toolCalls: ToolCallItem[];
  logs: LogItem[];
  artifacts: ArtifactItem[];
  errorText?: string;
}

export interface RepoTreeEntry {
  path: string;
  displayName: string;
  isDir: boolean;
  size?: number;
}

export interface RepoFileContent {
  path: string;
  content: string;
  truncated: boolean;
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
