import { request } from "./client";
import type { ServiceLogin } from "./types";

export function listServices() {
  return request<{ items: string[] }>("/api/services");
}

export function getAccountServices(accountId: number) {
  return request<{ account_id: number; items: ServiceLogin[] }>(`/api/accounts/${accountId}/services`);
}
