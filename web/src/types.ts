export type Paper = {
  id: string;
  title: string;
  authors: string[];
  published: string;
  abstract: string;
  categories: string[];
  upvotes: number | null;
  sources: string[];
  url?: string;
  score?: number;
};

export type Reference = {
  n: number;
  id: string;
  title: string;
  authors: string;
  year: string;
  url: string;
  contribution_quote: string;
};

export type Gate = { gate: string; passed: boolean; details: string[] };
export type Verdict = { faithfulness: number; coverage: number; issues: string[] };
export type TraceEvent = { seq: number; t_ms: number; kind: string; agent: string; payload: Record<string, unknown>; level: string };

export type Run = {
  run_id: string;
  question: string;
  status: string;
  plan: { subquestions: { text: string }[] } | null;
  choices: { subquestion: string; arms: string[]; scores: Record<string, number> }[];
  papers: Record<string, Paper>;
  gates: Gate[][];
  verdicts: Verdict[];
  drafts: unknown[];
  rendered: { takeaway: string; paragraphs: string[]; references: Reference[] } | null;
  events: TraceEvent[];
  llm_calls: number;
};

export type HeldOut = {
  n_train: number;
  n_test: number;
  best_fixed_arm: string;
  reward_per_call: Record<string, number>;
  hit_rate: Record<string, number>;
  linucb_minus_best_fixed: [number, number, number];
  chosen_arms: Record<string, number>;
};

export type Bandit = {
  curve: Record<"linucb" | "random" | "oracle", number[]>;
  regret: number[];
  held_out: HeldOut;
  arms: string[];
  arm_hit_rate: Record<string, number>;
  golden?: { n: number; precision_at_k: Record<string, number> };
};

export type Feed = { generated: string; window_days: number; sources: string[]; trending: Paper[]; new: Paper[] };
export type StaticData = { replays: Run[]; bandit: Bandit | null };
