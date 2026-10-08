"""Contextual bandit: code-computed context features, disjoint LinUCB, baselines, replay eval."""

import re

import numpy as np

from quoteline.models import ARMS

FEATURES = ["bias", "recency", "method", "survey", "fact", "length", "acronym"]
RECENCY = re.compile(
    r"\b(recent|latest|new|newest|current|state[- ]of[- ]the[- ]art|20\d{2})\b", re.I
)
METHOD = re.compile(r"^\s*how\b|\b(method|technique|algorithm|train|improve|reduce)\w*", re.I)
SURVEY = re.compile(
    r"\b(survey|overview|compare|comparison|review|landscape|approaches|alternatives)\b", re.I
)
FACT = re.compile(r"^\s*(what|which|who|when|is|does|are)\b", re.I)
ACRONYM = re.compile(r"\b[A-Z][A-Za-z]*[A-Z]+[A-Za-z0-9-]*\b")


def features(text: str) -> np.ndarray:
    return np.array(
        [
            1.0,
            float(bool(RECENCY.search(text))),
            float(bool(METHOD.search(text))),
            float(bool(SURVEY.search(text))),
            float(bool(FACT.search(text))),
            min(len(text.split()), 30) / 30,
            float(bool(ACRONYM.search(text))),
        ]
    )


class LinUCB:
    """Disjoint LinUCB: per-arm ridge regression of reward on context plus an alpha bonus."""

    def __init__(self, n_arms: int = len(ARMS), d: int = len(FEATURES), alpha: float = 0.5) -> None:
        self.alpha = alpha
        self.A = np.stack([np.eye(d) for _ in range(n_arms)])
        self.b = np.zeros((n_arms, d))

    def scores(self, x: np.ndarray, alpha: float | None = None) -> np.ndarray:
        a = self.alpha if alpha is None else alpha
        inv = np.linalg.inv(self.A)
        theta = np.einsum("aij,aj->ai", inv, self.b)
        bonus = np.sqrt(np.einsum("i,aij,j->a", x, inv, x))
        return theta @ x + a * bonus

    def select(self, x: np.ndarray, m: int = 1, alpha: float | None = None) -> list[int]:
        """Top-`m` arms by UCB score; ties go to the lower index."""
        return [int(i) for i in np.argsort(-self.scores(x, alpha), kind="stable")[:m]]

    def update(self, arm: int, x: np.ndarray, reward: float) -> None:
        self.A[arm] += np.outer(x, x)
        self.b[arm] += reward * x

    def to_dict(self) -> dict:
        return {"alpha": self.alpha, "A": self.A.tolist(), "b": self.b.tolist()}

    @classmethod
    def from_dict(cls, d: dict) -> "LinUCB":
        p = cls(alpha=d["alpha"])
        p.A, p.b = np.array(d["A"]), np.array(d["b"])
        return p


def online_replay(X: np.ndarray, R: np.ndarray, alpha: float, seed: int) -> dict[str, np.ndarray]:
    """Full-information replay over a shuffled stream; R[q, a] = reward of arm a on question q.

    Returns per-step rewards for LinUCB, uniform random and the oracle (best arm per question)."""
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(X))
    policy = LinUCB(n_arms=R.shape[1], d=X.shape[1], alpha=alpha)
    lin, rand = np.zeros(len(order)), np.zeros(len(order))
    for t, q in enumerate(order):
        a = policy.select(X[q])[0]
        lin[t], rand[t] = R[q, a], R[q, rng.integers(R.shape[1])]
        policy.update(a, X[q], R[q, a])
    return {"linucb": lin, "random": rand, "oracle": R[order].max(axis=1)}


def fit(X: np.ndarray, R: np.ndarray, alpha: float) -> LinUCB:
    """Offline fit with full information: every arm learns from every training question."""
    policy = LinUCB(n_arms=R.shape[1], d=X.shape[1], alpha=alpha)
    for x, r in zip(X, R, strict=True):
        for a in range(R.shape[1]):
            policy.update(a, x, r[a])
    return policy


def bootstrap_diff(
    a: np.ndarray, b: np.ndarray, n: int, seed: int = 0
) -> tuple[float, float, float]:
    """Mean of a−b with a 95% percentile bootstrap interval over questions."""
    rng = np.random.default_rng(seed)
    d = a - b
    means = d[rng.integers(0, len(d), size=(n, len(d)))].mean(axis=1)
    return float(d.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def evaluate(
    X: np.ndarray, R: np.ndarray, alpha: float, seeds: int, test_fraction: float, n_boot: int
) -> dict:
    """Learning curves on the training stream, then held-out comparison of the frozen policy."""
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(X))
    n_test = max(1, round(len(X) * test_fraction))
    test, train = idx[:n_test], idx[n_test:]
    runs = [online_replay(X[train], R[train], alpha, s) for s in range(seeds)]
    curve = {k: np.mean([np.cumsum(r[k]) for r in runs], axis=0) for k in runs[0]}
    policy = fit(X[train], R[train], alpha)
    best_fixed = int(R[train].mean(axis=0).argmax())
    chosen = np.array([policy.select(x, alpha=0.0)[0] for x in X[test]])
    lin = R[test, chosen]
    fixed = R[test, best_fixed]
    all_arms_hit = R[test].max(axis=1)
    held_out = {
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "best_fixed_arm": ARMS[best_fixed].name if R.shape[1] == len(ARMS) else str(best_fixed),
        "reward_per_call": {
            "linucb": float(lin.mean()),
            "best_fixed": float(fixed.mean()),
            "random": float(R[test].mean()),
            "all_arms": float(all_arms_hit.mean() / R.shape[1]),
        },
        "hit_rate": {"linucb": float(lin.mean()), "all_arms": float(all_arms_hit.mean())},
        "linucb_minus_best_fixed": bootstrap_diff(lin, fixed, n_boot),
        "chosen_arms": {
            ARMS[a].name if R.shape[1] == len(ARMS) else str(a): int((chosen == a).sum())
            for a in sorted(set(chosen.tolist()))
        },
    }
    return {
        "curve": {k: v.round(3).tolist() for k, v in curve.items()},
        "regret": (curve["oracle"] - curve["linucb"]).round(3).tolist(),
        "held_out": held_out,
        "policy": policy.to_dict(),
    }
