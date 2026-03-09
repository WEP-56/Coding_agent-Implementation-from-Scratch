import { useEffect, useState } from "react";

import {
  approveRequest,
  listPendingApprovals,
  listSessionPermissions,
  rejectRequest,
  type ApprovalRequest,
} from "../../api/bridge";
import { cn } from "../../lib/utils";

interface ApprovalPanelProps {
  sessionId: string | null;
}

export function ApprovalPanel({ sessionId }: ApprovalPanelProps) {
  const [items, setItems] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [sessionPerms, setSessionPerms] = useState<Array<{ toolName: string; action: string; path?: string }>>([]);

  const reload = () => {
    if (!sessionId) {
      setItems([]);
      return;
    }
    setLoading(true);
    setErrorText(null);
    listPendingApprovals(sessionId)
      .then(setItems)
      .catch((e) => setErrorText(String(e)))
      .finally(() => setLoading(false));

    listSessionPermissions(sessionId)
      .then((items) =>
        setSessionPerms(
          items.map((i) => ({ toolName: i.toolName, action: i.action, path: i.path })),
        ),
      )
      .catch(() => undefined);
  };

  useEffect(() => {
    reload();
    // Polling keeps panel fresh while model runs.
    const timer = window.setInterval(reload, 2500);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const onApprove = async (id: string) => {
    if (!sessionId) return;
    await approveRequest(sessionId, id);
    reload();
  };

  const onApproveForSession = async (id: string) => {
    if (!sessionId) return;
    await approveRequest(sessionId, id, undefined, true);
    reload();
  };

  const onReject = async (id: string) => {
    if (!sessionId) return;
    await rejectRequest(sessionId, id);
    reload();
  };

  return (
    <div className="h-full overflow-y-auto p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-xs font-semibold text-muted-foreground">审批队列</div>
        <button className="rounded border border-border/50 px-2 py-1 text-[10px] hover:bg-accent" onClick={reload}>
          刷新
        </button>
      </div>

      {loading && items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border/50 bg-card/30 p-4 text-center text-xs text-muted-foreground">
          加载中...
        </div>
      ) : null}

      {errorText ? (
        <div className="mb-2 rounded border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
          {errorText}
        </div>
      ) : null}

      {items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border/50 bg-card/30 p-4 text-center text-xs text-muted-foreground">
          暂无审批请求
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <div key={item.id} className="rounded-lg border border-border/50 bg-card/30 p-3">
              <div className="mb-1 flex items-center justify-between gap-2">
                <div className="truncate text-xs font-medium text-foreground">{item.toolName}</div>
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[10px] font-medium",
                    item.status === "pending" && "bg-amber-500/10 text-amber-400",
                    item.status === "approved" && "bg-emerald-500/10 text-emerald-400",
                    item.status === "rejected" && "bg-red-500/10 text-red-400",
                    item.status === "failed" && "bg-red-500/10 text-red-400",
                  )}
                >
                  {item.status}
                </span>
              </div>

              <div className="mb-1 text-[10px] text-muted-foreground">
                action: {item.action || "-"} · path: {item.path || "-"}
              </div>
              {sessionPerms.some(
                (p) =>
                  p.toolName === item.toolName &&
                  p.action === item.action &&
                  (p.path ?? "") === (item.path ?? ""),
              ) ? (
                <div className="mb-1 text-[10px] text-emerald-400">本会话已允许（allow_session）</div>
              ) : null}

              <pre className="mb-2 overflow-x-auto rounded bg-muted/50 p-2 text-[10px]">{item.argsJson}</pre>

              {item.status === "pending" ? (
                <div className="flex gap-2">
                  <button
                    className="flex-1 rounded bg-primary px-2 py-1.5 text-xs text-primary-foreground hover:bg-primary/90"
                    onClick={() => {
                      void onApprove(item.id);
                    }}
                  >
                    批准
                  </button>
                  <button
                    className="flex-1 rounded border border-primary/40 px-2 py-1.5 text-xs text-primary hover:bg-primary/10"
                    onClick={() => {
                      void onApproveForSession(item.id);
                    }}
                  >
                    本会话始终允许
                  </button>
                  <button
                    className="flex-1 rounded border border-border/50 px-2 py-1.5 text-xs hover:bg-accent"
                    onClick={() => {
                      void onReject(item.id);
                    }}
                  >
                    拒绝
                  </button>
                </div>
              ) : (
                <div className="text-[10px] text-muted-foreground">{item.resultJson ?? item.decisionNote ?? "-"}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
