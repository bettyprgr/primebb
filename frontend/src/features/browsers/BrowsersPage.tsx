import { useEffect, useState } from "react";
import { ensureBrowser, listBrowsers, openBrowser, closeBrowser } from "../../api/browsers";
import { listAccounts } from "../../api/accounts";
import type { Account } from "../../api/types";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Field, Select, TextInput } from "../../components/Field";

type SafeProfile = {
  id: string;
  name: string;
  status: string;
  proxyType: string;
  host: string;
  port: string;
  lastIp: string;
  lastCountry: string;
  updatedAt: string;
};

function normalizeProfiles(value: unknown): Record<string, unknown>[] {
  if (Array.isArray(value)) return value as Record<string, unknown>[];
  if (value && typeof value === "object") {
    const obj = value as { items?: unknown; data?: unknown; list?: unknown };
    if (Array.isArray(obj.items)) return obj.items as Record<string, unknown>[];
    if (Array.isArray(obj.list)) return obj.list as Record<string, unknown>[];
    if (obj.data && typeof obj.data === "object" && Array.isArray((obj.data as { list?: unknown }).list)) return (obj.data as { list: Record<string, unknown>[] }).list;
  }
  return [];
}

function stringValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function readString(profile: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = profile[key];
    if (value !== null && value !== undefined && value !== "") return String(value);
  }
  return "—";
}

function safeProfile(profile: Record<string, unknown>): SafeProfile {
  return {
    id: readString(profile, ["id", "browserId", "browser_id"]),
    name: readString(profile, ["name", "browserName", "browser_name"]),
    status: readString(profile, ["status", "state"]),
    proxyType: readString(profile, ["proxyType", "proxy_type"]),
    host: readString(profile, ["host", "proxyHost", "proxy_host"]),
    port: readString(profile, ["port", "proxyPort", "proxy_port"]),
    lastIp: readString(profile, ["lastIp", "last_ip", "ip"]),
    lastCountry: readString(profile, ["lastCountry", "last_country", "countryCode", "country_code"]),
    updatedAt: readString(profile, ["updateTime", "updated_at", "updatedAt"]),
  };
}

export function BrowsersPage() {
  const [profiles, setProfiles] = useState<Record<string, unknown>[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountId, setAccountId] = useState("");
  const [templateBrowserId, setTemplateBrowserId] = useState("");
  const [rotateProxy, setRotateProxy] = useState(false);
  const [browserId, setBrowserId] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    const [profileData, accountData] = await Promise.allSettled([listBrowsers(), listAccounts({ page_size: 200 })]);
    if (profileData.status === "fulfilled") setProfiles(normalizeProfiles(profileData.value));
    if (accountData.status === "fulfilled") setAccounts(accountData.value.items);
  }

  useEffect(() => { load().catch((err) => setMessage(err.message)); }, []);

  async function ensure() {
    if (!accountId) return;
    const result = await ensureBrowser({ account_id: Number(accountId), template_browser_id: templateBrowserId || null, rotate_proxy: rotateProxy });
    setBrowserId(result.browser_id);
    setMessage(`Ensured browser ${result.browser_id}`);
    await load();
  }

  async function open() {
    if (!browserId) return;
    const result = await openBrowser(browserId);
    setMessage(result.ws ? `Opened ${browserId}` : `Opened ${browserId}, no websocket returned`);
  }

  async function close() {
    if (!browserId) return;
    await closeBrowser(browserId);
    setMessage(`Closed ${browserId}`);
  }

  const safeProfiles = profiles.slice(0, 20).map(safeProfile);

  return (
    <div className="page-stack">
      <div className="page-heading"><h1>Browsers</h1><p>Shared BitBrowser profile operations for all tools.</p></div>
      <Card title="Ensure profile" description="Create or reuse a BitBrowser profile for an account.">
        <div className="filters">
          <Field label="Account"><Select value={accountId} onChange={(event) => setAccountId(event.target.value)}><option value="">Select account</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.email}</option>)}</Select></Field>
          <Field label="Template browser ID"><TextInput value={templateBrowserId} onChange={(event) => setTemplateBrowserId(event.target.value)} placeholder="optional" /></Field>
          <label className="checkbox"><input type="checkbox" checked={rotateProxy} onChange={(event) => setRotateProxy(event.target.checked)} /> Rotate proxy</label>
          <Button onClick={ensure} disabled={!accountId}>Ensure</Button>
        </div>
        {message && <p>{message}</p>}
      </Card>
      <Card title="Open / close" description="Use an existing BitBrowser profile id.">
        <div className="filters"><Field label="Browser ID"><TextInput value={browserId} onChange={(event) => setBrowserId(event.target.value)} /></Field><Button onClick={open}>Open</Button><Button onClick={close}>Close</Button></div>
      </Card>
      <Card title="BitBrowser profiles" description="Sensitive profile fields are intentionally hidden.">
        {safeProfiles.length === 0 ? (
          <div className="empty-state">No BitBrowser profiles returned.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Proxy</th>
                  <th>Last IP</th>
                  <th>Country</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {safeProfiles.map((profile, index) => (
                  <tr key={`${profile.id}-${index}`}>
                    <td>{profile.id}</td>
                    <td>{profile.name}</td>
                    <td>{stringValue(profile.status)}</td>
                    <td>{profile.proxyType} {profile.host !== "—" || profile.port !== "—" ? `${profile.host}:${profile.port}` : "—"}</td>
                    <td>{profile.lastIp}</td>
                    <td>{profile.lastCountry}</td>
                    <td>{profile.updatedAt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
