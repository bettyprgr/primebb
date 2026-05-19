type BadgeProps = {
  children: React.ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
  style?: React.CSSProperties;
};

export function Badge({ children, tone = "neutral", style }: BadgeProps) {
  return <span className={`badge badge-${tone}`} style={style}>{children}</span>;
}

export function statusTone(status?: string): BadgeProps["tone"] {
  if (!status) return "neutral";
  if (["success", "completed", "google_authenticated", "created", "active"].includes(status)) return "success";
  if (["manual_required", "partial_manual_required", "running", "pending"].includes(status)) return "warning";
  if (["failed", "error", "invalid_credentials", "locked", "suspended"].includes(status)) return "danger";
  if (["cancelled", "partial_cancelled"].includes(status)) return "neutral";
  return "info";
}
