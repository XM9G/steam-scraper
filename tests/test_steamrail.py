import unittest

from scrapers.steamrail import _build_tour


class BuildSteamrailTourTests(unittest.TestCase):
    def test_removes_duplicate_link_text_from_details(self):
        record = {
            "date": "Saturday 28th November 2026",
            "title": "Members Christmas Train (D)",
            "details_text": (
                "Join us for our annual end of year members train - Enjoy a day out to "
                "Maryborough behind classic vintage diesel locomotives.\n"
                "Sign up today as a member of Steamrail to travel.\n"
                "Book Now\u00a0| RSVP on Facebook"
            ),
            "links": [
                {
                    "text": "Sign up today as a member of Steamrail to travel.",
                    "url": "https://www.steamrail.com.au/membership",
                },
                {
                    "text": "Book Now",
                    "url": "https://www.trybooking.com/DQLDN",
                },
                {
                    "text": "RSVP on Facebook",
                    "url": "https://www.facebook.com/events/2404672786730337/",
                },
            ],
            "images": [],
        }

        tour = _build_tour(record)

        self.assertEqual(
            tour["details"],
            [
                "Join us for our annual end of year members train - Enjoy a day out to Maryborough behind classic vintage diesel locomotives."
            ],
        )
        self.assertEqual(len(tour["links"]), 3)


if __name__ == "__main__":
    unittest.main()
