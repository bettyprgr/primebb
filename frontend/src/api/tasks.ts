import { jsonBody, request } from "./client";
import type { Task, TaskCreateRequest } from "./types";

export function createTask(payload: TaskCreateRequest) {
  return request<Task>("/api/tasks", { method: "POST", body: jsonBody(payload) });
}

export function listTasks() {
  return request<Task[]>("/api/tasks");
}

export function getTask(taskId: string) {
  return request<Task>(`/api/tasks/${taskId}`);
}

export function cancelTask(taskId: string) {
  return request<{ message: string }>(`/api/tasks/${taskId}`, { method: "DELETE" });
}
