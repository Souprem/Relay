"""relay.site questions.json: the question text, hashes and Claude prompt come from the code."""

import relay.decisions.questions as questions_module
from relay.cases.policies import load_policy
from relay.decisions.claude_prompt import (
    CLAUDE_PROMPT_VERSION,
    YEAR_PLACEHOLDER,
    claude_question_set_hash,
    render_system_prompt,
)
from relay.decisions.questions import QUESTION_SET_VERSIONS, build_questions, question_set_hash
from relay.site.questions import questions_compare, questions_page
from relay.site.registry import RESULTS_URL
from tests.site_support import REPO, load


def _sets(site_export):
    return {s["version"]: s for s in load(site_export, "questions.json")["sets"]}


def test_every_question_set_is_exported_with_its_question_count(site_export):
    sets = _sets(site_export)
    assert list(sets) == list(QUESTION_SET_VERSIONS)
    assert sets["q-v0.1"]["count"] == len(sets["q-v0.1"]["questions"]) == 12
    assert sets["q-v0.2"]["count"] == len(sets["q-v0.2"]["questions"]) == 12
    assert sets["q-v0.3"]["count"] == len(sets["q-v0.3"]["questions"]) == 19


def test_the_exported_text_is_what_build_questions_produces(site_export):
    # The placeholder the export uses is the one question_set_hash hashes.
    assert YEAR_PLACEHOLDER == questions_module._YEAR_PLACEHOLDER
    policy = load_policy("immunara-v0.1")
    for version, exported in _sets(site_export).items():
        built = build_questions(policy, [YEAR_PLACEHOLDER], version)
        assert [q["id"] for q in exported["questions"]] == list(built)
        for row in exported["questions"]:
            dumped = built[row["id"]].model_dump(mode="json")
            assert row["type"] == dumped["type"]
            assert row["instructions"] == dumped["instructions"]
            assert {o["option"]: o["text"] for o in row["options"]} == dumped["criteria"]
            assert [o["option"] for o in row["options"]] == list(dumped["criteria"])


def test_the_exported_hashes_are_question_set_hash_under_each_policy(site_export):
    for version, exported in _sets(site_export).items():
        assert exported["hashes"] == [
            {"policy": p, "hash": question_set_hash(load_policy(p), version)}
            for p in ("immunara-v0.1", "immunara-v0.2")
        ]
        # Both policies name the same indication and required therapy, so nothing differs.
        assert exported["same_text_under_all_policies"] is True
        assert exported["same_hash_under_all_policies"] is True
        assert exported["recorded"]["matches"] is True
        assert exported["recorded"]["hashes"] == [exported["hashes"][0]["hash"]]


def test_value_lists_are_summarized_compactly(site_export):
    rows = {q["id"]: q for q in _sets(site_export)["q-v0.3"]["questions"]}
    assert rows["mtx_start_month"]["options_summary"] == "January … December, none"
    assert rows["mtx_pause_day"]["options_summary"] == "1 … 31, none"
    assert rows["mtx_restart_year"]["options_summary"] == "years found in the case, none"
    assert rows["diagnosis_support"]["options_summary"] is None
    assert rows["mtx_end_status"]["options_summary"] == "ended, ongoing, not_stated"


def test_claudes_system_prompt_and_recorded_hash_match_the_code(site_export):
    claude = load(site_export, "questions.json")["claude"]
    policy = load_policy("immunara-v0.1")
    assert claude["question_set"] == "q-v0.2"
    assert claude["prompt_version"] == CLAUDE_PROMPT_VERSION
    assert claude["question_set_version"] == f"q-v0.2+{CLAUDE_PROMPT_VERSION}"
    assert claude["system_prompt"] == render_system_prompt(policy, "q-v0.2")
    assert claude["hash"] == claude_question_set_hash(policy, "q-v0.2")
    assert claude["recorded"]["hashes"] == [claude["hash"]]
    assert claude["recorded"]["matches"] is True


def test_transitions_link_compare_pages_and_cite_results(site_export):
    data = load(site_export, "questions.json")
    assert [t["slug"] for t in data["transitions"]] == ["q-v0.1...q-v0.2", "q-v0.2...q-v0.3"]
    assert set(data["compare"]) >= {t["slug"] for t in data["transitions"]}
    assert "GOLD-TMP-17" in data["transitions"][1]["why"]
    assert "not a blind test" in data["transitions"][1]["why"]
    results = (REPO / "docs" / "RESULTS.md").read_text(encoding="utf-8")
    assert "Gold is not a blind test for q-v0.3" in results
    assert 'counts "never took methotrexate" as documented' in results
    for t in data["transitions"]:
        assert t["source"].startswith(RESULTS_URL + "#")
    assert data["rules"]["source"] == f"{RESULTS_URL}#baselines"


def test_runs_and_case_providers_link_their_question_set(site_export):
    runs = load(site_export, "runs.json")
    for dataset in runs["datasets"]:
        for run in dataset["runs"]:
            assert run["questions_page"] == questions_page(run["question_set"])
    tmp17 = load(site_export, "cases/GOLD-TMP-17.json")
    pages = {p["slug"]: p["questions_page"] for p in tmp17["providers"]}
    assert pages["jev-q-v0.2"] == "q-v0.2"
    assert pages["jev-q-v0.3"] == "q-v0.3"
    assert pages["claude"] == "claude-prompt"
    assert pages["rules"] == "rules"
    assert pages["groundtruth"] is None
    assert tmp17["diffs"][0]["questions_compare"] == "q-v0.2...q-v0.3"
    con03 = load(site_export, "cases/GOLD-CON-03.json")
    assert con03["diffs"][0]["questions_compare"] is None


def test_questions_compare_orders_older_first():
    assert questions_compare("q-v0.3", "q-v0.2") == "q-v0.2...q-v0.3"
    assert questions_compare("q-v0.2", "q-v0.2") is None
    assert questions_compare("q-v0.2", "q-v0.2+claude-prompt-v1") is None
