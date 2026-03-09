import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  getApprovalMeta,
  getArtifacts,
  getDiffFiles,
  getLogs,
  getTimeline,
  getToolCalls,
  listRepos,
  listSessions,
  rollbackPatchArtifact,
  runSessionMessage,
} from "../api/bridge";
import { Button } from "../components/ui/button";
import { ArtifactsPanel } from "../components/detail/artifacts-panel";
import { DiffPanel } from "../components/detail/diff-panel";
import { LogsPanel } from "../components/detail/logs-panel";
import { ToolsPanel } from "../components/detail/tools-panel";
import { ChatPanel } from "../components/workspace/chat-panel";
import { cn } from "../lib/utils";
import {
  findLatestRollbackArtifact,
  rollbackMetaPathForArtifact,
} from "../lib/mutation";
import { isTauriRuntime } from "../lib/platform";
import { openPathNative } from "../lib/native";
import { useAppStore } from "../store/app-store";
import { useSecurityStore } from "../store/security-store";
import { useSettingsStore } from "../store/settings-store";
import { useSessionStore } from "../store/session-store";
import { useUiStore } from "../store/ui-store";
import type { ApprovalMeta, DetailTab, SessionItem } from "../types/models";

function statusColor(
  status: "pending" | "running" | "success" | "failed",
): string {
  if (status === "success") return "bg-emerald-500";
  if (status === "running") return "bg-blue-500";
  if (status === "failed") return "bg-red-500";
  return "bg-zinc-500";
}

function statusLabel(
  status: "pending" | "running" | "success" | "failed",
): string {
  if (status === "pending") return "等待中";
  if (status === "running") return "运行中";
  if (status === "success") return "成功";
  return "失败";
}

