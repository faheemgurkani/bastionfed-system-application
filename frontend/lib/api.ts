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

/** Owner/admin client-view scope: set by ViewModeProvider (X-Client-View-Ids / SSE clientViewIds). */
let clientViewIdsForRequests: string | null = null;

export function setClientViewIdsForRequests(ids: string | null) {
  const t = ids?.trim();
  clientViewIdsForRequests = t || null;
}

export function getClientViewIdsForRequests(): string | null {
  return clientViewIdsForRequests;
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
      const code = (j.detail as { code?: string }).code;
      return code
        ? { detail: String((j.detail as { detail?: string }).detail), code }
        : { detail: String((j.detail as { detail?: string }).detail) };
    }
    if (typeof j.detail === 'string') {
      return j.code ? { detail: j.detail, code: j.code } : { detail: j.detail };
    }
  } catch {
    /* ignore */
  }
  return { detail: res.statusText };
}

export async function apiFetchJson<T>(
  path: string,
  init?: RequestInit & { guest?: boolean; devMode?: boolean }
): Promise<T> {
  const { guest, devMode, ...reqInit } = init || {};
  const headers = new Headers(reqInit.headers);
  if (!headers.has('Content-Type') && reqInit.body && typeof reqInit.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }
  const url = new URL(apiUrl(path));
  if (devMode || guest) url.searchParams.set('dev', 'true');
  if (clientViewIdsForRequests && !devMode && !guest) {
    headers.set('X-Client-View-Ids', clientViewIdsForRequests);
  }
  let res: Response;
  try {
    res = await fetch(url.toString(), { ...reqInit, headers });
  } catch (e) {
    if (e instanceof TypeError) {
      throw new ApiError(
        `Could not reach the API at ${API_BASE_URL}. Start the backend (e.g. python dev_server.py from backend/) and ensure NEXT_PUBLIC_API_URL in frontend/.env.local matches that URL (default http://localhost:8000).`,
        0,
        'NETWORK_ERROR'
      );
    }
    throw e;
  }
  if (!res.ok) {
    const { detail, code } = await parseError(res);
    throw new ApiError(detail || `HTTP ${res.status}`, res.status, code);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function eventsSourceUrl(token: string | null, isDevMode: boolean): string {
  const u = new URL(apiUrl('/api/events'));
  if (isDevMode) u.searchParams.set('dev', 'true');
  else if (token) u.searchParams.set('token', token);
  if (clientViewIdsForRequests && token && !isDevMode) {
    u.searchParams.set('clientViewIds', clientViewIdsForRequests);
  }
  return u.toString();
}

export function flEventsSourceUrl(token: string | null, isDevMode: boolean): string {
  const u = new URL(apiUrl('/api/fl-events'));
  if (isDevMode) u.searchParams.set('dev', 'true');
  else if (token) u.searchParams.set('token', token);
  if (clientViewIdsForRequests && token && !isDevMode) {
    u.searchParams.set('clientViewIds', clientViewIdsForRequests);
  }
  return u.toString();
}
