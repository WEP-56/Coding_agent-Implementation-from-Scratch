import { cn } from "../../lib/utils";
import { useUiStore } from "../../store/ui-store";

function kindClass(kind: "success" | "error" | "info" | "warning"): string {
  if (kind === "success") return "border-emerald-500/40 bg-emerald-500/10 text-emerald-200";
  if (kind === "error") return "border-red-500/40 bg-red-500/10 text-red-200";
  if (kind === "warning") return "border-yellow-500/40 bg-yellow-500/10 text-yellow-200";
  return "border-blue-500/40 bg-blue-500/10 text-blue-200";
}

export function ToastCenter() {
  const { toasts, removeToast } = useUiStore();

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[360px] flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            "pointer-events-auto rounded-md border px-3 py-2 text-sm shadow-lg backdrop-blur",
            kindClass(t.kind),
          )}
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="font-medium">{t.title}</div>
              {t.message ? <div className="mt-1 text-xs opacity-90">{t.message}</div> : null}
            </div>
            <button className="text-xs opacity-80 hover:opacity-100" onClick={() => removeToast(t.id)}>
              关闭
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
