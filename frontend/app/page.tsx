"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, BookOpen, GitBranch, Play, Scale } from "lucide-react";
import { api, CaseItem, MemoryItem } from "@/lib/api";

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
      setError("暂时无法连接后端服务，请确认后端已启动后重新连接。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadDashboard(); }, []);

  const demoCase = cases[0];

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-4">
        <Metric label="案件总数" value={cases.length} />
        <Metric label="知识沉淀" value={memories.length} />
        <Metric label="工作流阶段" value={workflowStatusLabel(demoCase?.status)} />
        <Metric label="演示类型" value="劳动仲裁" />
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.4fr_0.8fr]">
        <div className="card p-6">
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold text-ink">劳动仲裁 AI 工作流</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                从案件材料进入系统，到证据结构化、法律分析、文书初稿、人工修订和法律知识库复用提示，形成可追溯的演示闭环。
              </p>
            </div>
            {demoCase && (
              <Link href={`/cases/${demoCase.id}`} className="button-primary whitespace-nowrap">
                <Play size={16} />
                打开演示案件
              </Link>
            )}
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <Capability href={demoCase ? `/cases/${demoCase.id}` : "/cases"} icon={Scale} title="案件工作台" text="材料、证据、分析、草稿在一个页面串联。" />
            <Capability href={demoCase ? `/cases/${demoCase.id}/traces` : "/cases"} icon={GitBranch} title="决策留痕" text="记录 AI 建议、人工修改和修改原因。" />
            <Capability href="/memory" icon={BookOpen} title="法律知识库" text="将可复用判断沉淀为相似案件提示。" />
          </div>
        </div>

        <div className="card p-5">
          <div className="mb-4 text-sm font-semibold text-ink">最近案件</div>
          <div className="space-y-3">
            {loading && <div className="text-sm text-slate-500">正在读取本地服务...</div>}
            {error && (
              <div role="alert" className="border-l-2 border-amber-500 pl-3 text-sm leading-6 text-slate-600">
                <div>{error}</div>
                <button type="button" className="mt-2 text-sm font-medium text-court hover:underline" onClick={loadDashboard}>重新连接</button>
              </div>
            )}
            {cases.slice(0, 4).map((item) => (
              <Link key={item.id} href={`/cases/${item.id}`} className="block rounded-md border border-line p-3 hover:bg-slate-50">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-ink">{item.title}</div>
                  <ArrowRight size={15} className="text-slate-400" />
                </div>
                <div className="mt-1 text-xs text-slate-500">{item.claimant} / {item.employer}</div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-2 truncate text-xl font-semibold text-ink">{value}</div>
    </div>
  );
}

function Capability({ href, icon: Icon, title, text }: { href: string; icon: typeof Scale; title: string; text: string }) {
  return (
    <Link href={href} className="block rounded-md border border-line p-4 transition hover:border-court hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-court focus:ring-offset-2">
      <Icon size={18} className="text-court" />
      <div className="mt-3 font-medium text-ink">{title}</div>
      <div className="mt-1 text-sm leading-6 text-slate-600">{text}</div>
    </Link>
  );
}

function workflowStatusLabel(status?: string) {
  const labels: Record<string, string> = {
    created: "已创建",
    evidence_ready: "证据已结构化",
    analysis_ready: "法律分析已完成",
    draft_ready: "文书初稿已生成"
  };

  return status ? labels[status] || "处理中" : "待连接";
}
