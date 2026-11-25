import json
from datetime import date
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


@app.get("/")
def tours():
    with TOURS_FILE.open(encoding="utf-8") as json_file:
        data = json.load(json_file)
    upcoming_tours, past_tours = split_tours(data["tours"])
    return render_template(
        "index.html",
        upcoming_tours=upcoming_tours,
        past_tours=past_tours,
    )


if __name__ == "__main__":
    app.run()