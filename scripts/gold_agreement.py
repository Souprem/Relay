"""Second-pass import and agreement for gold-v0.1.

uv run python -m scripts.gold_agreement import BLIND_FILE
    Validate the reviewer's file, map CASE-### ids back, write evals/gold/second_pass.json.
uv run python -m scripts.gold_agreement report
    Write the pre-adjudication snapshot evals/gold/agreement.json (refuses to overwrite) and
    print the agreement table.
uv run python -m scripts.gold_agreement post
    Print agreement of the second pass with the CURRENT (post-adjudication) labels; writes nothing.
"""

import json
import sys
from pathlib import Path

from relay.cases.loader import load_dataset
from tests.gold_support import GOLD_DIR
from tests.gold_tools import agreement_markdown, compute_agreement, import_second_pass

SECOND_PASS = GOLD_DIR / "second_pass.json"
AGREEMENT = GOLD_DIR / "agreement.json"


def _summary(result: dict) -> str:
    cases = len({d["case_id"] for d in result["disagreements"]})
    return f"{len(result['disagreements'])} fact disagreement(s) in {cases} case(s)"


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "import":
        try:
            data = import_second_pass(json.loads(Path(argv[1]).read_text(encoding="utf-8")))
        except (ValueError, OSError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        SECOND_PASS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {SECOND_PASS} ({len(data['labels'])} cases)")
        return 0
    if argv in (["report"], ["post"]):
        second = json.loads(SECOND_PASS.read_text(encoding="utf-8"))
        result = compute_agreement(load_dataset(GOLD_DIR), second)
        if argv == ["report"]:
            if AGREEMENT.exists():
                print(
                    f"error: {AGREEMENT} is the pre-adjudication snapshot; refusing to overwrite",
                    file=sys.stderr,
                )
                return 2
            AGREEMENT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(agreement_markdown(result))
        print(f"\n{_summary(result)}" + (f"; wrote {AGREEMENT}" if argv == ["report"] else ""))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
