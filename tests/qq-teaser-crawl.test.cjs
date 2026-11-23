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

test('the committed data has both channels and a teaser on every entry', () => {
  const data = JSON.parse(fs.readFileSync(paths.join(root, 'data/qq-teaser.json'), 'utf8'));
  assert.ok(data.updatedAt && /\+08:00$/.test(data.updatedAt), 'saved in Beijing time');
  for (const channel of ['tv', 'movie']) {
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

test('the parser reads second_title first and falls back to actor_info_core_details', () => {
  const out = execFileSync('python3', ['-c', `
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("m", "scripts/update_qq_teaser.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(json.dumps([
  m.parse({"cid": "a", "title": "走马上任·更新", "second_title": "赵家班新爆笑喜剧"}),
  m.parse({"cid": "b", "title": "多喜一家人", "second_title": "", "actor_info_core_details": "平凡人家大戏启幕"}),
  m.parse({"cid": "", "title": "无 ID"}),
  m.parse({"cid": "c", "title": "无看点"}),
]))
`], { cwd: root, encoding: 'utf8' });
  const [first, fallback, noId, bare] = JSON.parse(out);
  assert.equal(first.title, '走马上任');
  assert.equal(first.teaser, '赵家班新爆笑喜剧');
  assert.equal(fallback.teaser, '平凡人家大戏启幕');
  assert.equal(noId, null, 'entries without an id are rejected');
  assert.equal(bare.teaser, '', 'an empty teaser stays empty, never invented');
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
