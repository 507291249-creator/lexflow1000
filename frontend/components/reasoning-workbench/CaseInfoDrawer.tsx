"use client";

import { useEffect } from "react";
import { X } from "lucide-react";
import type { CaseItem } from "@/lib/api";
import { CaseManagementPanel } from "@/components/CaseManagementPanel";

export function CaseInfoDrawer({
  open,
  caseItem,
  onClose,
  onUpdated,
}: {
  open: boolean;
  caseItem: CaseItem;
  onClose: () => void;
  onUpdated: () => Promise<void>;
}) {
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose, open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="案件管理信息">
      <button className="absolute inset-0 bg-slate-950/25" aria-label="关闭案件信息" onClick={onClose} />
      <aside className="absolute inset-y-0 right-0 w-full max-w-3xl overflow-y-auto border-l border-line bg-[#f7f9fb] p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-ink">案件信息</h2>
            <p className="mt-1 text-sm text-slate-500">案件管理信息已移至次级区域，不影响法律推理主流程。</p>
          </div>
          <button type="button" className="button-secondary h-9 w-9 p-0" title="关闭" onClick={onClose}><X size={17} /></button>
        </div>
        <dl className="mb-4 grid gap-3 rounded-md border border-line bg-white p-4 sm:grid-cols-3">
          <CaseMeta label="申请人" value={caseItem.claimant} />
          <CaseMeta label="被申请人" value={caseItem.employer} />
          <CaseMeta label="争议金额" value={caseItem.claim_amount} />
        </dl>
        <CaseManagementPanel caseItem={caseItem} onUpdated={onUpdated} />
      </aside>
    </div>
  );
}

function CaseMeta({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium text-slate-500">{label}</dt>
      <dd className="mt-1 break-words text-sm font-medium text-ink">{value || "未填写"}</dd>
    </div>
  );
}
