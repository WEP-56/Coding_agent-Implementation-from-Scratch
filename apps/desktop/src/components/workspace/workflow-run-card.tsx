import { useMemo, useState } from "react";

import { cn } from "../../lib/utils";
import type {
  ApprovalRequest,
  DiffFile,
  ErrorCategory,
  MutationProvenance,
  SessionRun,
  SessionTurn,
  SessionTurnItem,
  TimelineStep,
  ToolCallItem,
} from "../../types/models";
import { DiffCodeBlock } from "../detail/diff-code-block";

type WorkflowTab = "workflow" | "diff" | "tools";
type WorkflowEntryType = "run" | "modify";

interface WorkflowEntry {
  id: string;
  type: WorkflowEntryType;
  status: "pending" | "running" | "success" | "failed";
  badge: string;
  title: string;
  summary: string;
  meta?: string;
  detail?: string;
}

interface WorkflowRunCardProps {
  run: SessionRun;
  turn?: SessionTurn;
  timeline: TimelineStep[];
  diffFiles: DiffFile[];
  toolCalls: ToolCallItem[];
  defaultCollapsed?: boolean;
  pendingApprovals?: ApprovalRequest[];
  onApprove?: (approvalId: string, allowSession?: boolean) => void;
  onReject?: (approvalId: string) => void;
}

function parseTurnData<T>(item: SessionTurnItem): T | null {
  if (!item.dataJson) return null;
  try {
    return JSON.parse(item.dataJson) as T;
  } catch {
    return null;
  }
}

function errorCategoryLabel(category?: ErrorCategory | null): string | null {
  switch (category) {
    case "transport":
      return "传输错误";
    case "provider":
      return "Provider 错误";
    case "model":
      return "模型错误";
    case "routing":
      return "路由错误";
    case "tool":
      return "工具错误";
    case "approval":
      return "审批错误";
    case "validation":
      return "校验错误";
    case "rollback":
      return "回滚错误";
    case "command":
      return "命令错误";
    case "unknown":
      return "未知错误";
    default:
      return null;
  }
}

function withErrorTaxonomy(summary: string, item: SessionTurnItem): string {
  const category = errorCategoryLabel(item.errorCategory);
  const qualifiers = [
    category,
    item.retryable ? "可重试" : null,
    item.errorCode ?? null,
  ].filter(Boolean);
  if (qualifiers.length === 0) return summary;
  return `[${qualifiers.join(" · ")}] ${summary}`;
}

function diffFileFromTurnItem(item: SessionTurnItem): DiffFile {
  const parsed = parseTurnData<DiffFile>(item);
  if (parsed && typeof parsed.path === "string") {
    return parsed;
  }
  return {
    id: item.id,
    path: item.path ?? item.title,
    runId: item.runId,
    additions: 0,
    deletions: 0,
    oldSnippet: "",
    newSnippet: "",
    unifiedSnippet: item.detail ?? "",
    diff: item.detail ?? "",
  };
}

function summarizeToolArgs(tool: ToolCallItem): string {
  try {
    const parsed = JSON.parse(tool.argsJson) as Record<string, unknown>;
    const path = typeof parsed.path === "string" ? parsed.path : "";
    const pattern = typeof parsed.pattern === "string" ? parsed.pattern : "";
    if (path) return path;
    if (pattern) return `搜索 ${pattern}`;
    return tool.name;
  } catch {
    return tool.name;
  }
}

function friendlyToolName(name: string): string {
  const mapping: Record<string, string> = {
    apply_patch: "应用补丁",
    repo_apply_unified_diff: "应用补丁",
    repo_write_file_atomic: "写入文件",
    repo_read_file: "读取文件",
    repo_search: "搜索仓库",
    repo_list_tree: "浏览文件树",
    memory_set: "更新记忆",
    memory_list: "读取记忆",
  };
  return mapping[name] ?? name;
}

