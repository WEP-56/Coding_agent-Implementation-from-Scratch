import { useState } from "react";
import { cn } from "../../lib/utils";
import type { RepoItem, SessionItem } from "../../types/models";
import { useUiStore } from "../../store/ui-store";

function formatSessionDate(raw: string): string {
  const numeric = /^\d+$/.test(raw) ? Number(raw) : NaN;
  const date = Number.isFinite(numeric) ? new Date(numeric) : new Date(raw);
  if (Number.isNaN(date.getTime())) return "时间未知";
  return date.toLocaleDateString();
}

interface LeftSidebarProps {
  repos: RepoItem[];
  sessions: SessionItem[];
  currentRepoId: string | null;
  currentSessionId: string | null;
  onRepoSelect: (id: string) => void;
  onSessionSelect: (id: string) => void;
  onSessionCreate: (repoId: string, title: string, mode: "plan" | "build" | "auto") => void;
  onSessionDelete: (id: string) => void;
}

export function LeftSidebar({
  repos,
  sessions,
  currentRepoId,
  currentSessionId,
  onRepoSelect,
  onSessionSelect,
  onSessionCreate,
  onSessionDelete,
}: LeftSidebarProps) {
  const pushToast = useUiStore((s) => s.pushToast);
  const [expandedRepoId, setExpandedRepoId] = useState<string | null>(currentRepoId);
  const [creatingSessionForRepo, setCreatingSessionForRepo] = useState<string | null>(null);
  const [newSessionTitle, setNewSessionTitle] = useState("");

  const handleRepoClick = (repoId: string) => {
    if (expandedRepoId === repoId) {
      setExpandedRepoId(null);
    } else {
      setExpandedRepoId(repoId);
      onRepoSelect(repoId);
    }
  };

  const handleCreateSession = (repoId: string) => {
    const title = newSessionTitle.trim() || "新会话";
    onSessionCreate(repoId, title, "build");
    setNewSessionTitle("");
    setCreatingSessionForRepo(null);
    pushToast({ kind: "info", title: "正在创建会话", message: title });
  };

  const getRepoSessions = (repoId: string) => {
    return sessions.filter((s) => s.repoId === repoId);
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-border/50 px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">项目</h2>
      </div>

      {/* Projects List */}
      <div className="flex-1 overflow-y-auto p-2">
        {repos.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border/50 bg-card/30 p-4 text-center">
            <p className="mb-3 text-sm text-muted-foreground">还没有项目</p>
            <button className="w-full rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors">
              导入项目
            </button>
          </div>
        ) : (
          <div className="space-y-1">
            {repos.map((repo) => {
              const repoSessions = getRepoSessions(repo.id);
              const isExpanded = expandedRepoId === repo.id;

              return (
                <div key={repo.id} className="space-y-1">
                  {/* Repo Item */}
                  <button
                    onClick={() => handleRepoClick(repo.id)}
                    className={cn(
                      "group w-full rounded-lg px-3 py-2.5 text-left transition-colors",
                      currentRepoId === repo.id
                        ? "bg-accent"
                        : "hover:bg-accent/50"
                    )}
                  >
                    <div className="flex items-center gap-2">
                      {/* Expand Icon */}
                      <svg
                        className={cn(
                          "h-4 w-4 flex-shrink-0 text-muted-foreground transition-transform",
                          isExpanded && "rotate-90"
                        )}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>

                      {/* Folder Icon */}
                      <svg className="h-4 w-4 flex-shrink-0 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                      </svg>

                      {/* Repo Info */}
                      <div className="flex-1 overflow-hidden">
                        <div className="truncate text-sm font-medium text-foreground">
                          {repo.name}
                        </div>
                        <div className="truncate text-xs text-muted-foreground">
                          {repoSessions.length} 个会话
                        </div>
                      </div>
                    </div>
                  </button>

                  {/* Sessions List (when expanded) */}
                  {isExpanded && (
                    <div className="ml-6 space-y-1 border-l border-border/50 pl-2">
                      {repoSessions.map((session) => (
                        <div
                          key={session.id}
                          className={cn(
                            "group relative rounded-md px-3 py-2 transition-colors",
                            currentSessionId === session.id
                              ? "bg-accent/70"
                              : "hover:bg-accent/30"
                          )}
                        >
                          <button
                            onClick={() => onSessionSelect(session.id)}
                            className="w-full text-left"
                          >
                            <div className="truncate text-sm text-foreground">
                              {session.title}
                            </div>
                            <div className="mt-0.5 text-xs text-muted-foreground">
                              {formatSessionDate(session.updatedAt)}
                            </div>
                          </button>
                          <button
                            onClick={() => onSessionDelete(session.id)}
                            className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 rounded p-1 hover:bg-destructive/10 transition-opacity"
                            title="删除会话"
                          >
                            <svg className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </div>
                      ))}

                      {/* Create New Session */}
                      {creatingSessionForRepo === repo.id ? (
                        <div className="rounded-md bg-card/50 p-2">
                          <input
                            id={`new-session-title-${repo.id}`}
                            name="new-session-title"
                            type="text"
                            value={newSessionTitle}
                            onChange={(e) => setNewSessionTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleCreateSession(repo.id);
                              if (e.key === "Escape") {
                                setCreatingSessionForRepo(null);
                                setNewSessionTitle("");
                              }
                            }}
                            placeholder="会话标题"
                            className="w-full rounded border border-input bg-background px-2 py-1 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                            autoFocus
                          />
                          <div className="mt-1 flex gap-1">
                            <button
                              onClick={() => handleCreateSession(repo.id)}
                              className="flex-1 rounded bg-primary px-2 py-1 text-xs text-primary-foreground hover:bg-primary/90"
                            >
                              创建
                            </button>
                            <button
                              onClick={() => {
                                setCreatingSessionForRepo(null);
                                setNewSessionTitle("");
                              }}
                              className="flex-1 rounded border border-border/50 px-2 py-1 text-xs hover:bg-accent"
                            >
                              取消
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          onClick={() => setCreatingSessionForRepo(repo.id)}
                          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent/30 hover:text-foreground transition-colors"
                        >
                          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                          </svg>
                          <span>新建会话</span>
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
