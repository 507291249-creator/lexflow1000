"use client";

import { ChangeEvent, isValidElement, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  BookOpen,
  Check,
  ChevronRight,
  FileText,
  FileUp,
  Gavel,
  Layers3,
  Play,
  Plus,
  RefreshCw,
  Save,
  Sparkles,
  X,
} from "lucide-react";
import {
  AIOutput,
  api,
  CaseFact,
  CaseIssue,
  CaseWorkspace,
  MemoryItem,
  WorkUnit,
} from "@/lib/api";

const tabs = ["概览", "工作流", "材料", "事实", "争点", "分析", "成果", "决策记录"] as const;
type Tab = (typeof tabs)[number];

const statusClass: Record<string, string> = {
  "已批准": "bg-[#e7f1ef] text-mint",
  "已接受": "bg-[#e7f1ef] text-mint",
  "已修改": "bg-blue-50 text-blue-700",
  "已完成": "bg-[#e7f1ef] text-mint",
  "已确认": "bg-[#e7f1ef] text-mint",
  "可生成": "bg-[#e7f1ef] text-mint",
  "部分已批准": "bg-blue-50 text-blue-700",
  "待人工复核": "bg-amber-50 text-amber-700",
  "待确认": "bg-amber-50 text-amber-700",
  "AI建议": "bg-blue-50 text-blue-700",
  "分析中": "bg-blue-50 text-blue-700",
  "已驳回": "bg-rose-50 text-rose-700",
  "需修改": "bg-rose-50 text-rose-700",
  "需重新生成": "bg-amber-50 text-amber-700",
  "失败": "bg-rose-50 text-rose-700",
  "已失效": "bg-slate-100 text-slate-500",
  "候选": "bg-violet-50 text-violet-700",
};

function requestErrorMessage(error: unknown) {
  if (!(error instanceof Error)) return "操作未完成，请重试。";
  if (error.message === "Failed to fetch" || error.message.toLowerCase().includes("networkerror")) {
    return "暂时无法连接后端服务。请等待 Render 服务唤醒，或检查前端地址是否已加入后端跨域配置。";
  }
  try {
    const detail = (JSON.parse(error.message) as { detail?: string }).detail;
    return detail || error.message;
  } catch {
    return error.message || "操作未完成，请重试。";
  }
}

