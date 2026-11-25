from datetime import date
import unittest

from app import split_tours


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


if __name__ == "__main__":
    unittest.main()
