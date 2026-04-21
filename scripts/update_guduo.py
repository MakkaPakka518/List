import asyncio
import aiohttp
import json
import os
import re
import datetime

# --- 1. 核心配置区 ---
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "guduo-hot.json")

# 自动计算北京时间“昨天”的日期 (骨朵最新数据只有前一天的)
tz_bj = datetime.timezone(datetime.timedelta(hours=8))
yesterday = (datetime.datetime.now(tz_bj) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

# 动态构建骨朵 API 字典
GUDUO_API_URLS = {
    "动漫": f"https://d2.guduomedia.com/m/v3/billboard/list?type=DAILY&category=ALL_ANIME&date={yesterday}&attach=gdi&orderTitle=gdi&platformId=0",
    "剧集": f"https://d2.guduomedia.com/m/v3/billboard/list?type=DAILY&category=NETWORK_DRAMA&date={yesterday}&attach=gdi&orderTitle=gdi&platformId=0",
    "综艺": f"https://d2.guduomedia.com/m/v3/billboard/list?type=DAILY&category=NETWORK_VARIETY&date={yesterday}&attach=gdi&orderTitle=gdi&platformId=0",
    "电影": f"https://d2.guduomedia.com/m/v3/billboard/list?type=DAILY&category=NETWORK_MOVIE&date={yesterday}&attach=gdi&orderTitle=gdi&platformId=0"
}

# 伪装头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# TMDB 字典
GENRE_MAP = {16: "动画", 35: "喜剧", 18: "剧情", 10765: "科幻奇幻", 99: "纪录片", 10764: "真人秀", 10767: "脱口秀"}
COUNTRY_MAP = {"CN": "中国大陆", "JP": "日本", "KR": "韩国", "US": "美国", "TW": "中国台湾", "HK": "中国香港"}

# --- 2. 标题清洗黑科技 ---
def clean_title(title):
    """根据骨朵的命名习惯，进行极端清洗，并内置特定综艺白名单映射"""
    title = title.strip()

    # --- 1. 特定综艺白名单映射 (精准打击) ---
    # 只要名字里包含 key，就强制转换为 value，跳过后续所有正则
    special_cases = {
        "怦然心动20岁": "怦然心动20岁",
        "快乐老友": "快乐老友记"  # 处理 快乐老友·有风季 等
    }

    for key, value in special_cases.items():
        if key in title:
            return value

    # --- 2. 常规清洗逻辑 ---
    # 1. 去掉“年番”、“特别篇”、“篇”等修饰词 (例如: 凡人修仙传年番 -> 凡人修仙传)
    title = title.replace('年番', '').replace('特别篇', '')
    
    # 2. 去掉“第X季” (例如: 剑来 第二季 / 剑来 第2季 -> 剑来)
    title = re.sub(r'第[一二三四五六七八九十0-9]+[季期部]', '', title, flags=re.IGNORECASE)
    title = re.sub(r'(?i)Season\s*\d+', '', title)
    
    # 3. 去掉括号和里面的内容 (例如: 某某剧(超前点播) -> 某某剧)
    title = re.sub(r'\(.*?\)|（.*?）', '', title)
    
    # 4. 去掉结尾的数字 (例如: 成何体统2 -> 成何体统，庆余年2 -> 庆余年)
    title = re.sub(r'\s*\d+$', '', title)
    
    # 5. 去除多余空格
    return re.sub(r'\s+', ' ', title).strip()

# --- 3. 骨朵数据抓取模块 ---
async def fetch_guduo_category(session, category_name, url):
    """获取指定分类的骨朵榜单"""
    print(f"正在抓取骨朵 [{category_name}] 榜单 (日期: {yesterday})...")
    items_list = []
    
    try:
        async with session.get(url, headers=HEADERS) as resp:
            if resp.status != 200:
                print(f"❌ 获取 {category_name} 失败，状态码: {resp.status}")
                return items_list
                
            data = await resp.json()
            
            # 骨朵的返回结构通常是 data: [...] 数组形式
            raw_list = data.get("data", [])
            
            # 只取前 30 名，防止匹配太多无关的数据
            for i, item in enumerate(raw_list[:30]):
                items_list.append({
                    "title": item.get("name", "未知名称"),
                    "rank": i + 1,  # 按顺序直接给排名
                    "heat": item.get("gdi", 0.0), # 骨朵指数
                    "category": category_name
                })
            
            await asyncio.sleep(0.5) # 礼貌请求
    except Exception as e:
        print(f"❌ 解析 {category_name} 接口出错: {e}")
        
    return items_list

# --- 4. TMDB 匹配模块 ---
async def search_tmdb(session, item, cache):
    """依据不同分类执行专属匹配策略"""
    raw_title = item['title']
    clean_t = clean_title(raw_title)
    category = item['category']
    
    cache_key = f"{clean_t}_{category}"
    if cache_key in cache:
        return {**item, **cache[cache_key]}

    api_headers = {"accept": "application/json"}
    if TMDB_API_KEY.startswith("eyJ"):
        api_headers["Authorization"] = f"Bearer {TMDB_API_KEY}"

    async def do_search(query, is_movie=False):
        endpoint = "/search/movie" if is_movie else "/search/tv"
        url = f"https://api.themoviedb.org/3{endpoint}"
        params = {"query": query, "language": "zh-CN"}
        if not TMDB_API_KEY.startswith("eyJ"):
            params["api_key"] = TMDB_API_KEY
            
        try:
            async with session.get(url, params=params, headers=api_headers) as resp:
                if resp.status == 200:
                    return (await resp.json()).get("results", [])
        except:
            pass
        return []

    candidates = []
    
    # 🔥 核心：按分类在 TMDB 靶向搜索
    if category == "电影":
        candidates.extend(await do_search(clean_t, is_movie=True))
        
    elif category == "剧集":
        # 剧集不做限制：先搜TV分类，如果没搜到，说明TMDB把它当成了电影，直接去搜Movie
        res_tv = await do_search(clean_t, is_movie=False)
        if res_tv:
            candidates.extend(res_tv)
        else:
            # 降级全面撒网，去电影区捞
            candidates.extend(await do_search(clean_t, is_movie=True))
        
    elif category == "综艺":
        res_tv = await do_search(clean_t, is_movie=False)
        # TMDB 里的中国综艺经常没有正确打标签，所以我们优先找带 10764(真人秀) 或 10767(脱口秀) 的
        variety_cands = [r for r in res_tv if 10764 in r.get("genre_ids", []) or 10767 in r.get("genre_ids", [])]
        # 如果没找到带标签的，就相信 TMDB 的默认排序第一个
        candidates.extend(variety_cands if variety_cands else res_tv)
        
    elif category == "动漫":
        res_tv = await do_search(clean_t, is_movie=False)
        anime_tv = [r for r in res_tv if 16 in r.get("genre_ids", [])]
        if anime_tv:
            candidates.extend(anime_tv)
        else:
            # 可能是剧场版动漫电影
            res_movie = await do_search(clean_t, is_movie=True)
            anime_movie = [r for r in res_movie if 16 in r.get("genre_ids", [])]
            candidates.extend(anime_movie)

    if not candidates:
        print(f"⚠️ 丢弃: [{raw_title}] (清洗为: {clean_t}) -> 未在 TMDB 找到 [{category}] 数据")
        return None

    best_match = candidates[0]
    media_type = "movie" if "title" in best_match else "tv"
    tmdb_id = best_match["id"]
    
    # 格式化返回值
    country_names = [COUNTRY_MAP.get(c, c) for c in best_match.get("origin_country", [])]
    genre_names = [GENRE_MAP.get(g) for g in best_match.get("genre_ids", []) if GENRE_MAP.get(g)]
    
    info = {
        "tmdbId": tmdb_id,
        "mediaType": media_type,
        "tmdbTitle": best_match.get("name") or best_match.get("title"),
        "releaseDate": best_match.get("first_air_date") or best_match.get("release_date") or "",
        "posterPath": best_match.get("poster_path"),
        "rating": round(float(best_match.get("vote_average", 0)), 1),
        "overview": best_match.get('overview') or '暂无简介',
        "regionTitle": "/".join(country_names) if country_names else "未知地区",
        "genreTitle": " / ".join(genre_names[:3]) if genre_names else category
    }
    
    cache[cache_key] = info
    print(f"✅ 成功匹配: [{raw_title}] -> TMDB: {info['tmdbTitle']} (评分: {info['rating']})")
    
    return {**item, **info}

# --- 5. 批处理引擎 ---
async def batch_process_tmdb(session, items_list, size, cache):
    results = []
    for i in range(0, len(items_list), size):
        chunk = items_list[i:i + size]
        tasks = [search_tmdb(session, item, cache) for item in chunk]
        chunk_results = await asyncio.gather(*tasks)
        results.extend([r for r in chunk_results if r is not None])
        await asyncio.sleep(0.3)
    return results

# --- 6. 主程序 ---
async def main():
    if not TMDB_API_KEY:
        print("❌ 错误: 未检测到 TMDB_API_KEY 环境变量！")
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    all_guduo_items = []

    async with aiohttp.ClientSession() as session:
        print(f"🚀 开始并发请求骨朵数据中心...")
        tasks = [fetch_guduo_category(session, cat, url) for cat, url in GUDUO_API_URLS.items()]
            
        guduo_results = await asyncio.gather(*tasks)
        for res in guduo_results:
            all_guduo_items.extend(res)
            
        print(f"\n👉 骨朵数据抓取完毕，共 {len(all_guduo_items)} 条记录。开始进行 TMDB 智能洗库...")

        cache = {}
        matched_items = await batch_process_tmdb(session, all_guduo_items, 8, cache)

        # 按分类重组数据
        final_result = {
            "source": "Guduo Media",
            "billboard_date": yesterday,
            "last_updated": datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S"),
            "categories": {
                "剧集": [x for x in matched_items if x['category'] == '剧集'],
                "综艺": [x for x in matched_items if x['category'] == '综艺'],
                "动漫": [x for x in matched_items if x['category'] == '动漫'],
                "电影": [x for x in matched_items if x['category'] == '电影']
            }
        }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
        
    print(f"\n🎉 全部完成！严格匹配成功 {len(matched_items)} 个节点，数据已保存至 {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
