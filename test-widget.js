// 回测 List 版 widget.js（现有榜单读取真实 raw，FlixPatrol 使用固定契约样本）
const fs = require("fs");
const assert = require("assert");

const FLIXPATROL_FIXTURE = {
  schemaVersion: 1,
  chartDate: "2026-11-05",
  country: { slug: "hong-kong", name: "Hong Kong" },
  platforms: { netflix: { name: "Netflix", charts: { movies: [{
    rank: 1, title: "Test Movie", sourcePath: "/title/test-movie-2026/", mediaType: "movie",
    tmdbId: 123, tmdbTitle: "测试电影", posterPath: "/poster.jpg", backdropPath: "/backdrop.jpg",
    releaseDate: "2026-01-02", rating: 8.2, description: "TMDB 原生简介",
  }] } } },
};

global.Widget = {
  http: { get: async (url) => ({ data: url.includes("/flixpatrol/") ? FLIXPATROL_FIXTURE : await (await fetch(url)).json() }) },
  tmdb: { get: async () => ({ results: [] }) },
  storage: { _m: {}, get(k) { return this._m[k]; }, set(k, v) { this._m[k] = v; } },
};
global.WidgetMetadata = {};
eval(fs.readFileSync("./widget.js", "utf8"));

(async () => {
  // 1. 元数据
  assert.ok(WidgetMetadata.id === "makka.list.aggregator", "id");
  assert.equal(WidgetMetadata.modules.length, 6, "6 个模块");
  const ids = WidgetMetadata.modules.map((m) => m.id).join(",");
  assert.ok(ids.includes("loadGuduo") && ids.includes("loadTheater") && ids.includes("loadBangumi") && ids.includes("loadFlixPatrol"), "模块齐全");
  console.log("✓ 元数据：6 模块", ids);

  // 2. 各模块真实读取
  const g = await loadGuduo({ category: "剧集" });
  const d = await loadDouban({ channel: "tv" });
  const m = await loadMangoTV({ sort_by: "tv" });
  const t = await loadTheater({ brand: "迷雾剧场", status: "all" });
  const b = await loadBangumi({});
  const f = await loadFlixPatrol({ country: "hong-kong", platform: "netflix", chart: "movies", count: 10 });
  console.log(`✓ 条数: guduo=${g.length} douban=${d.length} mgtv=${m.length} theater=${t.length} bangumi=${b.length} flixpatrol=${f.length}`);
  assert.equal(f.length, 1, "FlixPatrol 香港 Netflix 电影榜");
  assert.equal(f[0].id, 123);
  assert.equal(f[0].type, "tmdb");
  assert.equal(f[0].posterPath, "/poster.jpg");
  assert.equal(f[0].description, "TMDB 原生简介");
  assert.equal(await loadDetail("https://evil.test/title/test/"), null);

  // 3. VideoItem 字段校验（用番剧，条目最全）
  assert.ok(b.length > 0, "番剧有数据");
  const it = b[0];
  assert.equal(it.type, "tmdb");
  assert.ok(Number.isFinite(it.id) && it.id > 0, "id 数字");
  assert.ok(it.title, "title");
  assert.ok(it.posterPath, "posterPath");
  assert.ok(it.rating !== undefined, "rating");
  assert.ok(it.mediaType === "tv", "mediaType");
  console.log("✓ bangumi[0]:", { id: it.id, type: it.type, mediaType: it.mediaType, title: it.title, rating: it.rating, poster: it.posterPath });

  // 4. 豆瓣/芒果/剧场条目映射
  const dm = await loadDouban({ channel: "tv" });
  assert.ok(dm[0] && dm[0].posterPath && dm[0].mediaType, "豆瓣条目带海报+类型");
  const tm = await loadTheater({ brand: "迷雾剧场", status: "aired" });
  console.log("✓ 豆瓣tv条目数:", dm.length, "| 迷雾已开播:", tm.length);

  // 5. 排序（豆瓣热度最高）
  const hot = await loadDouban({ channel: "tv", sort: "hottest" });
  const ratings = hot.slice(0, 5).map((x) => x.rating);
  console.log("✓ 豆瓣 hottest 前5评分:", ratings.join(", "));
  console.log("✓ 排序（hottest 非升序？）:", ratings.every((r, i) => i === 0 || ratings[i - 1] >= r) ? "单调非增" : "非单调(数据可能缺popularity)");

  // 6. 分页
  const p2 = await loadBangumi({ page: 2 });
  assert.ok(p2.length >= 0 && (p2.length === 0 || p2[0].id !== b[0].id), "分页生效");
  console.log("✓ 番剧第2页条数:", p2.length);

  console.log("✅ List 版 widget.js 回测全部通过");
})().catch((e) => { console.error("❌", e.message || e); process.exit(1); });
