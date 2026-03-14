import asyncio
import aiohttp
import json
import os

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
    db_title = item.get("title", "").strip()
    subtitle = item.get("card_subtitle", "")
    
    # 尝试从副标题提取年份，例如 "2024 / 中国大陆 / 剧情"
    db_year = subtitle.split('/')[0].strip() if subtitle else None
    if db_year and not (db_year.isdigit() and len(db_year) == 4): 
        db_year = None

    cache_key = f"{db_title}_{db_year}"
    if cache_key in cache: 
        return cache[cache_key]

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
                    genre_ids = res.get("genre_ids", [])
                    genre_names = ",".join([GENRE_MAP.get(gid) for gid in genre_ids if GENRE_MAP.get(gid)])

                    info = {
                        "id": str(res["id"]),
                        "type": "tmdb",
                        "title": res.get("name"),
                        "description": res.get("overview"),
                        "rating": res.get("vote_average"),
                        "vote_count": res.get("vote_count"),
                        "popularity": res.get("popularity"),
                        "releaseDate": first_air,
                        "posterPath": res.get("poster_path"),
                        "backdropPath": res.get("backdrop_path"),
                        "mediaType": "tv",
                        "genreTitle": genre_names
                    }
                    cache[cache_key] = info
                    return info
    except: pass
    return None

async def batch_process(session, items, size, cache):
    """控制并发量，防止被 TMDB 封 IP"""
    results = []
    for i in range(0, len(items), size):
        chunk = items[i:i + size]
        tasks = [fetch_tmdb_detail(session, item, cache) for item in chunk]
        chunk_results = await asyncio.gather(*tasks)
        results.extend([r for r in chunk_results if r is not None])
        await asyncio.sleep(0.2) # 稍微喘口气
    return results

async def main():
    if not TMDB_API_KEY:
        print("❌ 错误: 未检测到 TMDB_API_KEY 环境变量！")
        return

    os.makedirs(DATA_DIR, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        final_result = {
            "last_updated": ""
        }
        cache = {} # 全局缓存，避免重复请求相同的剧集
        
        for region in REGIONS:
            print(f"🚀 正在抓取: {region['title']} ({region['limit']}部)")
            items = await fetch_douban_list(session, region)
            print(f"   => 从豆瓣获取到 {len(items)} 条记录，开始 TMDB 匹配...")
            
            matched = await batch_process(session, items, 10, cache)
            print(f"   => 成功匹配到 {len(matched)} 条 TMDB 数据！\n")
            
            # 使用 REGIONS 里的 value 值作为 JSON 的键值
            final_result[region["value"]] = matched

    # 记录最后更新时间 (北京时间)
    import datetime, timezone
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    final_result["last_updated"] = datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    print(f"✅ 所有豆瓣热榜数据已成功保存至 {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
