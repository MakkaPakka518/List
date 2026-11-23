"""一次性回填豆瓣热评：只写 douban-hot.json 的 comments 数据组，不改动任何榜单字段。

comments 结构：
{
  "tv.12345": {"text": "简短热评", "author": "用户名", "rating": 5},
  ...
}

key 使用 mediaType.tmdbId，与 ForwardWidget / Rex 的作品 ID 一致，前端可直接按 ID 取。
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
HEADERS = {"User-Agent": UA, "Referer": "https://m.douban.com/movie/"}

MIN_LEN = 8
MAX_LEN = 46
COMMENT_COUNT = 10
SLEEP = 0.2

CHANNEL_TYPES = {
    "tv": "tv", "tv_domestic": "tv", "tv_american": "tv", "tv_japanese": "tv",
    "tv_korean": "tv", "tv_animation": "tv", "tv_documentary": "tv",
    "show_domestic": "tv", "show_foreign": "tv",
}
REGION_QUERY = {
    "tv": "tv", "tv_domestic": "tv_domestic", "tv_american": "tv_american",
    "tv_japanese": "tv_japanese", "tv_korean": "tv_korean", "tv_animation": "tv_animation",
    "tv_documentary": "tv_documentary", "show_domestic": "show_domestic",
    "show_foreign": "show_foreign",
}


def get(url, params=None):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())


def pick(interests):
    for item in interests or []:
        text = re.sub(r"\s+", " ", item.get("comment") or "").strip()
        if not (MIN_LEN <= len(text) <= MAX_LEN):
            continue
        if "http" in text or "www." in text:
            continue
        user = (item.get("user") or {}).get("name") or ""
        rating = (item.get("rating") or {}).get("value") or 0
        return {"text": text, "author": user, "rating": rating}
    return None


def main():
    with open("data/douban-hot.json", encoding="utf-8") as handle:
        data = json.load(handle)

    # 每个榜单抓当前前 60 条；先拿到豆瓣条目 ID 与剧名的映射
    douban_ids = {}
    for channel, query_type in REGION_QUERY.items():
        try:
            listing = get("https://m.douban.com/rexxar/api/v2/subject/recent_hot/tv",
                          {"start": 0, "limit": 60, "type": query_type})
        except Exception as error:
            print(f"列表失败 {channel}: {error}", file=sys.stderr)
            continue
        for entry in listing.get("items") or []:
            title = (entry.get("title") or "").strip()
            if title and entry.get("id"):
                douban_ids.setdefault(title, entry["id"])
        time.sleep(SLEEP)

    print(f"豆瓣条目映射 {len(douban_ids)} 条")

    comments = dict(data.get("comments") or {})
    wanted = []
    for channel, media_type in CHANNEL_TYPES.items():
        for item in (data.get(channel) or [])[:60]:
            key = f"{media_type}.{item.get('tmdbId') or item.get('id')}"
            douban_id = douban_ids.get((item.get("title") or "").strip())
            if douban_id and key not in comments:
                wanted.append((key, douban_id))

    print(f"待抓 {len(wanted)} 条")
    for index, (key, douban_id) in enumerate(wanted, 1):
        try:
            payload = get(f"https://m.douban.com/rexxar/api/v2/tv/{douban_id}/interests",
                          {"count": COMMENT_COUNT, "order_by": "hot", "start": 0})
            result = pick(payload.get("interests"))
            if result:
                comments[key] = result
        except Exception as error:
            print(f"跳过 {key}: {error}", file=sys.stderr)
        if index % 20 == 0:
            print(f"  进度 {index}/{len(wanted)}，已有 {len(comments)} 条")
        time.sleep(SLEEP)

    data["comments"] = comments
    with open("data/douban-hot.json", "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    print(f"完成：comments 共 {len(comments)} 条")


if __name__ == "__main__":
    main()
