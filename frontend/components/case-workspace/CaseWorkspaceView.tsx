"use client";

import { type ChangeEvent, useRef, useState } from "react";
import { ChevronRight, Play } from "lucide-react";
import { api, type CaseWorkspace, type DocumentItem } from "@/lib/api";
import { getNextWorkflowStep, type WorkflowStepCode } from "@/lib/workflow-config";
import {
  CaseInfoDrawer,
  ContextRail,
  ReasoningRail,
  ReasoningWorkbenchLayout,
} from "@/components/reasoning-workbench";
import { AnalysisPanel } from "./AnalysisPanel";
import { CaseHeader } from "./CaseHeader";
import { CaseOverviewPanel } from "./CaseOverviewPanel";
import { DecisionTracePanel } from "./DecisionTracePanel";
import { FactReviewPanel } from "./FactReviewPanel";
import { IssueReviewPanel } from "./IssueReviewPanel";
import { MaterialsPanel } from "./MaterialsPanel";
import { ReportPanel } from "./ReportPanel";
import { WorkflowNavigator } from "./WorkflowNavigator";
import { VersionHistoryPanel } from "./VersionHistoryPanel";
import { WorkspaceFeedback } from "./shared";

function requestErrorMessage(error: unknown) {
  if (!(error instanceof Error)) return "操作未完成，请重试。";
  if (error.message === "Failed to fetch" || error.message.toLowerCase().includes("networkerror")) return "暂时无法连接后端服务。请等待 Render 服务唤醒，或检查前端地址是否已加入后端跨域配置。";
  try { return (JSON.parse(error.message) as { detail?: string }).detail || error.message; } catch { return error.message || "操作未完成，请重试。"; }
}

const staleReasonLabels: Record<string, string> = {
  material_version_changed: "材料正式版本已变化",
  fact_version_changed: "事实正式版本已变化",
  issue_version_changed: "争点正式版本已变化",
  analysis_version_changed: "分析正式版本已变化",
  report_version_changed: "报告正式版本已变化",
  analysis_digest_changed: "正式分析内容摘要已变化",
  report_digest_changed: "正式报告内容摘要已变化",
  analysis_set_changed: "正式分析集合已变化",
  input_versions_changed: "多个输入正式版本已变化",
  input_versions_and_analysis_set_changed: "输入版本和正式分析集合均已变化",
  report_pending_review: "报告尚未完成人工复核",
};

function formatVersions(versions: Record<string, number>) {
  const labels: Record<string, string> = { material_version: "材料", fact_version: "事实", issue_version: "争点", analysis_version: "分析", report_version: "报告" };
  return Object.entries(versions).map(([key, value]) => `${labels[key] || key} ${value > 0 ? `V${value}` : "未发布"}`).join(" · ");
}

