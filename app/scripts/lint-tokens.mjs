// Design-system lint (09 §2.5 rules): components may only use tokens. Raw hex/rgb()/hsl() colours are
// allowed exclusively in src/design-system/tokens.css.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const root = new URL('../src/', import.meta.url).pathname;
const allowed = new Set(['design-system/tokens.css']);
const colour = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/g;
const failures = [];

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) { walk(path); continue; }
    if (!/\.(ts|css)$/.test(name)) continue;
    const rel = relative(root, path);
    if (allowed.has(rel)) continue;
    readFileSync(path, 'utf8').split('\n').forEach((line, i) => {
      // Ignore URL fragments such as `#token=` and `#/` and HTML entities.
      const cleaned = line.replace(/['"`][^'"`]*#[a-z_]+=?[^'"`]*['"`]/g, '').replace(/&#\d+;/g, '');
      const hits = cleaned.match(colour);
      if (hits) failures.push(`${rel}:${i + 1}: raw colour ${hits.join(', ')} (use a --vs-* token)`);
    });
  }
}

walk(root);
if (failures.length) {
  console.error(failures.join('\n'));
  console.error(`\nlint:tokens failed: ${failures.length} raw colour value(s) outside tokens.css`);
  process.exit(1);
}
console.log('lint:tokens passed: no raw colour values outside src/design-system/tokens.css');
