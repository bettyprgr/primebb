import { Badge } from "../components/Badge";

export function Header({ connected }: { connected: boolean }) {
  return (
    <header className="topbar">
      <div>
        <h1>PrimeBB Dashboard</h1>
        <p>Shared BitBrowser infrastructure with modular automation tools.</p>
      </div>
      <Badge tone={connected ? "success" : "warning"}>{connected ? "WebSocket connected" : "WebSocket offline"}</Badge>
    </header>
  );
}
