"""Pairwise gold action differences at each provider's own dev-selected `auto_process` threshold.

`relay compare --at` applies a single threshold to every run; the dev-selected operating points
differ per provider (Jev 0.89, rules 0.99, Claude 0.55 for gold-v0.1). This script re-runs
`determine_action` on each run's stored trace bundles with that run's own threshold substituted
(every other threshold keeps its stored value) -- the same technique `relay report --at` and
`relay compare --at` use internally (`relay.evaluation.compare._actions_at`) -- then diffs actions
pairwise the same way `relay compare` does. No provider calls; deterministic; offline.

Usage:
    uv run python -m scripts.gold_compare_own_thresholds \\
        "jev-q-v0.2=evals/baselines/gold-v0.1/<RUN_JEV>=0.89" \\
        "rules-v0.1=evals/baselines/gold-v0.1/<RUN_RULES>=0.99" \\
        "claude-opus-5=evals/baselines/gold-v0.1/<RUN_CLAUDE>=0.55"
"""

import sys
from itertools import combinations
from pathlib import Path

from relay.cases.loader import load_dataset
from relay.cases.models import PriorAuthCase
from relay.cases.policies import load_policy
from relay.evaluation.metrics import paired_cases, score_run
from relay.traces.models import WorkflowTrace
from relay.traces.store import read_traces
from relay.workflow.engine import determine_action
from relay.workflow.outcomes import WorkflowAction

DATASET_DIR = Path("evals/gold")


def _actions_at(
    traces: list[WorkflowTrace], cases: list[PriorAuthCase], auto_process: float
) -> dict[str, WorkflowAction]:
    actions = {}
    for trace, case in paired_cases(traces, cases):
        policy = load_policy(trace.policy_id)
        thresholds = trace.thresholds.model_copy(update={"auto_process": auto_process})
        outcome = determine_action(case.input, trace.decisions, policy, thresholds)
        actions[trace.case_id] = outcome.action
    return actions


def _is_unsafe(action: WorkflowAction, expected: WorkflowAction) -> bool:
    return action == WorkflowAction.AUTO_PROCESS and expected != WorkflowAction.AUTO_PROCESS


def main(argv: list[str]) -> int:
    parsed = []
    for arg in argv:
        label, _, rest = arg.partition("=")
        path, _, threshold_text = rest.rpartition("=")
        if not path or not threshold_text:
            print(f"expected LABEL=RUN_DIR=THRESHOLD, got {arg!r}", file=sys.stderr)
            return 2
        parsed.append((label, Path(path), float(threshold_text)))
    if len(parsed) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    cases = load_dataset(DATASET_DIR)
    runs = []
    for label, run_dir, threshold in parsed:
        [trace_path] = run_dir.glob("traces.jsonl.gz")
        traces = read_traces(trace_path)
        expected = {c.case_id: c.expected_action for c in score_run(traces, cases).cases}
        actions = _actions_at(traces, cases, threshold)
        runs.append((label, threshold, expected, actions))

    print(f"Gold action differences at each provider's own dev-selected threshold (n={len(cases)})")
    print()
    for label, threshold, _, _ in runs:
        print(f"  {label}: auto_process >= {threshold}")

    for (label_a, _, expected, actions_a), (label_b, _, _, actions_b) in combinations(runs, 2):
        diffs = []
        for case_id, action_a in actions_a.items():
            action_b = actions_b[case_id]
            if action_a == action_b:
                continue
            exp = expected[case_id]
            diffs.append(
                (
                    case_id,
                    exp,
                    action_a,
                    action_b,
                    _is_unsafe(action_b, exp) and not _is_unsafe(action_a, exp),
                    _is_unsafe(action_a, exp) and not _is_unsafe(action_b, exp),
                )
            )
        diffs.sort(key=lambda d: (not d[4], not d[5], d[0]))
        print()
        if not diffs:
            print(f"No action differences between {label_a} and {label_b}.")
            continue
        new_unsafe = sum(1 for d in diffs if d[4])
        print(
            f"Action differences {label_a} -> {label_b}: {len(diffs)} cases ({new_unsafe} new unsafe automations)"
        )
        a_width = max(len(label_a), 14) + 2
        b_width = max(len(label_b), 14) + 2
        print(
            f"  {'CASE':<14}{'EXPECTED':<14}{label_a:<{a_width}}{label_b:<{b_width}}FLAG".rstrip()
        )
        for case_id, exp, action_a, action_b, new, resolved in diffs:
            flag = "NEW UNSAFE AUTO" if new else ("unsafe resolved" if resolved else "")
            print(
                f"  {case_id:<14}{exp:<14}{action_a:<{a_width}}{action_b:<{b_width}}{flag}".rstrip()
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
