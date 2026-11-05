// 全站榜单（List 仓库版）· fw/rex 聚合模块
// 数据源： MakkaPakka518/List 仓库 data/*-hot.json（GitHub Actions 每日抓取提交）
// 使用：在 Forward 里添加本文件的地址即可。6 个子模块：骨朵/豆瓣/芒果TV/各平台剧场/热门番剧/FlixPatrol
WidgetMetadata = {
  id: "makka.list.aggregator",
  title: "全站榜单 (List)",
  version: "1.1.0",
  requiredVersion: "0.0.1",
  description: "骨朵/豆瓣/芒果TV/各平台剧场/热门番剧/FlixPatrol 全球流媒体榜单",
  author: "𝙈𝙖𝙠𝙠𝙖𝙋𝙖𝙠𝙠𝙖",
  site: "https://t.me/MakkaPakkaOvO",
  globalParams: [
    { name: "baseUrl", title: "数据地址", type: "input", placeholders: [{ title: "List 仓库数据接口", value: "https://raw.githubusercontent.com/MakkaPakka518/List/main/data" }] },
  ],
  modules: [
    {
      id: "loadGuduo",
      title: "骨朵熱度",
      functionName: "loadGuduo",
      cacheDuration: 3600,
      params: [
        { name: "category", title: "分類", type: "enumeration", value: "剧集", enumOptions: [{ title: "劇集", value: "剧集" }, { title: "綜藝", value: "综艺" }, { title: "動漫", value: "动漫" }, { title: "電影", value: "电影" }] },
        { name: "sort", title: "排序方式", type: "enumeration", value: "default", enumOptions: [{ title: "默認原序", value: "default" }, { title: "最近更新", value: "latestUpdate" }, { title: "最近發佈", value: "latestRelease" }, { title: "熱度最高", value: "hottest" }, { title: "高分優先", value: "highestRating" }] },
        { name: "page", title: "页码", type: "page", startPage: 1 },
      ],
    },
    {
      id: "loadDouban",
      title: "豆瓣熱榜",
      functionName: "loadDouban",
      cacheDuration: 3600,
      params: [
        { name: "channel", title: "榜單分類", type: "enumeration", value: "tv", enumOptions: [{ title: "全部劇集", value: "tv" }, { title: "大陸劇集", value: "tv_domestic" }, { title: "歐美劇集", value: "tv_american" }, { title: "日本劇集", value: "tv_japanese" }, { title: "南韓劇集", value: "tv_korean" }, { title: "動漫番劇", value: "tv_animation" }, { title: "紀錄片", value: "tv_documentary" }, { title: "大陸綜藝", value: "show_domestic" }, { title: "國外綜藝", value: "show_foreign" }] },
        { name: "sort", title: "排序方式", type: "enumeration", value: "default", enumOptions: [{ title: "默認原序", value: "default" }, { title: "最近更新", value: "latestUpdate" }, { title: "最近發佈", value: "latestRelease" }, { title: "熱度最高", value: "hottest" }, { title: "高分優先", value: "highestRating" }] },
        { name: "page", title: "页码", type: "page", startPage: 1 },
      ],
    },
    {
      id: "loadMangoTV",
      title: "芒果TV熱榜",
      functionName: "loadMangoTV",
      cacheDuration: 3600,
      params: [
        { name: "sort_by", title: "類型", type: "enumeration", value: "tv", enumOptions: [{ title: "全部劇集", value: "tv" }, { title: "王牌綜藝", value: "show" }] },
        { name: "sort", title: "排序方式", type: "enumeration", value: "default", enumOptions: [{ title: "默認原序", value: "default" }, { title: "最近更新", value: "latestUpdate" }, { title: "最近發佈", value: "latestRelease" }, { title: "熱度最高", value: "hottest" }, { title: "高分優先", value: "highestRating" }] },
        { name: "page", title: "页码", type: "page", startPage: 1 },
      ],
    },
    {
      id: "loadTheater",
      title: "各平臺劇場",
      functionName: "loadTheater",
      cacheDuration: 3600,
      params: [
        { name: "brand", title: "劇場品牌", type: "enumeration", value: "迷雾剧场", enumOptions: [{ title: "迷霧劇場", value: "迷雾剧场" }, { title: "白夜劇場", value: "白夜剧场" }, { title: "X 劇場", value: "X剧场" }, { title: "瑪卡的片單", value: "玛卡巴卡的悬疑剧" }, { title: "橫屏短劇", value: "横屏短剧" }, { title: "生花劇場", value: "生花剧场" }, { title: "大家劇場", value: "大家剧场" }, { title: "小逗劇場", value: "小逗剧场" }, { title: "十分劇場", value: "十分剧场" }, { title: "板凳單元", value: "板凳单元" }, { title: "螢火單元", value: "萤火单元" }, { title: "正午陽光", value: "正午阳光" }, { title: "戀戀劇場", value: "恋恋剧场" }, { title: "懸疑劇場", value: "悬疑剧场" }, { title: "微塵劇場", value: "微尘剧场" }] },
        { name: "status", title: "播出狀態", type: "enumeration", value: "all", enumOptions: [{ title: "全部", value: "all" }, { title: "已開播", value: "aired" }, { title: "即將推出", value: "upcoming" }] },
        { name: "sort", title: "排序方式", type: "enumeration", value: "default", enumOptions: [{ title: "默認原序", value: "default" }, { title: "最近更新", value: "latestUpdate" }, { title: "最近發佈", value: "latestRelease" }, { title: "熱度最高", value: "hottest" }, { title: "高分優先", value: "highestRating" }] },
        { name: "page", title: "页码", type: "page", startPage: 1 },
      ],
    },
    {
      id: "loadBangumi",
      title: "熱門番劇",
      functionName: "loadBangumi",
      cacheDuration: 3600,
      params: [
        { name: "sort", title: "排序方式", type: "enumeration", value: "default", enumOptions: [{ title: "默認原序", value: "default" }, { title: "最近更新", value: "latestUpdate" }, { title: "最近發佈", value: "latestRelease" }, { title: "熱度最高", value: "hottest" }, { title: "高分優先", value: "highestRating" }] },
        { name: "page", title: "页码", type: "page", startPage: 1 },
      ],
    },
    {
      id: "loadFlixPatrol",
      title: "FlixPatrol 全球榜",
      functionName: "loadFlixPatrol",
      cacheDuration: 3600,
      params: [
        {
          name: "country",
          title: "国家/地区",
          type: "input",
          value: "united-states",
          placeholders: [
            { title: "全球", value: "world" }, { title: "美国", value: "united-states" },
            { title: "香港", value: "hong-kong" }, { title: "台湾", value: "taiwan" },
            { title: "新加坡", value: "singapore" }, { title: "马来西亚", value: "malaysia" },
            { title: "英国", value: "united-kingdom" }, { title: "西班牙", value: "spain" },
            { title: "尼日利亚", value: "nigeria" }, { title: "加拿大", value: "canada" },
            { title: "韩国", value: "south-korea" }, { title: "日本", value: "japan" },
            { title: "澳大利亚", value: "australia" }, { title: "印度", value: "india" },
            { title: "德国", value: "germany" }, { title: "法国", value: "france" },
            { title: "巴西", value: "brazil" }, { title: "墨西哥", value: "mexico" },
          ],
        },
        {
          name: "platform",
          title: "平台",
          type: "enumeration",
          value: "netflix",
          enumOptions: [
            { title: "全部平台", value: "all" }, { title: "Netflix", value: "netflix" },
            { title: "Disney+", value: "disney" }, { title: "Apple TV", value: "apple-tv" },
            { title: "Amazon Prime", value: "amazon-prime" }, { title: "HBO Max", value: "hbo-max" },
            { title: "Paramount+", value: "paramount-plus" }, { title: "Hulu", value: "hulu" },
            { title: "Peacock", value: "peacock" }, { title: "Apple TV Store", value: "itunes" },
            { title: "自定义平台 slug", value: "custom" },
          ],
        },
        { name: "platformSlug", title: "平台 slug", type: "input", value: "", belongTo: { paramName: "platform", value: ["custom"] } },
        {
          name: "chart",
          title: "榜单",
          type: "enumeration",
          value: "all",
          enumOptions: [
            { title: "电影 + 剧集", value: "all" }, { title: "电影 TOP 10", value: "movies" },
            { title: "剧集 TOP 10", value: "tv" }, { title: "综合 TOP 10", value: "overall" },
            { title: "儿童电影", value: "kids_movies" }, { title: "儿童剧集", value: "kids_tv" },
            { title: "Amazon Channels", value: "amazon_channels" },
          ],
        },
        { name: "count", title: "数量", type: "count", value: "20" },
      ],
    },
  ],
};

