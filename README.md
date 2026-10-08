# 全站榜单 (List)

一个用 **GitHub Actions 每日定时抓取**榜单数据并提交到仓库的工程，产出 5 类榜单 JSON，另附一个可直接加载的 **fw/rex 聚合模块 `widget.js`**。

> 本仓库只做数据抓取与聚合模块，**脚本（`scripts/`）未做改动**；`widget.js` 与 `README.md` 为新增。

## 抓取的 5 个源
| 源 | 内容 | 数据文件 |
|---|---|---|
| 骨朵热度 | 剧集 / 综艺 / 动漫 / 电影 | `data/guduo-hot.json` |
| 豆瓣热榜 | 剧集（大陆/欧美/日/韩/动漫/纪录）+ 综艺 | `data/douban-hot.json` |
| 芒果TV | 剧集 + 王牌综艺 | `data/mgtv-hot.json` |
| 各平台剧场 | 迷雾/白夜/X/恋恋… 15 个剧场（已开播/即将） | `data/theater-data.json` |
| 热门番剧 | bgm.tv 排名 + TMDB 匹配 | `data/bangumi-hot.json` |

每个条目都经过 TMDB 匹配，自带 `title / rating / posterPath / mediaType / releaseDate` 等完整字段。

## 数据更新
`.github/workflows/` 下 5 个工作流，各自按 cron 定时运行对应 `scripts/update_*.py`，抓取后**提交更新**到 `data/*.json`。

## widget.js（fw/rex 聚合模块）
`widget.js` 是一个可直接加载的 ForwardWidget 模块，直接消费上面 5 个 `data/*.json`：

- **5 个子模块**：`loadGuduo` / `loadDouban` / `loadMangoTV` / `loadTheater` / `loadBangumi`
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
node test-widget.js   # 用真实 raw 数据回测 5 模块读取/映射/排序/分页
```

## 目录
```
.github/workflows/   5 个抓取工作流
scripts/             抓取脚本（未改动）
data/                抓取结果 JSON（Actions 自动提交）
widget.js            聚合模块（新增）
README.md            本说明（新增）
```
