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
}


def load_policy(policy_id: str) -> AuthorizationPolicy:
    try:
        spec = dict(_POLICIES[policy_id])
    except KeyError:
        raise KeyError(f"unknown policy {policy_id!r}; known: {sorted(_POLICIES)}") from None
    text = (POLICY_DIR / str(spec.pop("text_file"))).read_text(encoding="utf-8")
    return AuthorizationPolicy.model_validate({"id": policy_id, "text": text, **spec})