const BASE = "https://raw.githubusercontent.com/MakkaPakka518/List/main/data";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
const UA_HEADERS = { "User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9" };

function toVideo(it) {
  return {
    id: Number(it.tmdbId || it.id) || 0,
    type: "tmdb",
    mediaType: it.mediaType || (it.type === "movie" ? "movie" : "tv"),
    title: it.title || it.tmdbTitle || "",
    posterPath: it.posterPath,
    backdropPath: it.backdropPath,
    rating: it.rating,
    releaseDate: it.releaseDate,
    description: it.description || it.overview || "",
  };
}

// 排序：默认原序 / 最近更新(lastUpdateDate) / 最近发布(releaseDate) / 热度(popularity) / 高分(rating)
function sortItems(list, sort) {
  const s = sort || "default";
  const arr = (list || []).slice();
  if (s === "default") return arr;
  const key = s === "latestUpdate" ? "lastUpdateDate"
    : s === "latestRelease" ? "releaseDate"
    : s === "hottest" ? "popularity" : "rating";
  if (key === "lastUpdateDate" || key === "releaseDate") {
    arr.sort((a, b) => String(b[key] || "").localeCompare(String(a[key] || "")));
  } else {
    arr.sort((a, b) => (Number(b[key]) || 0) - (Number(a[key]) || 0));
  }
  return arr;
}

