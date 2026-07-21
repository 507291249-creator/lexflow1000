"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  Clock3,
  FileSearch,
  Files,
  Gavel,
  History,
  Scale,
  SearchCheck,
} from "lucide-react";
import { api, type CaseItem, type CaseWorkspace, type MemoryItem } from "@/lib/api";
import { WORKFLOW_STEPS, getWorkflowStepState } from "@/lib/workflow-config";
import { EntityCode, ErrorState, LoadingState, ReasoningStatusBadge } from "@/components/ui/ReasoningUI";

type CaseSnapshot = {
  stage: string;
  status: "ai_generated" | "pending_review" | "human_confirmed" | "rerun_required" | "failed";
  pending: number;
  latestAction: string;
};

function summarizeWorkspace(workspace: CaseWorkspace): CaseSnapshot {
  const states = WORKFLOW_STEPS.map((step) => ({ step, state: getWorkflowStepState(workspace, step.code) }));
  const current = states.find(({ state }) => state !== "human_confirmed") || states[states.length - 1];
  const pendingFacts = workspace.facts.filter((item) => item.status === "待确认").length;
  const pendingIssues = workspace.issues.filter((item) => !["人工确认", "分析中", "已完成"].includes(item.status)).length;
  const pendingAnalysis = workspace.ai_outputs.filter((item) => item.output_type === "legal_analysis" && !["已接受", "已修改"].includes(item.review_status)).length;
  const latest = [...workspace.ai_outputs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0];
  const mapped =
    current.state === "failed" ? "failed"
      : current.state === "rerun_required" ? "rerun_required"
      : current.state === "pending_review" ? "pending_review"
      : current.state === "human_confirmed" ? "human_confirmed"
      : "ai_generated";
  return { stage: current.step.title, status: mapped, pending: pendingFacts + pendingIssues + pendingAnalysis, latestAction: latest ? `${latest.title} · V${latest.version}` : "尚未生成 AI 输出" };
}

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
  const [snapshots, setSnapshots] = useState<Record<number, CaseSnapshot>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadDashboard() {
    setLoading(true);
    setError("");
    try {
      const caseData = await api<CaseItem[]>("/cases");
      setCases(caseData);
      const memoryData = await api<MemoryItem[]>("/memory").catch(() => [] as MemoryItem[]);
      setMemories(memoryData);
      const settled = await Promise.allSettled(caseData.map((item) => api<CaseWorkspace>(`/cases/${item.id}/workspace`)));
      const next: Record<number, CaseSnapshot> = {};
      settled.forEach((result, index) => {
        if (result.status === "fulfilled") next[caseData[index].id] = summarizeWorkspace(result.value);
      });
      setSnapshots(next);
    } catch {
      setError("暂时无法连接后端服务，请等待服务唤醒后重新加载。");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadDashboard(); }, []);

  const recentCases = useMemo(() => [...cases].sort((a, b) => b.id - a.id), [cases]);
  const latestCase = recentCases[0];
  const pendingCases = useMemo(
    () => cases
      .map((item) => ({ item, snapshot: snapshots[item.id] }))
      .filter(({ snapshot }) => snapshot && ["pending_review", "rerun_required", "failed", "ai_generated"].includes(snapshot.status))
      .sort((a, b) => (b.snapshot?.pending ?? 0) - (a.snapshot?.pending ?? 0)),
    [cases, snapshots],
  );
  const pendingCount = pendingCases.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="workspace-header">
        <div>
          <h1>工作台</h1>
          <p>跟踪推理进度，进入待复核案件，沉淀法律知识。</p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/cases/new" className="button-primary">
            <Scale size={16} />新建 AI 案件
          </Link>
        </div>
      </div>

      {/* Metric strip */}
      <section className="metric-strip">
        <MetricTile label="案件总数" value={String(cases.length)} hint={loading ? "读取中" : `${recentCases.length} 个工作区`} accent="court" />
        <MetricTile label="待复核" value={String(pendingCount)} hint="需人工确认或重跑" accent="warning" />
        <MetricTile label="法律记忆" value={String(memories.length)} hint="已批准沉淀" accent="mint" />
        <MetricTile label="最近推理" value={latestCase ? `C-${String(latestCase.id).padStart(2, "0")}` : "—"} hint={latestCase ? latestCase.title : "尚无案件"} accent="ai" />
      </section>

      {error && (
        <div role="alert" className="feedback-state border-[var(--warning-border)] bg-[var(--warning-bg)] text-[var(--warning)]">
          <span className="flex-1">{error}</span>
          <button className="button-secondary" onClick={loadDashboard}>重新加载</button>
        </div>
      )}

      {loading && <LoadingState label="正在读取案件与推理进度" />}

      {/* Work queue + recent */}
      <section className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <div className="min-w-0">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-base font-semibold text-ink">待办工作队列</h2>
            <Link href="/cases" className="text-sm font-medium text-court hover:underline">查看全部案件</Link>
          </div>
          {!loading && !pendingCount && (
            <div className="empty-state">
              <CheckCircle2 size={20} className="text-[var(--mint)]" />
              <div>
                <div className="font-medium text-ink">暂无待复核案件</div>
                <p>所有案件当前均处于已确认或已完成状态。</p>
              </div>
            </div>
          )}
          {pendingCases.length > 0 && (
            <div className="work-queue">
              <table>
                <thead>
                  <tr>
                    <th>案件</th>
                    <th className="hidden md:table-cell">阶段</th>
                    <th>状态</th>
                    <th className="hidden sm:table-cell">待处理</th>
                    <th className="hidden lg:table-cell">最近 AI 动作</th>
                  </tr>
                </thead>
                <tbody>
                  {pendingCases.slice(0, 8).map(({ item, snapshot }) => (
                    <tr key={item.id} className="work-queue-row-link" onClick={() => { window.location.href = `/cases/${item.id}`; }}>
                      <td>
                        <div className="flex items-center gap-2">
                          <EntityCode kind="case" id={item.id} />
                          <div className="min-w-0">
                            <div className="truncate font-medium text-ink">{item.title}</div>
                            <div className="text-xs text-slate-500">{item.case_type || "案件分析"} · F{item.fact_version} / I{item.issue_version}</div>
                          </div>
                        </div>
                      </td>
                      <td className="hidden md:table-cell text-sm text-slate-600">{snapshot?.stage || "—"}</td>
                      <td><ReasoningStatusBadge status={snapshot?.status || "ai_generated"} /></td>
                      <td className="hidden sm:table-cell">
                        <span className={snapshot?.pending ? "font-semibold text-[var(--warning)]" : "text-slate-400"}>{snapshot?.pending ?? "—"}</span>
                      </td>
                      <td className="hidden lg:table-cell">
                        <span className="flex items-center gap-1 text-xs text-slate-500"><Clock3 size={12} /><span className="truncate max-w-[200px]">{snapshot?.latestAction || "—"}</span></span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="min-w-0">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-base font-semibold text-ink">最近工作区</h2>
            <Link href={latestCase ? `/cases/${latestCase.id}` : "/cases/new"} className="text-sm font-medium text-court hover:underline">继续上次推理</Link>
          </div>
          <div className="divide-y divide-line rounded-lg border border-line bg-white">
            {!loading && !recentCases.length && <div className="px-4 py-8 text-center text-sm text-slate-500">暂无分析记录</div>}
            {recentCases.slice(0, 6).map((item) => (
              <Link key={item.id} href={`/cases/${item.id}`} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-[var(--surface-subtle)]">
                <div className="flex min-w-0 items-center gap-2">
                  <EntityCode kind="case" id={item.id} />
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-ink">{item.title}</div>
                    <div className="mt-1 flex gap-x-3 text-xs text-slate-500">
                      <span>事实 V{item.fact_version}</span>
                      <span>争点 V{item.issue_version}</span>
                      <span>{item.case_type || "案件分析"}</span>
                    </div>
                  </div>
                </div>
                <ArrowRight size={14} className="shrink-0 text-slate-400" />
              </Link>
            ))}
          </div>

          {/* Continue last reasoning shortcut */}
          {latestCase && (
            <Link href={`/cases/${latestCase.id}`} className="mt-3 flex items-center gap-3 rounded-md border border-line bg-white px-4 py-3 hover:border-court">
              <History size={16} className="text-court" />
              <div className="min-w-0 flex-1">
                <div className="text-xs text-slate-500">继续上次推理</div>
                <div className="truncate text-sm font-medium text-ink">{latestCase.title}</div>
              </div>
              <ArrowRight size={14} className="text-slate-400" />
            </Link>
          )}
        </div>
      </section>

      {/* System capabilities — compact status strip */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold text-ink">系统能力</h2>
          <span className="text-xs text-slate-500">已接入 / 预留</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {capabilities.map((item) => {
            const Icon = item.icon;
            return (
              <article key={item.title} className="reasoning-card">
                <div className="flex items-start justify-between gap-3">
                  <Icon size={18} className={item.available ? "text-court" : "text-inactive"} />
                  {!item.available && <ReasoningStatusBadge status="unavailable" />}
                </div>
                <h3 className="mt-3 text-sm font-semibold text-ink">{item.title}</h3>
                <p className="mt-1 text-xs leading-5 text-slate-500">{item.description}</p>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function MetricTile({ label, value, hint, accent }: { label: string; value: string; hint: string; accent: "court" | "warning" | "mint" | "ai" }) {
  const accentClass =
    accent === "warning" ? "text-[var(--warning)]"
      : accent === "mint" ? "text-[var(--mint)]"
      : accent === "ai" ? "text-[var(--ai-600)]"
      : "text-[var(--court)]";
  return (
    <div className="metric-tile">
      <div className="metric-tile-label">{label}</div>
      <div className={`metric-tile-value ${accentClass}`}>{value}</div>
      <div className="metric-tile-hint truncate">{hint}</div>
    </div>
  );
}
