import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
import os
import re
import datetime

# --- 配置区 ---
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "bangumi-hot.json")

# Bangumi 抓取页数 (每页24条，抓5页 = 120部热门动漫)
PAGES_TO_FETCH = 5 

# TMDB 标签和地区映射表
GENRE_MAP = {
    16: "动画", 10759: "动作冒险", 35: "喜剧", 18: "剧情", 14: "奇幻", 
    878: "科幻", 9648: "悬疑", 10749: "爱情", 27: "恐怖", 10765: "科幻奇幻", 
    80: "犯罪", 99: "纪录片", 10751: "家庭", 36: "历史", 10402: "音乐", 28: "动作", 12: "冒险"
}

COUNTRY_MAP = {
    "JP": "日本", "CN": "中国大陆", "US": "美国", "KR": "韩国", "GB": "英国", "TW": "中国台湾", "HK": "中国香港"
}

def clean_anime_title(title):
    """黑科技：清理标题中的季数，极大提高 TMDB 匹配命中率"""
    title = re.sub(r'第[一二三四五六七八九十\d]+[季期章].*', '', title, flags=re.IGNORECASE)
    title = re.sub(r'(?i)Season \d+.*', '', title)
    title = re.sub(r' \d{4}$', '', title) # 去除结尾可能附带的年份
    return title.strip()