function extractToolContent(raw: string): unknown {
  try {
    const parsed = JSON.parse(raw) as { content?: string };
    if (typeof parsed.content !== "string") return parsed;
    try {
      return JSON.parse(parsed.content);
    } catch {
      return parsed.content;
    }
  } catch {
    return raw;
  }
}

function summarizeToolResult(tool: ToolCallItem): string {
  const payload = extractToolContent(tool.resultJson);
  if (typeof payload === "string") {
    return payload.slice(0, 180);
  }
  if (!payload || typeof payload !== "object") {
    return tool.status === "failed" ? "执行失败" : "执行完成";
  }
  const record = payload as Record<string, unknown>;
  if (typeof record.error === "string") return `失败：${record.error}`;
  if (record.approval_required) return "已生成待审批操作，等待你确认";
  if (Array.isArray(record.matches))
    return `找到 ${record.matches.length} 条匹配`;
  if (Array.isArray(record.files)) return `处理 ${record.files.length} 个文件`;
  if (record.file && typeof record.file === "object") {
    const file = record.file as Record<string, unknown>;
    if (typeof file.path === "string") return `已读取 ${file.path}`;
  }
  if (typeof record.sha256 === "string") return "已完成文件写入";
  if (record.block) return "已更新记忆内容";
  return tool.status === "failed" ? "执行失败" : "执行完成";
}

function mutationProvenanceSummary(
  provenance?: MutationProvenance | null,
): string | null {
  if (!provenance) return null;
  const parts = [
    provenance.sourceKind,
    provenance.toolName,
    provenance.approvalId ? `approval=${provenance.approvalId}` : null,
    provenance.rollbackMetaPath
      ? `rollback=${provenance.rollbackMetaPath}`
      : null,
  ].filter(Boolean);
  return parts.join(" · ");
}

function humanizePhaseTitle(
  title: string,
  status: WorkflowEntry["status"],
  detail?: string | null,
): string | null {
  switch (title) {
    case "session.preflight":
      return "已完成本轮 preflight，确认 repo / route / permission context";
    case "turn.lifecycle":
      return status === "running"
        ? "本轮工作流已启动"
        : status === "failed"
          ? "本轮工作流以失败结束"
          : "本轮工作流已完成";
    case "trace.intent.routed":
      return detail ? `Intent routed: ${detail}` : "Intent routed";
    case "trace.phase.intake":
      return "正在理解你的任务并整理当前上下文";
    case "trace.phase.explore":
      return "正在浏览仓库，确定需要读取和搜索的位置";
    case "trace.phase.plan":
      return "正在规划接下来要执行的工具和修改";
    case "trace.phase.verify":
      return "正在检查本轮工具结果和改动状态";
    case "trace.phase.finalize":
      return "正在整理最终回复";
    default:
      return null;
  }
}

function humanizeContextTitle(
  title: string,
  detail?: string | null,
): string | null {
  switch (title) {
    case "trace.context.ready":
      return detail
        ? `Session context ready: ${detail}`
        : "Session context ready";
    case "trace.context.compacted":
      return detail
        ? `Session context compacted: ${detail}`
        : "Session context compacted";
    default:
      return null;
  }
}

function humanizeValidationTitle(
  title: string,
  detail?: string | null,
): string | null {
  switch (title) {
    case "trace.guard.read-before-write":
      return detail ?? "读写顺序校验阻止了未先阅读上下文的修改";
    case "trace.guard.repeated-tool-call":
      return detail ?? "重复工具调用保护已触发，避免进入死循环";
    case "trace.guard.tool-failure-storm":
      return detail ?? "工具连续失败保护已触发，停止继续空转";
    case "trace.guard.no-progress":
      return detail ?? "连续多轮没有成功工具结果，已停止本轮";
    case "trace.guard.provider-rate-limit":
      return detail ?? "提供商限流保护已触发，停止继续请求模型";
    default:
      return detail ?? title;
  }
}

