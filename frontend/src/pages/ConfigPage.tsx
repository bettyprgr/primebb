import { useEffect, useState } from "react";
import { getConfig, getHealth } from "../api/config";
import type { ConfigResponse } from "../api/types";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";

export function ConfigPage() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [health, setHealth] = useState<string>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getHealth(), getConfig()])
      .then(([healthResponse, configResponse]) => {
        setHealth(healthResponse.status);
        setConfig(configResponse);
      })
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div className="page-stack">
      <div className="page-heading"><h1>Config</h1><p>Read-only runtime configuration. Secrets are intentionally hidden.</p></div>
      {error && <Card><p className="error-text">{error}</p></Card>}
      <Card title="Backend" actions={<Badge tone={health === "ok" ? "success" : "warning"}>{health}</Badge>}>
        {config ? (
          <dl className="detail-list">
            <dt>BitBrowser URL</dt><dd>{config.bitbrowser_url}</dd>
            <dt>ipdata</dt><dd>{config.ipdata_configured ? "configured" : "not configured"}</dd>
            <dt>Proxy host</dt><dd>{config.proxy_host}:{config.proxy_port}</dd>
            <dt>Proxy username prefix</dt><dd>{config.proxy_username_prefix || "not configured"}</dd>
            <dt>Proxy session TTL</dt><dd>{config.proxy_session_ttl} min</dd>
            <dt>Delete browser after complete</dt><dd>{config.delete_browser_after_complete ? "yes" : "no"}</dd>
          </dl>
        ) : <p>Loading config...</p>}
      </Card>
    </div>
  );
}
