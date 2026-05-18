import { Outlet } from "react-router-dom";
import { usePrimeBbWebSocket } from "../api/websocket";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { StatusStrip } from "./StatusStrip";

export function DashboardLayout() {
  const live = usePrimeBbWebSocket();

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-shell">
        <Header connected={live.connected} />
        <StatusStrip logs={live.logs} />
        <main className="content">
          <Outlet context={live} />
        </main>
      </div>
    </div>
  );
}