function humanizeTool(step: TimelineStep): string | null {
  const itemType = step.itemType ?? "";
  const actionMap: Record<string, string> = {
    repo_read_file: "读取文件",
    repo_search: "搜索仓库",
    repo_list_tree: "浏览文件树",
    repo_write_file_atomic: "写入文件",
    repo_apply_unified_diff: "应用补丁",
    apply_patch: "应用补丁",
    memory_list: "读取记忆",
    memory_set: "更新记忆",
  };
  if (!actionMap[itemType]) return null;
  const prefix =
    step.status === "running"
      ? "正在"
      : step.status === "failed"
        ? "运行失败"
        : "已运行";
  const detail = step.detail ? step.detail.slice(0, 180) : "";
  return `${prefix}${actionMap[itemType]}${detail ? `：${detail}` : ""}`;
}

function buildWorkflowEntriesFromTimeline(
  run: SessionRun,
  timeline: TimelineStep[],
  diffFiles: DiffFile[],
  toolCalls: ToolCallItem[],
): WorkflowEntry[] {
  const runTimeline = timeline
    .filter((step) => step.runId === run.id)
    .sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0));

  const phaseEntries = runTimeline
    .filter(
      (step) =>
        step.title.startsWith("trace.phase.") ||
        step.title.startsWith("trace.session.") ||
        step.title.startsWith("trace.guard.") ||
        step.title.startsWith("trace.context.") ||
        step.title.startsWith("trace.intent."),
    )
    .map((step): WorkflowEntry | null => {
      const summary =
        humanizePhaseTitle(step.title, step.status, step.detail) ??
        humanizeContextTitle(step.title, step.detail) ??
        humanizeValidationTitle(step.title, step.detail);
      if (!summary) return null;
      return {
        id: step.id,
        type: "run",
        status: step.status,
        badge:
          step.status === "running"
            ? "正在运行"
            : step.status === "failed"
              ? "运行失败"
              : "已运行",
        title: "执行步骤",
        summary,
        meta: step.ts,
        detail: step.detail,
      };
    })
    .filter((entry): entry is WorkflowEntry => entry !== null);

  const toolGroups = new Map<string, TimelineStep[]>();
  for (const step of runTimeline) {
    if (step.traceType !== "tool") continue;
    const key = step.itemId ?? step.id;
    const list = toolGroups.get(key) ?? [];
    list.push(step);
    toolGroups.set(key, list);
  }
  const toolTimelineEntries = Array.from(toolGroups.entries()).map(
    ([key, steps]) => {
      const ordered = [...steps].sort(
        (a, b) => (a.sequence ?? 0) - (b.sequence ?? 0),
      );
      const latest = ordered[ordered.length - 1];
      const title = friendlyToolName(
        latest.itemType ??
          latest.title.replace(/^item\.(started|completed):tool\./, ""),
      );
      return {
        id: `timeline-tool-${key}`,
        type: "run" as const,
        status: latest.status,
        badge:
          latest.status === "running"
            ? "正在运行"
            : latest.status === "failed"
              ? "运行失败"
              : "已运行",
        title,
        summary: humanizeTool(latest) ?? latest.detail ?? title,
        meta: latest.ts,
        detail: ordered
          .map((step) => `${step.title}\n${step.detail ?? ""}`.trim())
          .join("\n\n"),
      };
    },
  );

  const diffEntries = diffFiles
    .filter((file) => file.runId === run.id)
    .map(
      (file): WorkflowEntry => ({
        id: `diff-${file.id}`,
        type: "modify",
        status: "success",
        badge: "已修改",
        title: file.path,
        summary: `新增 ${file.additions} 行，删除 ${file.deletions} 行`,
        meta: file.path,
        detail: file.diff,
      }),
    );

  const runningPatch = runTimeline.find(
    (step) =>
      step.status === "running" &&
      ((step.itemType ?? "").includes("patch") ||
        step.traceType === "artifact"),
  );
  if (runningPatch && diffEntries.length === 0) {
    diffEntries.unshift({
      id: `pending-modify-${run.id}`,
      type: "modify",
      status: "running",
      badge: "正在修改",
      title: "代码变更",
      summary: "正在生成并应用补丁，变更结果稍后出现",
      meta: runningPatch.ts,
      detail: runningPatch.detail,
    });
  }

  const toolEntries = toolCalls
    .filter((tool) => tool.runId === run.id)
    .map(
      (tool): WorkflowEntry => ({
        id: `tool-${tool.id}`,
        type: "run",
        status: tool.status,
        badge:
          tool.status === "running"
            ? "正在运行"
            : tool.status === "failed"
              ? "运行失败"
              : "已运行",
        title: friendlyToolName(tool.name),
        summary: `${summarizeToolArgs(tool)} · ${summarizeToolResult(tool)}`,
        meta: friendlyToolName(tool.name),
        detail: `参数\n${tool.argsJson}\n\n结果\n${tool.resultJson}`,
      }),
    );

  const merged = [
    ...phaseEntries,
    ...toolTimelineEntries,
    ...toolEntries,
    ...diffEntries,
  ];
  const deduped = new Map<string, WorkflowEntry>();
  for (const entry of merged) {
    deduped.set(entry.id, entry);
  }
  return Array.from(deduped.values());
}

