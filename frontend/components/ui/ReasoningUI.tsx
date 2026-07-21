"use client";

import type { ReactNode } from "react";
import { AlertCircle, Inbox, Loader2 } from "lucide-react";
import {
  formatEntityCode,
  normalizeProductStatus,
  productStatusMeta,
  type EntityKind,
  type ProductStatus,
} from "@/lib/ui-config";

export function EntityCode({ kind, id, className = "" }: { kind: EntityKind; id: number | string; className?: string }) {
  return <span className={`entity-code ${className}`}>{formatEntityCode(kind, id)}</span>;
}

export function ReasoningStatusBadge({ status, label }: { status: ProductStatus | string; label?: string }) {
  const normalized = status in productStatusMeta ? status as ProductStatus : normalizeProductStatus(status) || "unavailable";
  const meta = productStatusMeta[normalized];
  return <span className={`status-badge ${meta.className}`}>{label || meta.label}</span>;
}

export function PageHeading({ eyebrow, title, description, action }: { eyebrow?: string; title?: string; description: string; action?: ReactNode }) {
  return (
    <header className="page-heading">
      <div className="min-w-0">
        {eyebrow && <div className="page-eyebrow">{eyebrow}</div>}
        {title && <h1>{title}</h1>}
        <p>{description}</p>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  );
}

export function LoadingState({ label = "正在读取推理数据" }: { label?: string }) {
  return <div className="feedback-state"><Loader2 className="animate-spin text-court" size={18} /><span>{label}</span></div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="feedback-state border-rose-200 bg-rose-50 text-rose-800"><AlertCircle size={18} /><span className="flex-1">{message}</span>{onRetry && <button className="button-secondary" onClick={onRetry}>重新加载</button>}</div>;
}

export function EmptyReasoningState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="empty-state"><Inbox size={20} /><div><div className="font-medium text-ink">{title}</div><p>{description}</p></div>{action}</div>;
}
