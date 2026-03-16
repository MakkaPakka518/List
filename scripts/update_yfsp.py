import asyncio
import aiohttp
import json
import os
import re
import datetime
from bs4 import BeautifulSoup

# --- 配置区 ---
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "yfsp-hot.json")

# 抓取区域配置：包含了你提供的四个频道，并指明了对应的 TMDB 搜索类型
REGIONS = [
    {"title": "爱壹帆综艺", "value": "variety", "url": "https://www.yfsp.tv/list/variety?orderBy=1", "tmdb_type": "tv", "required_genre": None},
    {"title": "爱壹帆电视剧", "value": "drama",   "url": "https://www.yfsp.tv/list/drama?orderBy=1",   "tmdb_type": "tv", "required_genre": None},
    {"title": "爱壹帆电影", "value": "movie",   "url": "https://www.yfsp.tv/list/movie?orderBy=1",   "tmdb_type": "movie", "required_genre": None},
    {"title": "爱壹帆动漫", "value": "anime",   "url": "https://www.yfsp.tv/list/anime?orderBy=1",   "tmdb_type": "tv", "required_genre": 16} # 16是动画标签
]

def clean_yfsp_title(raw_title):
    """强力清洗影视站标题特有的杂质"""
    title = raw_title.strip()
    # 去除画质、语言、版本等杂质
    title = re.sub(r'(?i)(HD|BD|1080p|720p|4K|TS|TC|DVD|VOD|中字|国语|粤语|英语|完整版|未删减版|纯享版|加更版)', '', title)
    # 去除更新状态、季数等
    title = re.sub(r'更新至.*?集|第[一二三四五六七八九十百\d]+[季部章]', '', title)
    title = re.sub(r'(?i)Season\s*\d+', '', title)
    # 去除各类括号内容
    title = re.sub(r'\(.*?\)|（.*?）|\[.*?\]|【.*?】', '', title)
    return re.sub(r'\s+', ' ', title).strip()

async def fetch_yfsp_list(session, region):
    """请求页面，使用 BS4 智能提取海报和剧名"""
    url = region["url"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    
    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                print(f"❌ 爱壹帆请求失败: HTTP {resp.status}")
                return []
            
            html = await resp.text(errors="ignore")
            soup = BeautifulSoup(html, 'html.parser')
            
            items = []
            seen_titles = set()
            
            # 这类网站通常把海报图片放在特定的结构中，我们直接找 img 标签提取 alt 或 title
            for img in soup.find_all('img'):
                title = img.get('alt') or img.get('title') or ""
                if title and len(title) > 1 and len(title) < 30:
                    clean_t = clean_yfsp_title(title)
                    # 过滤掉杂音词汇
                    if clean_t and clean_t not in seen_titles and clean_t not in ["Logo", "爱壹帆", "加载中"]:
                        seen_titles.add(clean_t)
                        items.append({"title": clean_t, "raw_title": title})
            
            # 如果 img 没抓到，尝试找所有的 a 标签作为备用方案
            if len(items) < 10:
                for a in soup.find_all('a'):
                    title = a.get('title') or a.text.strip()
                    if title and len(title) > 1 and len(title) < 30:
                        clean_t = clean_yfsp_title(title)
                        if clean_t and clean_t not in seen_titles and clean_t not in ["首页", "排行榜", "搜索"]:
                            seen_titles.add(clean_t)
                            items.append({"title": clean_t, "raw_title": title})
            
            # 返回前 40 部
            return items[:40]
    except Exception as e:
        print(f"获取爱壹帆 {region['title']} 异常: {e}")
        return []

async def fetch_tmdb_detail(session, item, region_config, cache):
    """智能 TMDB 匹配：支持电影和 TV 的区分"""
    db_title = item["title"]
    if not db_title: return None

    tmdb_type = region_config["tmdb_type"]
    cache_key = f"{tmdb_type}_{db_title}"
    if cache_key in cache: 
        return cache[cache_key]

    url = f"https://api.themoviedb.org/3/search/{tmdb_type}"
    headers = {"accept": "application/json"}
    params = {"query": db_title, "language": "zh-CN"}
    
    if TMDB_API_KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {TMDB_API_KEY}"
    else:
        params["api_key"] = TMDB_API_KEY

    try:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200: return None
            data = await resp.json()
            results = data.get("results", [])
            
            for res in results:
                # 校验动漫专属标签
                req_genre = region_config.get("required_genre")
                if req_genre and req_genre not in res.get("genre_ids", []):
                    continue

                # 兼容 Movie(title) 和 TV(name) 字段的差异
                tmdb_t = (res.get("name") or res.get("title") or "").lower()
                tmdb_o = (res.get("original_name") or res.get("original_title") or "").lower()
                target = db_title.lower()
                
                if target in tmdb_t or target in tmdb_o or tmdb_t in target:
                    tmdb_id = res.get("id")
                    poster_path = res.get("poster_path")
                    
                    if not tmdb_id or not poster_path:
                        continue

                    info = {
                        "id": str(tmdb_id),
                        "type": "tmdb",
                        "title": res.get("name") or res.get("title"),
                        "yfsp_title": item["raw_title"], # 留个原名做对比
                        "description": res.get("overview"),
                        "rating": res.get("vote_average"),
                        "releaseDate": res.get("first_air_date") or res.get("release_date"),
                        "posterPath": poster_path,
                        "backdropPath": res.get("backdrop_path"),
                        "mediaType": tmdb_type
                    }
                    cache[cache_key] = info
                    return info
    except: pass
    return None

async def batch_process(session, items, region_config, size, cache):
    results = []
    for i in range(0, len(items), size):
        chunk = items[i:i + size]
        tasks = [fetch_tmdb_detail(session, item, region_config, cache) for item in chunk]
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
            items = await fetch_yfsp_list(session, region)
            print(f"   => 提取到 {len(items)} 个候选影片，开始 TMDB ({region['tmdb_type']}) 匹配...")
            
            matched = await batch_process(session, items, region, 10, cache)
            print(f"   => 成功匹配 {len(matched)} 部高清数据！\n")
            
            final_result[region["value"]] = matched

    # 北京时间记录
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    final_result["last_updated"] = datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    print(f"✅ 爱壹帆抓取圆满结束！已保存至 {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
