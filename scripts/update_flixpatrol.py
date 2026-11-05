import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scrapling.fetchers import StealthySession


ROOT_URL = "https://flixpatrol.com/top10/"
COUNTRY_URL = "https://flixpatrol.com/top10/streaming/{country}/"
WORLD_URL = ROOT_URL
OUTPUT_DIR = Path("data/flixpatrol")
TMDB_CACHE_FILE = OUTPUT_DIR / "tmdb-cache.json"
COUNTRY_LINK = re.compile(r"^/top10/[^/]+/([^/]+)/(20\d{2}-\d{2}-\d{2})/$")
HEADING_INFO = re.compile(r"^(.*?) TOP 10 in (.*?) on ([A-Z][a-z]+ \d{1,2}, \d{4})$")
MAIN_COUNTRIES = (
    "world", "united-states", "hong-kong", "taiwan", "singapore", "malaysia",
    "united-kingdom", "spain", "nigeria", "canada", "south-korea", "japan",
    "australia", "new-zealand", "india", "thailand", "indonesia", "philippines",
    "vietnam", "germany", "france", "italy", "netherlands", "sweden", "brazil",
    "mexico", "argentina", "turkey", "united-arab-emirates", "saudi-arabia",
    "south-africa",
)


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


def title_key(value):
    return re.sub(r"[^\w]+", "", str(value or "").casefold(), flags=re.UNICODE)


def item_year(item):
    match = re.search(r"-(19\d{2}|20\d{2})/$", str(item.get("sourcePath", "")))
    return match.group(1) if match else ""


def tmdb_get(path, params):
    api_key = os.environ.get("TMDB_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("TMDB_API_KEY is required")
    headers = {"Accept": "application/json"}
    query = dict(params)
    if api_key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        query["api_key"] = api_key
    request = Request(f"https://api.themoviedb.org/3/{path}?{urlencode(query)}", headers=headers)
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def match_tmdb(item):
    expected_type = item.get("mediaType") if item.get("mediaType") in ("movie", "tv") else ""
    target = title_key(item.get("title"))
    year = item_year(item)
    matches = {}
    for media_type in ([expected_type] if expected_type else ["movie", "tv"]):
        params = {"query": item.get("title", ""), "language": "en-US", "include_adult": "false"}
        if year:
            params["year" if media_type == "movie" else "first_air_date_year"] = year
        for candidate in tmdb_get(f"search/{media_type}", params).get("results", []):
            names = [candidate.get(key) for key in ("title", "name", "original_title", "original_name")]
            normalized = [title_key(name) for name in names if name]
            if target not in normalized:
                continue
            release_date = candidate.get("release_date") or candidate.get("first_air_date") or ""
            if year and not release_date.startswith(year):
                continue
            matches[candidate.get("id")] = {
                "tmdbId": candidate.get("id"),
                "mediaType": media_type,
            }
    return next(iter(matches.values())) if len(matches) == 1 else None


def enrich_tmdb(results):
    if not os.environ.get("TMDB_API_KEY", "").strip():
        raise RuntimeError("TMDB_API_KEY is required to publish FlixPatrol data")
    cache = json.loads(TMDB_CACHE_FILE.read_text(encoding="utf-8")) if TMDB_CACHE_FILE.exists() else {}
    references = {}
    for data in results:
        for platform in data["platforms"].values():
            for items in platform["charts"].values():
                for item in items:
                    key = f"v3:{item.get('mediaType', 'multi')}:{title_key(item.get('title'))}:{item_year(item)}"
                    references.setdefault(key, []).append(item)

    missing = {key: items[0] for key, items in references.items() if key not in cache}
    if missing:
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(match_tmdb, item): key for key, item in missing.items()}
            for index, future in enumerate(as_completed(futures), 1):
                key = futures[future]
                try:
                    match = future.result()
                    if match and match.get("tmdbId"):
                        cache[key] = match
                except Exception as error:
                    print(f"TMDB failed for {missing[key].get('title')}: {error}")
                if index % 100 == 0:
                    print(f"TMDB matched {index}/{len(missing)} new titles")

    matched = 0
    total = 0
    for key, items in references.items():
        info = cache.get(key)
        for item in items:
            total += 1
            if info:
                item.update(info)
                matched += 1
    write_json(TMDB_CACHE_FILE, cache)
    print(f"TMDB enriched {matched}/{total} chart entries using source language en-US")


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
        selected = [slug for slug in (requested or MAIN_COUNTRIES) if slug in countries]
        print(f"Discovered {len(countries)} countries; fetching {len(selected)} pages")

        for index, slug in enumerate(selected, 1):
            try:
                page = world_page if slug == "world" else fetch_page(session, COUNTRY_URL.format(country=slug))
                data = parse_country_page(page, slug, countries[slug])
                results.append(data)
                print(f"[{index}/{len(selected)}] {slug}: {len(data['platforms'])} platforms")
            except Exception as error:
                failures.append({"country": slug, "error": str(error)})
                print(f"[{index}/{len(selected)}] {slug}: FAILED - {error}")
            time.sleep(delay)

    if not results:
        raise RuntimeError("FlixPatrol returned no country data")

    enrich_tmdb(results)
    for data in results:
        write_json(OUTPUT_DIR / f"{data['country']['slug']}.json", data)

    platform_names = {}
    for data in results:
        for slug, platform in data["platforms"].items():
            platform_names.setdefault(slug, platform["name"])
    available = [
        {"slug": slug, "name": countries[slug], "file": f"{slug}.json"}
        for slug in selected
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
