import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { listAccounts } from "../api/accounts";
import { getConfig } from "../api/config";
import { listServices } from "../api/services";
import { listTasks } from "../api/tasks";
import type { Account, ConfigResponse, Task } from "../api/types";
import type { usePrimeBbWebSocket } from "../api/websocket";
import { Badge, statusTone } from "../components/Badge";
import { Card } from "../components/Card";

export function DashboardHome() {
  const live = useOutletContext<ReturnType<typeof usePrimeBbWebSocket>>();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [services, setServices] = useState<string[]>([]);
  const [config, setConfig] = useState<ConfigResponse | null>(null);

  useEffect(() => {
    listAccounts({ page_size: 200 }).then((data) => setAccounts(data.items)).catch(() => setAccounts([]));
    listTasks().then(setTasks).catch(() => setTasks([]));
    listServices().then((data) => setServices(data.items)).catch(() => setServices([]));
    getConfig().then(setConfig).catch(() => setConfig(null));
  }, []);

  const mergedTasks = useMemo(() => {
    const map = new Map(tasks.map((task) => [task.id, task]));
    Object.values(live.tasks).forEach((task) => map.set(task.id, task));
    return Array.from(map.values());
  }, [tasks, live.tasks]);

  const runningTasks = mergedTasks.filter((task) => task.status === "running").length;
  const manualAccounts = accounts.filter((account) => account.status === "manual_required").length;

  return (
    <div className="page-stack">
      <div className="page-heading">
        <h1>Dashboard</h1>
        <p>Overview of the PrimeBB tool suite and shared automation infrastructure.</p>
      </div>
      <div className="stats-grid">
        <Card><div className="stat"><span>Accounts</span><strong>{accounts.length}</strong></div></Card>
        <Card><div className="stat"><span>Manual required</span><strong>{manualAccounts}</strong></div></Card>
        <Card><div className="stat"><span>Running tasks</span><strong>{runningTasks}</strong></div></Card>
        <Card><div className="stat"><span>Services</span><strong>{services.length}</strong></div></Card>
      </div>
      <div className="grid-two">
        <Card title="Runtime" description="Backend configuration summary.">
          <dl className="detail-list">
            <dt>BitBrowser</dt><dd>{config?.bitbrowser_url || "Unavailable"}</dd>
            <dt>Proxy</dt><dd>{config ? `${config.proxy_host}:${config.proxy_port}` : "Unavailable"}</dd>
            <dt>ipdata</dt><dd>{config?.ipdata_configured ? "Configured" : "Not configured"}</dd>
          </dl>
        </Card>
        <Card title="Recent task state" description="Live task updates merge into this list.">
          <div className="list-stack">
            {mergedTasks.slice(0, 5).map((task) => (
              <div className="list-row" key={task.id}>
                <div><strong>{task.id}</strong><small>{task.type}</small></div>
                <Badge tone={statusTone(task.status)}>{task.status}</Badge>
              </div>
            ))}
            {!mergedTasks.length && <p>No tasks yet.</p>}
          </div>
        </Card>
      </div>
    </div>
  );
}
