"""What the dashboard shows: the committed runs, their operating points, and the demo diffs.

Every entry names committed files under evals/. The operating points are the ones the README
headline table uses (each provider's threshold chosen on a dev set before any holdout or gold
run); None means the run is shown at its recorded auto_process threshold.
"""

from dataclasses import dataclass

BASELINES = "evals/baselines"


@dataclass(frozen=True)
class DatasetSpec:
    id: str
    label: str
    path: str  # case folders, relative to the repository root
    committed: bool  # True when the case folders are tracked in git (gold, smoke)
    description: str


@dataclass(frozen=True)
class RunSpec:
    run_id: str
    dataset: str  # a DatasetSpec id
    run_dir: str  # relative to the repository root
    trace_name: str  # the trace file inside run_dir
    provider: str  # "jev" | "claude" | "rules" | "groundtruth"
    label: str  # e.g. "Jev q-v0.2"
    question_set: str
    slug: str  # unique within a dataset; used in URLs and per-case results
    operating_point: float | None
    operating_point_source: str
    note: str | None = None


@dataclass(frozen=True)
class DiffSpec:
    case_id: str
    title: str
    original: str  # a RunSpec run_id, decided at its operating point
    candidate_run: str | None  # a RunSpec run_id, decided at its operating point
    candidate_trace: str | None  # or a committed trace file used as recorded
    candidate_label: str
    summary: str


DATASETS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        "gold-v0.1",
        "Gold",
        "evals/gold",
        True,
        "100 individually written cases in five categories, labelled by AI agents.",
    ),
    DatasetSpec(
        "smoke-v0.1",
        "Smoke",
        "evals/smoke",
        True,
        "10 hand-written cases that exercise every action.",
    ),
    DatasetSpec(
        "gen-v0.2-dev",
        "gen-v0.2 dev",
        "evals/generated/gen-v0.2-dev",
        False,
        "400 generated cases for tuning thresholds and question sets.",
    ),
    DatasetSpec(
        "gen-v0.2-holdout",
        "gen-v0.2 holdout",
        "evals/generated/gen-v0.2-holdout",
        False,
        "1000 generated cases, run once per frozen configuration.",
    ),
    DatasetSpec(
        "gen-v0.3-dev",
        "gen-v0.3 dev",
        "evals/generated/gen-v0.3-dev",
        False,
        "400 generated cases with interrupted and old methotrexate courses.",
    ),
    DatasetSpec(
        "gen-v0.3-holdout",
        "gen-v0.3 holdout",
        "evals/generated/gen-v0.3-holdout",
        False,
        "1000 generated cases for the one-shot q-v0.2 vs q-v0.3 evaluation.",
    ),
    DatasetSpec(
        "gen-v0.3-shift",
        "gen-v0.3 shift",
        "evals/generated/gen-v0.3-shift",
        False,
        "400 generated cases labelled under immunara-v0.2's 12-month recency rule.",
    ),
)

_DEV2 = "chosen on gen-v0.2-dev"
_DEV3 = "chosen on gen-v0.3-dev"
_RECORDED = "recorded threshold"


def _run(
    dataset: str,
    folder: str,
    provider: str,
    label: str,
    question_set: str,
    slug: str,
    operating_point: float | None,
    source: str,
    *,
    run_id: str | None = None,
    trace_name: str = "traces.jsonl.gz",
    note: str | None = None,
) -> RunSpec:
    return RunSpec(
        run_id=run_id or folder,
        dataset=dataset,
        run_dir=f"{BASELINES}/{dataset}/{folder}",
        trace_name=trace_name,
        provider=provider,
        label=label,
        question_set=question_set,
        slug=slug,
        operating_point=operating_point,
        operating_point_source=source,
        note=note,
    )


