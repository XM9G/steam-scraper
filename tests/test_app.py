from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from flask import render_template

import app as app_module
from app import (
    app,
    format_last_updated,
    run_midnight_refresh_loop,
    seconds_until_next_midnight,
    split_tours,
)
from main import build_tours_payload, refresh_tours


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

    def test_renders_srhc_operator_badge(self):
        tours = [
            {
                "operator": "Seymour Railway Heritage Centre",
                "title": "Spirit of Wimmera",
                "date": "2027-04-16",
                "end_date": "2027-04-19",
                "date_text": "16-19 APRIL 2027",
                "details": ["(SG) - D"],
                "links": [{"text": "BOOK NOW", "url": "https://events.humanitix.com/spirit-of-wimmera"}],
                "images": [],
            }
        ]

        with app.test_request_context("/"):
            html = render_template("index.html", upcoming_tours=tours, past_tours=[])

        self.assertIn("operator-srhc", html)
        self.assertIn("Seymour Railway Heritage Centre", html)
        self.assertIn('class="tour-links"', html)
        self.assertIn('class="tour-link"', html)

    def test_formats_last_updated_timestamp(self):
        self.assertIsNone(format_last_updated(None))
        self.assertEqual(
            format_last_updated("2026-11-25T17:09:05+11:00"),
            "25 November 2026, 5:09 pm UTC+11:00",
        )
        self.assertEqual(format_last_updated("invalid-date"), "invalid-date")

    def test_renders_open_graph_meta_tags(self):
        tours = [
            {
                "operator": "Steamrail Victoria",
                "title": "Future Tour",
                "date": "2099-04-16",
                "end_date": None,
                "date_text": "16 April 2099",
                "details": [],
                "links": [],
                "images": [
                    {
                        "url": "https://example.com/tour.jpg",
                        "alt": "Future Tour",
                        "title": "Future Tour",
                    }
                ],
            }
        ]

        with app.test_request_context("/"):
            html = render_template(
                "index.html",
                upcoming_tours=tours,
                past_tours=[],
                last_updated=None,
            )

        self.assertIn('property="og:type" content="website"', html)
        self.assertIn('property="og:title" content="Heritage Rail Tours"', html)
        self.assertIn(
            'property="og:description" content="Upcoming heritage rail tours across Victoria."',
            html,
        )
        self.assertIn(
            'property="og:image" content="https://example.com/tour.jpg"',
            html,
        )

    def test_renders_last_updated_from_json_file(self):
        payload = build_tours_payload(
            [
                {
                    "operator": "Seymour Railway Heritage Centre",
                    "title": "Spirit of Wimmera",
                    "date": "2027-04-16",
                    "end_date": "2027-04-19",
                    "date_text": "16-19 APRIL 2027",
                    "details": [],
                    "links": [],
                    "images": [],
                }
            ],
            updated_at=datetime(2026, 11, 25, 17, 9, 5, tzinfo=timezone(timedelta(hours=11))),
        )
        self.assertEqual(payload["last_updated"], "2026-11-25T17:09:05+11:00")

        with tempfile.TemporaryDirectory() as tmpdir:
            tours_path = Path(tmpdir) / "tours.json"
            tours_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(app_module, "TOURS_FILE", tours_path):
                response = app.test_client().get("/")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Last updated: 25 November 2026, 5:09 pm", html)

    def test_seconds_until_next_midnight(self):
        tz = timezone(timedelta(hours=11))
        self.assertEqual(
            seconds_until_next_midnight(datetime(2026, 11, 25, 23, 59, 30, tzinfo=tz)),
            30.0,
        )
        self.assertEqual(
            seconds_until_next_midnight(datetime(2026, 11, 26, 0, 0, 0, tzinfo=tz)),
            86400.0,
        )

    def test_refresh_tours_writes_sorted_json_atomically(self):
        sample_tours = [
            {"title": "Later", "date": "2027-05-01"},
            {"title": "Sooner", "date": "2027-04-01"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "tours.json"
            data = refresh_tours(output_path, scrape_fn=lambda: sample_tours)
            written = json.loads(output_path.read_text(encoding="utf-8"))
            leftover_temps = list(Path(tmpdir).glob("*.tmp"))

        self.assertEqual([t["title"] for t in data["tours"]], ["Sooner", "Later"])
        self.assertEqual(written, data)
        self.assertIn("last_updated", written)
        self.assertEqual(leftover_temps, [])

    def test_midnight_refresh_loop_continues_after_error(self):
        stop_event = threading.Event()
        calls = 0

        def fake_refresh():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("transient network failure")
            stop_event.set()

        with self.assertLogs(app.logger, level="ERROR"):
            run_midnight_refresh_loop(
                stop_event,
                refresh_fn=fake_refresh,
                delay_fn=lambda: 0,
            )

        self.assertEqual(calls, 2)

    def test_renders_rss_feed_link_and_xml_endpoint(self):
        payload = build_tours_payload(
            [
                {
                    "operator": "Steamrail Victoria",
                    "title": "Past Tour",
                    "date": "2020-01-01",
                    "end_date": None,
                    "date_text": "1 January 2020",
                    "details": ["Old tour"],
                    "links": [],
                    "images": [],
                },
                {
                    "operator": "Seymour Railway Heritage Centre",
                    "title": "Spirit of Wimmera",
                    "date": "2099-04-16",
                    "end_date": "2099-04-19",
                    "date_text": "16-19 APRIL 2099",
                    "details": ["(SG) - D", "from Seymour"],
                    "links": [
                        {
                            "text": "BOOK NOW",
                            "url": "https://events.humanitix.com/spirit-of-wimmera",
                        }
                    ],
                    "images": [],
                },
            ],
            updated_at=datetime(2026, 11, 25, 17, 9, 5, tzinfo=timezone(timedelta(hours=11))),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tours_path = Path(tmpdir) / "tours.json"
            tours_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(app_module, "TOURS_FILE", tours_path):
                client = app.test_client()
                page_response = client.get("/")
                feed_response = client.get("/feed.xml")

        page_html = page_response.get_data(as_text=True)
        self.assertIn('href="/feed.xml"', page_html)
        self.assertIn("application/rss+xml", page_html)

        self.assertEqual(feed_response.status_code, 200)
        self.assertIn("application/rss+xml", feed_response.content_type)
        root = ET.fromstring(feed_response.data)
        self.assertEqual(root.tag, "rss")
        items = root.findall("./channel/item")
        self.assertEqual(len(items), 1)
        self.assertIn("Spirit of Wimmera", items[0].findtext("title"))
        self.assertEqual(
            items[0].findtext("link"),
            "https://events.humanitix.com/spirit-of-wimmera",
        )
        self.assertIsNotNone(root.find("./channel/lastBuildDate"))

    def test_renders_ical_link_and_ics_endpoint(self):
        payload = build_tours_payload(
            [
                {
                    "operator": "Seymour Railway Heritage Centre",
                    "title": "Spirit of Wimmera",
                    "date": "2027-04-16",
                    "end_date": "2027-04-19",
                    "date_text": "16-19 APRIL 2027",
                    "details": ["(SG) - D", "from Seymour, Melbourne"],
                    "links": [
                        {
                            "text": "BOOK NOW",
                            "url": "https://events.humanitix.com/spirit-of-wimmera",
                        }
                    ],
                    "images": [],
                },
                {
                    "operator": "707 Operations",
                    "title": "Day Tour",
                    "date": "2027-05-01",
                    "end_date": None,
                    "date_text": "1 May 2027",
                    "details": [],
                    "links": [],
                    "images": [],
                },
            ],
            updated_at=datetime(2026, 11, 25, 17, 9, 5, tzinfo=timezone(timedelta(hours=11))),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tours_path = Path(tmpdir) / "tours.json"
            tours_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(app_module, "TOURS_FILE", tours_path):
                client = app.test_client()
                page_response = client.get("/")
                ics_response = client.get("/tours.ics")

        page_html = page_response.get_data(as_text=True)
        self.assertIn('href="/tours.ics"', page_html)

        self.assertEqual(ics_response.status_code, 200)
        self.assertIn("text/calendar", ics_response.content_type)
        ics_text = ics_response.get_data(as_text=True)
        unfolded = ics_text.replace("\r\n ", "")
        self.assertIn("BEGIN:VCALENDAR\r\n", ics_text)
        self.assertIn("DTSTAMP:20261125T060905Z\r\n", unfolded)
        self.assertIn("DTSTART;VALUE=DATE:20270416\r\n", unfolded)
        self.assertIn("DTEND;VALUE=DATE:20270420\r\n", unfolded)
        self.assertIn("DTSTART;VALUE=DATE:20270501\r\n", unfolded)
        self.assertIn("DTEND;VALUE=DATE:20270502\r\n", unfolded)
        self.assertIn("from Seymour\\, Melbourne", unfolded)
        self.assertIn("URL:https://events.humanitix.com/spirit-of-wimmera\r\n", unfolded)
        self.assertTrue(all(len(line.encode("utf-8")) <= 75 for line in ics_text.split("\r\n")))


if __name__ == "__main__":
    unittest.main()
