import { jsonBody, request } from "./client";
import type { BrowserEnsureRequest, BrowserOpenResponse } from "./types";

export function listBrowsers() {
  return request<unknown>("/api/browsers");
}

export function ensureBrowser(payload: BrowserEnsureRequest) {
  return request<{ browser_id: string; profile?: unknown; proxy_url?: string }>("/api/browsers/ensure", { method: "POST", body: jsonBody(payload) });
}

export function openBrowser(browserId: string) {
  return request<BrowserOpenResponse>(`/api/browsers/${browserId}/open`, { method: "POST" });
}

export function closeBrowser(browserId: string) {
  return request<{ message: string }>(`/api/browsers/${browserId}/close`, { method: "POST" });
}
