import Link from "next/link";
import { BookOpen, BriefcaseBusiness, LayoutDashboard } from "lucide-react";

const nav = [
  { href: "/", label: "工作台", icon: LayoutDashboard },
  { href: "/cases", label: "案件", icon: BriefcaseBusiness },
  { href: "/memory", label: "法律知识库", icon: BookOpen }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-court text-sm font-bold text-white">LF</div>
            <div>
              <div className="text-base font-semibold text-ink">LexFlow MVP</div>
              <div className="text-xs text-slate-500">法律 AI 工作流与知识沉淀系统</div>
            </div>
          </Link>
          <nav className="flex items-center gap-2">
            {nav.map((item) => {
              const Icon = item.icon;
              return (
                <Link key={item.href} href={item.href} className="button-secondary">
                  <Icon size={16} />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-6">{children}</main>
    </div>
  );
}
