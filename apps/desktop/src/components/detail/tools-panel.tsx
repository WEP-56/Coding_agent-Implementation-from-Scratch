import { useState } from "react";

import { Button } from "../ui/button";
import type { ToolCallItem } from "../../types/models";

function statusClass(status: ToolCallItem["status"]): string {
  if (status === "success") return "bg-emerald-500/20 text-emerald-300";
  if (status === "failed") return "bg-red-500/20 text-red-300";
  return "bg-blue-500/20 text-blue-300";
}

interface ToolsPanelProps {
  items: ToolCallItem[];
}

export function ToolsPanel({ items }: ToolsPanelProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  if (items.length === 0) return <div className="text-xs text-muted-foreground">暂无工具调用。</div>;

  return (
    <div className="space-y-2">
      {items.map((t) => (
        <div key={t.id} className="rounded border border-border p-2">
          <div className="mb-1 flex items-center gap-2">
            <span className="text-xs font-medium">{t.name}</span>
            <span className={`rounded px-1.5 py-0.5 text-[10px] ${statusClass(t.status)}`}>{t.status}</span>
            <span className="ml-auto text-[10px] text-muted-foreground">{t.durationMs}ms</span>
            <Button
              variant="ghost"
              className="h-6 px-2 text-[10px]"
              onClick={() => setExpandedId((prev) => (prev === t.id ? null : t.id))}
            >
              {expandedId === t.id ? "收起" : "展开"}
            </Button>
          </div>
          {expandedId === t.id ? (
            <div className="grid gap-2 text-[11px]">
              <pre className="overflow-auto rounded bg-accent/50 p-2 whitespace-pre-wrap">args: {t.argsJson}</pre>
              <pre className="overflow-auto rounded bg-accent/50 p-2 whitespace-pre-wrap">result: {t.resultJson}</pre>
            </div>
          ) : (
            <div className="text-[11px] text-muted-foreground">已折叠，点击“展开”查看完整参数和结果。</div>
          )}
        </div>
      ))}
    </div>
  );
}
