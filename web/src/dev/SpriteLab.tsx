// Dev view (?spritelab): every vehicle sprite type at all 32 headings, on a grey ground, to check the sprites and
// their lamps by eye and in screenshots. For each type two rows: by day (no lamps), and at night braking with every
// lamp on (tail and brake lights, headlamps, lit windows). In the night row no red may show on a roof or on glass,
// and none at all in the frames heading down the screen (the rear of the vehicle faces away from the camera).
//
//   ?spritelab                    every type, each as large as fits 32 frames across the page (at most zoom 1.25)
//   ?spritelab&type=car&zoom=4    one type (or a comma list), at a fixed zoom, wrapping onto more lines
import { useEffect, useRef } from "react";
import { drawLamps, drawVehicle, loadSprites, type Sprites } from "../components/sprites";

const q = new URLSearchParams(location.search);
const only = q.get("type")?.split(",") ?? null;
const fixedZoom = q.has("zoom") ? Number(q.get("zoom")) : null;

const DAY = "#8a8a8a", NIGHT = "#2b2f3a";

function draw(cv: HTMLCanvasElement, s: Sprites) {
  const W = window.innerWidth, dpr = window.devicePixelRatio || 1;
  const types = Object.keys(s.types).filter((t) => !only || only.includes(t));
  const label = 110, pad = 4, cols = s.headings;
  // Layout first (to size the canvas): per type its zoom, cell size and rows.
  const plan = types.map((type) => {
    const t = s.types[type];
    const fit = ((W - label - 8) / cols - pad - 1) / (t.frame[0] * (s.mpp / s.map_mpp));
    const zoom = fixedZoom ?? Math.min(1.25, fit);
    const k = zoom * (s.mpp / s.map_mpp);
    const cw = Math.ceil(t.frame[0] * k) + pad, ch = Math.max(34, Math.ceil(t.frame[1] * k) + pad);
    const per = Math.max(1, Math.floor((W - label - 8) / cw));
    const lines = Math.ceil(cols / per);
    return { type, zoom, k, cw, ch, per, lines };
  });
  const H = plan.reduce((a, p) => a + 2 * p.lines * p.ch + 10, 10);
  cv.width = W * dpr; cv.height = H * dpr;
  cv.style.width = `${W}px`; cv.style.height = `${H}px`;
  const g = cv.getContext("2d")!;
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.fillStyle = DAY; g.fillRect(0, 0, W, H);
  g.font = "12px system-ui, sans-serif"; g.textBaseline = "top";
  let y = 10;
  for (const p of plan) {
    const t = s.types[p.type];
    for (const night of [false, true]) {
      const h = p.lines * p.ch;
      if (night) { g.fillStyle = NIGHT; g.fillRect(0, y, W, h); }
      g.fillStyle = night ? "#e6e6e6" : "#111";
      g.fillText(`${p.type} ${night ? "night, braking" : "day"}`, 6, y + 4);
      g.fillText(`zoom ${p.zoom.toFixed(2)}`, 6, y + 18);
      for (let i = 0; i < cols; i++) {
        const col = i % p.per, row = Math.floor(i / p.per);
        const heading = t.heading[i];
        // ground centre of the cell's frame
        const x = label + col * p.cw + t.anchor[0] * p.k + pad / 2, yy = y + row * p.ch + t.anchor[1] * p.k + pad / 2;
        drawVehicle(g, s, p.type, 0, x, yy, heading, p.zoom);
        if (night) drawLamps(g, s, p.type, x, yy, heading, p.zoom, { tail: 0.85, brake: 1, head: 1, glass: 0.8 });
      }
      y += h;
    }
    y += 10;
  }
}

export default function SpriteLab() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    document.body.style.overflow = "auto";
    loadSprites().then((s) => { if (ref.current) draw(ref.current, s); }).catch((e) => console.error(e));
  }, []);
  return <div style={{ position: "absolute", inset: 0, background: DAY }}><canvas ref={ref} style={{ display: "block" }} /></div>;
}
