import { useMemo, useState } from "react";

import { PageLayout } from "../components/layout/page-layout";
import { Button } from "../components/ui/button";
import { useAppStore } from "../store/app-store";
import { addRepo as addRepoRemote, removeRepo as removeRepoRemote, toggleRepoPin as toggleRepoPinRemote } from "../api/bridge";

export function RepositoriesPage() {
  const { repos, currentRepoId, setCurrentRepo, addRepo, removeRepo, toggleRepoPin } = useAppStore();
  const [pathInput, setPathInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  const sortedRepos = useMemo(() => {
    return [...repos].sort((a, b) => Number(b.pinned) - Number(a.pinned));
  }, [repos]);

  const onImportLocal = () => {
    const p = pathInput.trim();
    if (!p) {
      setError("请输入本地仓库路径");
      return;
    }
    addRepoRemote(p)
      .then((repo) => {
        addRepo(repo);
        setPathInput("");
        setError(null);
      })
      .catch((e) => {
        setError(`导入失败：${String(e)}`);
      });
  };

  return (
    <PageLayout>
      <div className="p-6">
        <h1 className="mb-2 text-lg font-semibold">仓库管理</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        本地仓库导入与最近仓库管理已可用；GitHub/OAuth 正在接入中。
      </p>

      <div className="mb-6 rounded-md border border-border bg-card p-4">
        <h2 className="mb-2 text-sm font-medium">导入本地仓库</h2>
        <div className="flex gap-2">
          <input
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            placeholder="例如：E:\\projects\\my-repo"
            className="h-9 flex-1 rounded-md border border-input bg-background px-3 text-sm"
          />
          <Button onClick={onImportLocal}>导入</Button>
        </div>
        {error ? <p className="mt-2 text-xs text-red-500">{error}</p> : null}
      </div>

      <div className="mb-6 rounded-md border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-medium">最近仓库</h2>
        {sortedRepos.length === 0 ? (
          <div className="rounded border border-dashed border-border p-3 text-xs text-muted-foreground">
            暂无仓库，请先导入本地目录。
          </div>
        ) : (
          <div className="space-y-2">
            {sortedRepos.map((repo) => (
              <div key={repo.id} className="flex items-center gap-2 rounded border border-border p-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-medium">{repo.name}</span>
                    {repo.pinned ? <span className="rounded bg-accent px-1.5 py-0.5 text-[10px]">置顶</span> : null}
                    {currentRepoId === repo.id ? (
                      <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] text-primary">当前</span>
                    ) : null}
                  </div>
                  <p className="truncate text-xs text-muted-foreground">{repo.path}</p>
                </div>
                <Button variant="outline" onClick={() => setCurrentRepo(repo.id)}>
                  切换
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    toggleRepoPinRemote(repo.id)
                      .then(() => toggleRepoPin(repo.id))
                      .catch((e) => setError(`置顶操作失败：${String(e)}`));
                  }}
                >
                  {repo.pinned ? "取消置顶" : "置顶"}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    removeRepoRemote(repo.id)
                      .then(() => removeRepo(repo.id))
                      .catch((e) => setError(`删除失败：${String(e)}`));
                  }}
                >
                  删除
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-md border border-border bg-card p-4">
        <h2 className="mb-2 text-sm font-medium">GitHub / OAuth</h2>
        <p className="mb-3 text-xs text-muted-foreground">
          Post-MVP：支持 GitHub HTTPS（默认浅克隆 depth=1）与私有仓库 OAuth。
        </p>
        <div className="flex gap-2">
          <Button variant="outline" disabled>
            从 GitHub URL 导入（即将开放）
          </Button>
          <Button variant="outline" disabled>
            连接 GitHub OAuth（即将开放）
          </Button>
        </div>
      </div>
      </div>
    </PageLayout>
  );
}
