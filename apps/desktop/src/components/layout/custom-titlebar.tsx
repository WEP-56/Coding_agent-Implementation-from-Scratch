import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { cn } from "../../lib/utils";
import { useAppStore } from "../../store/app-store";
import { isTauriRuntime } from "../../lib/platform";

interface CustomTitlebarProps {
  onToggleLeftSidebar?: () => void;
  onToggleRightSidebar?: () => void;
  onToggleTerminal?: () => void;
  onOpenInExplorer?: () => void;
  onOpenInVscode?: () => void;
  leftSidebarVisible?: boolean;
  rightSidebarVisible?: boolean;
  terminalVisible?: boolean;
  workspacePath?: string | null;
}

export function CustomTitlebar({
  onToggleLeftSidebar,
  onToggleRightSidebar,
  onToggleTerminal,
  onOpenInExplorer,
  onOpenInVscode,
  leftSidebarVisible = true,
  rightSidebarVisible = true,
  terminalVisible = false,
  workspacePath = null,
}: CustomTitlebarProps) {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useAppStore();
  const [isMaximized, setIsMaximized] = useState(false);
  const supportsWindowControl = isTauriRuntime();
  const canOpenWorkspace = !!workspacePath;

  useEffect(() => {
    if (!supportsWindowControl) return;
    const appWindow = getCurrentWindow();
    appWindow.isMaximized().then(setIsMaximized).catch(() => undefined);

    const unlisten = appWindow.onResized(async () => {
      try {
        setIsMaximized(await appWindow.isMaximized());
      } catch {
        // ignore runtime polling failures
      }
    });

    return () => {
      unlisten.then((dispose) => dispose()).catch(() => undefined);
    };
  }, [supportsWindowControl]);

  const handleMinimize = async () => {
    try {
      if (!supportsWindowControl) return;
      const appWindow = getCurrentWindow();
      await appWindow.minimize();
    } catch (error) {
      console.error("Minimize error:", error);
    }
  };

  const handleMaximize = async () => {
    try {
      if (!supportsWindowControl) return;
      const appWindow = getCurrentWindow();
      await appWindow.toggleMaximize();
      setIsMaximized(await appWindow.isMaximized());
    } catch (error) {
      console.error("Maximize error:", error);
    }
  };

  const handleClose = async () => {
    try {
      if (!supportsWindowControl) return;
      const appWindow = getCurrentWindow();
      await appWindow.close();
    } catch (error) {
      console.error("Close error:", error);
    }
  };

  return (
    <div className="flex h-12 items-center justify-between border-b border-border/50 bg-header select-none">
      {/* Left: Logo and Navigation */}
      <div className="flex items-center gap-4 px-4">
        {/* Logo - Draggable */}
          <div className="flex items-center gap-2" {...(supportsWindowControl ? { "data-tauri-drag-region": true } : {})}>
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10">
            <span className="text-xs font-bold text-primary">CG</span>
          </div>
            <span className="text-sm font-semibold" {...(supportsWindowControl ? { "data-tauri-drag-region": true } : {})}>CodingGirl</span>
          </div>

        {/* Navigation Buttons - Not draggable */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => navigate("/workspace")}
            className="rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            工作台
          </button>
          <button
            onClick={() => navigate("/repositories")}
            className="rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            仓库
          </button>
          <button
            onClick={() => navigate("/settings")}
            className="rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            设置
          </button>
          <button
            onClick={() => navigate("/plugins")}
            className="rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            插件
          </button>
        </div>
      </div>

      {/* Center: Draggable spacer + Tool Buttons */}
      <div className="flex flex-1 items-center justify-center gap-1" {...(supportsWindowControl ? { "data-tauri-drag-region": true } : {})}>
        {/* Draggable spacer */}
        <div className="flex-1" {...(supportsWindowControl ? { "data-tauri-drag-region": true } : {})} />
        
        {/* Tool Buttons - Not draggable */}
        <div className="flex items-center gap-1" data-tauri-drag-region="false">
        {/* Toggle Left Sidebar */}
        <button
          onClick={onToggleLeftSidebar}
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-md transition-colors",
            leftSidebarVisible
              ? "bg-accent text-foreground"
              : "text-muted-foreground hover:bg-accent hover:text-foreground"
          )}
          title="切换侧边栏"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        {/* Toggle Right Sidebar */}
        <button
          onClick={onToggleRightSidebar}
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-md transition-colors",
            rightSidebarVisible
              ? "bg-accent text-foreground"
              : "text-muted-foreground hover:bg-accent hover:text-foreground"
          )}
          title="切换详情面板"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 0v10" />
          </svg>
        </button>

        {/* Toggle Terminal */}
        {onOpenInVscode ? (
          <button
            onClick={onOpenInVscode}
            disabled={!canOpenWorkspace}
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-md transition-colors",
              canOpenWorkspace
                ? "text-muted-foreground hover:bg-accent hover:text-foreground"
                : "cursor-not-allowed text-muted-foreground/40"
            )}
            title={workspacePath ? `用 VS Code 打开 ${workspacePath}` : "当前没有可打开的工作区"}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 4l-8 7 8 9 4-2V6l-4-2z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M7 11l-2-1v4l2-1" />
            </svg>
          </button>
        ) : null}

        {onOpenInExplorer ? (
          <button
            onClick={onOpenInExplorer}
            disabled={!canOpenWorkspace}
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-md transition-colors",
              canOpenWorkspace
                ? "text-muted-foreground hover:bg-accent hover:text-foreground"
                : "cursor-not-allowed text-muted-foreground/40"
            )}
            title={workspacePath ? `在资源管理器中打开 ${workspacePath}` : "当前没有可打开的工作区"}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7.5A1.5 1.5 0 014.5 6H9l1.5 2H19.5A1.5 1.5 0 0121 9.5v7A1.5 1.5 0 0119.5 18h-15A1.5 1.5 0 013 16.5v-9z" />
            </svg>
          </button>
        ) : null}

        <button
          onClick={onToggleTerminal}
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-md transition-colors",
            terminalVisible
              ? "bg-accent text-foreground"
              : "text-muted-foreground hover:bg-accent hover:text-foreground"
          )}
          title="切换终端"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </button>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          title={theme === "dark" ? "切换到浅色模式" : "切换到深色模式"}
        >
          {theme === "dark" ? (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          ) : (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          )}
        </button>
        </div>
        
        {/* Draggable spacer */}
        <div className="flex-1" {...(supportsWindowControl ? { "data-tauri-drag-region": true } : {})} />
      </div>

      {/* Right: Window Controls */}
      <div className="flex items-center" data-tauri-drag-region="false">
        <button
          onClick={handleMinimize}
          disabled={!supportsWindowControl}
          className="flex h-12 w-12 items-center justify-center text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          title="最小化"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
          </svg>
        </button>
        <button
          onClick={handleMaximize}
          disabled={!supportsWindowControl}
          className="flex h-12 w-12 items-center justify-center text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          title={isMaximized ? "还原" : "最大化"}
        >
          {isMaximized ? (
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
            </svg>
          ) : (
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
          )}
        </button>
        <button
          onClick={handleClose}
          disabled={!supportsWindowControl}
          className="flex h-12 w-12 items-center justify-center text-muted-foreground hover:bg-destructive hover:text-destructive-foreground transition-colors"
          title="关闭"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
