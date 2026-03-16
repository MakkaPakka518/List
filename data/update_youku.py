import asyncio
import aiohttp
import json
import os
import re
import datetime

# --- 配置区 ---
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "youku-hot.json")

# TMDB 类型映射表
GENRE_MAP = {
    28: "动作", 12: "冒险", 16: "动画", 35: "喜剧", 80: "犯罪", 99: "纪录片", 18: "剧情", 
    10751: "家庭", 14: "奇幻", 36: "历史", 27: "恐怖", 10402: "音乐", 9648: "悬疑", 
    10749: "爱情", 878: "科幻", 10770: "电视电影", 53: "惊悚", 10752: "战争", 37: "西部", 
    10759: "动作冒险", 10762: "儿童", 10763: "新闻", 10764: "真人秀", 10765: "科幻奇幻", 
    10766: "肥皂剧", 10767: "脱口秀", 10768: "战争政治"
}

# 抓取区域配置（直接使用你提供的带过滤条件的优酷 URL）
REGIONS = [
    { 
        "title": "优酷热门剧集", 
        "value": "tv", 
        "limit": 60, # 网页 SSR 首屏一般会直接包含 30-60 部剧集的数据，足够提取热榜了
        "url": "https://www.youku.com/ku/webtv/list?filter=type_%E7%94%B5%E8%A7%86%E5%89%A7_sort_1"
    }
]

def clean_youku_title(raw_title):
    """清洗优酷的标题，去除季数、后缀等杂质"""
    title = raw_title.strip()
    title = re.sub(r'第[一二三四五六七八九十百\d]+季', '', title)
    title = re.sub(r'(?i)Season\s*\d+', '', title)
    # 优酷喜欢加的后缀，如加更版、特辑、大结局等
    title = re.sub(r'\(.*?\)|（.*?）', '', title)
    title = re.sub(r'加更版|纯享版|特辑|纪录片', '', title)
    return re.sub(r'\s+', ' ', title).strip()

async def fetch_youku_list(session, region):
    """请求优酷页面，并从 HTML 的 __INITIAL_DATA__ 中挖掘剧集"""
    url = region["url"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.youku.com/"
    }
    
    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                print(f"优酷请求失败: HTTP {resp.status}")
                return []
            
            html = await resp.text()
            
            # 💡 核心秘诀：直接截取隐藏在前端 JS 里的初始 JSON 数据
            match = re.search(r'__INITIAL_DATA__\s*=\s*({.*?});', html, re.DOTALL)
            if not match:
                print("❌ 未在优酷页面找到 __INITIAL_DATA__，可能页面结构发生改变。")
                return []
                
            data = json.loads(match.group(1))
            items = []
            seen_titles = set()
            
            # 由于优酷的数据结构层级极深且会变动，我们用“深度递归算法”扫荡所有带海报的视频卡片
            def extract_nodes(node):
                if isinstance(node, dict):
                    title = node.get("title", "").strip()
                    # 识别特征：既有 title 又有 pic/thumbUrl 等海报特征的字典，基本就是剧集卡片
                    if title and ("pic" in node or "thumbUrl" in node or "vthumbUrl" in node):
                        # 过滤掉短小无意义的 UI 字符，并去重
                        if len(title) > 1 and title not in seen_titles:
                            seen_titles.add(title)
                            items.append({
                                "title": title,
                                "card_subtitle": node.get("subTitle", "")
                            })
                    for k, v in node.items():
                        extract_nodes(v)
                elif isinstance(node, list):
                    for item in node:
                        extract_nodes(item)

            extract_nodes(data)
            return items[:region["limit"]]
    except Exception as e:
        print(f"获取优酷 {region['title']} 异常: {e}")
        return []

async def fetch_tmdb_detail(session, item, cache):
    """将清洗后的优酷名称发往 TMDB 匹配"""
    raw_title = item.get("title", "").strip()
    db_title = clean_youku_title(raw_title)
    subtitle = item.get("card_subtitle", "")
    
    # 从标题或副标题尝试拿年份
    db_year = None
    year_match = re.search(r'\b(20\d{2})\b', subtitle)
    if not year_match:
        year_match = re.search(r'\b(20\d{2})\b', raw_title)
        if year_match:
            db_title = db_title.replace(year_match.group(1), "").strip()
            
    if year_match:
        db_year = year_match.group(1)

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

    if db_year: params["first_air_date_year"] = db_year

    try:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200: return None
            data = await resp.json()
            results = data.get("results", [])
            
            # 若带年份搜不到，抛弃年份再次尝试
            if not results and db_year: 
                del params["first_air_date_year"]
                async with session.get(url, params=params, headers=headers) as resp2:
                    if resp2.status == 200:
                        results = (await resp2.json()).get("results", [])
            
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

                    genre_ids = res.get("genre_ids", [])
                    genre_names = ",".join([GENRE_MAP.get(gid) for gid in genre_ids if GENRE_MAP.get(gid)])

                    info = {
                        "id": str(tmdb_id),
                        "type": "tmdb",
                        "title": res.get("name"),
                        "description": res.get("overview"),
                        "rating": res.get("vote_average"),
                        "voteCount": res.get("vote_count"),
                        "popularity": res.get("popularity"),
                        "releaseDate": first_air,
                        "posterPath": poster_path,
                        "backdropPath": backdrop_path,
                        "mediaType": "tv",
                        "genreTitle": genre_names
                    }
                    cache[cache_key] = info
                    return info
    except: pass
    return None

async def batch_process(session, items, size, cache):
    """限速并发，保护 TMDB 账号"""
    results = []
    for i in range(0, len(items), size):
        chunk = items[i:i + size]
        tasks = [fetch_tmdb_detail(session, item, cache) for item in chunk]
        chunk_results = await asyncio.gather(*tasks)
        results.extend([r for r in chunk_results if r is not None])
        await asyncio.sleep(0.2)
    return results

async def main():
    if not TMDB_API_KEY:
        print("❌ 错误: 未检测到 TMDB_API_KEY")
        return

    os.makedirs(DATA_DIR, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        final_result = {"last_updated": ""}
        cache = {} 
        
        for region in REGIONS:
            print(f"🚀 正在抓取: {region['title']}")
            items = await fetch_youku_list(session, region)
            print(f"   => 成功从网页底库挖掘到 {len(items)} 条热门剧集，开始匹配 TMDB...")
            
            matched = await batch_process(session, items, 10, cache)
            print(f"   => 匹配完毕，获得 {len(matched)} 条高清结构化数据！\n")
            
            final_result[region["value"]] = matched

    # 北京时间记录
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    final_result["last_updated"] = datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    print(f"✅ 优酷数据抓取圆满结束！已保存至 {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
