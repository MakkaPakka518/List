const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const paths = require('node:path');

const root = paths.resolve(__dirname, '..');

function run(env = {}) {
  return execFileSync('python3', ['scripts/update_qq_teaser.py'], {
    cwd: root, env: { ...process.env, ...env }, encoding: 'utf8',
  });
}

function stub(dir, body) {
  fs.writeFileSync(paths.join(dir, 'sitecustomize.py'), body);
  return { PYTHONPATH: dir };
}

const { test } = require('node:test');

test('the workflow runs daily at 03:30 UTC, which is 11:30 Beijing time', () => {
  const yml = fs.readFileSync(paths.join(root, '.github/workflows/update-qq-teaser.yml'), 'utf8');
  assert.match(yml, /cron: '30 3 \* \* \*'/);
  assert.match(yml, /workflow_dispatch/);
  assert.match(yml, /scripts\/update_qq_teaser\.py/);
  assert.match(yml, /data\/qq-teaser\.json/);
});

test('the committed data keeps the current snapshot until the next crawl', () => {
  const data = JSON.parse(fs.readFileSync(paths.join(root, 'data/qq-teaser.json'), 'utf8'));
  assert.ok(data.channels && Object.keys(data.channels).length > 0);
});

test('the committed data has every channel and a teaser on every entry', () => {
  const data = JSON.parse(fs.readFileSync(paths.join(root, 'data/qq-teaser.json'), 'utf8'));
  assert.ok(data.updatedAt && /\+08:00$/.test(data.updatedAt), 'saved in Beijing time');
  for (const channel of ['tv', 'movie', 'variety', 'anime', 'doc', 'kids']) {
    assert.ok(Array.isArray(data.channels[channel]));
    const entries = data.channels[channel];
    assert.ok(entries.length > 0);
    assert.equal(entries.filter((entry) => entry.teaser).length, entries.length);
    for (const entry of entries) {
      assert.ok(entry.cid && entry.title);
      assert.equal(entry.title.includes('更新'), false, 'update marker is stripped from titles');
    }
  }
});

test('TV and movie lists merge QQ and iQiyi entries with distinct ids', () => {
  const data = JSON.parse(fs.readFileSync(paths.join(root, 'data/qq-teaser.json'), 'utf8'));
  for (const channel of ['tv', 'movie']) {
    const entries = data.channels[channel];
    const iq = entries.filter((entry) => entry.cid.startsWith('iq'));
    const qq = entries.filter((entry) => !entry.cid.startsWith('iq'));
    assert.ok(iq.length > 0, `${channel} has iQiyi entries`);
    assert.ok(qq.length > 0, `${channel} keeps QQ entries`);
    assert.equal(new Set(entries.map((entry) => entry.cid)).size, entries.length, 'no duplicate ids');
  }
});

test('QQ parsing keeps the teaser, tags and year', () => {
  const out = execFileSync('python3', ['-c', `
import importlib.util, json
spec = importlib.util.spec_from_file_location("m", "scripts/update_qq_teaser.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
labels = json.dumps([{"label": "板凳剧场"}, {"label": "搞笑喜剧"}, {"label": "评分 9.2"}, {"label": "更新至10集"}])
print(json.dumps([
  m.parse_qq({"cid": "a", "title": "走马上任·更新", "second_title": "赵家班新爆笑喜剧", "main_genre": "喜剧", "chnlist_search_label": labels, "year": "2026"}),
  m.parse_qq({"cid": "b", "title": "多喜一家人", "actor_info_core_details": "平凡人家大戏启幕", "publish_date": "2026-11-02"}),
  m.parse_qq({"cid": "", "title": "无 ID"}),
]))
`], { cwd: root, encoding: 'utf8' });
  const [first, fallback, bad] = JSON.parse(out);
  assert.equal(first.title, '走马上任');
  assert.equal(first.teaser, '赵家班新爆笑喜剧');
  assert.equal(first.year, '2026');
  assert.deepEqual(first.tags, ['喜剧', '搞笑喜剧'], 'noise labels and theatre names are dropped');
  assert.equal(fallback.teaser, '平凡人家大戏启幕');
  assert.equal(fallback.year, '2026', 'year falls back to the publish date');
  assert.equal(bad, null);
});

test('iQiyi parsing keeps desc, the period year and an empty tag list for TMDB to fill', () => {
  const out = execFileSync('python3', ['-c', `
import importlib.util, json
spec = importlib.util.spec_from_file_location("m", "scripts/update_qq_teaser.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(json.dumps([
  m.parse_iq({"albumId": 3190714930072901, "albumName": "两京十五日", "desc": "限时闯关“京”险不断", "period": "20261119", "lowerRightCorner": "更新至10集"}),
  m.parse_iq({"albumId": 5, "albumName": "小城良方", "desc": "", "kvs": {"featureSubTitle": "纯过日子"}, "year": 2026}),
  m.parse_iq({"albumId": 0, "albumName": "无 ID"}),
]))
`], { cwd: root, encoding: 'utf8' });
  const [first, fallback, bad] = JSON.parse(out);
  assert.equal(first.cid, 'iq3190714930072901');
  assert.equal(first.teaser, '限时闯关“京”险不断');
  assert.equal(first.year, '2026', 'year comes from the period');
  assert.deepEqual(first.tags, []);
  assert.equal(fallback.teaser, '纯过日子');
  assert.equal(bad, null);
});

test('an upstream failure keeps the previous data file', () => {
  const before = fs.readFileSync(paths.join(root, 'data/qq-teaser.json'), 'utf8');
  const dir = fs.mkdtempSync('/tmp/qqf-');
  const env = stub(dir, `
from urllib.request import Request
def _fail(*a, **k):
    raise OSError('network down')
import urllib.request
urllib.request.urlopen = _fail
`);
  assert.throws(() => run(env));
  assert.equal(fs.readFileSync(paths.join(root, 'data/qq-teaser.json'), 'utf8'), before);
});
