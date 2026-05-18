import { useEffect, useState } from "react";
import { deleteAccountsBulk, deleteAllAccounts, listAccounts } from "../../api/accounts";
import type { Account } from "../../api/types";
import { Card } from "../../components/Card";
import { Field, Select, TextInput } from "../../components/Field";
import { AccountImportPanel } from "./AccountImportPanel";
import { AccountTable } from "./AccountTable";

export function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  async function load() {
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

  useEffect(() => { load(); }, []);

  async function deleteSelected() {
    if (!selectedIds.size) return;
    if (!confirm(`Delete ${selectedIds.size} selected account(s)?`)) return;
    try {
      await deleteAccountsBulk([...selectedIds]);
      setSelectedIds(new Set());
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function deleteAll() {
    if (!confirm(`Delete ALL ${accounts.length} accounts? This cannot be undone.`)) return;
    try {
      await deleteAllAccounts();
      setSelectedIds(new Set());
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div className="page-stack">
      <div className="page-heading"><h1>Accounts</h1><p>Shared account pool for all PrimeBB tools. Passwords and TOTP secrets are never shown in tables.</p></div>
      <AccountImportPanel onImported={load} />
      <Card title="Account list" description="Filter by email or status.">
        <div className="filters">
          <Field label="Search"><TextInput value={search} onChange={(event) => setSearch(event.target.value)} placeholder="email" /></Field>
          <Field label="Status"><Select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All</option><option value="pending">pending</option><option value="google_authenticated">google_authenticated</option><option value="manual_required">manual_required</option><option value="error">error</option></Select></Field>
          <button className="button" onClick={load}>{loading ? "Loading..." : "Apply"}</button>
          {selectedIds.size > 0 && (
            <button className="button button-danger" onClick={deleteSelected}>
              Delete selected ({selectedIds.size})
            </button>
          )}
          {accounts.length > 0 && (
            <button className="button button-danger-ghost" onClick={deleteAll}>
              Delete all ({accounts.length})
            </button>
          )}
        </div>
        {error && <p className="error-text">{error}</p>}
        <AccountTable
          accounts={accounts}
          selectedIds={selectedIds}
          onSelectionChange={setSelectedIds}
          onChanged={load}
        />
      </Card>
    </div>
  );
}
