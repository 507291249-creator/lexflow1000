"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  FileSearch,
  Files,
  Gavel,
  History,
  Play,
  Scale,
  SearchCheck,
  Sparkles,
} from "lucide-react";
import { api, CaseItem, MemoryItem } from "@/lib/api";
import { EntityCode, ReasoningStatusBadge } from "@/components/ui/ReasoningUI";

const capabilities = [
  { title: "材料理解", description: "读取案件输入与上传材料，形成推理起点。", icon: Files, available: true },
  { title: "事实结构化", description: "将材料整理为可复核、可版本化的事实。", icon: FileSearch, available: true },
  { title: "争点发现", description: "基于已确认事实识别并关联争议焦点。", icon: Gavel, available: true },
  { title: "法律分析", description: "逐争点输出结构化分析并保留人工复核。", icon: Scale, available: true },
  { title: "法规检索", description: "围绕争点召回并选择适用法规。", icon: BookOpenCheck, available: false },
  { title: "类案对比", description: "比较相似事实、裁判观点与关键差异。", icon: SearchCheck, available: false },
];

export default function DashboardPage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDashboard = async () => {
    setLoading(true);
    setError("");
    try {
      const [caseData, memoryData] = await Promise.all([api<CaseItem[]>("/cases"), api<MemoryItem[]>("/memory")]);
      setCases(caseData);
      setMemories(memoryData);
    } catch {
      setError("暂时无法连接后端服务，请等待服务唤醒后重新加载。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadDashboard(); }, []);

  const recentCases = useMemo(() => [...cases].sort((a, b) => b.id - a.id), [cases]);
  const latestCase = recentCases[0];
  const pendingCases = cases.filter((item) => !["completed", "report_ready", "已完成"].includes(item.status));

  return (
    <div className="mx-auto max-w-[1600px] space-y-6">
      {/* Workspace Header */}
      <div className="workspace-header">
        <div>
          <h1>案件工作台</h1>
          <p>管理案件工作区，跟踪分析进度，沉淀法律知识</p>
        </div>
        <div className="flex items-center gap-6 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <span className="font-medium text-ink">案件总数</span>
            <span className="font-semibold text-[var(--court)]">{cases.length}</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="font-medium text-ink">待复核</span>
            <span className="font-semibold text-[var(--warning)]">{pendingCases.length}</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="font-medium text-ink">法律记忆</span>
            <span className="font-semibold text-[var(--success-600)]">{memories.length}</span>
          </span>
        </div>
        <Link href="/cases/new" className="button-primary">
          <Sparkles size={16} />新建 AI 案件
        </Link>
      </div>

      {/* Error Alert */}
      {error && (
        <div role="alert" className="mb-4 rounded-md border-l-2 border-[var(--warning)] bg-[var(--warning-bg)] px-4 py-3 text-sm text-[var(--warning)]">
          <span>{error}</span>
          <button className="ml-auto font-medium hover:underline" onClick={loadDashboard}>重新加载</button>
        </div>
      )}

      {/* Quick Actions */}
      <section className="grid gap-3 sm:grid-cols-3">
        <Link href="/cases/new" className="card-sm flex min-h-36 flex-col justify-between px-4 transition hover:border-[var(--court)]">
          <div><span className="flex h-8 w-8 items-center justify-center rounded-md bg-[var(--primary-100)] text-[var(--court)]"><Play size={16} /></span><h2 className="mt-3 text-base font-semibold text-ink">新建 AI 案件</h2><p className="mt-1 text-xs leading-5 text-slate-600">粘贴案件事实或上传材料，建立新的推理工作区。</p></div>
          <span className="mt-2 flex items-center gap-1 text-xs font-medium text-[var(--court)]">创建案件<ArrowRight size={14} /></span>
        </Link>

        <Link href={pendingCases[0] ? `/cases/${pendingCases[0].id}` : "/cases"} className="card-sm flex min-h-36 flex-col justify-between px-4 transition hover:border-[var(--court)]">
          <div><span className="flex h-8 w-8 items-center justify-center rounded-md bg-[var(--warning-bg)] text-[var(--warning)]"><CheckCircle2 size={16} /></span><div className="mt-3 flex items-center justify-between gap-2"><h2 className="text-base font-semibold text-ink">待人工复核</h2><span className="text-xl font-semibold text-[var(--warning)]">{pendingCases.length}</span></div><p className="mt-1 text-xs leading-5 text-slate-600">继续确认事实、争点或法律分析，推动推理闭环。</p></div>
          <span className="mt-2 flex items-center gap-1 text-xs font-medium text-[var(--court)]">查看待处理<ArrowRight size={14} /></span>
        </Link>

        <Link href={latestCase ? `/cases/${latestCase.id}` : "/cases/new"} className="card-sm flex min-h-36 flex-col justify-between px-4 transition hover:border-[var(--court)]">
          <div><span className="flex h-8 w-8 items-center justify-center rounded-md bg-[var(--primary-100)] text-[var(--court)]"><History size={16} /></span><h2 className="mt-3 text-base font-semibold text-ink">继续上次推理</h2><p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{latestCase ? latestCase.title : "尚无案件，先创建第一个分析工作区。"}</p></div>
          <span className="mt-2 flex items-center gap-1 text-xs font-medium text-[var(--court)]">进入工作区<ArrowRight size={14} /></span>
        </Link>
      </section>

      {/* Two Column Layout */}
      <section className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        {/* Recent Cases */}
        <div>
          <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold text-ink">最近工作区</h2><Link href="/cases" className="text-sm font-medium text-[var(--court)] hover:underline">查看全部</Link></div>
          <div className="divide-y divide-line rounded-lg border border-line bg-white">
            {loading && <div className="px-4 py-8 text-center text-sm text-slate-500">正在读取案件...</div>}
            {!loading && !recentCases.length && <div className="px-4 py-8 text-center text-sm text-slate-500">暂无分析记录</div>}
            {recentCases.slice(0, 6).map((item) => (
              <Link key={item.id} href={`/cases/${item.id}`} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-[var(--surface-subtle)]">
                <div className="flex min-w-0 items-center gap-2"><EntityCode kind="case" id={item.id} /><div className="min-w-0"><div className="truncate text-sm font-medium text-ink">{item.title}</div><div className="flex gap-x-3 gap-y-1 mt-1 text-xs text-slate-500"><span>事实 V{item.fact_version}</span><span>争点 V{item.issue_version}</span><span>{item.case_type || "案件分析"}</span></div></div></div>
                <ArrowRight size={14} className="shrink-0 text-slate-400" />
              </Link>
            ))}
          </div>
        </div>

        {/* System Capabilities */}
        <div>
          <h2 className="mb-4 text-lg font-semibold text-ink">系统能力</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {capabilities.map((item) => {
              const Icon = item.icon;
              return (
                <article key={item.title} className="reasoning-card">
                  <div className="flex items-start justify-between gap-3">
                    <Icon size={18} className={item.available ? "text-[var(--court)]" : "text-[var(--inactive)]"} />
                    {!item.available && <ReasoningStatusBadge status="unavailable" />}
                  </div>
                  <h3 className="mt-3 text-sm font-semibold text-ink">{item.title}</h3>
                  <p className="mt-1 text-xs leading-5 text-slate-500">{item.description}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>
    </div>
  );
}
