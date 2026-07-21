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
import { EntityCode, PageHeading, ReasoningStatusBadge } from "@/components/ui/ReasoningUI";

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
    <div className="mx-auto max-w-7xl space-y-8">
      <PageHeading eyebrow="法律 AI 推理工作台" description="大模型加持下的法律工作流，每个决策节点可追溯、可修改、可记忆" action={
          <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-slate-500">
            <span>案件 {cases.length}</span>
            <span>待复核 {pendingCases.length}</span>
            <span>法律记忆 {memories.length}</span>
          </div>
      } />

      {error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 border-l-2 border-amber-500 bg-amber-50 px-4 py-3 text-sm text-amber-800"><span>{error}</span><button className="font-medium hover:underline" onClick={loadDashboard}>重新加载</button></div>}

      <section className="grid gap-4 lg:grid-cols-3">
        <Link href="/cases/new" className="card flex min-h-44 flex-col justify-between p-5 transition hover:border-court">
          <div><span className="flex h-9 w-9 items-center justify-center rounded-md bg-court text-white"><Play size={17} /></span><h2 className="mt-4 text-lg font-semibold text-ink">开始一次法律分析</h2><p className="mt-2 text-sm leading-6 text-slate-600">粘贴案件事实或上传材料，建立新的推理工作区。</p></div>
          <span className="mt-4 flex items-center gap-1 text-sm font-medium text-court">新建 AI 案件<ArrowRight size={15} /></span>
        </Link>

        <Link href={pendingCases[0] ? `/cases/${pendingCases[0].id}` : "/cases"} className="card flex min-h-44 flex-col justify-between p-5 transition hover:border-court">
          <div><span className="flex h-9 w-9 items-center justify-center rounded-md bg-amber-50 text-amber-700"><CheckCircle2 size={18} /></span><div className="mt-4 flex items-center justify-between gap-3"><h2 className="text-lg font-semibold text-ink">待人工复核</h2><span className="text-2xl font-semibold text-amber-700">{pendingCases.length}</span></div><p className="mt-2 text-sm leading-6 text-slate-600">继续确认事实、争点或法律分析，推动推理闭环。</p></div>
          <span className="mt-4 flex items-center gap-1 text-sm font-medium text-court">查看待处理案件<ArrowRight size={15} /></span>
        </Link>

        <Link href={latestCase ? `/cases/${latestCase.id}` : "/cases/new"} className="card flex min-h-44 flex-col justify-between p-5 transition hover:border-court">
          <div><span className="flex h-9 w-9 items-center justify-center rounded-md bg-[#edf5fa] text-court"><History size={18} /></span><h2 className="mt-4 text-lg font-semibold text-ink">继续上次推理</h2><p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">{latestCase ? latestCase.title : "尚无案件，先创建第一个分析工作区。"}</p></div>
          <span className="mt-4 flex items-center gap-1 text-sm font-medium text-court">进入工作区<ArrowRight size={15} /></span>
        </Link>
      </section>

      <section className="grid gap-8 lg:grid-cols-[1fr_0.9fr]">
        <div>
          <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold text-ink">最近分析</h2><Link href="/cases" className="text-sm font-medium text-court hover:underline">查看全部</Link></div>
          <div className="divide-y divide-line rounded-lg border border-line bg-white">
            {loading && <div className="px-4 py-8 text-center text-sm text-slate-500">正在读取案件...</div>}
            {!loading && !recentCases.length && <div className="px-4 py-8 text-center text-sm text-slate-500">暂无分析记录</div>}
            {recentCases.slice(0, 5).map((item) => (
              <Link key={item.id} href={`/cases/${item.id}`} className="flex items-center justify-between gap-4 px-4 py-4 hover:bg-slate-50">
                <div className="flex min-w-0 items-start gap-3"><EntityCode kind="case" id={item.id} /><div className="min-w-0"><div className="truncate text-sm font-medium text-ink">{item.title}</div><div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500"><span>事实 V{item.fact_version}</span><span>争点 V{item.issue_version}</span><span>{item.case_type || "案件分析"}</span></div></div></div>
                <ArrowRight size={16} className="shrink-0 text-slate-400" />
              </Link>
            ))}
          </div>
        </div>

        <div>
          <h2 className="mb-4 text-lg font-semibold text-ink">系统能力</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {capabilities.map((item) => {
              const Icon = item.icon;
              return <article key={item.title} className="reasoning-card"><div className="flex items-start justify-between gap-3"><Icon size={18} className={item.available ? "text-court" : "text-slate-400"} />{!item.available && <ReasoningStatusBadge status="unavailable" />}</div><h3 className="mt-3 text-sm font-semibold text-ink">{item.title}</h3><p className="mt-1 text-xs leading-5 text-slate-500">{item.description}</p></article>;
            })}
          </div>
        </div>
      </section>
    </div>
  );
}