RUNS: tuple[RunSpec, ...] = (
    # gold-v0.1: the order here is the provider order on the case pages.
    _run(
        "gold-v0.1",
        "run_20260925T170857Z_b95be9",
        "jev",
        "Jev q-v0.2",
        "q-v0.2",
        "jev-q-v0.2",
        0.89,
        _DEV2,
    ),
    _run(
        "gold-v0.1",
        "run_20260927T072623Z_ad6f44",
        "jev",
        "Jev q-v0.3",
        "q-v0.3",
        "jev-q-v0.3",
        0.81,
        _DEV3,
        note="Gold is not a blind test for q-v0.3: the question set was motivated by GOLD-TMP-17.",
    ),
    _run(
        "gold-v0.1",
        "run_20260926T011730Z_f1852f",
        "claude",
        "Claude",
        "q-v0.2+claude-prompt-v1",
        "claude",
        0.55,
        _DEV2,
        note="Claude's probabilities are self-reported; gold labels were written by Claude agents.",
    ),
    _run(
        "gold-v0.1",
        "run_20260925T170839Z_d3b427",
        "rules",
        "Rules",
        "rules-v0.1",
        "rules",
        0.99,
        _DEV2,
        note="Rules probabilities are 0, 0.5 or 1 and are not calibrated.",
    ),
    _run(
        "gold-v0.1",
        "run_20260925T170825Z_440df0",
        "groundtruth",
        "Ground truth",
        "groundtruth",
        "groundtruth",
        None,
        _RECORDED,
        note="Ground truth is a pipeline check, not a model result.",
    ),
    # smoke-v0.1
    _run(
        "smoke-v0.1",
        "run_20260925T042324Z_eee114",
        "jev",
        "Jev q-v0.1",
        "q-v0.1",
        "jev-q-v0.1",
        None,
        _RECORDED,
        trace_name="run_20260925T042324Z_eee114.jsonl",
        note="The reference smoke run, made with q-v0.1 before q-v0.2 was adopted.",
    ),
    _run(
        "smoke-v0.1",
        "run_20260925T131052Z_f328de",
        "claude",
        "Claude",
        "q-v0.2+claude-prompt-v1",
        "claude",
        0.55,
        _DEV2,
    ),
    _run(
        "smoke-v0.1",
        "run_20260925T092347Z_cca17f",
        "rules",
        "Rules",
        "rules-v0.1",
        "rules",
        0.99,
        _DEV2,
    ),
    # gen-v0.2-dev
    _run(
        "gen-v0.2-dev",
        "run_20260925T071231Z_6f0b73",
        "jev",
        "Jev q-v0.2",
        "q-v0.2",
        "jev-q-v0.2",
        0.89,
        _DEV2,
    ),
    _run(
        "gen-v0.2-dev",
        "run_20260925T071157Z_d6b218",
        "jev",
        "Jev q-v0.1",
        "q-v0.1",
        "jev-q-v0.1",
        None,
        _RECORDED,
        note="Replaced by q-v0.2 under the dev adoption rule.",
    ),
    _run(
        "gen-v0.2-dev",
        "run_20260925T191752Z_288946",
        "claude",
        "Claude",
        "q-v0.2+claude-prompt-v1",
        "claude",
        0.55,
        _DEV2,
    ),
    _run(
        "gen-v0.2-dev",
        "run_20260925T092358Z_36888d",
        "rules",
        "Rules",
        "rules-v0.1",
        "rules",
        0.99,
        _DEV2,
    ),
    # gen-v0.2-holdout
    _run(
        "gen-v0.2-holdout",
        "run_20260925T075242Z_fd455f",
        "jev",
        "Jev q-v0.2",
        "q-v0.2",
        "jev-q-v0.2",
        0.89,
        _DEV2,
    ),
    _run(
        "gen-v0.2-holdout",
        "run_20260925T212034Z_bbee49",
        "claude",
        "Claude (150-case sample)",
        "q-v0.2+claude-prompt-v1",
        "claude-150",
        0.55,
        _DEV2,
        note="A 150-case sample (seed 7), so it is not in the headline table.",
    ),
    _run(
        "gen-v0.2-holdout",
        "run_20260925T092425Z_0aee97",
        "rules",
        "Rules",
        "rules-v0.1",
        "rules",
        0.99,
        _DEV2,
    ),
    # gen-v0.3-dev
    _run(
        "gen-v0.3-dev",
        "run_20260927T071912Z_cdaf0c",
        "jev",
        "Jev q-v0.3",
        "q-v0.3",
        "jev-q-v0.3",
        0.81,
        _DEV3,
    ),
    _run(
        "gen-v0.3-dev",
        "run_20260927T071846Z_e950c0",
        "jev",
        "Jev q-v0.2",
        "q-v0.2",
        "jev-q-v0.2",
        0.97,
        _DEV3,
    ),
    # gen-v0.3-holdout
    _run(
        "gen-v0.3-holdout",
        "run_20260927T072144Z_12e1e4",
        "jev",
        "Jev q-v0.3",
        "q-v0.3",
        "jev-q-v0.3",
        0.81,
        _DEV3,
    ),
    _run(
        "gen-v0.3-holdout",
        "run_20260927T072249Z_204814",
        "jev",
        "Jev q-v0.2",
        "q-v0.2",
        "jev-q-v0.2",
        0.97,
        _DEV3,
    ),
    # gen-v0.3-shift (scored against immunara-v0.2 labels at the recorded 0.95)
    _run(
        "gen-v0.3-shift",
        "aware-immunara-v0.2",
        "jev",
        "Jev q-v0.3, aware (v0.2)",
        "q-v0.3",
        "jev-q-v0.3-aware",
        None,
        _RECORDED,
        run_id="run_20260927T072949Z_bd430c",
        note="The stored answers composed under immunara-v0.2.",
    ),
    _run(
        "gen-v0.3-shift",
        "stale-immunara-v0.1",
        "jev",
        "Jev q-v0.3, stale (v0.1)",
        "q-v0.3",
        "jev-q-v0.3-stale",
        None,
        _RECORDED,
        run_id="run_20260927T072948Z_e5915e",
        note="The same stored answers composed under the old immunara-v0.1.",
    ),
    _run(
        "gen-v0.3-shift",
        "run_20260927T072915Z_007c7c",
        "jev",
        "Jev q-v0.3",
        "q-v0.3",
        "jev-q-v0.3",
        None,
        _RECORDED,
        note="The paid run both recompositions reuse.",
    ),
    _run(
        "gen-v0.3-shift",
        "run_20260927T073019Z_81a068",
        "rules",
        "Rules",
        "rules-v0.1",
        "rules",
        None,
        _RECORDED,
        note="rules-v0.1 has no recency rule.",
    ),
)

