import { useState } from "react";

import { PageLayout } from "../components/layout/page-layout";
import { Button } from "../components/ui/button";
import { useAppStore } from "../store/app-store";
import { useSecurityStore } from "../store/security-store";
import { TOOL_POLICY_KEYS, type ToolPolicyKey } from "../types/models";
import { useSettingsStore } from "../store/settings-store";
import { useUiStore } from "../store/ui-store";

export function SettingsPage() {
  const { repos, currentRepoId } = useAppStore();
  const { settings, update, updateModel, getRuleForRepo, setRuleForRepo, resetRuleForRepo } = useSettingsStore();
  const { getPolicy, setPolicy, getToolPolicy, setToolPolicy } = useSecurityStore();
  const pushToast = useUiStore((s) => s.pushToast);
  const [ruleDraftByRepo, setRuleDraftByRepo] = useState<Record<string, string>>({});

  const currentRuleDraft = currentRepoId
    ? (ruleDraftByRepo[currentRepoId] ?? getRuleForRepo(currentRepoId).content)
    : "";

  return (
    <PageLayout>
      <div className="space-y-6 p-6">
        <div>
          <h1 className="mb-2 text-lg font-semibold">设置</h1>
        <p className="text-sm text-muted-foreground">MVP：基础设置 / 安全权限 / 模型配置。</p>
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
        <h2 className="mb-3 text-sm font-medium">安全权限（按仓库）</h2>
        {repos.length === 0 ? (
          <div className="text-xs text-muted-foreground">暂无仓库，导入后可编辑敏感操作策略。</div>
        ) : (
          <div className="space-y-3">
            {repos.map((repo) => (
              <div key={repo.id} className="rounded border border-border p-3">
                <div className="mb-2 text-sm font-medium">{repo.name}</div>
                <div className="grid gap-2 text-xs">
                  <label className="flex items-center justify-between rounded border border-border px-2 py-1.5">
                    <span>run_shell</span>
                    <select
                      className="h-7 rounded border border-input bg-background px-2 text-xs"
                      value={getPolicy(repo.id, "run_shell")}
                      onChange={(e) =>
                        setPolicy(repo.id, "run_shell", e.target.value as "ask" | "allow" | "deny")
                      }
                    >
                      <option value="ask">ask</option>
                      <option value="allow">allow</option>
                      <option value="deny">deny</option>
                    </select>
                  </label>
                  <label className="flex items-center justify-between rounded border border-border px-2 py-1.5">
                    <span>install_dependency</span>
                    <select
                      className="h-7 rounded border border-input bg-background px-2 text-xs"
                      value={getPolicy(repo.id, "install_dependency")}
                      onChange={(e) =>
                        setPolicy(repo.id, "install_dependency", e.target.value as "ask" | "allow" | "deny")
                      }
                    >
                      <option value="ask">ask</option>
                      <option value="allow">allow</option>
                      <option value="deny">deny</option>
                    </select>
                  </label>

                  <div className="rounded border border-border bg-background p-2">
                    <div className="mb-2 text-[11px] font-medium text-foreground">工具权限（Tool Policies）</div>
                    <div className="grid gap-2">
                      {TOOL_POLICY_KEYS.map((tool) => (
                        <label
                          key={tool}
                          className="flex items-center justify-between rounded border border-border px-2 py-1.5"
                        >
                          <span className="font-mono text-[11px] text-foreground">{tool}</span>
                          <select
                            className="h-7 rounded border border-input bg-background px-2 text-xs"
                            value={getToolPolicy(repo.id, tool as ToolPolicyKey)}
                            onChange={(e) =>
                              setToolPolicy(repo.id, tool as ToolPolicyKey, e.target.value as "ask" | "allow" | "deny")
                            }
                          >
                            <option value="ask">ask</option>
                            <option value="allow">allow</option>
                            <option value="deny">deny</option>
                          </select>
                        </label>
                      ))}
                    </div>
                    <div className="mt-2 text-[10px] text-muted-foreground">
                      说明：这里的策略会直接影响 agent 工具是否执行（allow）、进入审批队列（ask）、或直接拒绝（deny）。
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-md border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-medium">项目规则 Rules</h2>
        {!currentRepoId ? (
          <div className="text-xs text-muted-foreground">请先选择仓库后编辑规则。</div>
        ) : (
          <div className="grid gap-2 text-xs">
            <div className="text-muted-foreground">作用域：仅当前仓库生效（保存后立即生效）。</div>
            <textarea
              className="h-28 w-full resize-y rounded border border-input bg-background px-2 py-2"
              value={currentRuleDraft}
              onChange={(e) =>
                setRuleDraftByRepo((prev) => ({
                  ...prev,
                  [currentRepoId]: e.target.value,
                }))
              }
              placeholder="例如：先分析再执行；涉及依赖升级必须询问；测试失败禁止 Apply。"
            />
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">最后更新时间：{getRuleForRepo(currentRepoId).updatedAt || "未保存"}</span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="h-7 px-2 text-xs"
                  onClick={() => {
                    resetRuleForRepo(currentRepoId);
                    setRuleDraftByRepo((prev) => ({ ...prev, [currentRepoId]: "" }));
                  }}
                >
                  重置
                </Button>
                <Button
                  className="h-7 px-2 text-xs"
                  onClick={() => {
                    setRuleForRepo(currentRepoId, currentRuleDraft.trim());
                    pushToast({ kind: "success", title: "Rules 已保存", message: "当前仓库规则已生效。" });
                  }}
                >
                  保存
                </Button>
              </div>
            </div>
            <div className="rounded border border-border bg-background p-2 text-muted-foreground">
              说明：Rules 负责行为约束；Ask/Allow/Deny 负责敏感动作授权。两者叠加后，最终决定是否执行工具动作。
            </div>
          </div>
        )}
      </section>

      <section className="rounded-md border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-medium">模型配置</h2>
        <div className="grid gap-2 text-xs">
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
