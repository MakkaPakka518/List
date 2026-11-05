import importlib.util
from pathlib import Path

from scrapling.parser import Selector


SCRIPT = Path(__file__).parents[1] / "scripts" / "update_flixpatrol.py"
SPEC = importlib.util.spec_from_file_location("update_flixpatrol", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

HTML = """
<html><body>
  <a href="/top10/netflix/united-states/2026-11-05/">United States</a>
  <a href="/top10/disney/united-states/2026-11-05/">United States</a>
  <h2 id="toc-netflix"><span></span><span>Netflix TOP 10 in the United States on November 5, 2026</span></h2>
  <div class="card -mx-content"><div><h3>TOP 10 Movies</h3></div><table class="card-table"><tr>
    <td>1.</td><td>+2</td><td><a href="/title/test-movie-2026/">Test Movie</a></td><td>3 d</td>
  </tr></table></div>
  <div class="card -mx-content"><div><h3>TOP 10 Overall</h3></div><table class="card-table"><tr>
    <td>1.</td><td>–</td><td><a href="/title/test-movie-2026/">Test Movie</a></td><td>3 d</td>
  </tr></table></div>
</body></html>
"""

page = Selector(HTML)
countries = MODULE.extract_countries(page)
assert countries == {"world": "Worldwide", "united-states": "United States"}

data = MODULE.parse_country_page(page, "united-states", "United States")
assert data["chartDate"] == "2026-11-05"
assert data["country"]["name"] == "United States"
movie = data["platforms"]["netflix"]["charts"]["movies"][0]
assert movie == {
    "rank": 1,
    "title": "Test Movie",
    "sourcePath": "/title/test-movie-2026/",
    "movement": "+2",
    "days": "3 d",
    "mediaType": "movie",
}
assert data["platforms"]["netflix"]["charts"]["overall"][0]["mediaType"] == "movie"
print("FlixPatrol parser tests passed")
