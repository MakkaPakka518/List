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


# 标题里这些后缀都不是作品本身的一部分，搜 TMDB 之前全部去掉。
TITLE_NOISE = (
    r"普通话版?|国语版?|粤语版?|日语版?|中配版?|原声版?|未删减版?|修复版?|重映版?|英语版?|台配版?|港配版?",
    r"第\s*[0-9一二三四五六七八九十百]+\s*[季期部篇]",
    r"(?:年番|完结季|完结篇|特别篇|加更篇|衍生篇|番外篇|总篇|精华篇)",
    r"(?:爽看版|精编版|加更版|会员版|悠享版|抢先版|完整版|导演剪辑版|速看版|高能版|纯享版|竖屏版|横屏版|特辑|大结局|升级版|重逢版)",
)


def clean_search_title(title):
    text = str(title or "").strip()
    for pattern in TITLE_NOISE:
        text = re.sub(pattern, "", text)
    text = re.sub(r"[（(][^)）]*[)）]", "", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"【[^】]*】", "", text)
    text = re.sub(r"\s+", " ", text)
    # 「蜡笔小新 第7季 普通话」这类标题去掉季数后，普通话版会残留在末尾；再清一次。
    for pattern in TITLE_NOISE:
        text = re.sub(pattern, "", text)
    text = re.sub(r"[\s·・]+$", "", text).strip()
    return text


def title_variants(title):
    raw = str(title or "").strip()
    if not raw:
        return []
    out = []

    def add(value):
        text = str(value or "").strip()
        if len(text) >= 2 and text not in out:
            out.append(text)

    add(clean_search_title(raw))
    base = clean_search_title(raw)
    add(base.split("·")[0].strip())
    return out


# 榜单只统计国产剧；TMDB 候选必须产自这些地区，避免「黑沙」匹配到冰岛剧。
CN_REGIONS = {"CN", "HK", "MO", "TW"}


def is_chinese_show(result):
    return bool(set(result.get("origin_country") or []) & CN_REGIONS)


def match_score(result, names, year):
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
    return score


def ranked_matches(results, names, year):
    """所有过阈值的候选，分数高的在前；首位没图时还能试下一位。
    只接受中国大陆/香港/澳门/台湾出品的候选。"""
    scored = []
    for result in results or []:
        if not result or not result.get("id"):
            continue
        if not is_chinese_show(result):
            continue
        score = match_score(result, names, year)
        if score >= 0.72:
            scored.append((score, result))
    scored.sort(key=lambda item: -item[0])
    return [result for _score, result in scored]


def resolve(entry, media_type):
    alias = ALIAS.get(clean_search_title(entry["title"]))
    names = [alias] if alias else title_variants(entry["title"])
    if not names:
        names = title_variants(entry["title"])
    for kind in (media_type, "movie" if media_type == "tv" else "tv"):
        for name in names[:2]:
            try:
                data = tmdb_get(f"search/{kind}", {"query": name, "language": "zh-CN", "include_adult": "false"})
            except Exception:
                continue
            # 首位候选没图时继续试下一位，全部没图才算匹配失败。
            for hit in ranked_matches(data.get("results"), names, entry["year"]):
                poster = hit.get("poster_path") or ""
                backdrop = hit.get("backdrop_path") or ""
                if not poster and not backdrop:
                    continue
                date = str(hit.get("first_air_date") or hit.get("release_date") or "")
                genres, last_update = tmdb_detail(kind, hit["id"])
                return {
                    "tmdbId": hit["id"],
                    "mediaType": kind,
                    "posterPath": poster,
                    "backdropPath": backdrop,
                    "releaseDate": date,
                    "lastUpdateDate": last_update or date,
                    "rating": hit.get("vote_average") or 0,
                    "voteCount": hit.get("vote_count") or 0,
                    "popularity": hit.get("popularity") or 0,
                    "genres": genres,
                }
    return None


GENRE_CACHE = {}


DETAIL_CACHE = {}


def tmdb_detail(kind, tmdb_id):
    """类型名 + last_air_date（与豆瓣热榜的最近更新同源），一次请求两个都要。"""
    key = f"{kind}:{tmdb_id}"
    if key in DETAIL_CACHE:
        return DETAIL_CACHE[key]
    genres, last_update = [], ""
    try:
        detail = tmdb_get(f"{kind}/{tmdb_id}", {"language": "zh-CN"})
        genres = [str(genre.get("name") or "").strip() for genre in detail.get("genres") or []]
        last_update = str(detail.get("last_air_date") or "").strip()
    except Exception:
        pass
    DETAIL_CACHE[key] = (genres, last_update)
    return DETAIL_CACHE[key]


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
            merged.append({**entry, "displayTitle": display_title(entry), **match, "tags": tags[:10]})
        channels[channel] = dedupe(merged)
    # 无海报的条目在卡片上没有意义，统一丢弃。
    for channel, entries in channels.items():
        channels[channel] = [entry for entry in entries if entry.get("posterPath") or entry.get("backdropPath")]
    return channels


# ---------------------------------------------------------------- 汇总

# 同一部作品在腾讯/爱奇艺的叫法不同，TMDB 又搜不到时，按这里映射到正确标题。
# 值为 TMDB 搜索词；命中后 displayTitle 保持平台原名，只有搜索用映射。
ALIAS = {
    # 腾讯「奔跑吧」各季与爱奇艺「奔跑吧」/「奔跑吧兄弟」系列在 TMDB 是同一部综艺。
    "奔跑吧大湾区篇": "奔跑吧",
    "奔跑吧第10季": "奔跑吧",
    "奔跑吧兄弟第10季": "奔跑吧",
    "奔跑吧": "奔跑吧",
    "奔跑吧兄弟": "奔跑吧兄弟",
}


def display_title(entry):
    """卡片显示用的标题：只去掉普通话版等后缀，保留季数信息由各平台展示。"""
    return clean_search_title(entry["title"])


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
