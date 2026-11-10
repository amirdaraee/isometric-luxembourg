// Two viewers on the same release, the same views: how many pixels differ.
//   node scripts/compare_viewers.mjs <base url A> <base url B> "<query>" ["<query>" ...]
// Used once to show that the viewer with the cutaways, toggle off, draws what the viewer before them drew
// (v2/docs/specs/landmark-cutaways.md, K6): serve each checkout's v2/web on its own port, then compare.
import { open, settle } from "./shot.mjs";

const [a, b, ...queries] = process.argv.slice(2);
const W = 1600, H = 1000;
const grab = async (base, q) => {
  const { browser, page, errors } = await open(base, W, H);
  await page.goto(base + "?noui&nosim&" + q);
  await settle(page, {});
  await page.waitForTimeout(2000);                    // the night's windows and lamps are in
  const px = await page.evaluate(() => {
    window.__v2.renderNow();
    const c = document.getElementById("map"), gl = c.getContext("webgl2");
    const d = new Uint8Array(c.width * c.height * 4);
    gl.readPixels(0, 0, c.width, c.height, gl.RGBA, gl.UNSIGNED_BYTE, d);
    return Array.from(d);
  });
  await browser.close();
  return { px, errors };
};
const out = [];
for (const q of queries) {
  const A = await grab(a, q), B = await grab(b, q);
  let n = 0;
  for (let i = 0; i < A.px.length; i += 4) if (A.px[i] !== B.px[i] || A.px[i + 1] !== B.px[i + 1] || A.px[i + 2] !== B.px[i + 2]) n++;
  out.push({ query: q, pixels: A.px.length / 4, differ: n, errors: [...A.errors, ...B.errors] });
}
console.log(JSON.stringify(out, null, 1));
