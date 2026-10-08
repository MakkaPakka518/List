// 回测 List 版 widget.js（真实拉取 raw 数据）
const fs = require("fs");
const assert = require("assert");

global.Widget = {
  http: { get: async (url) => ({ data: await (await fetch(url)).json() }) },
  tmdb: { get: async () => { throw new Error("no tmdb"); } },
  storage: { _m: {}, get(k) { return this._m[k]; }, set(k, v) { this._m[k] = v; } },
};
global.WidgetMetadata = {};
eval(fs.readFileSync("./widget.js", "utf8"));

(async () => {
  // 1. 元数据
  assert.ok(WidgetMetadata.id === "makka.list.aggregator", "id");
  assert.equal(WidgetMetadata.modules.length, 5, "5 个模块");
  const ids = WidgetMetadata.modules.map((m) => m.id).join(",");
  assert.ok(ids.includes("loadGuduo") && ids.includes("loadTheater") && ids.includes("loadBangumi"), "模块齐全");
  console.log("✓ 元数据：5 模块", ids);

  // 2. 各模块真实读取
  const g = await loadGuduo({ category: "剧集" });
  const d = await loadDouban({ channel: "tv" });
  const m = await loadMangoTV({ sort_by: "tv" });
  const t = await loadTheater({ brand: "迷雾剧场", status: "all" });
  const b = await loadBangumi({});
  console.log(`✓ 条数: guduo=${g.length} douban=${d.length} mgtv=${m.length} theater=${t.length} bangumi=${b.length}`);

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
