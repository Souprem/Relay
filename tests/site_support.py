"""Helpers for the site-export tests: a network guard, an export runner and a fake repository."""

import contextlib
import json
import shutil
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anthropic
import pytest
import typesafe_sdk

import relay.evaluation.tracediff as tracediff
from relay.site.export import export_site

REPO = Path(__file__).resolve().parents[1]
EXPORTED_AT = "2026-09-28T12:00:00Z"
GIT_SHA = "0000000000000000000000000000000000000000"


class NetworkUsed(AssertionError):
    pass


def _refuse(*_args: Any, **_kwargs: Any) -> None:
    raise NetworkUsed("the site export must not touch the network or build a provider client")


@contextlib.contextmanager
def no_network() -> Iterator[None]:
    """Fail on any socket connect or provider-client construction inside the block.

    It also pins the git SHA that replayed traces record (never exported): outside a git
    checkout, such as a fake repository, replay_trace would otherwise run git once per trace.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(tracediff, "current_git_sha", lambda cwd=None: GIT_SHA)
        mp.setattr(socket.socket, "connect", _refuse)
        mp.setattr(socket, "create_connection", _refuse)
        mp.setattr(typesafe_sdk.AsyncTypeSafeClient, "__init__", _refuse)
        mp.setattr(anthropic.AsyncAnthropic, "__init__", _refuse)
        mp.setattr(anthropic.Anthropic, "__init__", _refuse)
        yield


def run_export(out: Path, repo: Path = REPO, **kwargs: Any) -> list[Path]:
    with no_network():
        return export_site(repo, out, exported_at=EXPORTED_AT, git_sha=GIT_SHA, **kwargs)


def load(out: Path, name: str) -> Any:
    return json.loads((out / name).read_text(encoding="utf-8"))


def fake_repo(
    root: Path,
    *,
    copy_gold: bool = False,
    omit: tuple[str, ...] = (),
    with_generated: bool = False,
) -> Path:
    """A repository skeleton under `root` that links to the real committed inputs.

    evals/gold is copied (so a test may edit it) when copy_gold is set; every other input is a
    symlink. `omit` names relative paths to leave out (for example "evals/smoke" or
    "evals/baselines/smoke-v0.1"). evals/generated is linked only with with_generated.
    """
    evals = root / "evals"
    (evals / "baselines").mkdir(parents=True)
    for child in sorted((REPO / "evals" / "baselines").iterdir()):
        relative = f"evals/baselines/{child.name}"
        if relative not in omit:
            (evals / "baselines" / child.name).symlink_to(child)
    for name in ("smoke", "regression"):
        if f"evals/{name}" not in omit:
            (evals / name).symlink_to(REPO / "evals" / name)
    if "evals/gold" not in omit:
        if copy_gold:
            shutil.copytree(REPO / "evals" / "gold", evals / "gold")
        else:
            (evals / "gold").symlink_to(REPO / "evals" / "gold")
    if with_generated:
        (evals / "generated").symlink_to(REPO / "evals" / "generated")
    (root / "scripts").symlink_to(REPO / "scripts")
    return root
