"use client";

import type { ChangeEvent } from "react";
import { Download, FileText, FileUp, Trash2 } from "lucide-react";
import type { CaseFact, DocumentItem } from "@/lib/api";
import { EntityCode, ReasoningStatusBadge } from "@/components/ui/ReasoningUI";
import { RedactionWorkspace } from "./RedactionWorkspace";
import { EmptyState, PanelHeading, StatusBadge } from "./shared";

function formatFileSize(size: number | null) {
  if (!size) return "未知大小";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

const documentStatusLabel: Record<string, string> = {
  uploaded: "已上传",
  parsing: "解析中",
  parsed: "已解析",
  analyzing: "分析中",
  ready: "已完成",
  parse_failed: "解析失败",
  analysis_failed: "分析失败",
};

export function MaterialsPanel({
  caseId,
  documents,
  facts,
  busy,
  onUpload,
  onDownload,
  onDelete,
  onWorkspaceReload,
}: {
  caseId: number;
  documents: DocumentItem[];
  facts: CaseFact[];
  busy: string;
  onUpload: (event: ChangeEvent<HTMLInputElement>) => void;
  onDownload: (item: DocumentItem) => void;
  onDelete: (item: DocumentItem) => void;
  onWorkspaceReload: () => Promise<boolean>;
}) {
  return (
    <section className="space-y-5">
      <PanelHeading
        title="材料与脱敏"
        description="原始材料与脱敏分析副本独立保存。确认脱敏后，后续输入网关可使用副本；现有事实流程保持不变。"
        action={
          <label className="button-secondary cursor-pointer">
            <FileUp size={16} />
            {busy === "upload" ? "正在上传" : "上传材料"}
            <input className="hidden" type="file" accept=".txt,.pdf,.docx" onChange={onUpload} />
          </label>
        }
      />

      {!documents.length ? (
        <EmptyState title="暂无案件材料" description="上传 PDF、DOCX 或 TXT 后，文件及解析状态会显示在这里。" />
      ) : (
        <div className="space-y-3">
          {documents.map((item) => {
            const legacy = item.storage_provider === "legacy_local";
            const sourceName = item.original_filename || item.filename;
            const citations = facts.filter((fact) => fact.source_document === sourceName || fact.source_document === item.filename).length;
            const status = documentStatusLabel[item.processing_status] || (item.raw_text ? "已完成" : "待处理");
            return (
              <article key={item.id} className="reasoning-card">
                <div className="flex flex-wrap items-start gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-slate-100 text-court"><FileText size={19} /></span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="truncate font-semibold text-ink">{sourceName}</h3>
                      <EntityCode kind="document" id={item.id} />
                      <StatusBadge status={status} />
                    </div>
                    <p className="mt-1 text-sm text-slate-600">{item.mime_type || item.file_type || "未知类型"} · {formatFileSize(item.file_size)} · 上传于 {new Date(item.uploaded_at).toLocaleString("zh-CN")}</p>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                      <span>事实引用 {citations} 次</span>
                      <span>{item.raw_text ? `已解析 ${item.raw_text.length} 字符` : "尚无可用解析文本"}</span>
                      {legacy && <span className="text-amber-700">旧材料：原始文件可能已不可用，已保留解析文本。</span>}
                      {item.extraction_error && <span className="text-rose-700">解析提示：{item.extraction_error}</span>}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {!legacy && <button className="button-secondary px-2.5 py-2" type="button" title="下载材料" disabled={Boolean(busy)} onClick={() => onDownload(item)}><Download size={16} /></button>}
                    <button className="button-secondary px-2.5 py-2 text-rose-700" type="button" title="删除材料" disabled={Boolean(busy)} onClick={() => onDelete(item)}><Trash2 size={16} /></button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      <div className="border-t border-line pt-5">
        <RedactionWorkspace caseId={caseId} documents={documents} onWorkspaceReload={onWorkspaceReload} />
      </div>
      <div className="flex items-center gap-2 text-xs text-slate-500"><ReasoningStatusBadge status="unavailable" />现有事实提取尚未改为强制读取脱敏副本；本步骤先完成用户可见、可修改、可审计的确认闭环。</div>
    </section>
  );
}
