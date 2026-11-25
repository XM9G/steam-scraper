# Keeps every tour ever scraped, even after an operator takes it down.

import json
from pathlib import Path
import re


ARCHIVE_FILENAME = "tour_archive.json"


def tour_key(tour):
    title = re.sub(r"\s+", " ", (tour.get("title") or "")).strip().casefold()
    return "|".join([tour.get("operator") or "", tour.get("date") or "", title])


def load_archive(path):
    path = Path(path)
    try:
        with path.open(encoding="utf-8") as archive_file:
            return json.load(archive_file)
    except FileNotFoundError:
        return {"last_scraped": None, "tours": {}}


def update_archive(tours, scraped_at, path):
    path = Path(path)
    archive = load_archive(path)
    entries = archive.setdefault("tours", {})

    for tour in tours:
        key = tour_key(tour)
        first_seen = entries.get(key, {}).get("first_seen", scraped_at)
        entries[key] = {**tour, "first_seen": first_seen, "last_seen": scraped_at}

    archive["last_scraped"] = scraped_at

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(
        json.dumps(archive, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)
    return archive


def archived_tours(archive):
    last_scraped = archive.get("last_scraped")
    tours = [
        {**entry, "still_listed": entry.get("last_seen") == last_scraped}
        for entry in archive.get("tours", {}).values()
    ]
    return sorted(tours, key=lambda tour: tour.get("date") or "", reverse=True)
