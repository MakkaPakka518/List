# 全站榜单 (List)

一个用 **GitHub Actions 每日定时抓取**榜单数据并提交到仓库的工程，产出多类榜单 JSON，另附可直接加载的 fw/rex 聚合模块。

> 本仓库只做数据抓取与聚合模块，**脚本（`scripts/`）未做改动**；`widget.js` 与 `README.md` 为新增。

## 抓取的 5 个源
| 源 | 内容 | 数据文件 |
|---|---|---|
| 骨朵热度 | 剧集 / 综艺 / 动漫 / 电影 | `data/guduo-hot.json` |
| 豆瓣热榜 | 剧集（大陆/欧美/日/韩/动漫/纪录）+ 综艺 | `data/douban-hot.json` |
| 豆瓣热评 | 独立 `comments` 数据组（按 `媒体类型.tmdbId` 索引，每条一句简短热评） | `data/douban-hot.json` → `comments` |
| 芒果TV | 剧集 + 王牌综艺 | `data/mgtv-hot.json` |
| 各平台剧场 | 迷雾/白夜/X/恋恋… 15 个剧场（已开播/即将） | `data/theater-data.json` |
| 热门番剧 | bgm.tv 排名 + TMDB 匹配 | `data/bangumi-hot.json` |
| FlixPatrol | 全球、美国、台湾、香港、新加坡、韩国、日本的流媒体每日 TOP 10 | `data/flixpatrol/*.json` |
| 爱优腾看点 | 爱奇艺、腾讯、优酷三个平台剧集/电影/综艺/动漫的简短看点，每天北京时间 11:30 抓取（芒果由模块运行时现场抓取） | `data/qq-teaser.json` |
| 动画疯 | 通过仓库 Secret 中的台湾 SOCKS5 抓取月人气与年份榜，并匹配 TMDB ID | `data/anigamer-hot.json` |

每个条目都经过 TMDB 匹配，自带 `title / rating / posterPath / mediaType / releaseDate` 等完整字段。

来源站只决定入榜范围、分类和默认顺序；模块展示的标题、简介、海报、背景图、日期、评分和类型均来自 TMDB，不返回来源热度、来源评分或排名字段。

FlixPatrol 数据按国家拆分，`data/flixpatrol/index.json` 提供国家与平台索引。榜单代表 FlixPatrol 已发布的最新日榜，不是未来预测；rex 根据条目的 TMDB ID 和客户端语言加载海报与详情。

`update-flixpatrol.yml` 运行 `scripts/update_flixpatrol.py` 时必须传入仓库 Secret `TMDB_API_KEY`。脚本用 FlixPatrol 的英文源标题、媒体类型和 URL 年份严格匹配 TMDB，只保存 `tmdbId` 与 `mediaType`；海报和本地化元数据由 rex 按客户端语言加载。

动画疯任务只在 `update-anigamer.yml` 中注入 `ANIGAMER_PROXY_URL`，代理不会写入代码或数据。失败时 Workflow 标红，并把脱敏原因写入 `data/anigamer-status.json`；成功后发布 `data/anigamer-hot.json`，Rex 模块只读取 TMDB 身份。

## 数据更新
`.github/workflows/` 下 5 个工作流，各自按 cron 定时运行对应 `scripts/update_*.py`，抓取后**提交更新**到 `data/*.json`。

## widget.js（fw/rex 聚合模块）
`widget.js` 是一个可直接加载的 ForwardWidget 模块，直接消费仓库内的榜单 JSON：

- **6 个子模块**：`loadGuduo` / `loadDouban` / `loadMangoTV` / `loadTheater` / `loadBangumi` / `loadFlixPatrol`
- FlixPatrol 子模块可选择国家/地区、平台和电影/剧集榜；抓取任务按 TMDB 搜索相关度与热度顺序匹配，再用周趋势/热门池、英文标题、媒体类型和年份校验，保存 TMDB ID、原生简介与海报
- 标题和简介按简体中文 → 繁体中文 → 原始语言/原始名称 → 英文的顺序回退
- 海报优先使用 TMDB 无文字（无语言标记）海报，其次中文、英文和其他海报；每组候选都选择分辨率最高的原图
- 同一部影片在多个地区重复上榜时只匹配一次 TMDB，再把结果复用到各地区条目
- 每个模块带**排序方式**（默认原序 / 最近更新 / 最近发布 / 热度最高 / 高分优先）与**分页**
- 条目为标准 `VideoItem`（`type:"tmdb"` + 数字 `id` + `mediaType`），点击走播放器内置 TMDB 详情页
- 数据源默认指向本仓库 raw 地址，也可在模块 `globalParams.baseUrl` 里改

**使用方法**：在 Forward 里添加 `widget.js` 的文件地址即可，无需改脚本。

模块地址（raw）：
```
https://raw.githubusercontent.com/MakkaPakka518/List/main/widget.js
```

## 每日一言邮票

独立测试模块：[widgets/daily-stamp.js](widgets/daily-stamp.js)。在 Rex 添加下面的 GitHub 原始文件地址，选择「每日三枚」：

```text
https://raw.githubusercontent.com/MakkaPakka518/List/main/widgets/daily-stamp.js
```

返回固定三条电影配图与一言，按北京时间日期缓存。短句分别来自一言的诗词、文学和哲学分类，保留作者、出处与日期；配图取自 TMDB 电影周趋势，优先寻找 4:3 图片，缺少时使用横图。短句与配图独立，详情返回配图电影的真实简介。首页排版由 rexhome 的 daily-stamp HTML 组件负责。

```sh
node --test tests/daily-stamp.test.cjs
```

## 爱优腾看点

`scripts/update_qq_teaser.py` 每天由 `.github/workflows/update-qq-teaser.yml` 在北京时间 11:30 抓取看点，写入 `data/qq-teaser.json`：

- 腾讯：`second_title`，缺失时用 `actor_info_core_details`（电视剧、电影、动漫、综艺）。
- 爱奇艺：`desc`，缺失时用 `kvs.featureSubTitle`（电视剧、电影、动漫、综艺）。
- 优酷：当前片库采集取类型标签（如「悬疑 · 罪案」）作为看点补位；独播标记写成「优酷独播」，请求「中国内地」片库。签名和 Cookie 握手直接在脚本内完成，不需要 Worker。

三个平台共用 `channels` 下的同名字段，每个频道按 `(mediaType, tmdbId)` 去重。有文案时优先腾讯、其次爱奇艺的一句话看点，优酷类型词补位；空文案不会压掉其他平台的有效看点。合并保留所有平台的 `tags`、`alsoOn` 和「优酷独播」，同一作品只输出一条。

数据只保留 TMDB 匹配成功且有海报或横图的条目。`displayTitle` 去掉语言版本、季数等后缀；`lastUpdateDate` 用 TMDB 的 `last_air_date`，缺失回退首播日期。平台剧场 2.0.1+ 的「愛優騰芒-看點」（`loadQqTeaserMerged`）读取该文件，与设备现场获取的芒果条目去重后，统一筛选、排序和分页。

芒果TV 片库列表按地区返回不同内容，因此由用户设备现场抓取和匹配，不走本仓库。抓取全部失败或全部无法匹配时保留旧文件；部分平台失败时本次仅包含成功获取的数据。

```sh
node --test tests/qq-teaser-crawl.test.cjs tests/qq-teaser-yk.test.cjs
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
