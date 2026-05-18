import { jsonBody, request } from "./client";
import type { Account, AccountCreate, AccountListResponse, ImportAccountsResponse } from "./types";

export function listAccounts(params: { search?: string; status?: string; page?: number; page_size?: number } = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  const suffix = query.toString() ? `?${query}` : "";
  return request<AccountListResponse>(`/api/accounts${suffix}`);
}

export function createAccount(account: AccountCreate) {
  return request<Account>("/api/accounts", { method: "POST", body: jsonBody(account) });
}

export function importAccounts(content: string) {
  return request<ImportAccountsResponse>("/api/accounts/import", { method: "POST", body: jsonBody({ content }) });
}

export function updateAccount(accountId: number, data: { status?: string; message?: string }) {
  return request<Account>(`/api/accounts/${accountId}`, { method: "PATCH", body: jsonBody(data) });
}

export function deleteAccount(accountId: number) {
  return request<{ message: string }>(`/api/accounts/${accountId}`, { method: "DELETE" });
}

export function deleteAccountsBulk(accountIds: number[]) {
  return request<{ deleted: number }>("/api/accounts/bulk-delete", { method: "POST", body: jsonBody({ account_ids: accountIds }) });
}

export function deleteAllAccounts() {
  return request<{ deleted: number }>("/api/accounts", { method: "DELETE" });
}
