import { Outlet } from "react-router-dom";
import { usePrimeBbWebSocket } from "../api/websocket";
import { Sidebar } from "./Sidebar";

export function DashboardLayout() {
  const live = usePrimeBbWebSocket();

  return (
    <div className="app-shell">
      <Sidebar connected={live.connected} />
      <div className="main-shell">
        <main className="content">
          <Outlet context={live} />
        </main>
      </div>
    </div>
  );
}

