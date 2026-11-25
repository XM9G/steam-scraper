from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from flask import render_template

import app as app_module
from app import app, format_last_updated, split_tours
from main import build_tours_payload


class SplitToursTests(unittest.TestCase):
    def test_splits_completed_tours_from_upcoming_tours(self):
        tours = [
            {"title": "Completed", "date": "2026-11-20", "end_date": "2026-11-21"},
            {"title": "Happening today", "date": "2026-11-25", "end_date": None},
            {"title": "Upcoming range", "date": "2026-11-26", "end_date": "2026-11-28"},
        ]

        upcoming, past = split_tours(tours, today=date(2026, 11, 25))

        self.assertEqual([tour["title"] for tour in upcoming], ["Happening today", "Upcoming range"])
        self.assertEqual([tour["title"] for tour in past], ["Completed"])

    def test_renders_srhc_operator_badge(self):
        tours = [
            {
                "operator": "Seymour Railway Heritage Centre",
                "title": "Spirit of Wimmera",
                "date": "2027-04-16",
                "end_date": "2027-04-19",
                "date_text": "16-19 APRIL 2027",
                "details": ["(SG) - D"],
                "links": [],
                "images": [],
            }
        ]

        with app.test_request_context("/"):
            html = render_template("index.html", upcoming_tours=tours, past_tours=[])

        self.assertIn("operator-srhc", html)
        self.assertIn("Seymour Railway Heritage Centre", html)

    def test_formats_last_updated_timestamp(self):
        self.assertIsNone(format_last_updated(None))
        self.assertEqual(
            format_last_updated("2026-11-25T17:09:05+11:00"),
            "25 November 2026, 5:09 pm UTC+11:00",
        )
        self.assertEqual(format_last_updated("invalid-date"), "invalid-date")

    def test_renders_last_updated_from_json_file(self):
        payload = build_tours_payload(
            [
                {
                    "operator": "Seymour Railway Heritage Centre",
                    "title": "Spirit of Wimmera",
                    "date": "2027-04-16",
                    "end_date": "2027-04-19",
                    "date_text": "16-19 APRIL 2027",
                    "details": [],
                    "links": [],
                    "images": [],
                }
            ],
            updated_at=datetime(2026, 11, 25, 17, 9, 5, tzinfo=timezone(timedelta(hours=11))),
        )
        self.assertEqual(payload["last_updated"], "2026-11-25T17:09:05+11:00")

        with tempfile.TemporaryDirectory() as tmpdir:
            tours_path = Path(tmpdir) / "tours.json"
            tours_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(app_module, "TOURS_FILE", tours_path):
                response = app.test_client().get("/")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Last updated: 25 November 2026, 5:09 pm", html)


if __name__ == "__main__":
    unittest.main()
