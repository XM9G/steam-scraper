from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
import hashlib
from html import escape
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from flask import Flask, Response, render_template, request

from archive import ARCHIVE_FILENAME, archived_tours, load_archive
from tags import tour_tags


app = Flask(__name__)
app.add_template_global(tour_tags)
TOURS_FILE = Path(__file__).with_name("steamrail_tours.json")
ARCHIVE_FILE = Path(__file__).with_name(ARCHIVE_FILENAME)

ATOM_NS = "http://www.w3.org/2005/Atom"
ET.register_namespace("atom", ATOM_NS)


def split_tours(tours, today=None):
    today = today or date.today()
    upcoming = []
    past = []
    for tour in tours:
        final_date = date.fromisoformat(tour.get("end_date") or tour["date"])
        (past if final_date < today else upcoming).append(tour)
    return upcoming, past


@app.template_global()
def countdown(tour, today=None):
    today = today or date.today()
    start = date.fromisoformat(tour["date"])
    end = date.fromisoformat(tour.get("end_date") or tour["date"])
    days = (start - today).days
    if end < today:
        return None
    if days < 0:
        return "On now"
    if days == 0:
        return "Today"
    if days == 1:
        return "Tomorrow"
    return f"In {days} days"


def format_last_updated(last_updated):
    if not last_updated:
        return None
    try:
        dt = datetime.fromisoformat(last_updated)
    except ValueError:
        return str(last_updated)

    hour = dt.hour % 12 or 12
    period = "am" if dt.hour < 12 else "pm"
    tz = f" {dt.tzname()}" if dt.tzinfo and dt.tzname() else ""
    return f"{dt.day} {dt.strftime('%B %Y')}, {hour}:{dt.minute:02d} {period}{tz}"



@app.template_filter("seen_date")
def format_seen_date(timestamp):
    if not timestamp:
        return "unknown"
    try:
        dt = datetime.fromisoformat(timestamp)
    except ValueError:
        return str(timestamp)
    return f"{dt.day} {dt.strftime('%B %Y')}"



def group_tours_by_year(tours):
    groups = []
    for tour in tours:
        year = (tour.get("date") or "")[:4] or "Undated"
        if groups and groups[-1][0] == year:
            groups[-1][1].append(tour)
        else:
            groups.append((year, [tour]))
    return groups

def _first_http_url(items):
    for item in items or ():
        url = item.get("url")
        if url and url.startswith(("http://", "https://")):
            return url
    return None


def _build_tour_description_html(tour):
    parts = [f"<p><strong>{escape(tour.get('operator') or 'Unknown operator')}</strong> &mdash; {escape(tour.get('date_text') or tour['date'])}</p>"]
    for detail in tour.get("details") or ():
        parts.append(f"<p>{escape(detail)}</p>")
    for link in tour.get("links") or ():
        url = link.get("url")
        if url and url.startswith(("http://", "https://")):
            label = escape(link.get("text") or url)
            parts.append(f'<p><a href="{escape(url, quote=True)}">{label}</a></p>')
    for image in tour.get("images") or ():
        url = image.get("url")
        if url and url.startswith(("http://", "https://")):
            alt = escape(image.get("alt") or tour.get("title") or "", quote=True)
            parts.append(f'<p><img src="{escape(url, quote=True)}" alt="{alt}" /></p>')
    return "".join(parts)


