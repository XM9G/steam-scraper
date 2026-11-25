import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app as app_module
from app import app, split_traction
from main import build_tours_payload


def steamrail(title, operator="Steamrail Victoria"):
    return {"operator": operator, "title": title}


class SplitTractionTests(unittest.TestCase):
    def test_single_letter(self):
        self.assertEqual(split_traction(steamrail("Members Christmas Train (D)")), ("Members Christmas Train", ["Diesel"]))
        self.assertEqual(split_traction(steamrail("Ballarat Express (S)")), ("Ballarat Express", ["Steam"]))
        self.assertEqual(split_traction(steamrail("Spencer Street Shuttle (E)")), ("Spencer Street Shuttle", ["Electric"]))

    def test_multiple_letters(self):
        self.assertEqual(split_traction(steamrail("Geelong Flyer (S & D)")), ("Geelong Flyer", ["Steam", "Diesel"]))
        self.assertEqual(split_traction(steamrail("City Circle (S&E)")), ("City Circle", ["Steam", "Electric"]))

    def test_no_brackets(self):
        self.assertEqual(split_traction(steamrail("Open Day")), ("Open Day", []))

    def test_other_brackets_left_alone(self):
        self.assertEqual(split_traction(steamrail("Picnic Train (Sold Out)")), ("Picnic Train (Sold Out)", []))

    def test_only_applies_to_steamrail(self):
        tour = steamrail("Serviceton (S)", operator="Seymour Railway Heritage Centre")
        self.assertEqual(split_traction(tour), ("Serviceton (S)", []))


class TractionPillRenderingTests(unittest.TestCase):
    def test_home_page_shows_pills_and_clean_title(self):
        payload = build_tours_payload([
            {
                "operator": "Steamrail Victoria",
                "title": "Geelong Flyer (S & D)",
                "date": "2099-01-01",
                "end_date": None,
                "date_text": "1 January 2099",
                "details": [],
                "links": [],
                "images": [],
            }
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            tours_path = Path(tmpdir) / "tours.json"
            tours_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(app_module, "TOURS_FILE", tours_path):
                html = app.test_client().get("/").get_data(as_text=True)

        self.assertIn('<span class="traction-pill traction-steam">Steam</span>', html)
        self.assertIn('<span class="traction-pill traction-diesel">Diesel</span>', html)
        self.assertIn("<h2>Geelong Flyer</h2>", html)
        self.assertNotIn("(S &amp; D)", html)


if __name__ == "__main__":
    unittest.main()
