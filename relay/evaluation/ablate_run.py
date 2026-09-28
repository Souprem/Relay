"""relay ablate: a stored run re-decided with named engine gates disabled (Phase 3E), offline.

Each trace's stored decisions go through determine_action again with `ablate` set, under the
trace's own policy and thresholds (auto_process overridden first when given: the provider's
operating point). Nothing is called. The result is one new simulated run whose traces carry
`ablation`, written in the committed-bundle format by write_simulated_bundle.
"""

from collections.abc import Sequence

from relay.cases.models import PriorAuthCase
from relay.evaluation.tracediff import replay_run
from relay.traces.models import WorkflowTrace
from relay.traces.store import new_run_id
from relay.workflow.engine import ABLATIONS


def parse_disable(value: str) -> frozenset[str]:
    """The gate names of a --disable value ("contradiction", "missing_evidence" or both,
    comma-separated). ValueError for an empty, unknown or repeated name."""
    names = [name.strip() for name in value.split(",")]
    if any(not name for name in names):
        raise ValueError(f"--disable {value!r}: give gate names separated by commas")
    unknown = sorted(set(names) - ABLATIONS)
    if unknown:
        raise ValueError(
            f"cannot disable {unknown}; the gates that can be disabled are {sorted(ABLATIONS)}"
        )
    if len(set(names)) != len(names):
        raise ValueError(f"--disable {value!r} names a gate twice")
    return frozenset(names)


def ablation_name(disable: frozenset[str]) -> str:
    """The ablation's name as used in paths and labels: sorted gate names joined by "+"."""
    return "+".join(sorted(disable))


def ablate_run(
    traces: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    disable: frozenset[str],
    auto_process: float | None,
    run_id: str | None = None,
) -> list[WorkflowTrace]:
    """Every trace re-decided with the `disable` gates ablated, in trace order, as one new
    simulated run (run_id `run_id`, default a fresh run id; each trace's replay_of is its
    source trace).

    Pairing and hash checks are replay_run's (paired_cases: one run, full coverage, unchanged
    inputs; EvalError otherwise). ValueError for an empty or unknown `disable`, or for a run that
    is already ablated.
    """
    if not disable:
        raise ValueError("nothing to disable")
    unknown = sorted(set(disable) - ABLATIONS)
    if unknown:
        raise ValueError(f"unknown ablation(s) {unknown}; known: {sorted(ABLATIONS)}")
    if any(t.ablation for t in traces):
        raise ValueError(f"run {traces[0].run_id} is already ablated; ablate its source run")
    names = sorted(disable)
    marked = [t.model_copy(update={"ablation": names}) for t in traces]
    return replay_run(
        marked,
        cases,
        policy_id=None,
        auto_process=auto_process,
        mode="simulated",
        run_id=run_id or new_run_id(),
    )