def build_rss_feed(tours, last_updated, site_url, feed_url):
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Heritage Rail Tours"
    ET.SubElement(channel, "link").text = site_url
    ET.SubElement(channel, "description").text = "Upcoming heritage rail tours across Victoria."
    ET.SubElement(
        channel,
        f"{{{ATOM_NS}}}link",
        {"href": feed_url, "rel": "self", "type": "application/rss+xml"},
    )

    if last_updated:
        try:
            dt = datetime.fromisoformat(last_updated)
        except ValueError:
            dt = None
        if dt is not None:
            ET.SubElement(channel, "lastBuildDate").text = format_datetime(dt)

    for tour in tours:
        item = ET.SubElement(channel, "item")
        operator = tour.get("operator") or "Unknown operator"
        date_label = tour.get("date_text") or tour["date"]
        ET.SubElement(item, "title").text = f"{operator}: {tour['title']} ({date_label})"
        ET.SubElement(item, "link").text = _first_http_url(tour.get("links")) or site_url
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = (
            f"{operator}|{tour['date']}|{tour['title']}"
        )
        ET.SubElement(item, "description").text = _build_tour_description_html(tour)

    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def _escape_ical_text(value):
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def _fold_ical_line(line):
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line

    chunks = []
    current = ""
    current_bytes = 0
    limit = 75
    for char in line:
        char_bytes = len(char.encode("utf-8"))
        if current and current_bytes + char_bytes > limit:
            chunks.append(current)
            current = " " + char
            current_bytes = 1 + char_bytes
        else:
            current += char
            current_bytes += char_bytes
    if current:
        chunks.append(current)
    return "\r\n".join(chunks)


def _parse_dtstamp(last_updated):
    dt = None
    if last_updated:
        try:
            dt = datetime.fromisoformat(last_updated)
        except ValueError:
            dt = None
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def build_ical_feed(tours, last_updated=None):
    dtstamp = _parse_dtstamp(last_updated)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//steam-scraper//Heritage Rail Tours//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Heritage Rail Tours",
        "X-WR-CALDESC:Heritage rail tours across Victoria.",
    ]

    for tour in tours:
        operator = tour.get("operator") or "Unknown operator"
        start = date.fromisoformat(tour["date"])
        end_inclusive = date.fromisoformat(tour.get("end_date") or tour["date"])
        end_exclusive = end_inclusive + timedelta(days=1)

        uid_seed = f"{operator}|{tour['date']}|{tour['title']}".encode("utf-8")
        uid = f"{hashlib.sha256(uid_seed).hexdigest()[:16]}@steam-scraper"

        description_parts = list(tour.get("details") or ())
        for link in tour.get("links") or ():
            url = link.get("url")
            if url and url.startswith(("http://", "https://")):
                label = link.get("text")
                description_parts.append(f"{label}: {url}" if label else url)

        summary = f"{operator}: {tour['title']}"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{end_exclusive.strftime('%Y%m%d')}",
                f"SUMMARY:{_escape_ical_text(summary)}",
            ]
        )
        if description_parts:
            lines.append(
                f"DESCRIPTION:{_escape_ical_text(chr(10).join(description_parts))}"
            )
        primary_url = _first_http_url(tour.get("links"))
        if primary_url:
            lines.append(f"URL:{primary_url}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold_ical_line(line) for line in lines) + "\r\n"


@app.get("/")
def tours():
    try:
        with TOURS_FILE.open(encoding="utf-8") as json_file:
            data = json.load(json_file)
    except FileNotFoundError:
        data = {"tours": [], "last_updated": None}
    upcoming_tours, past_tours = split_tours(data["tours"])
    return render_template(
        "index.html",
        upcoming_tours=upcoming_tours,
        past_tours=past_tours,
        last_updated=format_last_updated(data.get("last_updated")),
    )


@app.get("/feed.xml")
def rss_feed():
    with TOURS_FILE.open(encoding="utf-8") as json_file:
        data = json.load(json_file)
    upcoming_tours, _ = split_tours(data["tours"])
    xml_bytes = build_rss_feed(
        upcoming_tours,
        data.get("last_updated"),
        site_url=request.url_root,
        feed_url=request.url,
    )
    return Response(xml_bytes, mimetype="application/rss+xml; charset=utf-8")


@app.get("/tours.ics")
def ical_feed():
    with TOURS_FILE.open(encoding="utf-8") as json_file:
        data = json.load(json_file)
    ics_text = build_ical_feed(data["tours"], data.get("last_updated"))
    return Response(
        ics_text,
        mimetype="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="tours.ics"'},
    )



@app.get("/archive")
def tour_archive():
    tours = archived_tours(load_archive(ARCHIVE_FILE))
    return render_template("archive.html", tours_by_year=group_tours_by_year(tours))

if __name__ == "__main__":
    app.run(port=6234)