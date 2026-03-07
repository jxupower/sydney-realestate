import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

interface PageShellProps {
  title: string;
  children: React.ReactNode;
  fullHeight?: boolean;
}

export function PageShell({ title, children, fullHeight }: PageShellProps) {
  return (
    <div className="flex h-screen bg-[#F8F9FB]">
      <Sidebar />
      <div className="flex-1 ml-[220px] flex flex-col overflow-hidden">
        <TopBar title={title} />
        <main className={fullHeight ? "flex-1 overflow-hidden" : "flex-1 overflow-auto p-6"}>
          {children}
        </main>
      </div>
    </div>
  );
}