# The README headline table, in its row order.
HEADLINE: tuple[tuple[str, str | None], ...] = (
    ("run_20260925T075242Z_fd455f", None),
    ("run_20260925T092425Z_0aee97", None),
    ("run_20260927T072144Z_12e1e4", None),
    ("run_20260925T170857Z_b95be9", None),
    ("run_20260926T011730Z_f1852f", None),
    ("run_20260925T170839Z_d3b427", None),
    ("run_20260927T072623Z_ad6f44", "not blind"),
)

# The two cases the home page links to.
EASY_CASE = "GOLD-STR-01"
HARD_CASE = "GOLD-CON-03"

_V2 = "run_20260925T170857Z_b95be9"
_V3 = "run_20260927T072623Z_ad6f44"
_ABLATED_V3 = f"{BASELINES}/ablation/gold-v0.1/jev-q-v0.3/contradiction/traces.jsonl.gz"

DIFFS: tuple[DiffSpec, ...] = (
    DiffSpec(
        "GOLD-TMP-17",
        "q-v0.2 to q-v0.3",
        _V2,
        _V3,
        None,
        "Jev q-v0.3 @0.81",
        "q-v0.2 has one start and one end date, so it reads the interrupted course as one "
        "133-day course and automates it. q-v0.3 can express the pause.",
    ),
    DiffSpec(
        "GOLD-TMP-18",
        "q-v0.2 to q-v0.3",
        _V2,
        _V3,
        None,
        "Jev q-v0.3 @0.81",
        "The later segment alone clears 12 weeks; q-v0.3 sees the restart and still approves.",
    ),
    DiffSpec(
        "GOLD-TMP-16",
        "q-v0.2 to q-v0.3",
        _V2,
        _V3,
        None,
        "Jev q-v0.3 @0.81",
        "No judgment moves by more than 0.03. The lower 0.81 bar lets the case through, and the "
        "missing-evidence gate has nothing to act on because Jev answers NONE.",
    ),
    DiffSpec(
        "GOLD-CON-03",
        "Contradiction gate removed",
        _V3,
        None,
        _ABLATED_V3,
        "Jev q-v0.3 @0.81, contradiction gate ablated",
        "The two sources disagree on how long methotrexate ran. Without the contradiction gate "
        "the engine automates the case.",
    ),
    DiffSpec(
        "GOLD-CON-13",
        "Contradiction gate removed",
        _V3,
        None,
        _ABLATED_V3,
        "Jev q-v0.3 @0.81, contradiction gate ablated",
        "Newly unsafe for all three model providers when contradiction detection is removed.",
    ),
)

GATES_CONFIG = "evals/regression/gates.json"
WAIVER_EXAMPLE = "evals/regression/examples/waiver-tmp17.json"
RESULTS_URL = "https://github.com/Souprem/Relay/blob/main/docs/RESULTS.md"


def run_spec(run_id: str) -> RunSpec:
    for spec in RUNS:
        if spec.run_id == run_id:
            return spec
    raise KeyError(f"no registered run {run_id!r}")


def dataset_spec(dataset_id: str) -> DatasetSpec:
    for spec in DATASETS:
        if spec.id == dataset_id:
            return spec
    raise KeyError(f"no registered dataset {dataset_id!r}")
