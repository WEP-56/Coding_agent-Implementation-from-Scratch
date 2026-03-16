import { useEffect, useRef, useState } from "react";

import { runTerminalCommand } from "../../api/bridge";

interface TerminalPanelProps {
  sessionId: string | null;
  repoPath: string | null;
  onCommandLifecycle?: (
    phase: "started" | "finished",
    sessionId: string,
  ) => void;
}

interface TerminalEntry {
  id: string;
  kind: "meta" | "command" | "stdout" | "stderr";
  text: string;
}

function makeEntry(kind: TerminalEntry["kind"], text: string): TerminalEntry {
  return {
    id: `${kind}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    kind,
    text,
  };
}

function initialEntries(repoPath: string | null): TerminalEntry[] {
  if (!repoPath) {
    return [
      makeEntry("meta", "Select a session to attach the workspace terminal."),
    ];
  }
  return [makeEntry("meta", `Workspace terminal attached to ${repoPath}`)];
}

export function TerminalPanel({
  sessionId,
  repoPath,
  onCommandLifecycle,
}: TerminalPanelProps) {
  const [cwd, setCwd] = useState(repoPath ?? "");
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [entries, setEntries] = useState<TerminalEntry[]>(
    initialEntries(repoPath),
  );
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setCwd(repoPath ?? "");
    setEntries(initialEntries(repoPath));
    setInput("");
    setHistory([]);
    setHistoryIndex(-1);
  }, [repoPath, sessionId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries, running]);

  const submit = async () => {
    const command = input.trim();
    if (!command || !sessionId || !repoPath || running) return;

    if (command === "clear" || command === "cls") {
      setEntries(initialEntries(repoPath));
      setInput("");
      return;
    }

    setEntries((current) => [
      ...current,
      makeEntry("command", `$ ${command}`),
    ]);
    setHistory((current) =>
      [command, ...current.filter((item) => item !== command)].slice(0, 50),
    );
    setHistoryIndex(-1);
    setInput("");
    setRunning(true);

    try {
      const pending = runTerminalCommand(sessionId, command, cwd || repoPath);
      onCommandLifecycle?.("started", sessionId);
      const result = await pending;
      setCwd(result.cwd);
      setEntries((current) => {
        const next = [...current];
        if (result.stdout.trim()) {
          next.push(makeEntry("stdout", result.stdout.trimEnd()));
        }
        if (result.stderr.trim()) {
          next.push(makeEntry("stderr", result.stderr.trimEnd()));
        }
        if (!result.stdout.trim() && !result.stderr.trim()) {
          next.push(
            makeEntry(
              "meta",
              result.success
                ? `✓ Exit code ${result.exitCode}`
                : `✗ Exit code ${result.exitCode}`,
            ),
          );
        }
        if (result.cwd !== cwd) {
          next.push(makeEntry("meta", `→ ${result.cwd}`));
        }
        return next;
      });
    } catch (error) {
      setEntries((current) => [...current, makeEntry("stderr", String(error))]);
    } finally {
      onCommandLifecycle?.("finished", sessionId);
      setRunning(false);
    }
  };

  return (
    <div className="flex h-full flex-col bg-[#09111d] text-slate-100">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-[0.16em] text-slate-400">
            Workspace Terminal
          </div>
          <div className="truncate text-xs text-slate-300">
            {cwd || repoPath || "No workspace path"}
          </div>
        </div>
        <button
          className="rounded-md border border-slate-700 px-2.5 py-1 text-[11px] text-slate-300 transition-colors hover:bg-slate-800"
          onClick={() => setEntries(initialEntries(repoPath))}
          type="button"
        >
          Clear
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 font-mono text-[12px] leading-6">
        {entries.map((entry) => (
          <div
            key={entry.id}
            className={
              entry.kind === "stderr"
                ? "whitespace-pre-wrap text-rose-300"
                : entry.kind === "command"
                  ? "whitespace-pre-wrap text-emerald-300"
                  : entry.kind === "meta"
                    ? "whitespace-pre-wrap text-slate-400"
                    : "whitespace-pre-wrap text-slate-100"
            }
          >
            {entry.text}
          </div>
        ))}
        {running ? <div className="text-slate-500">Running...</div> : null}
        <div ref={endRef} />
      </div>

      <div className="border-t border-slate-800 px-4 py-3">
        <div className="flex items-center gap-2 rounded-xl border border-slate-800 bg-[#0c1524] px-3 py-2">
          <span className="font-mono text-xs text-emerald-400">$</span>
          <input
            className="flex-1 bg-transparent font-mono text-sm text-slate-100 outline-none placeholder:text-slate-500"
            disabled={!sessionId || !repoPath || running}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void submit();
                return;
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                if (history.length === 0) return;
                const nextIndex = Math.min(
                  historyIndex + 1,
                  history.length - 1,
                );
                setHistoryIndex(nextIndex);
                setInput(history[nextIndex] ?? "");
                return;
              }
              if (event.key === "ArrowDown") {
                event.preventDefault();
                const nextIndex = historyIndex - 1;
                if (nextIndex < 0) {
                  setHistoryIndex(-1);
                  setInput("");
                  return;
                }
                setHistoryIndex(nextIndex);
                setInput(history[nextIndex] ?? "");
              }
              if (event.key === "Tab") {
                event.preventDefault();
              }
            }}
            placeholder={
              sessionId
                ? "Type command and press Enter..."
                : "Select a session to use terminal"
            }
            type="text"
            value={input}
          />
        </div>
        <div className="mt-2 flex items-center gap-3 text-[10px] text-slate-500">
          <span>↑↓ History</span>
          <span>Enter to run</span>
          <span>clear to reset</span>
        </div>
      </div>
    </div>
  );
}
