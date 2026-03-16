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
OUTPUT_FILE = os.path.join(DATA_DIR, "yinghua-hot.json")

# TMDB 中“动画”的分类 ID 是 16
REQUIRED_GENRE_ID = 16

# 抓取区域配置
REGIONS = [
    {"title": "樱花日漫", "value": "japanese", "url": "https://www.yinghuadongman.com.cn/h/1/"},
    {"title": "樱花国漫", "value": "chinese",  "url": "https://www.yinghuadongman.com.cn/h/2/"},
    {"title": "樱花美漫", "value": "american", "url": "https://www.yinghuadongman.com.cn/h/3/"}
]

def clean_anime_title(raw_title):
    """清洗动漫标题，去除季数、括号后缀、配音版本等，大幅提高 TMDB 命中率"""
    title = raw_title.strip()
    # 去除第X季/部/章等后缀
    title = re.sub(r'第[一二三四五六七八九十百\d]+[季部章]', '', title)
    title = re.sub(r'(?i)Season\s*\d+', '', title)
    # 去除各种括号里的修饰词 (比如: 最终季、Part2)
    title = re.sub(r'\(.*?\)|（.*?）|\[.*?\]|【.*?】', '', title)
    # 去除常见动漫特有后缀
    title = re.sub(r'国语版|日语版|中配版|剧场版|OVA|OAD|TV版|重制版', '', title)
    return re.sub(r'\s+', ' ', title).strip()

async def fetch_yinghua_list(session, region):
    """请求樱花页面，智能提取动漫剧名"""
    url = region["url"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }
    
    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                print(f"樱花动漫请求失败: HTTP {resp.status}")
                return []
            
            # 使用 bs4 容错解析 HTML
            html = await resp.text(errors="ignore")
            soup = BeautifulSoup(html, 'html.parser')
            
            items = []
            seen_titles = set()
            ignore_words = {"首页", "排行榜", "最近更新", "动画", "动漫", "留言", "登录", "注册", "搜索", "更多"}
            
            # 暴力且智能地扫荡所有链接标签，提取剧名
            for a in soup.find_all('a'):
                title = a.get('title') or ""
                if not title:
                    img = a.find('img')
                    if img:
                        title = img.get('alt') or ""
                if not title:
                    title = a.text.strip()
                
                # 过滤掉非剧名的杂音
                if len(title) > 1 and len(title) < 30 and title not in ignore_words:
                    if title not in seen_titles:
                        seen_titles.add(title)
                        items.append({"title": title})
            
            # 每个栏目取前 40 部热更剧集进行匹配
            return items[:40]
    except Exception as e:
        print(f"获取樱花动漫 {region['title']} 异常: {e}")
        return []

async def fetch_tmdb_detail(session, item, cache):
    """将清洗后的名字发往 TMDB，并强制校验「动画」标签"""
    raw_title = item.get("title", "").strip()
    db_title = clean_anime_title(raw_title)
    if not db_title: return None

    if db_title in cache: 
        return cache[db_title]

    url = "https://api.themoviedb.org/3/search/tv"
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
                genre_ids = res.get("genre_ids", [])
                
                # 🛑 核心过滤逻辑：如果这部剧没有包含“动画(16)”标签，直接跳过！
                if REQUIRED_GENRE_ID not in genre_ids:
                    continue

                tmdb_t = (res.get("name") or "").lower()
                tmdb_o = (res.get("original_name") or "").lower()
                target = db_title.lower()
                
                # 宽松匹配：只要包含即可
                if target in tmdb_t or target in tmdb_o or tmdb_t in target:
                    tmdb_id = res.get("id")
                    poster_path = res.get("poster_path")
                    
                    if not tmdb_id or not poster_path:
                        continue

                    info = {
                        "id": str(tmdb_id),
                        "type": "tmdb",
                        "title": res.get("name"),
                        "yinghua_title": raw_title, # 保留原站标题供你参考
                        "description": res.get("overview"),
                        "rating": res.get("vote_average"),
                        "releaseDate": res.get("first_air_date"),
                        "posterPath": poster_path,
                        "backdropPath": res.get("backdrop_path"),
                        "mediaType": "tv",
                        "genreTitle": "动画"
                    }
                    cache[db_title] = info
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
            items = await fetch_yinghua_list(session, region)
            print(f"   => 从页面提取到 {len(items)} 个候选剧名，开始匹配 TMDB 动漫标签...")
            
            matched = await batch_process(session, items, 10, cache)
            print(f"   => 成功匹配 {len(matched)} 部纯正动漫数据！\n")
            
            final_result[region["value"]] = matched

    # 北京时间记录
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    final_result["last_updated"] = datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    print(f"✅ 樱花动漫抓取圆满结束！已保存至 {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
