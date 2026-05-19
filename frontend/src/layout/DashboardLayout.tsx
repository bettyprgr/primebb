import { Outlet } from "react-router-dom";
import { usePrimeBbWebSocket } from "../api/websocket";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export function DashboardLayout() {
  const live = usePrimeBbWebSocket();

  return (
    <div className="app-shell">
      <Sidebar connected={live.connected} />
      <div className="main-shell">
        <Header />
        <main className="content">
          <Outlet context={live} />
        </main>
      </div>
    </div>
  );
}

