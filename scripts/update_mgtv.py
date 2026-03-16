import asyncio
import aiohttp
import json
import os
import re
import datetime

# --- 配置区 ---
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "mgtv-hot.json")

# 芒果TV 片库列表底层 API
MG_BASE_URL = "https://pianku.api.mgtv.com/rider/list/pcweb/v3"

# TMDB 类型映射表
GENRE_MAP = {
    28: "动作", 12: "冒险", 16: "动画", 35: "喜剧", 80: "犯罪", 99: "纪录片", 18: "剧情", 
    10751: "家庭", 14: "奇幻", 36: "历史", 27: "恐怖", 10402: "音乐", 9648: "悬疑", 
    10749: "爱情", 878: "科幻", 10770: "电视电影", 53: "惊悚", 10752: "战争", 37: "西部", 
    10759: "动作冒险", 10762: "儿童", 10763: "新闻", 10764: "真人秀", 10765: "科幻奇幻", 
    10766: "肥皂剧", 10767: "脱口秀", 10768: "战争政治"
}

# 自定义你的芒果抓取区域
REGIONS = [
    { 
        "title": "全部剧集 (热播榜)", 
        "value": "tv", 
        "limit": 150, 
        "channelId": 2, # 2表示电视剧
        "params": {
            "kind": "a1", "area": "a1", "year": "all", "sort": "c1", "chargeInfo": "a1"
        }
    },
    { 
        "title": "芒果王牌综艺", 
        "value": "show", 
        "limit": 150, 
        "channelId": 1, # 1表示综艺
        "params": {
            "kind": "a1", "area": "a1", "year": "all", "sort": "c1"
        }
    }
]

def clean_mgtv_title(raw_title):
    """清洗芒果TV的标题，去除季数、后缀等，提高TMDB匹配率"""
    title = raw_title.strip()
    # 🔴 升级：剔除 "第一季"、"Season 1"、"第2部"、"第3期" 等
    title = re.sub(r'第[一二三四五六七八九十百\d]+[季期部章]', '', title)
    title = re.sub(r'(?i)Season\s*\d+', '', title)
    # 🔴 升级：剔除常见的芒果特殊后缀，涵盖圆括号和方括号
    title = re.sub(r'\(.*?\)|（.*?）|\[.*?\]|【.*?】', '', title)
    # 压缩多余空格
    title = re.sub(r'\s+', ' ', title).strip()
    return title

async def fetch_mgtv_list(session, region):
    """请求芒果官方API，获取基础列表"""
    items = []
    page_size = 30
    page_count = (region["limit"] + page_size - 1) // page_size
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.mgtv.com/"
    }
    
    for page in range(1, page_count + 1):
        # 基础必需参数
        api_params = {
            "allowedpn": 1,
            "channelId": region["channelId"],
            "pn": page,
            "pc": page_size,
        }
        # 混入你的自定义筛选参数
        if "params" in region:
            api_params.update(region["params"])
            
        try:
            async with session.get(MG_BASE_URL, params=api_params, headers=headers) as resp:
                if resp.status != 200: 
                    print(f"芒果接口请求失败: {region['title']} 第{page}页 - HTTP {resp.status}")
                    break
                data = await resp.json()
                docs = data.get("data", {}).get("hitDocs", [])
                
                if not docs:
                    break
                
                for doc in docs:
                    items.append({
                        "title": doc.get("title", ""),
                        "card_subtitle": doc.get("subtitle", "")
                    })
                    
                if len(items) >= region["limit"]:
                    items = items[:region["limit"]]
                    break
        except Exception as e: 
            print(f"获取芒果TV {region['title']} 第{page}页异常: {e}")
            break
            
        await asyncio.sleep(0.5)
        
    return items

async def fetch_tmdb_detail(session, item, cache):
    """使用 TMDB API 洗出标准的高清海报和详情"""
    raw_title = item.get("title", "").strip()
    db_title = clean_mgtv_title(raw_title)
    subtitle = item.get("card_subtitle", "")
    
    # 尝试提取年份。芒果经常在标题带年份 (例如《乘风2024》) 或者在副标题里写年份
    db_year = None
    year_match = re.search(r'\b(20\d{2})\b', subtitle)
    if year_match:
        db_year = year_match.group(1)
    else:
        # 如果副标题没年份，去主标题里找
        title_year_match = re.search(r'\b(20\d{2})\b', raw_title)
        if title_year_match:
            db_year = title_year_match.group(1)
            # 找到后，把提取出的年份从剧名中删掉，防止 TMDB 搜 "乘风2024" 搜不到
            db_title = db_title.replace(db_year, "").strip()

    cache_key = f"{db_title}_{db_year}"
    if cache_key in cache: 
        return cache[cache_key]

    # 不管是芒果综艺还是电视剧，在 TMDB 统统归类为 tv
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
            
            # 容错机制：如果带年份搜不到，抛弃年份放宽条件再搜一次
            if not results and db_year: 
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
                        
                    # 🔴 核心新增：拿着 id 去请求详情，获取最新更新日期 (last_air_date)
                    detail_url = f"https://api.themoviedb.org/3/tv/{tmdb_id}"
                    detail_params = {"language": "zh-CN"}
                    if not TMDB_API_KEY.startswith("eyJ"):
                        detail_params["api_key"] = TMDB_API_KEY
                        
                    last_update_date = first_air # 默认用首播日期兜底
                    try:
                        async with session.get(detail_url, params=detail_params, headers=headers) as d_resp:
                            if d_resp.status == 200:
                                d_data = await d_resp.json()
                                # 获取最新播出日期，如果没有则退回到首播日期
                                last_update_date = d_data.get("last_air_date") or first_air
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
                        "voteCount": res.get("vote_count"),
                        "popularity": res.get("popularity"),
                        "releaseDate": first_air,
                        "lastUpdateDate": last_update_date, # 🔴 新增：这里保存给前端排序用
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
    """控制并发量，防止被 TMDB 封禁"""
    results = []
    for i in range(0, len(items), size):
        chunk = items[i:i + size]
        tasks = [fetch_tmdb_detail(session, item, cache) for item in chunk]
        chunk_results = await asyncio.gather(*tasks)
        results.extend([r for r in chunk_results if r is not None])
        await asyncio.sleep(0.3) # ⚠️ 稍微调慢了一点点防风控
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
        cache = {} 
        
        for region in REGIONS:
            print(f"🚀 正在抓取: {region['title']} ({region['limit']}部)")
            items = await fetch_mgtv_list(session, region)
            print(f"   => 从芒果TV获取到 {len(items)} 条基础记录，开始发送给 TMDB 洗数据...")
            
            matched = await batch_process(session, items, 10, cache)
            print(f"   => 完美匹配到 {len(matched)} 条双图高清数据！\n")
            
            final_result[region["value"]] = matched

    # 标记时间戳
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    final_result["last_updated"] = datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    print(f"✅ 伟大工程扩展！所有芒果TV数据已成功保存至 {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
