import type { LucideIcon } from "lucide-react";
import { AlertTriangle, Inbox } from "lucide-react";

export function Card({ label, value }: { label: string; value: string }) {
  return <div className="card"><p>{label}</p><div><b>{value}</b></div></div>;
}

type StateAction = {
  label: string;
  onClick: () => void;
};

type EmptyStateProps = {
  title: string;
  description: string;
  icon?: LucideIcon;
  action?: StateAction;
  secondaryAction?: StateAction;
  note?: string;
  compact?: boolean;
  className?: string;
};

/** A shared, accessible state pattern for authenticated product screens. */
export function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
  action,
  secondaryAction,
  note,
  compact = false,
  className = "",
}: EmptyStateProps) {
  return <section className={`app-state app-state-empty${compact ? " is-compact" : ""}${className ? ` ${className}` : ""}`}>
    <span className="app-state-illustration" aria-hidden="true"><Icon /></span>
    <div className="app-state-copy">
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
    {(action || secondaryAction) && <div className="app-state-actions">
      {action && <button type="button" className="app-state-primary" onClick={action.onClick}>{action.label}</button>}
      {secondaryAction && <button type="button" className="app-state-secondary" onClick={secondaryAction.onClick}>{secondaryAction.label}</button>}
    </div>}
    {note && <small className="app-state-note">{note}</small>}
  </section>;
}

export function ErrorState({
  title = "Không thể tải dữ liệu",
  description,
  retry,
  compact = false,
}: {
  title?: string;
  description: string;
  retry?: () => void;
  compact?: boolean;
}) {
  return <section className={`app-state app-state-error${compact ? " is-compact" : ""}`} role="alert">
    <span className="app-state-illustration" aria-hidden="true"><AlertTriangle /></span>
    <div className="app-state-copy"><h3>{title}</h3><p>{description}</p></div>
    {retry && <div className="app-state-actions"><button type="button" className="app-state-primary" onClick={retry}>Thử lại</button></div>}
  </section>;
}

export function StateSkeleton({ rows = 3, compact = false, label = "Đang tải dữ liệu" }: { rows?: number; compact?: boolean; label?: string }) {
  return <div className={`app-state-skeleton${compact ? " is-compact" : ""}`} role="status" aria-label={label}>
    {Array.from({ length: rows }, (_, index) => <div className="app-state-skeleton-row" key={index} aria-hidden="true">
      <span />
      <div><i /><i /></div>
    </div>)}
  </div>;
}

export function State({ text, error = false }: { text: string; error?: boolean }) {
  const cleanText = text.replace(/\s+trong database/gi, "");
  if (/^Đang tải/i.test(cleanText)) return <StateSkeleton compact label={cleanText} />;
  if (error) return <ErrorState compact description={cleanText} />;
  return <EmptyState compact title={cleanText} description="Dữ liệu mới sẽ xuất hiện tại đây khi có cập nhật." />;
}
