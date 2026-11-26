import asyncio
import datetime
import unittest
from unittest.mock import patch

from scripts import update_douban as db


class AiringTests(unittest.TestCase):
    def test_only_aired_regular_episodes(self):
        today = datetime.date(2026, 11, 27)
        ep = {"season_number": 2, "episode_number": 4, "air_date": "2026-11-22"}
        details = {"last_episode_to_air": ep, "next_episode_to_air": dict(ep, episode_number=5, air_date="2026-11-29"), "number_of_episodes": 10}
        self.assertEqual(db.tmdb_episode_text(details, today), "S02E04")
        for other in [None, dict(ep, season_number=0), dict(ep, air_date="2026-11-29"), dict(ep, air_date="2026-02-30")]:
            self.assertEqual(db.tmdb_episode_text(dict(details, last_episode_to_air=other), today), "")
        single = dict(details, last_episode_to_air=dict(ep, season_number=1), genres=[{"id":10764}])
        self.assertEqual(db.tmdb_episode_text(single, today), "更新至4期")
        self.assertEqual(db.tmdb_episode_text(dict(single, status="Ended", number_of_episodes=4, next_episode_to_air=None), today), "全4期")
        self.assertEqual(db.with_douban_fields({"episodeText":"S02E04"}, {"episodes_info":"共10集"})["episodeText"], "S02E04")

    def test_douban_rating_is_distinct_from_tmdb_even_without_episode_info(self):
        base = {"rating":7.1, "episodeText":"S02E04"}
        for value, expected in [({"value":8.6,"count":59833},8.6), ({"value":0,"count":0},"暂无评分"), (None,"暂无评分"), ({},"暂无评分")]:
            self.assertEqual(db.with_douban_fields(base, {"rating":value}), {**base, "doubanRating":expected})
        self.assertNotIn("doubanRating", base)

    def test_matching_preserves_fields_and_does_not_cache_row_progress(self):
        raw = {"title":"两京十五日", "episodes_info":"更新至16集", "card_subtitle":"2026 / 中国大陆 / 剧情 古装"}
        result = {"id":203483, "name":raw["title"], "first_air_date":"2026-11-20", "genre_ids":[18], "overview":"原剧情", "poster_path":"/p.jpg", "backdrop_path":"/b.jpg"}
        calls = []

        class Response:
            status = 200
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def json(self): return {"results":[result]} if len(calls) == 1 else {"last_air_date":"2026-11-23"}

        class Session:
            def get(self, url, **kwargs):
                calls.append(url)
                return Response()

        with patch.object(db, 'TMDB_API_KEY', 'test'):
            cache, session = {}, Session()
            def row(text, rating=None): return asyncio.run(db.fetch_tmdb_detail(session, dict(raw, episodes_info=text, rating=rating), cache))
            a, b, c = row("更新至16集"), row("24集全", {"value":7.9,"count":96602}), row("")
        self.assertEqual([r.pop("doubanRating") for r in (a,b,c)], ["暂无评分", 7.9, "暂无评分"])
        self.assertEqual(a.pop("episodeText"), "更新至16集")
        self.assertEqual(b.pop("episodeText"), "全24集")
        self.assertNotIn("episodeText", c)
        self.assertEqual(a, b); self.assertEqual(a, c)
        self.assertEqual((a["id"], a["type"], a["description"], a["genreTitle"], a["lastUpdateDate"]), ("203483", "tmdb", "原剧情", "剧情", "2026-11-23"))
        self.assertEqual(len(calls), 2)
