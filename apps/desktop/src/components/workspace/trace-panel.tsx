import { useMemo, useState } from "react";

import type { SessionEvent } from "../../types/models";

interface TracePanelProps {
  events: SessionEvent[];
}

type TraceFilter = "all" | "session" | "model" | "tool" | "approval" | "artifact" | "rollback";

export function TracePanel({ events }: TracePanelProps) {
  const [filter, setFilter] = useState<TraceFilter>("all");
  const [correlation, setCorrelation] = useState("");

  const traces = useMemo(() => {
    return events.filter((event) => {
      const matchesType = filter === "all" ? true : (event.traceType ?? "") === filter;
      const q = correlation.trim();
      const matchesCorrelation = !q
        ? true
        : (event.correlationId ?? "").toLowerCase().includes(q.toLowerCase());
      return matchesType && matchesCorrelation;
    });
  }, [events, filter, correlation]);

  const grouped = useMemo(() => {
    const map = new Map<string, SessionEvent[]>();
    for (const event of traces) {
      const key = event.turnId ?? "(no-turn)";
      const arr = map.get(key) ?? [];
      arr.push(event);
      map.set(key, arr);
    }
    return Array.from(map.entries()).map(([turnId, events]) => {
      const sortedEvents = [...events].sort((a, b) => a.seq - b.seq);
      const itemMap = new Map<string, SessionEvent[]>();
      for (const event of sortedEvents) {
        const itemKey = event.itemId ?? "(turn-level)";
        const arr = itemMap.get(itemKey) ?? [];
        arr.push(event);
        itemMap.set(itemKey, arr);
      }
      return {
        turnId,
        events: sortedEvents,
        items: Array.from(itemMap.entries()),
      };
    });
  }, [traces]);

  return (
    <div className="flex h-full flex-col p-3">
      <div className="mb-2 flex items-center gap-2">
        <select
          className="h-8 rounded border border-input bg-background px-2 text-xs"
          value={filter}
          onChange={(e) => setFilter(e.target.value as TraceFilter)}
        >
          <option value="all">all</option>
          <option value="session">session</option>
          <option value="model">model</option>
          <option value="tool">tool</option>
          <option value="approval">approval</option>
          <option value="artifact">artifact</option>
          <option value="rollback">rollback</option>
        </select>
        <input
          className="h-8 flex-1 rounded border border-input bg-background px-2 text-xs"
          value={correlation}
          onChange={(e) => setCorrelation(e.target.value)}
          placeholder="filter correlationId..."
        />
      </div>

      <div className="flex-1 overflow-y-auto rounded border border-border/50 bg-card/30 p-2">
        {traces.length === 0 ? (
          <div className="p-3 text-xs text-muted-foreground">暂无 trace 事件</div>
        ) : (
          <div className="space-y-2">
            {grouped.map((group) => (
              <div key={group.turnId} className="rounded border border-border/50 bg-card/40 p-2">
                <div className="mb-2 text-[11px] font-semibold text-primary">
                  turn={group.turnId} · events={group.events.length}
                </div>
                <div className="space-y-2">
                  {group.items.map(([itemId, itemEvents]) => (
                    <details key={`${group.turnId}-${itemId}`} className="rounded border border-border/50 bg-background p-2" open={itemId !== "(turn-level)"}>
                      <summary className="cursor-pointer text-xs font-medium text-foreground">
                        item={itemId} · {itemEvents[0]?.itemType ?? "turn"} · events={itemEvents.length}
                      </summary>
                      <div className="mt-2 space-y-1">
                        {itemEvents.map((event, idx) => (
                          <div key={`${event.eventId}-${event.seq}-${idx}`} className="rounded border border-border/50 bg-card/20 p-2">
                            <div className="text-xs font-medium text-foreground">{event.title}</div>
                            <div className="text-[10px] text-muted-foreground">
                              status={event.status}
                              {` · seq=${event.seq}`}
                              {` · trace=${event.traceType ?? "-"}`}
                              {` · kind=${event.kind}`}
                              {` · run=${event.runId ?? "-"}`}
                              {` · corr=${event.correlationId ?? "-"}`}
                              {` · agent=${event.agentId ?? "-"}`}
                              {` · parent=${event.parentAgentId ?? "-"}`}
                              {` · ts=${event.ts}`}
                            </div>
                            {event.detail ? <div className="mt-1 whitespace-pre-wrap text-[11px] text-muted-foreground">{event.detail}</div> : null}
                          </div>
                        ))}
                      </div>
                    </details>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
