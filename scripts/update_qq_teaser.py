"""抓取腾讯视频与爱奇艺片库的「本期看点」，写入 data/qq-teaser.json。

每天抓一次，并把每部作品匹配到 TMDB，数据里直接带好：
- 看点：腾讯 second_title（回退 actor_info_core_details）；爱奇艺 desc（回退 kvs.featureSubTitle）
- 标签：tags（腾讯自带类型与标签，爱奇艺用 TMDB 类型补齐）、releaseDate、rating、popularity、voteCount
- 身份：tmdbId、mediaType、posterPath、backdropPath

这样平台剧场模块只在本地筛选、排序、分页，运行时不再请求腾讯/爱奇艺或 TMDB。
"""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

QQ_API = (
    "https://pbaccess.video.qq.com/trpc.multi_vector_layout.mvl_controller"
    ".MVLPageHTTPService/getMVLPage?&vversion_platform=18"
)
QQ_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://v.qq.com",
    "Referer": "https://v.qq.com/tv-series-list/v-index.html",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}
IQ_API = "https://pub.m.iqiyi.com/h5/main/recVideos/lib/"
IQ_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

# 频道 -> (腾讯 channel_id, 爱奇艺 channel_id, TMDB 类型)
CHANNELS = {
    "tv": ("100113", 2, "tv"),
    "movie": ("100173", 1, "movie"),
    "variety": ("100109", 6, "tv"),
    "anime": ("100119", 4, "tv"),
}
IQ_PAGES = (1, 2, 3)
OUTPUT = Path("data/qq-teaser.json")
BEIJING = timezone(timedelta(hours=8))
TMDB_KEY = os.environ.get("TMDB_API_KEY", "").strip()


def clean_title(value):
    return str(value or "").replace("·更新", "").strip()


def clean_year(*values):
    for value in values:
        text = str(value or "")
        if text.isdigit() and len(text) == 4:
            return text
        if len(text) >= 4 and text[:4].isdigit():
            return text[:4]
    return ""


# ---------------------------------------------------------------- 腾讯

def qq_request(channel_id):
    payload = {
        "page_params": {
            "page_type": "operation",
            "page_id": "channel_list",
            "channel_id": channel_id,
            "filter_params": "",
        },
        "page_bypass_params": {
            "params": {
                "platform_id": "2",
                "caller_id": "3000010",
                "data_mode": "default",
                "user_mode": "default",
                "specified_strategy": "",
            },
            "scene": "operation",
        },
        "page_context": {},
    }
    req = Request(QQ_API, data=json.dumps(payload).encode("utf-8"), headers=QQ_HEADERS, method="POST")
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def qq_cards(data):
    modules = (data.get("data") or {}).get("modules") or {}
    for card in ((modules.get("normal") or {}).get("cards") or []):
        poster = (card.get("children_list") or {}).get("poster_card")
        if not poster:
            continue
        items = poster.get("cards") or poster
        if isinstance(items, list) and items:
            return [item.get("params") or {} for item in items]
    return []


QQ_NOISE = re.compile(r"评分|预约|在追|讨论|更新|全\s*\d+\s*集|^\d+(\.\d+)?$|剧场$")


def qq_tags(params):
    tags = []
    genre = str(params.get("main_genre") or "").strip()
    if genre:
        tags.append(genre)
    raw = params.get("chnlist_search_label")
    if raw:
        try:
            for item in json.loads(raw):
                label = str(item.get("label") or "").strip()
                if label and not QQ_NOISE.search(label) and label not in tags:
                    tags.append(label)
        except Exception:
            pass
    return tags[:8]


def parse_qq(params):
    teaser = str(params.get("second_title") or "").strip()
    if not teaser:
        teaser = str(params.get("actor_info_core_details") or "").strip()
    cid = str(params.get("cid") or "").strip()
    title = clean_title(params.get("title"))
    if not cid or not title:
        return None
    return {
        "source": "qq",
        "cid": cid,
        "title": title,
        "teaser": teaser,
        "year": clean_year(params.get("year"), params.get("publish_date")),
        "genre": str(params.get("main_genre") or "").strip(),
        "area": str(params.get("area_name") or "").strip(),
        "episodeText": str(params.get("timelong") or "").strip(),
        "tags": qq_tags(params),
    }


def collect_qq(channel_id):
    entries = []
    for params in qq_cards(qq_request(channel_id)):
        entry = parse_qq(params)
        if entry:
            entries.append(entry)
    return entries


