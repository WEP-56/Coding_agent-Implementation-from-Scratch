import { cn } from "../../lib/utils";

interface ContextUsageRingProps {
  estimatedTokens: number;
  limitTokens: number;
  className?: string;
}

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n));
}

function formatK(n: number): string {
  if (!Number.isFinite(n)) return "0";
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(Math.trunc(n));
}

export function ContextUsageRing({
  estimatedTokens,
  limitTokens,
  className,
}: ContextUsageRingProps) {
  const safeLimit = Math.max(1, limitTokens);
  const pct = clamp(estimatedTokens / safeLimit, 0, 1);
  const deg = Math.round(pct * 360);

  const tone =
    pct >= 0.9
      ? "bg-red-500"
      : pct >= 0.7
        ? "bg-amber-500"
        : "bg-emerald-500";

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div
        className={cn(
          "relative h-9 w-9 rounded-full",
          "bg-[conic-gradient(var(--tw-gradient-stops))]",
        )}
        style={
          {
            backgroundImage: `conic-gradient(hsl(var(--primary)) ${deg}deg, hsl(var(--muted)) 0deg)`,
          } as React.CSSProperties
        }
        title={`Context tokens: ${estimatedTokens}/${limitTokens}`}
      >
        <div className="absolute inset-[3px] rounded-full bg-background" />
        <div
          className={cn(
            "absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border border-background",
            tone,
          )}
        />
      </div>

      <div className="min-w-[76px] leading-tight">
        <div className="text-[11px] text-muted-foreground">CTX</div>
        <div className="text-xs font-semibold text-foreground">
          {formatK(estimatedTokens)}/{formatK(limitTokens)}
        </div>
      </div>
    </div>
  );
}