async def fetch_bangumi_hot(session):
    """获取 Bangumi 的近期热门动漫排行"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    anime_list = []
    
    for page in range(1, PAGES_TO_FETCH + 1):
        url = f"https://bgm.tv/anime/browser?sort=collects&page={page}"
        print(f"正在抓取 Bangumi 热门排行第 {page} 页...")
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    continue
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                items = soup.select('ul#browserItemList li.item')
                
                for item in items:
                    title_elem = item.select_one('h3 a.l')
                    orig_title_elem = item.select_one('h3 small.grey')
                    info_elem = item.select_one('p.info.tip')
                    
                    if title_elem:
                        title_cn = title_elem.text.strip()
                        title_orig = orig_title_elem.text.strip() if orig_title_elem else title_cn
                        
                        # 从描述里尝试提取年份，比如 "2023年10月 / TV"
                        info_text = info_elem.text.strip() if info_elem else ""
                        year_match = re.search(r'(\d{4})年', info_text)
                        year = year_match.group(1) if year_match else None
                        
                        anime_list.append({
                            "title": title_cn,
                            "original_title": title_orig,
                            "year": year
                        })
            await asyncio.sleep(1) # 尊重对方服务器，停顿一下
        except Exception as e:
            print(f"获取 Bangumi 第 {page} 页出错: {e}")
            
    return anime_list

async def search_tmdb(session, anime, cache):
    """匹配 TMDB，强制要求包含动画标签(16)，提取类型和地区"""
    raw_title = anime['title']
    clean_title = clean_anime_title(raw_title)
    orig_title = clean_anime_title(anime['original_title'])
    year = anime['year']
    
    cache_key = f"{clean_title}_{year}"
    if cache_key in cache:
        return cache[cache_key]

    headers = {"accept": "application/json"}
    if TMDB_API_KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {TMDB_API_KEY}"
    else:
        # 如果不是Token，则放在params里
        pass

    async def do_search(query_title, is_movie=False):
        endpoint = "/search/movie" if is_movie else "/search/tv"
        url = f"https://api.themoviedb.org/3{endpoint}"
        params = {"query": query_title, "language": "zh-CN"}
        if not TMDB_API_KEY.startswith("eyJ"):
            params["api_key"] = TMDB_API_KEY
            
        try:
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("results", [])
        except:
            pass
        return []

    # 策略：先搜剧集TV，如果没搜到或者没有动画标签，再搜电影Movie
    # 如果中文名搜不到，拿原名搜
    candidates = []
    
    # 1. 搜中文名 TV
    res_tv = await do_search(clean_title, False)
    candidates.extend([r for r in res_tv if 16 in r.get("genre_ids", [])])
    
    # 2. 如果没有，搜原名 TV
    if not candidates and orig_title != clean_title:
        res_tv_orig = await do_search(orig_title, False)
        candidates.extend([r for r in res_tv_orig if 16 in r.get("genre_ids", [])])
        
    # 3. 如果还是没有，说明可能是剧场版，搜中文名 Movie
    if not candidates:
        res_movie = await do_search(clean_title, True)
        candidates.extend([r for r in res_movie if 16 in r.get("genre_ids", [])])

    if not candidates:
        print(f"❌ 丢弃: [{raw_title}] -> 未匹配到带动画标签的TMDB数据")
        return None

    # 优先挑选年份匹配上的，如果没有，直接拿第一条
    best_match = candidates[0]
    if year:
        for c in candidates:
            c_date = c.get("first_air_date") or c.get("release_date") or ""
            if c_date.startswith(year):
                best_match = c
                break

    # === 构建保留类型和地区的终极数据 ===
    media_type = "movie" if "title" in best_match else "tv"
    tmdb_title = best_match.get("name") or best_match.get("title")
    release_date = best_match.get("first_air_date") or best_match.get("release_date") or ""
    score = best_match.get("vote_average", 0)
    
    # 转换地区 (TMDB 返回的 origin_country 是个数组，例如 ["JP"])
    raw_countries = best_match.get("origin_country", [])
    country_names = [COUNTRY_MAP.get(c, c) for c in raw_countries]
    country_str = "/".join(country_names) if country_names else "未知地区"

    # 转换类型 (剔除 16 动画本身，留下剧情、奇幻等具体流派)
    raw_genres = best_match.get("genre_ids", [])
    genre_names = [GENRE_MAP.get(g) for g in raw_genres if g != 16 and GENRE_MAP.get(g)]
    genre_str = " / ".join(genre_names[:3]) if genre_names else "动画"

    info = {
        "id": str(best_match["id"]),
        "tmdbId": best_match["id"],
        "type": "tmdb",
        "mediaType": media_type,
        "title": tmdb_title,
        "releaseDate": release_date,
        "posterPath": best_match.get("poster_path"),
        "backdropPath": best_match.get("backdrop_path"),
        "rating": round(float(score), 1),
        "description": f"{release_date[:4]} · ⭐ {round(float(score), 1)} · {country_str}\n{best_match.get('overview') or '暂无简介'}",
        # 为将来的 Widget 高级筛选铺路 👇
        "genreTitle": genre_str,
        "regionTitle": country_str,
        "rawGenres": raw_genres,
        "rawCountries": raw_countries
    }
    
    cache[cache_key] = info
    print(f"✅ 成功匹配: [{raw_title}] -> {tmdb_title} (类型: {genre_str} | 地区: {country_str})")
    return info

async def batch_process_tmdb(session, anime_list, size, cache):
    results = []
    for i in range(0, len(anime_list), size):
        chunk = anime_list[i:i + size]
        tasks = [search_tmdb(session, item, cache) for item in chunk]
        chunk_results = await asyncio.gather(*tasks)
        results.extend([r for r in chunk_results if r is not None])
        await asyncio.sleep(0.3) # 防止被封
    return results

async def main():
    if not TMDB_API_KEY:
        print("❌ 错误: 未检测到 TMDB_API_KEY 环境变量！")
        return

    os.makedirs(DATA_DIR, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        print("🚀 开始抓取 Bangumi 热门列表...")
        anime_list = await fetch_bangumi_hot(session)
        print(f"👉 共抓取到 {len(anime_list)} 部动漫，开始严格匹配 TMDB 纯动画分类...")
        
        cache = {}
        matched_animes = await batch_process_tmdb(session, anime_list, 8, cache)

        # 构建最终的数据结构
        tz_bj = datetime.timezone(datetime.timedelta(hours=8))
        final_result = {
            "last_updated": datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S"),
            "total_matched": len(matched_animes),
            "hot_anime": matched_animes
        }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
        
    print(f"\n🎉 抓取完毕！共找到 {len(anime_list)} 个目标，严格匹配成功 {len(matched_animes)} 个！文件已保存至 {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
