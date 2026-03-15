from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"E:\coding agent\codinggirl")
RX = re.compile(r"\bkind\s*=\s*\"([^\"]+)\"")


def main() -> int:
    counts: dict[str, int] = {}
    locations: dict[str, list[str]] = {}
    for f in ROOT.rglob("*.py"):
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in RX.finditer(text):
            k = m.group(1)
            counts[k] = counts.get(k, 0) + 1
            ln = text[: m.start()].count("\n") + 1
            locations.setdefault(k, []).append(f"{f}:{ln}")

    weird = [k for k in counts if k in {"class", "function", "variable", "async_function"}]
    print("weird:")
    for k in weird:
        print(f"  {k}: {counts[k]}")
        for loc in locations.get(k, [])[:10]:
            print(f"    - {loc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
