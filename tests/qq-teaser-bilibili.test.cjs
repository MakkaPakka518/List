const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const { test } = require('node:test');

function python(code) {
  const setup = `import importlib.util, json
spec = importlib.util.spec_from_file_location("m", "scripts/update_qq_teaser.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
`;
  return JSON.parse(execFileSync('python3', ['-c', setup + code], { cwd: path.resolve(__dirname, '..'), encoding: 'utf8' }));
}

test('Bilibili parsing uses the native short copy, not views or the long synopsis', () => {
  const [item, empty, japanese, invalid] = python(`
rank = {"season_id": 46585, "title": "灵笼 第二季", "copyright": "dujia", "badge": "出品", "new_ep": {"index_show": "全12话"}}
season = {"type": 4, "subtitle": "已观看4.0亿次", "share_sub_title": "幸存者能否重夺未来", "evaluate": "非常长的故事简介" * 20,
          "styles": ["原创", "战斗", "科幻", "热血"], "publish": {"pub_time": "2025-05-23 11:00:00"}}
print(json.dumps([m.parse_bili(rank, season), m.parse_bili(rank, dict(season, share_sub_title="")),
                 m.parse_bili(rank, dict(season, type=1)), m.parse_bili(dict(rank, season_id="bad/id"), season)]))
`);
  assert.equal(item.source, 'bili');
  assert.equal(item.cid, 'bili46585');
  assert.equal(item.teaser, '幸存者能否重夺未来');
  assert.equal(item.year, '2025');
  assert.equal(item.episodeText, '全12话');
  for (const tag of ['国漫', '动画', '科幻', '哔哩哔哩国创', '哔哩哔哩独播', '哔哩哔哩出品']) assert.ok(item.tags.includes(tag));
  assert.equal(empty.teaser, '', 'no copy is fabricated from views or the synopsis');
  assert.equal(japanese, null, 'a non-national season detail is rejected');
  assert.equal(invalid, null, 'invalid season identities are rejected');
});

test('the collector requests only season_type=4 and reads details once per season', () => {
  const result = python(`
from io import StringIO
from urllib.parse import urlparse, parse_qs
calls = []
def open_mock(request, timeout):
    parsed = urlparse(request.full_url); query = parse_qs(parsed.query)
    calls.append({"path": parsed.path, "params": query, "referer": request.get_header("Referer")})
    if parsed.path == "/pgc/web/rank/list":
        return StringIO(json.dumps({"code": 0, "result": {"list": [
            {"season_id": 11, "title": "国漫甲"}, {"season_id": 11, "title": "国漫甲"},
            {"season_id": 12, "title": "误入日漫"}, {"season_id": 0, "title": "无身份"}]}}))
    sid = query["season_id"][0]
    return StringIO(json.dumps({"code": 0, "data": {"type": 4 if sid == "11" else 1, "share_sub_title": "国漫短看点"}}))
m.urlopen = open_mock
items = m.collect_bili()
print(json.dumps({"items": items, "calls": calls}))
`);
  assert.deepEqual(result.items.map(item => item.cid), ['bili11']);
  assert.equal(result.items[0].teaser, '国漫短看点');
  assert.deepEqual(result.calls[0].params, { day: ['3'], season_type: ['4'] });
  assert.equal(result.calls[0].referer, 'https://www.bilibili.com/');
  assert.equal(result.calls.filter(call => call.path === '/pgc/view/web/season').length, 2);
});

test('Bilibili entries are collected once and added only to the anime channel', () => {
  const { channels, calls } = python(`
calls = []
m.collect_qq = lambda channel: []
m.collect_iq = lambda channel: []
m.collect_yk = lambda channel, category: []
def bili():
    calls.append("bili")
    return [m.parse_bili({"season_id": 1, "title": "国漫"}, {"type": 4, "share_sub_title": "短看点"})]
m.collect_bili = bili
print(json.dumps({"channels": m.collect(), "calls": calls}))
`);
  assert.deepEqual(calls, ['bili']);
  assert.equal(channels.anime[0].source, 'bili');
  for (const key of ['tv', 'movie', 'variety']) assert.deepEqual(channels[key], []);
});

