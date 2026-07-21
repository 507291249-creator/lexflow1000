import type { DocumentItem } from "@/lib/api";

export function SourceExcerptViewer({ document }: { document?: DocumentItem }) {
  if (!document) return <div className="rounded-md border border-dashed border-line px-4 py-6 text-center text-sm text-slate-500">选择材料后查看已解析文本。</div>;
  return (
    <section className="rounded-md border border-line bg-[var(--surface-subtle)] p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="truncate text-sm font-semibold text-ink">{document.original_filename || document.filename}</h3>
        <span className="badge shrink-0 bg-white text-slate-500">{document.file_type?.toUpperCase() || "文件"}</span>
      </div>
      <p className="mt-3 max-h-56 overflow-y-auto whitespace-pre-wrap text-xs leading-6 text-slate-600">
        {document.raw_text || "该材料尚无可用解析文本。"}
      </p>
    </section>
  );
}
