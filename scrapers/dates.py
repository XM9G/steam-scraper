from datetime import date
import re
from time import strptime


MONTH_PATTERN = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b",
    re.IGNORECASE,
)
DAY_PATTERN = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(\d{4})\b")


def normalize_tour_date(date_text, today=None, assume_current_year=False):
    month_match = MONTH_PATTERN.search(date_text)
    if not month_match:
        raise ValueError(f"Could not find a month in tour date: {date_text!r}")

    day_numbers = [
        int(day)
        for day in DAY_PATTERN.findall(date_text[: month_match.start()])
    ]
    if not day_numbers:
        raise ValueError(f"Could not find a day in tour date: {date_text!r}")

    month = strptime(month_match.group(1), "%B").tm_mon
    year_match = YEAR_PATTERN.search(date_text, month_match.end())
    if year_match:
        year = int(year_match.group(1))
    else:
        today = today or date.today()
        year = today.year
        if not assume_current_year and date(year, month, day_numbers[0]) < today:
            year += 1

    start = date(year, month, day_numbers[0])
    end = date(year, month, day_numbers[-1])
    return start.isoformat(), end.isoformat() if end != start else None
