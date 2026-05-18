import { useState } from "react";
import { updateAccount } from "../../api/accounts";
import type { Account } from "../../api/types";
import { Badge, statusTone } from "../../components/Badge";
import { EmptyState } from "../../components/EmptyState";

const GMAIL_STATUSES = ["pending", "google_authenticated", "manual_required", "invalid_credentials", "locked", "error"];

type EditCell = { id: number; field: "status" | "message"; value: string };

type Props = {
  accounts: Account[];
  selectedIds: Set<number>;
  onSelectionChange: (ids: Set<number>) => void;
  onChanged: () => void;
};

export function AccountTable({ accounts, selectedIds, onSelectionChange, onChanged }: Props) {
  const [editCell, setEditCell] = useState<EditCell | null>(null);

  if (!accounts.length) return <EmptyState title="No accounts" description="Import or create accounts to start using PrimeBB tools." />;

  const allSelected = accounts.length > 0 && accounts.every((a) => selectedIds.has(a.id));
  const someSelected = accounts.some((a) => selectedIds.has(a.id));

  function toggleAll() {
    if (allSelected) {
      const next = new Set(selectedIds);
      accounts.forEach((a) => next.delete(a.id));
      onSelectionChange(next);
    } else {
      const next = new Set(selectedIds);
      accounts.forEach((a) => next.add(a.id));
      onSelectionChange(next);
    }
  }

  function toggleOne(id: number) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onSelectionChange(next);
  }

  function startEdit(id: number, field: "status" | "message", value: string) {
    setEditCell({ id, field, value });
  }

  async function saveEdit() {
    if (!editCell) return;
    await updateAccount(editCell.id, { [editCell.field]: editCell.value });
    setEditCell(null);
    onChanged();
  }

  function cancelEdit() {
    setEditCell(null);
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th style={{ width: 36 }}>
              <input
                type="checkbox"
                checked={allSelected}
                ref={(el) => { if (el) el.indeterminate = someSelected && !allSelected; }}
                onChange={toggleAll}
              />
            </th>
            <th>Email</th>
            <th>Status</th>
            <th>Proxy region</th>
            <th>Proxy IP</th>
            <th>Message</th>
          </tr>
        </thead>
        <tbody>
          {accounts.map((account) => {
            const editingStatus = editCell?.id === account.id && editCell.field === "status";
            const editingMessage = editCell?.id === account.id && editCell.field === "message";
            return (
              <tr key={account.id} className={selectedIds.has(account.id) ? "row-selected" : ""}>
                <td>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(account.id)}
                    onChange={() => toggleOne(account.id)}
                  />
                </td>
                <td><strong>{account.email}</strong><small>#{account.id} · {account.account_year || "no year"}</small></td>
                <td>
                  {editingStatus ? (
                    <select
                      autoFocus
                      value={editCell!.value}
                      onChange={(e) => setEditCell({ ...editCell!, value: e.target.value })}
                      onBlur={saveEdit}
                      onKeyDown={(e) => { if (e.key === "Enter") saveEdit(); if (e.key === "Escape") cancelEdit(); }}
                      style={{ fontSize: 12, padding: "2px 4px" }}
                    >
                      {GMAIL_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  ) : (
                    <span style={{ cursor: "pointer" }} title="Click to edit" onClick={() => startEdit(account.id, "status", account.status)}>
                      <Badge tone={statusTone(account.status)}>{account.status}</Badge>
                    </span>
                  )}
                </td>
                <td>{account.proxy_state_region || account.proxy_country || "—"}</td>
                <td>{account.proxy_ip || "—"}</td>
                <td className="muted-cell">
                  {editingMessage ? (
                    <input
                      autoFocus
                      type="text"
                      value={editCell!.value}
                      onChange={(e) => setEditCell({ ...editCell!, value: e.target.value })}
                      onBlur={saveEdit}
                      onKeyDown={(e) => { if (e.key === "Enter") saveEdit(); if (e.key === "Escape") cancelEdit(); }}
                      style={{ fontSize: 12, padding: "2px 4px", width: "100%", background: "#1e293b", color: "#e2e8f0", border: "1px solid #475569", borderRadius: 4 }}
                    />
                  ) : (
                    <span style={{ cursor: "pointer" }} title="Click to edit" onClick={() => startEdit(account.id, "message", account.message || "")}>
                      {account.message || <span style={{ color: "#475569" }}>—</span>}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
