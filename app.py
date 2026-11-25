import json
from datetime import date, datetime
from pathlib import Path

from flask import Flask, render_template


app = Flask(__name__)
TOURS_FILE = Path(__file__).with_name("steamrail_tours.json")


def split_tours(tours, today=None):
    today = today or date.today()
    upcoming = []
    past = []
    for tour in tours:
        final_date = date.fromisoformat(tour.get("end_date") or tour["date"])
        (past if final_date < today else upcoming).append(tour)
    return upcoming, past


def format_last_updated(last_updated):
    if not last_updated:
        return None
    try:
        dt = datetime.fromisoformat(last_updated)
    except ValueError:
        return str(last_updated)

    hour = dt.hour % 12 or 12
    period = "am" if dt.hour < 12 else "pm"
    tz = f" {dt.tzname()}" if dt.tzinfo and dt.tzname() else ""
    return f"{dt.day} {dt.strftime('%B %Y')}, {hour}:{dt.minute:02d} {period}{tz}"


@app.get("/")
def tours():
    with TOURS_FILE.open(encoding="utf-8") as json_file:
        data = json.load(json_file)
    upcoming_tours, past_tours = split_tours(data["tours"])
    return render_template(
        "index.html",
        upcoming_tours=upcoming_tours,
        past_tours=past_tours,
        last_updated=format_last_updated(data.get("last_updated")),
    )


if __name__ == "__main__":
    app.run()