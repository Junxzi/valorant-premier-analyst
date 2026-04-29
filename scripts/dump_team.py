"""One-off: dump the raw Premier team API response so we can see field names."""

import json
import sys
from pathlib import Path

from valorant_analyst.api.henrik_client import HenrikClient
from valorant_analyst.config import load_config


def main() -> int:
    config = load_config()
    if not config.henrik_api_key:
        print("HENRIK_API_KEY missing in .env", file=sys.stderr)
        return 1
    if not config.premier_team_name or not config.premier_team_tag:
        print("PREMIER_TEAM_NAME / PREMIER_TEAM_TAG missing in .env", file=sys.stderr)
        return 1

    client = HenrikClient(api_key=config.henrik_api_key)
    payload = client.get_premier_team(config.premier_team_name, config.premier_team_tag)

    out = Path("data/raw/team_dump.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"saved {out}")

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        print("payload.data is not an object")
        return 0

    print()
    print("Top-level keys in data:")
    for k, v in data.items():
        kind = type(v).__name__
        size = len(v) if hasattr(v, "__len__") and not isinstance(v, str) else "-"
        print(f"  {k:<24} type={kind:<8} len={size}")

    print()
    for candidate in ("member", "members", "roster", "players", "users"):
        if candidate in data:
            print(f">>> data[{candidate!r}] sample (first 2):")
            value = data[candidate]
            if isinstance(value, list):
                for item in value[:2]:
                    print(json.dumps(item, ensure_ascii=False, indent=2))
            else:
                print(repr(value))
    return 0


if __name__ == "__main__":
    sys.exit(main())
