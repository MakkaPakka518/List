const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync(`${__dirname}/../widgets/daily-stamp.js`, 'utf8');
const movies = [101, 238, 603].map(id => ({ id, title: `电影 ${id}`, backdrop_path: `/${id}-wide.jpg`, poster_path: `/${id}-poster.jpg`, release_date: '2000-01-01', vote_average: 8 }));
const words = ['测试诗词十二个字用于排版', '测试文学十二个字用于排版', '测试哲学十二个字用于排版'];

function host(options = {}) {
  let now = Date.parse('2026-11-23T15:59:00Z');
  const calls = [], storage = new Map();
  class Clock extends Date { static now() { return now; } }
  const context = vm.createContext({ Date: Clock, console: { warn() {}, error() {} }, Widget: {
    storage: { async get(key) { return storage.get(key); }, async set(key, value) { storage.set(key, value); } },
    http: { async get(url, opts) {
      calls.push({ http: url, ...opts });
      if (options.failQuotes) throw new Error('一言暂不可用');
      return { data: options.quote || { hitokoto: words[calls.filter(c => c.http).length % 3], from_who: '作者', from: '出处' } };
    } },
    tmdb: { async get(path, opts) {
      calls.push({ tmdb: path, ...opts });
      if (path === 'trending/movie/week') return { results: options.movies || movies };
      if (path.endsWith('/images')) {
        if (options.failImages) throw new Error('图片索引暂不可用');
        return { backdrops: [{ file_path: '/wide.jpg', aspect_ratio: 16 / 9 }, { file_path: '/landscape.jpg', aspect_ratio: 4 / 3 }] };
      }
      return { ...movies.find(movie => `movie/${movie.id}` === path), overview: '电影真实简介' };
    } },
  } });
  vm.runInContext(source, context, { timeout: 500 });
  return { context, calls, storage, nextDay() { now += 120000; }, async load(params) { return JSON.parse(JSON.stringify(await context.loadDailyStamps(params))); } };
}

test('three url items preserve quotes and prefer real 4:3 art', async () => {
  assert.match(source.trimStart(), /^WidgetMetadata\s*=/);
  const app = host(), items = await app.load();
  assert.equal(app.context.WidgetMetadata.id, 'makka.daily.stamp');
  assert.equal(app.context.WidgetMetadata.modules[0].functionName, 'loadDailyStamps');
  assert.equal(items.length, 3);
  assert.deepEqual(items.map(item => item.id), movies.map(movie => `daily-stamp:movie:${movie.id}`));
  for (const item of items) {
    assert.equal(item.type, 'url'); assert.equal(item.link, item.id);
    assert.equal(item.posterPath, '/landscape.jpg'); assert.equal(item.coverRatio, 4 / 3);
    assert.deepEqual(Object.keys(JSON.parse(item.description)).sort(), ['author', 'date', 'source', 'text']);
    assert.equal(JSON.parse(item.description).date, '2026-11-23');
    assert.equal(item.overview, undefined); assert.equal(item.poster_path, undefined);
  }
  assert.deepEqual(app.calls.filter(call => call.http).map(call => call.params.c), ['i', 'd', 'k']);
  assert.ok(app.calls.filter(call => call.http).every(call => call.http === 'https://international.v1.hitokoto.cn/' && call.params.max_length === 32));
  assert.equal(app.calls[0].tmdb, 'trending/movie/week');
});

test('same-day reload uses storage and the Beijing midnight refreshes it', async () => {
  const app = host(), first = await app.load(), count = app.calls.length;
  assert.deepEqual(await app.load(), first);
  assert.equal(app.calls.length, count);
  app.nextDay();
  const second = await app.load();
  assert.equal(JSON.parse(second[0].description).date, '2026-11-24');
  assert.equal(app.calls.length, count * 2);
  assert.equal(app.storage.size, 1, 'daily snapshots replace the previous day');
});

test('image-index failure keeps the original 16:9 image and caches independently by language', async () => {
  const app = host({ failImages: true });
  const items = await app.load({ language: 'zh-TW' });
  assert.equal(items[0].posterPath, movies[0].backdrop_path);
  assert.equal(items[0].coverRatio, 16 / 9);
  assert.equal(app.calls[0].params.language, 'zh-TW');
  await app.load({ language: 'zh-CN' });
  assert.equal(app.storage.size, 2);
});

test('incomplete TMDB or invalid quote data is surfaced, not cached as success', async () => {
  for (const options of [{ failQuotes: true }, { quote: { hitokoto: '' } }, { quote: { hitokoto: '字'.repeat(33) } }, { movies: movies.slice(0, 2) }]) {
    const app = host(options);
    await assert.rejects(app.load());
    assert.equal(app.storage.size, 0);
  }
});

test('detail routing rejects unrelated links without requests and restores the actual movie', async () => {
  const app = host();
  for (const link of ['tmdb:movie:101', 'https://example.com/101', 'daily-stamp:tv:101', 'daily-stamp:movie:0', null]) {
    assert.equal(await app.context.loadDetail(link), null);
  }
  assert.equal(app.calls.length, 0);
  const movie = await app.context.loadDetail('daily-stamp:movie:101');
  assert.equal(movie.id, 101); assert.equal(movie.type, 'tmdb');
  assert.equal(movie.description, '电影真实简介');
  assert.equal(movie.posterPath, movies[0].poster_path);
  assert.equal(app.calls[0].tmdb, 'movie/101');
});
