"""Export the blind second-pass packet: uv run python -m scripts.gold_blind_export OUT_DIR

OUT_DIR must be empty or absent and outside the repository. It receives cases/CASE-###/ (case.json
with a neutral id, and documents/), RULES.md (the guide's label rules only) and
second_pass.template.json. No ground truth, notes, scenario table or gold ids are exported.
"""

import sys
from pathlib import Path

from tests.gold_tools import export_blind_packet


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m scripts.gold_blind_export OUT_DIR", file=sys.stderr)
        return 2
    try:
        ids = export_blind_packet(Path(argv[0]))
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"exported {len(ids)} blind cases to {Path(argv[0]).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
