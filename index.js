const axios = require('axios');
const fs = require('fs');
const path = require('path');

// 你的 TMDB API Key（将在 GitHub Secrets 中配置，防止泄露）
const TMDB_API_KEY = process.env.TMDB_API_KEY; 

// 国内精品剧场收录名单 (你可以随时在代码里增删)
const THEATERS = {
    "x_theater": [
        "漫长的季节", "繁城之下", "黑土无言", "欢颜"
    ],
    "light_on": [
        "隐秘的角落", "沉默的真相", "平原上的摩西", "回来的女儿", "不可告人", "交错的场景", "错位", "三大队"
    ],
    "white_night": [
        "白夜追凶", "新生", "微暗之火"
    ]
};

// 基础 Axios 实例
const tmdbAPI = axios.create({
    baseURL: 'https://api.themoviedb.org/3',
    params: {
        api_key: TMDB_API_KEY,
        language: 'zh-CN'
    }
});

// 搜索 TMDB 获取详细信息
async function fetchMovieData(title) {
    try {
        console.log(`正在搜索: ${title}`);
        const response = await tmdbAPI.get('/search/tv', {
            params: { query: title, page: 1 }
        });
        
        if (response.data.results && response.data.results.length > 0) {
            const item = response.data.results[0];
            return {
                id: String(item.id),
                tmdbId: item.id,
                type: "tmdb",
                mediaType: "tv",
                title: item.name || item.title,
                releaseDate: item.first_air_date || "",
                posterPath: item.poster_path ? `https://image.tmdb.org/t/p/w500${item.poster_path}` : "",
                backdropPath: item.backdrop_path ? `https://image.tmdb.org/t/p/w780${item.backdrop_path}` : "",
                rating: item.vote_average ? parseFloat(item.vote_average.toFixed(1)) : 0,
                description: `${item.first_air_date || ""} · ⭐ ${item.vote_average || 0}\n${item.overview || "暂无简介"}`
            };
        }
        return null;
    } catch (error) {
        console.error(`获取 ${title} 失败:`, error.message);
        return null;
    }
}

// 主函数：遍历抓取并保存
async function main() {
    if (!TMDB_API_KEY) {
        console.error("❌ 找不到 TMDB_API_KEY，请检查环境变量设置！");
        process.exit(1);
    }

    const finalData = {};

    for (const [theaterKey, titles] of Object.entries(THEATERS)) {
        console.log(`\n========== 开始抓取 ${theaterKey} ==========`);
        const theaterItems = [];
        
        for (const title of titles) {
            const data = await fetchMovieData(title);
            if (data) {
                theaterItems.push(data);
            }
            // 延时 300 毫秒，防止请求过快被 TMDB 限制
            await new Promise(resolve => setTimeout(resolve, 300));
        }
        
        // 按照评分从高到低排序
        theaterItems.sort((a, b) => b.rating - a.rating);
        finalData[theaterKey] = theaterItems;
    }

    // 保存到当前目录的 data.json
    const outputPath = path.join(__dirname, 'theater_data.json');
    fs.writeFileSync(outputPath, JSON.stringify(finalData, null, 2), 'utf-8');
    console.log(`\n✅ 所有数据已成功保存至 ${outputPath}`);
}

main();
