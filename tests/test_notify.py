from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from main import find_new_tours, refresh_tours
from archive import tour_key
from notify import build_embed, build_messages, notify_discord, webhook_urls


def tour(title, start="2099-04-18", operator="Seymour Railway Heritage Centre", **extra):
    return {
        "operator": operator,
        "title": title,
        "date": start,
        "end_date": None,
        "date_text": "18 APRIL 2099",
        "details": ["(SG) – D", "from Horsham"],
        "links": [{"text": "Book", "url": "https://example.com/book"}],
        "images": [{"url": "https://example.com/photo.jpg"}],
        **extra,
    }


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b""


class EmbedTests(unittest.TestCase):
    def test_embed_contents(self):
        embed = build_embed(tour("Serviceton"))

        self.assertEqual(embed["title"], "Serviceton")
        self.assertEqual(embed["url"], "https://example.com/book")
        self.assertEqual(embed["description"], "from Horsham")
        self.assertEqual(embed["thumbnail"], {"url": "https://example.com/photo.jpg"})
        self.assertEqual(embed["color"], 0x1B2237)
        fields = {field["name"]: field["value"] for field in embed["fields"]}
        self.assertRegex(fields["Date"], r"^18 APRIL 2099 \(<t:\d+:R>\)$")
        self.assertEqual(fields["Operator"], "Seymour Railway Heritage Centre")
        self.assertEqual(fields["Type"], "Diesel, Standard gauge")

    def test_steamrail_title_cleaned_and_falls_back_to_operator_page(self):
        embed = build_embed(tour("Ballarat Express (S)", operator="Steamrail Victoria", links=[], images=[], details=[]))

        self.assertEqual(embed["title"], "Ballarat Express")
        self.assertEqual(embed["url"], "https://www.steamrail.com.au/tours")
        self.assertNotIn("thumbnail", embed)
        self.assertNotIn("description", embed)

    def test_prefers_booking_link_over_first_link(self):
        links = [
            {"text": "Sign up today as a member of Steamrail to travel.", "url": "https://example.com/membership"},
            {"text": "Book Now", "url": "https://example.com/book"},
        ]
        self.assertEqual(build_embed(tour("Members Train", links=links))["url"], "https://example.com/book")

    def test_messages_split_into_batches_of_ten(self):
        messages = build_messages([tour(f"Tour {i}") for i in range(12)])

        self.assertEqual([len(m["embeds"]) for m in messages], [10, 2])

    def test_messages_have_no_text(self):
        self.assertNotIn("content", build_messages([tour("Solo")])[0])


class SendTests(unittest.TestCase):
    def test_skipped_without_webhook(self):
        self.assertEqual(notify_discord([tour("A")], webhook_url="", opener=None), 0)

    def test_posts_json_with_custom_user_agent(self):
        sent = []

        def opener(request, timeout):
            sent.append(request)
            return FakeResponse()

        count = notify_discord([tour("A")], webhook_url="https://discord.example/api/webhooks/1/x", opener=opener)

        self.assertEqual(count, 1)
        self.assertEqual(sent[0].get_method(), "POST")
        self.assertEqual(sent[0].get_header("User-agent"), "steam-scraper/1.0")
        self.assertEqual(json.loads(sent[0].data)["embeds"][0]["title"], "A")

    def test_posts_to_every_webhook_even_if_one_fails(self):
        sent = []

        def opener(request, timeout):
            if "broken" in request.full_url:
                raise OSError("404")
            sent.append(request.full_url)
            return FakeResponse()

        urls = "https://discord.example/api/webhooks/broken/x, https://discord.example/api/webhooks/2/y"
        count = notify_discord([tour("A")], webhook_url=urls, opener=opener)

        self.assertEqual(count, 1)
        self.assertEqual(sent, ["https://discord.example/api/webhooks/2/y"])

    def test_webhook_list_parsing(self):
        self.assertEqual(webhook_urls("a, b\nc  d"), ["a", "b", "c", "d"])
        self.assertEqual(webhook_urls(""), [])


class FindNewToursTests(unittest.TestCase):
    def test_only_unseen_upcoming_tours(self):
        known = {tour_key(tour("Old"))}
        tours = [tour("Old"), tour("Brand New"), tour("Already Happened", start="2020-01-01")]

        new = find_new_tours(tours, known, today=date(2026, 11, 26))

        self.assertEqual([t["title"] for t in new], ["Brand New"])

    def test_refresh_notifies_new_tours_but_not_on_first_run(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "tours.json"

            refresh_tours(output_path, scrape_fn=lambda prev: ([tour("Old")], []), on_new_tours=calls.append)
            self.assertEqual(calls, [])

            refresh_tours(output_path, scrape_fn=lambda prev: ([tour("Old"), tour("Brand New")], []), on_new_tours=calls.append)

        self.assertEqual([[t["title"] for t in batch] for batch in calls], [["Brand New"]])

    def test_notification_failure_does_not_break_refresh(self):
        def explode(tours):
            raise OSError("discord is down")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "tours.json"
            refresh_tours(output_path, scrape_fn=lambda prev: ([tour("Old")], []))
            data = refresh_tours(output_path, scrape_fn=lambda prev: ([tour("Old"), tour("New")], []), on_new_tours=explode)

        self.assertEqual(len(data["tours"]), 2)


if __name__ == "__main__":
    unittest.main()