export default function CaseDetailPage({ params }: { params: { id: string } }) {
  const caseId = Number(params.id);
  const [workspace, setWorkspace] = useState<CaseWorkspace | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("工作流");
  const [selectedUnitId, setSelectedUnitId] = useState<number | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [unitReason, setUnitReason] = useState("已完成材料与逻辑核验，可进入下一工作环节。");
  const [factEdit, setFactEdit] = useState<{ id: number; text: string; reason: string } | null>(null);
  const [issueDraft, setIssueDraft] = useState({ title: "", description: "", analysis_hint: "", reason: "人工补充案件争点。" });
  const [editingIssue, setEditingIssue] = useState<CaseIssue | null>(null);
  const [issueReason, setIssueReason] = useState("人工核验后更新争点状态。");
  const [analysisRevision, setAnalysisRevision] = useState("");
  const [analysisReason, setAnalysisReason] = useState("人工复核后调整结论的表述与证据策略。");
  const [supplement, setSupplement] = useState("");
  const [memoryEdit, setMemoryEdit] = useState<MemoryItem | null>(null);

  const load = async (): Promise<boolean> => {
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const data = await api<CaseWorkspace>(`/cases/${caseId}/workspace`);
        setWorkspace(data);
        setSelectedUnitId((current) => current || data.work_units[0]?.id || null);
        setError("");
        return true;
      } catch (loadError) {
        if (attempt < 2) {
          await new Promise((resolve) => window.setTimeout(resolve, attempt === 0 ? 500 : 1200));
          continue;
        }
        setError(requestErrorMessage(loadError));
      }
    }
    return false;
  };

  useEffect(() => { void load(); }, [caseId]);

  const selectedUnit = useMemo(
    () => workspace?.work_units.find((item) => item.id === selectedUnitId) || workspace?.work_units[0],
    [workspace, selectedUnitId]
  );
  const analysis = useMemo(
    () => workspace?.ai_outputs.find((item) => item.output_type === "analysis"),
    [workspace]
  );
  const draft = useMemo(
    () => workspace?.ai_outputs.find((item) => item.output_type === "draft"),
    [workspace]
  );

  useEffect(() => {
    if (analysis) setAnalysisRevision(analysis.reviewed_content || analysis.content);
  }, [analysis?.id]);

  async function request(path: string, method = "POST", body?: unknown): Promise<boolean> {
    setBusy(path);
    try {
      await api(path, body === undefined ? { method } : { method, body: JSON.stringify(body) });
      return await load();
    } catch (requestError) {
      setError(requestErrorMessage(requestError));
      return false;
    } finally {
      setBusy("");
    }
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy("upload");
    try {
      const form = new FormData();
      form.append("file", file);
      await api(`/cases/${caseId}/documents/upload`, { method: "POST", body: form });
      await load();
    } finally {
      setBusy("");
    }
  }

  if (!workspace) return <div className="card p-6 text-sm text-slate-600">{error ? <div className="flex flex-wrap items-center justify-between gap-3"><span>{error}</span><button className="button-secondary" type="button" onClick={() => void load()}><RefreshCw size={16} />重新加载案件</button></div> : "正在加载案件工作台..."}</div>;

  if (workspace.case.workflow_mode === "ai_case") {
    return <AiCaseWorkspace caseId={caseId} workspace={workspace} onReload={load} />;
  }

  const { case: caseItem } = workspace;
  const runUnit = (unit: WorkUnit) => request(`/cases/${caseId}/work-units/${unit.id}/run`);
  const reviewUnit = (unit: WorkUnit, action: string) => request(
    `/cases/${caseId}/work-units/${unit.id}/review`,
    "POST",
    { action, reason: unitReason, reviewer: caseItem.handler || "承办律师" }
  );
  const reviewFact = (fact: CaseFact, action: string, human_fact = "", reason = "人工核验案件材料后作出判断。") => request(
    `/facts/${fact.id}/review`,
    "POST",
    { action, human_fact, reason }
  );
  const reviewOutput = (output: AIOutput, action: string, human_revision = "", reason = analysisReason, supplementary_material = "") => request(
    `/ai-outputs/${output.id}/review`,
    "POST",
    { action, human_revision, reason, supplementary_material }
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold text-ink">{caseItem.title}</h1>
            <span className="badge bg-slate-100 text-slate-700">{caseItem.case_no || "案件编号待补"}</span>
          </div>
          <p className="mt-2 text-sm text-slate-600">{caseItem.claimant} 诉 {caseItem.employer} · {caseItem.case_type} · 承办人：{caseItem.handler || "未分配"}</p>
        </div>
        <button className="button-primary" disabled={Boolean(busy)} onClick={() => request(`/cases/${caseId}/workflow/run-standard`)}>
          <Play size={16} />
          运行 P0 标准工作流
        </button>
      </div>

      <div className="border-b border-line">
        <div className="flex min-w-max gap-1 overflow-x-auto pb-2">
          {tabs.map((tab) => (
            <button
              key={tab}
              className={activeTab === tab ? "rounded-md bg-court px-3 py-2 text-sm font-medium text-white" : "rounded-md px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"}
              onClick={() => setActiveTab(tab)}
              type="button"
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {error && <div role="alert" className="border-l-2 border-amber-500 bg-white px-4 py-3 text-sm text-slate-600">{error}</div>}

      {activeTab === "概览" && <Overview workspace={workspace} onOpen={(tab) => setActiveTab(tab)} />}

      {activeTab === "工作流" && (
        <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
          <section className="card p-5">
            <div className="flex items-center justify-between gap-3">
              <div><h2 className="font-semibold text-ink">标准工作流</h2><p className="mt-1 text-sm text-slate-500">按顺序运行，关键结果进入人工复核。</p></div>
              <Layers3 size={19} className="text-court" />
            </div>
            <div className="mt-5 space-y-2">
              {workspace.work_units.map((unit) => (
                <button key={unit.id} type="button" onClick={() => setSelectedUnitId(unit.id)} className={`flex w-full items-center gap-3 rounded-md border px-3 py-3 text-left ${selectedUnit?.id === unit.id ? "border-court bg-[#f0f6fb]" : "border-line hover:border-slate-400"}`}>
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600">{unit.sequence}</span>
                  <span className="min-w-0 flex-1"><span className="block font-medium text-ink">{unit.title}</span><span className="mt-0.5 block truncate text-xs text-slate-500">{unit.description}</span></span>
                  <span className={`badge shrink-0 ${statusClass[unit.status] || "bg-slate-100 text-slate-600"}`}>{unit.status}</span>
                </button>
              ))}
            </div>
          </section>

          {selectedUnit && <WorkUnitDetail
            unit={selectedUnit}
            candidate={workspace.memory_candidates.find((item) => item.source_work_unit_id === selectedUnit.id)}
            busy={busy}
            reason={unitReason}
            onReason={setUnitReason}
            onRun={() => runUnit(selectedUnit)}
            onReview={(action) => reviewUnit(selectedUnit, action)}
            onCandidate={() => request(`/work-units/${selectedUnit.id}/memory-candidate`)}
            onMemoryDecision={(memory, action, values) => request(`/memory/${memory.id}/decision`, "POST", { action, reason: values.reason, title: values.title, rule_summary: values.rule_summary, decision_pattern: values.decision_pattern, category: values.category })}
            memoryEdit={memoryEdit}
            onMemoryEdit={setMemoryEdit}
          />}
        </div>
      )}

      {activeTab === "材料" && (
        <section className="card p-5">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold text-ink">案件材料</h2><p className="mt-1 text-sm text-slate-500">上传后会进入材料理解与事实结构化工作单元。</p></div><label className="button-secondary cursor-pointer"><FileUp size={16} />{busy === "upload" ? "正在上传" : "上传材料"}<input className="hidden" type="file" accept=".txt,.pdf,.docx" onChange={upload} /></label></div>
          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {workspace.documents.map((doc) => <article key={doc.id} className="rounded-md border border-line p-4"><div className="flex items-start justify-between gap-3"><div className="font-medium text-ink">{doc.filename}</div><span className="badge bg-slate-100 text-slate-600">{doc.file_type}</span></div><p className="mt-3 line-clamp-5 text-sm leading-6 text-slate-600">{doc.raw_text}</p></article>)}
          </div>
          <EvidenceTable items={workspace.evidences} />
        </section>
      )}

      {activeTab === "事实" && (
        <section className="space-y-4">
          <div><h2 className="text-lg font-semibold text-ink">事实结构化</h2><p className="mt-1 text-sm text-slate-600">AI 提取的事实必须经人工接受、修改或驳回后才会进入已确认事实。</p></div>
          <div className="grid gap-4 lg:grid-cols-3">
            <FactColumn title="已确认事实" facts={workspace.facts.filter((item) => item.status === "已确认")} onAction={reviewFact} onEdit={setFactEdit} />
            <FactColumn title="待确认事实" facts={workspace.facts.filter((item) => item.status === "待确认")} onAction={reviewFact} onEdit={setFactEdit} />
            <FactColumn title="AI 提取事实" facts={workspace.facts.filter((item) => !item.human_fact && item.status !== "已驳回")} onAction={reviewFact} onEdit={setFactEdit} />
          </div>
          {factEdit && <section className="card p-5"><div className="flex items-center justify-between"><h3 className="font-semibold text-ink">修改 AI 提取事实</h3><button type="button" title="关闭" onClick={() => setFactEdit(null)}><X size={18} /></button></div><textarea className="mt-3 min-h-28 w-full rounded-md border border-line px-3 py-2 text-sm" value={factEdit.text} onChange={(event) => setFactEdit({ ...factEdit, text: event.target.value })} /><input className="mt-3 w-full rounded-md border border-line px-3 py-2 text-sm" placeholder="填写修改原因" value={factEdit.reason} onChange={(event) => setFactEdit({ ...factEdit, reason: event.target.value })} /><button className="button-primary mt-3" onClick={() => { const fact = workspace.facts.find((item) => item.id === factEdit.id); if (fact) void reviewFact(fact, "修改", factEdit.text, factEdit.reason).then(() => setFactEdit(null)); }}><Save size={16} />保存人工版本</button></section>}
        </section>
      )}

      {activeTab === "争点" && (
        <section className="space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-lg font-semibold text-ink">争点识别</h2><p className="mt-1 text-sm text-slate-600">从 AI 建议开始，经人工确认后进入分析和完成状态。</p></div><button className="button-secondary" onClick={() => setEditingIssue({ id: 0, case_id: caseId, work_unit_id: null, title: "", description: "", analysis_hint: "", source: "人工新增", status: "人工确认", importance: "中", related_facts: [], related_fact_ids: [], issue_version: workspace.case.issue_version, created_at: "", updated_at: "" })}><Plus size={16} />新增争点</button></div>
          <div className="grid gap-3">
            {workspace.issues.map((issue) => <IssueRow key={issue.id} issue={issue} busy={busy} onAction={(action) => request(`/issues/${issue.id}/action`, "POST", { action, reason: issueReason })} onEdit={() => setEditingIssue(issue)} onDelete={() => request(`/issues/${issue.id}`, "DELETE", { action: "删除", reason: "人工判断该争点不再适用。" })} />)}
          </div>
          {editingIssue && <IssueEditor issue={editingIssue} reason={issueReason} onReason={setIssueReason} onClose={() => setEditingIssue(null)} onSave={(issue) => { if (issue.id) return request(`/issues/${issue.id}`, "PATCH", { title: issue.title, description: issue.description, analysis_hint: issue.analysis_hint, status: issue.status, reason: issueReason }).then(() => setEditingIssue(null)); return request(`/cases/${caseId}/issues`, "POST", { ...issue, reason: issueReason }).then(() => setEditingIssue(null)); }} />}
        </section>
      )}

      {activeTab === "分析" && <AnalysisPanel output={analysis} revision={analysisRevision} onRevision={setAnalysisRevision} reason={analysisReason} onReason={setAnalysisReason} supplement={supplement} onSupplement={setSupplement} onReview={reviewOutput} />}

      {activeTab === "成果" && (
        <section className="space-y-4"><div><h2 className="text-lg font-semibold text-ink">成果</h2><p className="mt-1 text-sm text-slate-600">文书初稿与 AI 输出同样需要人工复核并保留版本差异。</p></div><OutputReviewCard output={draft} reason={analysisReason} onReason={setAnalysisReason} onReview={reviewOutput} /></section>
      )}

      {activeTab === "决策记录" && (
        <section className="card p-5"><div className="flex items-center gap-2"><BookOpen size={19} className="text-court" /><div><h2 className="font-semibold text-ink">决策记录</h2><p className="mt-1 text-sm text-slate-500">所有人工接受、修改、驳回、审批与沉淀都会留下可追溯记录。</p></div></div><div className="mt-5 space-y-4">{workspace.traces.map((trace) => <div key={trace.id} className="border-l-2 border-court pl-4"><div className="flex flex-wrap items-center gap-2"><span className="font-medium text-ink">{trace.action}</span><span className="badge bg-slate-100 text-slate-600">{trace.object_type}</span><span className="text-xs text-slate-500">{new Date(trace.created_at).toLocaleString("zh-CN")}</span></div><p className="mt-2 text-sm text-slate-700">修改原因：{trace.revision_reason}</p><details className="mt-2 text-sm text-slate-600"><summary className="cursor-pointer">查看 AI 原始版本与人工版本</summary><div className="mt-2 grid gap-2 lg:grid-cols-2"><pre className="whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs leading-5">{trace.ai_suggestion}</pre><pre className="whitespace-pre-wrap rounded-md bg-[#f0f6fb] p-3 text-xs leading-5">{trace.human_revision}</pre></div></details></div>)}</div></section>
      )}
    </div>
  );
}

function AiCaseWorkspace({ caseId, workspace, onReload }: { caseId: number; workspace: CaseWorkspace; onReload: () => Promise<boolean> }) {
  const [tab, setTab] = useState<Tab>("工作流");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [factEdit, setFactEdit] = useState<CaseFact | null>(null);
  const [issueEdit, setIssueEdit] = useState<CaseIssue | null>(null);
  const requestLock = useRef(false);

  const factUnit = workspace.work_units.find((item) => item.code === "fact_extraction");
  const issueUnit = workspace.work_units.find((item) => item.code === "issue_identification");
  const currentIssueIds = new Set(workspace.issues.map((item) => item.id));
  const analysisUnits = workspace.work_units.filter((item) => item.code.startsWith("legal_analysis:") && currentIssueIds.has(item.parent_issue_id || -1));
  const latestReport = workspace.ai_outputs.filter((item) => item.output_type === "legal_report" && item.fact_version === workspace.case.fact_version && item.issue_version === workspace.case.issue_version).sort((a, b) => b.version - a.version)[0];
  const report = workspace.workflow_state?.report_current === false ? undefined : latestReport;
  const latestFactOutput = workspace.ai_outputs.filter((item) => item.output_type === "fact_extraction").sort((a, b) => b.version - a.version)[0];
  const latestIssueOutput = workspace.ai_outputs.filter((item) => item.output_type === "issue_identification").sort((a, b) => b.version - a.version)[0];
  const factsConfirmed = workspace.facts.length > 0 && workspace.facts.every((item) => item.status !== "待确认") && workspace.facts.some((item) => item.status === "已确认");
  const issuesConfirmed = workspace.issues.length > 0 && workspace.issues.every((item) => ["人工确认", "分析中", "已完成"].includes(item.status));
  const issueRunPath = issueUnit ? `/cases/${caseId}/work-units/${issueUnit.id}/run` : "";
  const analysesConfirmPath = `/cases/${caseId}/analyses/confirm-all`;
  const pendingAnalysisCount = analysisUnits.filter((unit) => {
    const latest = workspace.ai_outputs
      .filter((item) => item.work_unit_id === unit.id && item.fact_version === workspace.case.fact_version && item.issue_version === workspace.case.issue_version)
      .sort((a, b) => b.version - a.version)[0];
    return latest?.review_status === "待复核";
  }).length;
  const approvedAnalysisCount = analysisUnits.filter((unit) => {
    const latest = workspace.ai_outputs
      .filter((item) => item.work_unit_id === unit.id && item.output_type === "legal_analysis" && item.fact_version === workspace.case.fact_version && item.issue_version === workspace.case.issue_version)
      .sort((a, b) => b.version - a.version)[0];
    return latest && ["已接受", "已修改"].includes(latest.review_status);
  }).length;
  const reportReady = workspace.workflow_state?.report_ready ?? (factsConfirmed && issuesConfirmed && approvedAnalysisCount > 0);
  const factStepStatus = factsConfirmed ? "已完成" : (factUnit?.status || "待处理");
  const issueStepStatus = issuesConfirmed ? "已完成" : (issueUnit?.status || (factsConfirmed ? "待处理" : "等待事实确认"));
  const analysisStepStatus = !analysisUnits.length
    ? "等待争点确认"
    : approvedAnalysisCount === analysisUnits.length
      ? "已完成"
      : approvedAnalysisCount > 0
        ? "部分已批准"
        : pendingAnalysisCount > 0
          ? "待人工复核"
          : "已创建";
  const reportStepStatus = report ? "已完成" : reportReady ? "可生成" : "等待已批准分析";

  function displayedUnitStatus(unit: WorkUnit) {
    if (unit.code === "fact_extraction" && factsConfirmed) return "已完成";
    if (unit.code === "issue_identification" && issuesConfirmed) return "已完成";
    if (unit.code.startsWith("legal_analysis:")) {
      const latest = workspace.ai_outputs
        .filter((item) => item.work_unit_id === unit.id && item.output_type === "legal_analysis" && item.fact_version === workspace.case.fact_version && item.issue_version === workspace.case.issue_version)
        .sort((a, b) => b.version - a.version)[0];
      if (latest && ["已接受", "已修改"].includes(latest.review_status)) return "已批准";
      if (latest?.review_status === "待复核") return "待人工复核";
      if (latest?.review_status === "已驳回") return "需修改";
    }
    return unit.status;
  }

  async function request(path: string, method = "POST", body?: unknown): Promise<boolean> {
    if (requestLock.current) return false;
    requestLock.current = true;
    setBusy(path);
    setError("");
    setNotice("");
    try {
      await api(path, body === undefined ? { method } : { method, body: JSON.stringify(body) });
      const refreshed = await onReload();
      if (!refreshed) {
        setError("操作已提交，但案件数据暂时未能刷新。请点击“重新加载案件数据”查看最新结果。");
        return false;
      } else {
        setNotice("操作已完成，页面已显示最新结果。");
      }
      return true;
    } catch (requestError) {
      setError(requestErrorMessage(requestError));
      return false;
    } finally {
      requestLock.current = false;
      setBusy("");
    }
  }

  async function reloadWorkspace() {
    setBusy("reload-workspace");
    const refreshed = await onReload();
    setError(refreshed ? "" : "案件数据仍未能读取。请稍后再试，并检查 Render 的跨域配置和服务状态。");
    setBusy("");
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy("upload");
    try {
      const body = new FormData();
      body.append("file", file);
      await api(`/cases/${caseId}/documents/upload`, { method: "POST", body });
      await onReload();
    } catch {
      setError("材料上传未完成，请检查文件后重试。");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><div className="flex flex-wrap items-center gap-2"><h1 className="text-2xl font-semibold text-ink">{workspace.case.title}</h1><span className="badge bg-[#eaf3f8] text-court">AI 案件</span></div><p className="mt-2 text-sm text-slate-600">现场材料驱动的事实、争点与法律分析闭环 · 事实版本 {workspace.case.fact_version} · 争点版本 {workspace.case.issue_version}</p></div>
        {factUnit && <button className="button-secondary" type="button" disabled={Boolean(busy)} onClick={() => request(`/cases/${caseId}/work-units/${factUnit.id}/run`)}><RefreshCw size={16} />{busy === `/cases/${caseId}/work-units/${factUnit.id}/run` ? "正在运行" : "重新提取事实"}</button>}
      </div>
      <div className="border-b border-line"><div className="flex min-w-max gap-1 overflow-x-auto pb-2">{tabs.map((item) => <button key={item} type="button" onClick={() => setTab(item)} className={tab === item ? "rounded-md bg-court px-3 py-2 text-sm font-medium text-white" : "rounded-md px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"}>{item}</button>)}</div></div>
      {error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 border-l-2 border-amber-500 bg-amber-50 px-4 py-3 text-sm text-amber-800"><span>{error}</span><button className="button-secondary" type="button" disabled={Boolean(busy)} onClick={() => void reloadWorkspace()}><RefreshCw size={16} />{busy === "reload-workspace" ? "正在加载" : "重新加载案件数据"}</button></div>}
      {notice && !error && <div role="status" className="border-l-2 border-emerald-500 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div>}

      {tab === "概览" && <AiOverview workspace={workspace} factsConfirmed={factsConfirmed} analysisCount={analysisUnits.length} onOpen={setTab} />}

      {tab === "工作流" && <section className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]"><div className="card p-5"><h2 className="font-semibold text-ink">现场分析路径</h2><div className="mt-5 space-y-3"><AiStep number="1" title="事实提取" status={factStepStatus} detail="基于现场输入和上传材料生成结构化事实。" /><AiStep number="2" title="人工确认事实" status={factsConfirmed ? "已完成" : "待确认"} detail="全部事实需接受、修改或驳回。" /><AiStep number="3" title="争点识别" status={issueStepStatus} detail="确认全部事实后，点击运行生成 AI 争点建议。" /><AiStep number="4" title="逐项法律分析" status={analysisStepStatus} detail={`${approvedAnalysisCount}/${analysisUnits.length} 项当前版本分析已批准。`} /><AiStep number="5" title="生成报告" status={reportStepStatus} detail={reportReady ? "当前已有可用于报告的已批准分析。" : "汇总当前版本的事实、争点和已批准分析。"} /></div>{reportReady && !report && <button className="button-primary mt-5 w-full" type="button" onClick={() => setTab("成果")}><FileText size={16} />前往生成法律分析报告</button>}</div><div className="card p-5"><h2 className="font-semibold text-ink">工作单元</h2><div className="mt-4 space-y-3">{workspace.work_units.map((unit) => { const runPath = `/cases/${caseId}/work-units/${unit.id}/run`; const blocked = unit.code === "issue_identification" && !factsConfirmed; const unitStatus = displayedUnitStatus(unit); return <div className="rounded-md border border-line p-4" key={unit.id}><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex items-center gap-2"><h3 className="font-medium text-ink">{unit.title}</h3><span className={`badge ${statusClass[unitStatus] || "bg-slate-100 text-slate-600"}`}>{unitStatus}</span></div><p className="mt-1 text-sm text-slate-600">{unit.description}</p></div>{(unit.code === "fact_extraction" || unit.code === "issue_identification" || unit.code.startsWith("legal_analysis:")) && <button className="button-secondary" type="button" disabled={Boolean(busy) || blocked} title={blocked ? "请先确认全部事实" : undefined} onClick={() => request(runPath)}><Play size={16} />{busy === runPath ? "正在运行" : unitStatus === "失败" ? "重新运行" : "运行"}</button>}</div>{blocked && <p className="mt-3 text-xs text-amber-700">请先在“事实”页一键确认或逐项处理全部事实。</p>}{unitStatus === "失败" && <p className="mt-3 border-l-2 border-rose-500 bg-rose-50 px-3 py-2 text-xs text-rose-700">{String((unit.output_json.error as { message?: string } | undefined)?.message || "结构化输出失败，可重新运行。")}</p>}{unit.code.startsWith("legal_analysis:") && <p className="mt-3 text-xs text-slate-500">输入事实版本 {workspace.case.fact_version} · 争点版本 {workspace.case.issue_version}</p>}</div>; })}</div></div></section>}

      {tab === "材料" && <section className="card p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold text-ink">原始材料</h2><p className="mt-1 text-sm text-slate-600">新增材料后可重新运行事实提取；已有分析不会被覆盖。</p></div><label className="button-secondary cursor-pointer"><FileUp size={16} />{busy === "upload" ? "正在上传" : "补充材料"}<input className="hidden" type="file" accept=".pdf,.docx,.txt" onChange={upload} /></label></div><div className="mt-5 divide-y divide-line">{workspace.documents.map((item) => <div key={item.id} className="py-3"><div className="font-medium text-ink">{item.filename}</div><p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-600">{item.raw_text.slice(0, 600) || "文件未能提取文本，请人工核验。"}</p></div>)}</div></section>}

      {tab === "事实" && <section className="space-y-4"><AiExtractionSummary output={latestFactOutput} outputs={workspace.ai_outputs.filter((item) => item.output_type === "fact_extraction")} /><div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-600">可先一键确认全部 AI 提取事实，再按需要逐项修改或驳回。</p><button className="button-primary" type="button" disabled={Boolean(busy) || !workspace.facts.some((item) => item.status === "待确认")} onClick={() => request(`/cases/${caseId}/facts/confirm-all`, "POST", { reason: "人工复核 AI 提取事实后批量确认，后续按需逐项修订。" })}><Check size={16} />{busy === `/cases/${caseId}/facts/confirm-all` ? "正在确认" : "一键确认全部事实"}</button></div><div className="grid gap-4 lg:grid-cols-2">{workspace.facts.map((fact) => <AiFactCard key={fact.id} fact={fact} disabled={Boolean(busy)} confirming={busy === `/facts/${fact.id}/review`} onAccept={() => request(`/facts/${fact.id}/review`, "POST", { action: "接受", reason: "人工核验现场材料后确认该事实。" })} onReject={() => request(`/facts/${fact.id}/review`, "POST", { action: "驳回", reason: "材料不足以支持该事实。" })} onEdit={() => setFactEdit(fact)} />)}</div>{factEdit && <AiFactEditor fact={factEdit} onClose={() => setFactEdit(null)} onSave={(text, reason) => request(`/facts/${factEdit.id}/review`, "POST", { action: "修改", human_fact: text, reason }).then((completed) => { if (completed) setFactEdit(null); return completed; })} />}</section>}

      {tab === "争点" && <section className="space-y-4"><AiIssueSummary output={latestIssueOutput} factsConfirmed={factsConfirmed} /><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold text-ink">已识别争点</h2><p className="mt-1 text-sm text-slate-600">可一键确认 AI 建议；确认后会动态创建对应的法律分析任务。</p></div><div className="flex flex-wrap gap-2">{issueUnit && <button className="button-secondary" type="button" disabled={Boolean(busy) || !factsConfirmed} onClick={() => request(issueRunPath)}><Play size={16} />{busy === issueRunPath ? "正在生成" : latestIssueOutput || workspace.issues.length ? "重新生成争点" : "生成 AI 争点"}</button>}<button className="button-primary" type="button" disabled={Boolean(busy) || !workspace.issues.some((item) => item.status === "AI建议")} onClick={() => request(`/cases/${caseId}/issues/confirm-all`, "POST", { reason: "人工复核 AI 争点建议后批量确认，后续按需逐项修订。" })}><Check size={16} />{busy === `/cases/${caseId}/issues/confirm-all` ? "正在确认" : "一键确认 AI 争点"}</button><button className="button-secondary" disabled={Boolean(busy) || !factsConfirmed} onClick={() => setIssueEdit({ id: 0, case_id: caseId, work_unit_id: issueUnit?.id || null, title: "", description: "", analysis_hint: "", source: "人工新增", status: "人工确认", importance: "中", related_facts: [], related_fact_ids: [], issue_version: workspace.case.issue_version, created_at: "", updated_at: "" })}><Plus size={16} />新增争点</button></div></div><div className="space-y-3">{workspace.issues.map((issue) => <AiIssueCard key={issue.id} issue={issue} facts={workspace.facts} disabled={Boolean(busy)} confirming={busy === `/issues/${issue.id}/action`} onConfirm={() => request(`/issues/${issue.id}/action`, "POST", { action: "确认", reason: "人工确认该争点需要进入法律分析。" })} onEdit={() => setIssueEdit(issue)} onDelete={() => request(`/issues/${issue.id}`, "DELETE", { action: "删除", reason: "人工判断该争点不适用。" })} />)}</div>{issueEdit && <AiIssueEditor issue={issueEdit} facts={workspace.facts} onClose={() => setIssueEdit(null)} onSave={(draft, reason) => { const payload = { title: draft.title, description: draft.description, analysis_hint: draft.analysis_hint, status: "人工确认", importance: draft.importance, related_facts: draft.related_facts, related_fact_ids: draft.related_fact_ids, reason }; const path = draft.id ? `/issues/${draft.id}` : `/cases/${caseId}/issues`; const method = draft.id ? "PATCH" : "POST"; return request(path, method, payload).then((completed) => { if (completed) setIssueEdit(null); return completed; }); }} />}</section>}

      {tab === "分析" && <section className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold text-ink">逐项法律分析</h2><p className="mt-1 text-sm text-slate-600">每个确认争点单独运行。重新运行会生成新的版本，并保留旧版本及其决策记录。</p><p className="mt-2 text-sm text-slate-500">当前版本：已批准 {approvedAnalysisCount} 项 · 待复核 {pendingAnalysisCount} 项 · 分析任务 {analysisUnits.length} 项</p></div><button className="button-primary" type="button" disabled={Boolean(busy) || pendingAnalysisCount === 0} onClick={() => request(analysesConfirmPath, "POST", { reason: "人工复核当前版本法律分析后批量接受，后续按需逐项修订。" })}><Check size={16} />{busy === analysesConfirmPath ? "正在接受" : `一键接受全部分析${pendingAnalysisCount ? `（${pendingAnalysisCount}）` : ""}`}</button></div>{analysisUnits.map((unit) => <AiAnalysisUnit key={unit.id} unit={unit} outputs={workspace.ai_outputs.filter((item) => item.work_unit_id === unit.id && item.output_type === "legal_analysis").sort((a, b) => b.version - a.version)} caseFactVersion={workspace.case.fact_version} caseIssueVersion={workspace.case.issue_version} busy={busy} onRun={() => request(`/cases/${caseId}/work-units/${unit.id}/run`)} onReview={(output, action, human_revision, reason, supplementary_material) => request(`/ai-outputs/${output.id}/review`, "POST", { action, human_revision, reason, supplementary_material })} />)}{!analysisUnits.length && <div className="card p-6 text-sm text-slate-500">请先在“争点”中确认至少一个争点。</div>}</section>}

      {tab === "成果" && <section className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold text-ink">法律分析报告</h2><p className="mt-1 text-sm text-slate-600">报告仅汇总当前事实版本、当前争点版本和已接受或已修改的法律分析。</p><p className={`mt-2 text-sm ${reportReady ? "text-emerald-700" : "text-amber-700"}`}>{reportReady ? `已具备生成条件：当前有 ${approvedAnalysisCount} 项分析获批。` : `尚未具备生成条件：当前有 ${approvedAnalysisCount} 项分析获批，请先运行并接受至少一项当前版本分析。`}</p></div><button className="button-primary" disabled={Boolean(busy) || !reportReady} title={reportReady ? undefined : "请先接受至少一项当前版本法律分析"} onClick={() => request(`/cases/${caseId}/legal-analysis-report`)}><FileText size={16} />{busy === `/cases/${caseId}/legal-analysis-report` ? "正在生成" : "生成法律分析报告"}</button></div>{report ? <div className="card p-5"><div className="flex items-center justify-between gap-3"><h3 className="font-semibold text-ink">{report.title}</h3><span className="badge bg-[#e7f1ef] text-mint">版本 {report.version}</span></div><pre className="mt-5 whitespace-pre-wrap text-sm leading-7 text-slate-700">{report.content}</pre></div> : <div className="card p-6 text-sm text-slate-500">确认事实与争点，并接受至少一份当前版本法律分析后即可生成报告。</div>}</section>}

      {tab === "决策记录" && <DecisionTimeline traces={workspace.traces} />}
    </div>
  );
}

function AiStep({ number, title, status, detail }: { number: string; title: string; status: string; detail: string }) { return <div className="flex gap-3"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#eaf3f8] text-xs font-semibold text-court">{number}</span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="font-medium text-ink">{title}</span><span className={`badge ${statusClass[status] || "bg-slate-100 text-slate-600"}`}>{status}</span></div><p className="mt-1 text-sm leading-6 text-slate-600">{detail}</p></div></div>; }

function AiOverview({ workspace, factsConfirmed, analysisCount, onOpen }: { workspace: CaseWorkspace; factsConfirmed: boolean; analysisCount: number; onOpen: (value: Tab) => void }) { const confirmedIssues = workspace.issues.filter((item) => ["人工确认", "分析中", "已完成"].includes(item.status)).length; const reportReady = Boolean(workspace.workflow_state?.report_ready); const nextTab: Tab = !factsConfirmed ? "事实" : confirmedIssues === 0 ? "争点" : reportReady ? "成果" : "分析"; const nextText = !factsConfirmed ? "先完成全部事实的接受、修改或驳回。" : confirmedIssues === 0 ? "确认需要进入分析的争点。" : reportReady ? "当前已有获批分析，可以生成法律分析报告。" : "运行并复核当前事实、争点版本对应的逐项法律分析。"; return <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]"><section className="card p-5"><h2 className="font-semibold text-ink">案件摘要</h2><p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700">{workspace.case.summary}</p><div className="mt-5 grid grid-cols-3 gap-3"><Metric label="确认事实" value={workspace.facts.filter((item) => item.status === "已确认").length} /><Metric label="确认争点" value={confirmedIssues} /><Metric label="分析任务" value={analysisCount} /></div></section><section className="card p-5"><h2 className="font-semibold text-ink">当前下一步</h2><p className="mt-2 text-sm leading-6 text-slate-600">{nextText}</p><button className="button-primary mt-5" onClick={() => onOpen(nextTab)}><ChevronRight size={16} />继续处理</button></section></div>; }

function AiExtractionSummary({ output, outputs }: { output?: AIOutput; outputs: AIOutput[] }) {
  if (!output) return <div className="card p-5 text-sm text-slate-500">事实提取任务尚未运行。</div>;
  const data = ((output.meta_json as { structured?: Record<string, unknown> })?.structured || {}) as Record<string, unknown>;
  const parties = (data.parties || {}) as Record<string, unknown>;
  const timeline = Array.isArray(data.timeline) ? data.timeline as Array<{ date?: string; event?: string }> : [];
  const pending = Array.isArray(data.pending_facts) ? data.pending_facts : [];
  const fallback = output.execution_mode === "fallback";
  return <section className="space-y-4"><section className="card p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold text-ink">AI 事实提取结果</h2><p className="mt-1 text-sm text-slate-600">版本 {output.version} · 事实版本 {output.fact_version}</p></div><span className={`badge ${fallback ? "bg-amber-50 text-amber-700" : "bg-[#e7f1ef] text-mint"}`}>{fallback ? "本地备用解析" : "AI 实时生成"}</span></div>{fallback && <p className="mt-3 border-l-2 border-amber-500 bg-amber-50 px-3 py-2 text-sm text-amber-800">当前结果由本地备用解析生成，请优先核验后再作为案件判断依据。</p>}<div className="mt-4 grid gap-3 lg:grid-cols-2"><AiField label="案件摘要" value={data.case_summary} /><AiField label="当事人" value={<>{Object.entries(parties).map(([key, value]) => <p key={key}>{key === "claimant" ? "申请人" : key === "employer" ? "被申请人" : "其他主体"}：{Array.isArray(value) ? value.join("、") || "无" : String(value || "待识别")}</p>)}</>} /><AiField label="时间线" value={<div className="space-y-2">{timeline.length ? timeline.map((item, index) => <p key={`${item.date}-${index}`}>{item.date || "待核验"}：{item.event || "待补充"}</p>) : "待生成"}</div>} /><AiField label="待确认事实" value={<div className="space-y-2">{pending.length ? pending.map((item, index) => <p key={index}>{String(item)}</p>) : "无"}</div>} /></div><div className="mt-3"><AiField label="事实置信度" value={data.fact_confidence} /></div></section><details className="card p-5"><summary className="cursor-pointer font-semibold text-ink">查看事实提取版本与输入快照（{outputs.length}）</summary><div className="mt-4 space-y-3">{[...outputs].sort((a, b) => b.version - a.version).map((item) => <div className="rounded-md border border-line p-3" key={item.id}><div className="flex flex-wrap justify-between gap-2 text-sm"><span>版本 {item.version} · {item.execution_mode === "fallback" ? "本地备用解析" : "AI 实时生成"}</span><span className="text-slate-500">事实版本 {item.fact_version}</span></div><pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-600">{JSON.stringify(item.input_snapshot_json, null, 2)}</pre></div>)}</div></details></section>;
}

function AiIssueSummary({ output, factsConfirmed }: { output?: AIOutput; factsConfirmed: boolean }) { if (!factsConfirmed) return <div className="card p-5 text-sm text-amber-700">请先完成全部事实确认，再在工作流中运行争点识别。</div>; const data = ((output?.meta_json as { structured?: Record<string, unknown> })?.structured || {}) as Record<string, unknown>; return <section className="card p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold text-ink">AI 争点建议</h2><p className="mt-1 text-sm text-slate-600">{output ? `版本 ${output.version}，请逐项确认、修改、删除或新增。` : "事实已确认，请在工作流中点击“运行”生成争点建议。"}</p></div>{output && <span className={`badge ${output.execution_mode === "fallback" ? "bg-amber-50 text-amber-700" : "bg-[#e7f1ef] text-mint"}`}>{output.execution_mode === "fallback" ? "本地备用解析" : "AI 实时生成"}</span>}</div>{output?.execution_mode === "fallback" && <p className="mt-3 border-l-2 border-amber-500 bg-amber-50 px-3 py-2 text-sm text-amber-800">请人工确认每个争点及其关联事实后再进入分析。</p>}{output && <div className="mt-4"><AiField label="AI 建议" value={data.issues} /></div>}</section>; }

function AiField({ label, value }: { label: string; value: unknown | ReactNode }) { const content = isValidElement(value) ? value : Array.isArray(value) || (value && typeof value === "object") ? JSON.stringify(value, null, 2) : String(value || "待生成"); return <div className="rounded-md border border-line p-3"><div className="text-xs font-medium text-slate-500">{label}</div>{isValidElement(content) ? <div className="mt-2 text-sm leading-6 text-slate-700">{content}</div> : <pre className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{content}</pre>}</div>; }

function AiFactCard({ fact, disabled, confirming, onAccept, onReject, onEdit }: { fact: CaseFact; disabled: boolean; confirming: boolean; onAccept: () => void; onReject: () => void; onEdit: () => void }) {
  return <article className="card p-4"><div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xs font-medium text-court">{fact.category}</span><span className={`badge ${statusClass[fact.status] || "bg-slate-100 text-slate-600"}`}>{fact.status}</span></div><p className="mt-3 text-sm leading-6 text-slate-700">{fact.human_fact || fact.ai_fact}</p><p className="mt-2 text-xs text-slate-500">置信度：{fact.confidence} · 来源：{fact.source_document}</p>{fact.status !== "已驳回" && <div className="mt-4 flex flex-wrap gap-2">{fact.status === "待确认" && <button className="button-primary" disabled={disabled} onClick={onAccept}>{confirming ? "正在确认" : "确认事实"}</button>}<button className="button-secondary" disabled={disabled} onClick={onEdit}>修改</button><button className="button-secondary" disabled={disabled} onClick={onReject}>驳回</button></div>}</article>;
}

function AiFactEditor({ fact, onClose, onSave }: { fact: CaseFact; onClose: () => void; onSave: (text: string, reason: string) => Promise<boolean> }) { const [text, setText] = useState(fact.human_fact || fact.ai_fact); const [reason, setReason] = useState("根据原始材料修订事实表述。"); return <section className="card p-5"><div className="flex items-center justify-between"><h2 className="font-semibold text-ink">修改事实</h2><button title="关闭" onClick={onClose}><X size={18} /></button></div><textarea className="mt-4 min-h-28 w-full rounded-md border border-line px-3 py-2 text-sm" value={text} onChange={(event) => setText(event.target.value)} /><input className="mt-3 w-full rounded-md border border-line px-3 py-2 text-sm" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="修改原因" /><button className="button-primary mt-3" onClick={() => void onSave(text, reason)}><Save size={16} />保存并确认</button></section>; }

function AiIssueCard({ issue, facts, disabled, confirming, onConfirm, onEdit, onDelete }: { issue: CaseIssue; facts: CaseFact[]; disabled: boolean; confirming: boolean; onConfirm: () => void; onEdit: () => void; onDelete: () => void }) {
  const linkedFacts = issue.related_fact_ids.map((id) => facts.find((fact) => String(fact.id) === id)).filter(Boolean) as CaseFact[];
  return <article className="card p-4"><div className="flex flex-wrap items-start justify-between gap-4"><div><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold text-ink">{issue.title}</h3><span className={`badge ${statusClass[issue.status] || "bg-slate-100 text-slate-600"}`}>{issue.status}</span><span className="badge bg-slate-100 text-slate-600">重要程度：{issue.importance}</span></div><p className="mt-2 text-sm leading-6 text-slate-700">{issue.description}</p><div className="mt-3 text-xs text-slate-500"><div>关联事实</div>{linkedFacts.length ? <ul className="mt-1 list-disc space-y-1 pl-4">{linkedFacts.map((fact) => <li key={fact.id}>#{fact.id} {fact.human_fact || fact.ai_fact}</li>)}</ul> : <p className="mt-1">{issue.related_facts.join("；") || "待补充"}</p>}</div></div><div className="flex flex-wrap gap-2">{issue.status === "AI建议" && <button className="button-primary" disabled={disabled} onClick={onConfirm}>{confirming ? "正在确认" : "确认争点"}</button>}<button className="button-secondary" disabled={disabled} onClick={onEdit}>修改</button><button className="button-secondary" disabled={disabled} onClick={onDelete}>删除</button></div></div></article>;
}

function AiIssueEditor({ issue, facts, onClose, onSave }: { issue: CaseIssue; facts: CaseFact[]; onClose: () => void; onSave: (draft: CaseIssue, reason: string) => Promise<boolean> }) { const [draft, setDraft] = useState(issue); const [reason, setReason] = useState("人工核验后更新争点内容。"); const toggleFact = (id: string) => setDraft({ ...draft, related_fact_ids: draft.related_fact_ids.includes(id) ? draft.related_fact_ids.filter((value) => value !== id) : [...draft.related_fact_ids, id] }); return <section className="card p-5"><div className="flex items-center justify-between"><h2 className="font-semibold text-ink">{issue.id ? "修改争点" : "新增争点"}</h2><button title="关闭" onClick={onClose}><X size={18} /></button></div><div className="mt-4 space-y-3"><input className="w-full rounded-md border border-line px-3 py-2 text-sm" value={draft.title} placeholder="争点标题" onChange={(event) => setDraft({ ...draft, title: event.target.value })} /><textarea className="min-h-20 w-full rounded-md border border-line px-3 py-2 text-sm" value={draft.description} placeholder="争点描述" onChange={(event) => setDraft({ ...draft, description: event.target.value })} /><select className="w-full rounded-md border border-line bg-white px-3 py-2 text-sm" value={draft.importance} onChange={(event) => setDraft({ ...draft, importance: event.target.value })}>{["高", "中", "低"].map((item) => <option key={item}>{item}</option>)}</select><div className="rounded-md border border-line p-3"><p className="text-xs font-medium text-slate-600">关联事实</p><div className="mt-2 space-y-2">{facts.filter((fact) => fact.status !== "已驳回").map((fact) => <label key={fact.id} className="flex items-start gap-2 text-sm text-slate-700"><input type="checkbox" checked={draft.related_fact_ids.includes(String(fact.id))} onChange={() => toggleFact(String(fact.id))} /><span>#{fact.id} {fact.human_fact || fact.ai_fact}</span></label>)}</div></div><input className="w-full rounded-md border border-line px-3 py-2 text-sm" value={reason} placeholder="修改原因" onChange={(event) => setReason(event.target.value)} /><button className="button-primary" onClick={() => void onSave(draft, reason)}><Save size={16} />保存并确认</button></div></section>; }

function AiAnalysisUnit({ unit, outputs, caseFactVersion, caseIssueVersion, busy, onRun, onReview }: { unit: WorkUnit; outputs: AIOutput[]; caseFactVersion: number; caseIssueVersion: number; busy: string; onRun: () => void; onReview: (output: AIOutput, action: string, human: string, reason: string, supplement: string) => void }) {
  const [selected, setSelected] = useState(outputs[0]?.id);
  const output = outputs.find((item) => item.id === selected) || outputs[0];
  const [revision, setRevision] = useState(output?.reviewed_content || output?.content || "");
  const [reason, setReason] = useState("人工复核该争点的法律分析。");
  const [supplement, setSupplement] = useState("");
  const latestOutputId = outputs[0]?.id;
  useEffect(() => { setSelected(latestOutputId); }, [latestOutputId]);
  useEffect(() => { setRevision(output?.reviewed_content || output?.content || ""); }, [output?.id, output?.reviewed_content]);
  const structured = ((output?.meta_json as { structured?: Record<string, unknown> })?.structured || {}) as Record<string, unknown>;
  const legalDirections = structured.legal_directions || structured.applicable_law;
  const reviewPath = output ? `/ai-outputs/${output.id}/review` : "";
  const runPath = `/cases/${unit.case_id}/work-units/${unit.id}/run`;
  const isReviewing = busy === reviewPath;
  const isLatest = Boolean(output && output.id === latestOutputId);
  const matchesCurrentInput = Boolean(output && output.fact_version === caseFactVersion && output.issue_version === caseIssueVersion);
  const reviewable = isLatest && matchesCurrentInput;
  const displayReviewStatus = reviewable ? output?.review_status : "历史版本";
  return <section className="card p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold text-ink">{unit.title}</h2><p className="mt-1 text-sm text-slate-600">当前案件输入：事实版本 {caseFactVersion} · 争点版本 {caseIssueVersion}</p></div><button className="button-primary" disabled={Boolean(busy)} onClick={onRun}><Play size={16} />{busy === runPath ? "正在运行" : unit.status === "失败" ? "重新运行" : outputs.length ? "重新运行分析" : "运行分析"}</button></div>{unit.status === "失败" && <p className="mt-4 border-l-2 border-rose-500 bg-rose-50 px-3 py-2 text-sm text-rose-700">{String((unit.output_json.error as { message?: string } | undefined)?.message || "本次结构化分析失败，请检查模型配置或稍后重新运行。")}</p>}{outputs.length > 0 && <><div className="mt-4 flex flex-wrap items-center gap-2">{outputs.map((item, index) => <button disabled={Boolean(busy)} className={item.id === output?.id ? "rounded-md bg-[#eaf3f8] px-3 py-1.5 text-xs font-medium text-court" : "rounded-md bg-slate-100 px-3 py-1.5 text-xs text-slate-600"} onClick={() => setSelected(item.id)} key={item.id}>版本 {item.version}{index === 0 ? "（最新）" : ""}</button>)}<span className={`badge ${output?.execution_mode === "fallback" ? "bg-amber-50 text-amber-700" : "bg-[#e7f1ef] text-mint"}`}>{output?.execution_mode === "fallback" ? "本地备用解析" : "AI 实时生成"}</span><span className={`badge ${statusClass[displayReviewStatus || ""] || "bg-slate-100 text-slate-600"}`}>{displayReviewStatus}</span></div>{!reviewable && <p className="mt-3 border-l-2 border-amber-500 bg-amber-50 px-3 py-2 text-sm text-amber-800">该结果属于历史版本或使用了旧事实、旧争点，只可查看。请切换最新版本，或重新运行后复核。</p>}{output?.execution_mode === "fallback" && <p className="mt-3 border-l-2 border-amber-500 bg-amber-50 px-3 py-2 text-sm text-amber-800">该分析并非实时模型输出，请在批准前完成充分人工复核。</p>}<div className="mt-4 grid gap-3 lg:grid-cols-2"><AiField label="核心结论" value={structured.core_conclusion} /><AiField label="风险等级" value={structured.risk_level} /><AiField label="主要理由" value={structured.main_reasons} /><AiField label="法律分析方向" value={legalDirections} /><AiField label="反方观点" value={structured.counter_arguments} /><AiField label="不确定事项" value={structured.uncertainties} /><AiField label="证据需求" value={structured.evidence_needs} /><AiField label="下一步行动" value={structured.next_actions} /><AiField label="AI 置信度" value={structured.confidence} /></div><details className="mt-4 rounded-md border border-line p-3"><summary className="cursor-pointer text-sm font-medium text-ink">查看本版本输入快照</summary><pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-600">{JSON.stringify(output?.input_snapshot_json || {}, null, 2)}</pre></details><div className="mt-5 border-t border-line pt-4"><textarea disabled={Boolean(busy) || !reviewable} className="min-h-40 w-full rounded-md border border-line px-3 py-3 text-sm leading-6" value={revision} onChange={(event) => setRevision(event.target.value)} /><input disabled={Boolean(busy) || !reviewable} className="mt-3 w-full rounded-md border border-line px-3 py-2 text-sm" value={reason} placeholder="复核或修改原因" onChange={(event) => setReason(event.target.value)} /><div className="mt-3 flex flex-wrap gap-2"><button className="button-primary" disabled={Boolean(busy) || !reviewable || output?.review_status === "已接受"} onClick={() => output && onReview(output, "接受", output.content, reason, "")}>{isReviewing ? "正在提交" : output?.review_status === "已接受" ? "已接受" : "接受"}</button><button className="button-secondary" disabled={Boolean(busy) || !reviewable} onClick={() => output && onReview(output, "修改", revision, reason, "")}>保存修改</button><button className="button-secondary" disabled={Boolean(busy) || !reviewable} onClick={() => output && onReview(output, "驳回", "", reason, "")}>驳回</button></div><textarea disabled={Boolean(busy) || !reviewable} className="mt-4 min-h-20 w-full rounded-md border border-line px-3 py-2 text-sm" value={supplement} placeholder="补充材料后重新分析（可填写新增证据或事实）" onChange={(event) => setSupplement(event.target.value)} /><button className="button-secondary mt-2" disabled={Boolean(busy) || !reviewable} onClick={() => output && onReview(output, "补充材料后重新分析", "", reason, supplement)}><RefreshCw size={16} />{isReviewing ? "正在提交" : "重新分析"}</button></div></>}</section>;
}

function DecisionTimeline({ traces }: { traces: CaseWorkspace["traces"] }) { return <section className="card p-5"><div className="flex items-center gap-2"><BookOpen size={19} className="text-court" /><div><h2 className="font-semibold text-ink">决策记录</h2><p className="mt-1 text-sm text-slate-500">每次事实、争点和分析的人工操作均保留 AI 原始版本、人工版本和原因。</p></div></div><div className="mt-5 space-y-4">{traces.map((trace) => <div className="border-l-2 border-court pl-4" key={trace.id}><div className="flex flex-wrap items-center gap-2"><span className="font-medium text-ink">{trace.action}</span><span className="badge bg-slate-100 text-slate-600">{trace.object_type}</span><span className="text-xs text-slate-500">{new Date(trace.created_at).toLocaleString("zh-CN")}</span></div><p className="mt-2 text-sm text-slate-700">原因：{trace.revision_reason}</p><details className="mt-2 text-sm text-slate-600"><summary className="cursor-pointer">查看版本差异</summary><div className="mt-2 grid gap-2 lg:grid-cols-2"><pre className="whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs leading-5">{trace.ai_suggestion}</pre><pre className="whitespace-pre-wrap rounded-md bg-[#f0f6fb] p-3 text-xs leading-5">{trace.human_revision}</pre></div></details></div>)}</div></section>; }

function Overview({ workspace, onOpen }: { workspace: CaseWorkspace; onOpen: (tab: Tab) => void }) {
  const confirmed = workspace.facts.filter((item) => item.status === "已确认").length;
  return <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]"><section className="card p-5"><h2 className="font-semibold text-ink">案件概览</h2><p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700">{workspace.case.summary || "尚未补充案件摘要。"}</p><div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4"><Metric label="工作单元" value={workspace.work_units.length} /><Metric label="已确认事实" value={confirmed} /><Metric label="争点" value={workspace.issues.length} /><Metric label="决策记录" value={workspace.traces.length} /></div></section><section className="card p-5"><h2 className="font-semibold text-ink">下一步</h2><p className="mt-2 text-sm leading-6 text-slate-600">{workspace.case.next_action || "从工作流开始运行材料理解与事实结构化。"}</p><button className="button-primary mt-5" onClick={() => onOpen("工作流")}><ChevronRight size={16} />进入工作流</button></section></div>;
}

function Metric({ label, value }: { label: string; value: number }) { return <div className="rounded-md border border-line p-3"><div className="text-xs text-slate-500">{label}</div><div className="mt-1 text-xl font-semibold text-ink">{value}</div></div>; }

function WorkUnitDetail({ unit, candidate, busy, reason, onReason, onRun, onReview, onCandidate, onMemoryDecision, memoryEdit, onMemoryEdit }: { unit: WorkUnit; candidate?: MemoryItem; busy: string; reason: string; onReason: (value: string) => void; onRun: () => void; onReview: (action: string) => void; onCandidate: () => void; onMemoryDecision: (memory: MemoryItem, action: string, values: { title: string; rule_summary: string; decision_pattern: string; category: string; reason: string }) => void; memoryEdit: MemoryItem | null; onMemoryEdit: (item: MemoryItem | null) => void }) {
  const [memoryReason, setMemoryReason] = useState("人工核验后确认该经验具有复用价值。");
  return <section className="space-y-5"><div className="card p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex items-center gap-2"><span className="text-xs text-slate-500">工作单元 {unit.sequence}</span><span className={`badge ${statusClass[unit.status] || "bg-slate-100 text-slate-600"}`}>{unit.status}</span></div><h2 className="mt-2 text-lg font-semibold text-ink">{unit.title}</h2><p className="mt-2 text-sm leading-6 text-slate-600">{unit.description}</p></div><button className="button-secondary" disabled={Boolean(busy)} onClick={onRun}><RefreshCw size={16} />运行</button></div><div className="mt-5 rounded-md border border-line bg-slate-50 p-4"><div className="text-xs font-medium text-slate-500">工作单元输出</div><pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap text-sm leading-6 text-slate-700">{Object.keys(unit.output_json || {}).length ? JSON.stringify(unit.output_json, null, 2) : "尚未运行该工作单元。"}</pre></div>{unit.status === "待人工复核" && <div className="mt-5"><label className="block text-xs font-medium text-slate-600">复核原因<input className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" value={reason} onChange={(event) => onReason(event.target.value)} /></label><div className="mt-3 flex flex-wrap gap-2"><button className="button-primary" onClick={() => onReview("批准")}><Check size={16} />批准工作单元</button><button className="button-secondary" onClick={() => onReview("退回修改")}>退回修改</button></div></div>}</div>{unit.status === "已批准" && !candidate && <section className="card p-5"><h3 className="font-semibold text-ink">候选法律记忆</h3><p className="mt-1 text-sm text-slate-600">已批准的工作单元可以转为候选知识，由人工决定是否沉淀。</p><button className="button-primary mt-4" onClick={onCandidate}><Sparkles size={16} />生成候选知识</button></section>}{candidate && <section className="card p-5"><div className="flex items-start justify-between gap-3"><div><div className="flex items-center gap-2"><h3 className="font-semibold text-ink">候选法律记忆</h3><span className={`badge ${statusClass[candidate.status] || "bg-slate-100 text-slate-600"}`}>{candidate.status}</span></div><p className="mt-2 text-sm text-slate-600">分类：{candidate.category} · {candidate.title}</p></div></div>{candidate.status === "候选" && <div className="mt-4 flex flex-wrap gap-2"><button className="button-primary" onClick={() => onMemoryDecision(candidate, "批准沉淀", { title: candidate.title, rule_summary: candidate.rule_summary, decision_pattern: candidate.decision_pattern, category: candidate.category, reason: memoryReason })}>批准沉淀</button><button className="button-secondary" onClick={() => onMemoryEdit(candidate)}>修改后沉淀</button><button className="button-secondary" onClick={() => onMemoryDecision(candidate, "忽略", { title: candidate.title, rule_summary: candidate.rule_summary, decision_pattern: candidate.decision_pattern, category: candidate.category, reason: "当前经验不具备稳定复用价值。" })}>忽略</button></div>}{memoryEdit?.id === candidate.id && <div className="mt-4 space-y-2"><input className="w-full rounded-md border border-line px-3 py-2 text-sm" value={memoryEdit.title} onChange={(event) => onMemoryEdit({ ...memoryEdit, title: event.target.value })} /><textarea className="min-h-20 w-full rounded-md border border-line px-3 py-2 text-sm" value={memoryEdit.rule_summary} onChange={(event) => onMemoryEdit({ ...memoryEdit, rule_summary: event.target.value })} /><select className="w-full rounded-md border border-line bg-white px-3 py-2 text-sm" value={memoryEdit.category} onChange={(event) => onMemoryEdit({ ...memoryEdit, category: event.target.value })}>{["裁判规则", "案件经验", "论证模式", "证据规则", "工作流经验"].map((item) => <option key={item}>{item}</option>)}</select><input className="w-full rounded-md border border-line px-3 py-2 text-sm" value={memoryReason} onChange={(event) => setMemoryReason(event.target.value)} /><button className="button-primary" onClick={() => onMemoryDecision(candidate, "修改后沉淀", { title: memoryEdit.title, rule_summary: memoryEdit.rule_summary, decision_pattern: memoryEdit.decision_pattern, category: memoryEdit.category, reason: memoryReason })}>保存并沉淀</button></div>}</section>}</section>;
}

function EvidenceTable({ items }: { items: CaseWorkspace["evidences"] }) { if (!items.length) return null; return <div className="mt-5 overflow-hidden rounded-md border border-line"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr><th className="px-3 py-2">证据</th><th className="px-3 py-2">证明事实</th><th className="px-3 py-2">强度</th></tr></thead><tbody className="divide-y divide-line">{items.map((item) => <tr key={item.id}><td className="px-3 py-3 font-medium text-ink">{item.name}</td><td className="px-3 py-3 text-slate-600">{item.fact_to_prove}</td><td className="px-3 py-3 text-slate-600">{item.strength}</td></tr>)}</tbody></table></div>; }

function FactColumn({ title, facts, onAction, onEdit }: { title: string; facts: CaseFact[]; onAction: (fact: CaseFact, action: string, human_fact?: string, reason?: string) => void; onEdit: (value: { id: number; text: string; reason: string }) => void }) { return <section className="card p-4"><h3 className="font-semibold text-ink">{title}<span className="ml-2 text-sm font-normal text-slate-500">{facts.length}</span></h3><div className="mt-4 space-y-3">{facts.map((fact) => <article key={fact.id} className="rounded-md border border-line p-3"><div className="flex items-center justify-between gap-2"><span className="text-xs font-medium text-court">{fact.category}</span><span className={`badge ${statusClass[fact.status] || "bg-slate-100 text-slate-600"}`}>{fact.status}</span></div><p className="mt-2 text-sm leading-6 text-slate-700">{fact.human_fact || fact.ai_fact}</p><div className="mt-2 text-xs text-slate-500">AI 置信度：{fact.confidence} · 来源：{fact.source_document || "案件摘要"}</div>{fact.status === "待确认" && <div className="mt-3 flex flex-wrap gap-2"><button className="button-secondary" onClick={() => onAction(fact, "接受")}>接受</button><button className="button-secondary" onClick={() => onEdit({ id: fact.id, text: fact.ai_fact, reason: "根据原始材料修订事实表述。" })}>修改</button><button className="button-secondary" onClick={() => onAction(fact, "驳回", "", "现有材料不足以支持该事实。")}>驳回</button></div>}</article>)}{!facts.length && <p className="text-sm text-slate-500">运行“事实结构化”后生成。</p>}</div></section>; }

function IssueRow({ issue, onAction, onEdit, onDelete }: { issue: CaseIssue; busy: string; onAction: (action: string) => void; onEdit: () => void; onDelete: () => void }) { return <article className="card p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex items-center gap-2"><h3 className="font-semibold text-ink">{issue.title}</h3><span className={`badge ${statusClass[issue.status] || "bg-slate-100 text-slate-600"}`}>{issue.status}</span></div><p className="mt-2 text-sm leading-6 text-slate-600">{issue.description}</p><p className="mt-2 text-sm text-court">分析提示：{issue.analysis_hint}</p></div><div className="flex flex-wrap gap-2"><button className="button-secondary" onClick={() => onAction("确认")}>确认</button><button className="button-secondary" onClick={() => onAction("开始分析")}>分析中</button><button className="button-secondary" onClick={() => onAction("完成")}>已完成</button><button className="button-secondary" onClick={onEdit}>修改</button><button className="button-secondary" onClick={onDelete}>删除</button></div></div></article>; }

function IssueEditor({ issue, reason, onReason, onClose, onSave }: { issue: CaseIssue; reason: string; onReason: (value: string) => void; onClose: () => void; onSave: (issue: CaseIssue) => Promise<void> }) { const [draft, setDraft] = useState(issue); return <section className="card p-5"><div className="flex items-center justify-between"><h3 className="font-semibold text-ink">{issue.id ? "修改争点" : "新增争点"}</h3><button type="button" title="关闭" onClick={onClose}><X size={18} /></button></div><div className="mt-4 space-y-3"><input className="w-full rounded-md border border-line px-3 py-2 text-sm" placeholder="争点标题" value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /><textarea className="min-h-20 w-full rounded-md border border-line px-3 py-2 text-sm" placeholder="争点说明" value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /><input className="w-full rounded-md border border-line px-3 py-2 text-sm" placeholder="分析提示" value={draft.analysis_hint} onChange={(event) => setDraft({ ...draft, analysis_hint: event.target.value })} /><input className="w-full rounded-md border border-line px-3 py-2 text-sm" placeholder="修改原因" value={reason} onChange={(event) => onReason(event.target.value)} /><button className="button-primary" onClick={() => void onSave(draft)}><Save size={16} />保存争点</button></div></section>; }

function AnalysisPanel({ output, revision, onRevision, reason, onReason, supplement, onSupplement, onReview }: { output?: AIOutput; revision: string; onRevision: (value: string) => void; reason: string; onReason: (value: string) => void; supplement: string; onSupplement: (value: string) => void; onReview: (output: AIOutput, action: string, human_revision?: string, reason?: string, supplementary_material?: string) => void }) {
  if (!output) return <section className="card p-6 text-sm text-slate-500">请先在工作流中运行“法律检索”“类案分析”或“综合论证”。</section>;
  const structured = ((output.meta_json as { structured?: Record<string, unknown> })?.structured || {}) as Record<string, unknown>;
  const fields: Array<[string, unknown]> = [
    ["核心结论", structured.core_conclusion], ["风险等级", structured.risk_level], ["主要理由", structured.main_reasons], ["支持依据", structured.supporting_basis],
    ["反方观点", structured.counter_arguments], ["不确定事项", structured.uncertainties], ["下一步证据", structured.next_evidence], ["AI 置信度", structured.confidence],
  ];
  return <section className="space-y-4"><div><h2 className="text-lg font-semibold text-ink">结构化 AI 分析</h2><p className="mt-1 text-sm text-slate-600">每次接受、修改、驳回或补充材料后重新分析都会进入决策记录。</p></div><div className="grid gap-4 lg:grid-cols-2">{fields.map(([label, value]) => <div key={label} className="card p-4"><div className="text-xs font-medium text-slate-500">{label}</div><div className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{Array.isArray(value) ? value.map((item) => `• ${item}`).join("\n") : String(value || "待生成")}</div></div>)}</div><section className="card p-5"><h3 className="font-semibold text-ink">人工复核 AI 分析</h3><textarea className="mt-3 min-h-44 w-full rounded-md border border-line px-3 py-3 text-sm leading-6" value={revision} onChange={(event) => onRevision(event.target.value)} /><input className="mt-3 w-full rounded-md border border-line px-3 py-2 text-sm" placeholder="修改或复核原因" value={reason} onChange={(event) => onReason(event.target.value)} /><div className="mt-3 flex flex-wrap gap-2"><button className="button-primary" onClick={() => onReview(output, "接受", output.content, reason)}>接受</button><button className="button-secondary" onClick={() => onReview(output, "修改", revision, reason)}>修改</button><button className="button-secondary" onClick={() => onReview(output, "驳回", "", reason)}>驳回</button></div><div className="mt-5 border-t border-line pt-4"><label className="text-sm font-medium text-ink">补充材料后重新分析<textarea className="mt-2 min-h-20 w-full rounded-md border border-line px-3 py-2 text-sm" placeholder="例如：已补充解除通知原始聊天记录和工资流水。" value={supplement} onChange={(event) => onSupplement(event.target.value)} /></label><button className="button-secondary mt-2" onClick={() => onReview(output, "补充材料后重新分析", "", reason, supplement)}><RefreshCw size={16} />重新分析</button></div></section></section>;
}

function OutputReviewCard({ output, reason, onReason, onReview }: { output?: AIOutput; reason: string; onReason: (value: string) => void; onReview: (output: AIOutput, action: string, human_revision?: string, reason?: string, supplementary_material?: string) => void }) { const [draft, setDraft] = useState(output?.reviewed_content || output?.content || ""); useEffect(() => setDraft(output?.reviewed_content || output?.content || ""), [output?.id, output?.reviewed_content]); if (!output) return <section className="card p-6 text-sm text-slate-500">运行“文书生成”工作单元后显示劳动仲裁申请书初稿。</section>; return <section className="card p-5"><div className="flex items-center justify-between"><h3 className="font-semibold text-ink">{output.title}</h3><span className={`badge ${statusClass[output.review_status] || "bg-slate-100 text-slate-600"}`}>{output.review_status}</span></div>{output.review_status === "已修改" && <p className="mt-3 border-l-2 border-court bg-[#f0f6fb] px-3 py-2 text-sm text-court">当前显示人工修改版本，AI 原始版本仍保留在决策记录中。</p>}<textarea className="mt-4 min-h-96 w-full rounded-md border border-line px-3 py-3 font-mono text-sm leading-6" value={draft} onChange={(event) => setDraft(event.target.value)} /><input className="mt-3 w-full rounded-md border border-line px-3 py-2 text-sm" placeholder="人工修改原因" value={reason} onChange={(event) => onReason(event.target.value)} /><div className="mt-3 flex flex-wrap gap-2"><button className="button-primary" onClick={() => onReview(output, "接受", output.content, reason)}>接受初稿</button><button className="button-secondary" onClick={() => onReview(output, "修改", draft, reason)}>保存人工修改</button><button className="button-secondary" onClick={() => onReview(output, "驳回", "", reason)}>驳回</button></div></section>; }
