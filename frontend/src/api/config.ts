import { request } from "./client";
import type { ConfigResponse } from "./types";

export function getConfig() {
  return request<ConfigResponse>("/api/config");
}

export function getHealth() {
  return request<{ status: string }>("/api/health");
}
