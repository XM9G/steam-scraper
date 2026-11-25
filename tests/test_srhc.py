import unittest

from scrapers.srhc import OPERATOR, _build_tour


class BuildSrhcTourTests(unittest.TestCase):
    def test_builds_multi_day_tour_with_booking_link(self):
        record = {
            "title": "Spirit of Wimmera",
            "paragraphs": [
                "16-19 APRIL 2027 \u2013 (SG) \u2013 D\nfrom Seymour, Melbourne or North Shore",
                "We make our second journey to Horsham.",
                "The theme is 19th century space travel.",
            ],
            "links": [
                {
                    "text": "BOOK NOW",
                    "url": "https://events.humanitix.com/spirit-of-wimmera",
                }
            ],
            "unlinked_labels": [],
            "images": [
                {
                    "url": "https://i0.wp.com/srhc.org.au/wp-content/uploads/2026/06/SSPPU.jpg",
                    "alt": "",
                    "title": "",
                }
            ],
        }

        tour = _build_tour(record)

        self.assertEqual(tour["operator"], OPERATOR)
        self.assertEqual(tour["date"], "2027-04-16")
        self.assertEqual(tour["end_date"], "2027-04-19")
        self.assertEqual(tour["date_text"], "16-19 APRIL 2027")
        self.assertEqual(tour["title"], "Spirit of Wimmera")
        self.assertEqual(
            tour["details"],
            [
                "(SG) \u2013 D",
                "from Seymour, Melbourne or North Shore",
                "We make our second journey to Horsham.",
                "The theme is 19th century space travel.",
            ],
        )
        self.assertEqual(
            tour["links"],
            [{"text": "BOOK NOW", "url": "https://events.humanitix.com/spirit-of-wimmera"}],
        )

    def test_builds_single_day_tour_with_coming_soon_label(self):
        record = {
            "title": "Serviceton",
            "paragraphs": [
                "18 APRIL 2027 \u2013 (SG) \u2013 D\nfrom Horsham",
                "Travel with us on a fabulous day out from Horsham and Dimboola.",
            ],
            "links": [],
            "unlinked_labels": ["COMING SOON"],
            "images": [],
        }

        tour = _build_tour(record)

        self.assertEqual(tour["date"], "2027-04-18")
        self.assertIsNone(tour["end_date"])
        self.assertEqual(tour["date_text"], "18 APRIL 2027")
        self.assertEqual(
            tour["details"],
            [
                "(SG) \u2013 D",
                "from Horsham",
                "Travel with us on a fabulous day out from Horsham and Dimboola.",
                "COMING SOON",
            ],
        )
        self.assertEqual(tour["links"], [])


if __name__ == "__main__":
    unittest.main()
