import { type ReactNode } from "react";

/**
 * Pure presentational primitives for the case workspace.
 *
 * No state, no API calls, no workflow logic, no business fields.
 * Every prop (action, children, business strings) is passed through verbatim.
 * Use only where it genuinely improves consistency and readability.
 */

export function WorkspaceCard({
  children,
  className = "",
  as: Tag = "article",
}: {
  children: ReactNode;
  className?: string;
  as?: "article" | "section" | "div";
}) {
  return <Tag className={`workspace-card ${className}`}>{children}</Tag>;
}

export function SectionHeader({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-header">
      <div className="min-w-0">
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/**
 * VersionChip renders a real version marker derived from backend data.
 * `tone="court"` highlights the active/current version axis (fact/issue).
 * Never fabricated — caller passes actual version numbers.
 */
export function VersionChip({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string | number;
  tone?: "default" | "court";
}) {
  return (
    <span className={`version-chip ${tone === "court" ? "version-chip-court" : ""}`}>
      <span className="text-slate-400">{label}</span>
      <span className="font-semibold">{value}</span>
    </span>
  );
}

/**
 * SourceTag renders provenance — source document name or "案件输入".
 * Caller supplies the real source_document value; nothing is invented.
 */
export function SourceTag({ children }: { children: ReactNode }) {
  return <span className="source-tag">{children}</span>;
}
