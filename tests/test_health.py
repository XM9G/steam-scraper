import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

from main import (
    build_push_url,
    health_summary,
    push_status,
    refresh_tours,
    scrape_all_tours,
)


def tour(operator, title, date="2099-01-01"):
    return {"operator": operator, "title": title, "date": date}


def working(*tours):
    return lambda: {"tours": list(tours)}


def broken():
    raise TimeoutError("page took too long")


class ScrapeAllToursTests(unittest.TestCase):
    def test_all_operators_ok(self):
        operators = [
            ("A Rail", "A", working(tour("A Rail", "One"))),
            ("B Rail", "B", working(tour("B Rail", "Two"), tour("B Rail", "Three"))),
        ]
        tours, health = scrape_all_tours([], operators)

        self.assertEqual([t["title"] for t in tours], ["One", "Two", "Three"])
        self.assertEqual(health, [
            {"operator": "A", "count": 1, "error": None},
            {"operator": "B", "count": 2, "error": None},
        ])

    def test_failed_operator_keeps_previous_tours_and_others_still_update(self):
        previous = [tour("A Rail", "Old A"), tour("B Rail", "Old B")]
        operators = [
            ("A Rail", "A", broken),
            ("B Rail", "B", working(tour("B Rail", "New B"))),
        ]
        tours, health = scrape_all_tours(previous, operators)

        self.assertEqual([t["title"] for t in tours], ["Old A", "New B"])
        self.assertEqual(health[0]["count"], 0)
        self.assertIn("TimeoutError", health[0]["error"])
        self.assertIsNone(health[1]["error"])

    def test_zero_tours_counts_as_a_problem(self):
        previous = [tour("A Rail", "Old A")]
        tours, health = scrape_all_tours(previous, [("A Rail", "A", working())])

        self.assertEqual([t["title"] for t in tours], ["Old A"])
        self.assertEqual(health[0]["error"], "returned 0 tours")


class HealthSummaryTests(unittest.TestCase):
    def test_up_message_lists_counts(self):
        ok, message = health_summary([
            {"operator": "Steamrail", "count": 1, "error": None},
            {"operator": "SRHC", "count": 3, "error": None},
        ])
        self.assertTrue(ok)
        self.assertEqual(message, "4 tours: Steamrail 1, SRHC 3")

    def test_down_message_names_problems(self):
        ok, message = health_summary([
            {"operator": "Steamrail", "count": 1, "error": None},
            {"operator": "SRHC", "count": 0, "error": "returned 0 tours"},
            {"operator": "707", "count": 0, "error": "failed: TimeoutError: slow"},
        ])
        self.assertFalse(ok)
        self.assertEqual(message, "SRHC returned 0 tours; 707 failed: TimeoutError: slow")


class PushTests(unittest.TestCase):
    def test_build_push_url_replaces_existing_query(self):
        url = build_push_url(
            "https://status.example.com/api/push/abc?status=up&msg=OK&ping=",
            False,
            "SRHC returned 0 tours",
            ping_ms=18234.7,
        )
        parts = urlsplit(url)
        self.assertEqual(parts.path, "/api/push/abc")
        self.assertEqual(parse_qs(parts.query), {
            "status": ["down"],
            "msg": ["SRHC returned 0 tours"],
            "ping": ["18234"],
        })

    def test_push_skipped_without_url(self):
        calls = []
        self.assertFalse(push_status(True, "OK", base_url="", opener=lambda *a, **k: calls.append(a)))
        self.assertEqual(calls, [])

    def test_push_failure_does_not_raise(self):
        def unreachable(url, timeout):
            raise OSError("connection refused")

        self.assertFalse(push_status(True, "OK", base_url="https://status.example.com/api/push/abc", opener=unreachable))


class RefreshHealthTests(unittest.TestCase):
    def test_refresh_saves_health_and_passes_previous_tours(self):
        seen_previous = []

        def fake_scrape(previous):
            seen_previous.append(previous)
            return [tour("A Rail", "New")], [{"operator": "A", "count": 1, "error": None}]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "tours.json"
            output_path.write_text(json.dumps({"tours": [tour("A Rail", "Old")]}), encoding="utf-8")
            refresh_tours(output_path, scrape_fn=fake_scrape)
            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual([t["title"] for t in seen_previous[0]], ["Old"])
        self.assertEqual(written["health"], [{"operator": "A", "count": 1, "error": None}])


if __name__ == "__main__":
    unittest.main()
