import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { createAmazonTask, importPhones, listAmazonAccounts } from "../../api/amazon";
import type { AmazonAccount } from "../../api/amazon";
import type { usePrimeBbWebSocket } from "../../api/websocket";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Field, Textarea, TextInput } from "../../components/Field";

const STATE_ABBREV: Record<string, string> = {
  Alabama: "AL", Alaska: "AK", Arizona: "AZ", Arkansas: "AR", California: "CA",
  Colorado: "CO", Connecticut: "CT", Delaware: "DE", Florida: "FL", Georgia: "GA",
  Hawaii: "HI", Idaho: "ID", Illinois: "IL", Indiana: "IN", Iowa: "IA",
  Kansas: "KS", Kentucky: "KY", Louisiana: "LA", Maine: "ME", Maryland: "MD",
  Massachusetts: "MA", Michigan: "MI", Minnesota: "MN", Mississippi: "MS",
  Missouri: "MO", Montana: "MT", Nebraska: "NE", Nevada: "NV",
  "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
  "North Carolina": "NC", "North Dakota": "ND", Ohio: "OH", Oklahoma: "OK",
  Oregon: "OR", Pennsylvania: "PA", "Rhode Island": "RI", "South Carolina": "SC",
  "South Dakota": "SD", Tennessee: "TN", Texas: "TX", Utah: "UT",
  Vermont: "VT", Virginia: "VA", Washington: "WA", "West Virginia": "WV",
  Wisconsin: "WI", Wyoming: "WY",
};

function abbrevRegion(r?: string | null): string {
  if (!r) return "";
  return STATE_ABBREV[r] || r;
}

type Phase = "idle" | "running" | "done";

export function AmazonCreationWorkspace() {
  const live = useOutletContext<ReturnType<typeof usePrimeBbWebSocket>>();

  const [phonesText, setPhonesText] = useState("");
  const [proxiesText, setProxiesText] = useState("");
  const [templateBrowserId, setTemplateBrowserId] = useState("");
  const [concurrency, setConcurrency] = useState(3);
  const [phase, setPhase] = useState<Phase>("idle");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<AmazonAccount[]>([]);

  function loadAccounts() {
    listAmazonAccounts().then((d) => setAccounts(d.items)).catch(() => {});
  }

  useEffect(() => { loadAccounts(); }, []);

  useEffect(() => {
    if (phase !== "running") return;
    const interval = setInterval(loadAccounts, 5000);
    return () => clearInterval(interval);
  }, [phase]);

  useEffect(() => {
    if (!taskId || phase !== "running") return;
    const task = live.tasks[taskId];
    if (!task) return;
    if (!["completed", "failed", "partial_manual_required", "cancelled", "partial_cancelled"].includes(task.status)) return;
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
    setError(null);
    setPhonesText("");
    setProxiesText("");
  }

  const createdAccounts = accounts.filter((a) => a.status === "created");
  const createdText = createdAccounts
    .map((a) => `${a.phone}|${a.sms_url}|${a.password ?? ""}|${a.name ?? ""}|${abbrevRegion(a.proxy_region)}|${a.created_at ? a.created_at.slice(0, 10) : ""}`)
    .join("\n");

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
                  <TextInput type="number" min={1} max={10} value={concurrency} onChange={(e) => setConcurrency(Number(e.target.value))} />
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
                    placeholder={"5136634109|https://sms222.us?token=abc123\n5139876543|https://sms222.us?token=xyz456|John|TX"}
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
              <p style={{ color: "#86efac", margin: 0 }}>Task completed.</p>
              <div className="form-actions">
                <Button onClick={reset}>Run again</Button>
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* Full-width created accounts */}
      <Card
        title="Created accounts"
        description={`${createdAccounts.length} created · phone|sms_url|pass|name|region|date_created`}
      >
        <textarea
          readOnly
          value={createdText}
          style={{
            width: "100%",
            minHeight: 200,
            fontFamily: "monospace",
            fontSize: 12,
            background: "#0f172a",
            color: "#e2e8f0",
            border: "1px solid #334155",
            borderRadius: 6,
            padding: "10px 12px",
            resize: "vertical",
            boxSizing: "border-box",
          }}
          placeholder="Created accounts will appear here…"
        />
      </Card>
    </div>
  );
}
