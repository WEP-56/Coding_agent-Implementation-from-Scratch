import { useState, useRef, useEffect, type CSSProperties, type ReactNode } from "react";
import { cn } from "../../lib/utils";

interface WorkspaceLayoutProps {
  leftSidebar: ReactNode;
  rightSidebar: ReactNode;
  children: ReactNode;
  bottomPanel?: ReactNode;
  bottomPanelVisible?: boolean;
  leftCollapsed?: boolean;
  rightCollapsed?: boolean;
  onLeftToggle?: () => void;
  onRightToggle?: () => void;
}

export function WorkspaceLayout({
  leftSidebar,
  rightSidebar,
  children,
  bottomPanel,
  bottomPanelVisible = false,
  leftCollapsed = false,
  rightCollapsed = false,
  onLeftToggle,
  onRightToggle,
}: WorkspaceLayoutProps) {
  const [leftWidth, setLeftWidth] = useState(280);
  const [rightWidth, setRightWidth] = useState(400);
  const [resizing, setResizing] = useState<"left" | "right" | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!resizing) return;

    const handleMouseMove = (event: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();

      if (resizing === "left") {
        const newWidth = Math.max(200, Math.min(500, event.clientX - rect.left));
        setLeftWidth(newWidth);
      } else {
        const newWidth = Math.max(300, Math.min(800, rect.right - event.clientX));
        setRightWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setResizing(null);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [resizing]);

  return (
    <div ref={containerRef} className="relative flex h-full overflow-hidden">
      <aside
        className={cn(
          "flex-shrink-0 border-r border-border/50 bg-sidebar transition-all duration-200",
          leftCollapsed ? "w-0 overflow-hidden" : "",
        )}
        style={{ width: leftCollapsed ? 0 : leftWidth }}
      >
        {leftSidebar}
      </aside>

      {!leftCollapsed ? (
        <div
          className="w-1 flex-shrink-0 cursor-col-resize bg-border/30 transition-colors hover:bg-primary/50"
          onMouseDown={() => setResizing("left")}
        />
      ) : null}

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="relative flex flex-1 overflow-hidden">
          <main className="flex-1 overflow-hidden bg-background">{children}</main>

          {!rightCollapsed ? (
            <div
              className="w-1 flex-shrink-0 cursor-col-resize bg-border/30 transition-colors hover:bg-primary/50"
              onMouseDown={() => setResizing("right")}
            />
          ) : null}

          <aside
            className={cn(
              "flex-shrink-0 border-l border-border/50 bg-sidebar transition-all duration-200",
              rightCollapsed ? "w-0 overflow-hidden" : "",
            )}
            style={{ width: rightCollapsed ? 0 : rightWidth }}
          >
            {rightSidebar}
          </aside>
        </div>

        {bottomPanelVisible ? (
          <section className="h-[280px] flex-shrink-0 border-t border-border/50 bg-[#09111d]">
            {bottomPanel}
          </section>
        ) : null}
      </div>

      <button
        className="absolute left-0 top-1/2 z-20 flex h-12 w-6 -translate-y-1/2 items-center justify-center rounded-r-lg border border-l-0 border-border/50 bg-sidebar transition-all hover:bg-accent"
        onClick={onLeftToggle}
        style={
          {
            left: leftCollapsed ? 0 : leftWidth + 1,
            top: bottomPanelVisible ? "calc(50% - 140px)" : "50%",
          } as CSSProperties
        }
        title={leftCollapsed ? "显示左侧栏" : "隐藏左侧栏"}
      >
        <svg
          className={cn("h-4 w-4 transition-transform", leftCollapsed ? "" : "rotate-180")}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} />
        </svg>
      </button>

      <button
        className="absolute right-0 top-1/2 z-20 flex h-12 w-6 -translate-y-1/2 items-center justify-center rounded-l-lg border border-r-0 border-border/50 bg-sidebar transition-all hover:bg-accent"
        onClick={onRightToggle}
        style={
          {
            right: rightCollapsed ? 0 : rightWidth + 1,
            top: bottomPanelVisible ? "calc(50% - 140px)" : "50%",
          } as CSSProperties
        }
        title={rightCollapsed ? "显示右侧栏" : "隐藏右侧栏"}
      >
        <svg
          className={cn("h-4 w-4 transition-transform", rightCollapsed ? "rotate-180" : "")}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} />
        </svg>
      </button>
    </div>
  );
}
