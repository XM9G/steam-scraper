import argparse
from datetime import datetime
import json
from pathlib import Path

from scrapers.sevenoseven import scrape_sevenoseven
from scrapers.slowrailjourneys import scrape_slowrailjourneys
from scrapers.srhc import scrape_srhc
from scrapers.steamrail import DEFAULT_OUTPUT_PATH, scrape_steamrail


def build_tours_payload(tours, updated_at=None):
    updated_at = updated_at or datetime.now().astimezone()
    return {
        "last_updated": updated_at.isoformat(timespec="seconds"),
        "tours": sorted(tours, key=lambda tour: tour["date"]),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Scrape heritage rail tours to a JSON file."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"JSON output path (default: {DEFAULT_OUTPUT_PATH})",
    )
    args = parser.parse_args()

    tours = (
        scrape_steamrail()["tours"]
        + scrape_slowrailjourneys()["tours"]
        + scrape_sevenoseven()["tours"]
        + scrape_srhc()["tours"]
    )
    data = build_tours_payload(tours)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(data['tours'])} tours from all operators to {args.output}")


if __name__ == "__main__":
    main()