function isMutationToolName(name: string): boolean {
  return (
    name === "apply_patch" ||
    name === "repo_apply_unified_diff" ||
    name === "repo_write_file_atomic" ||
    name === "memory_set"
  );
}

function statusBadge(
  status: WorkflowEntry["status"],
  type: WorkflowEntryType,
): string {
  if (type === "modify") {
    return status === "running"
      ? "正在修改"
      : status === "failed"
        ? "修改失败"
        : "已修改";
  }
  return status === "running"
    ? "正在运行"
    : status === "failed"
      ? "运行失败"
      : "已运行";
}

function buildTurnItemDetail(item: SessionTurnItem): string {
  const errorHeader = item.errorCategory
    ? `error_category: ${item.errorCategory}\nerror_code: ${item.errorCode ?? "unknown"}\nretryable: ${item.retryable ? "true" : "false"}\n\n`
    : "";
  if (item.kind === "tool_call") {
    const args = item.detail ?? "";
    const result = item.dataJson ?? "";
    if (args && result && args !== result) {
      return `${errorHeader}参数\n${args}\n\n结果\n${result}`;
    }
  }
  if (item.kind === "command") {
    const result = item.dataJson ?? "";
    if (item.detail && result && result !== item.detail) {
      return `${errorHeader}${item.detail}\n\n结果\n${result}`;
    }
  }
  return `${errorHeader}${item.detail ?? item.dataJson ?? item.summary ?? item.title}`;
}

function summarizeTurnItem(item: SessionTurnItem): string {
  switch (item.kind) {
    case "phase":
      return (
        humanizePhaseTitle(item.title, item.status, item.detail) ??
        item.summary ??
        item.detail ??
        item.title
      );
    case "context":
      return (
        humanizeContextTitle(item.title, item.detail) ??
        item.summary ??
        item.title
      );
    case "model_request":
      return (
        item.summary ??
        (item.status === "running"
          ? "正在请求模型生成下一步动作"
          : item.status === "failed"
            ? "模型请求失败"
            : "模型已返回下一步动作")
      );
    case "command":
      return item.summary ?? item.detail ?? item.title;
    case "validation":
      return (
        humanizeValidationTitle(item.title, item.detail) ??
        item.summary ??
        item.title
      );
    case "tool_call":
      return (
        item.summary ??
        item.detail ??
        friendlyToolName(item.toolName ?? item.title)
      );
    case "diff":
      return item.summary ?? item.path ?? item.title;
    case "approval":
      return withErrorTaxonomy(item.summary ?? item.detail ?? item.title, item);
    case "error":
      return withErrorTaxonomy(item.summary ?? item.detail ?? item.title, item);
    default:
      return withErrorTaxonomy(item.summary ?? item.detail ?? item.title, item);
  }
}

