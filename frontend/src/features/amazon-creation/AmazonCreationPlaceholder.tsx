import { Link } from "react-router-dom";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";

const stages = ["Account source selection", "BitBrowser profile preparation", "Amazon signup automation", "OTP and manual challenge handling", "Result tracking"];

export function AmazonCreationPlaceholder() {
  return (
    <div className="page-stack">
      <div className="page-heading"><h1>Amazon Creation</h1><p>The next PrimeBB tool module. The dashboard shell is ready for this workflow.</p></div>
      <Card title="Planned workflow" actions={<Badge tone="warning">coming soon</Badge>}>
        <ol className="stage-list">{stages.map((stage) => <li key={stage}>{stage}</li>)}</ol>
        <Link to="/tools"><Button>Back to launcher</Button></Link>
      </Card>
    </div>
  );
}
