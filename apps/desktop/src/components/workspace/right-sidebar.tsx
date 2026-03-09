import { useEffect, useState } from "react";

import { getSessionContextDebug, listRepoTree, readRepoFile, writeRepoFile } from "../../api/bridge";
import { cn } from "../../lib/utils";
import type { RepoFileContent, RepoTreeEntry, SessionContextDebugSnapshot } from "../../types/models";
import { ContextPanel } from "./context-panel";
import { MemoryPanel } from "./memory-panel";

interface RightSidebarProps {
  sessionId: string | null;
  traceVersion?: string;
}

type TabType = "files" | "memory" | "context";

export function RightSidebar({ sessionId, traceVersion }: RightSidebarProps) {
  const [activeTab, setActiveTab] = useState<TabType>("files");
  const [repoTree, setRepoTree] = useState<RepoTreeEntry[]>([]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [filePreview, setFilePreview] = useState<RepoFileContent | null>(null);
  const [loadingFile, setLoadingFile] = useState(false);
  const [draftContent, setDraftContent] = useState("");
  const [contextSnapshot, setContextSnapshot] = useState<SessionContextDebugSnapshot | null>(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [contextError, setContextError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId || activeTab !== "files") return;
    let canceled = false;
    void listRepoTree(sessionId)
      .then((items) => {
        if (!canceled) setRepoTree(items);
      })
      .catch(() => {
        if (!canceled) setRepoTree([]);
      });
    return () => {
      canceled = true;
    };
  }, [sessionId, activeTab]);

  useEffect(() => {
    if (!sessionId || activeTab !== "context") {
      setContextSnapshot(null);
      setContextLoading(false);
      setContextError(null);
      return;
    }
    let canceled = false;
    setContextLoading(true);
    setContextError(null);
    void getSessionContextDebug(sessionId)
      .then((snapshot) => {
        if (!canceled) {
          setContextSnapshot(snapshot);
        }
      })
      .catch((error) => {
        if (!canceled) {
          setContextSnapshot(null);
          setContextError(String(error));
        }
      })
      .finally(() => {
        if (!canceled) {
          setContextLoading(false);
        }
      });
    return () => {
      canceled = true;
    };
  }, [sessionId, activeTab, traceVersion]);

  const openFile = (path: string) => {
    if (!sessionId) return;
    setSelectedPath(path);
    setLoadingFile(true);
    readRepoFile(sessionId, path)
      .then((f) => {
        setFilePreview(f);
        setDraftContent(f.content);
      })
      .catch(() => {
        setFilePreview({ path, content: "读取失败", truncated: false });
        setDraftContent("读取失败");
      })
      .finally(() => setLoadingFile(false));
  };

  const saveFile = () => {
    if (!sessionId || !selectedPath) return;
    writeRepoFile(sessionId, selectedPath, draftContent)
      .then(() => {
        setFilePreview({ path: selectedPath, content: draftContent, truncated: false });
      })
      .catch(() => undefined);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex border-b border-border/50 bg-card/30">
        <button
          onClick={() => setActiveTab("files")}
          className={cn(
            "flex-1 px-3 py-2.5 text-xs font-medium transition-colors",
            activeTab === "files"
              ? "border-b-2 border-primary text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          文件树
        </button>
        <button
          onClick={() => setActiveTab("memory")}
          className={cn(
            "flex-1 px-3 py-2.5 text-xs font-medium transition-colors",
            activeTab === "memory"
              ? "border-b-2 border-primary text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          Memory
        </button>
        <button
          onClick={() => setActiveTab("context")}
          className={cn(
            "flex-1 px-3 py-2.5 text-xs font-medium transition-colors",
            activeTab === "context"
              ? "border-b-2 border-primary text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          Context
        </button>
      </div>

      <div className="flex-1 overflow-hidden">
        {activeTab === "files" ? (
          <div className="grid h-full grid-cols-[220px_1fr] overflow-hidden">
            <div className="overflow-y-auto border-r border-border/50 p-3">
              <div className="mb-2 text-xs font-semibold text-muted-foreground">文件浏览器</div>
              {!sessionId ? (
                <div className="rounded-lg border border-dashed border-border/50 bg-card/30 p-4 text-center text-xs text-muted-foreground">
                  请先选择会话
                </div>
              ) : repoTree.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border/50 bg-card/30 p-4 text-center text-xs text-muted-foreground">
                  暂无文件
                </div>
              ) : (
                repoTree.map((entry) => (
                  <button
                    key={entry.path}
                    onClick={() => {
                      if (!entry.isDir) openFile(entry.path);
                    }}
                    className="w-full rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent/50"
                  >
                    <div className="flex items-center gap-2">
                      <span className="truncate text-foreground">{entry.isDir ? `📁 ${entry.displayName}` : entry.displayName}</span>
                    </div>
                  </button>
                ))
              )}
            </div>

            <div className="overflow-hidden p-3">
              {!selectedPath ? (
                <div className="rounded-lg border border-dashed border-border/50 bg-card/30 p-4 text-center text-xs text-muted-foreground">
                  请选择一个文件预览
                </div>
              ) : loadingFile ? (
                <div className="rounded-lg border border-dashed border-border/50 bg-card/30 p-4 text-center text-xs text-muted-foreground">
                  读取文件中...
                </div>
              ) : (
                <div className="flex h-full flex-col gap-2">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="truncate">{filePreview?.path}</span>
                    <button className="rounded border border-border/50 px-2 py-1 hover:bg-accent" onClick={saveFile}>
                      保存
                    </button>
                  </div>
                  <textarea
                    className="h-full w-full resize-none rounded border border-border/50 bg-background p-3 font-mono text-xs"
                    value={draftContent}
                    onChange={(e) => setDraftContent(e.target.value)}
                  />
                </div>
              )}
            </div>
          </div>
        ) : activeTab === "memory" ? (
          <MemoryPanel sessionId={sessionId} />
        ) : activeTab === "context" ? (
          <ContextPanel
            sessionId={sessionId}
            snapshot={contextSnapshot}
            loading={contextLoading}
            errorText={contextError}
          />
        ) : (
          <ContextPanel
            sessionId={sessionId}
            snapshot={contextSnapshot}
            loading={contextLoading}
            errorText={contextError}
          />
        )}
      </div>
    </div>
  );
}
