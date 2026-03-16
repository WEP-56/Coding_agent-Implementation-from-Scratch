import { PageLayout } from "../components/layout/page-layout";
import { Button } from "../components/ui/button";
import { useSettingsStore } from "../store/settings-store";
import { useUiStore } from "../store/ui-store";

export function SettingsPage() {
  const { settings, update, updateModel } = useSettingsStore();
  const pushToast = useUiStore((s) => s.pushToast);

  return (
    <PageLayout>
      <div className="space-y-6 p-6">
        <div>
          <h1 className="mb-2 text-lg font-semibold">设置</h1>
        <p className="text-sm text-muted-foreground">基础设置 / 模型配置 / 并行 Agent 配置</p>
      </div>

      <section className="rounded-md border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-medium">基础设置</h2>
        <div className="grid gap-3 text-sm">
          <label className="flex items-center justify-between rounded border border-border px-3 py-2">
            <span>关键事件通知</span>
            <input
              type="checkbox"
              checked={settings.notificationsEnabled}
              onChange={(e) => update({ notificationsEnabled: e.target.checked })}
            />
          </label>

          <label className="flex items-center justify-between rounded border border-border px-3 py-2">
            <span>默认会话模式</span>
            <select
              className="h-8 rounded border border-input bg-background px-2 text-xs"
              value={settings.defaultSessionMode}
              onChange={(e) => update({ defaultSessionMode: e.target.value as "plan" | "build" | "auto" })}
            >
              <option value="plan">plan</option>
              <option value="build">build</option>
              <option value="auto">auto</option>
            </select>
          </label>
        </div>
      </section>

      <section className="rounded-md border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-medium">并行 Agent 配置</h2>
        <div className="grid gap-3 text-sm">
          <label className="flex items-center justify-between rounded border border-border px-3 py-2">
            <span>启用并行 Agent</span>
            <input
              type="checkbox"
              checked={settings.parallelAgents?.enabled ?? true}
              onChange={(e) => update({
                parallelAgents: {
                  ...settings.parallelAgents,
                  enabled: e.target.checked
                }
              })}
            />
          </label>

          <label className="flex flex-col gap-2 rounded border border-border px-3 py-2">
            <div className="flex items-center justify-between">
              <span>最大并行数</span>
              <span className="text-xs text-muted-foreground">{settings.parallelAgents?.maxParallelAgents ?? 4}</span>
            </div>
            <input
              type="range"
              min="1"
              max="8"
              value={settings.parallelAgents?.maxParallelAgents ?? 4}
              onChange={(e) => update({
                parallelAgents: {
                  ...settings.parallelAgents,
                  maxParallelAgents: Number(e.target.value)
                }
              })}
              className="w-full"
            />
            <div className="text-xs text-muted-foreground">
              建议：小项目 2-4，大项目 4-8
            </div>
          </label>

          <label className="flex items-center justify-between rounded border border-border px-3 py-2">
            <span>自动任务分解</span>
            <input
              type="checkbox"
              checked={settings.parallelAgents?.autoDecomposition ?? true}
              onChange={(e) => update({
                parallelAgents: {
                  ...settings.parallelAgents,
                  autoDecomposition: e.target.checked
                }
              })}
            />
          </label>

          <label className="flex items-center justify-between rounded border border-border px-3 py-2">
            <span>结果自动综合</span>
            <input
              type="checkbox"
              checked={settings.parallelAgents?.resultSynthesis ?? true}
              onChange={(e) => update({
                parallelAgents: {
                  ...settings.parallelAgents,
                  resultSynthesis: e.target.checked
                }
              })}
            />
          </label>
        </div>
      </section>

      <section className="rounded-md border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-medium">模型配置</h2>
        <div className="grid gap-2 text-xs">
          <label className="flex items-center justify-between rounded border border-border px-2 py-1.5">
            <span>Style</span>
            <select
              className="h-7 rounded border border-input bg-background px-2 text-xs"
              value={settings.outputStyle ?? "default"}
              onChange={(e) =>
                update({
                  outputStyle: e.target.value as "default" | "kawaii-schoolgirl",
                })
              }
            >
              <option value="default">default</option>
              <option value="kawaii-schoolgirl">kawaii-schoolgirl</option>
            </select>
          </label>
          <label className="flex items-center justify-between rounded border border-border px-2 py-1.5">
            <span>Provider</span>
            <select
              className="h-7 rounded border border-input bg-background px-2 text-xs"
              value={settings.model.provider}
              onChange={(e) =>
                updateModel({ provider: e.target.value as "mock" | "openai-compatible" })
              }
            >
              <option value="mock">mock</option>
              <option value="openai-compatible">openai-compatible</option>
            </select>
          </label>

          <label className="rounded border border-border px-2 py-1.5">
            <div className="mb-1">Model</div>
            <input
              className="h-8 w-full rounded border border-input bg-background px-2"
              value={settings.model.model}
              onChange={(e) => updateModel({ model: e.target.value })}
            />
          </label>

          <label className="rounded border border-border px-2 py-1.5">
            <div className="mb-1">Base URL</div>
            <input
              className="h-8 w-full rounded border border-input bg-background px-2"
              value={settings.model.baseUrl}
              onChange={(e) => updateModel({ baseUrl: e.target.value })}
            />
          </label>

          <label className="rounded border border-border px-2 py-1.5">
            <div className="mb-1">API Key</div>
            <input
              type="password"
              className="h-8 w-full rounded border border-input bg-background px-2"
              value={settings.model.apiKey}
              onChange={(e) => updateModel({ apiKey: e.target.value })}
            />
          </label>

          <label className="rounded border border-border px-2 py-1.5">
            <div className="mb-1">Timeout (sec)</div>
            <input
              type="number"
              min={10}
              max={900}
              className="h-8 w-full rounded border border-input bg-background px-2"
              value={settings.model.timeoutSec ?? 180}
              onChange={(e) =>
                updateModel({
                  timeoutSec: Math.max(
                    10,
                    Math.min(900, Number(e.target.value) || 180),
                  ),
                })
              }
            />
          </label>

          <label className="rounded border border-border px-2 py-1.5">
            <div className="mb-1">Context token limit (auto-compact)</div>
            <input
              type="number"
              min={2000}
              max={200000}
              className="h-8 w-full rounded border border-input bg-background px-2"
              value={settings.model.contextTokenLimit ?? ""}
              onChange={(e) => {
                const raw = e.target.value;
                if (!raw.trim()) {
                  updateModel({ contextTokenLimit: undefined });
                  return;
                }
                const parsed = Number(raw);
                if (!Number.isFinite(parsed)) return;
                updateModel({
                  contextTokenLimit: Math.max(
                    2000,
                    Math.min(200000, Math.trunc(parsed)),
                  ),
                });
              }}
              placeholder="留空则使用默认值（更保守）"
            />
            <div className="mt-1 text-[10px] text-muted-foreground">
              建议：小模型 8k~16k，大模型 32k~64k。达到阈值会触发上下文压缩并在 Trace 里记录。
            </div>
          </label>

          <div className="mt-1 flex justify-end">
            <Button
              variant="outline"
              onClick={() => {
                if (settings.model.provider === "openai-compatible") {
                  if (!settings.model.baseUrl.trim()) {
                    pushToast({ kind: "error", title: "验证失败", message: "请填写 Base URL。" });
                    return;
                  }
                  if (!settings.model.apiKey.trim()) {
                    pushToast({ kind: "error", title: "验证失败", message: "请填写 API Key。" });
                    return;
                  }
                  if (!settings.model.model.trim()) {
                    pushToast({ kind: "error", title: "验证失败", message: "请填写 Model。" });
                    return;
                  }
                }
                pushToast({ kind: "success", title: "设置已保存", message: "配置已持久化并可用于对话。" });
              }}
            >
              保存并验证
            </Button>
          </div>
        </div>
      </section>
      </div>
    </PageLayout>
  );
}
