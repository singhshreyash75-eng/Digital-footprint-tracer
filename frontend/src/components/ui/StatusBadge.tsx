type StatusBadgeProps = {
  children: string;
  status?: "idle" | "active" | "success" | "warning";
};

export default function StatusBadge({
  children,
  status = "idle",
}: StatusBadgeProps) {
  return (
    <span className={`status-badge status-badge--${status}`}>
      <span className="status-badge__dot" />
      {children}
    </span>
  );
}