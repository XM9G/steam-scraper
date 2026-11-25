from playwright.sync_api import sync_playwright

from scrapers.dates import normalize_tour_date


URL = "https://www.slowrailjourneys.com.au/upcoming-journeys"

PAGE_DATA_SCRIPT = r"""() => {
    return [...document.querySelectorAll('a[href*="/post/"]')].flatMap(link => {
        const card = link.closest(".gallery-item-container") ||
            link.closest('[data-hook="post-list-item"]') ||
            link.parentElement;
        const titleElement = card.querySelector('[data-hook="post-title"]');
        const descriptionElement = card.querySelector('[data-hook="post-description"]');
        const loadedImages = [...card.querySelectorAll(
            'img[data-hook="gallery-item-image-img"]'
        )];
        const images = loadedImages.length
            ? loadedImages
            : [...card.querySelectorAll("img")];
        const rawTitle = (titleElement?.innerText || link.innerText).trim();
        const dateMatch = rawTitle.match(
            /^((?:\d{1,2}\s*[-–]\s*\d{1,2}|\d{1,2})\s+[A-Za-z]+(?:\s+\d{4})?)/
        );
        const date = dateMatch ? dateMatch[1].replace(/\s+/g, " ").trim() : "";
        let title = dateMatch
            ? rawTitle.slice(dateMatch[0].length).replace(/^\s*[-:]\s*/, "").trim()
            : rawTitle;
        const details = [];
        const subtitleMarker = "Exclusive Overnight Escape:";
        const subtitleIndex = title.indexOf(subtitleMarker);
        if (subtitleIndex !== -1) {
            details.push(title.slice(subtitleIndex).trim());
            title = title.slice(0, subtitleIndex).trim();
        }
        const description = descriptionElement?.innerText.trim();
        if (description) details.push(description);

        return [{
            date,
            title,
            details,
            url: link.href,
            images: images.flatMap(image => {
                const url = image.currentSrc ||
                    image.src ||
                    image.dataset.src ||
                    image.dataset.original ||
                    image.getAttribute("data-lazy-src");
                return url ? [{
                    url,
                    alt: image.alt,
                    title: image.title
                }] : [];
            })
        }];
    });
}"""


def _clean_lines(lines):
    return [
        line.strip()
        for text in lines
        for line in text.replace("\ufeff", "").splitlines()
        if line.strip()
    ]


def _build_tour(record):
    start_date, end_date = normalize_tour_date(
        record["date"],
        assume_current_year=True,
    )
    return {
        "operator": "Slow Rail Journeys",
        "date": start_date,
        "end_date": end_date,
        "date_text": record["date"],
        "title": record["title"],
        "details": _clean_lines(record["details"]),
        "links": [{"text": "View journey", "url": record["url"]}],
        "images": record["images"],
    }


def scrape_slowrailjourneys():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_default_navigation_timeout(60000)
            page.goto(URL, wait_until="domcontentloaded")
            page.wait_for_selector('a[href*="/post/"]', timeout=30000)
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
            records = page.evaluate(PAGE_DATA_SCRIPT)
        finally:
            browser.close()

    tours = [
        _build_tour(record)
        for record in records
        if record["title"]
    ]
    if not tours:
        raise RuntimeError("No journeys were found on the Slow Rail Journeys page.")

    return {"tours": tours}