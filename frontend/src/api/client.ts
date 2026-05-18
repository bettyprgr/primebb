const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const detail = data?.detail;
    const message = Array.isArray(detail) ? detail.map((item) => item.msg || JSON.stringify(item)).join(", ") : detail || response.statusText;
    throw new Error(message);
  }

  return data as T;
}

export function jsonBody(value: unknown): string {
  return JSON.stringify(value);
}
