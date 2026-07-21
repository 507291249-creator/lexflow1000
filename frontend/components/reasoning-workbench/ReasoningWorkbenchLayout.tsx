"use client";

import { useState, type ReactNode } from "react";
import { PanelRightOpen, X } from "lucide-react";

export function ReasoningWorkbenchLayout({
  header,
  mobileNavigator,
  reasoningRail,
  contextRail,
  children,
}: {
  header: ReactNode;
  mobileNavigator: ReactNode;
  reasoningRail: ReactNode;
  contextRail: ReactNode;
  children: ReactNode;
}) {
  const [contextOpen, setContextOpen] = useState(false);

  return (
    <div className="space-y-4 lg:flex lg:h-[calc(100vh-2.5rem)] lg:flex-col lg:gap-4 lg:space-y-0 lg:overflow-hidden">
      {/* Case header — fixed, does not scroll with the rails */}
      <div className="lg:shrink-0">{header}</div>

      {/* Mobile horizontal workflow navigator */}
      <div className="lg:hidden">{mobileNavigator}</div>

      {/* Independent scroll regions: reasoning rail | main | context rail */}
      <div className="grid min-w-0 gap-4 lg:min-h-0 lg:flex-1 lg:grid-cols-[260px_minmax(0,1fr)] lg:overflow-hidden xl:grid-cols-[280px_minmax(0,1fr)_360px]">
        <aside className="hidden lg:block lg:min-h-0 lg:overflow-y-auto lg:pr-1">{reasoningRail}</aside>
        <main className="min-w-0 space-y-4 lg:min-h-0 lg:overflow-y-auto lg:pr-1">{children}</main>
        <aside className="hidden xl:block xl:min-h-0 xl:overflow-y-auto xl:pl-1">{contextRail}</aside>
      </div>

      {/* Context rail access on screens without the persistent context column */}
      <button
        type="button"
        className="button-primary fixed bottom-5 right-5 z-30 shadow-lg xl:hidden"
        onClick={() => setContextOpen(true)}
      >
        <PanelRightOpen size={17} />
        查看上下文
      </button>

      {contextOpen && (
        <div className="fixed inset-0 z-50 xl:hidden" role="dialog" aria-modal="true" aria-label="推理上下文">
          <button className="absolute inset-0 bg-slate-950/30" aria-label="关闭上下文" onClick={() => setContextOpen(false)} />
          <div className="absolute inset-x-0 bottom-0 max-h-[82vh] overflow-y-auto rounded-t-lg border border-line bg-white p-4 shadow-2xl">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-semibold text-ink">推理上下文</h2>
              <button type="button" className="button-secondary h-9 w-9 p-0" title="关闭" onClick={() => setContextOpen(false)}>
                <X size={17} />
              </button>
            </div>
            {contextRail}
          </div>
        </div>
      )}
    </div>
  );
}
