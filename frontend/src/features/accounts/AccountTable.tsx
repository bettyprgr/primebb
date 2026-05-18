import { deleteAccount } from "../../api/accounts";
import type { Account } from "../../api/types";
import { Badge, statusTone } from "../../components/Badge";
import { Button } from "../../components/Button";
import { EmptyState } from "../../components/EmptyState";

type Props = {
  accounts: Account[];
  selectedIds: Set<number>;
  onSelectionChange: (ids: Set<number>) => void;
  onChanged: () => void;
};

export function AccountTable({ accounts, selectedIds, onSelectionChange, onChanged }: Props) {
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

  async function remove(account: Account) {
    if (!confirm(`Delete ${account.email}?`)) return;
    await deleteAccount(account.id);
    const next = new Set(selectedIds);
    next.delete(account.id);
    onSelectionChange(next);
    onChanged();
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
            <th>Country</th>
            <th>Proxy region</th>
            <th>Proxy IP</th>
            <th>Message</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {accounts.map((account) => (
            <tr key={account.id} className={selectedIds.has(account.id) ? "row-selected" : ""}>
              <td>
                <input
                  type="checkbox"
                  checked={selectedIds.has(account.id)}
                  onChange={() => toggleOne(account.id)}
                />
              </td>
              <td><strong>{account.email}</strong><small>#{account.id} · {account.account_year || "no year"}</small></td>
              <td><Badge tone={statusTone(account.status)}>{account.status}</Badge></td>
              <td>{account.country || "—"}</td>
              <td>{account.proxy_state_region || account.proxy_country || "—"}</td>
              <td>{account.proxy_ip || "—"}</td>
              <td className="muted-cell">{account.message || "—"}</td>
              <td><Button className="button-ghost" onClick={() => remove(account)}>Delete</Button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