# ---------------------------------------------------------------- 爱奇艺

def iq_request(channel_id, page):
    query = {
        "page_id": page,
        "mode": 11,
        "channel_id": channel_id,
        "ret_num": 21,
        "pos": 1,
        "type": "list",
        "post": "list",
        "from": "mobile_videolib",
        "is_unified_interface": 1,
        "version": "1.0.0",
        "play_platform": "H5_QIYI",
    }
    req = Request(
        IQ_API + "?" + urlencode(query),
        headers={"User-Agent": IQ_UA, "Referer": "https://m.iqiyi.com/", "Accept": "application/json"},
    )
    with urlopen(req, timeout=30) as response:
        body = json.load(response)
    return ((body.get("data") or {}).get("videos") or [])


def parse_iq(video):
    kvs = video.get("kvs") or {}
    teaser = str(video.get("desc") or "").strip()
    if not teaser:
        teaser = str(kvs.get("featureSubTitle") or "").strip()
    aid = str(video.get("albumId") or video.get("qipuId") or "").strip()
    title = clean_title(video.get("albumName") or video.get("shortTitle"))
    if not aid or not title:
        return None
    return {
        "source": "iq",
        "cid": "iq" + aid,
        "title": title,
        "teaser": teaser,
        "year": clean_year(video.get("year"), video.get("period")),
        "genre": "",
        "area": "",
        "episodeText": str(video.get("lowerRightCorner") or "").strip(),
        "tags": [],
    }


def collect_iq(channel_id):
    entries, seen = [], set()
    for page in IQ_PAGES:
        for video in iq_request(channel_id, page):
            entry = parse_iq(video)
            if entry and entry["cid"] not in seen:
                seen.add(entry["cid"])
                entries.append(entry)
    return entries


# ---------------------------------------------------------------- TMDB

def tmdb_get(path, params):
    if not TMDB_KEY:
        raise RuntimeError("TMDB_API_KEY is required to publish QQ teaser data")
    headers = {"Accept": "application/json"}
    query = dict(params)
    if TMDB_KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {TMDB_KEY}"
    else:
        query["api_key"] = TMDB_KEY
    request = Request(f"https://api.themoviedb.org/3/{path}?{urlencode(query)}", headers=headers)
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def norm_title(value):
    text = str(value or "").lower()
    text = re.sub(r"[（(][^)）]*[)）]", "", text)
    return re.sub(r"[^\w]+", "", text, flags=re.UNICODE)


def title_variants(title):
    raw = str(title or "").strip()
    if not raw:
        return []
    out = []

    def add(value):
        text = str(value or "").strip()
        if len(text) >= 2 and text not in out:
            out.append(text)

    add(raw)
    base = re.sub(r"[（(][^)）]*[)）]", "", raw)
    base = re.sub(r"【[^】]*】|\[[^\]]*\]", "", base).strip()
    add(base)
    add(base.split("·")[0].strip())
    add(re.sub(r"第\s*[0-9一二三四五六七八九十]+\s*[季期部篇].*$", "", base).strip())
    return out


def best_match(results, names, year):
    best, best_score = None, 0.0
    for result in results or []:
        if not result or not result.get("id"):
            continue
        titles = [result.get(key) for key in ("name", "title", "original_name", "original_title")]
        titles = [value for value in titles if value]
        score = 0.0
        for name in names:
            for title in titles:
                score = max(score, SequenceMatcher(None, norm_title(name), norm_title(title)).ratio())
        date = str(result.get("first_air_date") or result.get("release_date") or "")
        if year and date[:4] == year:
            score += 0.5
        elif year and date and abs(int(date[:4]) - int(year)) == 1:
            score += 0.25
        score += min(0.2, float(result.get("popularity") or 0) / 5000)
        if score > best_score:
            best, best_score = result, score
    return best if best_score >= 0.72 else None


def resolve(entry, media_type):
    names = title_variants(entry["title"])
    for kind in (media_type, "movie" if media_type == "tv" else "tv"):
        for name in names[:2]:
            try:
                data = tmdb_get(f"search/{kind}", {"query": name, "language": "zh-CN", "include_adult": "false"})
            except Exception:
                continue
            hit = best_match(data.get("results"), names, entry["year"])
            if not hit:
                continue
            date = str(hit.get("first_air_date") or hit.get("release_date") or "")
            genres = tmdb_genres(kind, hit["id"])
            return {
                "tmdbId": hit["id"],
                "mediaType": kind,
                "posterPath": hit.get("poster_path") or "",
                "backdropPath": hit.get("backdrop_path") or "",
                "releaseDate": date,
                "rating": hit.get("vote_average") or 0,
                "voteCount": hit.get("vote_count") or 0,
                "popularity": hit.get("popularity") or 0,
                "genres": genres,
            }
    return None


