import { useEffect, useMemo, useState } from "react";

import {
  listRepoTree,
  listenSessionStateChanged,
  readRepoFile,
  writeRepoFile,
} from "../../api/bridge";
import { cn } from "../../lib/utils";
import type { RepoFileContent, RepoTreeEntry } from "../../types/models";

interface RightSidebarProps {
  sessionId: string | null;
  traceVersion?: string;
}

function dirname(path: string): string {
  const idx = path.lastIndexOf("/");
  return idx >= 0 ? path.slice(0, idx) : "";
}

function basename(path: string): string {
  const idx = path.lastIndexOf("/");
  return idx >= 0 ? path.slice(idx + 1) : path;
}

function depth(path: string): number {
  if (!path) return 0;
  return path.split("/").filter(Boolean).length;
}

export function RightSidebar({ sessionId }: RightSidebarProps) {
  const [repoTree, setRepoTree] = useState<RepoTreeEntry[]>([]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [filePreview, setFilePreview] = useState<RepoFileContent | null>(null);
  const [loadingFile, setLoadingFile] = useState(false);
  const [draftContent, setDraftContent] = useState("");
  const [refreshNonce, setRefreshNonce] = useState(0);

  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());
  const [childrenByDir, setChildrenByDir] = useState<Record<string, RepoTreeEntry[]>>({});

  const rootKey = "";

  useEffect(() => {
    let active = true;
    let dispose: (() => void) | null = null;
    void listenSessionStateChanged((event) => {
      if (!active) return;
      if (!sessionId || event.sessionId !== sessionId) return;
      setRefreshNonce((value) => value + 1);
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
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    let canceled = false;
    void listRepoTree(sessionId, "")
      .then((items) => {
        if (!canceled) {
          setRepoTree(items);
          setChildrenByDir((m) => ({ ...m, [rootKey]: items }));
        }
      })
      .catch(() => {
        if (!canceled) {
          setRepoTree([]);
          setChildrenByDir((m) => ({ ...m, [rootKey]: [] }));
        }
      });
    return () => {
      canceled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, refreshNonce]);

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
        setFilePreview({
          path: selectedPath,
          content: draftContent,
          truncated: false,
        });
      })
      .catch(() => undefined);
  };

  const entriesByDir = useMemo(() => {
    const map: Record<string, RepoTreeEntry[]> = {};
    for (const entry of repoTree) {
      const d = dirname(entry.path);
      map[d] ??= [];
      map[d].push(entry);
    }
    for (const key of Object.keys(map)) {
      map[key].sort((a, b) => {
        // dirs first
        if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
        return a.displayName.localeCompare(b.displayName);
      });
    }
    return map;
  }, [repoTree]);

  const loadDir = async (dirPath: string) => {
    if (!sessionId) return;
    if (childrenByDir[dirPath]) return;
    const items = await listRepoTree(sessionId, dirPath);
    setChildrenByDir((m) => ({ ...m, [dirPath]: items }));
  };

  const toggleDir = async (dirPath: string) => {
    const next = new Set(expandedDirs);
    if (next.has(dirPath)) {
      next.delete(dirPath);
      setExpandedDirs(next);
      return;
    }
    await loadDir(dirPath);
    next.add(dirPath);
    setExpandedDirs(next);
  };

  const renderDir = (dirPath: string) => {
    const items = childrenByDir[dirPath] ?? entriesByDir[dirPath] ?? [];
    const indent = depth(dirPath);

    return (
      <div key={`dir-${dirPath}`}>
        {dirPath !== rootKey ? (
          <button
            onClick={() => void toggleDir(dirPath)}
            className={cn(
              "w-full rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent/50",
            )}
            style={{ paddingLeft: `${8 + indent * 12}px` }}
          >
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">
                {expandedDirs.has(dirPath) ? "▾" : "▸"}
              </span>
              <span className="truncate text-foreground">
                📁 {basename(dirPath)}
              </span>
            </div>
          </button>
        ) : null}

        {(dirPath === rootKey || expandedDirs.has(dirPath)) && (
          <div>
            {items.map((entry) => {
              const itemIndent = depth(entry.path);
              if (entry.isDir) {
                return (
                  <div key={entry.path}>
                    <button
                      onClick={() => void toggleDir(entry.path)}
                      className="w-full rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent/50"
                      style={{ paddingLeft: `${8 + itemIndent * 12}px` }}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">
                          {expandedDirs.has(entry.path) ? "▾" : "▸"}
                        </span>
                        <span className="truncate text-foreground">
                          📁 {basename(entry.path)}
                        </span>
                      </div>
                    </button>
                    {expandedDirs.has(entry.path) && renderDir(entry.path)}
                  </div>
                );
              }
              return (
                <button
                  key={entry.path}
                  onClick={() => openFile(entry.path)}
                  className={cn(
                    "w-full rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent/50",
                    selectedPath === entry.path ? "bg-accent/40" : "",
                  )}
                  style={{ paddingLeft: `${8 + itemIndent * 12}px` }}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">•</span>
                    <span className="truncate text-foreground">{basename(entry.path)}</span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border/50 bg-card/30 px-3 py-2">
        <div className="text-xs font-semibold text-foreground">文件树</div>
        <div className="text-[11px] text-muted-foreground">
          {sessionId ? "" : "请先选择会话"}
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        <div className="grid h-full grid-cols-[260px_1fr] overflow-hidden">
          <div className="overflow-y-auto border-r border-border/50 p-3">
            {sessionId && (childrenByDir[rootKey]?.length ?? 0) === 0 ? (
              <div className="rounded-lg border border-dashed border-border/50 bg-card/30 p-4 text-center text-xs text-muted-foreground">
                暂无文件
              </div>
            ) : (
              renderDir(rootKey)
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
                  <button
                    className="rounded border border-border/50 px-2 py-1 hover:bg-accent"
                    onClick={saveFile}
                  >
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
      </div>
    </div>
  );
}
