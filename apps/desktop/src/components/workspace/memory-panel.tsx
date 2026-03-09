import { useEffect, useMemo, useState } from "react";

import { cn } from "../../lib/utils";
import {
  listMemoryBlocks,
  setMemoryBlock,
  type MemoryBlock,
} from "../../api/bridge";

interface MemoryPanelProps {
  sessionId: string | null;
  refreshToken?: string;
}

function scopeLabel(scope: string): string {
  return scope === "global" ? "Global" : "Project";
}

export function MemoryPanel({ sessionId, refreshToken }: MemoryPanelProps) {
  const [blocks, setBlocks] = useState<MemoryBlock[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [draft, setDraft] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setBlocks([]);
      setActive(null);
      setDraft("");
      setErrorText(null);
      return;
    }
    setLoading(true);
    setErrorText(null);
    listMemoryBlocks(sessionId)
      .then((items) => {
        setBlocks(items);
        const first = items[0];
        if (first) {
          const key = `${first.scope}:${first.label}`;
          setActive(key);
          setDraft(first.content);
        }
      })
      .catch((e) => {
        setBlocks([]);
        setErrorText(String(e));
      })
      .finally(() => setLoading(false));
  }, [sessionId, refreshToken]);

  const activeBlock = useMemo(() => {
    if (!active) return null;
    const [scope, label] = active.split(":");
    return blocks.find((b) => b.scope === scope && b.label === label) ?? null;
  }, [active, blocks]);

  useEffect(() => {
    if (!activeBlock) return;
    setDraft(activeBlock.content);
  }, [activeBlock]);

  const save = async () => {
    if (!sessionId || !activeBlock) return;
    setSaving(true);
    setErrorText(null);
    try {
      const updated = await setMemoryBlock({
        sessionId,
        scope: activeBlock.scope === "global" ? "global" : "project",
        label: activeBlock.label,
        content: draft,
        description: activeBlock.description ?? undefined,
        readOnly: activeBlock.readOnly,
        limit: activeBlock.limit,
      });
      setBlocks((prev) =>
        prev.map((b) =>
          b.scope === updated.scope && b.label === updated.label ? updated : b,
        ),
      );
    } catch (e) {
      setErrorText(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid h-full grid-cols-[220px_1fr] overflow-hidden">
      <div className="overflow-y-auto border-r border-border/50 p-3">
        <div className="mb-2 text-xs font-semibold text-muted-foreground">
          记忆（Memory）
        </div>
        {!sessionId ? (
          <div className="rounded-lg border border-dashed border-border/50 bg-card/30 p-4 text-center text-xs text-muted-foreground">
            请先选择会话
          </div>
        ) : loading ? (
          <div className="rounded-lg border border-dashed border-border/50 bg-card/30 p-4 text-center text-xs text-muted-foreground">
            加载中...
          </div>
        ) : blocks.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border/50 bg-card/30 p-4 text-center text-xs text-muted-foreground">
            暂无记忆块
          </div>
        ) : (
          <div className="space-y-1">
            {blocks.map((b) => {
              const key = `${b.scope}:${b.label}`;
              return (
                <button
                  key={key}
                  onClick={() => setActive(key)}
                  className={cn(
                    "w-full rounded-md px-2 py-1.5 text-left text-xs transition-colors",
                    active === key ? "bg-accent" : "hover:bg-accent/50",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-foreground">{b.label}</span>
                    <span className="text-[10px] text-muted-foreground">
                      {scopeLabel(b.scope)}
                    </span>
                  </div>
                  {b.description ? (
                    <div className="truncate text-[10px] text-muted-foreground">
                      {b.description}
                    </div>
                  ) : null}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="overflow-hidden p-3">
        {!activeBlock ? (
          <div className="rounded-lg border border-dashed border-border/50 bg-card/30 p-4 text-center text-xs text-muted-foreground">
            请选择一个记忆块
          </div>
        ) : (
          <div className="flex h-full flex-col gap-2">
            <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
              <div className="min-w-0 truncate">
                {scopeLabel(activeBlock.scope)} · {activeBlock.label}
                {activeBlock.readOnly ? " (read-only)" : ""}
              </div>
              <button
                className={cn(
                  "rounded border border-border/50 px-2 py-1 transition-colors",
                  activeBlock.readOnly
                    ? "cursor-not-allowed opacity-50"
                    : "hover:bg-accent",
                )}
                disabled={activeBlock.readOnly || saving}
                onClick={() => {
                  void save();
                }}
              >
                {saving ? "保存中..." : "保存"}
              </button>
            </div>
            {errorText ? (
              <div className="rounded border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
                {errorText}
              </div>
            ) : null}
            <textarea
              className="h-full w-full resize-none rounded border border-border/50 bg-background p-3 font-mono text-xs"
              value={draft}
              disabled={activeBlock.readOnly}
              onChange={(e) => setDraft(e.target.value)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
