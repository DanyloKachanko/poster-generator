import { getApiUrl } from './api';

const TOKEN_KEY = 'auth_token';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export async function login(username: string, password: string): Promise<boolean> {
  const response = await fetch(`${getApiUrl()}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) return false;
  const data = await response.json();
  setToken(data.token);
  return true;
}

export function logout() {
  clearToken();
  window.location.href = '/login';
}

/**
 * Fetch wrapper that adds auth token and handles 401 redirects.
 */
export async function authFetch(url: string, init?: RequestInit): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init?.headers || {});
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const response = await fetch(url, { ...init, headers });
  if (response.status === 401 && typeof window !== 'undefined') {
    clearToken();
    window.location.href = '/login';
    throw new Error('Session expired');
  }
  return response;
}