function workflowTitleFromTurnItem(item: SessionTurnItem): string {
  switch (item.kind) {
    case "phase":
      return "执行阶段";
    case "context":
      return "上下文";
    case "model_request":
      return "模型请求";
    case "command":
      return "命令执行";
    case "validation":
      return "规则校验";
    case "tool_call":
      return friendlyToolName(item.toolName ?? item.title);
    case "approval":
      return "审批";
    case "error":
      return "执行错误";
    case "diff":
      return item.path ?? item.title;
    default:
      return item.title;
  }
}

function workflowEntryFromTurnItem(
  item: SessionTurnItem,
): WorkflowEntry | null {
  if (
    item.kind === "user_message" ||
    item.kind === "assistant_message" ||
    item.kind === "artifact"
  ) {
    return null;
  }
  if (item.kind === "approval" && item.status === "pending") {
    return null;
  }
  const type: WorkflowEntryType = item.kind === "diff" ? "modify" : "run";
  return {
    id: `turn-item-${item.id}`,
    type,
    status:
      item.kind === "diff" && item.status === "pending"
        ? "running"
        : item.status,
    badge: statusBadge(
      item.kind === "diff"
        ? item.status === "pending"
          ? "running"
          : item.status
        : item.status,
      type,
    ),
    title: workflowTitleFromTurnItem(item),
    summary: summarizeTurnItem(item),
    meta:
      item.kind === "diff"
        ? (item.path ?? formatTimestamp(item.updatedAt))
        : formatTimestamp(item.updatedAt),
    detail: buildTurnItemDetail(item),
  };
}

function buildWorkflowEntriesFromTurn(
  run: SessionRun,
  turn: SessionTurn,
  timeline: TimelineStep[],
  diffFiles: DiffFile[],
  toolCalls: ToolCallItem[],
): WorkflowEntry[] {
  const hasCanonicalRuntime = turn.items.some(
    (item) =>
      item.kind === "phase" ||
      item.kind === "context" ||
      item.kind === "model_request" ||
      item.kind === "validation" ||
      item.kind === "command" ||
      item.kind === "error" ||
      item.kind === "approval",
  );
  if (!hasCanonicalRuntime) {
    return buildWorkflowEntriesFromTimeline(
      run,
      timeline,
      diffFiles,
      toolCalls,
    );
  }

  const entries = turn.items
    .filter((item) => !item.runId || item.runId === run.id)
    .map(workflowEntryFromTurnItem)
    .filter((entry): entry is WorkflowEntry => entry !== null);

  if (entries.length === 0) {
    return buildWorkflowEntriesFromTimeline(
      run,
      timeline,
      diffFiles,
      toolCalls,
    );
  }

  const hasModifyEntry = entries.some((entry) => entry.type === "modify");
  const runningMutation = turn.items.find(
    (item) =>
      item.kind === "tool_call" &&
      item.status === "running" &&
      isMutationToolName(item.toolName ?? item.title),
  );
  if (!hasModifyEntry && runningMutation) {
    entries.push({
      id: `pending-modify-${run.id}`,
      type: "modify",
      status: "running",
      badge: "正在修改",
      title: "代码变更",
      summary: "正在生成并应用补丁，变更结果稍后出现",
      meta: formatTimestamp(runningMutation.updatedAt),
      detail: buildTurnItemDetail(runningMutation),
    });
  }

  return entries;
}

function buildWorkflowEntries(
  run: SessionRun,
  turn: SessionTurn | undefined,
  timeline: TimelineStep[],
  diffFiles: DiffFile[],
  toolCalls: ToolCallItem[],
): WorkflowEntry[] {
  if (turn) {
    return buildWorkflowEntriesFromTurn(
      run,
      turn,
      timeline,
      diffFiles,
      toolCalls,
    );
  }
  return buildWorkflowEntriesFromTimeline(run, timeline, diffFiles, toolCalls);
}

