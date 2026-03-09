import { Button } from "../ui/button";
import { cn } from "../../lib/utils";
import type { DiffFile, DiffViewMode } from "../../types/models";

interface DiffPanelProps {
  files: DiffFile[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  viewMode: DiffViewMode;
  onChangeView: (mode: DiffViewMode) => void;
  mode: "plan" | "build" | "auto";
  onApply: () => void;
  onReject: () => void;
  onRollback: () => void;
  onUndo: () => void;
  onRedo: () => void;
  canUndo: boolean;
  canRedo: boolean;
}

export function DiffPanel({ files, selectedId, onSelect, viewMode, onChangeView, mode, onApply, onReject, onRollback, onUndo, onRedo, canUndo, canRedo }: DiffPanelProps) {
  const selected = files.find((f) => f.id === selectedId) ?? files[0] ?? null;

  if (!selected) {
    return <div className="text-xs text-muted-foreground">暂无 diff 数据。</div>;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 rounded border border-border bg-accent/30 p-2">
        <span className="text-[11px] text-muted-foreground">当前模式：{mode}</span>
        <div className="ml-auto flex items-center gap-2">
          <div className="flex gap-1 rounded border border-border bg-background/70 p-1">
          <Button className="h-7 px-2 text-xs" variant="outline" onClick={onUndo} disabled={!canUndo}>
            Undo
          </Button>
          <Button className="h-7 px-2 text-xs" variant="outline" onClick={onRedo} disabled={!canRedo}>
            Redo
          </Button>
          </div>
          <div className="flex gap-1 rounded border border-border bg-background/70 p-1">
          <Button className="h-7 px-2 text-xs" variant="default" onClick={onApply} disabled={mode === "plan" || files.length === 0}>
            Apply
          </Button>
          <Button className="h-7 px-2 text-xs" variant="outline" onClick={onReject} disabled={files.length === 0}>
            Reject
          </Button>
          <Button className="h-7 px-2 text-xs" variant="outline" onClick={onRollback} disabled={files.length === 0}>
            Rollback
          </Button>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="text-xs text-muted-foreground">文件变更（{files.length}）</div>
        <div className="flex gap-1">
          <Button variant={viewMode === "split" ? "default" : "outline"} className="h-7 px-2 text-xs" onClick={() => onChangeView("split")}>Split</Button>
          <Button variant={viewMode === "unified" ? "default" : "outline"} className="h-7 px-2 text-xs" onClick={() => onChangeView("unified")}>Unified</Button>
        </div>
      </div>

      <div className="max-h-36 overflow-auto rounded border border-border p-1">
        {files.map((f) => (
          <button
            key={f.id}
            className={cn(
              "mb-1 w-full rounded px-2 py-1 text-left text-xs hover:bg-accent",
              selected.id === f.id && "bg-accent",
            )}
            onClick={() => onSelect(f.id)}
          >
            <div className="truncate">{f.path}</div>
            <div className="text-[10px] text-muted-foreground">+{f.additions} / -{f.deletions}</div>
          </button>
        ))}
      </div>

      <div className="rounded border border-border">
        <div className="border-b border-border px-2 py-1 text-[11px] text-muted-foreground">{selected.path}</div>
        {viewMode === "split" ? (
          <div className="grid grid-cols-2 gap-0 text-[11px]">
            <pre className="max-h-48 overflow-auto border-r border-border bg-red-500/5 p-2 text-red-200 whitespace-pre-wrap">
              {selected.oldSnippet}
            </pre>
            <pre className="max-h-48 overflow-auto bg-emerald-500/5 p-2 text-emerald-200 whitespace-pre-wrap">
              {selected.newSnippet}
            </pre>
          </div>
        ) : (
          <pre className="max-h-56 overflow-auto bg-card p-2 text-[11px] text-foreground whitespace-pre-wrap">
            {selected.unifiedSnippet}
          </pre>
        )}
      </div>
    </div>
  );
}
