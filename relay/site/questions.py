"""questions.json: the exact questions each provider was asked, rendered from the code.

Every Jev question set comes from build_questions() and is hashed with question_set_hash(), the
same calls the Jev provider makes. Claude's system prompt is render_system_prompt() for the question
set its committed traces record. The hashes those traces record are exported beside the computed
ones, so the page shows whether the code still produces what was sent.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.decisions.claude_prompt import (
    CLAUDE_PROMPT_VERSION,
    CLAUDE_QUESTION_SETS,
    YEAR_PLACEHOLDER,
    claude_question_set_hash,
    claude_question_set_version,
    render_system_prompt,
)
from relay.decisions.questions import (
    DEFAULT_QUESTION_SET_VERSION,
    Q_V0_1,
    Q_V0_2,
    Q_V0_3,
    QUESTION_SET_VERSIONS,
    build_questions,
    question_ids,
    question_set_hash,
)
from relay.site.common import ExportContext, ExportError, write_json
from relay.site.registry import RESULTS_URL, RUNS

# The policy every question set is rendered under, and the other one it is checked against.
PRIMARY_POLICY = "immunara-v0.1"
POLICY_IDS: tuple[str, ...] = ("immunara-v0.1", "immunara-v0.2")
YEAR_DISPLAY = "years found in the case"
CLAUDE_PAGE = "claude-prompt"
RULES_PAGE = "rules"
LATEST_QUESTION_SET = Q_V0_3

# Why each question set replaced the one before it (docs/RESULTS.md, "Evaluation" and
# "Question set q-v0.3 (interrupted courses)").
TRANSITIONS: tuple[dict[str, str], ...] = (
    {
        "from": Q_V0_1,
        "to": Q_V0_2,
        "why": (
            "q-v0.2 rewords two criteria, documentation_complete's yes criterion and "
            "missing_evidence's TREATMENT_HISTORY option, so that a record stating the patient "
            "never took methotrexate counts as documented treatment history. It was adopted on "
            "gen-v0.2-dev by a rule fixed in advance (330/400 correct against q-v0.1's 257/400, "
            "0 unsafe for both); RESULTS.md notes that part of the gain is alignment with the "
            "generator's own labelling convention for never-taken methotrexate."
        ),
        "source": f"{RESULTS_URL}#evaluation",
    },
    {
        "from": Q_V0_2,
        "to": Q_V0_3,
        "why": (
            "q-v0.3 adds seven questions for an interrupted course, prompted by GOLD-TMP-17: "
            "q-v0.2 has one start and one end date, so it read that held-and-restarted course as "
            "one 133-day course and both Jev and Claude auto-approved it. q-v0.3 was developed on "
            "gen-v0.3-dev and evaluated once on gen-v0.3-holdout; gold is not a blind test for it "
            "on GOLD-TMP-17 and GOLD-TMP-18."
        ),
        "source": f"{RESULTS_URL}#question-set-q-v03-interrupted-courses",
    },
)

RULES_NOTE = (
    "rules-v0.1 sends no prompt. It is a deterministic provider that matches keyword patterns and "
    'fixed phrases (for example "never tried methotrexate" or "inadequate response") and checks '
    "the member-ID field; the same policy engine and thresholds then decide the action."
)


def compare_slug(a: str, b: str) -> str:
    return f"{a}...{b}"


def questions_page(question_set: str) -> str | None:
    """The /questions/ page for a recorded question_set_version: a Jev set, Claude's prompt, the
    rules note, or None (ground truth asks nothing)."""
    if question_set in QUESTION_SET_VERSIONS:
        return question_set
    if question_set.endswith(f"+{CLAUDE_PROMPT_VERSION}"):
        return CLAUDE_PAGE
    if question_set.startswith("rules-"):
        return RULES_PAGE
    return None


def questions_compare(original: str, candidate: str) -> str | None:
    """The compare page for two Jev question sets, older first; None when they are the same."""
    if original == candidate or not {original, candidate} <= set(QUESTION_SET_VERSIONS):
        return None
    a, b = sorted((original, candidate), key=QUESTION_SET_VERSIONS.index)
    return compare_slug(a, b)


def _options_summary(options: Sequence[dict[str, Any]]) -> str:
    """Every option in order, with each run of options that carry no criterion text collapsed to
    "first … last": "January … December, none"."""
    parts: list[str] = []
    run: list[str] = []

    def flush() -> None:
        if len(run) > 2:
            parts.append(f"{run[0]} … {run[-1]}")
        else:
            parts.extend(run)
        run.clear()

    for option in options:
        label = YEAR_DISPLAY if option["option"] == YEAR_PLACEHOLDER else option["option"]
        if option["text"] is None:
            run.append(label)
        else:
            flush()
            parts.append(label)
    flush()
    return ", ".join(parts)


def question_rows(policy: AuthorizationPolicy, version: str) -> list[dict[str, Any]]:
    """Each question as sent: id, type, instructions verbatim and every option with its criterion
    text (None where the option has none). Years are the placeholder question_set_hash uses."""
    rows = []
    for qid, question in build_questions(policy, [YEAR_PLACEHOLDER], version).items():
        dumped = question.model_dump(mode="json")
        options = [{"option": k, "text": v} for k, v in dumped["criteria"].items()]
        rows.append(
            {
                "id": qid,
                "type": dumped["type"],
                "instructions": dumped["instructions"],
                "options": options,
                "options_summary": None if dumped["type"] == "noul" else _options_summary(options),
            }
        )
    return rows


def _recorded(ctx: ExportContext) -> dict[str, dict[str, Any]]:
    """question_set_version -> the hashes and policies its committed traces record."""
    seen: dict[str, dict[str, Any]] = {}
    for loaded in ctx.loaded_runs.values():
        for trace in loaded.recorded:
            entry = seen.setdefault(
                trace.question_set_version, {"hashes": set(), "policies": set(), "traces": 0}
            )
            entry["hashes"].add(trace.question_set_hash)
            entry["policies"].add(trace.policy_id)
            entry["traces"] += 1
    return seen


def _recorded_json(entry: dict[str, Any] | None, computed: str) -> dict[str, Any] | None:
    if entry is None:
        return None
    hashes = sorted(entry["hashes"])
    return {
        "hashes": hashes,
        "policies": sorted(entry["policies"]),
        "traces": entry["traces"],
        "matches": hashes == [computed],
    }


def _used_by(match: Any) -> list[dict[str, str]]:
    return [
        {"run_id": r.run_id, "label": r.label, "dataset": r.dataset}
        for r in RUNS
        if match(r.question_set)
    ]


def question_set_json(version: str, recorded: dict[str, dict[str, Any]]) -> dict[str, Any]:
    policies = {p: load_policy(p) for p in POLICY_IDS}
    primary = policies[PRIMARY_POLICY]
    rows = question_rows(primary, version)
    hashes = [
        {"policy": p, "hash": question_set_hash(policy, version)} for p, policy in policies.items()
    ]
    same_text = all(question_rows(policy, version) == rows for policy in policies.values())
    computed = hashes[0]["hash"]
    return {
        "version": version,
        "count": len(rows),
        "ids": list(question_ids(version)),
        "policy": PRIMARY_POLICY,
        "hashes": hashes,
        "same_text_under_all_policies": same_text,
        "same_hash_under_all_policies": len({h["hash"] for h in hashes}) == 1,
        "recorded": _recorded_json(recorded.get(version), computed),
        "used_by": _used_by(lambda qs, v=version: qs == v),
        "questions": rows,
    }


def claude_json(ctx: ExportContext, recorded: dict[str, dict[str, Any]]) -> dict[str, Any]:
    claude_versions = sorted(
        {
            t.question_set_version
            for loaded in ctx.loaded_runs.values()
            if loaded.spec.provider == "claude"
            for t in loaded.recorded
        }
    )
    if len(claude_versions) != 1:
        raise ExportError(f"expected one Claude question set version, found {claude_versions}")
    recorded_version = claude_versions[0]
    question_set = recorded_version.split("+", 1)[0]
    if question_set not in CLAUDE_QUESTION_SETS:
        raise ExportError(
            f"Claude's traces record {recorded_version}, which the code cannot render"
        )
    entry = recorded[recorded_version]
    if len(entry["policies"]) != 1:
        raise ExportError(f"Claude's traces span policies {sorted(entry['policies'])}")
    policy = load_policy(next(iter(entry["policies"])))
    computed = claude_question_set_hash(policy, question_set)
    return {
        "prompt_version": CLAUDE_PROMPT_VERSION,
        "question_set": question_set,
        "question_set_version": claude_question_set_version(question_set),
        "policy": policy.id,
        "hash": computed,
        "recorded": _recorded_json(entry, computed),
        "used_by": _used_by(lambda qs: qs == recorded_version),
        "system_prompt": render_system_prompt(policy, question_set),
        "hash_covers": (
            "The hash covers exactly what is sent once per policy: the rendered system prompt and "
            "the response schema, with a placeholder for the case-specific years. The user "
            "message is the case JSON, the same state Jev receives."
        ),
    }


def composition_notes() -> dict[str, Any]:
    """How raw answers become the five decisions (relay/decisions/composition.py,
    step_therapy.py), with the policy figures read from the policies themselves."""
    v01, v02 = load_policy("immunara-v0.1"), load_policy("immunara-v0.2")
    assert v01.min_weeks == v02.min_weeks
    weeks, recency = v01.min_weeks, v02.max_days_since_therapy
    return {
        "intro": (
            "Jev and Claude answer the same narrow questions. Code turns the answers into the five "
            "decisions the policy engine reads; only the judgment source differs between providers."
        ),
        "decisions": [
            {
                "decision": "diagnosis_support",
                "text": "p_yes of diagnosis_support, used as it is.",
            },
            {
                "decision": "step_therapy",
                "text": (
                    f"Composed in code: P(a methotrexate course of at least {weeks} weeks) × p_yes "
                    "of mtx_inadequate_response. The model reads date parts; code does all the "
                    "date arithmetic. A month-only date becomes a range and duration is measured "
                    "conservatively, latest possible start to earliest possible end; an unknown "
                    "part, or an end that is not stated, adds no probability toward satisfied. "
                    "Date parts are treated as independent."
                ),
            },
            {
                "decision": "documentation_complete",
                "text": "p_yes of documentation_complete, used as it is.",
            },
            {
                "decision": "material_contradiction",
                "text": "p_yes of material_contradiction, used as it is.",
            },
            {
                "decision": "missing_evidence",
                "text": "The missing_evidence answer and its probability for each of the six labels.",
            },
        ],
        "step_therapy_paths": [
            {
                "versions": [Q_V0_1, Q_V0_2],
                "text": (
                    "One course: the first start to the final end, from mtx_start_*, "
                    "mtx_end_status and mtx_end_*. An ongoing course ends at the request's "
                    "as_of_date."
                ),
            },
            {
                "versions": [Q_V0_3],
                "text": (
                    "Pause and restart segments: p = (1 − p_int) · P(first start → final end) + "
                    "p_int · P(start → pause or restart → end), where p_int is p_yes of "
                    "mtx_interrupted. The two segments are combined by inclusion-exclusion; an "
                    "unknown pause or restart adds nothing."
                ),
            },
        ],
        "recency": (
            f"Under immunara-v0.2 (max_days_since_therapy {recency}) the qualifying course must "
            "also be ongoing or have ended, at its earliest possible end, no more than "
            f"{recency} days before as_of. The rule applies on both paths; immunara-v0.1 has none."
        ),
        "source": "relay/decisions/composition.py, relay/decisions/step_therapy.py",
    }


def policy_note(sets: Sequence[dict[str, Any]]) -> str:
    """Whether the wording depends on the policy: the questions read only the policy's
    indication and required therapy (build_questions)."""
    policies = [load_policy(p) for p in POLICY_IDS]
    named = sorted({(p.indication, p.required_therapy) for p in policies})
    listed = " and ".join(POLICY_IDS)
    if all(s["same_text_under_all_policies"] and s["same_hash_under_all_policies"] for s in sets):
        indication, therapy = named[0]
        return (
            "The questions read only the policy's indication and required therapy. "
            f"{listed} both name {indication} and {therapy}, so every set's wording and hash "
            "are identical under both. immunara-v0.2's recency rule changes how step therapy "
            "is composed, not what is asked."
        )
    return (
        "The questions read the policy's indication and required therapy, which differ between "
        f"{listed}; each set lists its hash under each policy."
    )


def questions_payload(ctx: ExportContext) -> dict[str, Any]:
    recorded = _recorded(ctx)
    sets = [question_set_json(v, recorded) for v in QUESTION_SET_VERSIONS]
    pairs = [
        (a, b) for i, a in enumerate(QUESTION_SET_VERSIONS) for b in QUESTION_SET_VERSIONS[i + 1 :]
    ]
    return {
        "default_version": DEFAULT_QUESTION_SET_VERSION,
        "latest_version": LATEST_QUESTION_SET,
        "primary_policy": PRIMARY_POLICY,
        "policies": list(POLICY_IDS),
        "policy_note": policy_note(sets),
        "year_placeholder": YEAR_PLACEHOLDER,
        "year_display": YEAR_DISPLAY,
        "sets": sets,
        "claude": claude_json(ctx, recorded),
        "rules": {
            "version": "rules-v0.1",
            "text": RULES_NOTE,
            "source": f"{RESULTS_URL}#baselines",
            "used_by": _used_by(lambda qs: qs.startswith("rules-")),
        },
        "composition": composition_notes(),
        "transitions": [t | {"slug": compare_slug(t["from"], t["to"])} for t in TRANSITIONS],
        "compare": [compare_slug(a, b) for a, b in pairs],
    }


def export_questions(out: Path, ctx: ExportContext) -> list[Path]:
    return [write_json(out / "questions.json", questions_payload(ctx))]
