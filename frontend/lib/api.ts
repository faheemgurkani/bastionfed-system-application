/**
 * BastionFed FastAPI backend base URL.
 * Set in `.env.local`: NEXT_PUBLIC_API_URL=http://localhost:8000
 */
export const API_BASE_URL =
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) ||
  'http://localhost:8000';

export function apiUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL.replace(/\/$/, '')}${p}`;
}

/** True when `fetch` was aborted (React Strict Mode / effect cleanup). */
export function isAbortError(e: unknown): boolean {
  return e instanceof DOMException && e.name === 'AbortError';
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public body?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function parseError(res: Response): Promise<{ detail?: string; code?: string }> {
  try {
    const j = (await res.json()) as { detail?: string | { detail?: string; code?: string }; code?: string };
    if (typeof j.detail === 'object' && j.detail !== null && 'detail' in j.detail) {
      return { detail: String((j.detail as { detail?: string }).detail), code: (j.detail as { code?: string }).code };
    }
    if (typeof j.detail === 'string') return { detail: j.detail, code: j.code };
  } catch {
    /* ignore */
  }
  return { detail: res.statusText };
}

export async function apiFetchJson<T>(
  path: string,
  init?: RequestInit & { guest?: boolean }
): Promise<T> {
  const { guest, ...reqInit } = init || {};
  const headers = new Headers(reqInit.headers);
  if (!headers.has('Content-Type') && reqInit.body && typeof reqInit.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }
  const url = new URL(apiUrl(path));
  if (guest) url.searchParams.set('guest', 'true');
  const res = await fetch(url.toString(), { ...reqInit, headers });
  if (!res.ok) {
    const { detail, code } = await parseError(res);
    throw new ApiError(detail || `HTTP ${res.status}`, res.status, code);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function eventsSourceUrl(token: string | null, isGuest: boolean): string {
  const u = new URL(apiUrl('/api/events'));
  if (isGuest) u.searchParams.set('guest', 'true');
  else if (token) u.searchParams.set('token', token);
  return u.toString();
}

export function flEventsSourceUrl(token: string | null, isGuest: boolean): string {
  const u = new URL(apiUrl('/api/fl-events'));
  if (isGuest) u.searchParams.set('guest', 'true');
  else if (token) u.searchParams.set('token', token);
  return u.toString();
}
