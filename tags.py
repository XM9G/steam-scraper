import re


# Steamrail puts the traction in brackets after the title, e.g. "(D)" or "(S & E)".
# SRHC puts gauge and traction on the first detail line, e.g. "(SG) – D".
TRACTION_NAMES = {"S": "Steam", "D": "Diesel", "E": "Electric"}
GAUGE_NAMES = {"SG": "Standard gauge", "BG": "Broad gauge", "NG": "Narrow gauge"}
TRACTION_LETTERS = r"[SDE](?:\s*[&/,+]\s*[SDE])*"
STEAMRAIL_TRACTION_PATTERN = re.compile(rf"\s*\(\s*({TRACTION_LETTERS})\s*\)")
SRHC_TRACTION_PATTERN = re.compile(rf"^\(\s*(SG|BG|NG)\s*\)(?:\s*[–—-]\s*({TRACTION_LETTERS}))?$")


def _traction_names(letters):
    return [TRACTION_NAMES[letter] for letter in dict.fromkeys(re.findall(r"[SDE]", letters))]


def tour_tags(tour):
    title = tour.get("title") or ""
    details = list(tour.get("details") or [])
    traction = []
    gauge = None

    if tour.get("operator") == "Steamrail Victoria":
        match = STEAMRAIL_TRACTION_PATTERN.search(title)
        if match:
            traction = _traction_names(match.group(1))
            title = (title[:match.start()] + title[match.end():]).strip() or title

    elif tour.get("operator") == "Seymour Railway Heritage Centre" and details:
        match = SRHC_TRACTION_PATTERN.match(details[0].strip())
        if match:
            gauge = GAUGE_NAMES[match.group(1)]
            traction = _traction_names(match.group(2) or "")
            details = details[1:]

    return {"title": title, "details": details, "traction": traction, "gauge": gauge}
