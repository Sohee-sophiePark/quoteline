import type { Feed, Run, StaticData } from "./types";

export const isStatic = Boolean(import.meta.env.VITE_STATIC);

async function getJson<T>(path: string): Promise<T | null> {
  const res = await fetch(path);
  return res.ok ? ((await res.json()) as T) : null;
}

export const loadStatic = () => getJson<StaticData>("./static-data.json");
export const loadFeed = () => getJson<Feed>("./feed.json");

export async function askLive(question: string): Promise<Run> {
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Request failed");
  return body as Run;
}

export async function approveLive(runId: string): Promise<Run> {
  const res = await fetch(`/api/runs/${runId}/approve`, { method: "POST" });
  if (!res.ok) throw new Error("Approval failed");
  return (await res.json()) as Run;
}
