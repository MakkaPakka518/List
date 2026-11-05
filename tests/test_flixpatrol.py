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

calls = []
def fake_tmdb(path, params):
    calls.append((path, params))
    if path == "search/movie":
        if params["query"] == "The Day After Tomorrow":
            return {"results": [
                {"id": 435, "title": "The Day After Tomorrow", "release_date": "2004-05-26", "popularity": 50},
                {"id": 1615365, "title": "The Day After Tomorrow", "release_date": "2026-01-01", "popularity": 500},
            ]}
        return {"results": [
            {"id": 123, "title": "Test Movie", "release_date": "2026-01-02", "popularity": 10},
            {"id": 999, "title": "Test Movie", "release_date": "2000-01-02", "popularity": 999},
        ]}
    if path == "search/tv":
        return {"results": [
            {"id": 222, "name": "Lupin", "first_air_date": "2021-01-08", "popularity": 10},
            {"id": 111, "name": "Lupin", "first_air_date": "2007-01-01", "popularity": 999},
        ]}
    media_type, tmdb_id = path.split("/")
    assert media_type in ("movie", "tv")
    return {
        "id": int(tmdb_id),
        "poster_path": f"/{tmdb_id}.jpg",
        "backdrop_path": f"/{tmdb_id}-back.jpg",
        "release_date": "2026-01-02" if media_type == "movie" else None,
        "first_air_date": "2021-01-08" if media_type == "tv" else None,
        "vote_average": 8.2,
        "translations": {"translations": [
            {"iso_639_1": "zh", "iso_3166_1": "CN", "data": {"title": "简体电影", "name": "简体剧名", "overview": "简体简介"}},
            {"iso_639_1": "zh", "iso_3166_1": "TW", "data": {"title": "繁體電影", "name": "繁體劇名", "overview": "繁體簡介"}},
            {"iso_639_1": "en", "iso_3166_1": "US", "data": {"title": "English Movie", "name": "English Show", "overview": "English overview"}},
        ]},
        "images": {
            "posters": [
                {"file_path": "/zh-small.jpg", "iso_639_1": "zh", "width": 500, "height": 750},
                {"file_path": "/zh-4k.jpg", "iso_639_1": "zh", "width": 2160, "height": 3240},
                {"file_path": "/clean-4k.jpg", "iso_639_1": None, "width": 2000, "height": 3000},
                {"file_path": "/en-4k.jpg", "iso_639_1": "en", "width": 3000, "height": 4500},
            ],
            "backdrops": [{"file_path": "/back-4k.jpg", "iso_639_1": None, "width": 3840, "height": 2160}],
        },
    }

MODULE.tmdb_get = fake_tmdb
matched = MODULE.match_tmdb(movie, {("movie", 123): 0})
assert calls[0][0] == "search/movie"
assert calls[0][1]["language"] == "en-US"
assert matched["tmdbId"] == 123
assert matched["posterPath"] == "/clean-4k.jpg"
assert matched["backdropPath"] == "/back-4k.jpg"
assert matched["tmdbTitle"] == "简体电影"
assert matched["description"] == "简体简介"

lupin = {"title": "Lupin", "sourcePath": "/title/lupin/", "mediaType": "tv"}
lupin_match = MODULE.match_tmdb(lupin, {("tv", 222): 0})
assert lupin_match["tmdbId"] == 222
assert lupin_match["releaseDate"] == "2021-01-08"
assert lupin_match["tmdbTitle"] == "简体剧名"

day_after = {"title": "The Day After Tomorrow", "sourcePath": "/title/the-day-after-tomorrow/", "mediaType": "movie"}
day_after_match = MODULE.match_tmdb(day_after, {("movie", 1615365): 0})
assert day_after_match["tmdbId"] == 435
print("FlixPatrol parser tests passed")
