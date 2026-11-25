from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app as app_module
from app import app, countdown
from archive import update_archive
from main import build_tours_payload


TODAY = date(2026, 11, 26)


def tour(start, end=None, title="Test Tour"):
    return {
        "operator": "707 Operations",
        "title": title,
        "date": start,
        "end_date": end,
        "date_text": start,
        "details": [],
        "links": [],
        "images": [],
    }


class CountdownTests(unittest.TestCase):
    def test_wording(self):
        self.assertEqual(countdown(tour("2026-11-26"), TODAY), "Today")
        self.assertEqual(countdown(tour("2026-11-27"), TODAY), "Tomorrow")
        self.assertEqual(countdown(tour("2026-11-28"), TODAY), "In 2 days")
        self.assertEqual(countdown(tour("2027-04-16"), TODAY), "In 141 days")

    def test_multi_day_tour_in_progress(self):
        self.assertEqual(countdown(tour("2026-11-24", "2026-11-27"), TODAY), "On now")
        self.assertEqual(countdown(tour("2026-11-24", "2026-11-26"), TODAY), "On now")

    def test_finished_tour_has_no_countdown(self):
        self.assertIsNone(countdown(tour("2026-11-20"), TODAY))
        self.assertIsNone(countdown(tour("2026-11-20", "2026-11-25"), TODAY))


class CountdownRenderingTests(unittest.TestCase):
    def test_home_page_shows_countdown_on_upcoming_only(self):
        payload = build_tours_payload([
            tour("2099-01-01", title="Future"),
            tour("2000-01-01", title="Long Gone"),
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            tours_path = Path(tmpdir) / "tours.json"
            tours_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(app_module, "TOURS_FILE", tours_path):
                html = app.test_client().get("/").get_data(as_text=True)

        self.assertEqual(html.count('class="countdown"'), 1)
        self.assertRegex(html, r'<strong>2099-01-01</strong> <span class="countdown">In \d+ days</span>')

    def test_archive_has_no_countdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = Path(tmpdir) / "tour_archive.json"
            update_archive([tour("2099-01-01")], "2026-11-26T00:05:00+11:00", archive_path)
            with patch.object(app_module, "ARCHIVE_FILE", archive_path):
                html = app.test_client().get("/archive").get_data(as_text=True)

        self.assertNotIn('class="countdown"', html)


if __name__ == "__main__":
    unittest.main()
