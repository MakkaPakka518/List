import asyncio
import json
import os
import datetime
import re  # 🔴 必须引入正则模块来清洗标题

# --- 配置区 ---
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "douban-hot.json")

# 豆瓣内部隐藏 API
DB_BASE_URL = "https://m.douban.com/rexxar/api/v2/subject/recent_hot/tv"

# TMDB 类型映射表
GENRE_MAP = {
    28: "动作", 12: "冒险", 16: "动画", 35: "喜剧", 80: "犯罪", 99: "纪录片", 18: "剧情", 
    10751: "家庭", 14: "奇幻", 36: "历史", 27: "恐怖", 10402: "音乐", 9648: "悬疑", 
    10749: "爱情", 878: "科幻", 10770: "电视电影", 53: "惊悚", 10752: "战争", 37: "西部", 
    10759: "动作冒险", 10762: "儿童", 10763: "新闻", 10764: "真人秀", 10765: "科幻奇幻", 
    10766: "肥皂剧", 10767: "脱口秀", 10768: "战争政治"
}

# 热评抓取：每条剧目最多取 1 条简短热评，存入独立 comments 数据组
COMMENT_COUNT = 10          # 每次向豆瓣请求的评论条数上限
COMMENT_MIN_LEN = 8         # 太短没有信息量
COMMENT_MAX_LEN = 46        # 太长卡片显示不下
COMMENT_PER_REGION = 30     # 每个榜单只给前 N 条抓热评，控制请求量

# 你定义的抓取区域和数量
REGIONS = [
    { "title": "全部剧集", "value": "tv", "limit": 300},
    { "title": "国产剧", "value": "tv_domestic", "limit": 150 },
    { "title": "欧美剧", "value": "tv_american", "limit": 150},
    { "title": "日剧", "value": "tv_japanese", "limit": 150 },
    { "title": "韩剧", "value": "tv_korean", "limit": 150},
    { "title": "动画", "value": "tv_animation", "limit": 150 },
    { "title": "纪录片", "value": "tv_documentary", "limit": 150 },
    { "title": "国内综艺", "value": "show_domestic", "limit": 150},
    { "title": "国外综艺", "value": "show_foreign", "limit": 150 }
]

def clean_douban_title(raw_title):
    """🔴 核心清洗逻辑：去除标题中可能的季数后缀，提高 TMDB 匹配率"""
    title = raw_title.strip()
    # 正则剔除 "第一季"、"第1季"、"Season 1"、"season1" 等字眼 (忽略大小写)
    title = re.sub(r'第[一二三四五六七八九十百\d]+季', '', title)
    title = re.sub(r'(?i)Season\s*\d+', '', title)
    # 压缩多余空格
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def tmdb_episode_text(detail, today):
    """只用已到播出日的常规集；总集数不是最新已播集。"""
    last = detail.get("last_episode_to_air") or {}
    season, episode = last.get("season_number"), last.get("episode_number")
    try:
        aired = datetime.date.fromisoformat(last.get("air_date") or "") <= today
    except ValueError:
        aired = False
    if not aired or type(season) is not int or type(episode) is not int or min(season, episode) < 1:
        return ""
    if season > 1 or (detail.get("number_of_seasons") or 0) > 1:
        return f"S{season:02d}E{episode:02d}"
    total = detail.get("number_of_episodes")
    unit = "期" if any(g.get("id") in (10764, 10767) for g in detail.get("genres", [])) else "集"
    if detail.get("status") == "Ended" and not detail.get("next_episode_to_air") and total == episode:
        return f"全{episode}{unit}"
    return f"更新至{episode}{unit}"


def with_douban_progress(info, text):
    # TMDB 缓存按剧共享；豆瓣的集数属于当前榜单条目，不能写回缓存。
    fallback = info.get("episodeText", "")
    if fallback.startswith("S"):
        return info
    text = re.sub(r"\s+", "", text or "")
    text = re.sub(r"^(\d+)(集|期)全$", r"全\1\2", text)
    match = re.fullmatch(r"(更新至|更至|全|共)第?(0*[1-9]\d*)(集|期)", text)
    if not match or (match[1] == "共" and fallback):
        return info
    prefix = "更新至" if match[1] == "更至" else match[1]
    return {**info, "episodeText": f"{prefix}{match[2]}{match[3]}"}

