"""Versioned synthetic authorization policies."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict

POLICY_DIR = Path(__file__).resolve().parents[2] / "policies"


class AuthorizationPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    version: str
    medication: str
    indication: str
    min_age: int
    required_therapy: str
    min_weeks: int
    text: str
    # Recency (immunara-v0.2): the qualifying course must be ongoing or have ended at most this
    # many days before the request's as_of_date. None (immunara-v0.1) means no recency rule.
    max_days_since_therapy: int | None = None


_POLICIES: dict[str, dict[str, object]] = {
    "immunara-v0.1": {
        "version": "v0.1",
        "medication": "Immunara",
        "indication": "rheumatoid arthritis",
        "min_age": 18,
        "required_therapy": "methotrexate",
        "min_weeks": 12,
        "text_file": "immunara-v0.1.md",
    },
    "immunara-v0.2": {
        "version": "v0.2",
        "medication": "Immunara",
        "indication": "rheumatoid arthritis",
        "min_age": 18,
        "required_therapy": "methotrexate",
        "min_weeks": 12,
        "max_days_since_therapy": 365,
        "text_file": "immunara-v0.2.md",
    },
}


def load_policy(policy_id: str) -> AuthorizationPolicy:
    try:
        spec = dict(_POLICIES[policy_id])
    except KeyError:
        raise KeyError(f"unknown policy {policy_id!r}; known: {sorted(_POLICIES)}") from None
    text = (POLICY_DIR / str(spec.pop("text_file"))).read_text(encoding="utf-8")
    return AuthorizationPolicy.model_validate({"id": policy_id, "text": text, **spec})


def _version_key(version: str) -> tuple[int, ...]:
    """'v0.10' -> (0, 10): versions compare numerically, so v0.10 sorts after v0.9."""
    return tuple(int(part) for part in version.removeprefix("v").split("."))


def latest_policy_for(policy_id: str) -> str:
    """The id of the registered policy for the same medication with the highest version."""
    try:
        medication = _POLICIES[policy_id]["medication"]
    except KeyError:
        raise KeyError(f"unknown policy {policy_id!r}; known: {sorted(_POLICIES)}") from None
    same = [pid for pid, spec in _POLICIES.items() if spec["medication"] == medication]
    return max(same, key=lambda pid: _version_key(str(_POLICIES[pid]["version"])))
