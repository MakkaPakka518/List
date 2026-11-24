"""抓取腾讯视频、爱奇艺、优酷与哔哩哔哩国创榜看点，写入 data/qq-teaser.json。

每天抓一次，并把每部作品匹配到 TMDB，数据里直接带好：
- 看点：腾讯 second_title；爱奇艺 desc；优酷类型标签补位；哔哩哔哩 share_sub_title（只进动漫）
- 标签：tags（平台运营标签、哔哩哔哩国创/类型/独播、TMDB 类型补齐）、releaseDate、lastUpdateDate、rating、popularity、voteCount
- 身份：tmdbId、mediaType、posterPath、backdropPath

爱优腾哔在抓取时完成 TMDB 匹配；模块只本地筛选排序。芒果由用户设备现场抓取和匹配。
"""

import hashlib
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


# ---------------------------------------------------------------- 优酷

YK_APP = "24679788"
YK_API = "mtop.youku.columbus.home.query"
YK_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
YK_HEADERS = {"User-Agent": YK_UA, "Referer": "https://www.youku.com/ku/webtv", "Accept": "application/json"}
YK_CHANNEL_CATEGORY = {"tv": "电视剧", "movie": "电影", "variety": "综艺", "anime": "动漫"}
YK_SYS_INFO = json.dumps({
    "device": "pcweb", "os": "pcweb", "ver": "1.0.0.0", "userAgent": YK_UA,
    "guid": "1590141704165YXe", "appPackageKey": "com.youku.pcweb", "young": 0,
    "brand": "", "network": "", "ouid": "", "idfa": "", "scale": "", "operator": "",
    "resolution": "", "pid": "36370125020498", "appkey": YK_APP, "childGender": 0,
    "disableUserRec": "0",
}, separators=(",", ":"))
YK_TOKEN = {"tk": "", "ck": ""}


