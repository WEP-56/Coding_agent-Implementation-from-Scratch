import { useState } from "react";

import { PageLayout } from "../components/layout/page-layout";
import { Button } from "../components/ui/button";
import { usePluginStore } from "../store/plugin-store";
import { useUiStore } from "../store/ui-store";

export function PluginsPage() {
  const { plugins, importLocal, toggleEnabled, removePlugin } = usePluginStore();
  const pushToast = useUiStore((s) => s.pushToast);
  const [pathInput, setPathInput] = useState("");

  const onImport = () => {
    const p = pathInput.trim();
    if (!p) {
      pushToast({ kind: "warning", title: "请输入插件路径" });
      return;
    }
    importLocal(p);
    setPathInput("");
    pushToast({ kind: "success", title: "插件已导入", message: p });
  };

  return (
    <PageLayout>
      <div className="space-y-6 p-6">
      <div>
          <h1 className="mb-2 text-lg font-semibold">插件市场</h1>
        <p className="text-sm text-muted-foreground">当前支持本地插件导入；在线市场后续开放。</p>
      </div>

      <section className="rounded-md border border-border bg-card p-4">
        <h2 className="mb-2 text-sm font-medium">导入本地插件</h2>
        <div className="flex gap-2">
          <input
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            placeholder="例如：E:\\plugins\\my-skill"
            className="h-9 flex-1 rounded border border-input bg-background px-3 text-sm"
          />
          <Button onClick={onImport}>导入</Button>
        </div>
      </section>

      <section className="rounded-md border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-medium">已导入插件</h2>
        {plugins.length === 0 ? (
          <div className="rounded border border-dashed border-border p-3 text-xs text-muted-foreground">
            暂无插件。可先导入本地目录。
          </div>
        ) : (
          <div className="space-y-2">
            {plugins.map((p) => (
              <div key={p.id} className="flex items-center gap-2 rounded border border-border p-3">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">{p.name}</div>
                  <div className="truncate text-xs text-muted-foreground">{p.sourcePath}</div>
                </div>
                <Button variant="outline" onClick={() => toggleEnabled(p.id)}>
                  {p.enabled ? "禁用" : "启用"}
                </Button>
                <Button variant="ghost" onClick={() => removePlugin(p.id)}>
                  删除
                </Button>
              </div>
            ))}
          </div>
        )}
      </section>
      </div>
    </PageLayout>
  );
}
