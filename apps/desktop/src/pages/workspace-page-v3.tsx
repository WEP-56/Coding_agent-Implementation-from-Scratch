import { useEffect, useRef, useState } from "react";

import { ChatArea } from "../components/workspace/chat-area";
import { LeftSidebar } from "../components/workspace/left-sidebar";
import { RightSidebar } from "../components/workspace/right-sidebar";
import { TerminalPanel } from "../components/workspace/terminal-panel";
import { WorkspaceLayout } from "../components/workspace/workspace-layout";
import { CustomTitlebar } from "../components/layout/custom-titlebar";
import {
  addRepo,
  cancelPythonAgentRun,
  createSession as createSessionRemote,
  deleteSession as deleteSessionRemote,
  exportTraceBundle,
  getArtifacts,
  getDiffFiles,
  getLogs,
  getTimeline,
  getToolCalls,
  listenSessionWorkflowSnapshot,
  listRepos as listReposRemote,
  listSessionRuns,
  listSessions,
  listSessionTurns,
  openPathInExplorer,
  openPathInVscode,
  rollbackPatchArtifact,
  runPythonAgentMessage,
  updateSessionMode as updateSessionModeRemote,
} from "../api/bridge";
import {
  findLatestRollbackArtifact,
  rollbackMetaPathForArtifact,
} from "../lib/mutation";
import { useAppStore } from "../store/app-store";
import { useSessionStore } from "../store/session-store";
import { useUiStore } from "../store/ui-store";
import type {
  PythonTodoState,
  SessionMode,
  SessionRun,
  SessionTurn,
} from "../types/models";

