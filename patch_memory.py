"""
Patch memory.md in-place while preserving its original line endings (CRLF).
"""

import re
import sys

PATH = "memory.md"

NEW_COMMIT_HASH = "6b7f0a4"
NEW_COMMIT_ROW = (
    "| `{hash}` | Consolidate 2013-2026 auction history from Kaggle source "
    "with schema-drift handling | Phase 1.1 |"
).format(hash=NEW_COMMIT_HASH)

OLD_NEXT_ACTION_MARKER = "NEXT ACTION: Implement local package setup"
NEW_NEXT_ACTION_BLOCK = (
    "CURRENT PHASE: Phase 1 — Data Ingestion\n"
    "CURRENT SUBPHASE: 1.1 — Auction History Consolidation\n"
    "NEXT ACTION: Validate franchise-total-vs-purse-cap consistency for the "
    "consolidated auction dataset (see Known Issues); add data_sources.yaml "
    "entry review to CI.\n"
    "BLOCKERS: None"
)


def patch(text: str) -> str:
    if NEW_COMMIT_HASH not in text:
        text = re.sub(
            r"(\| `21894a7` \|[^\n]*\|\n)",
            r"\1" + NEW_COMMIT_ROW + "\n",
            text,
            count=1,
        )

    if OLD_NEXT_ACTION_MARKER in text:
        text = re.sub(
            r"CURRENT PHASE:.*?BLOCKERS: None",
            NEW_NEXT_ACTION_BLOCK,
            text,
            count=1,
            flags=re.DOTALL,
        )

    return text


def main():
    with open(PATH, "r", encoding="cp1252", newline="") as f:
        original = f.read()

    updated = patch(original)

    if updated == original:
        print("No changes made — markers not found. Check memory.md contents by hand.")
        sys.exit(1)

    with open(PATH, "w", encoding="cp1252", newline="") as f:
        f.write(updated)

    print("memory.md patched. Run `git diff --stat memory.md` to confirm only "
          "the intended lines changed (line endings preserved).")


if __name__ == "__main__":
    main()