test('TMDB matching cleans the title and rejects live action, foreign and artwork-less candidates', () => {
  const result = python(`
entry = m.parse_bili({"season_id": 1, "title": "测试动画 第二季 普通话版"}, {"type": 4, "share_sub_title": "看点"})
calls = []
def get_tv(path, params):
    calls.append({"path": path, "query": params["query"]})
    base = {"name": "测试动画", "origin_country": ["CN"], "genre_ids": [16], "poster_path": "/p.jpg"}
    return {"results": [dict(base, id=1, genre_ids=[18], popularity=10000), dict(base, id=2, poster_path=""),
                        dict(base, id=3, origin_country=["JP"]), dict(base, id=4)]}
m.tmdb_get = get_tv
m.tmdb_detail = lambda kind, ident: (["动画", "科幻"], "2026-11-24")
tv = m.resolve(entry, "tv")
tv_calls = list(calls); calls.clear()
def get_movie(path, params):
    calls.append(path)
    return {"results": [] if path == "search/tv" else [{"id": 5, "title": "测试动画", "origin_country": ["CN"], "genre_ids": [16], "poster_path": "/m.jpg"}]}
m.tmdb_get = get_movie
movie = m.resolve(entry, "tv")
print(json.dumps({"tv": tv, "tvCalls": tv_calls, "movie": movie, "movieCalls": calls}))
`);
  assert.equal(result.tv.tmdbId, 4);
  assert.equal(result.tv.mediaType, 'tv');
  assert.equal(result.tv.lastUpdateDate, '2026-11-24');
  assert.deepEqual(result.tvCalls, [{ path: 'search/tv', query: '测试动画' }]);
  assert.equal(result.movie.mediaType, 'movie', 'animated films are still allowed inside anime');
  assert.deepEqual(result.movieCalls, ['search/tv', 'search/movie']);
});

test('Bilibili short copy beats Youku genre words without displacing nonempty QQ/IQ copy', () => {
  const groups = python(`
import itertools
base = {"title": "同一动画", "mediaType": "tv", "tmdbId": 1, "posterPath": "/p.jpg"}
items = [dict(base, source="qq", cid="q", teaser="腾讯一句话", tags=["科幻"]),
         dict(base, source="iq", cid="i", teaser="爱奇艺一句话", tags=["冒险"]),
         dict(base, source="bili", cid="b", teaser="哔哩哔哩一句话", tags=["哔哩哔哩国创"]),
         dict(base, source="yk", cid="y", teaser="科幻 · 冒险", tags=["优酷独播"])]
groups = [items, [dict(item, teaser="") if item["source"] in ("qq", "iq") else item for item in items]]
print(json.dumps([[m.dedupe(list(order)) for order in itertools.permutations(group)] for group in groups]))
`);
  for (const [index, orders] of groups.entries()) {
    for (const entries of orders) {
      assert.equal(entries.length, 1);
      assert.equal(entries[0].source, index === 0 ? 'qq' : 'bili');
      assert.deepEqual(entries[0].alsoOn, ['bili', 'iq', 'qq', 'yk']);
      assert.ok(entries[0].tags.includes('优酷独播'));
      assert.ok(entries[0].tags.includes('哔哩哔哩国创'));
    }
  }
});

test('Bilibili nonzero API codes fail instead of masquerading as a successful empty list', () => {
  const result = python(`
from io import StringIO
m.urlopen = lambda *args, **kwargs: StringIO(json.dumps({"code": -412, "message": "request blocked"}))
try:
    m.collect_bili()
    outcome = "unexpected success"
except RuntimeError:
    outcome = "rejected"
print(json.dumps(outcome))
`);
  assert.equal(result, 'rejected');
});
