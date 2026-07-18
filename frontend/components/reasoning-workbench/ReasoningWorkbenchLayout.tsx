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
    <div className="space-y-4">
      {header}
      <div className="xl:hidden">{mobileNavigator}</div>
      <div className="grid min-w-0 gap-4 xl:grid-cols-[280px_minmax(0,1fr)_360px] xl:items-start">
        <aside className="hidden xl:sticky xl:top-20 xl:block">{reasoningRail}</aside>
        <main className="min-w-0 space-y-4">{children}</main>
        <aside className="hidden xl:sticky xl:top-20 xl:block">{contextRail}</aside>
      </div>

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
          <button className="absolute inset-0 bg-slate-950/25" aria-label="关闭上下文" onClick={() => setContextOpen(false)} />
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
