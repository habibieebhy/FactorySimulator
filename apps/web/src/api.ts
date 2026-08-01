export const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8100";

export async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}
