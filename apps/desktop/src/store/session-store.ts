import { create } from "zustand";

import type {
  ArtifactItem,
  DetailTab,
  DiffFile,
  DiffViewMode,
  LogItem,
  LogLevel,
  ChatMessage,
  SessionItem,
  TimelineStep,
  ToolCallItem,
  WorkflowRunCard,
} from "../types/models";

import { getChatHistory } from "../api/bridge";

interface SessionState {
  sessions: SessionItem[];
  globalSessions: SessionItem[];
  currentSessionId: string | null;
  timeline: TimelineStep[];
  diffFiles: DiffFile[];
  selectedDiffFileId: string | null;
  diffViewMode: DiffViewMode;
  toolCalls: ToolCallItem[];
  logs: LogItem[];
  logFilter: LogLevel | "all";
  logKeyword: string;
  artifacts: ArtifactItem[];
  messagesBySession: Record<string, ChatMessage[]>;
  workflowRunsBySession: Record<string, WorkflowRunCard[]>;
  pastTimeline: TimelineStep[][];
  futureTimeline: TimelineStep[][];
  summaryBySession: Record<string, string>;
  activeDetailTab: DetailTab;
  leftView: "repo" | "global";
  leftWidth: number;
  rightWidth: number;
  isLoadingSessions: boolean;
  isLoadingTimeline: boolean;
  errorText: string | null;
  setSessions: (sessions: SessionItem[]) => void;
  setGlobalSessions: (sessions: SessionItem[]) => void;
  setCurrentSession: (sessionId: string) => void;
  createSession: (input: { repoId: string; title: string; mode: SessionItem["mode"] }) => string;
  deleteSession: (sessionId: string) => void;
  updateSessionMode: (sessionId: string, mode: SessionItem["mode"]) => void;
  setTimeline: (timeline: TimelineStep[]) => void;
  setDiffFiles: (files: DiffFile[]) => void;
  setSelectedDiffFile: (fileId: string | null) => void;
  setDiffViewMode: (mode: DiffViewMode) => void;
  setToolCalls: (calls: ToolCallItem[]) => void;
  setLogs: (items: LogItem[]) => void;
  setLogFilter: (filter: LogLevel | "all") => void;
  setLogKeyword: (keyword: string) => void;
  setArtifacts: (items: ArtifactItem[]) => void;
  getMessages: (sessionId: string | null) => ChatMessage[];
  appendMessage: (sessionId: string, role: ChatMessage["role"], content: string) => void;
  addWorkflowRun: (sessionId: string, run: WorkflowRunCard) => void;
  updateWorkflowRun: (sessionId: string, runId: string, patch: Partial<WorkflowRunCard>) => void;
  loadSessionMessagesFromBackend: (sessionId: string) => Promise<void>;
  retryStep: (stepId: string) => void;
  rollbackCurrentBatch: () => void;
  openDiagnosis: () => void;
  undoTimeline: () => void;
  redoTimeline: () => void;
  canUndoTimeline: () => boolean;
  canRedoTimeline: () => boolean;
  getSessionSummary: (sessionId: string) => string;
  setSessionSummary: (sessionId: string, summary: string) => void;
  setActiveDetailTab: (tab: DetailTab) => void;
  setLeftView: (v: "repo" | "global") => void;
  setPanelWidths: (leftWidth: number, rightWidth: number) => void;
  setLoadingSessions: (v: boolean) => void;
  setLoadingTimeline: (v: boolean) => void;
  setError: (v: string | null) => void;
}

function deriveTimelineSummary(items: TimelineStep[]): string {
  const failed = items.find((step) => step.status === "failed");
  if (failed) return `失败：${failed.title}`;
  const running = items.find((step) => step.status === "running");
  if (running) return `执行中：${running.title}`;
  const pending = items.find((step) => step.status === "pending");
  if (pending) return `等待中：${pending.title}`;
  return items.length > 0 ? "已完成" : "未开始";
}

function isSameTimeline(a: TimelineStep[], b: TimelineStep[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((step, idx) => {
    const other = b[idx];
    return !!other && step.id === other.id && step.status === other.status && step.title === other.title && step.detail === other.detail;
  });
}

const LAYOUT_KEY = "codinggirl.workspace.layout";

function readLayout(): { leftWidth: number; rightWidth: number; detailTab: DetailTab; leftView: "repo" | "global" } {
  try {
    const raw = window.localStorage.getItem(LAYOUT_KEY);
    if (!raw) {
      return { leftWidth: 280, rightWidth: 360, detailTab: "diff", leftView: "repo" };
    }
    const obj = JSON.parse(raw) as Partial<{
      leftWidth: number;
      rightWidth: number;
      detailTab: DetailTab;
      leftView: "repo" | "global";
    }>;
    const leftWidth = typeof obj.leftWidth === "number" ? obj.leftWidth : 280;
    const rightWidth = typeof obj.rightWidth === "number" ? obj.rightWidth : 360;
    const detailTab = obj.detailTab ?? "diff";
    const leftView = obj.leftView ?? "repo";
    return { leftWidth, rightWidth, detailTab, leftView };
  } catch {
    return { leftWidth: 280, rightWidth: 360, detailTab: "diff", leftView: "repo" };
  }
}

function saveLayout(layout: { leftWidth: number; rightWidth: number; detailTab: DetailTab; leftView: "repo" | "global" }): void {
  window.localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout));
}

