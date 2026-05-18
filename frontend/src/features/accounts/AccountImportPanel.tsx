import { useState } from "react";
import { importAccounts } from "../../api/accounts";
import type { ImportAccountsResponse } from "../../api/types";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Textarea } from "../../components/Field";

export function AccountImportPanel({ onImported }: { onImported: () => void }) {
  const [content, setContent] = useState("");
  const [result, setResult] = useState<ImportAccountsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    setError(null);
    try {
      const response = await importAccounts(content);
      setResult(response);
      if (response.imported) {
        setContent("");
        onImported();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card title="Import accounts" description="Pipe-only format: email|password|recovery_email|totp_secret|account_year|country">
      <Textarea value={content} onChange={(event) => setContent(event.target.value)} rows={6} placeholder="user@example.com|password|recovery@example.com|BASE32TOTPSECRET|2024|United States" />
      <div className="form-actions"><Button onClick={submit} disabled={loading || !content.trim()}>{loading ? "Importing..." : "Import accounts"}</Button></div>
      {error && <p className="error-text">{error}</p>}
      {result && (
        <div className="result-box">
          <strong>Imported: {result.imported}</strong>
          {result.errors.length > 0 && <ul>{result.errors.map((item) => <li key={item}>{item}</li>)}</ul>}
        </div>
      )}
    </Card>
  );
}