function formatTimestamp(value?: string | null): string {
  if (!value) return "--:--:--";
  if (/^\d+$/.test(value)) {
    const numeric = Number(value);
    const ms = value.length <= 10 ? numeric * 1000 : numeric;
    return new Date(ms).toLocaleTimeString();
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString();
}

export function WorkflowRunCard({
  run,
  turn,
  timeline,
  diffFiles,
  toolCalls,
  defaultCollapsed = false,
  pendingApprovals = [],
  onApprove,
  onReject,
}: WorkflowRunCardProps) {
  const [tab, setTab] = useState<WorkflowTab>("workflow");
  const [openItems, setOpenItems] = useState<Record<string, boolean>>({});
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  const turnItems = turn?.items ?? [];
  const runDiffs = useMemo(() => {
    const turnDiffs = turnItems
      .filter((item) => item.kind === "diff")
      .map(diffFileFromTurnItem);
    return turnDiffs.length > 0
      ? turnDiffs
      : diffFiles.filter((file) => file.runId === run.id);
  }, [diffFiles, run.id, turnItems]);
  const runToolCalls = useMemo(
    () => toolCalls.filter((tool) => tool.runId === run.id),
    [toolCalls, run.id],
  );
  const turnToolItems = useMemo(
    () => turnItems.filter((item) => item.kind === "tool_call"),
    [turnItems],
  );
  const workflowEntries = useMemo(
    () => buildWorkflowEntries(run, turn, timeline, diffFiles, toolCalls),
    [run, turn, timeline, diffFiles, toolCalls],
  );
  const approvals = useMemo(
    () => pendingApprovals.filter((approval) => approval.runId === run.id),
    [pendingApprovals, run.id],
  );
  const completedChanges = runDiffs.length;
  const completedRuns = workflowEntries.filter(
    (entry) => entry.type === "run",
  ).length;
  const toolCount =
    turnToolItems.length > 0 ? turnToolItems.length : runToolCalls.length;

  const statusText =
    run.status === "running"
      ? "执行中"
      : run.status === "failed"
        ? "执行失败"
        : "执行完成";

  return (
    <div className="overflow-hidden rounded-[24px] border border-border/60 bg-gradient-to-b from-card via-card/95 to-card/75 shadow-[0_22px_60px_rgba(0,0,0,0.24)]">
      <div className="border-b border-border/50 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.14),transparent_28%),radial-gradient(circle_at_top_right,rgba(16,185,129,0.12),transparent_22%)] px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-foreground">
              本轮工作流
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {statusText} · {run.mode} · {formatTimestamp(run.createdAt)}
            </div>
            <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
              <span className="rounded-full bg-background/70 px-2.5 py-1 text-foreground/85">
                已运行 {completedRuns}
              </span>
              <span className="rounded-full bg-background/70 px-2.5 py-1 text-foreground/85">
                已修改 {completedChanges}
              </span>
              {approvals.length > 0 ? (
                <span className="rounded-full bg-amber-500/10 px-2.5 py-1 text-amber-300">
                  待审批 {approvals.length}
                </span>
              ) : null}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "rounded-full px-2.5 py-1 text-[11px] font-medium",
                run.status === "running"
                  ? "bg-blue-500/10 text-blue-300"
                  : run.status === "failed"
                    ? "bg-red-500/10 text-red-300"
                    : "bg-emerald-500/10 text-emerald-300",
              )}
            >
              {statusText}
            </span>
            <button
              className="rounded-lg border border-border/50 px-2.5 py-1 text-[11px] text-muted-foreground hover:bg-accent"
              onClick={() => setCollapsed((value) => !value)}
            >
              {collapsed ? "展开" : "收起"}
            </button>
          </div>
        </div>
        {collapsed ? (
          <div className="mt-3 rounded-2xl border border-border/40 bg-background/40 px-3 py-3 text-xs text-muted-foreground">
            {run.userText}
          </div>
        ) : null}
      </div>

      {collapsed ? null : (
        <>
          <div className="px-4 py-4">
            <div className="mb-4 flex gap-2">
              {(
                [
                  ["workflow", "本轮工作流"],
                  ["diff", `Diff(${runDiffs.length})`],
                  ["tools", `Tools(${toolCount})`],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  className={cn(
                    "rounded-lg border px-3 py-1.5 text-xs transition-colors",
                    tab === key
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border/50 text-muted-foreground hover:bg-accent",
                  )}
                  onClick={() => setTab(key)}
                >
                  {label}
                </button>
              ))}
            </div>

            {tab === "workflow" ? (
              <div className="space-y-2">
                {approvals.length > 0 ? (
                  <div className="space-y-2 rounded-xl border border-amber-500/25 bg-amber-500/5 p-3">
                    <div className="text-xs font-semibold text-amber-200">
                      待审批
                    </div>
                    {approvals.map((approval) => (
                      <div
                        key={approval.id}
                        className="rounded-xl border border-border/50 bg-background/60 p-3"
                      >
                        <div className="text-xs font-medium text-foreground">
                          {approval.toolName}
                        </div>
                        <div className="mt-1 text-[11px] text-muted-foreground">
                          {approval.action}
                          {approval.path ? ` · ${approval.path}` : ""}
                        </div>
                        <div className="mt-2 flex gap-2">
                          <button
                            className="rounded-lg border border-primary/40 px-2.5 py-1 text-[11px] text-primary hover:bg-primary/10"
                            onClick={() => onApprove?.(approval.id, false)}
                          >
                            批准
                          </button>
                          <button
                            className="rounded-lg border border-primary/40 px-2.5 py-1 text-[11px] text-primary hover:bg-primary/10"
                            onClick={() => onApprove?.(approval.id, true)}
                          >
                            本会话允许
                          </button>
                          <button
                            className="rounded-lg border border-border/50 px-2.5 py-1 text-[11px] text-muted-foreground hover:bg-accent"
                            onClick={() => onReject?.(approval.id)}
                          >
                            拒绝
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}

                {workflowEntries.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-border/50 bg-background/40 p-4 text-xs text-muted-foreground">
                    这一轮还没有可显示的执行或修改记录。
                  </div>
                ) : (
                  workflowEntries.map((entry) => {
                    const open = !!openItems[entry.id];
                    return (
                      <div
                        key={entry.id}
                        className="rounded-xl border border-border/50 bg-background/50"
                      >
                        <button
                          className="flex w-full items-start justify-between gap-3 px-3 py-3 text-left"
                          onClick={() =>
                            setOpenItems((prev) => ({
                              ...prev,
                              [entry.id]: !open,
                            }))
                          }
                        >
                          <div className="min-w-0">
                            <div className="mb-1 flex items-center gap-2">
                              <span
                                className={cn(
                                  "rounded-full px-2 py-0.5 text-[10px] font-medium",
                                  entry.type === "modify"
                                    ? entry.status === "running"
                                      ? "bg-amber-500/10 text-amber-300"
                                      : entry.status === "failed"
                                        ? "bg-red-500/10 text-red-300"
                                        : "bg-emerald-500/10 text-emerald-300"
                                    : entry.status === "running"
                                      ? "bg-blue-500/10 text-blue-300"
                                      : entry.status === "failed"
                                        ? "bg-red-500/10 text-red-300"
                                        : "bg-slate-500/10 text-slate-200",
                                )}
                              >
                                {entry.badge}
                              </span>
                              <span className="truncate text-xs font-medium text-foreground">
                                {entry.title}
                              </span>
                            </div>
                            {entry.meta ? (
                              <div className="mb-1 text-[10px] text-muted-foreground/80">
                                {entry.meta}
                              </div>
                            ) : null}
                            <div className="whitespace-pre-wrap text-xs text-muted-foreground">
                              {entry.summary}
                            </div>
                          </div>
                          <span className="pt-0.5 text-xs text-muted-foreground">
                            {open ? "收起" : "展开"}
                          </span>
                        </button>
                        {open ? (
                          <div className="border-t border-border/50 px-3 py-3">
                            <pre className="rounded-xl bg-[#09111d] text-[11px] leading-5 text-slate-200">
                              <code>{entry.detail || entry.summary}</code>
                            </pre>
                          </div>
                        ) : null}
                      </div>
                    );
                  })
                )}
              </div>
            ) : null}

            {tab === "diff" ? (
              <div className="space-y-2">
                {runDiffs.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-border/50 bg-background/40 p-4 text-xs text-muted-foreground">
                    这一轮还没有文件改动。
                  </div>
                ) : (
                  runDiffs.map((file) => {
                    const open = !!openItems[file.id];
                    return (
                      <div
                        key={file.id}
                        className="rounded-xl border border-border/50 bg-background/50"
                      >
                        <button
                          className="flex w-full items-start justify-between gap-3 px-3 py-3 text-left"
                          onClick={() =>
                            setOpenItems((prev) => ({
                              ...prev,
                              [file.id]: !open,
                            }))
                          }
                        >
                          <div>
                            <div className="text-xs font-medium text-foreground">
                              {file.path}
                            </div>
                            <div className="mt-1 text-[11px] text-muted-foreground">
                              +{file.additions} / -{file.deletions}
                            </div>
                            {file.mutationProvenance ? (
                              <div className="mt-1 text-[10px] text-muted-foreground/80">
                                {mutationProvenanceSummary(
                                  file.mutationProvenance,
                                )}
                              </div>
                            ) : null}
                          </div>
                          <span className="pt-0.5 text-xs text-muted-foreground">
                            {open ? "收起" : "展开"}
                          </span>
                        </button>
                        {open ? (
                          <div className="border-t border-border/50 px-3 py-3">
                            <DiffCodeBlock
                              text={
                                file.diff ||
                                file.unifiedSnippet ||
                                file.newSnippet
                              }
                            />
                          </div>
                        ) : null}
                      </div>
                    );
                  })
                )}
              </div>
            ) : null}

            {tab === "tools" ? (
              <div className="space-y-2">
                {turnToolItems.length === 0 && runToolCalls.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-border/50 bg-background/40 p-4 text-xs text-muted-foreground">
                    这一轮还没有工具记录。
                  </div>
                ) : (
                  (turnToolItems.length > 0
                    ? turnToolItems.map((item) => ({
                        id: item.id,
                        name: item.toolName ?? item.title,
                        status: item.status,
                        argsJson: item.detail ?? "",
                        resultJson: item.dataJson ?? item.detail ?? "",
                        summary: item.summary ?? item.title,
                      }))
                    : runToolCalls.map((tool) => ({
                        id: tool.id,
                        name: tool.name,
                        status: tool.status,
                        argsJson: tool.argsJson,
                        resultJson: tool.resultJson,
                        summary: summarizeToolArgs(tool),
                      }))
                  ).map((tool) => {
                    const key = `tool-panel-${tool.id}`;
                    const open = !!openItems[key];
                    return (
                      <div
                        key={tool.id}
                        className="rounded-xl border border-border/50 bg-background/50"
                      >
                        <button
                          className="flex w-full items-start justify-between gap-3 px-3 py-3 text-left"
                          onClick={() =>
                            setOpenItems((prev) => ({ ...prev, [key]: !open }))
                          }
                        >
                          <div>
                            <div className="text-xs font-medium text-foreground">
                              {tool.name}
                            </div>
                            <div className="mt-1 text-[11px] text-muted-foreground">
                              {tool.status} · {tool.summary}
                            </div>
                          </div>
                          <span className="pt-0.5 text-xs text-muted-foreground">
                            {open ? "收起" : "展开"}
                          </span>
                        </button>
                        {open ? (
                          <div className="space-y-2 border-t border-border/50 px-3 py-3">
                            <pre className="rounded-xl bg-[#09111d] text-[11px] leading-5 text-slate-200">
                              <code>{tool.argsJson}</code>
                            </pre>
                            <pre className="rounded-xl bg-[#09111d] text-[11px] leading-5 text-slate-200">
                              <code>{tool.resultJson}</code>
                            </pre>
                          </div>
                        ) : null}
                      </div>
                    );
                  })
                )}
              </div>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}