export function WorkspacePageV3() {
  const { repos, currentRepoId, setRepos, setCurrentRepo } = useAppStore();
  const {
    sessions,
    currentSessionId,
    timeline,
    diffFiles,
    toolCalls,
    logs,
    isLoadingTimeline,
    setSessions,
    setCurrentSession,
    deleteSession,
    updateSessionMode,
    setTimeline,
    setDiffFiles,
    setToolCalls,
    setLogs,
    setArtifacts,
    artifacts,
    getMessages,
    appendMessage,
    loadSessionMessagesFromBackend,
    retryStep,
    setLoadingTimeline,
  } = useSessionStore();
  const pushToast = useUiStore((s) => s.pushToast);

  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [terminalVisible, setTerminalVisible] = useState(false);
  const [sessionRuns, setSessionRuns] = useState<SessionRun[]>([]);
  const [sessionTurns, setSessionTurns] = useState<SessionTurn[]>([]);
  const [pythonTodo, setPythonTodo] = useState<PythonTodoState | null>(null);
  const currentSessionIdRef = useRef<string | null>(currentSessionId);

  const currentSession = sessions.find((s) => s.id === currentSessionId);
  const currentRepo =
    repos.find(
      (repo) => repo.id === (currentSession?.repoId ?? currentRepoId),
    ) ?? null;
  const currentRepoPath = currentRepo?.path ?? null;
  const messages = getMessages(currentSessionId);

  const refreshWorkflowState = (sessionId: string) =>
    Promise.all([
      getTimeline(sessionId),
      getDiffFiles(sessionId),
      getToolCalls(sessionId),
      getLogs(sessionId),
      getArtifacts(sessionId),
      listSessionRuns(sessionId),
      listSessionTurns(sessionId),
    ]).then(
      ([nextTimeline, diffs, tools, logItems, artifactItems, runs, turns]) => {
        if (currentSessionIdRef.current !== sessionId) {
          return;
        }
        setTimeline(nextTimeline);
        setDiffFiles(diffs);
        setToolCalls(tools);
        setLogs(logItems);
        setArtifacts(artifactItems);
        setSessionRuns(runs);
        setSessionTurns(turns);
      },
    );

  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  useEffect(() => {
    let active = true;
    let dispose: (() => void) | null = null;
    void listenSessionWorkflowSnapshot((event) => {
      if (!active) return;
      if (event.sessionId !== currentSessionIdRef.current) return;
      setTimeline(event.timeline);
      setDiffFiles(event.diffFiles);
      setToolCalls(event.toolCalls);
      setLogs(event.logs);
      setArtifacts(event.artifacts);
      setSessionRuns(event.sessionRuns);
      setSessionTurns(event.sessionTurns);
      setPythonTodo(event.pythonTodo ?? null);
    }).then((unlisten) => {
      if (!active) {
        unlisten();
        return;
      }
      dispose = unlisten;
    });
    return () => {
      active = false;
      if (dispose) dispose();
    };
  }, []);

  useEffect(() => {
    if (!currentSessionId) return;
    if (getMessages(currentSessionId).length > 0) return;
    loadSessionMessagesFromBackend(currentSessionId).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSessionId]);

  useEffect(() => {
    listReposRemote()
      .then(setRepos)
      .catch((e) => {
        pushToast({ kind: "error", title: "加载仓库失败", message: String(e) });
      });
  }, [setRepos, pushToast]);

  useEffect(() => {
    if (repos.length === 0) return;
    if (currentRepoId && repos.some((r) => r.id === currentRepoId)) return;
    setCurrentRepo(repos[0].id);
  }, [repos, currentRepoId, setCurrentRepo]);

  useEffect(() => {
    if (!currentRepoId) {
      setSessions([]);
      return;
    }
    listSessions(currentRepoId)
      .then(setSessions)
      .catch((e) => {
        pushToast({ kind: "error", title: "加载会话失败", message: String(e) });
        setSessions([]);
      });
  }, [currentRepoId, setSessions, pushToast]);

  useEffect(() => {
    setLoadingTimeline(true);
    if (!currentSessionId) {
      setTimeline([]);
      setSessionRuns([]);
      setSessionTurns([]);
      setLoadingTimeline(false);
      return;
    }
    Promise.all([
      getTimeline(currentSessionId),
      listSessionRuns(currentSessionId),
      listSessionTurns(currentSessionId),
    ])
      .then(([items, runs, turns]) => {
        setTimeline(items);
        setSessionRuns(runs);
        setSessionTurns(turns);
        const failed = items.find((i) => i.status === "failed");
        if (failed) {
          pushToast({
            kind: "error",
            title: "执行失败",
            message: `步骤「${failed.title}」失败`,
          });
        }
      })
      .catch((e) => {
        pushToast({
          kind: "error",
          title: "加载时间线失败",
          message: String(e),
        });
        setTimeline([]);
        setSessionRuns([]);
        setSessionTurns([]);
      })
      .finally(() => setLoadingTimeline(false));
  }, [currentSessionId, setTimeline, setLoadingTimeline, pushToast]);

  useEffect(() => {
    if (!currentSessionId) {
      setDiffFiles([]);
      setToolCalls([]);
      setLogs([]);
      setArtifacts([]);
      setSessionTurns([]);
      return;
    }
    Promise.all([
      getDiffFiles(currentSessionId),
      getToolCalls(currentSessionId),
      getLogs(currentSessionId),
      getArtifacts(currentSessionId),
    ])
      .then(([diffs, tools, logItems, artifactItems]) => {
        setDiffFiles(diffs);
        setToolCalls(tools);
        setLogs(logItems);
        setArtifacts(artifactItems);
      })
      .catch(() => undefined);
  }, [currentSessionId, setDiffFiles, setToolCalls, setLogs, setArtifacts]);

  const handleSessionCreate = (
    repoId: string,
    title: string,
    mode: SessionMode,
  ) => {
    const repo = repos.find((r) => r.id === repoId);
    const ensureRepo = repo
      ? addRepo(repo.path).catch(() => undefined)
      : Promise.resolve(undefined);
    ensureRepo.then(() =>
      createSessionRemote(repoId, title, mode)
        .then((item) => {
          if (item.repoId !== repoId) {
            setCurrentRepo(item.repoId);
          }
          setSessions([
            {
              id: item.id,
              repoId: item.repoId,
              title: item.title,
              mode: item.mode,
              createdAt: item.createdAt,
              updatedAt: item.updatedAt,
            },
            ...sessions.filter((s) => s.id !== item.id),
          ]);
          setCurrentSession(item.id);
          appendMessage(item.id, "system", `已创建会话，模式：${mode}`);
          pushToast({ kind: "success", title: "会话已创建" });
          listSessions(item.repoId)
            .then(setSessions)
            .catch(() => undefined);
        })
        .catch((e) => {
          pushToast({
            kind: "error",
            title: "创建会话失败",
            message: String(e),
          });
        }),
    );
  };

  const handleSessionDelete = (id: string) => {
    deleteSessionRemote(id)
      .then(() => {
        if (!currentRepoId) {
          deleteSession(id);
          pushToast({ kind: "info", title: "会话已删除" });
          return;
        }
        return listSessions(currentRepoId).then((items) => {
          setSessions(items);
          pushToast({ kind: "info", title: "会话已删除" });
        });
      })
      .catch((e) =>
        pushToast({ kind: "error", title: "删除会话失败", message: String(e) }),
      );
  };

  const handleModeChange = (mode: SessionMode) => {
    if (!currentSessionId) return;
    updateSessionModeRemote(currentSessionId, mode)
      .then(() => {
        updateSessionMode(currentSessionId, mode);
        pushToast({
          kind: "info",
          title: "模式已更新",
          message: `当前模式：${mode}`,
        });
        if (currentRepoId) {
          listSessions(currentRepoId)
            .then(setSessions)
            .catch(() => undefined);
        }
      })
      .catch((e) =>
        pushToast({ kind: "error", title: "模式更新失败", message: String(e) }),
      );
  };

  const handleSend = (text: string, mode: SessionMode) => {
    if (!currentSessionId) return;

    if (currentSession && currentSession.mode !== mode) {
      updateSessionModeRemote(currentSessionId, mode)
        .then(() => updateSessionMode(currentSessionId, mode))
        .catch((e) =>
          pushToast({
            kind: "error",
            title: "模式同步失败",
            message: String(e),
          }),
        );
    }

    appendMessage(currentSessionId, "user", text);
    setLoadingTimeline(true);

    runPythonAgentMessage(currentSessionId, mode, text)
      .then((result) => {
        appendMessage(currentSessionId, "assistant", result.assistantMessage);
        setTimeline(result.timeline);
      })
      .catch((e) => {
        appendMessage(currentSessionId, "system", `执行失败：${String(e)}`);
        pushToast({ kind: "error", title: "执行失败", message: String(e) });
      })
      .finally(() => {
        setLoadingTimeline(false);
      });
  };

  const handleStop = () => {
    if (!currentSessionId) return;
    cancelPythonAgentRun(currentSessionId)
      .then((ok) => {
        pushToast({
          kind: "info",
          title: ok ? "已请求停止" : "当前没有可停止的任务",
        });
      })
      .catch((e) =>
        pushToast({ kind: "error", title: "停止失败", message: String(e) }),
      );
  };

  const handleTerminalCommandLifecycle = (
    _phase: "started" | "finished",
    _sessionId: string,
  ) => {
    // Kept for future: terminal runs also emit workflow snapshots via backend events.
  };

  const handleRollback = () => {
    if (!currentSessionId) return;
    const rollbackArtifact = findLatestRollbackArtifact(artifacts);
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
      .then(() => {
        pushToast({
          kind: "warning",
          title: "已回滚变更",
          message: rollbackMetaPath,
        });
        return refreshWorkflowState(currentSessionId);
      })
      .catch((error) => {
        pushToast({
          kind: "error",
          title: "回滚失败",
          message: String(error),
        });
      })
      .finally(() => setLoadingTimeline(false));
  };

  const handleRetryStep = (stepId: string) => {
    retryStep(stepId);
    pushToast({ kind: "info", title: "正在重试..." });
  };

  const handleExportTrace = () => {
    if (!currentSessionId) return;
    exportTraceBundle(currentSessionId)
      .then((res) => {
        pushToast({
          kind: "success",
          title: "Trace 已导出",
          message: res.filePath,
        });
      })
      .catch((e) => {
        pushToast({
          kind: "error",
          title: "Trace 导出失败",
          message: String(e),
        });
      });
  };

  const handleOpenInExplorer = () => {
    if (!currentRepoPath) {
      pushToast({ kind: "warning", title: "没有可打开的工作区" });
      return;
    }
    openPathInExplorer(currentRepoPath).catch((error) => {
      pushToast({
        kind: "error",
        title: "打开资源管理器失败",
        message: String(error),
      });
    });
  };

  const handleOpenInVscode = () => {
    if (!currentRepoPath) {
      pushToast({ kind: "warning", title: "没有可打开的工作区" });
      return;
    }
    openPathInVscode(currentRepoPath).catch((error) => {
      pushToast({
        kind: "error",
        title: "打开 VS Code 失败",
        message: String(error),
      });
    });
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <CustomTitlebar
        onToggleLeftSidebar={() => setLeftCollapsed(!leftCollapsed)}
        onToggleRightSidebar={() => setRightCollapsed(!rightCollapsed)}
        onToggleTerminal={() => setTerminalVisible(!terminalVisible)}
        onOpenInExplorer={handleOpenInExplorer}
        onOpenInVscode={handleOpenInVscode}
        leftSidebarVisible={!leftCollapsed}
        rightSidebarVisible={!rightCollapsed}
        terminalVisible={terminalVisible}
        workspacePath={currentRepoPath}
      />
      <div className="flex-1 overflow-hidden">
        <WorkspaceLayout
          bottomPanel={
            <TerminalPanel
              onCommandLifecycle={handleTerminalCommandLifecycle}
              repoPath={currentRepoPath}
              sessionId={currentSessionId}
            />
          }
          bottomPanelVisible={terminalVisible}
          leftCollapsed={leftCollapsed}
          rightCollapsed={rightCollapsed}
          onLeftToggle={() => setLeftCollapsed(!leftCollapsed)}
          onRightToggle={() => setRightCollapsed(!rightCollapsed)}
          leftSidebar={
            <LeftSidebar
              repos={repos}
              sessions={sessions}
              currentRepoId={currentRepoId}
              currentSessionId={currentSessionId}
              onRepoSelect={setCurrentRepo}
              onSessionSelect={setCurrentSession}
              onSessionCreate={handleSessionCreate}
              onSessionDelete={handleSessionDelete}
            />
          }
          rightSidebar={
            <RightSidebar
              sessionId={currentSessionId}
              traceVersion={`${sessionTurns.length}:${sessionTurns[0]?.updatedAt ?? "empty"}:${timeline.length}:${timeline[0]?.status ?? "none"}`}
            />
          }
        >
          <ChatArea
            sessionId={currentSessionId}
            messages={messages}
            timeline={timeline}
            diffFiles={diffFiles}
            toolCalls={toolCalls}
            logs={logs}
            artifacts={artifacts}
            sessionRuns={sessionRuns}
            sessionTurns={sessionTurns}
            pythonTodo={pythonTodo}
            currentMode={currentSession?.mode ?? "build"}
            isRunning={isLoadingTimeline}
            onSend={handleSend}
            onStop={handleStop}
            onModeChange={handleModeChange}
            onRetryStep={handleRetryStep}
            onRollback={handleRollback}
            onExportTrace={handleExportTrace}
          />
        </WorkspaceLayout>
      </div>
    </div>
  );
}
