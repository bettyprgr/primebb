import { Link } from "react-router-dom";
import { tools } from "../app/tools";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";

export function ToolLauncher() {
  return (
    <div className="page-stack">
      <div className="page-heading">
        <h1>Tool Launcher</h1>
        <p>Launch PrimeBB modules from one dashboard while sharing accounts, browsers, proxies, and task logs.</p>
      </div>
      <div className="tool-grid">
        {tools.map((tool) => (
          <Card key={tool.id} title={tool.name} description={tool.description} actions={<Badge tone={tool.status === "available" ? "success" : "warning"}>{tool.status.replace("_", " ")}</Badge>}>
            <Link to={tool.route}><Button>{tool.primaryActionLabel}</Button></Link>
          </Card>
        ))}
      </div>
    </div>
  );
}
