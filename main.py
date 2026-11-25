import argparse
import json
from pathlib import Path

from scrapers.slowrailjourneys import scrape_slowrailjourneys
from scrapers.sevenoseven import scrape_sevenoseven
from scrapers.steamrail import DEFAULT_OUTPUT_PATH, scrape_steamrail


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
    )
    tours.sort(key=lambda tour: tour["date"])
    data = {"tours": tours}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(tours)} tours from all operators to {args.output}")


if __name__ == "__main__":
    main()