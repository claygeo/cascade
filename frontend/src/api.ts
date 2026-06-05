// Thin API client: JSON fetch with bearer auth + transparent refresh-token retry.
const API_BASE = import.meta.env.VITE_API_BASE || "";
const PREFIX = `${API_BASE}/api/v1`;

const ACCESS_KEY = "cascade_access";
const REFRESH_KEY = "cascade_refresh";

export function getAccess() {
  return localStorage.getItem(ACCESS_KEY);
}
export function getRefresh() {
  return localStorage.getItem(REFRESH_KEY);
}
export function setTokens(t: { access_token: string; refresh_token: string }) {
  localStorage.setItem(ACCESS_KEY, t.access_token);
  localStorage.setItem(REFRESH_KEY, t.refresh_token);
}
export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function rawFetch(path: string, init: RequestInit, withAuth: boolean): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init.headers as Record<string, string>) || {}),
  };
  if (withAuth) {
    const token = getAccess();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  return fetch(`${PREFIX}${path}`, { ...init, headers });
}

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const refresh = getRefresh();
  if (!refresh) return false;
  if (!refreshing) {
    refreshing = (async () => {
      const res = await rawFetch(
        "/auth/refresh",
        { method: "POST", body: JSON.stringify({ refresh_token: refresh }) },
        false,
      );
      if (!res.ok) {
        clearTokens();
        return false;
      }
      setTokens(await res.json());
      return true;
    })().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

export interface ApiOpts {
  method?: string;
  body?: unknown;
  auth?: boolean;
}

export async function api<T = unknown>(path: string, opts: ApiOpts = {}): Promise<T> {
  const withAuth = opts.auth ?? true;
  const init: RequestInit = {
    method: opts.method || "GET",
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  };

  let res = await rawFetch(path, init, withAuth);
  if (res.status === 401 && withAuth) {
    if (await tryRefresh()) res = await rawFetch(path, init, true);
  }

  if (!res.ok) {
    let detail: string = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}
