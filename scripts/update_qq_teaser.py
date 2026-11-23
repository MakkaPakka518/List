"""抓取腾讯视频与爱奇艺片库的「本期看点」，写入 data/qq-teaser.json。

腾讯：second_title，缺失时用 actor_info_core_details。
爱奇艺：desc，缺失时用 kvs.featureSubTitle。
两个渠道共用同一字段格式，卡片无需区分来源。
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
QQ_CHANNELS = (("tv", "100113"), ("movie", "100173"))
IQ_CHANNELS = (("tv", 2), ("movie", 1), ("variety", 6), ("anime", 4), ("doc", 3), ("kids", 15))
IQ_API = "https://pub.m.iqiyi.com/h5/main/recVideos/lib/"
IQ_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
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


def iq_request(channel_id, page=1, mode=11):
    query = {
        "page_id": page,
        "mode": mode,
        "channel_id": channel_id,
        "ret_num": 21,
        "pos": 1,
        "type": "list",
        "post": "list",
        "from": "mobile_videolib",
        "is_unified_interface": 1,
        "version": "1.0.0",
        "play_platform": "H5_QIYI",
    }
    from urllib.parse import urlencode

    req = Request(
        IQ_API + "?" + urlencode(query),
        headers={
            "User-Agent": IQ_UA,
            "Referer": "https://m.iqiyi.com/",
            "Accept": "application/json",
        },
    )
    with urlopen(req, timeout=30) as response:
        body = json.load(response)
    return ((body.get("data") or {}).get("videos") or [])


def parse_iq(video):
    kvs = video.get("kvs") or {}
    teaser = str(video.get("desc") or "").strip()
    if not teaser:
        teaser = str(kvs.get("featureSubTitle") or "").strip()
    aid = str(video.get("albumId") or video.get("qipuId") or "").strip()
    title = clean_title(video.get("albumName") or video.get("shortTitle"))
    if not aid or not title:
        return None
    year = str(video.get("year") or "")
    if not (year.isdigit() and len(year) == 4):
        period = str(video.get("period") or "")
        year = period[:4] if period[:4].isdigit() else ""
    return {
        "cid": "iq" + aid,
        "title": title,
        "teaser": teaser,
        "year": year,
        "genre": "",
        "area": "",
        "episodeText": str(video.get("lowerRightCorner") or "").strip(),
    }


def collect_iq(channel_id):
    entries = []
    seen = set()
    for video in iq_request(channel_id):
        entry = parse_iq(video)
        if entry and entry["cid"] not in seen:
            seen.add(entry["cid"])
            entries.append(entry)
    return entries


def collect(results):
    for channel, channel_id in QQ_CHANNELS:
        entries, seen = [], set()
        for params in cards(request(channel_id)):
            entry = parse(params)
            if entry and entry["cid"] not in seen:
                seen.add(entry["cid"])
                entries.append(entry)
        with_teaser = sum(1 for entry in entries if entry["teaser"])
        print(f"qq {channel}: {len(entries)} entries, {with_teaser} with teaser")
        results[channel] = entries
    for channel, channel_id in IQ_CHANNELS:
        try:
            entries = collect_iq(channel_id)
        except Exception as error:
            print(f"iq {channel} failed, keeping previous entries: {error}")
            continue
        with_teaser = sum(1 for entry in entries if entry["teaser"])
        print(f"iq {channel}: {len(entries)} entries, {with_teaser} with teaser")
        # 爱奇艺补充到同名字段；已存在的按 cid 去重，不改腾讯条目。
        existing = results.setdefault(channel, [])
        seen = {entry["cid"] for entry in existing}
        existing.extend(entry for entry in entries if entry["cid"] not in seen)
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
