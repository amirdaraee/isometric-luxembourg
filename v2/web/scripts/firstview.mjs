// First-view timing: node scripts/firstview.mjs <base url> [query] [runs]
import { open } from "./shot.mjs";

const [base, q = "", runs = "3"] = process.argv.slice(2);
const { browser } = await open(base);
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
const out = [];
let n = 0;
page.on("request", () => n++);
for (let i = 0; i < +runs; i++) {
  n = 0;
  await page.goto(base + "?noui&" + q);
  await page.waitForFunction(() => window.__v2 && window.__v2.firstViewMs, null, { timeout: 60000 });
  const t = await page.evaluate(() => ({ first: window.__v2.firstViewMs, nav: performance.timing.domContentLoadedEventEnd - performance.timing.navigationStart }));
  out.push({ ...t, requests: n });
}
console.log(JSON.stringify(out));
await browser.close();
