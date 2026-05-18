import type { Task } from "../../api/types";
import { Badge, statusTone } from "../../components/Badge";

export function TaskProgressCard({ task }: { task: Task }) {
  const percent = task.total ? Math.round(((task.completed + task.failed + task.manual_required) / task.total) * 100) : 0;
  return (
    <div className="task-card">
      <div className="list-row">
        <div><strong>{task.id}</strong><small>{task.type}</small></div>
        <Badge tone={statusTone(task.status)}>{task.status}</Badge>
      </div>
      <div className="progress"><span style={{ width: `${percent}%` }} /></div>
      <div className="task-stats"><span>Total {task.total}</span><span>Done {task.completed}</span><span>Failed {task.failed}</span><span>Manual {task.manual_required}</span></div>
      {task.message && <small>{task.message}</small>}
    </div>
  );
}
