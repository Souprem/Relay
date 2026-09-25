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
