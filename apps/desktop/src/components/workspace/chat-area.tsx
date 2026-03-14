import { useEffect, useMemo, useRef, useState } from "react";

import {
  approveRequest,
  listPendingApprovals,
  rejectRequest,
} from "../../api/bridge";
import { cn } from "../../lib/utils";
import type {
  ApprovalRequest,
  ArtifactItem,
  ChatMessage,
  DiffFile,
  LogItem,
  SessionMode,
  PythonTodoState,
  SessionRun,
  SessionTurn,
  TimelineStep,
  ToolCallItem,
} from "../../types/models";
import { WorkflowRunCard } from "./workflow-run-card";

interface ChatAreaProps {
  sessionId: string | null;
  messages: ChatMessage[];
  timeline: TimelineStep[];
  diffFiles: DiffFile[];
  toolCalls: ToolCallItem[];
  logs: LogItem[];
  artifacts: ArtifactItem[];
  sessionRuns?: SessionRun[];
  sessionTurns?: SessionTurn[];
  pythonTodo?: PythonTodoState | null;
  currentMode: SessionMode;
  isRunning: boolean;
  onSend: (text: string, mode: SessionMode) => void;
  onStop?: () => void;
  onModeChange: (mode: SessionMode) => void;
  onRetryStep?: (stepId: string) => void;
  onRollback?: () => void;
  onExportTrace?: () => void;
}

type TranscriptItem =
  | { key: string; kind: "message"; message: ChatMessage }
  | { key: string; kind: "run"; run: SessionRun };

function toSortableTime(value: string): number {
  if (/^\d+$/.test(value)) {
    const numeric = Number(value);
    return value.length <= 10 ? numeric * 1000 : numeric;
  }
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function buildTranscript(
  messages: ChatMessage[],
  sessionRuns: SessionRun[],
): TranscriptItem[] {
  const transcript: TranscriptItem[] = [
    ...messages.map((message) => ({
      key: message.id,
      kind: "message" as const,
      message,
    })),
    ...sessionRuns
      .filter((run) => run.mode !== "terminal")
      .map((run) => ({
        key: `run-${run.id}`,
        kind: "run" as const,
        run,
      })),
  ];

  transcript.sort((lhs, rhs) => {
    const lhsTime =
      lhs.kind === "message"
        ? toSortableTime(lhs.message.createdAt)
        : toSortableTime(lhs.run.createdAt);
    const rhsTime =
      rhs.kind === "message"
        ? toSortableTime(rhs.message.createdAt)
        : toSortableTime(rhs.run.createdAt);
    if (lhsTime !== rhsTime) return lhsTime - rhsTime;
    if (lhs.kind !== rhs.kind) {
      return lhs.kind === "message" ? -1 : 1;
    }
    return lhs.key.localeCompare(rhs.key);
  });

  return transcript;
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  return (
    <div className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
      {!isUser ? (
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10">
          <svg
            className="h-5 w-5 text-primary"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
            />
          </svg>
        </div>
      ) : null}

      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3 shadow-[0_16px_40px_rgba(0,0,0,0.18)]",
          isUser
            ? "bg-primary text-primary-foreground"
            : isSystem
              ? "border border-border/40 bg-muted/40 text-muted-foreground"
              : "border border-border/50 bg-card text-foreground",
        )}
      >
        <div className="whitespace-pre-wrap text-sm leading-7">
          {message.content}
        </div>
        <div className="mt-2 text-xs opacity-60">
          {new Date(message.createdAt).toLocaleTimeString()}
        </div>
      </div>

      {isUser ? (
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-accent">
          <svg
            className="h-5 w-5 text-foreground"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
            />
          </svg>
        </div>
      ) : null}
    </div>
  );
}

