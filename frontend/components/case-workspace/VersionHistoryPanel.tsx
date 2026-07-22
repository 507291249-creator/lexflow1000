"use client";

import { useEffect, useState } from "react";
import { History } from "lucide-react";
import { api, type VersionHistoryPage } from "@/lib/api";

const labels: Record<string, string> = { material: "材料", fact: "事实", issue: "争点", analysis: "分析", report: "报告" };

export function VersionHistoryPanel({ caseId, refreshKey = "" }: { caseId: number; refreshKey?: string }) {
  const [history, setHistory] = useState<VersionHistoryPage | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    let active = true;
    api<VersionHistoryPage>(`/cases/${caseId}/version-history?page=1&page_size=100`).then((result) => { if (active) setHistory(result); }).catch(() => { if (active) setHistory(null); });
    return () => { active = false; };
  }, [caseId, refreshKey]);
  if (!history) return null;
  const publications = history.items.filter((item) => item.entry_type === "publication");
  return <section className="rounded-md border border-line bg-[var(--surface-subtle)]">
    <button type="button" className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left" onClick={() => setOpen((value) => !value)}>
      <span className="flex items-center gap-2 text-sm font-medium text-ink"><History size={15} className="text-court" />正式版本历史</span><span className="text-xs text-slate-500">{publications.length} 次发布</span>
    </button>
    {open && <div className="space-y-2 border-t border-line-subtle px-4 py-3">
      {!publications.length ? <p className="text-xs text-slate-500">尚无正式发布事件；版本 0 表示未正式发布。</p> : publications.map((item) => <div key={item.event_id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-white px-3 py-2 text-xs">
        <span className="font-medium text-ink">{labels[item.object_type] || item.object_type} {item.published_version ? `V${item.published_version}` : "未发布"}</span>
        <span className={item.is_current ? "text-[var(--mint)]" : "text-[var(--warning)]"}>{item.is_current ? "当前正式版本" : "已被后续版本取代"}</span>
        <span className="text-slate-500">{new Date(item.created_at).toLocaleString("zh-CN")}</span>
        {item.reason && <span className="w-full text-slate-600">{item.reason}</span>}
      </div>)}
    </div>}
  </section>;
}
