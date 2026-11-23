"""抓取腾讯视频片库的「本期看点」，写入 data/qq-teaser.json。

看点原文在腾讯列表接口的 second_title 字段，少数条目只有 actor_info_core_details。
脚本不依赖 TMDB，只保存榜单原文；TMDB 匹配由 rex 模块运行时完成。
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

API = (
    "https://pbaccess.video.qq.com/trpc.multi_vector_layout.mvl_controller"
    ".MVLPageHTTPService/getMVLPage?&vversion_platform=18"
)
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://v.qq.com",
    "Referer": "https://v.qq.com/tv-series-list/v-index.html",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}
CHANNELS = (("tv", "100113"), ("movie", "100173"))
OUTPUT = Path("data/qq-teaser.json")
BEIJING = timezone(timedelta(hours=8))


def clean_title(value):
    return str(value or "").replace("·更新", "").strip()


def request(channel_id):
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
    body = json.dumps(payload).encode("utf-8")
    req = Request(API, data=body, headers=HEADERS, method="POST")
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def cards(data):
    modules = (data.get("data") or {}).get("modules") or {}
    for card in ((modules.get("normal") or {}).get("cards") or []):
        poster = (card.get("children_list") or {}).get("poster_card")
        if not poster:
            continue
        items = poster.get("cards") or poster
        if isinstance(items, list) and items:
            return [item.get("params") or {} for item in items]
    return []


def parse(params):
    teaser = str(params.get("second_title") or "").strip()
    if not teaser:
        teaser = str(params.get("actor_info_core_details") or "").strip()
    cid = params.get("cid")
    title = clean_title(params.get("title"))
    if not cid or not title:
        return None
    return {
        "cid": cid,
        "title": title,
        "teaser": teaser,
        "year": str(params.get("year") or "")[:4],
        "genre": params.get("main_genre") or "",
        "area": params.get("area_name") or "",
        "episodeText": params.get("timelong") or "",
    }


def collect(results):
    out = []
    for channel, channel_id in CHANNELS:
        entries = []
        for params in cards(request(channel_id)):
            entry = parse(params)
            if entry:
                entries.append(entry)
        with_teaser = sum(1 for entry in entries if entry["teaser"])
        print(f"{channel}: {len(entries)} entries, {with_teaser} with teaser")
        results[channel] = entries
    return results


def main():
    results = {}
    collect(results)
    if not any(results.values()):
        raise SystemExit("no cards parsed, keeping the previous file")
    payload = {
        "updatedAt": datetime.now(BEIJING).isoformat(timespec="seconds"),
        "source": "腾讯视频片库列表",
        "channels": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, OUTPUT)
    total = sum(len(items) for items in results.values())
    print(f"saved {total} entries to {OUTPUT}")


if __name__ == "__main__":
    main()
