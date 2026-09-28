"""Shared Jev test doubles: raw answer builders, q-v0.3 payloads and a generic fake client.

No network and no real key. Every value is synthetic.
"""

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from typesafe_sdk import Noul, SystemOneResponse

REPO = Path(__file__).resolve().parents[1]
AUTO01_FIXTURE = REPO / "tests" / "fixtures" / "jev" / "auto01_response.json"
DATE_PARTS = ("month", "day", "year")


def raw_noul(p_yes: float) -> dict[str, Any]:
    return {"type": "noul", "noul": p_yes}


def raw_choice(answer: str, probability: float = 1.0) -> dict[str, Any]:
    return {
        "type": "choice",
        "choice": answer,
        "confidence": probability,
        "probabilities": {answer: probability},
    }


def raw_date(prefix: str, month: str, day: str, year: str) -> dict[str, dict[str, Any]]:
    """Certain date-part answers, e.g. raw_date("mtx_pause", "February", "23", "2026")."""
    values = dict(zip(DATE_PARTS, (month, day, year), strict=True))
    return {f"{prefix}_{part}": raw_choice(values[part]) for part in DATE_PARTS}


# q-v0.3's seven extra answers for a course that was never interrupted.
NOT_INTERRUPTED: dict[str, dict[str, Any]] = {
    "mtx_interrupted": raw_noul(0.02),
    **raw_date("mtx_pause", "none", "none", "none"),
    **raw_date("mtx_restart", "none", "none", "none"),
}


def q_v0_3_payload(**answers: dict[str, Any]) -> dict[str, Any]:
    """The AUTO-01 fixture response (methotrexate 2026-01-12 -> 2026-06-01, ended, inadequate
    response) plus q-v0.3's interruption answers; keyword answers replace any answer by id."""
    payload = json.loads(AUTO01_FIXTURE.read_text())
    payload["answers"] = payload["answers"] | NOT_INTERRUPTED | answers
    return payload


def generic_answers(questions: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """A well-formed answer for any question set: 0.5 for a Noul, the first option otherwise."""
    return {
        qid: raw_noul(0.5) if isinstance(q, Noul) else raw_choice(next(iter(q.criteria)))
        for qid, q in questions.items()
    }


class GenericSystemOneClient:
    """Answers whatever questions it is sent. input_tokens = base + per_question * len(questions),
    so cost grows with the question count. `on_call(questions)` runs before each answer (a test
    uses it to advance a fake clock). Every call is recorded in `calls`."""

    def __init__(
        self,
        *,
        base_tokens: int = 1000,
        tokens_per_question: int = 50,
        on_call: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> None:
        self.base_tokens = base_tokens
        self.tokens_per_question = tokens_per_question
        self.on_call = on_call
        self.calls: list[dict[str, Any]] = []

    async def system_one(
        self, state: Any, questions: Mapping[str, Any], *, model: str | None = None, **kwargs: Any
    ) -> SystemOneResponse:
        self.calls.append({"state": state, "questions": dict(questions), "model": model})
        if self.on_call is not None:
            self.on_call(questions)
        tokens = self.base_tokens + self.tokens_per_question * len(questions)
        return SystemOneResponse.model_validate(
            {
                "model": model or "jev-1.13.0",
                "answers": generic_answers(questions),
                "usage": {"input_tokens": tokens, "output_tokens": 10},
            }
        )
