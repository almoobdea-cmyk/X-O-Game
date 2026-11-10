// Render the model page locally and save one screenshot per view.
// Usage: node shot.js <page.html> <three.min.js path> <outDir> view1 view2 ...
// The page must expose window.__model = { setView(name, instant), setAuto(bool) }.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [page, three, out, ...views] = process.argv.slice(2);
  const html = fs.readFileSync(page, 'utf8')
    .replace(/https:\/\/cdnjs\.cloudflare\.com\/ajax\/libs\/three\.js\/r128\/three\.min\.js/, 'file://' + path.resolve(three))
    .replace(/<link rel="stylesheet"[^>]*>/g, '');
  const tmp = path.join(out, '_test.html');
  fs.writeFileSync(tmp, '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0">' + html + '</body></html>');
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 1200, height: 1000 } });
  p.on('pageerror', e => console.log('PAGEERR', e.message));
  p.on('console', m => { if (m.type() === 'error') console.log('ERR', m.text()); });
  await p.goto('file://' + path.resolve(tmp));
  await p.waitForTimeout(1500);
  for (const v of views) {
    await p.evaluate(v => { const m = window.__model || window.__dome; m.setAuto(false); m.setView(v, true); }, v);
    await p.waitForTimeout(700);
    await p.locator('#stage').screenshot({ path: path.join(out, `view_${v}.png`) });
  }
  await p.screenshot({ path: path.join(out, 'page_desktop.png'), fullPage: true });
  await p.setViewportSize({ width: 400, height: 800 });
  await p.waitForTimeout(500);
  await p.screenshot({ path: path.join(out, 'page_phone.png'), fullPage: true });
  console.log('overflow check:', await p.evaluate(() => document.documentElement.scrollWidth + ' vs ' + innerWidth));
  await b.close();
})();
