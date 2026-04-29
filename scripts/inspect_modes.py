"""Quick diagnostic: show the mode/queue distribution of the latest fetch."""

import collections
import json
import sys
from pathlib import Path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw/latest_matches.json")
data = json.loads(path.read_text(encoding="utf-8")).get("data") or []

print(f"matches returned: {len(data)}")
print()
counter: collections.Counter = collections.Counter()
for m in data:
    md = m.get("metadata") or {}
    counter[(md.get("mode"), md.get("queue"))] += 1

print(f"{'mode':<20} {'queue':<20} count")
print("-" * 50)
for (mode, queue), n in counter.most_common():
    print(f"{str(mode):<20} {str(queue):<20} {n}")
