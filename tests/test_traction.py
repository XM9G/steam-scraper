import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app as app_module
from app import app, tour_tags
from main import build_tours_payload


def steamrail(title):
    return {"operator": "Steamrail Victoria", "title": title, "details": []}


def srhc(first_detail, title="Serviceton"):
    return {
        "operator": "Seymour Railway Heritage Centre",
        "title": title,
        "details": [first_detail, "from Horsham"],
    }


def pills(tour):
    tags = tour_tags(tour)
    return tags["title"], tags["traction"], tags["gauge"]


class SteamrailTractionTests(unittest.TestCase):
    def test_single_letter(self):
        self.assertEqual(pills(steamrail("Members Christmas Train (D)")), ("Members Christmas Train", ["Diesel"], None))
        self.assertEqual(pills(steamrail("Ballarat Express (S)")), ("Ballarat Express", ["Steam"], None))
        self.assertEqual(pills(steamrail("Spencer Street Shuttle (E)")), ("Spencer Street Shuttle", ["Electric"], None))

    def test_multiple_letters(self):
        self.assertEqual(pills(steamrail("Geelong Flyer (S & D)")), ("Geelong Flyer", ["Steam", "Diesel"], None))
        self.assertEqual(pills(steamrail("City Circle (S&E)")), ("City Circle", ["Steam", "Electric"], None))

    def test_no_brackets(self):
        self.assertEqual(pills(steamrail("Open Day")), ("Open Day", [], None))

    def test_other_brackets_left_alone(self):
        self.assertEqual(pills(steamrail("Picnic Train (Sold Out)")), ("Picnic Train (Sold Out)", [], None))


class SrhcTractionTests(unittest.TestCase):
    def test_gauge_and_traction(self):
        tags = tour_tags(srhc("(SG) – D"))
        self.assertEqual((tags["traction"], tags["gauge"]), (["Diesel"], "Standard gauge"))
        self.assertEqual(tags["details"], ["from Horsham"])

    def test_broad_gauge_steam_and_diesel(self):
        tags = tour_tags(srhc("(BG) - S & D"))
        self.assertEqual((tags["traction"], tags["gauge"]), (["Steam", "Diesel"], "Broad gauge"))

    def test_gauge_without_traction(self):
        tags = tour_tags(srhc("(SG)"))
        self.assertEqual((tags["traction"], tags["gauge"]), ([], "Standard gauge"))
        self.assertEqual(tags["details"], ["from Horsham"])

    def test_ordinary_first_line_left_alone(self):
        tags = tour_tags(srhc("A day out to Serviceton"))
        self.assertEqual((tags["traction"], tags["gauge"]), ([], None))
        self.assertEqual(tags["details"], ["A day out to Serviceton", "from Horsham"])

    def test_steamrail_style_title_ignored_for_srhc(self):
        self.assertEqual(tour_tags(srhc("from Horsham", title="Serviceton (S)"))["title"], "Serviceton (S)")


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


    def test_home_page_shows_srhc_pills_and_hides_code_line(self):
        payload = build_tours_payload([
            {
                "operator": "Seymour Railway Heritage Centre",
                "title": "Serviceton",
                "date": "2099-04-18",
                "end_date": None,
                "date_text": "18 APRIL 2099",
                "details": ["(SG) – D", "from Horsham"],
                "links": [],
                "images": [],
            }
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            tours_path = Path(tmpdir) / "tours.json"
            tours_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(app_module, "TOURS_FILE", tours_path):
                html = app.test_client().get("/").get_data(as_text=True)

        self.assertIn('<span class="traction-pill traction-diesel">Diesel</span>', html)
        self.assertIn('<span class="traction-pill gauge-pill">Standard gauge</span>', html)
        self.assertNotIn("(SG)", html)
        self.assertIn("<p>from Horsham</p>", html)

if __name__ == "__main__":
    unittest.main()
