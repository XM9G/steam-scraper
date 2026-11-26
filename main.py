import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path
import time
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from archive import ARCHIVE_FILENAME, load_archive, tour_key, update_archive
from notify import notify_discord
from scrapers.sevenoseven import scrape_sevenoseven
from scrapers.slowrailjourneys import scrape_slowrailjourneys
from scrapers.srhc import scrape_srhc
from scrapers.steamrail import DEFAULT_OUTPUT_PATH, scrape_steamrail


# (operator name as it appears on tours, short name for status messages, scraper)
OPERATORS = [
    ("Steamrail Victoria", "Steamrail", scrape_steamrail),
    ("Slow Rail Journeys", "Slow Rail", scrape_slowrailjourneys),
    ("707 Operations", "707", scrape_sevenoseven),
    ("Seymour Railway Heritage Centre", "SRHC", scrape_srhc),
]


def build_tours_payload(tours, updated_at=None):
    updated_at = updated_at or datetime.now().astimezone()
    return {
        "last_updated": updated_at.isoformat(timespec="seconds"),
        "tours": sorted(tours, key=lambda tour: tour["date"]),
    }


def scrape_all_tours(previous_tours=(), operators=OPERATORS):
    """Scrape each operator on its own. If one fails or finds nothing, keep its
    tours from the last run so the site and archive don't lose them."""
    tours = []
    health = []
    for name, short_name, scrape in operators:
        print(f"Scraping {name} tours...")
        try:
            found = scrape()["tours"]
            error = None if found else "returned 0 tours"
        except Exception as exc:
            found = []
            error = f"failed: {type(exc).__name__}: {exc}"

        if error:
            kept = [tour for tour in previous_tours if tour.get("operator") == name]
            print(f"  {name} {error}; keeping {len(kept)} tours from the last run")
            tours.extend(kept)
        else:
            print(f"  Found {len(found)} {name} tours")
            tours.extend(found)

        health.append({"operator": short_name, "count": len(found), "error": error})
    return tours, health


def load_previous_tours(path):
    try:
        with Path(path).open(encoding="utf-8") as tours_file:
            return json.load(tours_file).get("tours", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def refresh_tours(
    output_path=DEFAULT_OUTPUT_PATH,
    scrape_fn=scrape_all_tours,
    archive_path=None,
    on_new_tours=None,
):
    output_path = Path(output_path)
    if archive_path is None:
        archive_path = output_path.with_name(ARCHIVE_FILENAME)
    print("Scraping tours from all operators...")
    tours, health = scrape_fn(load_previous_tours(output_path))
    data = build_tours_payload(tours)
    data["health"] = health
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
    known_keys = set(load_archive(archive_path).get("tours", {}))
    archive = update_archive(data["tours"], data["last_updated"], archive_path)
    print(f"Tour archive at {archive_path} now holds {len(archive['tours'])} tours")

    # Skip on the very first run, otherwise every existing tour looks new.
    new_tours = find_new_tours(data["tours"], known_keys) if known_keys else []
    if new_tours and on_new_tours:
        print(f"Found {len(new_tours)} new tours")
        try:
            on_new_tours(new_tours)
        except Exception as exc:
            print(f"Could not send new tour notifications: {exc}")
    return data


def find_new_tours(tours, known_keys, today=None):
    today = today or date.today()
    return [
        tour
        for tour in tours
        if tour_key(tour) not in known_keys
        and date.fromisoformat(tour.get("end_date") or tour["date"]) >= today
    ]


def health_summary(health):
    problems = [f"{item['operator']} {item['error']}" for item in health if item["error"]]
    if problems:
        return False, "; ".join(problems)
    total = sum(item["count"] for item in health)
    counts = ", ".join(f"{item['operator']} {item['count']}" for item in health)
    return True, f"{total} tours: {counts}"


def build_push_url(base_url, ok, message, ping_ms=None):
    parts = urlsplit(base_url)
    query = {"status": "up" if ok else "down", "msg": message}
    if ping_ms is not None:
        query["ping"] = str(int(ping_ms))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def push_status(ok, message, ping_ms=None, base_url=None, opener=urlopen):
    """Report to an Uptime Kuma push monitor. Set KUMA_PUSH_URL to enable."""
    base_url = base_url or os.environ.get("KUMA_PUSH_URL")
    if not base_url:
        return False
    url = build_push_url(base_url, ok, message, ping_ms)
    # Cloudflare blocks Python's default "Python-urllib" user agent.
    request = Request(url, headers={"User-Agent": "steam-scraper/1.0"})
    try:
        with opener(request, timeout=15) as response:
            response.read()
        print(f"Reported {'up' if ok else 'down'} to Uptime Kuma: {message}")
        return True
    except Exception as exc:
        print(f"Could not reach Uptime Kuma: {exc}")
        return False



ENV_FILE = Path(__file__).with_name(".env")


def load_env(path=ENV_FILE, environ=os.environ):
    """Read KEY=value lines from .env. Variables already set take priority."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        environ.setdefault(key, value)


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
    load_env()

    print("Starting heritage rail tour refresh...")
    started = time.monotonic()
    try:
        data = refresh_tours(args.output, on_new_tours=notify_discord)
    except Exception as exc:
        push_status(False, f"Scrape crashed: {type(exc).__name__}: {exc}")
        raise
    elapsed_ms = (time.monotonic() - started) * 1000
    ok, message = health_summary(data["health"])
    push_status(ok, message, ping_ms=elapsed_ms)
    print(f"Wrote {len(data['tours'])} tours from all operators to {args.output}")


if __name__ == "__main__":
    main()
