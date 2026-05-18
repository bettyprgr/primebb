import { jsonBody, request } from "./client";

export type AmazonAccount = {
  id: number;
  phone: string;
  sms_url: string;
  name?: string | null;
  password?: string | null;
  proxy_url?: string | null;
  proxy_region?: string | null;
  bitbrowser_id?: string | null;
  status: string;
  message?: string | null;
  check_after_at?: string | null;
  last_checked_at?: string | null;
  created_at?: string;
  updated_at?: string;
};

export function importPhones(content: string) {
  return request<{ imported: number; errors: string[]; account_ids: number[] }>(
    "/api/amazon/phones/import",
    { method: "POST", body: jsonBody({ content }) }
  );
}

export function listAmazonAccounts() {
  return request<{ items: AmazonAccount[] }>("/api/amazon/accounts");
}

export function deleteAmazonAccount(id: number) {
  return request<{ ok: boolean }>(`/api/amazon/accounts/${id}`, { method: "DELETE" });
}

export function bulkDeleteAmazonAccounts(ids: number[]) {
  return request<{ deleted: number }>("/api/amazon/accounts/bulk-delete", {
    method: "POST",
    body: jsonBody({ ids }),
  });
}

export function createAmazonTask(amazon_ids: number[], template_browser_id: string | null, concurrency: number, proxy_urls: string[] = []) {
  return request<{ id: string; status: string; total: number; completed: number; failed: number; manual_required: number }>(
    "/api/amazon/tasks",
    { method: "POST", body: jsonBody({ amazon_ids, template_browser_id, concurrency, proxy_urls }) }
  );
}
