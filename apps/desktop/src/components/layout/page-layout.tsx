import { CustomTitlebar } from "./custom-titlebar";

interface PageLayoutProps {
  children: React.ReactNode;
}

export function PageLayout({ children }: PageLayoutProps) {
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <CustomTitlebar />
      <div className="flex-1 overflow-y-auto">
        {children}
      </div>
    </div>
  );
}
