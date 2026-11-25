import re

from playwright.sync_api import sync_playwright

from scrapers.dates import normalize_tour_date


URL = "https://srhc.org.au/tours/"
OPERATOR = "Seymour Railway Heritage Centre"

DATE_LINE_PATTERN = re.compile(
    r"^((?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+)?"
    r"\d{1,2}(?:st|nd|rd|th)?(?:\s*[-–]\s*\d{1,2}(?:st|nd|rd|th)?)?\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"(?:\s+\d{4})?)"
    r"(?:\s*[–—-]\s*(.+))?$",
    re.IGNORECASE,
)

PAGE_DATA_SCRIPT = r"""() => {
    const main = document.querySelector("main") || document.body;
    const dateLinePattern = /^(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+)?\d{1,2}(?:st|nd|rd|th)?(?:\s*[-–]\s*\d{1,2}(?:st|nd|rd|th)?)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\b/i;
    const sections = [...main.querySelectorAll("section.elementor-top-section")];

    return sections.flatMap(section => {
        const heading = section.querySelector(".elementor-widget-heading h2, h2.elementor-heading-title, h2");
        const title = heading ? heading.innerText.replace(/\s+/g, " ").trim() : "";
        const editor = section.querySelector(".elementor-widget-text-editor");
        if (!title || !editor) return [];

        const paragraphs = [...editor.querySelectorAll("p")]
            .map(p => p.innerText.replace(/\u00a0/g, " ").trim())
            .filter(Boolean);
        if (!paragraphs.length) return [];

        const firstLines = paragraphs[0]
            .split(/\r?\n/)
            .map(line => line.trim())
            .filter(Boolean);
        if (!firstLines.length || !dateLinePattern.test(firstLines[0])) return [];

        const links = [];
        const unlinkedButtonLabels = [];
        const seenUrls = new Set();

        for (const anchor of section.querySelectorAll("a")) {
            const text = anchor.innerText.replace(/\s+/g, " ").trim();
            if (anchor.href) {
                if (!seenUrls.has(anchor.href)) {
                    seenUrls.add(anchor.href);
                    links.push({
                        text: text || "View tour",
                        url: anchor.href
                    });
                }
            } else if (text && !unlinkedButtonLabels.includes(text)) {
                unlinkedButtonLabels.push(text);
            }
        }

        const images = [...section.querySelectorAll("img")].flatMap(image => {
            const url = image.currentSrc ||
                image.src ||
                image.dataset.src ||
                image.dataset.original ||
                image.getAttribute("data-lazy-src");
            if (!url || url.startsWith("data:")) return [];
            return [{
                url,
                alt: image.alt || "",
                title: image.title || ""
            }];
        });

        return [{
            title,
            paragraphs,
            links,
            unlinked_labels: unlinkedButtonLabels,
            images
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
    paragraphs = record["paragraphs"]
    first_lines = _clean_lines([paragraphs[0]])
    if not first_lines:
        raise ValueError(f"Missing date line for SRHC tour: {record.get('title')!r}")

    date_match = DATE_LINE_PATTERN.match(first_lines[0])
    if not date_match:
        raise ValueError(f"Could not parse SRHC tour date line: {first_lines[0]!r}")

    date_text = re.sub(r"\s+", " ", date_match.group(1)).strip()
    start_date, end_date = normalize_tour_date(
        date_text,
        assume_current_year=True,
    )

    details = []
    if date_match.group(2):
        details.append(date_match.group(2).strip())
    details.extend(first_lines[1:])
    details.extend(_clean_lines(paragraphs[1:]))
    details.extend(_clean_lines(record.get("unlinked_labels", [])))

    return {
        "operator": OPERATOR,
        "date": start_date,
        "end_date": end_date,
        "date_text": date_text,
        "title": record["title"],
        "details": details,
        "links": record.get("links", []),
        "images": record.get("images", []),
    }


def scrape_srhc():
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
            records = page.evaluate(PAGE_DATA_SCRIPT)
        finally:
            browser.close()

    tours = [_build_tour(record) for record in records]
    if not tours:
        raise RuntimeError("No tours were found on the SRHC tours page.")

    return {"tours": tours}
