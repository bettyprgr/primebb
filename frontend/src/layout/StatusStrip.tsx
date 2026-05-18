import type { LiveLog } from "../api/websocket";
import { Badge } from "../components/Badge";

export function StatusStrip({ logs }: { logs: LiveLog[] }) {
  return (
    <div className="status-strip">
      <Badge tone="info">Live activity</Badge>
      <span>{logs[0]?.message || "Waiting for task events"}</span>
    </div>
  );
}
