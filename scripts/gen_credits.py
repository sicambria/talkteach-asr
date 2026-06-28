#!/usr/bin/env python3
"""Generate the in-app credits data from project/docs/THIRD_PARTY.md (roadmap #28).

Parses the licence table in project/docs/THIRD_PARTY.md and writes
ui/src/lib/credits.json, which the UI's credits screen renders. Keeping a single
source of truth (the markdown table) means attribution can never drift from the
documented licences. Run it in CI or a pre-release step.

    python scripts/gen_credits.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "project" / "docs" / "THIRD_PARTY.md"
OUT = REPO / "ui" / "src" / "lib" / "credits.json"

# Matches a markdown table row: | **Name** | role | licence |
_ROW = re.compile(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$")


def _clean(cell: str) -> str:
    """Strip markdown emphasis/backticks from a table cell."""
    return re.sub(r"[*`]", "", cell).strip()


def parse_components(md: str) -> list[dict]:
    components = []
    for line in md.splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        name, role, lic = (_clean(c) for c in m.groups())
        # Skip the header row and separator-ish rows.
        if name.lower() in ("component", "") or set(name) <= set("-: "):
            continue
        components.append({"name": name, "role": role, "license": lic})
    return components


def main() -> int:
    md = SRC.read_text(encoding="utf-8")
    components = parse_components(md)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_from": "project/docs/THIRD_PARTY.md",
        "note": "TalkTeach is GPL-3.0-or-later; these are its third-party components.",
        "components": components,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(components)} components → {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
