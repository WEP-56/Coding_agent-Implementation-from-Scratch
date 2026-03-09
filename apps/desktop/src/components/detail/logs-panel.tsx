import { Button } from "../ui/button";
import type { LogItem, LogLevel } from "../../types/models";

interface LogsPanelProps {
  logs: LogItem[];
  filter: LogLevel | "all";
  onFilter: (f: LogLevel | "all") => void;
  keyword: string;
  onKeywordChange: (v: string) => void;
}

export function LogsPanel({ logs, filter, onFilter, keyword, onKeywordChange }: LogsPanelProps) {
  const base = filter === "all" ? logs : logs.filter((l) => l.level === filter);
  const filtered = keyword.trim().length === 0
    ? base
    : base.filter((l) => `${l.source} ${l.message}`.toLowerCase().includes(keyword.toLowerCase()));

  return (
    <div className="space-y-2">
      <div className="flex gap-1">
        {(["all", "info", "warn", "error"] as const).map((f) => (
          <Button key={f} variant={filter === f ? "default" : "outline"} className="h-7 px-2 text-xs" onClick={() => onFilter(f)}>
            {f}
          </Button>
        ))}
      </div>
      <input
        value={keyword}
        onChange={(e) => onKeywordChange(e.target.value)}
        placeholder="按关键字过滤 source/message"
        className="h-8 w-full rounded border border-input bg-background px-2 text-xs"
      />
      {filtered.length === 0 ? (
        <div className="text-xs text-muted-foreground">当前过滤条件下无日志。</div>
      ) : (
        <div className="max-h-72 space-y-2 overflow-auto rounded border border-border p-2">
          {filtered.map((l) => (
            <div key={l.id} className="rounded bg-accent/40 p-2 text-[11px]">
              <div className="mb-1 flex items-center gap-2 text-[10px] text-muted-foreground">
                <span>{l.ts}</span>
                <span>{l.level.toUpperCase()}</span>
                <span>{l.source}</span>
              </div>
              <pre className="whitespace-pre-wrap">{l.message}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
