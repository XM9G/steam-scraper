import argparse
from datetime import datetime
import json
from pathlib import Path

from archive import ARCHIVE_FILENAME, update_archive
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


def scrape_all_tours():
    print("Scraping Steamrail Victoria tours...")
    steamrail_tours = scrape_steamrail()["tours"]
    print(f"  Found {len(steamrail_tours)} Steamrail Victoria tours")

    print("Scraping Slow Rail Journeys tours...")
    slowrail_tours = scrape_slowrailjourneys()["tours"]
    print(f"  Found {len(slowrail_tours)} Slow Rail Journeys tours")

    print("Scraping 707 Operations tours...")
    sevenoseven_tours = scrape_sevenoseven()["tours"]
    print(f"  Found {len(sevenoseven_tours)} 707 Operations tours")

    print("Scraping Seymour Railway Heritage Centre tours...")
    srhc_tours = scrape_srhc()["tours"]
    print(f"  Found {len(srhc_tours)} Seymour Railway Heritage Centre tours")

    return steamrail_tours + slowrail_tours + sevenoseven_tours + srhc_tours


def refresh_tours(
    output_path=DEFAULT_OUTPUT_PATH,
    scrape_fn=scrape_all_tours,
    archive_path=None,
):
    output_path = Path(output_path)
    if archive_path is None:
        archive_path = output_path.with_name(ARCHIVE_FILENAME)
    print("Scraping tours from all operators...")
    data = build_tours_payload(scrape_fn())
    print(f"Building JSON payload with {len(data['tours'])} tours")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing tour data to {output_path}...")
    temp_path = output_path.with_name(f".{output_path.name}.tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(output_path)
    print(f"Successfully saved tour data to {output_path}")
    archive = update_archive(data["tours"], data["last_updated"], archive_path)
    print(f"Tour archive at {archive_path} now holds {len(archive['tours'])} tours")
    return data


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

    print("Starting heritage rail tour refresh...")
    data = refresh_tours(args.output)
    print(f"Wrote {len(data['tours'])} tours from all operators to {args.output}")


if __name__ == "__main__":
    main()