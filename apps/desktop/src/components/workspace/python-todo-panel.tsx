import type { PythonTodoState } from "../../types/models";

interface PythonTodoPanelProps {
  todo: PythonTodoState | null;
}

function statusLabel(status: string): string {
  if (status === "completed") return "已完成";
  if (status === "in_progress") return "进行中";
  return "待处理";
}

function statusColor(status: string): string {
  if (status === "completed") return "text-emerald-300";
  if (status === "in_progress") return "text-primary";
  return "text-muted-foreground";
}

export function PythonTodoPanel({ todo }: PythonTodoPanelProps) {
  if (!todo) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-xs text-muted-foreground">
        暂无 Todo（运行 Python agent 后会显示进度）。
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col p-3">
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-xl border border-border/50 bg-card/40 p-3">
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            Total
          </div>
          <div className="mt-1 text-lg font-semibold text-foreground">
            {todo.stats.total}
          </div>
        </div>
        <div className="rounded-xl border border-border/50 bg-card/40 p-3">
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            Completed
          </div>
          <div className="mt-1 text-lg font-semibold text-foreground">
            {todo.stats.completed}
          </div>
        </div>
        <div className="rounded-xl border border-border/50 bg-card/40 p-3">
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            In Progress
          </div>
          <div className="mt-1 text-lg font-semibold text-foreground">
            {todo.stats.inProgress}
          </div>
        </div>
        <div className="rounded-xl border border-border/50 bg-card/40 p-3">
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            Pending
          </div>
          <div className="mt-1 text-lg font-semibold text-foreground">
            {todo.stats.pending}
          </div>
        </div>
      </div>

      <div className="mt-3 flex-1 overflow-y-auto">
        <div className="mb-2 text-xs font-semibold text-muted-foreground">
          Steps
        </div>
        {todo.items.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border/40 bg-background/40 p-3 text-xs text-muted-foreground">
            暂无步骤。
          </div>
        ) : (
          <div className="space-y-2">
            {todo.items.map((item) => (
              <div
                key={item.stepId}
                className="rounded-lg border border-border/40 bg-background/40 p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="truncate text-xs text-foreground">
                    {item.title}
                  </div>
                  <div className={`text-[11px] ${statusColor(item.status)}`}>
                    {statusLabel(item.status)}
                  </div>
                </div>
                {item.activeForm ? (
                  <div className="mt-2 whitespace-pre-wrap text-[11px] text-muted-foreground">
                    {item.activeForm}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}

        {todo.rendered ? (
          <details className="mt-3 rounded-xl border border-border/50 bg-card/30 p-3">
            <summary className="cursor-pointer text-xs font-semibold text-foreground">
              Rendered (for prompt)
            </summary>
            <pre className="mt-2 whitespace-pre-wrap text-[11px] text-muted-foreground">
              {todo.rendered}
            </pre>
          </details>
        ) : null}
      </div>

      <div className="mt-3 text-[11px] text-muted-foreground">
        Updated: {new Date(todo.updatedAt).toLocaleString()}
      </div>
    </div>
  );
}
