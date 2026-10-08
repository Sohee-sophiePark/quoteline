"""quoteline CLI: feed, dataset steps, bandit eval, research runs, demo recording, export."""

import argparse
import asyncio
import datetime as dt
import json
import shutil
import uuid
from pathlib import Path

import yaml

from quoteline import dataset as ds
from quoteline.bandit import LinUCB, evaluate, fit
from quoteline.config import ROOT, Settings, settings
from quoteline.feed import build as build_feed
from quoteline.harness import Runner, Trace, make_client
from quoteline.models import ARMS, Paper
from quoteline.orchestrator import approve, run
from quoteline.retriever import Retriever
from quoteline.sources.http import PoliteHttp
from quoteline.state import RunState, load_state

BANDIT = ROOT / "data" / "bandit"
GOLDEN = ROOT / "evals" / "golden.yaml"
DEMOS = ["g01", "g04", "g08", "g11", "g24", "g28"]


def today() -> str:
    return dt.date.today().isoformat()


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1), encoding="utf-8")


def policy() -> LinUCB:
    path = BANDIT / "policy.json"
    return LinUCB.from_dict(json.loads(path.read_text())) if path.exists() else LinUCB()


def runner(s: Settings, cassette: str) -> Runner:
    return Runner(s, make_client(s, s.path("cassettes") / f"{cassette}.jsonl"), Trace())


async def research(state: RunState, s: Settings) -> RunState:
    http = None if s.run_mode == "replay" else PoliteHttp(s.sources)
    retr = Retriever(
        s.run_mode, s.path("data") / "retrieval.jsonl", http, s.research.top_k, today()
    )
    try:
        return await run(state, s, runner(s, "runs"), retr, policy(), s.path("runs"))
    finally:
        if http:
            await http.aclose()


async def cmd_feed(a: argparse.Namespace, s: Settings) -> None:
    http = PoliteHttp(s.sources)
    feed = await build_feed(http, s.feed, today())
    await http.aclose()
    out = Path(a.out) if a.out else s.path("feed")
    write_json(out, feed)
    print(f"feed: {len(feed['trending'])} trending, {len(feed['new'])} new → {out}")


async def cmd_dataset_targets(a: argparse.Namespace, s: Settings) -> None:
    http = PoliteHttp(s.sources)
    dates = ds.sample_dates(dt.date(2023, 6, 1), dt.date.today() - dt.timedelta(days=7), a.dates)
    targets = await ds.sample_targets(http, dates, a.per_date, today())
    await http.aclose()
    path = BANDIT / "targets.jsonl"
    path.unlink(missing_ok=True)
    ds.append_jsonl(path, [p.model_dump() for p in targets])
    print(f"targets: {len(targets)} papers from {len(dates)} dates → {path}")


async def cmd_dataset_questions(a: argparse.Namespace, s: Settings) -> None:
    targets = [Paper.model_validate(r) for r in ds.read_jsonl(BANDIT / "targets.jsonl")]
    path = BANDIT / "questions.jsonl"
    rows = ds.read_jsonl(path)
    r = runner(s, "dataset")
    for _ in range(a.rounds):  # resumable: only targets without a kept question are retried
        kept = {row["target"] for row in rows}
        todo = [t for t in targets if t.id not in kept]
        if not todo:
            break
        rows += await ds.generate_questions(r, todo, today())
    rows = [
        {"qid": f"k{i:03d}", "question": x["question"], "target": x["target"]}
        for i, x in enumerate(rows)
    ]
    path.unlink(missing_ok=True)
    ds.append_jsonl(path, rows)
    print(f"questions: {len(rows)} kept of {len(targets)} targets, {r.calls} LLM calls → {path}")


async def cmd_dataset_arms(a: argparse.Namespace, s: Settings) -> None:
    rows = (
        yaml.safe_load(GOLDEN.read_text())
        if a.golden
        else ds.read_jsonl(BANDIT / "questions.jsonl")
    )
    path = BANDIT / ("golden_arms.jsonl" if a.golden else "arms.jsonl")
    done = {r["qid"] for r in ds.read_jsonl(path)}
    http = PoliteHttp(s.sources)
    try:
        for row in rows:
            if row["qid"] in done:
                continue
            arms = await ds.record_arms(http, row["question"], s.research.top_k, today())
            ds.append_jsonl(
                path, [{**row, "arms": {k: [p.id for p in v] for k, v in arms.items()}}]
            )
            print(f"{row['qid']}: {sum(map(len, arms.values()))} hits, {http.requests} requests")
        if a.golden:
            papers = await ds.golden_papers(http, ds.read_jsonl(path), today())
            (BANDIT / "golden_papers.jsonl").unlink(missing_ok=True)
            ds.append_jsonl(BANDIT / "golden_papers.jsonl", [p.model_dump() for p in papers])
            print(f"golden papers: {len(papers)}")
    finally:
        await http.aclose()


async def cmd_dataset_judge(a: argparse.Namespace, s: Settings) -> None:
    papers = {
        p["id"]: Paper.model_validate(p) for p in ds.read_jsonl(BANDIT / "golden_papers.jsonl")
    }
    path = BANDIT / "judgments.jsonl"
    done = {r["qid"] for r in ds.read_jsonl(path)}
    r = runner(s, "dataset")
    for row in ds.read_jsonl(BANDIT / "golden_arms.jsonl"):
        if row["qid"] in done:
            continue
        ids = list(dict.fromkeys(i for v in row["arms"].values() for i in v if i in papers))
        verdicts = await ds.judge(r, row["question"], [papers[i] for i in ids])
        ds.append_jsonl(path, [{"qid": row["qid"], "judgments": verdicts}])
        print(f"{row['qid']}: {sum(verdicts.values())}/{len(verdicts)} relevant")