const initialLayout = readLayout();

export const useSessionStore = create<SessionState>((set, get) => ({
  sessions: [],
  globalSessions: [],
  currentSessionId: null,
  timeline: [],
  diffFiles: [],
  selectedDiffFileId: null,
  diffViewMode: "split",
  toolCalls: [],
  logs: [],
  logFilter: "all",
  logKeyword: "",
  artifacts: [],
  messagesBySession: {},
  workflowRunsBySession: {},
  pastTimeline: [],
  futureTimeline: [],
  summaryBySession: {},
  activeDetailTab: initialLayout.detailTab,
  leftView: initialLayout.leftView,
  leftWidth: initialLayout.leftWidth,
  rightWidth: initialLayout.rightWidth,
  isLoadingSessions: false,
  isLoadingTimeline: false,
  errorText: null,
  setSessions: (sessions) =>
    set((state) => ({
      sessions,
      currentSessionId: sessions.some((s) => s.id === state.currentSessionId)
        ? state.currentSessionId
        : (sessions[0]?.id ?? null),
    })),
  setGlobalSessions: (sessions) => set({ globalSessions: sessions }),
  setCurrentSession: (sessionId) =>
    set({
      currentSessionId: sessionId,
      timeline: [],
      pastTimeline: [],
      futureTimeline: [],
      logFilter: "all",
      logKeyword: "",
      selectedDiffFileId: null,
      diffFiles: [],
      toolCalls: [],
      logs: [],
      artifacts: [],
    }),
  createSession: ({ repoId, title, mode }) => {
    const id = `s-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const item: SessionItem = {
      id,
      repoId,
      title,
      mode,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    set((state) => ({
      sessions: [item, ...state.sessions],
      globalSessions: [item, ...state.globalSessions],
      currentSessionId: id,
    }));
    return id;
  },
  deleteSession: (sessionId) => {
    const { sessions, globalSessions, currentSessionId } = get();
    const nextSessions = sessions.filter((s) => s.id !== sessionId);
    const nextGlobal = globalSessions.filter((s) => s.id !== sessionId);
    const nextCurrent = currentSessionId === sessionId ? (nextSessions[0]?.id ?? null) : currentSessionId;
    set({ sessions: nextSessions, globalSessions: nextGlobal, currentSessionId: nextCurrent });
  },
  updateSessionMode: (sessionId, mode) => {
    const update = (arr: SessionItem[]) =>
      arr.map((s) => (s.id === sessionId ? { ...s, mode, updatedAt: new Date().toISOString() } : s));
    set((state) => ({ sessions: update(state.sessions), globalSessions: update(state.globalSessions) }));
  },
  setTimeline: (timeline) =>
    set((state) => {
      if (isSameTimeline(state.timeline, timeline)) {
        return state;
      }
      const currentSessionId = get().currentSessionId;
      return {
        timeline,
        pastTimeline: [...state.pastTimeline, state.timeline],
        futureTimeline: [],
        summaryBySession: currentSessionId
          ? { ...state.summaryBySession, [currentSessionId]: deriveTimelineSummary(timeline) }
          : state.summaryBySession,
      };
    }),
  setDiffFiles: (files) =>
    set((state) => ({
      diffFiles: files,
      selectedDiffFileId: state.selectedDiffFileId ?? files[0]?.id ?? null,
    })),
  setSelectedDiffFile: (fileId) => set({ selectedDiffFileId: fileId }),
  setDiffViewMode: (mode) => set({ diffViewMode: mode }),
  setToolCalls: (calls) => set({ toolCalls: calls }),
  setLogs: (items) => set({ logs: items }),
  setLogFilter: (filter) => set({ logFilter: filter }),
  setLogKeyword: (keyword) => set({ logKeyword: keyword }),
  setArtifacts: (items) => set({ artifacts: items }),
  getMessages: (sessionId) => {
    if (!sessionId) return [];
    return get().messagesBySession[sessionId] ?? [];
  },
  appendMessage: (sessionId, role, content) => {
    const msg: ChatMessage = {
      id: `m-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      sessionId,
      role,
      content,
      createdAt: new Date().toISOString(),
    };
    set((state) => {
      const existing = state.messagesBySession[sessionId] ?? [];
      return {
        messagesBySession: {
          ...state.messagesBySession,
          [sessionId]: [...existing, msg],
        },
      };
    });
  },
  addWorkflowRun: (sessionId, run) => {
    set((state) => {
      const current = state.workflowRunsBySession[sessionId] ?? [];
      const next = [run, ...current].slice(0, 20);
      return {
        workflowRunsBySession: {
          ...state.workflowRunsBySession,
          [sessionId]: next,
        },
      };
    });
  },
  updateWorkflowRun: (sessionId, runId, patch) => {
    set((state) => {
      const current = state.workflowRunsBySession[sessionId] ?? [];
      const next = current.map((r) => (r.id === runId ? { ...r, ...patch } : r));
      return {
        workflowRunsBySession: {
          ...state.workflowRunsBySession,
          [sessionId]: next,
        },
      };
    });
  },
  loadSessionMessagesFromBackend: async (sessionId) => {
    try {
      const turns = await getChatHistory(sessionId);
      const mapped: ChatMessage[] = turns.map((t, idx) => ({
        id: `m-backend-${sessionId}-${idx}`,
        sessionId,
        role: t.role === "user" || t.role === "assistant" || t.role === "system" ? t.role : "system",
        content: String(t.content ?? ""),
        createdAt: new Date().toISOString(),
      }));
      set((state) => ({
        messagesBySession: {
          ...state.messagesBySession,
          [sessionId]: mapped,
        },
      }));
    } catch {
      // non-blocking
    }
  },
  retryStep: (stepId) => {
    const nextTimeline = get().timeline.map((t) => {
      if (t.id !== stepId) return t;
      return {
        ...t,
        status: "running" as const,
        detail: "正在重试此步骤...",
      };
    });
    get().setTimeline(nextTimeline);
  },
  rollbackCurrentBatch: () => {
    const current = get().timeline;
    const nextTimeline = current.map((t, idx) =>
      idx === current.length - 1 ? { ...t, status: "pending" as const, detail: "已执行回滚，等待重新运行" } : t,
    );
    get().setTimeline(nextTimeline);
  },
  openDiagnosis: () => {
    const nextTimeline = get().timeline.map((t) =>
      t.status === "failed"
        ? { ...t, detail: `${t.detail ?? "执行失败"} | 诊断：请检查工具调用日志与变更上下文。` }
        : t,
    );
    get().setTimeline(nextTimeline);
  },
  undoTimeline: () => {
    const { pastTimeline, timeline, currentSessionId } = get();
    if (pastTimeline.length === 0) return;
    const previous = pastTimeline[pastTimeline.length - 1] ?? [];
    set((state) => ({
      timeline: previous,
      pastTimeline: state.pastTimeline.slice(0, -1),
      futureTimeline: [...state.futureTimeline, timeline],
      summaryBySession: currentSessionId
        ? { ...state.summaryBySession, [currentSessionId]: deriveTimelineSummary(previous) }
        : state.summaryBySession,
    }));
  },
  redoTimeline: () => {
    const { futureTimeline, timeline, currentSessionId } = get();
    if (futureTimeline.length === 0) return;
    const next = futureTimeline[futureTimeline.length - 1] ?? [];
    set((state) => ({
      timeline: next,
      futureTimeline: state.futureTimeline.slice(0, -1),
      pastTimeline: [...state.pastTimeline, timeline],
      summaryBySession: currentSessionId
        ? { ...state.summaryBySession, [currentSessionId]: deriveTimelineSummary(next) }
        : state.summaryBySession,
    }));
  },
  canUndoTimeline: () => get().pastTimeline.length > 0,
  canRedoTimeline: () => get().futureTimeline.length > 0,
  getSessionSummary: (sessionId) => {
    return get().summaryBySession[sessionId] ?? "未开始";
  },
  setSessionSummary: (sessionId, summary) => {
    set((state) => ({ summaryBySession: { ...state.summaryBySession, [sessionId]: summary } }));
  },
  setActiveDetailTab: (tab) => {
    const current = get();
    saveLayout({
      leftWidth: current.leftWidth,
      rightWidth: current.rightWidth,
      detailTab: tab,
      leftView: current.leftView,
    });
    set({ activeDetailTab: tab });
  },
  setLeftView: (v) => {
    const current = get();
    saveLayout({
      leftWidth: current.leftWidth,
      rightWidth: current.rightWidth,
      detailTab: current.activeDetailTab,
      leftView: v,
    });
    set({ leftView: v });
  },
  setPanelWidths: (leftWidth, rightWidth) => {
    const current = get();
    saveLayout({ leftWidth, rightWidth, detailTab: current.activeDetailTab, leftView: current.leftView });
    set({ leftWidth, rightWidth });
  },
  setLoadingSessions: (v) => set({ isLoadingSessions: v }),
  setLoadingTimeline: (v) => set({ isLoadingTimeline: v }),
  setError: (v) => set({ errorText: v }),
}));
