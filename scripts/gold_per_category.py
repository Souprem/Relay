"""Per-category gold results: uv run python -m scripts.gold_per_category LABEL=RUN_DIR [...]

RUN_DIR is a committed run directory containing results.json. Prints one Markdown table.
"""

import json
import sys
from pathlib import Path

from tests.gold_tools import per_category_markdown


def main(argv: list[str]) -> int:
    runs = []
    for arg in argv:
        label, sep, path = arg.partition("=")
        if not sep:
            print(f"expected LABEL=RUN_DIR, got {arg!r}", file=sys.stderr)
            return 2
        runs.append((label, json.loads((Path(path) / "results.json").read_text(encoding="utf-8"))))
    if not runs:
        print(__doc__, file=sys.stderr)
        return 2
    print(per_category_markdown(runs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