def yk_md5(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def yk_raw(data):
    token = YK_TOKEN["tk"]
    timestamp = str(int(time.time() * 1000))
    sign = yk_md5(token + "&" + timestamp + "&" + YK_APP + "&" + data)
    query = urlencode({
        "jsv": "2.6.1", "appKey": YK_APP, "t": timestamp, "sign": sign,
        "api": YK_API, "v": "1.0", "dataType": "json", "type": "originaljson", "data": data,
    })
    request = Request(
        f"https://acs.youku.com/h5/{YK_API}/1.0/?{query}",
        headers={"User-Agent": YK_UA, "Referer": "https://www.youku.com/ku/webtv", "Cookie": YK_TOKEN["ck"]},
    )
    with urlopen(request, timeout=30) as response:
        # headers.get 只回第一条 Set-Cookie；把所有条目拼起来再解析。
        set_cookie = "; ".join(response.headers.get_all("Set-Cookie") or [])
        body = json.load(response)
    match = re.search(r"_m_h5_tk=([^;,]+)", set_cookie)
    if match:
        YK_TOKEN["tk"] = match.group(1).split("_")[0]
        enc = re.search(r"_m_h5_tk_enc=([^;,]+)", set_cookie)
        YK_TOKEN["ck"] = f"_m_h5_tk={match.group(1)}; _m_h5_tk_enc={enc.group(1) if enc else ''}"
    return body


def yk_call(data):
    if not YK_TOKEN["tk"]:
        try:
            yk_raw(data)
        except Exception:
            pass
    body = yk_raw(data)
    ret = (body or {}).get("ret") or []
    if ret and "TOKEN" in str(ret[0]):
        body = yk_raw(data)
    return body


def yk_collect_nodes(node, out):
    if not isinstance(node, (dict, list)):
        return
    if isinstance(node, list):
        for item in node:
            yk_collect_nodes(item, out)
        return
    data = node.get("data")
    if isinstance(data, dict) and data.get("title") and data.get("action") and (data.get("img") or data.get("hImg")):
        tags = [item.get("text", {}).get("title") for item in (data.get("tags") or []) if isinstance(item, dict)]
        out.append({"title": str(data["title"]), "tags": [tag for tag in tags if tag]})
    for key, value in node.items():
        if key in ("action", "trackShow", "report"):
            continue
        yk_collect_nodes(value, out)


def yk_teaser(tags):
    """当前片库采集使用类型标签（「悬疑 · 罪案」）作为看点补位。"""
    for tag in reversed(tags or []):
        if "限免" in tag or tag in ("独播", "VIP") or "更新" in tag or "集" in tag and "期" not in tag and "话" not in tag:
            continue
        if re.match(r"^[0-9]+[-~][0-9]+期?$", tag):
            continue
        return tag
    return ""


def parse_yk(item, channel):
    title = clean_title(item.get("title"))
    if not title:
        return None
    tags = []
    for tag in (item.get("tags") or []):
        tag = str(tag or "").strip()
        if not tag:
            continue
        # 平台标记带来源，聚合成榜单后才知道是哪个平台独播。
        if tag == "独播":
            tag = "优酷独播"
        tags.append(tag)
    genre = next((tag for tag in reversed(tags) if " · " in tag), "")
    episode = next((tag for tag in tags if tag.startswith("更新至") or tag.endswith("集全") or tag.endswith("期全") or tag.endswith("话")), "")
    return {
        "source": "yk",
        "cid": "yk" + title,
        "title": title,
        "teaser": genre or yk_teaser(tags),
        "year": "",
        "genre": genre.split(" · ")[0] if genre else "",
        "area": "中国内地",
        "episodeText": episode,
        "tags": yk_card_tags(tags),
    }


def yk_card_tags(tags):
    """卡片标签：类型词 + 平台独播标记；限免/集数/VIP 不进标签。"""
    out = []
    if "优酷独播" in tags:
        out.append("优酷独播")
    for tag in tags:
        if " · " in tag:
            for part in tag.split(" · "):
                part = part.strip()
                if part and part not in out:
                    out.append(part)
    return out


def collect_yk(channel, category):
    filter_param = "type:" + category + "|mainArea:中国内地"
    inner = {
        "utdid": "FE1oI9Z/92QCAWeOjJcxfUHN", "gray": "0", "pageNo": 1, "debug": 0,
        "bizKey": "kuflix_pc_home", "appPackageKey": "com.youku.pcweb",
        "showNodeList": 1, "reqSubNode": 1, "nodeKey": "ALL", "ip": "127.0.0.1",
        "bizContext": json.dumps({"filterParam": filter_param, "category": category, "optionRefresh": 1}, separators=(",", ":")),
    }
    payload = json.dumps({"ms_codes": "2019061000", "params": json.dumps(inner, ensure_ascii=False), "system_info": YK_SYS_INFO}, ensure_ascii=False)
    body = yk_call(payload)
    items = []
    yk_collect_nodes(body, items)
    entries = []
    for item in items:
        entry = parse_yk(item, channel)
        if entry:
            entries.append(entry)
    return entries


# ---------------------------------------------------------------- 哔哩哔哩（仅国创，只合入 anime）

BILI_API = "https://api.bilibili.com"
BILI_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"}

# 哔哩哔哩国创榜会混进短剧、漫剧、动态漫和少儿向作品；只保留 TMDB 明确标成动画的条目。
BILI_ANIMATION_GENRES = {16}
BILI_KIDS_GENRES = {10762}
BILI_REJECT_GENRES = {10763, 10764, 10766, 10767}
BILI_REJECT_GENRE_NAMES = {"新闻", "真人秀", "脱口秀", "肥皂剧", "News", "Reality", "Talk", "Soap"}
BILI_LOW_AGE_STYLES = ("少儿", "儿童", "亲子", "早教", "低幼", "幼儿", "益智", "启蒙", "儿歌", "睡前")
BILI_LOW_AGE_TITLE = re.compile(
    r"(?:宝宝巴士|贝乐虎|儿歌|睡前故事|学龄前|亲子|早教|低幼|幼儿|启蒙|识字|"
    r"红小豆|开心锤锤|叶罗丽|熊出没|喜羊羊|京剧猫|熊猫和小鼹鼠|"
    r"不白吃|哆啦A梦|蜡笔小新|海绵宝宝|小猪佩奇|汪汪队|超级飞侠|巴啦啦小魔仙)"
)
BILI_LOW_AGE_DESC = re.compile(r"(?:宝宝|幼儿|学龄前|亲子|早教|儿歌|睡前故事|低幼)")


def bili_get(path, params):
    request = Request(BILI_API + path + "?" + urlencode(params), headers=BILI_HEADERS)
    with urlopen(request, timeout=30) as response:
        body = json.load(response)
    if body.get("code") != 0:
        raise RuntimeError(f"Bilibili {path}: {body.get('code')} {body.get('message')}")
    return body.get("result") or body.get("data") or {}


def bili_low_age_entry(title, styles=(), desc=""):
    """标题、B 站风格标签和简介只要命中明显低幼特征，就不进国创榜。"""
    text = str(title or "")
    if BILI_LOW_AGE_TITLE.search(text):
        return True
    if any(marker in str(style or "") for style in styles for marker in BILI_LOW_AGE_STYLES):
        return True
    return bool(BILI_LOW_AGE_DESC.search(str(desc or "")))


def bili_tmdb_allows(hit, detail_genres=()):
    """国创只认 TMDB 动画类型：genre_ids 或详情类型至少一个明确为动画，
    同时排除儿童、真人秀、新闻、脱口秀等明显不是剧情动画的类型。"""
    ids = set(hit.get("genre_ids") or [])
    names = {str(name or "").strip() for name in detail_genres or []}
    if not (ids & BILI_ANIMATION_GENRES or names & {"动画", "Animation"}):
        return False
    if ids & BILI_KIDS_GENRES or names & {"儿童", "Kids"}:
        return False
    if ids & BILI_REJECT_GENRES or names & BILI_REJECT_GENRE_NAMES:
        return False
    return True


def parse_bili(item, season=None):
    season = season or {}
    sid = str(item.get("season_id") or "")
    title = clean_title(item.get("title") or season.get("title"))
    if not sid.isdigit() or int(sid) <= 0 or not title:
        return None
    if str(season.get("type") or 4) != "4":
        return None
    styles = [str(style).strip() for style in season.get("styles") or [] if str(style).strip()]
    if bili_low_age_entry(title, styles, season.get("evaluate") or season.get("desc") or ""):
        return None
    tags = ["国漫", "动画", "哔哩哔哩国创"] + styles
    if item.get("copyright") == "dujia" or item.get("badge") in ("独家", "独播"):
        tags.append("哔哩哔哩独播")
    if item.get("badge") == "出品":
        tags.append("哔哩哔哩出品")
    return {
        "source": "bili",
        "cid": "bili" + sid,
        "title": title,
        # subtitle 是「已观看 N 次」，不把播放量或长 evaluate 当作看点。
        "teaser": str(season.get("share_sub_title") or item.get("share_sub_title") or "").strip(),
        "year": clean_year((season.get("publish") or {}).get("pub_time")),
        "genre": "动画",
        "area": "中国内地",
        "episodeText": str((item.get("new_ep") or {}).get("index_show") or ""),
        "tags": list(dict.fromkeys(tags)),
    }


def collect_bili():
    rows = bili_get("/pgc/web/rank/list", {"day": 3, "season_type": 4}).get("list") or []
    unique = {entry["cid"]: item for item in rows if (entry := parse_bili(item))}

    def with_detail(item):
        try:
            season = bili_get("/pgc/view/web/season", {"season_id": item["season_id"]})
        except Exception as error:
            print(f"bilibili season {item['season_id']} failed: {error}")
            season = {}
        return parse_bili(item, season)

    with ThreadPoolExecutor(max_workers=8) as pool:
        return [entry for entry in pool.map(with_detail, unique.values()) if entry]


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
    """search/movie 对部分国产片返回空 origin_country；空列表放行交给
    标题匹配兜底，代价是少数缺字段的外语片可能漏进榜单。"""
    regions = set(result.get("origin_country") or [])
    if not regions:
        return True
    return bool(regions & CN_REGIONS)


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
                genres, last_update = tmdb_detail(kind, hit["id"])
                if entry.get("source") == "bili" and not bili_tmdb_allows(hit, genres):
                    continue
                date = str(hit.get("first_air_date") or hit.get("release_date") or "")
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
    """保留主条目看点，补齐缺字段并保留全部平台标签。"""
    merged = dict(primary)
    for key, value in extra.items():
        if merged.get(key) in ("", None, []):
            merged[key] = value
    merged["tags"] = list(dict.fromkeys((primary.get("tags") or []) + (extra.get("tags") or [])))
    merged["alsoOn"] = sorted(set(filter(None, (primary.get("alsoOn") or []) +
        (extra.get("alsoOn") or []) + [primary.get("source"), extra.get("source")])))
    merged["lastUpdateDate"] = max(primary.get("lastUpdateDate") or "", extra.get("lastUpdateDate") or "")
    return merged


def teaser_priority(entry):
    """有文案优先；腾讯、爱奇艺、哔哩哔哩短看点优于优酷类型词。"""
    return (bool(str(entry.get("teaser") or "").strip()), {"qq": 4, "iq": 3, "bili": 2, "yk": 1}.get(entry.get("source"), 0))


def dedupe(entries):
    """按 (mediaType, tmdbId) 去重，优先真实看点；作品位置保持不变。"""
    seen = {}
    for entry in entries:
        key = (entry.get("mediaType"), entry.get("tmdbId"))
        if not entry.get("tmdbId"):
            key = ("raw", entry["cid"])
        if key in seen:
            current = seen[key]
            if teaser_priority(entry) > teaser_priority(current):
                seen[key] = merge_entries(entry, current)
            else:
                seen[key] = merge_entries(current, entry)
        else:
            seen[key] = entry
    return list(seen.values())


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
            match = dict(hit.get(entry["cid"]) or {})
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
    """搜索和卡片标题都去掉语言版本、季数等后缀。"""
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
        try:
            entries.extend(collect_yk(channel, YK_CHANNEL_CATEGORY[channel]))
        except Exception as error:
            print(f"youku {channel} failed: {error}")
        if channel == "anime":
            try:
                entries.extend(collect_bili())
            except Exception as error:
                print(f"bilibili anime failed: {error}")
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
        "source": "腾讯视频 + 爱奇艺 + 优酷片库列表 + 哔哩哔哩国创榜（仅动漫）",
        "channels": channels,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, OUTPUT)
    print(f"saved {sum(len(v) for v in channels.values())} entries to {OUTPUT}")


if __name__ == "__main__":
    main()
