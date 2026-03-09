import { cn } from "../../lib/utils";

interface DiffCodeBlockProps {
  text: string;
  className?: string;
}

function lineTone(line: string): string {
  if (line.startsWith("+") && !line.startsWith("+++")) {
    return "bg-emerald-500/14 text-emerald-200";
  }
  if (line.startsWith("-") && !line.startsWith("---")) {
    return "bg-rose-500/14 text-rose-200";
  }
  if (line.startsWith("@@")) {
    return "bg-sky-500/12 text-sky-200";
  }
  if (
    line.startsWith("diff ") ||
    line.startsWith("index ") ||
    line.startsWith("---") ||
    line.startsWith("+++")
  ) {
    return "bg-slate-800/60 text-slate-300";
  }
  return "text-slate-200";
}

export function DiffCodeBlock({ text, className }: DiffCodeBlockProps) {
  const normalized = text.replace(/\r\n/g, "\n");
  const lines = normalized.split("\n");

  return (
    <div
      className={cn(
        "overflow-auto rounded-xl bg-[#09111d] font-mono text-[11px] leading-5",
        className,
      )}
    >
      <div className="min-w-full">
        {lines.map((line, index) => (
          <div
            key={`${index}-${line}`}
            className={cn(
              "grid grid-cols-[44px_minmax(0,1fr)]",
              lineTone(line),
            )}
          >
            <span className="select-none border-r border-slate-800/80 px-2 py-0.5 text-right text-slate-500">
              {index + 1}
            </span>
            <code className="whitespace-pre-wrap px-3 py-0.5">
              {line || " "}
            </code>
          </div>
        ))}
      </div>
    </div>
  );
}
