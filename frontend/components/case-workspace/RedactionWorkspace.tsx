"use client";

import { Fragment, type ReactNode, useEffect, useMemo, useState } from "react";
import {
  CheckCheck,
  Eye,
  FileWarning,
  Pencil,
  Plus,
  RefreshCw,
  ShieldCheck,
  ShieldOff,
  Trash2,
} from "lucide-react";
import { api, type DocumentItem, type RedactionItem, type RedactionRecord } from "@/lib/api";
import { EntityCode, ReasoningStatusBadge } from "@/components/ui/ReasoningUI";

type RedactionAction = RedactionItem["action"];

const entityLabels: Record<string, string> = {
  "身份证": "身份证",
  "手机号": "手机号",
  "邮箱": "邮箱",
  "银行卡": "银行卡",
  "统一社会信用代码": "统一社会信用代码",
  "固定电话": "固定电话",
  "IP地址": "IP 地址",
  "自然人姓名": "姓名",
  "企业名称": "企业名称",
  "地址": "地址",
  "自定义敏感信息": "自定义敏感信息",
};

const actionLabels: Record<RedactionAction, string> = {
  consistent_alias: "一致别名",
  partial_mask: "部分遮盖",
  full_replace: "完全替换",
  keep: "保留原文",
};

function redactionStatus(record: RedactionRecord) {
  if (!record.source_current || record.status === "superseded") return "已过期";
  if (record.status === "confirmed") return "已人工确认";
  if (record.status === "original_confirmed") return "已确认原文分析";
  return "待人工确认";
}

function formatError(error: unknown) {
  if (!(error instanceof Error)) return "操作未完成，请重试。";
  try {
    return (JSON.parse(error.message) as { detail?: string }).detail || error.message;
  } catch {
    return error.message || "操作未完成，请重试。";
  }
}

function HighlightedText({ text, items }: { text: string; items: RedactionItem[] }) {
  const visibleItems = [...items]
    .filter((item) => item.review_status !== "已移除")
    .sort((left, right) => left.start_offset - right.start_offset);
  let cursor = 0;
  const nodes: ReactNode[] = [];
  visibleItems.forEach((item) => {
    if (item.start_offset < cursor || item.end_offset > text.length) return;
    nodes.push(<Fragment key={`plain-${item.id}`}>{text.slice(cursor, item.start_offset)}</Fragment>);
    nodes.push(
      <mark
        key={item.id}
        className={item.action === "keep" ? "rounded bg-[var(--surface-subtle)] px-0.5 text-slate-600" : "rounded bg-[var(--warning-bg)] px-0.5 text-[var(--warning)]"}
        title={`${entityLabels[item.entity_type] || item.entity_type}：${actionLabels[item.action]}`}
      >
        {text.slice(item.start_offset, item.end_offset)}
      </mark>,
    );
    cursor = item.end_offset;
  });
  nodes.push(<Fragment key="tail">{text.slice(cursor)}</Fragment>);
  return <>{nodes}</>;
}

