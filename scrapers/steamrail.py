import argparse
import json
from pathlib import Path
import re

from playwright.sync_api import sync_playwright

from scrapers.dates import normalize_tour_date


URL = "https://www.steamrail.com.au/tours"
DEFAULT_OUTPUT_PATH = Path("steamrail_tours.json")
DATE_PATTERN = re.compile(
    r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
    r"\s+\d{1,2}(?:st|nd|rd|th)?\b.*\b\d{4}$",
    re.IGNORECASE,
)

PAGE_DATA_SCRIPT = r"""() => {
    const main = document.querySelector("main") || document.body;
    const headings = [...main.querySelectorAll("h1, h2, h3, h4, h5, h6")];
    const datePattern = /^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+\d{1,2}(?:st|nd|rd|th)?\b.*\b\d{4}$/i;
    const pastHeading = headings.find(heading => /^Past Tours\b/i.test(heading.innerText.trim()));
    const dateHeadings = headings.filter(heading =>
        datePattern.test(heading.innerText.replace(/\s+/g, " ").trim())
    );
    const tours = dateHeadings
        .filter(heading => !pastHeading ||
            !(pastHeading.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING))
        .map(heading => {
            const group = heading.closest(".element-group") ||
                heading.closest("article") ||
                heading.parentElement;
            const imageContainer = heading.closest(".w-container.row") || group;
            const rawDate = heading.innerText.trim();
            const titleHeading = [...group.querySelectorAll("h1, h2, h3, h4, h5, h6")]
                .find(candidate => candidate !== heading && candidate.innerText.trim());
            const title = titleHeading
                ? titleHeading.innerText.replace(/\s+/g, " ").trim()
                : null;
            const rawText = group.innerText.trim();
            let detailsText = rawText.startsWith(rawDate)
                ? rawText.slice(rawDate.length).trim()
                : rawText;
            if (title && detailsText.startsWith(title)) {
                detailsText = detailsText.slice(title.length).trim();
            }
            return {
                date: rawDate.replace(/\s+/g, " "),
                title,
                details_text: detailsText,
                raw_text: rawText,
                links: [...group.querySelectorAll("a")].map(link => ({
                    text: link.innerText.trim(),
                    url: link.href
                })),
                images: [...imageContainer.querySelectorAll("img")].flatMap(image => {
                    const url = image.currentSrc ||
                        image.src ||
                        image.dataset.src ||
                        image.dataset.original ||
                        image.getAttribute("data-lazy-src") ||
                        image.closest("a")?.href;
                    return url ? [{
                        url,
                        alt: image.alt,
                        title: image.title
                    }] : [];
                })
            };
        });

    return tours;
}"""


def _clean_lines(text):
    return [
        line.strip()
        for line in text.replace("\ufeff", "").splitlines()
        if line.strip()
    ]


def _build_tour(record):
    start_date, end_date = normalize_tour_date(record["date"])
    return {
        "operator": "Steamrail Victoria",
        "date": start_date,
        "end_date": end_date,
        "date_text": record["date"],
        "title": record["title"],
        "details": _clean_lines(record["details_text"]),
        "links": record["links"],
        "images": record["images"],
    }


def scrape_steamrail():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_default_navigation_timeout(60000)
            page.goto(URL, wait_until="domcontentloaded")
            page.wait_for_function(
                "() => document.querySelector('main') && "
                "document.querySelector('main').innerText.trim().length > 100",
                timeout=30000,
            )
            page.evaluate(
                """async () => {
                    for (let y = 0; y < document.body.scrollHeight; y += 600) {
                        window.scrollTo(0, y);
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }
                    window.scrollTo(0, 0);
                }"""
            )
            page.wait_for_timeout(500)
            tour_records = page.evaluate(PAGE_DATA_SCRIPT)
        finally:
            browser.close()

    tour_records = [
        record
        for record in tour_records
        if DATE_PATTERN.match(record["date"])
    ]
    if not tour_records:
        raise RuntimeError(
            "No upcoming tour entries were found on the Steamrail tours page."
        )

    return {"tours": [_build_tour(record) for record in tour_records]}


def steamrail(output_path=DEFAULT_OUTPUT_PATH):
    data = scrape_steamrail()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Steamrail Victoria's tours page to a JSON file."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"JSON output path (default: {DEFAULT_OUTPUT_PATH})",
    )
    args = parser.parse_args()

    data = steamrail(args.output)
    print(f"Wrote {len(data['tours'])} tours to {args.output}")


if __name__ == "__main__":
    main()
