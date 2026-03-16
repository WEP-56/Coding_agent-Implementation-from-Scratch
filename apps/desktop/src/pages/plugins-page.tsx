import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";

import { PageLayout } from "../components/layout/page-layout";
import { Button } from "../components/ui/button";
import { usePluginStore } from "../store/plugin-store";
import { useUiStore } from "../store/ui-store";

export function PluginsPage() {
  const { plugins, importLocal, toggleEnabled, removePlugin } = usePluginStore();
  const pushToast = useUiStore((s) => s.pushToast);
  const [pathInput, setPathInput] = useState("");

  const onSelectFolder = async () => {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: "选择插件文件夹",
      });

      if (selected && typeof selected === "string") {
        setPathInput(selected);
      }
    } catch (e) {
      pushToast({ kind: "error", title: "选择文件夹失败", message: String(e) });
    }
  };

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
        <h2 className="mb-3 text-sm font-medium">内置 Skills</h2>
        <p className="mb-3 text-xs text-muted-foreground">
          这些 skills 已内置在系统中，可直接在聊天时使用 @skillname 调用
        </p>
        <div className="space-y-2">
          {[
            { name: "git-workflow", description: "Git 提交、分支和 PR 最佳实践", tags: ["git", "version-control"] },
            { name: "testing", description: "测试策略、框架选择和覆盖率指南", tags: ["testing", "quality"] },
            { name: "debugging", description: "诊断步骤、常见问题和性能分析", tags: ["debugging", "performance"] },
            { name: "code-review", description: "代码审查清单、安全和性能检查", tags: ["review", "security"] },
          ].map((skill) => (
            <div key={skill.name} className="flex items-center gap-2 rounded border border-border/50 bg-background/50 p-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium">@{skill.name}</span>
                  <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-300">
                    内置
                  </span>
                </div>
                <div className="text-xs text-muted-foreground">{skill.description}</div>
                <div className="mt-1 flex gap-1">
                  {skill.tags.map((tag) => (
                    <span key={tag} className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  navigator.clipboard.writeText(`@${skill.name}`);
                  pushToast({ kind: "success", title: "已复制", message: `@${skill.name}` });
                }}
              >
                复制
              </Button>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-md border border-border bg-card p-4">
        <h2 className="mb-2 text-sm font-medium">导入本地插件</h2>
        <p className="mb-3 text-xs text-muted-foreground">
          导入自定义 skills 或插件（支持 .md 格式的 skill 文件）
        </p>
        <div className="flex gap-2">
          <input
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            placeholder="例如：E:\\plugins\\my-skill"
            className="h-9 flex-1 rounded border border-input bg-background px-3 text-sm"
          />
          <Button variant="outline" onClick={onSelectFolder}>
            📁 浏览
          </Button>
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
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-medium">{p.name}</span>
                    {p.enabled ? (
                      <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-300">
                        已启用
                      </span>
                    ) : (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        已禁用
                      </span>
                    )}
                  </div>
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

      <section className="rounded-md border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-medium">推荐 Skills 资源</h2>
        <div className="space-y-3 text-sm">
          <div className="rounded border border-border/50 bg-background/50 p-3">
            <div className="mb-1 flex items-center gap-2">
              <span className="font-medium">Awesome Claude Prompts</span>
              <a
                href="https://github.com/langgptai/awesome-claude-prompts"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-primary hover:underline"
              >
                GitHub →
              </a>
            </div>
            <p className="text-xs text-muted-foreground">
              精选的 Claude 提示词和技能集合，涵盖编码、调试、代码审查等场景
            </p>
          </div>

          <div className="rounded border border-border/50 bg-background/50 p-3">
            <div className="mb-1 flex items-center gap-2">
              <span className="font-medium">Prompt Engineering Guide</span>
              <a
                href="https://www.promptingguide.ai/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-primary hover:underline"
              >
                Website →
              </a>
            </div>
            <p className="text-xs text-muted-foreground">
              提示工程最佳实践和技巧，帮助你编写更有效的 AI 指令
            </p>
          </div>

          <div className="rounded border border-border/50 bg-background/50 p-3">
            <div className="mb-1 flex items-center gap-2">
              <span className="font-medium">ShareAI Skills</span>
              <a
                href="https://learn.shareai.run/en/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-primary hover:underline"
              >
                Learn →
              </a>
            </div>
            <p className="text-xs text-muted-foreground">
              本项目参考教程，包含 Coding Agent 构建指南和技能模板
            </p>
          </div>
        </div>
      </section>
      </div>
    </PageLayout>
  );
}
