// 全站榜单（List 仓库版）· fw/rex 聚合模块
// 数据源： MakkaPakka518/List 仓库 data/*-hot.json（GitHub Actions 每日抓取提交）
// 使用：在 Forward 里添加本文件的地址即可。5 个子模块：骨朵/豆瓣/芒果TV/各平台剧场/热门番剧
WidgetMetadata = {
  id: "makka.list.aggregator",
  title: "全站榜单 (List)",
  version: "1.0.0",
  requiredVersion: "0.0.1",
  description: "骨朵/豆瓣/芒果TV/各平台剧场/热门番剧 五源榜单（GitHub Actions 每日抓取）",
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
