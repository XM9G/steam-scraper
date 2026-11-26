# Posts newly found tours to a Discord channel. Set DISCORD_WEBHOOK_URL to enable.

from datetime import date, datetime, time
import json
import os
import re
from urllib.request import Request, urlopen

from tags import tour_tags


OPERATOR_STYLE = {
    "Steamrail Victoria": (0xB30000, "https://www.steamrail.com.au/tours"),
    "Slow Rail Journeys": (0x000080, "https://www.slowrailjourneys.com.au/upcoming-journeys"),
    "707 Operations": (0xE0322A, "https://www.707operations.com/day"),
    "Seymour Railway Heritage Centre": (0x1B2237, "https://srhc.org.au/tours/"),
}
EMBEDS_PER_MESSAGE = 10  # Discord's limit


def _first_http_url(items):
    for item in items or ():
        url = item.get("url") or ""
        if url.startswith(("http://", "https://")):
            return url
    return None


def _booking_url(links):
    """Prefer a "Book Now" / tickets link over e.g. a membership sign-up link."""
    for link in links or ():
        text = (link.get("text") or "").lower()
        if ("book" in text or "ticket" in text) and (link.get("url") or "").startswith(("http://", "https://")):
            return link["url"]
    return _first_http_url(links)


def _trim(text, limit):
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build_embed(tour):
    tags = tour_tags(tour)
    color, operator_url = OPERATOR_STYLE.get(tour.get("operator"), (0x555555, None))

    start = datetime.combine(date.fromisoformat(tour["date"]), time()).astimezone()
    when = f"{tour.get('date_text') or tour['date']} (<t:{int(start.timestamp())}:R>)"

    fields = [
        {"name": "Date", "value": when, "inline": False},
        {"name": "Operator", "value": tour.get("operator") or "Unknown", "inline": True},
    ]
    kinds = tags["traction"] + ([tags["gauge"]] if tags["gauge"] else [])
    if kinds:
        fields.append({"name": "Type", "value": ", ".join(kinds), "inline": True})

    embed = {
        "title": _trim(tags["title"], 256),
        "color": color,
        "fields": fields,
    }
    url = _booking_url(tour.get("links")) or operator_url
    if url:
        embed["url"] = url
    if tags["details"]:
        embed["description"] = _trim(tags["details"][0], 300)
    image = _first_http_url(tour.get("images"))
    if image:
        embed["thumbnail"] = {"url": image}
    return embed


def build_messages(tours):
    return [
        {
            "embeds": [build_embed(tour) for tour in tours[start : start + EMBEDS_PER_MESSAGE]],
            "allowed_mentions": {"parse": []},
        }
        for start in range(0, len(tours), EMBEDS_PER_MESSAGE)
    ]


def webhook_urls(value):
    """DISCORD_WEBHOOK_URL can hold several webhooks separated by commas or spaces."""
    return [url for url in re.split(r"[\s,]+", value or "") if url]


def notify_discord(tours, webhook_url=None, opener=urlopen):
    urls = webhook_urls(webhook_url or os.environ.get("DISCORD_WEBHOOK_URL"))
    if not urls or not tours:
        return 0
    messages = build_messages(tours)
    delivered = 0
    for url in urls:
        try:
            for message in messages:
                request = Request(
                    url,
                    data=json.dumps(message).encode("utf-8"),
                    # Discord's Cloudflare rejects Python's default user agent.
                    headers={"Content-Type": "application/json", "User-Agent": "steam-scraper/1.0"},
                    method="POST",
                )
                with opener(request, timeout=15) as response:
                    response.read()
            delivered += 1
        except Exception as exc:
            # One broken webhook shouldn't stop the others.
            print(f"Could not post to a Discord webhook: {exc}")
    print(f"Posted {len(tours)} new tours to {delivered} of {len(urls)} Discord webhooks")
    return delivered
