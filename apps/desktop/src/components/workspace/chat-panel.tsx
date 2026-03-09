import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "../ui/button";
import type { ChatMessage, SessionMode } from "../../types/models";

interface ChatPanelProps {
  sessionId: string | null;
  mode: SessionMode;
  messages: ChatMessage[];
  isRunning: boolean;
  onSend: (text: string) => void;
}

function roleLabel(role: ChatMessage["role"]): string {
  if (role === "assistant") return "Agent";
  if (role === "system") return "System";
  return "You";
}

export function ChatPanel({ sessionId, mode, messages, isRunning, onSend }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement | null>(null);

  const disabled = !sessionId;

  useEffect(() => {
    if (!listRef.current) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  const modeHint = useMemo(() => {
    if (mode === "plan") return "Plan 模式：只读分析，不会应用代码变更。";
    if (mode === "build") return "Build 模式：生成变更后需要审批。";
    return "Auto 模式：默认自动应用（请注意回滚与安全策略）。";
  }, [mode]);

  const submit = () => {
    const text = input.trim();
    if (!text) return;
    onSend(text);
    setInput("");
  };

  const copyMessage = async (content: string) => {
    await navigator.clipboard.writeText(content);
  };

  return (
    <div className="mb-4 rounded-md border border-border bg-card p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm font-medium">会话对话</div>
        <div className="text-xs text-muted-foreground">{modeHint}</div>
      </div>
      {isRunning ? <div className="mb-2 text-xs text-primary">Agent 正在执行（running）…</div> : null}

      <div ref={listRef} className="mb-3 max-h-64 space-y-2 overflow-auto rounded border border-border bg-background p-3">
        {!sessionId ? (
          <div className="text-xs text-muted-foreground">请先创建或选择一个会话。</div>
        ) : messages.length === 0 ? (
          <div className="text-xs text-muted-foreground">暂无消息。输入任务目标开始执行。</div>
        ) : (
          messages.map((m) => (
            <div key={m.id} className="rounded border border-border p-2 text-xs">
              <div className="mb-1 flex items-center gap-2 text-[10px] text-muted-foreground">
                <span>{roleLabel(m.role)} · {new Date(m.createdAt).toLocaleTimeString()}</span>
                <div className="ml-auto flex gap-1">
                  <Button
                    variant="ghost"
                    className="h-6 px-2 text-[10px]"
                    onClick={() => {
                      copyMessage(m.content).catch(() => {
                        // noop: clipboard may be unavailable in some environments
                      });
                    }}
                  >
                    复制
                  </Button>
                  {m.role === "user" ? (
                    <Button
                      variant="ghost"
                      className="h-6 px-2 text-[10px]"
                      onClick={() => onSend(m.content)}
                    >
                      重试发送
                    </Button>
                  ) : null}
                </div>
              </div>
              <div className="whitespace-pre-wrap text-sm">{m.content}</div>
            </div>
          ))
        )}
      </div>

      <div className="flex gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              submit();
            }
          }}
          disabled={disabled}
          className="h-20 flex-1 resize-none rounded border border-input bg-background px-3 py-2 text-sm"
          placeholder={disabled ? "请先选择会话" : "输入任务描述（Ctrl+Enter 发送）"}
        />
        <div className="flex flex-col gap-2">
          <Button onClick={submit} disabled={disabled || input.trim().length === 0}>发送</Button>
          <Button variant="outline" onClick={() => setInput("")} disabled={disabled || input.length === 0}>
            清空
          </Button>
        </div>
      </div>
    </div>
  );
}
