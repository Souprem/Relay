"""Check gold cases against the authoring guide: uv run python -m scripts.gold_check [CAT ...]

CAT is one of STR MIS CON TMP TRK. With no argument it checks every category and the whole set.
Prints one summary line per case (derived action and labels vs the scenario table), then every
problem. Exit 0 when there are no problems, 1 when there are, 2 for a bad argument.
"""

import sys

from tests.gold_support import (
    CATEGORIES,
    case_problems,
    case_summary,
    category_problems,
    present_case_dirs,
    set_problems,
)


def main(argv: list[str]) -> int:
    unknown = [arg for arg in argv if arg not in CATEGORIES]
    if unknown:
        print(f"unknown category {unknown}; choose from {list(CATEGORIES)}", file=sys.stderr)
        return 2
    problems: list[str] = []
    for category in argv or list(CATEGORIES):
        dirs = [d for d in present_case_dirs() if d.name.startswith(f"GOLD-{category}-")]
        print(f"== GOLD-{category}: {len(dirs)} case directories")
        for case_dir in dirs:
            print("  " + case_summary(case_dir))
            problems += case_problems(case_dir)
        if dirs:
            problems += category_problems(category)
    if not argv:
        problems += set_problems()
    for problem in problems:
        print(f"PROBLEM: {problem}")
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
