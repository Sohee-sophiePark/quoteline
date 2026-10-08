import numpy as np

from quoteline.bandit import (
    FEATURES,
    LinUCB,
    bootstrap_diff,
    evaluate,
    features,
    online_replay,
)


def test_features_shape_and_flags():
    x = features("What are the latest LLM approaches to speculative decoding?")
    assert x.shape == (len(FEATURES),)
    on = {f for f, v in zip(FEATURES, x, strict=True) if v == 1.0}
    assert {"bias", "recency", "survey", "fact", "acronym"} <= on and "method" not in on
    assert features("How do I reduce KV cache memory")[2] == 1.0


def test_untrained_linucb_ties_break_to_lowest_index():
    assert LinUCB(n_arms=3, d=2).select(np.array([1.0, 0.0]), m=2) == [0, 1]


def test_linucb_learns_context_dependent_arm():
    # arm 0 pays when feature 1 is on, arm 1 pays otherwise
    rng = np.random.default_rng(1)
    X = np.array([[1.0, float(rng.integers(2))] for _ in range(300)])
    R = np.stack([X[:, 1], 1 - X[:, 1], np.zeros(300)], axis=1)
    out = online_replay(X, R, alpha=0.5, seed=0)
    assert out["linucb"][-100:].mean() > 0.95 and out["random"].mean() < 0.5
    assert np.array_equal(out["oracle"], np.ones(300))


def test_policy_roundtrip():
    p = LinUCB(n_arms=2, d=3)
    p.update(1, np.array([1.0, 0.0, 1.0]), 1.0)
    q = LinUCB.from_dict(p.to_dict())
    x = np.array([1.0, 0.0, 1.0])
    assert np.allclose(p.scores(x), q.scores(x))


def test_bootstrap_diff_interval_contains_mean():
    mean, lo, hi = bootstrap_diff(np.ones(50), np.zeros(50), n=200)
    assert mean == lo == hi == 1.0


def test_evaluate_beats_best_fixed_when_context_matters():
    rng = np.random.default_rng(2)
    X = np.array([[1.0, float(rng.integers(2))] for _ in range(200)])
    R = np.stack([X[:, 1], 1 - X[:, 1], np.full(200, 0.4)], axis=1)
    out = evaluate(X, R, alpha=0.5, seeds=3, test_fraction=0.2, n_boot=200)
    h = out["held_out"]
    assert h["n_test"] == 40 and h["reward_per_call"]["linucb"] == 1.0
    assert h["linucb_minus_best_fixed"][1] > 0  # CI lower bound above zero
    assert len(out["curve"]["linucb"]) == 160 and out["regret"][-1] >= 0