export function CaseWorkspaceView({ caseId, workspace, activeStep, onStepChange, onReload }: { caseId: number; workspace: CaseWorkspace; activeStep: WorkflowStepCode; onStepChange: (step: WorkflowStepCode) => void; onReload: () => Promise<boolean> }) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [caseInfoOpen, setCaseInfoOpen] = useState(false);
  const requestLock = useRef(false);

  async function request(path: string, method = "POST", body?: unknown): Promise<boolean> {
    if (requestLock.current) return false;
    requestLock.current = true;
    setBusy(path); setError(""); setNotice("");
    try {
      await api(path, body === undefined ? { method } : { method, body: JSON.stringify(body) });
      const refreshed = await onReload();
      if (!refreshed) { setError("操作已提交，但案件数据暂时未能刷新。请重新加载查看最新结果。"); return false; }
      setNotice("操作已完成，页面已显示最新结果。");
      return true;
    } catch (requestError) { setError(requestErrorMessage(requestError)); return false; }
    finally { requestLock.current = false; setBusy(""); }
  }

  async function reloadWorkspace() { setBusy("reload-workspace"); const ok = await onReload(); setError(ok ? "" : "案件数据仍未能读取，请稍后再试。"); setBusy(""); }
  async function upload(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (!file) return; setBusy("upload"); setError(""); try { const form = new FormData(); form.append("file", file); await api(`/cases/${caseId}/documents/upload`, { method: "POST", body: form }); await onReload(); setNotice("材料已上传并进入现有解析流程。"); } catch (uploadError) { setError(requestErrorMessage(uploadError)); } finally { setBusy(""); event.target.value = ""; } }
  async function download(item: DocumentItem) { setBusy(`download:${item.id}`); try { const result = await api<{ url: string }>(`/documents/${item.id}/download-url`); const anchor = document.createElement("a"); anchor.href = result.url; anchor.rel = "noopener noreferrer"; anchor.click(); } catch (downloadError) { setError(requestErrorMessage(downloadError)); } finally { setBusy(""); } }
  async function remove(item: DocumentItem) { if (!window.confirm(`确认删除材料“${item.original_filename || item.filename}”吗？原始文件也会同步删除。`)) return; await request(`/cases/${caseId}/documents/${item.id}`, "DELETE"); }

  const factUnit = workspace.work_units.find((unit) => unit.code === "fact_extraction");
  const nextStep = getNextWorkflowStep(activeStep);
  const contextRail = <ContextRail workspace={workspace} activeStep={activeStep} />;
  const historyRefreshKey = workspace.workflow_state?.versions
    ? Object.values(workspace.workflow_state.versions).join(":")
    : `${workspace.case.material_version}:${workspace.case.fact_version}:${workspace.case.issue_version}:${workspace.case.analysis_version}:${workspace.case.report_version}`;
  const traceRefreshKey = `${historyRefreshKey}:${workspace.traces.length}`;

  return (
    <>
      <ReasoningWorkbenchLayout
        header={<CaseHeader workspace={workspace} activeStep={activeStep} busy={Boolean(busy)} onOpenCaseInfo={() => setCaseInfoOpen(true)} onRefreshFacts={workspace.case.workflow_mode === "ai_case" && factUnit ? () => void request(`/cases/${caseId}/work-units/${factUnit.id}/run`) : undefined} />}
        mobileNavigator={<WorkflowNavigator workspace={workspace} activeStep={activeStep} onChange={onStepChange} />}
        reasoningRail={<ReasoningRail workspace={workspace} activeStep={activeStep} onChange={onStepChange} />}
        contextRail={contextRail}
      >
        <WorkspaceFeedback loading={Boolean(busy) && busy !== "reload-workspace"} error={error} notice={notice} onRetry={() => void reloadWorkspace()} />
        {workspace.workflow_state?.stale_outputs?.length ? <details className="feedback-state border-[var(--warning-border)] bg-[var(--warning-bg)] text-[var(--warning)]">
          <summary className="cursor-pointer font-medium">{workspace.workflow_state.stale_outputs.length} 项产物需要更新</summary>
          <div className="mt-2 space-y-1 text-xs">{workspace.workflow_state.stale_outputs.map((item) => <div key={`${item.entity_type}:${item.entity_id}`}>{item.title} · {staleReasonLabels[item.stale_reason] || item.stale_reason} · 输入：{formatVersions(item.input_versions)} · 当前：{formatVersions(item.current_versions)}</div>)}</div>
        </details> : null}
        {activeStep === "case_input" && (
          <>
            <CaseOverviewPanel workspace={workspace} onNext={onStepChange} />
            {workspace.case.workflow_mode !== "ai_case" && <div className="flex justify-end"><button className="button-primary" disabled={Boolean(busy)} onClick={() => request(`/cases/${caseId}/workflow/run-standard`)}><Play size={16} />运行标准工作流</button></div>}
          </>
        )}
        {activeStep === "materials" && <MaterialsPanel caseId={caseId} documents={workspace.documents} facts={workspace.facts} busy={busy} onUpload={upload} onDownload={(item) => void download(item)} onDelete={(item) => void remove(item)} onWorkspaceReload={onReload} />}
        {activeStep === "fact_review" && <FactReviewPanel caseId={caseId} workspace={workspace} busy={busy} request={request} />}
        {activeStep === "issue_review" && <IssueReviewPanel caseId={caseId} workspace={workspace} busy={busy} request={request} />}
        {activeStep === "legal_analysis" && <AnalysisPanel caseId={caseId} workspace={workspace} busy={busy} request={request} />}
        {activeStep === "report" && <><ReportPanel caseId={caseId} workspace={workspace} busy={busy} request={request} /><VersionHistoryPanel caseId={caseId} refreshKey={historyRefreshKey} /><DecisionTracePanel caseId={caseId} refreshKey={traceRefreshKey} /></>}
        {nextStep && <div className="flex justify-end"><button className="button-secondary" type="button" onClick={() => onStepChange(nextStep)}>进入下一步<ChevronRight size={16} /></button></div>}
      </ReasoningWorkbenchLayout>
      <CaseInfoDrawer open={caseInfoOpen} caseItem={workspace.case} onClose={() => setCaseInfoOpen(false)} onUpdated={async () => { const ok = await onReload(); return void ok; }} />
    </>
  );
}
