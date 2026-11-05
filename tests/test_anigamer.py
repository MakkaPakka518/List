import importlib.util
from pathlib import Path

from scrapling.parser import Selector


SCRIPT = Path(__file__).parents[1] / "scripts" / "update_anigamer.py"
SPEC = importlib.util.spec_from_file_location("update_anigamer", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

page = Selector("""
<a class="theme-list-main" href="animeRef.php?sn=114209">
  <div class="anime-label-block"></div>
  <p class="theme-name">學生會也有洞！</p>
  <p class="theme-time">年份：2026/10</p>
</a>
""")
items = MODULE.parse_page(page)
assert items == [{"sn": "114209", "sourceTitle": "學生會也有洞！", "year": "2026", "mediaHint": ""}]

calls = []
MODULE.tmdb_get = lambda path, params: calls.append((path, params)) or {"results": [{"id": 202, "name": "學生會也有洞！", "first_air_date": "2026-10-01"}]}
assert MODULE.match_tmdb(items[0]) == {"tmdbId": 202, "mediaType": "tv"}
assert calls[0][0] == "search/tv"
assert calls[0][1]["language"] == "zh-TW"
assert MODULE.FILTERS["categories"] == ["電影", "OVA", "雙語", "泡麵番", "真人演出"]
print("AniGamer scraper tests passed")
