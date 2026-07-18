import { FileText } from "lucide-react";

export type CitationItem = {
  id: string;
  title: string;
  meta?: string;
};

export function CitationList({ items, emptyText }: { items: CitationItem[]; emptyText: string }) {
  if (!items.length) return <p className="text-sm leading-6 text-slate-500">{emptyText}</p>;
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={item.id} className="flex items-start gap-2 rounded-md border border-line px-3 py-2">
          <FileText className="mt-0.5 shrink-0 text-court" size={15} />
          <div className="min-w-0">
            <div className="text-sm leading-5 text-ink">{item.title}</div>
            {item.meta && <div className="mt-1 text-xs text-slate-500">{item.meta}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}