function paginate(list, page, size = 24) {
  const p = Number(page || 1);
  const start = (p - 1) * size;
  return (list || []).slice(start, start + size).map(toVideo);
}

async function loadGuduo(params = {}) {
  const res = await Widget.http.get((params.baseUrl || BASE) + "/guduo-hot.json", { headers: UA_HEADERS });
  const list = (res.data && res.data.categories && res.data.categories[params.category || "剧集"]) || [];
  return paginate(sortItems(list, params.sort), params.page);
}

async function loadDouban(params = {}) {
  const res = await Widget.http.get((params.baseUrl || BASE) + "/douban-hot.json", { headers: UA_HEADERS });
  const list = (res.data && res.data[params.channel || "tv"]) || [];
  return paginate(sortItems(list, params.sort), params.page);
}

async function loadMangoTV(params = {}) {
  const res = await Widget.http.get((params.baseUrl || BASE) + "/mgtv-hot.json", { headers: UA_HEADERS });
  const list = (res.data && res.data[params.sort_by || "tv"]) || [];
  return paginate(sortItems(list, params.sort), params.page);
}

async function loadTheater(params = {}) {
  const res = await Widget.http.get((params.baseUrl || BASE) + "/theater-data.json", { headers: UA_HEADERS });
  const brand = (res.data || {})[params.brand || "迷雾剧场"];
  if (!brand) return [];
  let list = [];
  if (params.status === "aired") list = brand.aired || [];
  else if (params.status === "upcoming") list = brand.upcoming || [];
  else list = [...(brand.upcoming || []), ...(brand.aired || [])];
  return paginate(sortItems(list, params.sort), params.page);
}

async function loadBangumi(params = {}) {
  const res = await Widget.http.get((params.baseUrl || BASE) + "/bangumi-hot.json", { headers: UA_HEADERS });
  const list = (res.data && res.data.hot_anime) || [];
  return paginate(sortItems(list, params.sort), params.page);
}

const FLIX_ORIGIN = "https://flixpatrol.com";
const FLIX_TMDB_CACHE = {};
const FLIX_DETAIL_CACHE = {};

function flixBody(response) {
  let body = response && response.data !== undefined ? response.data : response;
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch (error) { return null; }
  }
  return body && typeof body === "object" ? body : null;
}

function flixSlug(value, fallback) {
  const slug = String(value || fallback || "").trim().toLowerCase();
  return /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug) ? slug : "";
}

function flixCount(value) {
  const count = Number(value || 20);
  return Number.isFinite(count) ? Math.min(40, Math.max(1, Math.floor(count))) : 20;
}

function flixTitleKey(value) {
  return String(value || "").toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "");
}

function flixYear(item) {
  const match = String(item && item.sourcePath || "").match(/-(19\d{2}|20\d{2})\/$/);
  return match ? match[1] : "";
}

function flixMediaType(item, chart) {
  if (item && (item.mediaType === "movie" || item.mediaType === "tv")) return item.mediaType;
  if (chart === "movies" || chart === "kids_movies") return "movie";
  if (chart === "tv" || chart === "kids_tv") return "tv";
  return "";
}

function flixSourceUrl(item) {
  const path = String(item && item.sourcePath || "");
  return /^\/title\/[a-z0-9][a-z0-9-%]*\/$/.test(path) ? FLIX_ORIGIN + path : "";
}

async function flixFindTmdb(item, chart) {
  const expectedType = flixMediaType(item, chart);
  const cacheKey = `${expectedType || "multi"}:${flixTitleKey(item.title)}:${flixYear(item)}`;
  if (Object.prototype.hasOwnProperty.call(FLIX_TMDB_CACHE, cacheKey)) return FLIX_TMDB_CACHE[cacheKey];
  try {
    const response = await Widget.tmdb.get(expectedType ? `search/${expectedType}` : "search/multi", {
      params: { query: item.title, language: "en-US", include_adult: false },
    });
    const target = flixTitleKey(item.title);
    const year = flixYear(item);
    const matches = {};
    for (const candidate of response && response.results || []) {
      const mediaType = expectedType || candidate.media_type;
      const title = candidate.title || candidate.name || candidate.original_title || candidate.original_name || "";
      if (!candidate.id || !["movie", "tv"].includes(mediaType) || flixTitleKey(title) !== target) continue;
      const date = candidate.release_date || candidate.first_air_date || "";
      if (year && !date.startsWith(year)) continue;
      matches[candidate.id] = { ...candidate, media_type: mediaType };
    }
    const candidates = Object.values(matches);
    const match = candidates.length === 1 ? candidates[0] : null;
    FLIX_TMDB_CACHE[cacheKey] = match;
    return match;
  } catch (error) {
    console.warn("[loadFlixPatrol] TMDB 匹配失败:", error.message || error);
    return null;
  }
}

