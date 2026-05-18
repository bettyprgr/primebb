import { useEffect, useState } from "react";
import { listAccounts } from "../../api/accounts";
import { getAccountServices } from "../../api/services";
import type { Account, ServiceLogin } from "../../api/types";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Field, Select } from "../../components/Field";
import { ServicesMatrix } from "./ServicesMatrix";

export function ServicesPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountId, setAccountId] = useState("");
  const [services, setServices] = useState<ServiceLogin[]>([]);

  useEffect(() => { listAccounts({ page_size: 200 }).then((data) => setAccounts(data.items)).catch(() => setAccounts([])); }, []);

  async function load() {
    if (!accountId) return;
    const data = await getAccountServices(Number(accountId));
    setServices(data.items);
  }

  return (
    <div className="page-stack">
      <div className="page-heading"><h1>Services</h1><p>Per-account service login statuses for Social Pumper.</p></div>
      <Card title="Account services">
        <div className="filters"><Field label="Account"><Select value={accountId} onChange={(event) => setAccountId(event.target.value)}><option value="">Select account</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.email}</option>)}</Select></Field><Button onClick={load} disabled={!accountId}>Load</Button></div>
        <ServicesMatrix services={services} />
      </Card>
    </div>
  );
}
