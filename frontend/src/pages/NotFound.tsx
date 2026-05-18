import { Link } from "react-router-dom";
import { Button } from "../components/Button";
import { Card } from "../components/Card";

export function NotFound() {
  return (
    <Card title="Page not found" description="The requested workspace does not exist.">
      <Link to="/"><Button>Back to dashboard</Button></Link>
    </Card>
  );
}
