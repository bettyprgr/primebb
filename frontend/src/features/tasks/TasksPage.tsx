import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { cancelTask, createTask, listTasks } from "../../api/tasks";
import type { Task, TaskCreateRequest, TaskType } from "../../api/types";
import type { usePrimeBbWebSocket } from "../../api/websocket";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Field, Select, TextInput } from "../../components/Field";
import { TaskProgressCard } from "./TaskProgressCard";

export function TasksPage() {
  const live = useOutletContext<ReturnType<typeof usePrimeBbWebSocket>>();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [type, setType] = useState<TaskType>("login_gmail");
  const [accountIds, setAccountIds] = useState("");
  const [services, setServices] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    setTasks(await listTasks());
  }

  useEffect(() => { load().catch((err) => setMessage(err.message)); }, []);

  const mergedTasks = useMemo(() => {
    const map = new Map(tasks.map((task) => [task.id, task]));
    Object.values(live.tasks).forEach((task) => map.set(task.id, task));
    return Array.from(map.values()).sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
  }, [tasks, live.tasks]);

  async function submit() {
    const payload: TaskCreateRequest = {
      type,
      account_ids: accountIds.split(",").map((item) => Number(item.trim())).filter(Boolean),
      services: services.split(",").map((item) => item.trim()).filter(Boolean),
      concurrency: 1,
      close_after: false,
    };
    const task = await createTask(payload);
    setMessage(`Created task ${task.id}`);
    await load();
  }

  async function cancel(taskId: string) {
    await cancelTask(taskId);
    await load();
  }

  return (
    <div className="page-stack">
      <div className="page-heading"><h1>Tasks</h1><p>Shared task runner for all tool modules.</p></div>
      <Card title="Create task" description="Generic backend task form. Social Pumper has a guided version.">
        <div className="filters">
          <Field label="Type"><Select value={type} onChange={(event) => setType(event.target.value as TaskType)}><option value="login_gmail">login_gmail</option><option value="login_service">login_service</option><option value="login_all_services">login_all_services</option></Select></Field>
          <Field label="Account IDs"><TextInput value={accountIds} onChange={(event) => setAccountIds(event.target.value)} placeholder="1,2,3" /></Field>
          <Field label="Services"><TextInput value={services} onChange={(event) => setServices(event.target.value)} placeholder="youtube,reddit" /></Field>
          <Button onClick={submit} disabled={!accountIds.trim()}>Create</Button>
        </div>
        {message && <p>{message}</p>}
      </Card>
      <Card title="Task history">
        <div className="task-grid">
          {mergedTasks.map((task) => <div key={task.id}><TaskProgressCard task={task} /><Button className="button-ghost" onClick={() => cancel(task.id)}>Cancel</Button></div>)}
          {!mergedTasks.length && <p>No tasks yet.</p>}
        </div>
      </Card>
    </div>
  );
}
