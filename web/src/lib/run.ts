import type { Run } from "../types";

/** Paper ID → the searches (or direct lookup) that found it. */
export function foundBy(run: Run): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const [k, ids] of Object.entries(run.retrieval)) {
    const via = k.startsWith("lookup|") ? "direct lookup" : k.split("|")[0];
    for (const id of ids) out[id] = [...new Set([...(out[id] ?? []), via])];
  }
  return out;
}

export const quotesVerified = (run: Run): boolean =>
  run.gates.at(-1)?.find((g) => g.gate.startsWith("G2"))?.passed ?? false;
