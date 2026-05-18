import { useEffect, useState } from "react";
import { importAccounts, listAccounts } from "../../api/accounts";
import { listServices } from "../../api/services";
import { cancelTask, createTask } from "../../api/tasks";
import type { Account, TaskCreateRequest, TaskType } from "../../api/types";
import type { usePrimeBbWebSocket } from "../../api/websocket";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Field, Select, Textarea, TextInput } from "../../components/Field";

type Phase = "idle" | "running" | "done";

export function SocialPumperRunForm({ live }: { live: ReturnType<typeof usePrimeBbWebSocket> }) {
  const [accountsText, setAccountsText] = useState("");
  const [proxiesText, setProxiesText] = useState("");
  const [services, setServices] = useState<string[]>([]);
  const [selectedServices, setSelectedServices] = useState<string[]>([]);
  const [operation, setOperation] = useState<TaskType>("login_all_services");
  const [concurrency, setConcurrency] = useState(1);
  const [closeAfter, setCloseAfter] = useState(false);
  const [templateBrowserId, setTemplateBrowserId] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [importedIds, setImportedIds] = useState<number[]>([]);
  const [results, setResults] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listServices()
      .then((data) => { setServices(data.items); setSelectedServices(data.items); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!taskId || phase !== "running") return;
    const task = live.tasks[taskId];
    if (!task) return;
    const terminal = ["completed", "failed", "partial_manual_required", "cancelled"];
    if (!terminal.includes(task.status)) return;
    listAccounts({ page_size: 200 })
      .then((data) => {
        const ids = new Set(importedIds);
        const relevant = data.items.filter((a: Account) => ids.has(a.id));
        setResults(relevant.map((a: Account) => `${a.email}|${a.status}|${a.message ?? ""}`).join("\n"));
        setPhase("done");
      })
      .catch(() => setPhase("done"));
  }, [live.tasks, taskId, phase, importedIds]);

  const filteredLogs = taskId ? live.logs.filter((log) => log.task_id === taskId) : [];
  const task = taskId ? live.tasks[taskId] : null;

  function toggleService(service: string) {
    setSelectedServices((prev) => prev.includes(service) ? prev.filter((s) => s !== service) : [...prev, service]);
  }

  async function run() {
    setError(null);
    const accountLines = accountsText.trim().split("\n").filter((l) => l.trim() && !l.trim().startsWith("#"));
    if (!accountLines.length) { setError("No accounts entered."); return; }

    const proxyLines = proxiesText.trim().split("\n").filter((l) => l.trim());
    if (proxyLines.length > 0 && proxyLines.length !== accountLines.length) {
      setError(`Proxy count (${proxyLines.length}) must match account count (${accountLines.length}).`);
      return;
    }

    try {
      const imported = await importAccounts(accountsText);
      if (!imported.account_ids.length) {
        setError(imported.errors.length ? imported.errors.join("; ") : "No accounts imported.");
        return;
      }
      setImportedIds(imported.account_ids);
      const payload: TaskCreateRequest = {
        type: operation,
        account_ids: imported.account_ids,
        services: operation === "login_gmail" ? [] : selectedServices,
        concurrency,
        close_after: closeAfter,
        template_browser_id: templateBrowserId || null,
        proxy_urls: proxyLines.length ? proxyLines : undefined,
      };
      const created = await createTask(payload);
      setTaskId(created.id);
      setPhase("running");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function stop() {
    if (!taskId) return;
    try {
      await cancelTask(taskId);
    } catch {
      // ignore
    }
  }

  function reset() {
    setPhase("idle");
    setTaskId(null);
    setImportedIds([]);
    setResults("");
    setError(null);
  }

  return (
    <Card title="Run Social Pumper" description="Paste accounts, set proxy, and start.">
      {phase === "idle" && (
        <>
          <div className="form-grid">
            <Field label="Operation">
              <Select value={operation} onChange={(e) => setOperation(e.target.value as TaskType)}>
                <option value="login_gmail">Authenticate Gmail</option>
                <option value="login_service">Connect selected services</option>
                <option value="login_all_services">Connect all supported services</option>
              </Select>
            </Field>
            <Field label="Concurrency">
              <TextInput type="number" min={1} max={3} value={concurrency} onChange={(e) => setConcurrency(Number(e.target.value))} />
            </Field>
            <Field label="Template browser ID">
              <TextInput value={templateBrowserId} onChange={(e) => setTemplateBrowserId(e.target.value)} placeholder="optional" />
            </Field>
            <label className="checkbox">
              <input type="checkbox" checked={closeAfter} onChange={(e) => setCloseAfter(e.target.checked)} />
              Close browser after success
            </label>
          </div>
          <div className="sp-full-fields">
            <Field label="SOCKS5 proxies — one per line, must match account count">
              <Textarea
                value={proxiesText}
                onChange={(e) => setProxiesText(e.target.value)}
                placeholder={"user:pass@host:port\nuser2:pass2@host:port"}
                style={{ minHeight: 120, fontFamily: "monospace", fontSize: 13 }}
              />
            </Field>
            <Field label="Accounts — one per line: email|password|recovery_email|totp_secret|account_year|country">
              <Textarea
                value={accountsText}
                onChange={(e) => setAccountsText(e.target.value)}
                placeholder={"user@gmail.com|password|recovery@gmail.com|TOTP_SECRET|2023|US\nuser2@gmail.com|password2|||2022|US"}
                style={{ minHeight: 200, fontFamily: "monospace", fontSize: 13 }}
              />
            </Field>
          </div>
          {operation !== "login_gmail" && (
            <div className="chooser-block">
              <h3>Services</h3>
              <div className="pill-grid">
                {services.map((service) => (
                  <button
                    key={service}
                    className={selectedServices.includes(service) ? "pill selected" : "pill"}
                    onClick={() => toggleService(service)}
                  >
                    {service}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="form-actions">
            <Button onClick={run} disabled={!accountsText.trim()}>Start Social Pumper</Button>
          </div>
          {error && <p className="error-text">{error}</p>}
        </>
      )}

      {phase === "running" && (
        <div className="sp-running">
          {task && (
            <div className="task-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong>Task {task.id}</strong>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span className="badge">{task.status}</span>
                  <Button className="button-ghost" onClick={stop}>Stop</Button>
                </div>
              </div>
              <div className="progress">
                <span style={{ width: task.total ? `${Math.round(((task.completed + task.failed + task.manual_required) / task.total) * 100)}%` : "0%" }} />
              </div>
              <div className="task-stats">
                <span>{task.completed} done</span>
                <span>{task.failed} failed</span>
                <span>{task.manual_required} manual</span>
                <span>{task.total} total</span>
              </div>
            </div>
          )}
          <div className="log-list sp-log-scroll">
            {filteredLogs.length
              ? filteredLogs.map((log) => (
                  <div key={log.id}><span className="badge">{log.level}</span><span>{log.message}</span></div>
                ))
              : <p style={{ color: "#94a3b8", margin: 0 }}>Waiting for logs…</p>}
          </div>
        </div>
      )}

      {phase === "done" && (
        <div className="sp-done">
          <p style={{ color: "#86efac", margin: 0 }}>Task completed. Copy results below.</p>
          <Field label="Results — email|status|message">
            <Textarea
              readOnly
              value={results}
              style={{ minHeight: 200, fontFamily: "monospace", fontSize: 13 }}
              onClick={(e) => (e.target as HTMLTextAreaElement).select()}
            />
          </Field>
          <div className="form-actions">
            <Button onClick={reset}>Run again</Button>
          </div>
        </div>
      )}
    </Card>
  );
}
