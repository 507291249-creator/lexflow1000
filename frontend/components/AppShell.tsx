"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import {
  BookOpenCheck,
  BriefcaseBusiness,
  LayoutGrid,
  Menu,
  Plus,
  Scale,
  X,
} from "lucide-react";

type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutGrid;
  match: (path: string) => boolean;
};

const NAV: NavItem[] = [
  { href: "/", label: "工作台", icon: LayoutGrid, match: (path) => path === "/" },
  { href: "/cases", label: "案件工作区", icon: BriefcaseBusiness, match: (path) => path.startsWith("/cases") },
  { href: "/research", label: "法律研究", icon: Scale, match: (path) => path.startsWith("/research") },
  { href: "/memory", label: "法律记忆", icon: BookOpenCheck, match: (path) => path.startsWith("/memory") },
];

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="flex min-w-0 items-center gap-3 py-1">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[var(--court)] text-white text-sm font-semibold">LF</span>
      {!compact && (
        <span className="min-w-0">
          <span className="block truncate text-sm font-semibold text-ink">LexFlow</span>
          <span className="block truncate text-[11px] text-slate-500">法律推理工作台</span>
        </span>
      )}
    </Link>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="全局导航" className="space-y-1">
      <div className="rail-section-label">主导航</div>
      {NAV.map((item) => {
        const active = item.match(pathname);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={`side-link ${active ? "side-link-active" : ""}`}
            aria-current={active ? "page" : undefined}
          >
            <Icon size={17} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function PrimaryAction({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="px-1 pt-3">
      <Link href="/cases/new" onClick={onNavigate} className="button-primary w-full justify-start">
        <Plus size={16} />
        新建案件
      </Link>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="app-shell">
      {/* Desktop sidebar */}
      <aside className="app-sidebar">
        <div className="app-sidebar-brand">
          <Brand />
        </div>
        <div className="app-sidebar-nav">
          <PrimaryAction />
          <div className="pt-4">
            <NavLinks />
          </div>
        </div>
        <div className="app-sidebar-footer">
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--mint)]" />
            推理可审计 · AI 与人工判断分离
          </div>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="app-topbar">
        <div className="flex h-14 items-center gap-3 px-4">
          <button
            type="button"
            className="button-secondary h-9 w-9 p-0"
            aria-label="打开导航"
            onClick={() => setMobileOpen(true)}
          >
            <Menu size={18} />
          </button>
          <Brand compact />
          <Link href="/cases/new" className="button-primary ml-auto button-sm">
            <Plus size={15} />
            新建
          </Link>
        </div>
      </header>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="全局导航">
          <button className="absolute inset-0 bg-slate-950/30" aria-label="关闭导航" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85%] overflow-y-auto border-r border-line bg-white p-4 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <Brand />
              <button type="button" className="button-secondary h-9 w-9 p-0" aria-label="关闭导航" onClick={() => setMobileOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <PrimaryAction onNavigate={() => setMobileOpen(false)} />
            <div className="pt-4">
              <NavLinks onNavigate={() => setMobileOpen(false)} />
            </div>
          </div>
        </div>
      )}

      <div className="app-main">
        <main className="app-content">{children}</main>
      </div>
    </div>
  );
}
