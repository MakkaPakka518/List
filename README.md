# 全站榜单 (List)

一个用 **GitHub Actions 每日定时抓取**榜单数据并提交到仓库的工程，产出多类榜单 JSON，另附可直接加载的 fw/rex 聚合模块。

> 本仓库只做数据抓取与聚合模块，**脚本（`scripts/`）未做改动**；`widget.js` 与 `README.md` 为新增。

## 抓取的 5 个源
| 源 | 内容 | 数据文件 |
|---|---|---|
| 骨朵热度 | 剧集 / 综艺 / 动漫 / 电影 | `data/guduo-hot.json` |
| 豆瓣热榜 | 剧集（大陆/欧美/日/韩/动漫/纪录）+ 综艺 | `data/douban-hot.json` |
| 芒果TV | 剧集 + 王牌综艺 | `data/mgtv-hot.json` |
| 各平台剧场 | 迷雾/白夜/X/恋恋… 15 个剧场（已开播/即将） | `data/theater-data.json` |
| 热门番剧 | bgm.tv 排名 + TMDB 匹配 | `data/bangumi-hot.json` |
| FlixPatrol | 美国、香港、台湾、新加坡、马来西亚、英国、西班牙、尼日利亚、加拿大、韩国、日本的流媒体每日 TOP 10 | `data/flixpatrol/*.json` |

每个条目都经过 TMDB 匹配，自带 `title / rating / posterPath / mediaType / releaseDate` 等完整字段。

FlixPatrol 数据按国家拆分，`data/flixpatrol/index.json` 提供国家与平台索引。榜单代表 FlixPatrol 已发布的最新日榜，不是未来预测；rex 根据条目的 TMDB ID 和客户端语言加载海报与详情。

`update-flixpatrol.yml` 运行 `scripts/update_flixpatrol.py` 时必须传入仓库 Secret `TMDB_API_KEY`。脚本用 FlixPatrol 的英文源标题、媒体类型和 URL 年份严格匹配 TMDB，只保存 `tmdbId` 与 `mediaType`；海报和本地化元数据由 rex 按客户端语言加载。

## 数据更新
`.github/workflows/` 下 5 个工作流，各自按 cron 定时运行对应 `scripts/update_*.py`，抓取后**提交更新**到 `data/*.json`。

## widget.js（fw/rex 聚合模块）
`widget.js` 是一个可直接加载的 ForwardWidget 模块，直接消费仓库内的榜单 JSON：

- **6 个子模块**：`loadGuduo` / `loadDouban` / `loadMangoTV` / `loadTheater` / `loadBangumi` / `loadFlixPatrol`
- FlixPatrol 子模块可选择国家/地区、平台和电影/剧集榜；抓取任务按 TMDB 搜索相关度与热度顺序匹配，再用周趋势/热门池、英文标题、媒体类型和年份校验，保存 TMDB ID、原生简介与海报
- 标题和简介按简体中文 → 繁体中文 → 原始语言/原始名称 → 英文的顺序回退
- 海报优先使用 TMDB 无文字（无语言标记）海报，其次中文、英文和其他海报；每组候选都选择分辨率最高的原图
- 每个模块带**排序方式**（默认原序 / 最近更新 / 最近发布 / 热度最高 / 高分优先）与**分页**
- 条目为标准 `VideoItem`（`type:"tmdb"` + 数字 `id` + `mediaType`），点击走播放器内置 TMDB 详情页
- 数据源默认指向本仓库 raw 地址，也可在模块 `globalParams.baseUrl` 里改

**使用方法**：在 Forward 里添加 `widget.js` 的文件地址即可，无需改脚本。

模块地址（raw）：
```
https://raw.githubusercontent.com/MakkaPakka518/List/main/widget.js
```

## 本地验证
```bash
node test-widget.js   # 用真实 raw 数据回测 6 模块读取/映射/排序/分页
```

## 目录
```
.github/workflows/   5 个抓取工作流
scripts/             抓取脚本（未改动）
data/                抓取结果 JSON（Actions 自动提交）
widget.js            聚合模块（新增）
README.md            本说明（新增）
```
