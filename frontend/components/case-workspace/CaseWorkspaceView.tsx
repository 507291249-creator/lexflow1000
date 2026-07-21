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
import { WorkspaceFeedback } from "./shared";

function requestErrorMessage(error: unknown) {
  if (!(error instanceof Error)) return "操作未完成，请重试。";
  if (error.message === "Failed to fetch" || error.message.toLowerCase().includes("networkerror")) return "暂时无法连接后端服务。请等待 Render 服务唤醒，或检查前端地址是否已加入后端跨域配置。";
  try { return (JSON.parse(error.message) as { detail?: string }).detail || error.message; } catch { return error.message || "操作未完成，请重试。"; }
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

  return (
    <>
      <ReasoningWorkbenchLayout
        header={<CaseHeader workspace={workspace} activeStep={activeStep} busy={Boolean(busy)} onOpenCaseInfo={() => setCaseInfoOpen(true)} onRefreshFacts={workspace.case.workflow_mode === "ai_case" && factUnit ? () => void request(`/cases/${caseId}/work-units/${factUnit.id}/run`) : undefined} />}
        mobileNavigator={<WorkflowNavigator workspace={workspace} activeStep={activeStep} onChange={onStepChange} />}
        reasoningRail={<ReasoningRail workspace={workspace} activeStep={activeStep} onChange={onStepChange} />}
        contextRail={contextRail}
      >
        <WorkspaceFeedback loading={Boolean(busy) && busy !== "reload-workspace"} error={error} notice={notice} onRetry={() => void reloadWorkspace()} />
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
        {activeStep === "report" && <><ReportPanel caseId={caseId} workspace={workspace} busy={busy} request={request} /><DecisionTracePanel traces={workspace.traces} /></>}
        {nextStep && <div className="flex justify-end"><button className="button-secondary" type="button" onClick={() => onStepChange(nextStep)}>进入下一步<ChevronRight size={16} /></button></div>}
      </ReasoningWorkbenchLayout>
      <CaseInfoDrawer open={caseInfoOpen} caseItem={workspace.case} onClose={() => setCaseInfoOpen(false)} onUpdated={async () => { const ok = await onReload(); return void ok; }} />
    </>
  );
}
