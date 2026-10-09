# Eval report (tier 2, offline)

| qid | status | llm_calls | revisions | citations_resolve | hard_gates | all_gates | expected_retrieved | expected_cited | faithfulness | coverage |
|---|---|---|---|---|---|---|---|---|---|---|
| g01 | AWAITING_APPROVAL | 4 | 0 | True | True | True | False | False | 5 | 5 |
| g04 | AWAITING_APPROVAL | 4 | 0 | True | True | True | False | False | 5 | 5 |
| g08 | AWAITING_APPROVAL | 4 | 0 | True | True | True | True | True | 5 | 5 |
| g11 | AWAITING_APPROVAL | 4 | 0 | True | True | True | True | True | 5 | 5 |
| g24 | AWAITING_APPROVAL | 5 | 1 | True | True | True | True | True | 5 | 5 |
| g28 | AWAITING_APPROVAL | 4 | 0 | True | True | True | None | None | 5 | 5 |
| g31 | AWAITING_APPROVAL | 4 | 0 | True | True | True | True | True | 5 | 5 |

## Source policy (held-out known-item questions)

n_train=174 n_test=44 best fixed arm=openalex:keyword

| policy | reward_per_call |
|---|---|
| linucb | 0.159 |
| best_fixed | 0.114 |
| random | 0.096 |
| all_arms | 0.043 |

LinUCB − best fixed: +0.045 (95% CI +0.000 to +0.114) → does NOT beat the best fixed arm (stop)

Failures: none
