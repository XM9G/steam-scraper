import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app as app_module
from app import app
from archive import archived_tours, load_archive, tour_key, update_archive
from main import refresh_tours


def make_tour(title, date="2027-03-01", operator="Steamrail Victoria", **extra):
    return {
        "operator": operator,
        "title": title,
        "date": date,
        "end_date": None,
        "date_text": date,
        "details": [],
        "links": [],
        "images": [],
        **extra,
    }


class UpdateArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "tour_archive.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_missing_archive_loads_empty(self):
        self.assertEqual(load_archive(self.path), {"last_scraped": None, "tours": {}})

    def test_keeps_tours_that_disappear_from_later_scrapes(self):
        update_archive([make_tour("Goldfields Express"), make_tour("Snow Train")], "2026-11-01T00:05:00+11:00", self.path)
        update_archive([make_tour("Snow Train")], "2026-11-02T00:05:00+11:00", self.path)

        tours = {t["title"]: t for t in archived_tours(load_archive(self.path))}

        self.assertEqual(set(tours), {"Goldfields Express", "Snow Train"})
        self.assertFalse(tours["Goldfields Express"]["still_listed"])
        self.assertEqual(tours["Goldfields Express"]["last_seen"], "2026-11-01T00:05:00+11:00")
        self.assertTrue(tours["Snow Train"]["still_listed"])

    def test_repeat_sighting_keeps_first_seen_and_refreshes_details(self):
        update_archive([make_tour("Snow Train", details=["Old"])], "2026-11-01T00:05:00+11:00", self.path)
        update_archive([make_tour("Snow Train", details=["New"])], "2026-11-02T00:05:00+11:00", self.path)

        archive = load_archive(self.path)
        (entry,) = archive["tours"].values()

        self.assertEqual(entry["first_seen"], "2026-11-01T00:05:00+11:00")
        self.assertEqual(entry["last_seen"], "2026-11-02T00:05:00+11:00")
        self.assertEqual(entry["details"], ["New"])

    def test_key_ignores_title_case_and_spacing(self):
        self.assertEqual(
            tour_key(make_tour("Snow  Train")),
            tour_key(make_tour("snow train")),
        )

    def test_same_title_on_different_dates_are_separate_tours(self):
        update_archive(
            [make_tour("Christmas Train", date="2025-12-06"), make_tour("Christmas Train", date="2026-12-05")],
            "2026-11-01T00:05:00+11:00",
            self.path,
        )
        self.assertEqual(len(load_archive(self.path)["tours"]), 2)

    def test_archived_tours_sorted_newest_first(self):
        update_archive(
            [make_tour("Older", date="2025-05-01"), make_tour("Newer", date="2027-01-01")],
            "2026-11-01T00:05:00+11:00",
            self.path,
        )
        self.assertEqual([t["title"] for t in archived_tours(load_archive(self.path))], ["Newer", "Older"])

    def test_refresh_tours_updates_archive_next_to_output(self):
        output_path = Path(self.tmpdir.name) / "tours.json"
        refresh_tours(output_path, scrape_fn=lambda previous: ([make_tour("Snow Train")], []))

        archive = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual([t["title"] for t in archive["tours"].values()], ["Snow Train"])
        self.assertEqual(list(Path(self.tmpdir.name).glob(".*.tmp")), [])


class ArchivePageTests(unittest.TestCase):
    def get_archive_page(self, archive_path):
        with patch.object(app_module, "ARCHIVE_FILE", archive_path):
            return app.test_client().get("/archive")

    def test_renders_removed_and_listed_tours(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tour_archive.json"
            update_archive([make_tour("Goldfields Express", date="2026-03-01")], "2026-02-01T00:05:00+11:00", path)
            update_archive([make_tour("Snow Train", date="2027-07-01")], "2026-11-25T00:05:00+11:00", path)
            response = self.get_archive_page(path)

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("<title>Tour Archive</title>", html)
        self.assertLess(html.index("<h2>2027</h2>"), html.index("<h2>2026</h2>"))
        self.assertEqual(html.count("Removed from the operator's site"), 1)
        self.assertIn("Removed from the operator's site after 1 February 2026", html)

    def test_empty_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            response = self.get_archive_page(Path(tmpdir) / "missing.json")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Nothing here yet.", response.get_data(as_text=True))

    def test_pages_link_to_each_other(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(app_module, "TOURS_FILE", Path(tmpdir) / "missing.json"):
                home = app.test_client().get("/").get_data(as_text=True)
            archive = self.get_archive_page(Path(tmpdir) / "missing.json").get_data(as_text=True)

        for page in (home, archive):
            self.assertRegex(page, r'href="/archive"[^>]*>.*Tour Archive</a>')
            self.assertRegex(page, r'href="/"[^>]*>.*Upcoming Tours</a>')
        self.assertRegex(home, r'href="/" aria-current="page"')
        self.assertRegex(archive, r'href="/archive" aria-current="page"')


if __name__ == "__main__":
    unittest.main()
