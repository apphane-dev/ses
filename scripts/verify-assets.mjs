import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

const publicRoot = new URL('../public/', import.meta.url);
const manifest = JSON.parse(readFileSync(new URL('media/manifest.json', publicRoot), 'utf8'));
assert.equal(manifest.audio_tracks, 0, 'Marketing films must be silent');
assert.equal(manifest.duration_seconds, 32);
assert.ok(manifest.files['media/ses.mp4']);
assert.ok(manifest.files['brand/tokens.css']);
for (const [path, expected] of Object.entries(manifest.files)) {
  const actual = createHash('sha256').update(readFileSync(new URL(path, publicRoot))).digest('hex');
  assert.equal(actual, expected, `${path} drifted. Re-sync from main with marketing/scripts/site-assets.py`);
}
console.log(`Verified ${Object.keys(manifest.files).length} identity and film asset hashes.`);
