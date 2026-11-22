// Renders logo.svg to PNGs (used once; outputs are committed). Usage: node render.js <dir>
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const dir = process.argv[2];
  const svg = fs.readFileSync(`${dir}/logo.svg`, 'utf8');
  const browser = await chromium.launch();
  for (const size of [16, 32, 48, 64, 128, 256, 512]) {
    const page = await browser.newPage({ viewport: { width: size, height: size }, deviceScaleFactor: 1 });
    await page.setContent(`<html><body style="margin:0;background:transparent">${svg.replace('width="256" height="256"', `width="${size}" height="${size}"`)}</body></html>`);
    await page.screenshot({ path: `${dir}/logo-${size}.png`, omitBackground: true });
    await page.close();
  }
  await browser.close();
})();
