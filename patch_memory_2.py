"""
Patch memory.md: log the purse-cap ceiling validation as complete and advance
the Current Next Action block. Preserves CRLF line endings (cp1252 encoded).
"""

import re
import sys

PATH = "memory.md"

NEW_COMMIT_HASH = "19053dd"
NEW_COMMIT_ROW = (
    "| `{hash}` | Add purse-cap ceiling validation (src/validation/purse_cap_check.py) "
    "and configs/purse_caps.yaml; 0 violations across 52 checked franchise-years | Phase 1.2 |"
).format(hash=NEW_COMMIT_HASH)

OLD_NEXT_ACTION_MARKER = "Validate franchise-total-vs-purse-cap consistency"
NEW_NEXT_ACTION_BLOCK = (
    "CURRENT PHASE: Phase 1 — Data Ingestion\n"
    "CURRENT SUBPHASE: 1.2 — Auction Data Quality Validation\n"
    "NEXT ACTION: [fill in your actual next step here]\n"
    "BLOCKERS: Purse-cap reference table (configs/purse_caps.yaml) has confirmed "
    "figures for 6 of 13 years only (2013, 2015-2016, 2019, 2021-2023, 2026 unconfirmed); "
    "not a blocker for current validation (skipped, not failed) but should be closed "
    "before this check is relied on for automated CI gating."
)


def patch(text: str) -> str:
    if NEW_COMMIT_HASH not in text:
        text = re.sub(
            r"(\| `6b7f0a4` \|[^\n]*\|\n)",
            r"\1" + NEW_COMMIT_ROW + "\n",
            text,
            count=1,
        )

    if OLD_NEXT_ACTION_MARKER in text:
        text = re.sub(
            r"CURRENT PHASE:.*?BLOCKERS:[^\n]*",
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
          "a handful of lines changed.")


if __name__ == "__main__":
    main()
