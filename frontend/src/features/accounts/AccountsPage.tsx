import { useEffect, useState } from "react";
import { deleteAccountsBulk, deleteAllAccounts, listAccounts } from "../../api/accounts";
import { bulkDeleteAmazonAccounts, listAmazonAccounts, updateAmazonAccount } from "../../api/amazon";
import type { AmazonAccount } from "../../api/amazon";
import type { Account } from "../../api/types";
import { Badge, statusTone } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Field, Select, TextInput } from "../../components/Field";
import { AccountImportPanel } from "./AccountImportPanel";
import { AccountTable } from "./AccountTable";

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
  if (!r) return "—";
  return STATE_ABBREV[r] || r;
}

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function AccountsPage() {
  const [tab, setTab] = useState<"gmail" | "amazon">("gmail");

  // Gmail state
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Amazon state
  const [amazonAccounts, setAmazonAccounts] = useState<AmazonAccount[]>([]);
  const [amazonSearch, setAmazonSearch] = useState("");
  const [amazonStatus, setAmazonStatus] = useState("");
  const [amazonSelected, setAmazonSelected] = useState<Set<number>>(new Set());
  const [amazonError, setAmazonError] = useState<string | null>(null);
  const [amazonEditCell, setAmazonEditCell] = useState<{ id: number; field: "status" | "message"; value: string } | null>(null);
  const [amazonDetail, setAmazonDetail] = useState<AmazonAccount | null>(null);
  const [amazonExportOpen, setAmazonExportOpen] = useState(false);

  async function loadGmail() {
    setLoading(true);
    setError(null);
    try {
      const data = await listAccounts({ search, status, page_size: 200 });
      setAccounts(data.items);
      setSelectedIds((prev) => {
        const validIds = new Set(data.items.map((a) => a.id));
        return new Set([...prev].filter((id) => validIds.has(id)));
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load accounts");
    } finally {
      setLoading(false);
    }
  }

  async function loadAmazon() {
    try {
      const data = await listAmazonAccounts();
      setAmazonAccounts(data.items);
    } catch (err) {
      setAmazonError(err instanceof Error ? err.message : "Failed to load Amazon accounts");
    }
  }

  useEffect(() => { loadGmail(); loadAmazon(); }, []);

  async function deleteSelected() {
    if (!selectedIds.size) return;
    if (!confirm(`Delete ${selectedIds.size} selected account(s)?`)) return;
    try {
      await deleteAccountsBulk([...selectedIds]);
      setSelectedIds(new Set());
      await loadGmail();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function deleteAll() {
    if (!confirm(`Delete ALL ${accounts.length} accounts? This cannot be undone.`)) return;
    try {
      await deleteAllAccounts();
      setSelectedIds(new Set());
      await loadGmail();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function deleteAmazonSelected() {
    if (!amazonSelected.size) return;
    if (!confirm(`Delete ${amazonSelected.size} Amazon account(s)?`)) return;
    try {
      await bulkDeleteAmazonAccounts([...amazonSelected]);
      setAmazonSelected(new Set());
      await loadAmazon();
    } catch (err) {
      setAmazonError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function deleteAllAmazon() {
    if (!confirm(`Delete ALL ${filteredAmazon.length} Amazon accounts? This cannot be undone.`)) return;
    try {
      await bulkDeleteAmazonAccounts(filteredAmazon.map((a) => a.id));
      setAmazonSelected(new Set());
      await loadAmazon();
    } catch (err) {
      setAmazonError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  function toggleAmazonAll() {
    const filteredIds = filteredAmazon.map((a) => a.id);
    const allSelected = filteredIds.every((id) => amazonSelected.has(id));
    if (allSelected) {
      setAmazonSelected((prev) => { const next = new Set(prev); filteredIds.forEach((id) => next.delete(id)); return next; });
    } else {
      setAmazonSelected((prev) => { const next = new Set(prev); filteredIds.forEach((id) => next.add(id)); return next; });
    }
  }

  function toggleAmazonOne(id: number) {
    setAmazonSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function buildDetailText(a: AmazonAccount): string {
    const region = abbrevRegion(a.proxy_region);
    const date = a.created_at ? a.created_at.slice(0, 10) : "";
    return [a.phone, a.sms_url ?? "", a.password ?? "", a.name ?? "", region, date].join("|");
  }

  function startAmazonEdit(id: number, field: "status" | "message", value: string) {
    setAmazonEditCell({ id, field, value });
  }

  async function saveAmazonEdit() {
    if (!amazonEditCell) return;
    await updateAmazonAccount(amazonEditCell.id, { [amazonEditCell.field]: amazonEditCell.value });
    setAmazonEditCell(null);
    await loadAmazon();
  }

  function cancelAmazonEdit() {
    setAmazonEditCell(null);
  }

  const filteredAmazon = amazonAccounts.filter((a) => {
    const matchSearch = !amazonSearch || a.phone.includes(amazonSearch) || (a.name ?? "").toLowerCase().includes(amazonSearch.toLowerCase());
    const matchStatus = !amazonStatus || a.status === amazonStatus;
    return matchSearch && matchStatus;
  });

  const allFilteredSelected = filteredAmazon.length > 0 && filteredAmazon.every((a) => amazonSelected.has(a.id));

  return (
    <div className="page-stack">
      <div className="page-heading">
        <h1>Accounts</h1>
        <p>Shared account pool for all PrimeBB tools.</p>
      </div>

      <div className="tab-bar">
        <button className={`tab-btn${tab === "gmail" ? " tab-active" : ""}`} onClick={() => setTab("gmail")}>
          Gmail ({accounts.length})
        </button>
        <button className={`tab-btn${tab === "amazon" ? " tab-active" : ""}`} onClick={() => setTab("amazon")}>
          Amazon ({amazonAccounts.length})
        </button>
      </div>

      {tab === "gmail" && (
        <>
          <AccountImportPanel onImported={loadGmail} />
          <Card title="Gmail accounts" description="Filter by email or status.">
            <div className="filters">
              <Field label="Search"><TextInput value={search} onChange={(e) => setSearch(e.target.value)} placeholder="email" /></Field>
              <Field label="Status">
                <Select value={status} onChange={(e) => setStatus(e.target.value)}>
                  <option value="">All</option>
                  <option value="pending">pending</option>
                  <option value="google_authenticated">google_authenticated</option>
                  <option value="manual_required">manual_required</option>
                  <option value="error">error</option>
                </Select>
              </Field>
              <button className="button" onClick={loadGmail}>{loading ? "Loading..." : "Apply"}</button>
              {selectedIds.size > 0 && (
                <button className="button button-danger" style={{ marginLeft: "auto" }} onClick={deleteSelected}>Delete selected ({selectedIds.size})</button>
              )}
            </div>
            {error && <p className="error-text">{error}</p>}
            <AccountTable accounts={accounts} selectedIds={selectedIds} onSelectionChange={setSelectedIds} onChanged={loadGmail} />
          </Card>
        </>
      )}

      {tab === "amazon" && (
        <Card title="Amazon accounts" description="Filter by phone, name or status.">
          <div className="filters">
            <Field label="Search"><TextInput value={amazonSearch} onChange={(e) => setAmazonSearch(e.target.value)} placeholder="phone or name" /></Field>
            <Field label="Status">
              <Select value={amazonStatus} onChange={(e) => setAmazonStatus(e.target.value)}>
                <option value="">All</option>
                <option value="pending">pending</option>
                <option value="created">created</option>
                <option value="active">active</option>
                <option value="suspended">suspended</option>
                <option value="failed">failed</option>
                <option value="cancelled">cancelled</option>
                <option value="manual_required">manual_required</option>
                <option value="error">error</option>
              </Select>
            </Field>
            <button className="button" onClick={loadAmazon}>Refresh</button>
            {amazonSelected.size > 0 && (
              <button className="button" onClick={() => setAmazonExportOpen(true)}>Export selected ({amazonSelected.size})</button>
            )}
            {amazonSelected.size > 0 && (
              <button className="button button-danger" style={{ marginLeft: "auto" }} onClick={deleteAmazonSelected}>Delete selected ({amazonSelected.size})</button>
            )}
          </div>
          {amazonError && <p className="error-text">{amazonError}</p>}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th style={{ width: 36 }}>
                    <input type="checkbox" checked={allFilteredSelected} onChange={toggleAmazonAll} />
                  </th>
                  <th>Phone</th>
                  <th>Name</th>
                  <th>Password</th>
                  <th>Region</th>
                  <th>Status</th>
                  <th>Message</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {filteredAmazon.length === 0 && (
                  <tr><td colSpan={8} style={{ color: "#94a3b8", textAlign: "center" }}>No Amazon accounts</td></tr>
                )}
                {filteredAmazon.map((a) => {
                  const editingStatus = amazonEditCell?.id === a.id && amazonEditCell.field === "status";
                  const editingMessage = amazonEditCell?.id === a.id && amazonEditCell.field === "message";
                  return (
                    <tr key={a.id} className={amazonSelected.has(a.id) ? "row-selected" : ""}>
                      <td><input type="checkbox" checked={amazonSelected.has(a.id)} onChange={() => toggleAmazonOne(a.id)} /></td>
                      <td style={{ fontFamily: "monospace", cursor: "pointer" }} onClick={() => setAmazonDetail(a)}>{a.phone}</td>
                      <td style={{ cursor: "pointer" }} onClick={() => setAmazonDetail(a)}>{a.name ?? <span style={{ color: "#64748b" }}>—</span>}</td>
                      <td style={{ fontFamily: "monospace", fontSize: 12, cursor: "pointer" }} onClick={() => setAmazonDetail(a)}>{a.password ?? <span style={{ color: "#64748b" }}>—</span>}</td>
                      <td>{abbrevRegion(a.proxy_region)}</td>
                      <td>
                        {editingStatus ? (
                          <select
                            autoFocus
                            value={amazonEditCell!.value}
                            onChange={(e) => setAmazonEditCell({ ...amazonEditCell!, value: e.target.value })}
                            onBlur={saveAmazonEdit}
                            onKeyDown={(e) => { if (e.key === "Enter") saveAmazonEdit(); if (e.key === "Escape") cancelAmazonEdit(); }}
                            style={{ fontSize: 12, padding: "2px 4px" }}
                          >
                            {["pending", "created", "active", "suspended", "failed", "cancelled", "manual_required", "error"].map((s) => (
                              <option key={s} value={s}>{s}</option>
                            ))}
                          </select>
                        ) : (
                          <span style={{ cursor: "pointer" }} title="Click to edit" onClick={() => startAmazonEdit(a.id, "status", a.status)}>
                            <Badge tone={statusTone(a.status)}>{capitalize(a.status)}</Badge>
                          </span>
                        )}
                      </td>
                      <td className="muted-cell">
                        {editingMessage ? (
                          <input
                            autoFocus
                            type="text"
                            value={amazonEditCell!.value}
                            onChange={(e) => setAmazonEditCell({ ...amazonEditCell!, value: e.target.value })}
                            onBlur={saveAmazonEdit}
                            onKeyDown={(e) => { if (e.key === "Enter") saveAmazonEdit(); if (e.key === "Escape") cancelAmazonEdit(); }}
                            style={{ fontSize: 12, padding: "2px 4px", width: "100%", background: "#1e293b", color: "#e2e8f0", border: "1px solid #475569", borderRadius: 4 }}
                          />
                        ) : (
                          <span style={{ cursor: "pointer" }} title="Click to edit" onClick={() => startAmazonEdit(a.id, "message", a.message || "")}>
                            {a.message ?? <span style={{ color: "#475569" }}>—</span>}
                          </span>
                        )}
                      </td>
                      <td className="muted-cell">{a.created_at ? a.created_at.slice(0, 10) : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {amazonExportOpen && (
        <div
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }}
          onClick={() => setAmazonExportOpen(false)}
        >
          <div
            style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 10, padding: "24px 28px", minWidth: 480, maxWidth: 680, maxHeight: "80vh", display: "flex", flexDirection: "column" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ marginBottom: 12, color: "#94a3b8", fontSize: 13 }}>
              {amazonSelected.size} account(s) — click text to copy all
            </div>
            <div
              style={{ fontFamily: "monospace", fontSize: 12, background: "#0f172a", border: "1px solid #334155", borderRadius: 6, padding: "12px 14px", cursor: "pointer", wordBreak: "break-all", color: "#e2e8f0", overflowY: "auto", flex: 1, whiteSpace: "pre-wrap" }}
              title="Click to copy all"
              onClick={() => {
                const text = amazonAccounts
                  .filter((a) => amazonSelected.has(a.id))
                  .map(buildDetailText)
                  .join("\n");
                navigator.clipboard.writeText(text);
                setAmazonExportOpen(false);
              }}
            >
              {amazonAccounts.filter((a) => amazonSelected.has(a.id)).map(buildDetailText).join("\n")}
            </div>
            <div style={{ marginTop: 16, display: "flex", justifyContent: "flex-end" }}>
              <button className="button button-ghost" onClick={() => setAmazonExportOpen(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
      {amazonDetail && (
        <div
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }}
          onClick={() => setAmazonDetail(null)}
        >
          <div
            style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 10, padding: "24px 28px", minWidth: 420, maxWidth: 600 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ marginBottom: 12, color: "#94a3b8", fontSize: 13 }}>Account detail — click text to copy</div>
            <div
              style={{ fontFamily: "monospace", fontSize: 13, background: "#0f172a", border: "1px solid #334155", borderRadius: 6, padding: "12px 14px", cursor: "pointer", wordBreak: "break-all", color: "#e2e8f0" }}
              title="Click to copy"
              onClick={() => { navigator.clipboard.writeText(buildDetailText(amazonDetail)); setAmazonDetail(null); }}
            >
              {buildDetailText(amazonDetail)}
            </div>
            <div style={{ marginTop: 16, display: "flex", justifyContent: "flex-end" }}>
              <button className="button button-ghost" onClick={() => setAmazonDetail(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
