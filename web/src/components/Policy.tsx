import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Bandit } from "../types";

const LABEL: Record<string, string> = {
  linucb: "LinUCB (learned)",
  best_fixed: "Best fixed arm",
  random: "Random arm",
  all_arms: "Query all 9 arms",
};

export default function Policy({ bandit }: { bandit: Bandit | null }) {
  if (!bandit) return <p className="text-sm text-muted">Policy results are not recorded yet.</p>;
  const h = bandit.held_out;
  const [mean, lo, hi] = h.linucb_minus_best_fixed;
  const rows = bandit.curve.linucb.map((v, i) => ({
    step: i + 1,
    linucb: v,
    random: bandit.curve.random[i],
    oracle: bandit.curve.oracle[i],
  }));
  return (
    <section aria-labelledby="policy-h" className="flex flex-col gap-6">
      <div>
        <h2 id="policy-h" className="text-lg font-semibold text-ink">Learning which source to ask</h2>
        <p className="mt-1 text-sm text-ink">
          A contextual bandit (LinUCB) picks one of 9 arms (arXiv, Hugging Face or OpenAlex × keyword, conceptual or
          recent-first query) from features of the question. Reward: the known target paper appears in the arm's top
          5. Every arm was recorded for every question, so each policy is scored exactly on the same data.
        </p>
      </div>
      <figure>
        <figcaption className="mb-2 text-sm font-medium text-ink">
          Cumulative reward over {h.n_train} training questions (mean of replays)
        </figcaption>
        <div className="h-64 w-full">
          <ResponsiveContainer>
            <LineChart data={rows} margin={{ left: 0, right: 8 }}>
              <CartesianGrid stroke="#e4e4e7" />
              <XAxis dataKey="step" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} width={36} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line dataKey="oracle" name="Oracle (best arm per question)" stroke="#71717a" dot={false} strokeDasharray="4 3" isAnimationActive={false} />
              <Line dataKey="linucb" name="LinUCB" stroke="#4338ca" dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line dataKey="random" name="Random arm" stroke="#d97706" dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </figure>
      <div>
        <h3 className="mb-2 text-sm font-semibold text-ink">
          Held-out questions ({h.n_test}): hits per search call
        </h3>
        <ul className="flex flex-col gap-1 text-sm">
          {Object.entries(h.reward_per_call).map(([k, v]) => (
            <li key={k} className="flex items-center gap-2">
              <span className="w-36 shrink-0 text-ink">{LABEL[k] ?? k}</span>
              <span className="h-3 rounded bg-accent" style={{ width: `${Math.max(2, v * 100 * 2)}px` }} aria-hidden />
              <span className="font-mono text-ink">{v.toFixed(3)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-sm text-ink">
          Best fixed arm on training data: <span className="font-mono">{h.best_fixed_arm}</span>. LinUCB minus best
          fixed arm: <span className="font-mono">{mean >= 0 ? "+" : ""}{mean.toFixed(3)}</span> (95% CI{" "}
          {lo.toFixed(3)} to {hi.toFixed(3)}).{" "}
          {lo > 0
            ? "The learned policy beats the best single source."
            : "Not a clear win over the best single source; reported as measured."}
        </p>
      </div>
      {bandit.golden && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-ink">
            Golden questions ({bandit.golden.n}): judged-relevant papers in top 5
          </h3>
          <ul className="text-sm text-ink">
            {Object.entries(bandit.golden.precision_at_k).map(([k, v]) => (
              <li key={k}>
                {k.replaceAll("_", " ")}: <span className="font-mono">{v.toFixed(3)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
