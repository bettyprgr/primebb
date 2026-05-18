import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { createAmazonTask, deleteAmazonAccount, importPhones, listAmazonAccounts } from "../../api/amazon";
import type { AmazonAccount } from "../../api/amazon";
import type { usePrimeBbWebSocket } from "../../api/websocket";
import { Badge, statusTone } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Field, Textarea, TextInput } from "../../components/Field";

type Phase = "idle" | "running" | "done";

export function AmazonCreationWorkspace() {
  const live = useOutletContext<ReturnType<typeof usePrimeBbWebSocket>>();

  const [phonesText, setPhonesText] = useState("");
  const [proxiesText, setProxiesText] = useState("");
  const [templateBrowserId, setTemplateBrowserId] = useState("");
  const [concurrency, setConcurrency] = useState(1);
  const [phase, setPhase] = useState<Phase>("idle");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [importedIds, setImportedIds] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<AmazonAccount[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  function loadAccounts() {
    listAmazonAccounts().then((d) => setAccounts(d.items)).catch(() => {});
  }

  useEffect(() => { loadAccounts(); }, []);

  // Poll accounts while running, refresh on done
  useEffect(() => {
    if (phase !== "running") return;
    const interval = setInterval(loadAccounts, 5000);
    return () => clearInterval(interval);
  }, [phase]);

  // Detect task completion
  useEffect(() => {
    if (!taskId || phase !== "running") return;
    const task = live.tasks[taskId];
    if (!task) return;
    const terminal = ["completed", "failed", "partial_manual_required", "cancelled"];
    if (!terminal.includes(task.status)) return;
    loadAccounts();
    setPhase("done");
  }, [live.tasks, taskId, phase]);

  const filteredLogs = taskId ? live.logs.filter((l) => l.task_id === taskId) : [];
  const task = taskId ? live.tasks[taskId] : null;

  async function run() {
    setError(null);
    const lines = phonesText.trim().split("\n").filter((l) => l.trim() && !l.trim().startsWith("#"));
    if (!lines.length) { setError("No phones entered."); return; }
    const proxyLines = proxiesText.trim().split("\n").filter((l) => l.trim());
    if (proxyLines.length > 0 && proxyLines.length !== lines.length) {
      setError(`Proxy count (${proxyLines.length}) must match phone count (${lines.length}).`);
      return;
    }
    try {
      const imported = await importPhones(phonesText);
      if (!imported.account_ids.length) {
        setError(imported.errors.length ? imported.errors.join("; ") : "No phones imported.");
        return;
      }
      setImportedIds(imported.account_ids);
      const created = await createAmazonTask(imported.account_ids, templateBrowserId || null, concurrency, proxyLines.length ? proxyLines : []);
      setTaskId(created.id);
      setPhase("running");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  function reset() {
    setPhase("idle");
    setTaskId(null);
    setImportedIds([]);
    setError(null);
    setPhonesText("");
    setProxiesText("");
  }

  function toggleSelect(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (selected.size === accounts.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(accounts.map((a) => a.id)));
    }
  }

  async function deleteSelected() {
    if (!selected.size) return;
    await Promise.all(Array.from(selected).map((id) => deleteAmazonAccount(id).catch(() => {})));
    setSelected(new Set());
    loadAccounts();
  }

  return (
    <div className="page-stack">
      <div className="page-heading">
        <h1>Amazon Creation</h1>
        <p>Register Amazon accounts via phone number and SMS OTP.</p>
      </div>

      <div className="grid-two">
        {/* Left: launch panel */}
        <Card title="Launch" description="Paste phone list and start.">
          {phase === "idle" && (
            <>
              <div className="form-grid" style={{ gridTemplateColumns: "repeat(2, minmax(0,1fr))" }}>
                <Field label="Concurrency">
                  <TextInput type="number" min={1} max={3} value={concurrency} onChange={(e) => setConcurrency(Number(e.target.value))} />
                </Field>
                <Field label="Template browser ID">
                  <TextInput value={templateBrowserId} onChange={(e) => setTemplateBrowserId(e.target.value)} placeholder="optional" />
                </Field>
              </div>
              <div className="sp-full-fields">
                <Field label="SOCKS5 proxies — one per line, must match phone count">
                  <Textarea
                    value={proxiesText}
                    onChange={(e) => setProxiesText(e.target.value)}
                    placeholder={"user:pass@host:port\nuser2:pass2@host:port"}
                    style={{ minHeight: 100, fontFamily: "monospace", fontSize: 13 }}
                  />
                </Field>
                <Field label="Phones — one per line: phone|sms_url">
                  <Textarea
                    value={phonesText}
                    onChange={(e) => setPhonesText(e.target.value)}
                    placeholder={"5136634109|https://sms222.us?token=abc123\n5139876543|https://sms222.us?token=xyz456"}
                    style={{ minHeight: 180, fontFamily: "monospace", fontSize: 13 }}
                  />
                </Field>
              </div>
              <div className="form-actions">
                <Button onClick={run} disabled={!phonesText.trim()}>Start Creation</Button>
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
                    <Badge>{task.status}</Badge>
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
              <p style={{ color: "#86efac", margin: 0 }}>Task completed. See results in the table.</p>
              <div className="form-actions">
                <Button onClick={reset}>Run again</Button>
              </div>
            </div>
          )}
        </Card>

        {/* Right: results table */}
        <Card
          title="Accounts"
          description={`${accounts.length} total`}
          actions={
            selected.size > 0
              ? <Button className="button-danger-ghost" onClick={deleteSelected}>Delete {selected.size}</Button>
              : undefined
          }
        >
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th><input type="checkbox" checked={accounts.length > 0 && selected.size === accounts.length} onChange={toggleAll} /></th>
                  <th>Phone</th>
                  <th>Name</th>
                  <th>Password</th>
                  <th>Region</th>
                  <th>Status</th>
                  <th>Last checked</th>
                </tr>
              </thead>
              <tbody>
                {accounts.length === 0 && (
                  <tr><td colSpan={7} style={{ color: "#94a3b8", textAlign: "center" }}>No accounts yet</td></tr>
                )}
                {accounts.map((a) => (
                  <tr key={a.id} className={selected.has(a.id) ? "row-selected" : ""}>
                    <td><input type="checkbox" checked={selected.has(a.id)} onChange={() => toggleSelect(a.id)} /></td>
                    <td style={{ fontFamily: "monospace" }}>{a.phone}</td>
                    <td>{a.name ?? <span style={{ color: "#64748b" }}>—</span>}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>{a.password ?? <span style={{ color: "#64748b" }}>—</span>}</td>
                    <td>{a.proxy_region ?? <span style={{ color: "#64748b" }}>—</span>}</td>
                    <td><Badge tone={statusTone(a.status)}>{a.status}</Badge></td>
                    <td style={{ color: "#94a3b8", fontSize: 12 }}>{a.last_checked_at ? a.last_checked_at.slice(0, 16) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