async def fetch_douban_list(session, region):
    """请求豆瓣隐藏API，获取基础列表"""
    params = {"start": 0, "limit": region["limit"], "type": region["value"]}
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Referer": "https://m.douban.com/movie/"
    }
    try:
        async with session.get(DB_BASE_URL, params=params, headers=headers) as resp:
            if resp.status != 200: 
                print(f"豆瓣接口请求失败: {region['title']} - HTTP {resp.status}")
                return []
            data = await resp.json()
            return data.get("items", [])
    except Exception as e: 
        print(f"获取豆瓣 {region['title']} 异常: {e}")
        return []

async def fetch_tmdb_detail(session, item, cache):
    """使用 TMDB API 洗出标准的高清海报和详情"""
    raw_title = item.get("title", "").strip()
    # 🔴 在这里调用清洗函数，把 "嗜血法医 第一季 Dexter Season 1" 洗成 "嗜血法医 Dexter"
    db_title = clean_douban_title(raw_title)
    subtitle = item.get("card_subtitle", "")
    
    # 尝试从副标题提取年份，例如 "2024 / 中国大陆 / 剧情"
    db_year = subtitle.split('/')[0].strip() if subtitle else None
    if db_year and not (db_year.isdigit() and len(db_year) == 4): 
        db_year = None

    cache_key = f"{db_title}_{db_year}"
    if cache_key in cache: 
        return with_douban_progress(cache[cache_key], item.get("episodes_info"))

    url = "https://api.themoviedb.org/3/search/tv"
    headers = {"accept": "application/json"}
    params = {"query": db_title, "language": "zh-CN"}
    
    if TMDB_API_KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {TMDB_API_KEY}"
    else:
        params["api_key"] = TMDB_API_KEY

    if db_year: 
        params["first_air_date_year"] = db_year

    try:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200: return None
            data = await resp.json()
            results = data.get("results", [])
            if not results: 
                # 如果带年份搜不到，尝试不带年份再搜一次
                if db_year:
                    del params["first_air_date_year"]
                    async with session.get(url, params=params, headers=headers) as resp2:
                        if resp2.status == 200:
                            data2 = await resp2.json()
                            results = data2.get("results", [])
            
            if not results: return None

            for res in results:
                tmdb_t = (res.get("name") or "").lower()
                tmdb_o = (res.get("original_name") or "").lower()
                target = db_title.lower()
                
                is_title_ok = (target in tmdb_t or target in tmdb_o or tmdb_t in target)
                first_air = res.get("first_air_date")
                
                is_year_ok = True
                if db_year and first_air:
                    is_year_ok = first_air.startswith(db_year)
                
                if is_title_ok and is_year_ok:
                    tmdb_id = res.get("id")
                    poster_path = res.get("poster_path")
                    backdrop_path = res.get("backdrop_path")
                    
                    if not tmdb_id or not poster_path or not backdrop_path:
                        continue

                    # 🔴 拿着 id 去请求详情，获取最新更新日期 (last_air_date)
                    detail_url = f"https://api.themoviedb.org/3/tv/{tmdb_id}"
                    detail_params = {"language": "zh-CN"}
                    if not TMDB_API_KEY.startswith("eyJ"):
                        detail_params["api_key"] = TMDB_API_KEY
                        
                    last_update_date = first_air # 默认用首播日期兜底
                    episode_text = ""
                    try:
                        async with session.get(detail_url, params=detail_params, headers=headers) as d_resp:
                            if d_resp.status == 200:
                                d_data = await d_resp.json()
                                # 获取最新播出日期，如果没有则退回到首播日期
                                last_update_date = d_data.get("last_air_date") or first_air
                                today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
                                episode_text = tmdb_episode_text(d_data, today)
                    except Exception as e:
                        pass # 详情获取失败不影响主体逻辑

                    genre_ids = res.get("genre_ids", [])
                    genre_names = ",".join([GENRE_MAP.get(gid) for gid in genre_ids if GENRE_MAP.get(gid)])

                    info = {
                        "id": str(tmdb_id),
                        "type": "tmdb",
                        "title": res.get("name"),
                        "description": res.get("overview"),
                        "rating": res.get("vote_average"),
                        "vote_count": res.get("vote_count"),
                        "popularity": res.get("popularity"),
                        "releaseDate": first_air,
                        "lastUpdateDate": last_update_date, # 🔴 这里保存给前端排序用
                        "posterPath": poster_path,
                        "backdropPath": backdrop_path,
                        "mediaType": "tv",
                        "genreTitle": genre_names
                    }
                    if episode_text:
                        info["episodeText"] = episode_text
                    cache[cache_key] = info
                    return with_douban_progress(info, item.get("episodes_info"))
    except: pass
    return None

