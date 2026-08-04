export const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8100";

type ValidationIssue = {
  loc?: Array<string | number>;
  msg?: string;
};

function readableApiError(status: number, body: string): string {
  if (!body.trim()) return `Request failed with HTTP ${status}`;
  try {
    const parsed = JSON.parse(body) as { detail?: string | ValidationIssue[] | unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) {
      const messages = (parsed.detail as ValidationIssue[])
        .map((issue) => {
          const location = Array.isArray(issue.loc)
            ? issue.loc.filter((part) => part !== "body").join(" → ")
            : "";
          return `${location ? `${location}: ` : ""}${issue.msg ?? "Invalid value"}`;
        })
        .filter(Boolean);
      if (messages.length) return messages.join("\n");
    }
  } catch {
    // Preserve non-JSON server responses below.
  }
  return body;
}

export async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(readableApiError(response.status, body));
  }
  return response.json() as Promise<T>;
}