function flixChartName(chart) {
  return ({ movies: "电影", tv: "剧集", overall: "综合", kids_movies: "儿童电影", kids_tv: "儿童剧集", amazon_channels: "Amazon Channels" })[chart] || chart;
}

function flixChartItems(platform, chart) {
  const charts = platform && platform.charts || {};
  if (chart === "all") {
    return [...(charts.movies || []).map((item) => ({ item, chart: "movies" })), ...(charts.tv || []).map((item) => ({ item, chart: "tv" }))];
  }
  return (charts[chart] || []).map((item) => ({ item, chart }));
}

async function flixVideo(entry, platformName, countryName, chartDate) {
  const item = entry.item;
  const description = [
    `#${item.rank}`, platformName, flixChartName(entry.chart), countryName, chartDate,
    item.movement ? `变化 ${item.movement}` : "", item.days ? `在榜 ${item.days}` : "",
  ].filter(Boolean).join(" · ");
  if (Number(item.tmdbId) > 0 && (item.mediaType === "movie" || item.mediaType === "tv")) {
    return {
      id: Number(item.tmdbId), type: "tmdb", mediaType: item.mediaType, title: item.title,
      description,
    };
  }
  const tmdb = await flixFindTmdb(item, entry.chart);
  if (tmdb) {
    return {
      id: Number(tmdb.id), type: "tmdb", mediaType: tmdb.media_type, title: item.title,
      description,
    };
  }
  const link = flixSourceUrl(item);
  if (!link) return null;
  const result = { id: link, type: "url", title: item.title, description: `${description} · 未匹配到 TMDB`, link };
  const mediaType = flixMediaType(item, entry.chart);
  if (mediaType) result.mediaType = mediaType;
  FLIX_DETAIL_CACHE[link] = result;
  return result;
}

async function loadFlixPatrol(params = {}) {
  try {
    const country = flixSlug(params.country, "united-states");
    const platformSlug = params.platform === "custom" ? flixSlug(params.platformSlug) : flixSlug(params.platform, "netflix");
    if (!country || (!platformSlug && params.platform !== "all")) return [];
    const response = await Widget.http.get(`${params.baseUrl || BASE}/flixpatrol/${country}.json`, { headers: UA_HEADERS });
    const body = flixBody(response);
    if (!body || body.schemaVersion !== 1 || !body.platforms) throw new Error("榜单 JSON 格式不正确");
    const chart = ["all", "movies", "tv", "overall", "kids_movies", "kids_tv", "amazon_channels"].includes(params.chart) ? params.chart : "all";
    let entries = [];
    if (params.platform === "all") {
      for (const slug of Object.keys(body.platforms)) {
        const platform = body.platforms[slug];
        entries.push(...flixChartItems(platform, chart).map((entry) => ({ ...entry, platformName: platform.name || slug })));
      }
    } else {
      const platform = body.platforms[platformSlug];
      if (!platform) return [];
      entries = flixChartItems(platform, chart).map((entry) => ({ ...entry, platformName: platform.name || platformSlug }));
    }
    entries = entries.slice(0, flixCount(params.count));
    const countryName = body.country && body.country.name || country;
    const videos = await Promise.all(entries.map((entry) => flixVideo(entry, entry.platformName, countryName, body.chartDate || "")));
    return videos.filter(Boolean);
  } catch (error) {
    console.error("[loadFlixPatrol] 失败:", error.message || error);
    throw error;
  }
}

async function loadDetail(link) {
  const value = String(link || "").trim();
  if (!/^https:\/\/flixpatrol\.com\/title\/[a-z0-9][a-z0-9-%]*\/$/.test(value)) return null;
  if (FLIX_DETAIL_CACHE[value]) return FLIX_DETAIL_CACHE[value];
  const slug = value.match(/\/title\/([^/]+)\//)[1].replace(/-19\d{2}$|-20\d{2}$/, "");
  return { id: value, type: "url", title: slug.split("-").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" "), description: "FlixPatrol 榜单条目；未匹配到 TMDB。", link: value };
}