export function RedactionWorkspace({
  caseId,
  documents,
  onWorkspaceReload,
}: {
  caseId: number;
  documents: DocumentItem[];
  onWorkspaceReload: () => Promise<boolean>;
}) {
  const readableDocuments = documents.filter((item) => Boolean(item.raw_text?.trim()));
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(readableDocuments[0]?.id ?? null);
  const [records, setRecords] = useState<RedactionRecord[]>([]);
  const [selectedRecordId, setSelectedRecordId] = useState<number | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showAiText, setShowAiText] = useState(false);
  const [editingItemId, setEditingItemId] = useState<number | null>(null);
  const [manualStart, setManualStart] = useState(0);
  const [manualEnd, setManualEnd] = useState(0);
  const [manualType, setManualType] = useState("自定义敏感信息");
  const [manualReplacement, setManualReplacement] = useState("");
  const [useOriginalConfirmed, setUseOriginalConfirmed] = useState(false);
  const [riskAcknowledged, setRiskAcknowledged] = useState(false);

  const selectedDocument = readableDocuments.find((item) => item.id === selectedDocumentId) || readableDocuments[0];
  const documentRecords = useMemo(
    () => records.filter((item) => item.document_id === selectedDocument?.id).sort((left, right) => right.version - left.version),
    [records, selectedDocument?.id],
  );
  const selectedRecord = documentRecords.find((item) => item.id === selectedRecordId) || documentRecords[0];
  const groupedItems = useMemo(() => {
    const groups = new Map<string, RedactionItem[]>();
    selectedRecord?.items.forEach((item) => groups.set(item.entity_type, [...(groups.get(item.entity_type) || []), item]));
    return Array.from(groups.entries());
  }, [selectedRecord]);

  async function loadRecords() {
    try {
      const response = await api<RedactionRecord[]>(`/cases/${caseId}/redactions`);
      setRecords(response);
      return response;
    } catch (requestError) {
      setError(formatError(requestError));
      return [];
    }
  }

  useEffect(() => {
    void loadRecords();
  }, [caseId]);

  useEffect(() => {
    if (!selectedDocumentId && readableDocuments[0]) setSelectedDocumentId(readableDocuments[0].id);
  }, [readableDocuments, selectedDocumentId]);

  async function run(label: string, request: () => Promise<RedactionRecord>) {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      const record = await request();
      await loadRecords();
      await onWorkspaceReload();
      setSelectedRecordId(record.id);
      setNotice("脱敏版本已更新；原始材料未被修改。");
      return record;
    } catch (requestError) {
      setError(formatError(requestError));
      return null;
    } finally {
      setBusy("");
    }
  }

  async function detect(force = false) {
    if (!selectedDocument) return;
    if (force && selectedRecord) {
      await run("retry", () => api<RedactionRecord>(`/redactions/${selectedRecord.id}/retry`, { method: "POST" }));
      return;
    }
    await run("detect", () => api<RedactionRecord>(`/cases/${caseId}/redactions/detect`, {
      method: "POST",
      body: JSON.stringify({ document_id: selectedDocument.id, force }),
    }));
  }

  async function updateItem(item: RedactionItem, change: Record<string, unknown>) {
    if (!selectedRecord) return;
    await run(`item:${item.id}`, () => api<RedactionRecord>(`/redactions/${selectedRecord.id}/items/${item.id}`, {
      method: "PATCH",
      body: JSON.stringify(change),
    }));
    setEditingItemId(null);
  }

  async function removeItem(item: RedactionItem) {
    if (!selectedRecord || !window.confirm("确认删除这个脱敏项吗？原始文本不会被修改。")) return;
    await run(`item:${item.id}`, () => api<RedactionRecord>(`/redactions/${selectedRecord.id}/items/${item.id}`, { method: "DELETE" }));
  }

  async function addManualItem() {
    if (!selectedRecord) return;
    const result = await run("manual", () => api<RedactionRecord>(`/redactions/${selectedRecord.id}/items`, {
      method: "POST",
      body: JSON.stringify({
        start_offset: Number(manualStart),
        end_offset: Number(manualEnd),
        entity_type: manualType,
        replacement: manualReplacement,
        action: manualType === "自然人姓名" || manualType === "企业名称" ? "consistent_alias" : "full_replace",
        confidence: 1,
        rule_code: "manual",
        review_status: "已接受",
      }),
    }));
    if (result) {
      setManualStart(0);
      setManualEnd(0);
      setManualReplacement("");
    }
  }

  if (!readableDocuments.length) {
    return <div className="feedback-state border-[var(--warning)] bg-[var(--warning-bg)] text-[var(--warning)]"><FileWarning size={18} />请先上传并解析 TXT、PDF 或 DOCX 材料；只有已解析文本才能进入脱敏复核。</div>;
  }

  return (
    <section className="space-y-4" aria-label="材料脱敏工作区">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-[var(--mint-subtle)] bg-[var(--mint-subtle)] p-4">
        <div><div className="flex items-center gap-2 font-semibold text-ink"><ShieldCheck size={18} className="text-[var(--mint)]" />用户可见的材料脱敏</div><p className="mt-1 text-sm leading-6 text-slate-600">原文仅用于人工核对。确认前，不会因本步骤额外向 AI 发送任何材料。</p></div>
        <div className="flex flex-wrap gap-2">
          <select className="rounded-md border border-line bg-white px-3 py-2 text-sm" value={selectedDocument?.id || ""} onChange={(event) => { setSelectedDocumentId(Number(event.target.value)); setSelectedRecordId(null); }}>
            {readableDocuments.map((item) => <option value={item.id} key={item.id}>{item.original_filename || item.filename}</option>)}
          </select>
          <button className="button-secondary" type="button" disabled={Boolean(busy)} onClick={() => void detect(Boolean(selectedRecord))}><RefreshCw size={16} />{selectedRecord ? "重新检测" : "检测敏感项"}</button>
        </div>
      </div>

      {error && <div role="alert" className="feedback-state border-[var(--danger)] bg-[var(--danger-bg)] text-[var(--danger)]"><FileWarning size={17} />{error}</div>}
      {notice && <div role="status" className="feedback-state border-[var(--mint)] bg-[var(--mint-subtle)] text-[var(--mint)]"><ShieldCheck size={17} />{notice}</div>}

      {!selectedRecord ? (
        <div className="empty-state"><ShieldOff size={21} /><div><div className="font-medium text-ink">尚未生成脱敏检测</div><p>先检测当前材料，系统会给出敏感项、替换建议和可人工调整的预览。</p></div><button className="button-primary" type="button" disabled={Boolean(busy)} onClick={() => void detect()}>开始检测</button></div>
      ) : (
        <div className="grid min-w-0 gap-4 xl:grid-cols-[220px_minmax(0,1fr)_320px]">
          <aside className="workspace-card h-fit min-w-0">
            <div className="flex items-center justify-between"><h3 className="font-semibold text-ink">敏感项</h3><ReasoningStatusBadge status={redactionStatus(selectedRecord)} /></div>
            <p className="mt-2 text-xs leading-5 text-slate-500">D-{selectedDocument?.id} · 脱敏版本 v{selectedRecord.version}</p>
            <div className="mt-4 space-y-2">
              {groupedItems.length ? groupedItems.map(([type, items]) => <div key={type} className="rounded-md border border-line px-3 py-2"><div className="flex items-center justify-between gap-2 text-sm font-medium text-ink"><span>{entityLabels[type] || type}</span><span className="text-xs text-slate-500">{items.length}</span></div><p className="mt-1 text-xs text-slate-500">{items.filter((item) => ["已确认", "已接受"].includes(item.review_status)).length} 条已接受</p></div>) : <p className="text-sm text-slate-500">未检测到敏感项，可人工新增。</p>}
            </div>
            <button className="button-secondary mt-4 w-full" type="button" disabled={Boolean(busy)} onClick={() => void run("batch", () => api<RedactionRecord>(`/redactions/${selectedRecord.id}/items/batch-accept`, { method: "POST", body: JSON.stringify({ review_status: "已接受" }) }))}><CheckCheck size={16} />接受高置信度规则</button>
          </aside>

          <main className="workspace-card min-w-0">
            <div className="flex flex-wrap items-center justify-between gap-2"><div><h3 className="font-semibold text-ink">原始材料核对</h3><p className="mt-1 text-xs text-slate-500">高亮内容为检测项；原始材料不会被覆盖。</p></div><EntityCode kind="document" id={selectedDocument?.id || "-"} /></div>
            <div className="mt-4 max-h-[440px] overflow-auto whitespace-pre-wrap rounded-md border border-line bg-[var(--surface-subtle)] p-4 text-sm leading-7 text-slate-700"><HighlightedText text={selectedDocument?.raw_text || ""} items={selectedRecord.items} /></div>
            <div className="mt-4 space-y-3">
              {selectedRecord.items.map((item) => <RedactionItemRow key={item.id} item={item} editing={editingItemId === item.id} busy={Boolean(busy)} onEdit={() => setEditingItemId(item.id)} onCancel={() => setEditingItemId(null)} onUpdate={(change) => void updateItem(item, change)} onDelete={() => void removeItem(item)} />)}
            </div>
            <div className="mt-5 rounded-md border border-dashed border-line bg-white p-3"><div className="flex items-center gap-2 text-sm font-medium text-ink"><Plus size={16} />人工新增敏感项</div><p className="mt-1 text-xs text-slate-500">填写原文中的起止位置；位置从 0 开始，可用于姓名、地址、项目或商业秘密等补充标记。</p><div className="mt-3 grid gap-2 sm:grid-cols-2"><input className="rounded-md border border-line px-3 py-2 text-sm" type="number" min="0" value={manualStart} onChange={(event) => setManualStart(Number(event.target.value))} placeholder="开始位置" /><input className="rounded-md border border-line px-3 py-2 text-sm" type="number" min="0" value={manualEnd} onChange={(event) => setManualEnd(Number(event.target.value))} placeholder="结束位置" /><select className="rounded-md border border-line px-3 py-2 text-sm" value={manualType} onChange={(event) => setManualType(event.target.value)}>{Object.entries(entityLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><input className="rounded-md border border-line px-3 py-2 text-sm" value={manualReplacement} onChange={(event) => setManualReplacement(event.target.value)} placeholder="替换文本（可留空自动生成）" /></div><button className="button-secondary mt-3" type="button" disabled={Boolean(busy)} onClick={() => void addManualItem()}><Plus size={16} />新增敏感项</button></div>
          </main>

          <aside className="workspace-card h-fit min-w-0">
            <div className="flex items-center justify-between gap-2"><div><h3 className="font-semibold text-ink">分析副本预览</h3><p className="mt-1 text-xs text-slate-500">仅此脱敏文本可被后续 AI 输入网关使用。</p></div><span className="entity-code">R-{String(selectedRecord.version).padStart(2, "0")}</span></div>
            <div className="mt-4 space-y-2 text-sm"><SendRow label="原始材料" value="不会发送" /><SendRow label="脱敏文本" value={selectedRecord.status === "confirmed" ? "已确认，可作为后续候选输入" : "当前内容尚未发送给 AI"} good={selectedRecord.status === "confirmed"} /><SendRow label="主体映射" value="不会发送，仅保留替换别名" /><SendRow label="原始文件" value="不会发送" /></div>
            <button className="button-secondary mt-4 w-full" type="button" onClick={() => setShowAiText((value) => !value)}><Eye size={16} />{showAiText ? "收起完整内容" : "查看将发送给 AI 的完整内容"}</button>
            {showAiText && <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-[var(--surface-subtle)] p-3 text-xs leading-6 text-slate-700">{selectedRecord.redacted_text}</pre>}
            {!selectedRecord.source_current || selectedRecord.status === "superseded" ? <div className="mt-4 rounded-md bg-[var(--warning-bg)] p-3 text-sm leading-6 text-[var(--warning)]">原始解析文本已变化。当前版本不可继续作为默认分析输入，请重新检测。</div> : selectedRecord.status === "confirmed" ? <div className="mt-4 rounded-md bg-[var(--mint-subtle)] p-3 text-sm text-[var(--mint)]">已确认脱敏版本 v{selectedRecord.version}。C1 仅保存可审计选择，现有事实提取链路将在后续输入网关接入时切换。</div> : <><button className="button-primary mt-4 w-full" type="button" disabled={Boolean(busy)} onClick={() => void run("confirm", () => api<RedactionRecord>(`/redactions/${selectedRecord.id}/confirm`, { method: "POST", body: JSON.stringify({ use_original: false }) }))}><ShieldCheck size={16} />确认脱敏版本</button><p className="mt-2 text-xs leading-5 text-slate-500">确认前，当前内容尚未发送给 AI。</p></>}
            <details className="mt-4 border-t border-line pt-3"><summary className="cursor-pointer text-sm font-medium text-[var(--danger)]">使用原文分析（高风险）</summary><p className="mt-2 text-xs leading-5 text-slate-600">仅适用于虚构、公开或已自行脱敏的材料。本确认会被记录，但 C1 不会自动重跑现有 AI 流程。</p><label className="mt-2 flex gap-2 text-xs text-slate-700"><input type="checkbox" checked={useOriginalConfirmed} onChange={(event) => setUseOriginalConfirmed(event.target.checked)} />材料为虚构或已自行脱敏</label><label className="mt-2 flex gap-2 text-xs text-slate-700"><input type="checkbox" checked={riskAcknowledged} onChange={(event) => setRiskAcknowledged(event.target.checked)} />我了解原文可能进入后续 AI 分析</label><button className="button-secondary mt-3 w-full text-[var(--danger)]" type="button" disabled={Boolean(busy) || !useOriginalConfirmed || !riskAcknowledged} onClick={() => void run("original", () => api<RedactionRecord>(`/redactions/${selectedRecord.id}/confirm`, { method: "POST", body: JSON.stringify({ use_original: true, original_material_confirmed: useOriginalConfirmed, risk_acknowledged: riskAcknowledged }) }))}>确认使用原文分析</button></details>
          </aside>
        </div>
      )}
    </section>
  );
}

function SendRow({ label, value, good = false }: { label: string; value: string; good?: boolean }) {
  return <div className="rounded-md border border-line bg-white px-3 py-2"><div className="text-xs text-slate-500">{label}</div><div className={good ? "mt-1 text-xs font-medium text-[var(--mint)]" : "mt-1 text-xs text-slate-700"}>{value}</div></div>;
}

function RedactionItemRow({
  item,
  editing,
  busy,
  onEdit,
  onCancel,
  onUpdate,
  onDelete,
}: {
  item: RedactionItem;
  editing: boolean;
  busy: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onUpdate: (change: Record<string, unknown>) => void;
  onDelete: () => void;
}) {
  const [replacement, setReplacement] = useState(item.replacement);
  const [entityType, setEntityType] = useState(item.entity_type);
  const [action, setAction] = useState<RedactionAction>(item.action);
  useEffect(() => { setReplacement(item.replacement); setEntityType(item.entity_type); setAction(item.action); }, [item]);
  return <div className="rounded-md border border-line bg-white p-3"><div className="flex flex-wrap items-center justify-between gap-2"><div className="flex flex-wrap items-center gap-2"><span className="font-medium text-ink">{entityLabels[item.entity_type] || item.entity_type}</span><span className="status-badge status-ai">{Math.round(item.confidence * 100)}%</span><span className="text-xs text-slate-500">{actionLabels[item.action]}</span></div><div className="flex gap-2">{!editing && <><button className="button-secondary px-2 py-1" type="button" disabled={busy} onClick={() => onUpdate({ review_status: "已接受" })}>接受</button><button className="button-secondary px-2 py-1" type="button" disabled={busy} onClick={() => onUpdate({ action: "keep", review_status: "已保留" })}>保留</button><button className="button-secondary px-2 py-1" type="button" disabled={busy} onClick={onEdit}><Pencil size={14} /></button><button className="button-secondary px-2 py-1 text-[var(--danger)]" type="button" disabled={busy} onClick={onDelete}><Trash2 size={14} /></button></>}{editing && <><button className="button-secondary px-2 py-1" type="button" onClick={onCancel}>取消</button><button className="button-primary px-2 py-1" type="button" disabled={busy} onClick={() => onUpdate({ entity_type: entityType, replacement, action, review_status: "已接受" })}>保存</button></>}</div></div>{editing ? <div className="mt-3 grid gap-2 sm:grid-cols-3"><select className="rounded-md border border-line px-2 py-1.5 text-xs" value={entityType} onChange={(event) => setEntityType(event.target.value)}>{Object.entries(entityLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><select className="rounded-md border border-line px-2 py-1.5 text-xs" value={action} onChange={(event) => setAction(event.target.value as RedactionAction)}>{Object.entries(actionLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><input className="rounded-md border border-line px-2 py-1.5 text-xs" value={replacement} onChange={(event) => setReplacement(event.target.value)} /></div> : <p className="mt-2 text-xs text-slate-600">替换为：<span className="font-medium text-ink">{item.replacement}</span> · 状态：{item.review_status}</p>}</div>;
}
