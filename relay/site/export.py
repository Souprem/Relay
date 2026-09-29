"""relay export-site: write the dashboard's JSON data from committed artifacts.

Offline (no provider client, no key) and deterministic: sorted keys, stable ordering, and no
timestamp except the caller's `exported_at`.
"""

import shutil
from pathlib import Path

from relay.site.common import ExportError
from relay.site.core import export_core
from relay.site.experiments import export_experiments
from relay.site.gates import export_gates
from relay.site.questions import export_questions


def prepare_out(out: Path) -> None:
    """Start from an empty output directory. An existing one is cleared only when it is empty or
    holds a previous export (index.json), so a mistyped --out never deletes unrelated files."""
    if out.exists():
        if not out.is_dir():
            raise ExportError(f"--out {out} is not a directory")
        if any(out.iterdir()) and not (out / "index.json").is_file():
            raise ExportError(f"--out {out} is not empty and holds no previous export")
        shutil.rmtree(out)
    out.mkdir(parents=True)


def export_site(
    repo: Path,
    out: Path,
    *,
    exported_at: str,
    git_sha: str | None,
    strict_generated: bool = False,
) -> list[Path]:
    """Write every data file under `out`; return their paths, sorted."""
    prepare_out(out)
    written, ctx = export_core(repo, out, exported_at=exported_at, git_sha=git_sha)
    written += export_gates(repo, out, ctx, strict_generated=strict_generated)
    written += export_experiments(repo, out, strict_generated=strict_generated)
    written += export_questions(out, ctx)
    return sorted(written)
