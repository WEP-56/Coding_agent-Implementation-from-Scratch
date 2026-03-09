import type { SessionContextDebugSnapshot } from "../../types/models";

interface ContextPanelProps {
  sessionId: string | null;
  snapshot: SessionContextDebugSnapshot | null;
  loading: boolean;
  errorText?: string | null;
}

function formatTimestamp(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function roleLabel(role: string): string {
  if (role === "user") return "User";
  if (role === "assistant") return "Assistant";
  return "System";
}

export function ContextPanel({
  sessionId,
  snapshot,
  loading,
  errorText,
}: ContextPanelProps) {
  if (!sessionId) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-xs text-muted-foreground">
        Select a session to inspect context.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-xs text-muted-foreground">
        Loading session context...
      </div>
    );
  }

  if (errorText) {
    return (
      <div className="p-4">
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
          {errorText}
        </div>
      </div>
    );
  }

  if (!snapshot) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-xs text-muted-foreground">
        No context snapshot available.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col p-3">
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-xl border border-border/50 bg-card/40 p-3">
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            Estimated Tokens
          </div>
          <div className="mt-1 text-lg font-semibold text-foreground">
            {snapshot.estimatedTokens}
          </div>
        </div>
        <div className="rounded-xl border border-border/50 bg-card/40 p-3">
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            Visible Turns
          </div>
          <div className="mt-1 text-lg font-semibold text-foreground">
            {snapshot.budget.visibleTurns}/{snapshot.budget.maxVisibleHistory}
          </div>
        </div>
        <div className="rounded-xl border border-border/50 bg-card/40 p-3">
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            Memory Blocks
          </div>
          <div className="mt-1 text-lg font-semibold text-foreground">
            {snapshot.memoryBlocks.length}
          </div>
        </div>
        <div className="rounded-xl border border-border/50 bg-card/40 p-3">
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            Compaction
          </div>
          <div className="mt-1 text-sm font-semibold text-foreground">
            {snapshot.compaction.applied
              ? "Applied"
              : snapshot.compaction.wouldApply
                ? "Will compact on run"
                : "Stable"}
          </div>
          <div className="mt-1 text-[11px] text-muted-foreground">
            Dropped {snapshot.compaction.droppedTurns} turns
          </div>
        </div>
      </div>

      <div className="mt-3 flex-1 space-y-2 overflow-y-auto">
        <details
          className="rounded-xl border border-border/50 bg-card/30 p-3"
          open
        >
          <summary className="cursor-pointer text-xs font-semibold text-foreground">
            Budget
          </summary>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              History chars: {snapshot.budget.historyChars}
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              Summary chars: {snapshot.budget.summaryChars}
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              Memory chars: {snapshot.budget.memoryChars}
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              History turns: {snapshot.historyCount}
            </div>
          </div>
        </details>

        <details
          className="rounded-xl border border-border/50 bg-card/30 p-3"
          open
        >
          <summary className="cursor-pointer text-xs font-semibold text-foreground">
            Token Breakdown
          </summary>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              History tokens: {snapshot.tokenBreakdown.historyTokens}
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              Summary tokens: {snapshot.tokenBreakdown.summaryTokens}
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              Memory tokens: {snapshot.tokenBreakdown.memoryTokens}
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              Pruned output tokens:{" "}
              {snapshot.tokenBreakdown.prunedToolOutputTokens}
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 p-2 col-span-2">
              Total tokens: {snapshot.tokenBreakdown.totalTokens}
            </div>
          </div>
        </details>

        <details
          className="rounded-xl border border-border/50 bg-card/30 p-3"
          open
        >
          <summary className="cursor-pointer text-xs font-semibold text-foreground">
            Tool Output Prune
          </summary>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              Applied: {snapshot.prune.applied ? "Yes" : "No"}
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              Pruned turns: {snapshot.prune.prunedTurns}
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              Chars removed: {snapshot.prune.charsRemoved}
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              Kept chars: {snapshot.prune.keptChars}
            </div>
          </div>
        </details>

        <details
          className="rounded-xl border border-border/50 bg-card/30 p-3"
          open
        >
          <summary className="cursor-pointer text-xs font-semibold text-foreground">
            Normalization
          </summary>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              Kept turns: {snapshot.normalization.keptTurns}
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              Dropped empty: {snapshot.normalization.droppedEmptyTurns}
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              Dropped invalid roles:{" "}
              {snapshot.normalization.droppedInvalidRoles}
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 p-2">
              Total turns: {snapshot.normalization.totalTurns}
            </div>
          </div>
        </details>

        <details
          className="rounded-xl border border-border/50 bg-card/30 p-3"
          open
        >
          <summary className="cursor-pointer text-xs font-semibold text-foreground">
            Visible History
          </summary>
          <div className="mt-3 space-y-2">
            {snapshot.visibleHistory.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border/40 bg-background/40 p-3 text-xs text-muted-foreground">
                No visible turns.
              </div>
            ) : (
              snapshot.visibleHistory.map((turn, index) => (
                <div
                  key={`${turn.role}-${index}`}
                  className="rounded-lg border border-border/40 bg-background/40 p-3"
                >
                  <div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                    <span>{roleLabel(turn.role)}</span>
                    <span>{turn.chars} chars</span>
                  </div>
                  <div className="mt-2 whitespace-pre-wrap text-xs text-foreground">
                    {turn.content}
                  </div>
                </div>
              ))
            )}
          </div>
        </details>

        <details
          className="rounded-xl border border-border/50 bg-card/30 p-3"
          open
        >
          <summary className="cursor-pointer text-xs font-semibold text-foreground">
            Summary
          </summary>
          <pre className="mt-3 whitespace-pre-wrap rounded-lg bg-[#09111d] p-3 text-[11px] leading-5 text-slate-200">
            <code>{snapshot.summary || "No summary yet."}</code>
          </pre>
        </details>

        <details
          className="rounded-xl border border-border/50 bg-card/30 p-3"
          open
        >
          <summary className="cursor-pointer text-xs font-semibold text-foreground">
            Memory Blocks
          </summary>
          <div className="mt-3 space-y-2">
            {snapshot.memoryBlocks.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border/40 bg-background/40 p-3 text-xs text-muted-foreground">
                No memory blocks.
              </div>
            ) : (
              snapshot.memoryBlocks.map((block) => (
                <div
                  key={`${block.scope}:${block.label}`}
                  className="rounded-lg border border-border/40 bg-background/40 p-3"
                >
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <div className="font-medium text-foreground">
                      {block.scope}:{block.label}
                    </div>
                    <div className="text-muted-foreground">
                      {block.chars}/{block.limit}
                    </div>
                  </div>
                  {block.description ? (
                    <div className="mt-1 text-[11px] text-muted-foreground">
                      {block.description}
                    </div>
                  ) : null}
                  <div className="mt-1 text-[11px] text-muted-foreground">
                    Updated {formatTimestamp(block.updatedAt)}
                  </div>
                  <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-[#09111d] p-3 text-[11px] leading-5 text-slate-200">
                    <code>{block.contentPreview || "(empty)"}</code>
                  </pre>
                </div>
              ))
            )}
          </div>
        </details>

        <details
          className="rounded-xl border border-border/50 bg-card/30 p-3"
          open
        >
          <summary className="cursor-pointer text-xs font-semibold text-foreground">
            Recent Failures
          </summary>
          <div className="mt-3 space-y-2">
            {snapshot.recentFailures.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border/40 bg-background/40 p-3 text-xs text-muted-foreground">
                No recent failure turns.
              </div>
            ) : (
              snapshot.recentFailures.map((turn, index) => (
                <div
                  key={`failure-${index}`}
                  className="rounded-lg border border-destructive/20 bg-destructive/5 p-3"
                >
                  <div className="text-[11px] text-muted-foreground">
                    {turn.chars} chars
                  </div>
                  <div className="mt-2 whitespace-pre-wrap text-xs text-foreground">
                    {turn.content}
                  </div>
                </div>
              ))
            )}
          </div>
        </details>
      </div>
    </div>
  );
}
