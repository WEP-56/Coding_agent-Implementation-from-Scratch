import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { ToastCenter } from "../ui/toast-center";
import { Button } from "../ui/button";
import { useAppStore } from "../../store/app-store";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { theme, toggleTheme } = useAppStore();

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <header className="sticky top-0 z-10 flex h-12 items-center justify-between border-b border-border/50 bg-header px-4 backdrop-blur-xl">
        <div className="flex items-center gap-4" data-tauri-drag-region>
          <div className="flex items-center gap-2" data-tauri-drag-region>
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
              <span className="text-sm font-bold text-primary">CG</span>
            </div>
            <span className="select-none text-sm font-semibold tracking-tight" data-tauri-drag-region>
              CodingGirl
            </span>
          </div>
          <nav className="flex items-center gap-1 text-sm" data-tauri-drag-region>
            {(
              [
                { to: "/workspace", label: "工作台" },
                { to: "/repositories", label: "仓库" },
                { to: "/settings", label: "设置" },
                { to: "/plugins", label: "插件" },
              ] as const
            ).map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  [
                    "rounded-md px-3 py-1.5 text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground",
                    isActive ? "bg-accent text-foreground" : "",
                  ].join(" ")
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <Button 
          variant="ghost" 
          className="h-8 w-8 rounded-lg p-0 hover:bg-accent" 
          onClick={toggleTheme}
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
        </Button>
      </header>
      <main className="flex-1 overflow-auto">{children}</main>
      <ToastCenter />
    </div>
  );
}