def pick_comment(interests):
    """从热评列表里挑一条简短、可读、无链接的评价"""
    for item in interests or []:
        text = re.sub(r"\s+", " ", (item.get("comment") or "")).strip()
        if not text:
            continue
        if len(text) < COMMENT_MIN_LEN or len(text) > COMMENT_MAX_LEN:
            continue
        if "http" in text or "www." in text:
            continue
        user = (item.get("user") or {}).get("name") or ""
        rating = (item.get("rating") or {}).get("value") or 0
        return {"text": text, "author": user, "rating": rating}
    return None


async def fetch_hot_comment(session, media_type, douban_id):
    """按豆瓣条目 ID 取一条热门短评；失败不影响榜单主体"""
    if not douban_id:
        return None
    url = f"https://m.douban.com/rexxar/api/v2/{media_type}/{douban_id}/interests"
    params = {"count": COMMENT_COUNT, "order_by": "hot", "start": 0}
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Referer": "https://m.douban.com/movie/"
    }
    try:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return pick_comment(data.get("interests"))
    except Exception:
        return None


async def batch_process(session, items, size, cache):
    """控制并发量，防止被 TMDB 封 IP"""
    results = []
    for i in range(0, len(items), size):
        chunk = items[i:i + size]
        tasks = [fetch_tmdb_detail(session, item, cache) for item in chunk]
        chunk_results = await asyncio.gather(*tasks)
        results.extend([r for r in chunk_results if r is not None])
        await asyncio.sleep(0.3) 
    return results

async def main():
    import aiohttp
    if not TMDB_API_KEY:
        print("❌ 错误: 未检测到 TMDB_API_KEY 环境变量！")
        return

    os.makedirs(DATA_DIR, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        final_result = {
            "last_updated": ""
        }
        cache = {} 
        comments = {}
        
        for region in REGIONS:
            print(f"🚀 正在抓取: {region['title']} ({region['limit']}部)")
            items = await fetch_douban_list(session, region)
            print(f"   => 从豆瓣获取到 {len(items)} 条记录，开始 TMDB 匹配...")
            
            matched = await batch_process(session, items, 10, cache)
            print(f"   => 成功匹配到 {len(matched)} 条 TMDB 数据！\n")
            
            final_result[region["value"]] = matched

            # 只给榜单前几条抓热评，避免请求过多被限流
            added = 0
            for raw in items[:COMMENT_PER_REGION]:
                info = await fetch_tmdb_detail(session, raw, cache)
                if not info:
                    continue
                key = f"{info['mediaType']}.{info['id']}"
                if comments.get(key):
                    continue
                comment = await fetch_hot_comment(session, "tv", str(raw.get("id") or ""))
                comments[key] = comment
                if comment:
                    added += 1
                await asyncio.sleep(0.15)
            print(f"   => 本榜新增热评 {added} 条，累计 {len([v for v in comments.values() if v])} 条")

    # 记录最后更新时间 (北京时间)
    if not any(final_result[r["value"]] for r in REGIONS):
        raise RuntimeError("本次没有匹配到任何作品，保留旧榜单")
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    final_result["last_updated"] = datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S")
    # 独立数据组：键为 "mediaType.tmdbId"，只放简短热评，不掺进榜单条目字段
    final_result["comments"] = {key: value for key, value in comments.items() if value}
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    print(f"✅ 所有豆瓣热榜数据已成功保存至 {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
