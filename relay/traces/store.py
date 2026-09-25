"""Append-only JSONL trace files, one per run, plus a write-once run manifest."""

import gzip
import secrets
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

from relay.traces.models import RunManifest, WorkflowTrace


def new_run_id(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return f"run_{now:%Y%m%dT%H%M%SZ}_{secrets.token_hex(3)}"


def new_trace_id() -> str:
    return f"tr_{uuid.uuid4().hex}"


def current_git_sha(cwd: Path | None = None) -> str | None:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=cwd
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return f"{sha}-dirty" if dirty else sha


class TraceStore:
    """Traces are only ever appended; existing lines are never rewritten."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def create(cls, root: Path, run_id: str) -> "TraceStore":
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{run_id}.jsonl"
        with path.open("x", encoding="utf-8"):
            pass
        return cls(path)

    def append(self, trace: WorkflowTrace) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(trace.model_dump_json() + "\n")

    def write_manifest(self, manifest: RunManifest) -> Path:
        path = self.path.with_suffix(".manifest.json")
        with path.open("x", encoding="utf-8") as handle:
            handle.write(manifest.model_dump_json(indent=2) + "\n")
        return path


def read_traces(path: Path) -> list[WorkflowTrace]:
    """Read a .jsonl trace file, or a gzipped .jsonl.gz one (committed baselines)."""
    if path.suffix == ".gz":
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                text = handle.read()
        except (OSError, EOFError) as error:
            raise ValueError(f"{path.name}: {error}") from error
    else:
        text = path.read_text(encoding="utf-8")
    return [WorkflowTrace.model_validate_json(line) for line in text.splitlines() if line.strip()]
