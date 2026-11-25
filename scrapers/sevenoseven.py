from playwright.sync_api import sync_playwright

from scrapers.dates import normalize_tour_date


URL = "https://www.707operations.com/day"

PAGE_DATA_SCRIPT = r"""() => {
    const main = document.querySelector("main") || document.body;
    const comesBefore = (first, second) =>
        Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING);
    const isDate = text => /^\d{1,2}\s+[A-Za-z]+\s+\d{4}$/.test(text.trim());
    const dateElements = [...main.querySelectorAll("p")]
        .filter(element => isDate(element.innerText));
    const headings = [...main.querySelectorAll("h2")]
        .filter(element => element.innerText.replace(/\u200b/g, "").trim());
    const images = [...main.querySelectorAll("img")];

    return dateElements.map((dateElement, index) => {
        const nextDate = dateElements[index + 1];
        const heading = headings.find(element =>
            comesBefore(dateElement, element) &&
            (!nextDate || comesBefore(element, nextDate))
        );
        if (!heading) return null;

        const description = [...main.querySelectorAll("p")]
            .filter(element =>
                comesBefore(heading, element) &&
                (!nextDate || comesBefore(element, nextDate)) &&
                !isDate(element.innerText) &&
                element.innerText.replace(/\u200b/g, "").trim()
            )
            .map(element => element.innerText.trim());
        const image = images
            .filter(element => comesBefore(element, dateElement))
            .pop();
        const imageUrl = image && (
            image.currentSrc ||
            image.src ||
            image.dataset.src ||
            image.dataset.original
        );
        const links = [
            heading.querySelector("a"),
            image && image.closest("a")
        ].filter((link, linkIndex, all) =>
            link && all.indexOf(link) === linkIndex && link.href
        ).map(link => ({
            text: link.innerText.trim() || "View tour",
            url: link.href
        }));

        return {
            date: dateElement.innerText.trim(),
            title: heading.innerText.replace(/\u200b/g, "").trim(),
            details: description,
            links,
            images: imageUrl ? [{
                url: imageUrl,
                alt: image.alt,
                title: image.title
            }] : []
        };
    }).filter(Boolean);
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
        "operator": "707 Operations",
        "date": start_date,
        "end_date": end_date,
        "date_text": record["date"],
        "title": record["title"],
        "details": _clean_lines(record["details"]),
        "links": record["links"],
        "images": record["images"],
    }


def scrape_sevenoseven():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_default_navigation_timeout(60000)
            page.goto(URL, wait_until="domcontentloaded")
            page.wait_for_function(
                "() => [...document.querySelectorAll('p')].some(element => "
                "/^\\d{1,2}\\s+[A-Za-z]+\\s+\\d{4}$/.test(element.innerText.trim()))",
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
            records = page.evaluate(PAGE_DATA_SCRIPT)
        finally:
            browser.close()

    tours = [_build_tour(record) for record in records]
    if not tours:
        raise RuntimeError("No day tours were found on the 707 Operations page.")

    return {"tours": tours}
