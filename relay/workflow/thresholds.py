"""Versioned autonomy thresholds. Tune on held-out data; never treat as truth."""

from pydantic import BaseModel, ConfigDict


class Thresholds(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    auto_process: float
    contradiction_review: float
    contradiction_auto_block: float
    documentation_request_info: float
    missing_evidence_request_info: float


THRESHOLDS_V0_1 = Thresholds(
    version="v0.1",
    auto_process=0.95,
    contradiction_review=0.80,
    contradiction_auto_block=0.20,
    documentation_request_info=0.60,
    missing_evidence_request_info=0.70,
)

_BY_VERSION = {THRESHOLDS_V0_1.version: THRESHOLDS_V0_1}


def load_thresholds(version: str) -> Thresholds:
    try:
        return _BY_VERSION[version]
    except KeyError:
        raise KeyError(
            f"unknown thresholds version {version!r}; known: {sorted(_BY_VERSION)}"
        ) from None


def override_auto_process(thresholds: Thresholds, auto_process: float) -> Thresholds:
    """`thresholds` with auto_process replaced, and a version that records the override.

    v0.1 becomes v0.1+at0.89. An earlier override is replaced rather than stacked, so
    v0.1+at0.89 overridden to 0.9 becomes v0.1+at0.9. Every other threshold is unchanged.
    """
    base = thresholds.version.split("+at", 1)[0]
    return thresholds.model_copy(
        update={"auto_process": auto_process, "version": f"{base}+at{auto_process:g}"}
    )
