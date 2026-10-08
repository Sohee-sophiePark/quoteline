"""Tier 2 evals (offline): recorded demo runs re-run from cassettes, citation checks, bandit report.

Usage: RUN_MODE=replay uv run python evals/run_evals.py
Writes evals/reports/latest.md; exits 1 on failure.
"""

import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

from quoteline.cli import policy, runner
from quoteline.config import ROOT, settings
from quoteline.gates import check
from quoteline.orchestrator import run
from quoteline.retriever import Retriever
from quoteline.state import RunState

GOLDEN = {g["qid"]: g for g in yaml.safe_load((ROOT / "evals" / "golden.yaml").read_text())}


async def rerun(saved: RunState, runs: Path) -> RunState:
    s = settings()
    retr = Retriever("replay", s.path("data") / "retrieval.jsonl")
    fresh = RunState(run_id=saved.run_id, question=saved.question)
    return await run(fresh, s, runner(s, "runs"), retr, policy(), runs)


def score(state: RunState) -> dict:
    final = state.drafts[-1]
    gates = check(final, state.papers, state.question)
    refs = state.rendered.references if state.rendered else []
    expected = GOLDEN.get(state.run_id, {}).get("expected", [])
    v = state.verdicts[-1] if state.verdicts else None
    return {
        "qid": state.run_id,
        "status": state.status,
        "llm_calls": state.llm_calls,
        "revisions": len(state.drafts) - 1,
        "citations_resolve": all(r.id in state.papers for r in refs),
        "hard_gates": all(g.passed for g in gates if g.gate[:2] in ("G1", "G2")),
        "all_gates": all(g.passed for g in gates),
        "expected_retrieved": any(e in state.papers for e in expected) if expected else None,
        "expected_cited": any(e in {r.id for r in refs} for e in expected) if expected else None,
        "faithfulness": v.faithfulness if v else None,
        "coverage": v.coverage if v else None,
    }


def table(rows: list[dict]) -> str:
    cols = list(rows[0])
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    return "\n".join(lines)


async def main() -> int:
    s = settings()
    replays = sorted(s.path("replays").glob("*.json"))
    rows, failures = [], []
    runs = Path(tempfile.mkdtemp())
    try:
        for path in replays:
            saved = RunState.model_validate_json(path.read_text())
            again = await rerun(saved, runs)
            if again.rendered != saved.rendered:
                failures.append(f"{saved.run_id}: replay differs from the recorded run")
            row = score(saved)
            rows.append(row)
            if not (row["citations_resolve"] and row["hard_gates"]):
                failures.append(f"{saved.run_id}: citation or quote check failed")
    finally:
        shutil.rmtree(runs)
    report = ROOT / "data" / "bandit" / "report.json"
    bandit = json.loads(report.read_text()) if report.exists() else None
    out = ["# Eval report (tier 2, offline)", ""]
    out += [table(rows), ""] if rows else ["No recorded runs in replays/ yet.", ""]
    if bandit:
        h = bandit["held_out"]
        mean, lo, hi = h["linucb_minus_best_fixed"]
        per_call = h["reward_per_call"]
        verdict = "beats best fixed arm" if lo > 0 else "does NOT beat the best fixed arm (stop)"
        out += [
            "## Source policy (held-out known-item questions)",
            "",
            f"n_train={h['n_train']} n_test={h['n_test']} best fixed arm={h['best_fixed_arm']}",
            "",
            table([{"policy": k, "reward_per_call": round(v, 3)} for k, v in per_call.items()]),
            "",
            f"LinUCB − best fixed: {mean:+.3f} (95% CI {lo:+.3f} to {hi:+.3f}) → {verdict}",
        ]
    out += ["", "Failures: " + ("; ".join(failures) if failures else "none")]
    dest = ROOT / "evals" / "reports" / "latest.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