export function ChatArea({
  sessionId,
  messages,
  timeline,
  diffFiles,
  toolCalls,
  logs,
  artifacts,
  sessionRuns = [],
  sessionTurns = [],
  pythonTodo = null,
  currentMode,
  isRunning,
  onSend,
  onStop,
  onModeChange,
}: ChatAreaProps) {
  const [input, setInput] = useState("");
  const [selectedMode, setSelectedMode] = useState<SessionMode>(currentMode);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequest[]>(
    [],
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const transcript = useMemo(
    () => buildTranscript(messages, sessionRuns),
    [messages, sessionRuns],
  );

  useEffect(() => {
    setSelectedMode(currentMode);
  }, [currentMode]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript, isRunning]);

  useEffect(() => {
    if (!sessionId) {
      setPendingApprovals([]);
      return;
    }
    let canceled = false;
    listPendingApprovals(sessionId)
      .then((items) => {
        if (!canceled) {
          setPendingApprovals(
            items.filter((item) => item.status === "pending"),
          );
        }
      })
      .catch(() => {
        if (!canceled) setPendingApprovals([]);
      });
    return () => {
      canceled = true;
    };
  }, [sessionId, timeline, toolCalls]);

  const handleSend = () => {
    if (isRunning) return;
    const text = input.trim();
    if (!text) return;
    onSend(text, selectedMode);
    setInput("");
  };

  const handleStop = () => {
    onStop?.();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape" && isRunning) {
      e.preventDefault();
      handleStop();
      return;
    }
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSend();
    }
  };

  const getModeInfo = (mode: SessionMode) => {
    switch (mode) {
      case "plan":
        return {
          label: "Plan",
          color: "bg-blue-500/10 text-blue-300 border-blue-500/30",
          desc: "只读分析",
        };
      case "build":
        return {
          label: "Build",
          color: "bg-amber-500/10 text-amber-300 border-amber-500/30",
          desc: "需要审批",
        };
      case "auto":
        return {
          label: "Auto",
          color: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
          desc: "自动应用",
        };
    }
  };

  void logs;
  void artifacts;

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {transcript.length === 0 ? (
            <div className="flex h-full min-h-[360px] items-center justify-center">
              <div className="text-center">
                <div className="mb-4 text-4xl">💬</div>
                <h3 className="mb-2 text-lg font-semibold text-foreground">
                  开始新对话
                </h3>
                <p className="text-sm text-muted-foreground">
                  输入你的任务描述，让 AI 助手开始工作。
                </p>
              </div>
            </div>
          ) : (
            transcript.map((item) => {
              if (item.kind === "message") {
                return <MessageBubble key={item.key} message={item.message} />;
              }
              return (
                <WorkflowRunCard
                  key={item.key}
                  run={item.run}
                  turn={sessionTurns.find(
                    (turn) => turn.id === item.run.turnId,
                  )}
                  timeline={timeline}
                  diffFiles={diffFiles}
                  toolCalls={toolCalls}
                  defaultCollapsed
                  pendingApprovals={pendingApprovals}
                  onApprove={(approvalId, allowSession) => {
                    if (!sessionId) return;
                    approveRequest(
                      sessionId,
                      approvalId,
                      undefined,
                      allowSession,
                    )
                      .then(() => {
                        setPendingApprovals((items) =>
                          items.filter((item) => item.id !== approvalId),
                        );
                      })
                      .catch(() => undefined);
                  }}
                  onReject={(approvalId) => {
                    if (!sessionId) return;
                    rejectRequest(sessionId, approvalId)
                      .then(() => {
                        setPendingApprovals((items) =>
                          items.filter((item) => item.id !== approvalId),
                        );
                      })
                      .catch(() => undefined);
                  }}
                />
              );
            })
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="border-t border-border/50 bg-card/30 p-4">
        <div className="mx-auto max-w-3xl">
          <div className="mb-3 flex items-center gap-2">
            <span className="text-xs text-muted-foreground">执行模式：</span>
            <div className="flex gap-1">
              {(["plan", "build", "auto"] as const).map((mode) => {
                const info = getModeInfo(mode);
                return (
                  <button
                    key={mode}
                    onClick={() => {
                      setSelectedMode(mode);
                      onModeChange(mode);
                    }}
                    className={cn(
                      "rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                      selectedMode === mode
                        ? info.color
                        : "border-border/50 text-muted-foreground hover:bg-accent",
                    )}
                    title={info.desc}
                  >
                    {info.label}
                  </button>
                );
              })}
            </div>
            <span className="ml-auto text-xs text-muted-foreground">
              {getModeInfo(selectedMode).desc}
            </span>
          </div>

          {pythonTodo ? (
            <details className="mb-3 rounded-xl border border-border/50 bg-background/40 px-3 py-2">
              <summary className="cursor-pointer list-none select-none text-xs text-muted-foreground">
                <span className="font-medium text-foreground">Todo</span>
                <span className="ml-2">
                  {pythonTodo.stats.completed}/{pythonTodo.stats.total}
                </span>
                {pythonTodo.stats.inProgress > 0 ? (
                  <span className="ml-2 rounded bg-emerald-500/10 px-2 py-0.5 text-emerald-300">
                    进行中 {pythonTodo.stats.inProgress}
                  </span>
                ) : null}
                <span className="ml-2 opacity-70">(展开/收起)</span>
              </summary>
              <div className="mt-2 space-y-1">
                {pythonTodo.items.length === 0 ? (
                  <div className="text-xs text-muted-foreground">暂无 todo</div>
                ) : (
                  pythonTodo.items.map((item) => {
                    const mark =
                      item.status === "completed"
                        ? "✓"
                        : item.status === "in_progress"
                          ? "→"
                          : " ";
                    return (
                      <div
                        key={item.stepId}
                        className={cn(
                          "flex items-start gap-2 text-xs",
                          item.status === "in_progress"
                            ? "text-foreground"
                            : "text-muted-foreground",
                        )}
                      >
                        <span className="mt-0.5 inline-flex h-4 w-4 items-center justify-center rounded border border-border/60">
                          {mark}
                        </span>
                        <div className="flex-1">
                          <div className="leading-6">{item.title}</div>
                          {item.status === "in_progress" && item.activeForm ? (
                            <div className="opacity-80">{item.activeForm}</div>
                          ) : null}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </details>
          ) : null}

          <div className="flex gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入任务描述... (Ctrl+Enter 发送)"
              className="flex-1 resize-none rounded-2xl border border-border/50 bg-background px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              rows={3}
              disabled={isRunning}
            />
            <button
              onClick={isRunning ? handleStop : handleSend}
              disabled={isRunning ? !onStop : !input.trim()}
              className={cn(
                "flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-2xl transition-colors",
                (isRunning ? Boolean(onStop) : input.trim())
                  ? "bg-primary text-primary-foreground hover:bg-primary/90"
                  : "cursor-not-allowed bg-muted text-muted-foreground",
              )}
            >
              {isRunning ? (
                <svg
                  className="h-5 w-5"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <rect x="7" y="7" width="10" height="10" rx="2" />
                </svg>
              ) : (
                <svg
                  className="h-5 w-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                  />
                </svg>
              )}
            </button>
          </div>

          {isRunning ? (
            <div className="mt-2 text-xs text-muted-foreground">
              AI 正在处理中...
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
