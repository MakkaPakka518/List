const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const paths = require('node:path');
const root = paths.resolve(__dirname, '..');
const { test } = require('node:test');

test('Youku entries mark their platform in the tags and use the genre as the teaser', () => {
  const out = execFileSync('python3', ['-c', `
import importlib.util, json
spec = importlib.util.spec_from_file_location("m", "scripts/update_qq_teaser.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(json.dumps([
  m.parse_yk({"title": "嫁金钗", "tags": ["独播", "30集全", "古装 · 爱情"]}, "tv"),
  m.parse_yk({"title": "谷雨", "tags": ["限免中", "限免15集", "悬疑 · 罪案"]}, "tv"),
  m.parse_yk({"title": "背水一战", "tags": ["VIP", "动作 · 冒险"]}, "movie"),
]))
`], { cwd: root, encoding: 'utf8' });
  const [exclusive, limited, vip] = JSON.parse(out);
  assert.equal(exclusive.teaser, '古装 · 爱情');
  assert.ok(exclusive.tags.includes('优酷独播'), '独播 becomes 优酷独播');
  assert.equal(limited.teaser, '悬疑 · 罪案');
  assert.ok(!limited.tags.includes('限免中'), 'promo tags stay out of the card tags');
  assert.equal(vip.teaser, '动作 · 冒险');
  assert.ok(!vip.tags.includes('VIP'), 'VIP stays out of the card tags');
});

test('the committed data marks Youku entries distinctly', () => {
  const data = JSON.parse(fs.readFileSync(paths.join(root, 'data/qq-teaser.json'), 'utf8'));
  const youku = Object.values(data.channels).flat().filter((entry) => entry.source === 'yk');
  for (const entry of youku) {
    if (entry.tags.includes('优酷独播')) continue;
    assert.ok(entry.teaser, 'Youku entries without the badge still carry a teaser');
  }
});
