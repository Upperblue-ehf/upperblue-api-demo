"""Shared offline and live entry points for the two examples."""

import argparse
import json
from datetime import date
from pathlib import Path

from requests import RequestException

DATA = Path(__file__).with_name("data")


def run(description, sample, filename, fetch, draw):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--date", type=date.fromisoformat, help="fetch live data starting on YYYY-MM-DD (UTC)"
    )
    parser.add_argument("--output", type=Path, default=Path(filename), help="output PNG path")
    args = parser.parse_args()
    try:
        data = (
            fetch(args.date)
            if args.date
            else json.loads((DATA / sample).read_text(encoding="utf-8"))
        )
        draw(data, args.output)
    except (RequestException, OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Saved {args.output}")
