import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from scrapling.fetchers import StealthySession


ROOT_URL = "https://flixpatrol.com/top10/"
COUNTRY_URL = "https://flixpatrol.com/top10/streaming/{country}/"
WORLD_URL = "https://flixpatrol.com/top10/streaming/world/today/full/"
OUTPUT_DIR = Path("data/flixpatrol")
COUNTRY_LINK = re.compile(r"^/top10/[^/]+/([^/]+)/(20\d{2}-\d{2}-\d{2})/$")
HEADING_INFO = re.compile(r"^(.*?) TOP 10 in (.*?) on ([A-Z][a-z]+ \d{1,2}, \d{4})$")


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def extract_countries(page):
    countries = {"world": "Worldwide"}
    for link in page.css('a[href^="/top10/"]'):
        match = COUNTRY_LINK.match(str(link.attrib.get("href", "")))
        if not match or match.group(1) == "world":
            continue
        slug = match.group(1)
        countries.setdefault(slug, clean_text(link.text) or slug.replace("-", " ").title())
    return countries


def chart_key(title):
    value = clean_text(title).lower()
    if value.startswith("top 10 kids movies"):
        return "kids_movies"
    if value.startswith("top 10 kids tv shows"):
        return "kids_tv"
    if value.startswith("top 10 movies"):
        return "movies"
    if value.startswith("top 10 tv shows"):
        return "tv"
    if value.startswith("top 10 overall (from amazon channels)"):
        return "amazon_channels"
    if value.startswith("top 10 overall"):
        return "overall"
    return ""


def parse_country_page(page, country_slug, fallback_name):
    platforms = {}
    current_platform = None
    country_name = fallback_name
    chart_date = ""

    for heading in page.css('h2[id^="toc-"], h3'):
        if heading.tag == "h2":
            current_platform = str(heading.attrib.get("id", ""))[4:]
            texts = [clean_text(text) for text in heading.css("span::text").getall() if clean_text(text)]
            full_title = texts[-1] if texts else ""
            match = HEADING_INFO.match(full_title)
            if match:
                platform_name, _heading_country, raw_date = match.groups()
                chart_date = datetime.strptime(raw_date, "%B %d, %Y").date().isoformat()
            else:
                platform_name = current_platform.replace("-", " ").title()
            platforms[current_platform] = {"name": platform_name, "charts": {}}
            continue

        key = chart_key(heading.text)
        if not current_platform or not key:
            continue
        rows = heading.parent.parent.css("table.card-table tr")
        items = []
        for row in rows:
            cells = row.css("td")
            links = cells[2].css('a[href^="/title/"]') if len(cells) >= 3 else []
            rank_match = re.search(r"\d+", clean_text(cells[0].text)) if cells else None
            if not links or not rank_match:
                continue
            source_path = str(links[0].attrib.get("href", ""))
            items.append({
                "rank": int(rank_match.group()),
                "title": clean_text(links[0].text),
                "sourcePath": source_path,
                "movement": clean_text(" ".join(cells[1].xpath(".//text()").getall())) if len(cells) > 1 else "",
                "days": clean_text(cells[3].text) if len(cells) > 3 else "",
            })
        if items:
            platforms[current_platform]["charts"][key] = items[:10]

    for platform in platforms.values():
        known_types = {}
        for key, media_type in (("movies", "movie"), ("kids_movies", "movie"), ("tv", "tv"), ("kids_tv", "tv")):
            for item in platform["charts"].get(key, []):
                known_types[item["sourcePath"]] = media_type
                item["mediaType"] = media_type
        for key in ("overall", "amazon_channels"):
            for item in platform["charts"].get(key, []):
                if item["sourcePath"] in known_types:
                    item["mediaType"] = known_types[item["sourcePath"]]

    if not platforms:
        raise RuntimeError(f"No charts found for {country_slug}")
    return {
        "schemaVersion": 1,
        "source": "FlixPatrol",
        "sourceUrl": COUNTRY_URL.format(country=country_slug) if country_slug != "world" else WORLD_URL,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "chartDate": chart_date,
        "country": {"slug": country_slug, "name": country_name},
        "platforms": platforms,
    }


def fetch_page(session, url):
    last_error = None
    for attempt in range(3):
        try:
            page = session.fetch(url, timeout=90000, wait_selector='h2[id^="toc-"]')
            if page.css('h2[id^="toc-"]'):
                return page
            raise RuntimeError("chart headings missing")
        except Exception as error:
            last_error = error
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    delay = max(0.5, float(os.environ.get("FLIXPATROL_DELAY", "1.0")))
    requested = [value.strip() for value in os.environ.get("FLIXPATROL_COUNTRIES", "").split(",") if value.strip()]
    failures = []
    results = []

    with StealthySession(
        headless=True,
        block_ads=True,
        disable_resources=True,
        solve_cloudflare=True,
        max_pages=1,
    ) as session:
        world_page = fetch_page(session, ROOT_URL)
        countries = extract_countries(world_page)
        selected = requested or list(countries)
        if requested:
            selected = [slug for slug in selected if slug in countries]
        print(f"Discovered {len(countries)} countries; fetching {len(selected)} pages")

        for index, slug in enumerate(selected, 1):
            url = WORLD_URL if slug == "world" else COUNTRY_URL.format(country=slug)
            try:
                data = parse_country_page(fetch_page(session, url), slug, countries[slug])
                write_json(OUTPUT_DIR / f"{slug}.json", data)
                results.append(data)
                print(f"[{index}/{len(selected)}] {slug}: {len(data['platforms'])} platforms")
            except Exception as error:
                failures.append({"country": slug, "error": str(error)})
                print(f"[{index}/{len(selected)}] {slug}: FAILED - {error}")
            time.sleep(delay)

    if not results:
        raise RuntimeError("FlixPatrol returned no country data")

    platform_names = {}
    for data in results:
        for slug, platform in data["platforms"].items():
            platform_names.setdefault(slug, platform["name"])
    available = [
        {"slug": slug, "name": countries[slug], "file": f"{slug}.json"}
        for slug in countries
        if (OUTPUT_DIR / f"{slug}.json").exists()
    ]
    index_data = {
        "schemaVersion": 1,
        "source": "FlixPatrol",
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "chartDate": max((data["chartDate"] for data in results if data["chartDate"]), default=""),
        "countries": available,
        "platforms": [{"slug": slug, "name": name} for slug, name in sorted(platform_names.items())],
        "failures": failures,
    }
    write_json(OUTPUT_DIR / "index.json", index_data)
    print(f"Saved {len(available)} countries; {len(failures)} failed")


if __name__ == "__main__":
    main()
