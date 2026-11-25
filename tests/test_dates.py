from datetime import date
import unittest

from scrapers.dates import normalize_tour_date


class NormalizeTourDateTests(unittest.TestCase):
    def test_normalizes_single_date(self):
        self.assertEqual(
            normalize_tour_date("Saturday 28th November 2026"),
            ("2026-11-28", None),
        )

    def test_normalizes_date_range(self):
        self.assertEqual(
            normalize_tour_date("Saturday 7th to Monday 9th March 2026"),
            ("2026-03-07", "2026-03-09"),
        )

    def test_assigns_next_future_year_when_missing(self):
        self.assertEqual(
            normalize_tour_date(
                "23-24 November",
                today=date(2026, 11, 25),
            ),
            ("2027-11-23", "2027-11-24"),
        )

    def test_can_use_current_year_when_missing(self):
        self.assertEqual(
            normalize_tour_date(
                "23-24 November",
                today=date(2026, 11, 25),
                assume_current_year=True,
            ),
            ("2026-11-23", "2026-11-24"),
        )


if __name__ == "__main__":
    unittest.main()
