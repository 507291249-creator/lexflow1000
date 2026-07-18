"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpenCheck, BriefcaseBusiness, LayoutGrid, Scale } from "lucide-react";

const nav = [
  { href: "/", label: "推理首页", icon: LayoutGrid, match: (path: string) => path === "/" },
  { href: "/cases", label: "案件分析", icon: BriefcaseBusiness, match: (path: string) => path.startsWith("/cases") },
  { href: "/research", label: "法律研究", icon: Scale, match: (path: string) => path.startsWith("/research") },
  { href: "/memory", label: "法律记忆", icon: BookOpenCheck, match: (path: string) => path.startsWith("/memory") },
];

export function TopNavigation() {
  const pathname = usePathname();
  return (
    <header className="top-navigation">
      <div className="mx-auto flex max-w-[1920px] items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="flex min-w-0 items-center gap-3 py-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-court text-sm font-bold text-white">LF</span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-ink">LexFlow</span>
            <span className="hidden text-xs text-slate-500 lg:block">法律 AI 推理工作台</span>
          </span>
        </Link>
        <span className="hidden h-7 w-px bg-line md:block" />
        <nav className="ml-auto flex min-w-0 items-center gap-1 overflow-x-auto py-2" aria-label="全局导航">
          {nav.map((item) => {
            const active = item.match(pathname);
            const Icon = item.icon;
            return <Link key={item.href} href={item.href} className={`top-nav-link ${active ? "top-nav-link-active" : ""}`}><Icon size={15} /><span>{item.label}</span></Link>;
          })}
        </nav>
      </div>
    </header>
  );
}