export function WorkspacePage() {
  const navigate = useNavigate();
  const { repos, currentRepoId, setRepos, setCurrentRepo } = useAppStore();
  const {
    sessions,
    globalSessions,
    currentSessionId,
    timeline,
    diffFiles,
    selectedDiffFileId,
    diffViewMode,
    toolCalls,
    logs,
    logFilter,
    logKeyword,
    artifacts,
    activeDetailTab,
    leftView,
    leftWidth,
    rightWidth,
    isLoadingSessions,
    isLoadingTimeline,
    errorText,
    setSessions,
    setGlobalSessions,
    setCurrentSession,
    createSession,
    deleteSession,
    updateSessionMode,
    setTimeline,
    setDiffFiles,
    setSelectedDiffFile,
    setDiffViewMode,
    setToolCalls,
    setLogs,
    setLogFilter,
    setLogKeyword,
    setArtifacts,
    getMessages,
    appendMessage,
    retryStep,
    openDiagnosis,
    undoTimeline,
    redoTimeline,
    canUndoTimeline,
    canRedoTimeline,
    getSessionSummary,
    setActiveDetailTab,
    setLeftView,
    setPanelWidths,
    setLoadingSessions,
    setLoadingTimeline,
    setError,
  } = useSessionStore();
  const pushToast = useUiStore((s) => s.pushToast);
  const { settings } = useSettingsStore();
  const { getPolicy, setPolicy } = useSecurityStore();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const pendingSensitiveAllowRef = useRef<null | (() => void)>(null);
  const [resizing, setResizing] = useState<null | "left" | "right">(null);
  const [newSessionTitle, setNewSessionTitle] = useState("");
  const [newSessionModeOverride, setNewSessionModeOverride] = useState<
    "plan" | "build" | "auto" | null
  >(null);
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [approvalMeta, setApprovalMeta] = useState<ApprovalMeta | null>(null);
  const [rollbackConfirmOpen, setRollbackConfirmOpen] = useState(false);
  const [sensitivePrompt, setSensitivePrompt] = useState<null | {
    action: "install_dependency" | "run_shell";
    remember: boolean;
  }>(null);

  const currentRepo = useMemo(
    () => repos.find((r) => r.id === currentRepoId) ?? null,
    [repos, currentRepoId],
  );
  const visibleSessions: SessionItem[] =
    leftView === "repo" ? sessions : globalSessions;
  const currentSession = useMemo(
    () => visibleSessions.find((s) => s.id === currentSessionId) ?? null,
    [visibleSessions, currentSessionId],
  );

  useEffect(() => {
    // hydrate from mock only when no local/persisted repos exist.
    if (repos.length > 0) return;
    setError(null);
    listRepos()
      .then((items) => {
        setRepos(items);
      })
      .catch((e) => {
        setError(`加载仓库失败：${String(e)}`);
      });
  }, [setRepos, repos.length, setError]);

  useEffect(() => {
    setLoadingSessions(true);
    if (!currentRepoId) {
      setSessions([]);
      setLoadingSessions(false);
      return;
    }
    listSessions(currentRepoId)
      .then((items) => {
        setSessions(items);
      })
      .catch((e) => {
        setError(`加载会话失败：${String(e)}`);
        setSessions([]);
      })
      .finally(() => setLoadingSessions(false));
  }, [currentRepoId, setSessions, setLoadingSessions, setError]);

  useEffect(() => {
    // global sessions secondary view
    Promise.all(repos.map((r) => listSessions(r.id)))
      .then((all) => {
        setGlobalSessions(all.flat());
      })
      .catch(() => {
        // non-blocking
      });
  }, [repos, setGlobalSessions]);

  useEffect(() => {
    setLoadingTimeline(true);
    if (!currentSessionId) {
      setTimeline([]);
      setLoadingTimeline(false);
      return;
    }
    getTimeline(currentSessionId)
      .then((items) => {
        setTimeline(items);
        const failed = items.find((i) => i.status === "failed");
        const running = items.find((i) => i.status === "running");
        if (failed) {
          pushToast({
            kind: "error",
            title: "执行失败",
            message: `步骤「${failed.title}」失败，可重试/回滚/诊断。`,
          });
        } else if (!running && items.length > 0) {
          pushToast({
            kind: "success",
            title: "执行完成",
            message: "本次任务步骤已完成。",
          });
        }
      })
      .catch((e) => {
        setError(`加载时间线失败：${String(e)}`);
        setTimeline([]);
      })
      .finally(() => setLoadingTimeline(false));
  }, [currentSessionId, setTimeline, setLoadingTimeline, setError, pushToast]);

  useEffect(() => {
    if (!currentSessionId || timeline.length === 0) return;
    timelineRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [timeline, currentSessionId]);

  useEffect(() => {
    if (!currentSessionId) {
      setDiffFiles([]);
      setToolCalls([]);
      setLogs([]);
      setArtifacts([]);
      return;
    }
    getDiffFiles(currentSessionId)
      .then(setDiffFiles)
      .catch(() => setDiffFiles([]));
    getToolCalls(currentSessionId)
      .then(setToolCalls)
      .catch(() => setToolCalls([]));
    getLogs(currentSessionId)
      .then(setLogs)
      .catch(() => setLogs([]));
    getArtifacts(currentSessionId)
      .then(setArtifacts)
      .catch(() => setArtifacts([]));
  }, [currentSessionId, setArtifacts, setDiffFiles, setLogs, setToolCalls]);

  useEffect(() => {
    if (!resizing) return;
    const onMove = (evt: MouseEvent) => {
      if (!rootRef.current) return;
      const rect = rootRef.current.getBoundingClientRect();
      const min = 220;
      const maxLeft = Math.max(min, rect.width - rightWidth - 420);
      const maxRight = Math.max(min, rect.width - leftWidth - 420);
      if (resizing === "left") {
        const next = Math.min(Math.max(evt.clientX - rect.left, min), maxLeft);
        setPanelWidths(next, rightWidth);
      } else {
        const width = rect.right - evt.clientX;
        const next = Math.min(Math.max(width, min), maxRight);
        setPanelWidths(leftWidth, next);
      }
    };
    const onUp = () => setResizing(null);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [resizing, leftWidth, rightWidth, setPanelWidths]);

  const detailTabs: Array<{ key: DetailTab; label: string }> = [
    { key: "diff", label: "Diff" },
    { key: "tools", label: "Tools" },
    { key: "logs", label: "Logs" },
    { key: "artifacts", label: "Artifacts" },
  ];

  const mode = currentSession?.mode ?? "plan";
  const messages = useMemo(
    () => getMessages(currentSessionId),
    [currentSessionId, getMessages],
  );
  const timelineRef = useRef<HTMLDivElement | null>(null);
  const canUndo = canUndoTimeline();
  const canRedo = canRedoTimeline();

  const requestSensitiveAction = (
    action: "install_dependency" | "run_shell",
    onAllow: () => void,
  ) => {
    const repoId = currentRepoId;
    if (!repoId) {
      pushToast({ kind: "warning", title: "未选择仓库" });
      return;
    }
    const policy = getPolicy(repoId, action);
    if (policy === "deny") {
      pushToast({
        kind: "error",
        title: "策略拒绝",
        message: `动作 ${action} 已被该仓库策略拒绝。`,
      });
      return;
    }
    if (policy === "allow") {
      onAllow();
      return;
    }
    pendingSensitiveAllowRef.current = onAllow;
    setSensitivePrompt({ action, remember: false });
  };

  const handleApply = () => {
    if (mode === "plan") {
      pushToast({
        kind: "warning",
        title: "Plan 模式不可 Apply",
        message: "请切换到 Build 或 Auto。",
      });
      return;
    }
    if (mode === "auto") {
      pushToast({
        kind: "success",
        title: "Auto 已自动应用",
        message: "变更已直接应用。",
      });
      return;
    }
    if (!currentSessionId) return;
    getApprovalMeta(currentSessionId)
      .then((meta) => {
        setApprovalMeta(meta);
        setApprovalOpen(true);
      })
      .catch(() => {
        setApprovalMeta(null);
        setApprovalOpen(true);
      });
  };

  const handleReject = () => {
    pushToast({ kind: "info", title: "已拒绝本次变更" });
  };

  const handleRollback = () => {
    setRollbackConfirmOpen(true);
  };

  const onCreateSession = () => {
    if (!currentRepoId) {
      pushToast({
        kind: "warning",
        title: "请先选择仓库",
        message: "创建会话前请先选定仓库。",
      });
      return;
    }
    const title = newSessionTitle.trim() || "新会话";
    const modeForCreate = newSessionModeOverride ?? settings.defaultSessionMode;
    const id = createSession({
      repoId: currentRepoId,
      title,
      mode: modeForCreate,
    });
    setCurrentSession(id);
    appendMessage(id, "system", `已创建会话，当前模式：${modeForCreate}`);
    setNewSessionTitle("");
    setNewSessionModeOverride(null);
    pushToast({
      kind: "info",
      title: "会话已创建",
      message: `模式：${modeForCreate}`,
    });
  };

  const onDeleteCurrentSession = () => {
    if (!currentSessionId) return;
    deleteSession(currentSessionId);
    pushToast({ kind: "warning", title: "会话已删除" });
  };

  const onModeChange = (mode: "plan" | "build" | "auto") => {
    if (!currentSessionId) return;
    updateSessionMode(currentSessionId, mode);
    appendMessage(currentSessionId, "system", `会话模式已切换为 ${mode}`);
    pushToast({
      kind: "info",
      title: "模式已更新",
      message: `当前模式：${mode}`,
    });
  };

  const onSendChat = (text: string) => {
    if (!currentSessionId) return;
    appendMessage(currentSessionId, "user", text);
    setLoadingTimeline(true);
    runSessionMessage(currentSessionId, mode, text)
      .then((result) => {
        appendMessage(currentSessionId, "assistant", result.assistantMessage);
        setTimeline(result.timeline);
        pushToast({
          kind: "info",
          title: "已生成新执行轮次",
          message: "时间线已更新。",
        });
      })
      .catch((e) => {
        appendMessage(currentSessionId, "system", `执行失败：${String(e)}`);
        pushToast({ kind: "error", title: "执行失败", message: String(e) });
      })
      .finally(() => setLoadingTimeline(false));
  };

  const newSessionMode = newSessionModeOverride ?? settings.defaultSessionMode;

  return (
    <div ref={rootRef} className="h-[calc(100vh-49px)]">
      <div className="flex items-center gap-3 border-b border-border/50 bg-card/30 px-4 py-2.5 text-xs backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">仓库</span>
          <span className="font-medium text-foreground">
            {currentRepo?.name ?? "未选择"}
          </span>
        </div>
        <span className="text-border">•</span>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">会话</span>
          <span className="font-medium text-foreground">
            {currentSession?.title ?? "无"}
          </span>
        </div>
        <span className="text-border">•</span>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">模式</span>
          <span
            className={cn(
              "rounded-md px-2 py-0.5 text-xs font-medium",
              currentSession?.mode === "plan" && "bg-blue-500/10 text-blue-400",
              currentSession?.mode === "build" &&
                "bg-amber-500/10 text-amber-400",
              currentSession?.mode === "auto" &&
                "bg-emerald-500/10 text-emerald-400",
              !currentSession?.mode && "bg-muted text-muted-foreground",
            )}
          >
            {currentSession?.mode ?? "-"}
          </span>
        </div>
        <span className="text-border">•</span>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">状态</span>
          <div className="flex items-center gap-1.5">
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                isLoadingTimeline
                  ? "bg-blue-500 animate-pulse"
                  : timeline.some((t) => t.status === "failed")
                    ? "bg-red-500"
                    : "bg-emerald-500",
              )}
            />
            <span className="font-medium text-foreground">
              {isLoadingTimeline
                ? "执行中"
                : timeline.some((t) => t.status === "failed")
                  ? "失败"
                  : "就绪"}
            </span>
          </div>
        </div>
      </div>
      <div className="flex h-[calc(100%-37px)]">
        <aside
          className="border-r border-border/50 bg-sidebar p-4"
          style={{ width: leftWidth }}
        >
          <div className="mb-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              仓库
            </p>
            {repos.length === 0 ? (
              <div className="mb-4 rounded-lg border border-dashed border-border/50 bg-card/30 p-4 text-xs text-muted-foreground">
                <div className="mb-3 text-sm font-medium text-foreground">
                  开始使用
                </div>
                <div className="mb-3">导入本地仓库开始工作</div>
                <Button
                  className="h-9 w-full rounded-lg font-medium"
                  onClick={() => navigate("/repositories")}
                >
                  导入仓库
                </Button>
              </div>
            ) : (
              <div className="mb-4 space-y-1.5">
                {repos.map((repo) => (
                  <button
                    key={repo.id}
                    className={cn(
                      "w-full rounded-lg px-3 py-2.5 text-left text-sm transition-colors hover:bg-accent/50",
                      currentRepoId === repo.id && "bg-accent shadow-sm",
                    )}
                    onClick={() => setCurrentRepo(repo.id)}
                  >
                    <div className="font-medium text-foreground">
                      {repo.name}
                    </div>
                    <div className="mt-0.5 truncate text-xs text-muted-foreground">
                      {repo.path}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="mb-4 flex rounded-lg border border-border/50 bg-card/30 p-1 text-xs">
            <button
              className={cn(
                "flex-1 rounded-md px-3 py-1.5 font-medium transition-colors",
                leftView === "repo" && "bg-accent shadow-sm text-foreground",
                leftView !== "repo" &&
                  "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setLeftView("repo")}
            >
              当前仓库
            </button>
            <button
              className={cn(
                "flex-1 rounded-md px-3 py-1.5 font-medium transition-colors",
                leftView === "global" && "bg-accent shadow-sm text-foreground",
                leftView !== "global" &&
                  "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setLeftView("global")}
            >
              全局会话
            </button>
          </div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            会话
          </p>
          <div className="mb-3 rounded-lg border border-border/50 bg-card/30 p-3">
            <input
              value={newSessionTitle}
              onChange={(e) => setNewSessionTitle(e.target.value)}
              placeholder="新会话标题"
              className="mb-3 h-9 w-full rounded-lg border border-input bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <div className="mb-3 flex gap-1.5 text-xs">
              {(["plan", "build", "auto"] as const).map((m) => (
                <button
                  key={m}
                  className={cn(
                    "flex-1 rounded-md border border-border/50 px-2 py-1.5 font-medium transition-colors",
                    newSessionMode === m &&
                      "bg-accent text-foreground shadow-sm",
                    newSessionMode !== m &&
                      "text-muted-foreground hover:bg-accent/30 hover:text-foreground",
                  )}
                  onClick={() => setNewSessionModeOverride(m)}
                >
                  {m}
                </button>
              ))}
            </div>
            <Button
              className="h-9 w-full rounded-lg font-medium"
              variant="outline"
              onClick={onCreateSession}
            >
              新建会话
            </Button>
          </div>
          {isLoadingSessions ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
              加载会话中...
            </div>
          ) : visibleSessions.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border/50 bg-card/30 p-4 text-xs text-muted-foreground">
              <div className="mb-2 text-sm font-medium text-foreground">
                暂无会话
              </div>
              新建一个 Build 会话开始执行
            </div>
          ) : (
            <div className="space-y-1.5">
              {visibleSessions.map((s) => (
                <button
                  key={s.id}
                  className={cn(
                    "w-full rounded-lg px-3 py-2.5 text-left text-sm transition-colors hover:bg-accent/50",
                    currentSessionId === s.id && "bg-accent shadow-sm",
                  )}
                  onClick={() => setCurrentSession(s.id)}
                >
                  <div className="truncate font-medium text-foreground">
                    {s.title}
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-xs">
                    <span
                      className={cn(
                        "rounded px-1.5 py-0.5 font-medium",
                        s.mode === "plan" && "bg-blue-500/10 text-blue-400",
                        s.mode === "build" && "bg-amber-500/10 text-amber-400",
                        s.mode === "auto" &&
                          "bg-emerald-500/10 text-emerald-400",
                      )}
                    >
                      {s.mode}
                    </span>
                  </div>
                  <div className="mt-1 truncate text-[11px] text-muted-foreground">
                    {getSessionSummary(s.id)}
                  </div>
                </button>
              ))}
            </div>
          )}
          {errorText ? (
            <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-400">
              {errorText}
            </div>
          ) : null}
        </aside>

        <div
          className="w-1 cursor-col-resize bg-border/30 hover:bg-primary/50 transition-colors"
          role="separator"
          aria-orientation="vertical"
          onMouseDown={() => setResizing("left")}
        />

        <section className="flex-1 bg-background p-5">
          <ChatPanel
            sessionId={currentSessionId}
            mode={mode}
            messages={messages}
            isRunning={isLoadingTimeline}
            onSend={onSendChat}
          />
          <div className="mb-5 rounded-xl border border-border/50 bg-card shadow-codex p-5">
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">
                当前模式
              </span>
              {(["plan", "build", "auto"] as const).map((m) => (
                <Button
                  key={m}
                  variant={currentSession?.mode === m ? "default" : "outline"}
                  className={cn(
                    "h-8 rounded-lg px-3 text-xs font-medium transition-all",
                    currentSession?.mode === m && "shadow-sm",
                  )}
                  onClick={() => onModeChange(m)}
                  disabled={!currentSessionId}
                >
                  {m}
                </Button>
              ))}
              <Button
                variant="ghost"
                className="ml-auto h-8 rounded-lg px-3 text-xs text-muted-foreground hover:text-destructive"
                onClick={onDeleteCurrentSession}
                disabled={!currentSessionId}
              >
                删除当前会话
              </Button>
              <Button
                variant="outline"
                className="h-8 rounded-lg px-3 text-xs"
                onClick={() =>
                  requestSensitiveAction("run_shell", () => {
                    pushToast({
                      kind: "info",
                      title: "已执行敏感动作",
                      message: "run_shell 已允许执行（模拟）。",
                    });
                  })
                }
              >
                运行敏感命令
              </Button>
              <Button
                variant="outline"
                className="h-8 rounded-lg px-3 text-xs"
                onClick={() =>
                  requestSensitiveAction("install_dependency", () => {
                    pushToast({
                      kind: "info",
                      title: "已执行敏感动作",
                      message: "install_dependency 已允许执行（模拟）。",
                    });
                  })
                }
              >
                安装依赖
              </Button>
            </div>
          </div>
          <div
            ref={timelineRef}
            className="rounded-xl border border-border/50 bg-card shadow-codex p-5"
          >
            <div className="mb-4 text-sm font-semibold text-foreground">
              执行时间线
            </div>
            {isLoadingTimeline ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <div className="h-3 w-3 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
                加载时间线中...
              </div>
            ) : timeline.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border/50 bg-muted/30 p-4 text-xs text-muted-foreground">
                当前会话暂无执行步骤
              </div>
            ) : (
              <div className="space-y-3">
                {timeline.map((step) => (
                  <div
                    key={step.id}
                    className="rounded-lg border border-border/50 bg-muted/30 p-4 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex items-center gap-2.5">
                      <span
                        className={cn(
                          "h-2.5 w-2.5 rounded-full",
                          statusColor(step.status),
                        )}
                      />
                      <span className="text-sm font-medium text-foreground">
                        {step.title}
                      </span>
                      <span className="ml-auto text-xs font-medium text-muted-foreground">
                        {statusLabel(step.status)}
                      </span>
                    </div>
                    {step.detail ? (
                      <p className="mt-2 text-xs text-muted-foreground">
                        {step.detail}
                      </p>
                    ) : null}
                    {step.status === "failed" ? (
                      <div className="mt-3 flex gap-2">
                        <Button
                          className="h-8 rounded-lg px-3 text-xs font-medium shadow-sm"
                          onClick={() => {
                            retryStep(step.id);
                            pushToast({
                              kind: "info",
                              title: "已触发重试",
                              message: `步骤：${step.title}`,
                            });
                          }}
                        >
                          重试本步
                        </Button>
                        <Button
                          variant="outline"
                          className="h-8 rounded-lg px-3 text-xs"
                          onClick={() => {
                            setRollbackConfirmOpen(true);
                          }}
                        >
                          回滚本次变更
                        </Button>
                        <Button
                          variant="outline"
                          className="h-8 rounded-lg px-3 text-xs"
                          onClick={() => {
                            openDiagnosis();
                            setActiveDetailTab("logs");
                            pushToast({
                              kind: "info",
                              title: "诊断已打开",
                              message: "已切换至 Logs。",
                            });
                          }}
                        >
                          查看诊断
                        </Button>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <div
          className="w-1 cursor-col-resize bg-border/30 hover:bg-primary/50 transition-colors"
          role="separator"
          aria-orientation="vertical"
          onMouseDown={() => setResizing("right")}
        />

        <aside
          className="border-l border-border/50 bg-sidebar p-4"
          style={{ width: rightWidth }}
        >
          <p className="mb-4 text-sm font-semibold text-foreground">详情面板</p>
          <div className="mb-4 grid grid-cols-4 gap-1 rounded-lg border border-border/50 bg-card/30 p-1 text-xs">
            {detailTabs.map((tab) => (
              <button
                key={tab.key}
                className={cn(
                  "rounded-md px-2 py-1.5 font-medium transition-colors",
                  activeDetailTab === tab.key &&
                    "bg-accent shadow-sm text-foreground",
                  activeDetailTab !== tab.key &&
                    "text-muted-foreground hover:text-foreground",
                )}
                onClick={() => setActiveDetailTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="rounded-xl border border-border/50 bg-card shadow-codex p-4 text-xs text-muted-foreground">
            {activeDetailTab === "diff" && (
              <DiffPanel
                files={diffFiles}
                selectedId={selectedDiffFileId}
                onSelect={setSelectedDiffFile}
                viewMode={diffViewMode}
                onChangeView={setDiffViewMode}
                mode={mode}
                onApply={handleApply}
                onReject={handleReject}
                onRollback={handleRollback}
                onUndo={undoTimeline}
                onRedo={redoTimeline}
                canUndo={canUndo}
                canRedo={canRedo}
              />
            )}
            {activeDetailTab === "tools" && <ToolsPanel items={toolCalls} />}
            {activeDetailTab === "logs" && (
              <LogsPanel
                logs={logs}
                filter={logFilter}
                onFilter={setLogFilter}
                keyword={logKeyword}
                onKeywordChange={setLogKeyword}
              />
            )}
            {activeDetailTab === "artifacts" && (
              <ArtifactsPanel
                items={artifacts}
                supportsNativeOpen={isTauriRuntime()}
                onCopyPath={(path) => {
                  navigator.clipboard
                    .writeText(path)
                    .then(() =>
                      pushToast({
                        kind: "success",
                        title: "路径已复制",
                        message: path,
                      }),
                    )
                    .catch(() =>
                      pushToast({ kind: "error", title: "复制失败" }),
                    );
                }}
                onOpenPath={(path) => {
                  openPathNative(path)
                    .then((ok) => {
                      if (ok) {
                        pushToast({
                          kind: "success",
                          title: "已打开（系统）",
                          message: path,
                        });
                        return;
                      }
                      const fileUrl = path.startsWith("file://")
                        ? path
                        : `file:///${path.replace(/\\/g, "/")}`;
                      window.open(fileUrl, "_blank", "noopener,noreferrer");
                      pushToast({
                        kind: "info",
                        title: "已请求打开",
                        message: path,
                      });
                    })
                    .catch(() =>
                      pushToast({
                        kind: "error",
                        title: "打开失败",
                        message: path,
                      }),
                    );
                }}
              />
            )}
          </div>
        </aside>
      </div>

      {approvalOpen ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-[480px] rounded-xl border border-border/50 bg-card shadow-codex-lg p-6">
            <h3 className="mb-3 text-base font-semibold text-foreground">
              审批确认
            </h3>
            <p className="mb-4 text-sm text-muted-foreground">
              你即将应用当前 PatchSet 到仓库，是否继续？
            </p>
            <div className="mb-5 space-y-2 rounded-lg border border-border/50 bg-muted/30 p-4 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">文件数</span>
                <span className="font-medium text-foreground">
                  {approvalMeta?.fileCount ?? diffFiles.length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">增删行</span>
                <span className="font-medium text-foreground">
                  <span className="text-emerald-400">
                    +
                    {approvalMeta?.additions ??
                      diffFiles.reduce((sum, f) => sum + f.additions, 0)}
                  </span>
                  {" / "}
                  <span className="text-red-400">
                    -
                    {approvalMeta?.deletions ??
                      diffFiles.reduce((sum, f) => sum + f.deletions, 0)}
                  </span>
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">风险标签</span>
                <span
                  className={cn(
                    "rounded-md px-2 py-0.5 text-xs font-medium",
                    approvalMeta?.risk === "low" &&
                      "bg-emerald-500/10 text-emerald-400",
                    approvalMeta?.risk === "medium" &&
                      "bg-amber-500/10 text-amber-400",
                    approvalMeta?.risk === "high" &&
                      "bg-red-500/10 text-red-400",
                    !approvalMeta?.risk && "bg-amber-500/10 text-amber-400",
                  )}
                >
                  {approvalMeta?.risk ?? "medium"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">应用目标</span>
                <span className="font-medium text-foreground">
                  {approvalMeta?.repoName ?? currentRepo?.name ?? "未选择仓库"}{" "}
                  / {approvalMeta?.branch ?? "main"}
                </span>
              </div>
            </div>
            <div className="flex justify-end gap-3">
              <Button
                variant="outline"
                className="h-9 rounded-lg px-4"
                onClick={() => setApprovalOpen(false)}
              >
                取消
              </Button>
              <Button
                className="h-9 rounded-lg px-4 shadow-sm"
                onClick={() => {
                  setApprovalOpen(false);
                  pushToast({
                    kind: "success",
                    title: "审批通过",
                    message: "已应用变更（模拟）。",
                  });
                }}
              >
                审批并 Apply
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {rollbackConfirmOpen ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-[480px] rounded-xl border border-border/50 bg-card shadow-codex-lg p-6">
            <h3 className="mb-3 text-base font-semibold text-foreground">
              回滚确认
            </h3>
            <p className="mb-5 text-sm text-muted-foreground">
              将回滚当前变更批次。该操作可撤销吗？（MVP 模拟不可撤销）
            </p>
            <div className="flex justify-end gap-3">
              <Button
                variant="outline"
                className="h-9 rounded-lg px-4"
                onClick={() => setRollbackConfirmOpen(false)}
              >
                取消
              </Button>
              <Button
                variant="destructive"
                className="h-9 rounded-lg px-4 shadow-sm"
                onClick={() => {
                  setRollbackConfirmOpen(false);
                  if (!currentSessionId) return;
                  const rollbackArtifact =
                    findLatestRollbackArtifact(artifacts);
                  const rollbackMetaPath = rollbackArtifact
                    ? rollbackMetaPathForArtifact(rollbackArtifact)
                    : null;
                  if (!rollbackMetaPath) {
                    pushToast({
                      kind: "warning",
                      title: "没有可回滚的批次",
                      message: "当前会话还没有 rollback metadata artifact。",
                    });
                    return;
                  }
                  setLoadingTimeline(true);
                  rollbackPatchArtifact(currentSessionId, rollbackMetaPath)
                    .then(() =>
                      Promise.all([
                        getTimeline(currentSessionId)
                          .then(setTimeline)
                          .catch(() => setTimeline([])),
                        getDiffFiles(currentSessionId)
                          .then(setDiffFiles)
                          .catch(() => setDiffFiles([])),
                        getToolCalls(currentSessionId)
                          .then(setToolCalls)
                          .catch(() => setToolCalls([])),
                        getLogs(currentSessionId)
                          .then(setLogs)
                          .catch(() => setLogs([])),
                        getArtifacts(currentSessionId)
                          .then(setArtifacts)
                          .catch(() => setArtifacts([])),
                      ]),
                    )
                    .then(() => {
                      pushToast({
                        kind: "warning",
                        title: "已回滚",
                        message: rollbackMetaPath,
                      });
                    })
                    .catch((error) => {
                      pushToast({
                        kind: "error",
                        title: "回滚失败",
                        message: String(error),
                      });
                    })
                    .finally(() => setLoadingTimeline(false));
                }}
              >
                确认回滚
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {sensitivePrompt ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-[500px] rounded-xl border border-border/50 bg-card shadow-codex-lg p-6">
            <h3 className="mb-3 text-base font-semibold text-foreground">
              敏感操作确认
            </h3>
            <p className="mb-4 text-sm text-muted-foreground">
              操作{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">
                {sensitivePrompt.action}
              </code>{" "}
              需要确认。是否允许？
            </p>
            <label className="mb-5 flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={sensitivePrompt.remember}
                onChange={(e) =>
                  setSensitivePrompt({
                    ...sensitivePrompt,
                    remember: e.target.checked,
                  })
                }
                className="h-4 w-4 rounded border-border bg-background"
              />
              记住本仓库策略
            </label>
            <div className="flex justify-end gap-3">
              <Button
                variant="outline"
                className="h-9 rounded-lg px-4"
                onClick={() => {
                  if (currentRepoId && sensitivePrompt.remember) {
                    setPolicy(currentRepoId, sensitivePrompt.action, "deny");
                  }
                  pendingSensitiveAllowRef.current = null;
                  pushToast({ kind: "warning", title: "已拒绝敏感操作" });
                  setSensitivePrompt(null);
                }}
              >
                拒绝
              </Button>
              <Button
                className="h-9 rounded-lg px-4 shadow-sm"
                onClick={() => {
                  if (currentRepoId && sensitivePrompt.remember) {
                    setPolicy(currentRepoId, sensitivePrompt.action, "allow");
                  }
                  pendingSensitiveAllowRef.current?.();
                  pendingSensitiveAllowRef.current = null;
                  pushToast({ kind: "success", title: "已允许敏感操作" });
                  setSensitivePrompt(null);
                }}
              >
                允许
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
