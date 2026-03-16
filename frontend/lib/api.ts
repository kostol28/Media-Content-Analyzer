const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/api';

export async function api(path: string, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res;
}
