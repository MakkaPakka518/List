import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scrapling.fetchers import Fetcher


BASE_URL = "https://ani.gamer.com.tw/animeList.php"
DATA_FILE = Path("data/anigamer-hot.json")
CACHE_FILE = Path("data/anigamer-tmdb-cache.json")
STATUS_FILE = Path("data/anigamer-status.json")
PAGES = range(1, 6)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def safe_reason(error, proxy):
    message = str(error).replace(proxy, "[REDACTED_PROXY]") if proxy else str(error)
    message = re.sub(r"socks5h?://[^\s@]+@", "socks5://[REDACTED]@", message)
    lower = message.lower()
    if "407" in message or "auth" in lower:
        return "台湾代理认证失败，请检查 ANIGAMER_PROXY_URL 的账号或密码"
    if "timeout" in lower or "timed out" in lower:
        return "通过台湾代理访问动画疯超时"
    if "403" in message:
        return "动画疯返回 403，代理可能未生效或出口不在台湾"
    if any(word in lower for word in ("proxy", "connect", "resolve", "dns")):
        return "台湾代理无法连接或解析域名"
    return message[:500]


def title_key(value):
    text = re.sub(r"第[一二三四五六七八九十百\d]+季", "", str(value or ""), flags=re.I)
    text = re.sub(r"Season\s*\d+", "", text, flags=re.I)
    return re.sub(r"[^\w]+", "", text.casefold(), flags=re.UNICODE)


def parse_page(page):
    items = []
    for link in page.css('a.theme-list-main[href^="animeRef.php?sn="]'):
        href = str(link.attrib.get("href", ""))
        sn_match = re.search(r"sn=(\d+)", href)
        title_nodes = link.css(".theme-name")
        title = str(title_nodes[0].text).strip() if title_nodes else ""
        if not sn_match or not title:
            continue
        time_nodes = link.css(".theme-time")
        year_match = re.search(r"(19\d{2}|20\d{2})", str(time_nodes[0].text) if time_nodes else "")
        label_nodes = link.css(".anime-label-block")
        label = " ".join(map(str, label_nodes[0].xpath(".//text()").getall())) if label_nodes else ""
        items.append({
            "sn": sn_match.group(1),
            "sourceTitle": title,
            "year": year_match.group(1) if year_match else "",
            "mediaHint": "movie" if "電影" in label else "",
        })
    return items


def fetch_page(proxy, sort, page):
    params = urlencode({"tags": "全部", "category": "全部", "target": "全部", "sort": sort, "page": page})
    response = Fetcher.get(f"{BASE_URL}?{params}", proxy=proxy, timeout=60)
    if response.status != 200:
        raise RuntimeError(f"动画疯 HTTP {response.status}: sort={sort} page={page}")
    items = parse_page(response)
    if not items:
        raise RuntimeError(f"动画疯页面结构变化或榜单为空: sort={sort} page={page}")
    return items


def tmdb_get(path, params):
    api_key = os.environ.get("TMDB_API_KEY", "").strip()
    headers = {"Accept": "application/json"}
    query = dict(params)
    if api_key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        query["api_key"] = api_key
    request = Request(f"https://api.themoviedb.org/3/{path}?{urlencode(query)}", headers=headers)
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def match_tmdb(item):
    target = title_key(item["sourceTitle"])
    types = [item["mediaHint"]] if item["mediaHint"] else ["tv", "movie"]
    for media_type in types:
        for with_year in (True, False):
            params = {"query": item["sourceTitle"], "language": "zh-TW", "include_adult": "false"}
            if with_year and item["year"]:
                params["year" if media_type == "movie" else "first_air_date_year"] = item["year"]
            candidates = tmdb_get(f"search/{media_type}", params).get("results", [])
            exact = [candidate for candidate in candidates if title_key(candidate.get("title") or candidate.get("name") or candidate.get("original_title") or candidate.get("original_name")) == target]
            matches = exact or [candidate for candidate in candidates if target and (target in title_key(candidate.get("title") or candidate.get("name")) or title_key(candidate.get("title") or candidate.get("name")) in target)]
            if item["year"]:
                dated = [candidate for candidate in matches if str(candidate.get("release_date") or candidate.get("first_air_date") or "").startswith(item["year"])]
                if dated:
                    return {"tmdbId": dated[0]["id"], "mediaType": media_type}
                if with_year:
                    continue
            if matches:
                return {"tmdbId": matches[0]["id"], "mediaType": media_type}
    return None


def main():
    proxy = os.environ.get("ANIGAMER_PROXY_URL", "").strip()
    if not proxy:
        raise RuntimeError("ANIGAMER_PROXY_URL Secret 未配置")
    if not proxy.startswith(("socks5://", "socks5h://")):
        raise RuntimeError("ANIGAMER_PROXY_URL 必须是 SOCKS5 链接")
    if not os.environ.get("TMDB_API_KEY", "").strip():
        raise RuntimeError("TMDB_API_KEY Secret 未配置")

    lists = {"monthly": {}, "yearly": {}}
    unique = {}
    for name, sort in (("monthly", "2"), ("yearly", "1")):
        for page in PAGES:
            items = fetch_page(proxy, sort, page)
            lists[name][str(page)] = items
            for item in items:
                key = f"v1:{item['sn']}:{item['year']}:{item['mediaHint'] or 'all'}"
                unique.setdefault(key, item)
            time.sleep(0.5)

    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}
    missing = {key: item for key, item in unique.items() if key not in cache}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(match_tmdb, item): key for key, item in missing.items()}
        for future in as_completed(futures):
            key = futures[future]
            match = future.result()
            if match:
                cache[key] = match

    matched = 0
    total = 0
    for pages in lists.values():
        for items in pages.values():
            for item in items:
                total += 1
                key = f"v1:{item['sn']}:{item['year']}:{item['mediaHint'] or 'all'}"
                if key in cache:
                    item.update(cache[key])
                    matched += 1

    output = {
        "schemaVersion": 1,
        "source": "AniGamer",
        "sourceUrl": BASE_URL,
        "updatedAt": now(),
        "lists": lists,
    }
    write_json(DATA_FILE, output)
    write_json(CACHE_FILE, cache)
    write_json(STATUS_FILE, {"ok": True, "updatedAt": now(), "matched": matched, "total": total, "unmatched": total - matched})
    print(f"AniGamer updated: matched {matched}/{total}")


if __name__ == "__main__":
    proxy = os.environ.get("ANIGAMER_PROXY_URL", "").strip()
    try:
        main()
    except Exception as error:
        reason = safe_reason(error, proxy)
        write_json(STATUS_FILE, {"ok": False, "updatedAt": now(), "reason": reason})
        print(f"AniGamer update failed: {reason}", file=sys.stderr)
        raise SystemExit(1)
