WidgetMetadata = {
  id: "makka.daily.stamp",
  title: "每日一言邮票",
  version: "1.0.0",
  requiredVersion: "0.0.1",
  description: "每日三句诗词、文学与哲思，搭配 TMDB 电影图片",
  author: "𝙈𝙖𝙠𝙠𝙖𝙋𝙖𝙠𝙠𝙖",
  site: "https://github.com/MakkaPakka518/List",
  detailCacheDuration: 3600,
  modules: [{
    id: "loadDailyStamps",
    title: "每日三枚",
    functionName: "loadDailyStamps",
    cacheDuration: 60,
    params: [{ name: "language", title: "配图语言", type: "language", value: "zh-CN" }],
  }],
};

async function loadDailyStamps(params = {}) {
  try {
    const language = params.language || "zh-CN";
    const day = new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10);
    const key = "daily-stamp.v1." + language;
    const stored = await Widget.storage.get(key);
    let cached;
    try { cached = stored ? JSON.parse(stored) : null; } catch (_) { cached = null; }
    if (cached && cached.day === day && Array.isArray(cached.items) && cached.items.length === 3) return cached.items;

    const response = await Widget.tmdb.get("trending/movie/week", { params: { language } });
    const movies = (response.results || []).filter(movie =>
      Number.isSafeInteger(movie.id) && movie.id > 0 && movie.title && movie.backdrop_path && !movie.adult
    ).slice(0, 3);
    if (movies.length !== 3) throw new Error("TMDB 未提供三张电影配图");

    const items = [];
    const categories = ["i", "d", "k"];
    for (let index = 0; index < 3; index++) {
      const movie = movies[index];
      let image = movie.backdrop_path;
      let ratio = 16 / 9;
      try {
        const images = await Widget.tmdb.get("movie/" + movie.id + "/images", { params: { include_image_language: "null,zh,en" } });
        const landscape = (images.backdrops || []).concat(images.posters || []).find(asset =>
          asset.file_path && Math.abs(asset.aspect_ratio - 4 / 3) < 0.04
        );
        if (landscape) { image = landscape.file_path; ratio = landscape.aspect_ratio; }
      } catch (error) {
        console.warn("[loadDailyStamps] 使用电影默认横图:", error.message || error);
      }
      const res = await Widget.http.get("https://international.v1.hitokoto.cn/", {
        params: { c: categories[index], min_length: 12, max_length: 32, encode: "json" },
      });
      const quote = typeof res.data === "string" ? JSON.parse(res.data) : res.data;
      if (!quote || typeof quote.hitokoto !== "string" || !quote.hitokoto.trim()) throw new Error("一言接口未返回短句");
      const text = quote.hitokoto.trim();
      if (Array.from(text).length > 32) throw new Error("一言短句超过 32 字");
      const id = "daily-stamp:movie:" + movie.id;
      items.push({
        id, link: id, type: "url", mediaType: "movie", title: movie.title,
        posterPath: image, backdropPath: image, detailPoster: movie.poster_path || "", coverRatio: ratio,
        releaseDate: movie.release_date || "", rating: movie.vote_average,
        description: JSON.stringify({
          text, author: quote.from_who || "", source: quote.from || "", date: day,
        }),
      });
    }
    await Widget.storage.set(key, JSON.stringify({ day, items }));
    return items;
  } catch (error) {
    console.error("[loadDailyStamps] 加载失败:", error.message || error);
    throw error;
  }
}

async function loadDetail(link) {
  const match = typeof link === "string" && /^daily-stamp:movie:([1-9]\d*)$/.exec(link);
  if (!match || !Number.isSafeInteger(Number(match[1]))) return null;
  try {
    const movie = await Widget.tmdb.get("movie/" + match[1], { params: { language: "zh-CN" } });
    if (!movie || movie.id !== Number(match[1])) throw new Error("电影详情身份不匹配");
    return {
      id: movie.id, type: "tmdb", mediaType: "movie", title: movie.title,
      description: movie.overview || "", posterPath: movie.poster_path || "",
      backdropPath: movie.backdrop_path || "", releaseDate: movie.release_date || "",
      rating: movie.vote_average,
    };
  } catch (error) {
    console.error("[loadDetail] 加载失败:", error.message || error);
    throw error;
  }
}
