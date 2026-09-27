"""override_auto_process: one helper for every --at style override (F1 / 3A Minor 2)."""

from relay.workflow.thresholds import (
    THRESHOLDS_V0_1,
    THRESHOLDS_V0_2,
    load_thresholds,
    override_auto_process,
)


def test_the_override_replaces_auto_process_and_records_it_in_the_version():
    overridden = override_auto_process(THRESHOLDS_V0_1, 0.89)
    assert overridden.auto_process == 0.89
    assert overridden.version == "v0.1+at0.89"
    assert overridden.model_dump(exclude={"auto_process", "version"}) == (
        THRESHOLDS_V0_1.model_dump(exclude={"auto_process", "version"})
    )
    assert THRESHOLDS_V0_1.version == "v0.1" and THRESHOLDS_V0_1.auto_process == 0.95


def test_a_second_override_replaces_the_first_rather_than_stacking():
    twice = override_auto_process(override_auto_process(THRESHOLDS_V0_1, 0.89), 0.9)
    assert twice.version == "v0.1+at0.9"
    assert twice.auto_process == 0.9


def test_an_override_to_the_same_value_is_still_labelled():
    assert override_auto_process(THRESHOLDS_V0_1, 0.95).version == "v0.1+at0.95"


def test_v0_2_thresholds_are_v0_1_values_under_their_own_version():
    assert load_thresholds("v0.2") is THRESHOLDS_V0_2
    assert THRESHOLDS_V0_2.version == "v0.2"
    assert THRESHOLDS_V0_2.model_dump(exclude={"version"}) == THRESHOLDS_V0_1.model_dump(
        exclude={"version"}
    )
