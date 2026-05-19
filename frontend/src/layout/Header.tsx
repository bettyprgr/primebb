import { Badge } from "../components/Badge";

export function Header({ connected }: { connected: boolean }) {
  return (
    <header className="topbar">
      <div />
      <Badge tone={connected ? "success" : "warning"}>{connected ? "WebSocket connected" : "WebSocket offline"}</Badge>
    </header>
  );
}