GENRE_CACHE = {}


def tmdb_genres(kind, tmdb_id):
    key = f"{kind}:{tmdb_id}"
    if key in GENRE_CACHE:
        return GENRE_CACHE[key]
    names = []
    try:
        detail = tmdb_get(f"{kind}/{tmdb_id}", {"language": "zh-CN"})
        names = [str(genre.get("name") or "").strip() for genre in detail.get("genres") or []]
    except Exception:
        pass
    GENRE_CACHE[key] = [name for name in names if name]
    return GENRE_CACHE[key]


def merge_entries(primary, extra):
    """同一部作品的两个平台条目合成一条：腾讯优先，缺失字段互相补齐。"""
    merged = dict(primary)
    for key, value in extra.items():
        if merged.get(key) in ("", None, []):
            merged[key] = value
    merged["tags"] = list(dict.fromkeys((primary.get("tags") or []) + (extra.get("tags") or [])))
    merged["alsoOn"] = [s for s in {primary.get("source"), extra.get("source")} if s] \
        if primary.get("source") != extra.get("source") else [primary.get("source")]
    return merged


def dedupe(entries):
    """TMDB 匹配后按 tmdbId 去重；腾讯条目优先，其余字段取并集。"""
    seen = {}
    order = []
    for entry in entries:
        key = (entry.get("mediaType"), entry.get("tmdbId"))
        if not entry.get("tmdbId"):
            key = ("raw", entry["cid"])
        if key in seen:
            index, current = seen[key]
            # 腾讯条目信息更全（自带类型标签），保留它作为主条目。
            if current["source"] != "qq" and entry["source"] == "qq":
                seen[key] = (index, merge_entries(entry, current))
            else:
                seen[key] = (index, merge_entries(current, entry))
        else:
            seen[key] = (len(order), entry)
            order.append(key)
    return [seen[key][1] for key in order]


def enrich(channels):
    jobs = []
    for channel, entries in channels.items():
        media_type = CHANNELS[channel][2]
        for entry in entries:
            jobs.append((entry, media_type))
    hit = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(resolve, entry, media_type): entry for entry, media_type in jobs}
        for index, future in enumerate(futures, 1):
            entry = futures[future]
            try:
                match = future.result()
            except Exception:
                match = None
            if match:
                hit[entry["cid"]] = match
            if index % 25 == 0:
                print(f"tmdb resolved {index}/{len(jobs)}")
    for channel, entries in channels.items():
        merged = []
        for entry in entries:
            match = hit.get(entry["cid"])
            if not match:
                continue
            tags = list(entry.get("tags") or [])
            for name in match.pop("genres", []):
                if name not in tags:
                    tags.append(name)
            merged.append({**entry, **match, "tags": tags[:10]})
        channels[channel] = dedupe(merged)
    return channels


# ---------------------------------------------------------------- 汇总

def collect():
    results = {}
    for channel, (qq_id, iq_id, _kind) in CHANNELS.items():
        entries = []
        for collector, cid in ((collect_qq, qq_id), (collect_iq, iq_id)):
            try:
                batch = collector(cid)
            except Exception as error:
                print(f"{collector.__name__} {channel} failed: {error}")
                continue
            entries.extend(batch)
        results[channel] = entries
    return results


def main():
    channels = collect()
    total = sum(len(entries) for entries in channels.values())
    if not total:
        raise SystemExit("no entries parsed, keeping the previous file")
    channels = enrich(channels)
    for channel, entries in channels.items():
        teasers = sum(1 for entry in entries if entry["teaser"])
        print(f"{channel}: {len(entries)} entries, {teasers} with teaser")
    if not any(channels.values()):
        raise SystemExit("no entries matched TMDB, keeping the previous file")
    payload = {
        "updatedAt": datetime.now(BEIJING).isoformat(timespec="seconds"),
        "source": "腾讯视频 + 爱奇艺片库列表",
        "channels": channels,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, OUTPUT)
    print(f"saved {sum(len(v) for v in channels.values())} entries to {OUTPUT}")


if __name__ == "__main__":
    main()