def cmd_bandit(a: argparse.Namespace, s: Settings) -> None:
    b = s.bandit
    rows = ds.read_jsonl(BANDIT / "arms.jsonl")
    X, R = ds.known_item_matrix(rows)
    report = evaluate(X, R, b.alpha, b.seeds, b.test_fraction, b.bootstrap)
    write_json(BANDIT / "policy.json", fit(X, R, b.alpha).to_dict())
    report.pop("policy")
    report["arms"] = [a.name for a in ARMS]
    report["arm_hit_rate"] = dict(
        zip(report["arms"], R.mean(axis=0).round(3).tolist(), strict=True)
    )
    golden = ds.read_jsonl(BANDIT / "golden_arms.jsonl")
    judged = {r["qid"]: r["judgments"] for r in ds.read_jsonl(BANDIT / "judgments.jsonl")}
    golden = [g for g in golden if g["qid"] in judged]
    if golden:
        GX, GR = ds.golden_matrix(golden, judged, s.research.top_k)
        p = fit(X, R, b.alpha)
        chosen = [p.select(x, alpha=0.0)[0] for x in GX]
        best = int(R.mean(axis=0).argmax())
        report["golden"] = {
            "n": len(golden),
            "precision_at_k": {
                "linucb": float(GR[range(len(golden)), chosen].mean()),
                "best_fixed": float(GR[:, best].mean()),
                "random": float(GR.mean()),
                "best_arm_in_hindsight": float(GR.mean(axis=0).max()),
            },
        }
    write_json(BANDIT / "report.json", report)
    print(json.dumps({k: report[k] for k in ("held_out", "arm_hit_rate")}, indent=1))
    if "golden" in report:
        print(json.dumps(report["golden"], indent=1))


async def cmd_ask(a: argparse.Namespace, s: Settings) -> None:
    state = RunState(run_id=a.run_id or uuid.uuid4().hex[:8], question=a.question)
    state = await research(state, s)
    print(f"{state.run_id}: {state.status}, {state.llm_calls} LLM calls")


async def cmd_resume(a: argparse.Namespace, s: Settings) -> None:
    state = await research(load_state(s.path("runs"), a.run_id), s)
    print(f"{state.run_id}: {state.status}, {state.llm_calls} LLM calls")


def cmd_approve(a: argparse.Namespace, s: Settings) -> None:
    print(approve(load_state(s.path("runs"), a.run_id), s.path("runs")))


async def cmd_record_demos(a: argparse.Namespace, s: Settings) -> None:
    golden = {g["qid"]: g for g in yaml.safe_load(GOLDEN.read_text())}
    for qid in a.qids or DEMOS:
        state = await research(RunState(run_id=qid, question=golden[qid]["question"]), s)
        s.path("replays").mkdir(exist_ok=True)
        shutil.copy(s.path("runs") / qid / "state.json", s.path("replays") / f"{qid}.json")
        print(f"{qid}: {state.status}, {state.llm_calls} LLM calls")


def cmd_export(a: argparse.Namespace, s: Settings) -> None:
    replays = [json.loads(p.read_text()) for p in sorted(s.path("replays").glob("*.json"))]
    report = BANDIT / "report.json"
    out = ROOT / "web" / "public" / "static-data.json"
    write_json(
        out,
        {"replays": replays, "bandit": json.loads(report.read_text()) if report.exists() else None},
    )
    print(f"export: {len(replays)} replays → {out}")


async def cmd_smoke(a: argparse.Namespace, s: Settings) -> None:
    from quoteline.llm.gemini import GeminiClient

    names = await GeminiClient().list_models()
    print("\n".join(n for n in names if "flash" in n))


def main() -> None:
    p = argparse.ArgumentParser(prog="quoteline")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("feed", help="build the daily feed (network, no LLM)").add_argument("--out")
    t = sub.add_parser("dataset-targets", help="sample target papers (network)")
    t.add_argument("--dates", type=int, default=46)
    t.add_argument("--per-date", type=int, default=5)
    q = sub.add_parser("dataset-questions", help="generate known-item questions (LLM, resumable)")
    q.add_argument("--rounds", type=int, default=3)
    sub.add_parser(
        "dataset-arms", help="record all arms per question (network, resumable)"
    ).add_argument("--golden", action="store_true")
    sub.add_parser("dataset-judge", help="judge golden relevance (LLM, resumable)")
    sub.add_parser("bandit", help="replay evaluation + fit policy (offline)")
    ask = sub.add_parser("ask", help="run the research flow")
    ask.add_argument("question")
    ask.add_argument("--run-id")
    sub.add_parser("resume").add_argument("run_id")
    sub.add_parser("approve").add_argument("run_id")
    sub.add_parser("record-demos", help="record demo runs into replays/").add_argument(
        "qids", nargs="*"
    )
    sub.add_parser("export", help="write web/public/static-data.json")
    sub.add_parser("smoke", help="list available Gemini flash models (live)")
    a = p.parse_args()
    fn = globals()[f"cmd_{a.cmd.replace('-', '_')}"]
    result = fn(a, settings())
    if asyncio.iscoroutine(result):
        asyncio.run(result)
