// A Ferris wheel drawn live in the map's own projection (the camera of build_sprites.py: 45 degrees round, 30
// degrees down), so it reads as a solid wheel standing on its painted platform: its rim is an ellipse on screen,
// its gondolas hang straight down from their pins while the rim turns, and at night bulbs light the rims and spokes.
// It turns continuously with the clock (no frames), so the movement is smooth at any speed and every visitor sees
// the same position.
//
// World axes, metres: x east-ish (screen right and down), y north-ish (screen right and up), z up. The wheel's plane
// is upright and holds the y axis; its axle runs along x. The origin is the ground anchor (the platform's centre).

export interface WheelSpec {
  /** rim radius, m */
  radius: number;
  /** hub height above the anchor, m */
  hub: number;
  /** number of gondolas (and spokes per side) */
  gondolas: number;
  /** seconds per turn */
  period: number;
  /** half the distance between the two rims, m */
  halfWidth: number;
  /** gondola colours, repeated round the wheel */
  colours: string[];
}

export const CONSTITUTION_WHEEL: WheelSpec = {
  radius: 14.5,
  hub: 17.0,
  gondolas: 24,
  period: 150,
  halfWidth: 1.3,
  colours: ["#ce2a2c", "#f2ead8", "#2f6fb0", "#f2ead8"],
};

const R = 0.70710678, SE = 0.5, CE = 0.8660254, MAP_MPP = 0.25;

/** World point (m) -> screen offset in map px from the anchor (y down). */
export function proj(x: number, y: number, z: number): [number, number] {
  return [((x + y) * R) / MAP_MPP, -(((-x + y) * R * SE + z * CE) / MAP_MPP)];
}

/** Nearer to the viewer = larger. Used to order gondolas and to split the rims into back and front. */
function depth(x: number, y: number): number {
  return x - y;
}

type RGB = [number, number, number];
function hex(c: string): RGB {
  const n = parseInt(c.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function mix(a: RGB, b: RGB, t: number): RGB {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}
function css(c: RGB, k = 1): string {
  return `rgb(${Math.round(c[0] * k)},${Math.round(c[1] * k)},${Math.round(c[2] * k)})`;
}
/** A colour seen at night: dim and blue, as the night art treats lit-less surfaces. */
function nightOf(c: RGB): RGB {
  const l = (c[0] + c[1] + c[2]) / 3;
  return [l * 0.22 + c[0] * 0.08 + 8, l * 0.25 + c[1] * 0.06 + 12, l * 0.36 + c[2] * 0.06 + 26];
}

const STEEL: RGB = [240, 240, 236];
const STEEL_SHADE: RGB = [196, 202, 212];
const INK: RGB = [24, 22, 28];
const GLASS: RGB = [70, 84, 110];
const LIT: RGB = [255, 214, 140];

export interface WheelView {
  /** screen px of the anchor */
  sx: number;
  sy: number;
  /** screen px per map px */
  z: number;
  /** 0 day .. 1 night */
  night: number;
  /** rotation, radians */
  theta: number;
  /** seconds, for the slow light pattern at night */
  sec: number;
  /** a soft warm dot for bulbs (drawn with "lighter") */
  glow: CanvasImageSource;
}

/** The wheel's rotation at a time: one turn per period, continuous. */
export function wheelAngle(spec: WheelSpec, sec: number): number {
  return ((sec % spec.period) / spec.period) * Math.PI * 2;
}

/**
 * Draws the wheel: back support, back rim and spokes, gondolas from back to front, front rim and spokes, front
 * support, hub. Line widths follow the zoom (a 0.5 m tube is 2 map px), never under a hairline.
 */
export function drawWheel(g: CanvasRenderingContext2D, spec: WheelSpec, v: WheelView): void {
  const { sx, sy, z, night: n, theta } = v;
  const P = (x: number, y: number, zz: number): [number, number] => {
    const [px, py] = proj(x, y, zz);
    return [sx + px * z, sy + py * z];
  };
  const m = z / MAP_MPP;                       // screen px per metre (across the screen)
  const lw = (metres: number) => Math.max(0.6, metres * m);
  const steel = mix(STEEL, nightOf(STEEL), n), shade = mix(STEEL_SHADE, nightOf(STEEL_SHADE), n);
  const ink = css(mix(INK, [10, 12, 22], n));
  const { radius: r, hub: h, gondolas: N, halfWidth: a } = spec;
  const detail = z >= 0.45;                    // further out: no spokes' cross cables, fewer rim segments
  const SEG = detail ? 96 : 48;

  const rimPoint = (ang: number, x: number, rr = r): [number, number, number] => [x, rr * Math.cos(ang), h + rr * Math.sin(ang)];

  /** A tube along world points, with a dark ink edge under it. */
  const tube = (pts: [number, number][], width: number, colour: string, closed = false, inkEdge = true) => {
    g.beginPath();
    pts.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y)));
    if (closed) g.closePath();
    if (inkEdge) {
      g.strokeStyle = ink;
      g.lineWidth = width + Math.max(1, 0.35 * m);
      g.stroke();
    }
    g.strokeStyle = colour;
    g.lineWidth = width;
    g.stroke();
  };

  const support = (x: number) => {
    // an A-frame each side, legs splayed along the wheel's plane and leaning out from the axle
    const foot = r * 0.62, out = Math.sign(x) * 2.2;
    const top = P(x, 0, h), l = P(x + out, -foot, 0), rr = P(x + out, foot, 0);
    const mid = 0.45;
    const bl = P(x + out * mid, -foot * mid, h * (1 - mid)), br = P(x + out * mid, foot * mid, h * (1 - mid));
    g.lineCap = "round";
    tube([l, top, rr], lw(0.55), css(steel));
    tube([bl, br], lw(0.3), css(steel));
  };

  const rim = (x: number) => {
    const pts: [number, number][] = [];
    for (let i = 0; i <= SEG; i++) {
      const p = rimPoint(theta + (i / SEG) * Math.PI * 2, x);
      pts.push(P(p[0], p[1], p[2]));
    }
    tube(pts, lw(0.45), css(steel), true);
    // inner ring, as on most wheels a lighter truss inside the rim
    const inner: [number, number][] = [];
    for (let i = 0; i <= SEG; i++) {
      const p = rimPoint(theta + (i / SEG) * Math.PI * 2, x, r * 0.86);
      inner.push(P(p[0], p[1], p[2]));
    }
    tube(inner, lw(0.2), css(steel), true, false);
  };

  const spokes = (x: number) => {
    g.strokeStyle = css(shade, 0.92);
    g.lineWidth = lw(0.12);
    g.beginPath();
    const c = P(x * 0.35, 0, h);
    for (let i = 0; i < N; i++) {
      const ang = theta + ((i + 0.5) / N) * Math.PI * 2;
      const p = rimPoint(ang, x);
      const q = P(p[0], p[1], p[2]);
      g.moveTo(c[0], c[1]);
      g.lineTo(q[0], q[1]);
    }
    g.stroke();
  };

  // gondola pins round the rim, back to front
  const pins = Array.from({ length: N }, (_, i) => {
    const ang = theta + (i / N) * Math.PI * 2;
    return { i, ang, y: r * Math.cos(ang), zz: h + r * Math.sin(ang) };
  }).sort((p, q) => depth(0, q.y) - depth(0, p.y));

  const gondola = (y: number, zz: number, colour: RGB) => {
    // a cabin hanging under its pin: 1.9 m along the axle, 1.7 m across, 1.9 m tall, roof cap on top
    const gx = 1.05, gy = 0.95, top = zz - 0.45, bot = top - 2.1;
    const col = mix(colour, nightOf(colour), n);
    const corner = (dx: number, dy: number, zz2: number) => P(dx, y + dy, zz2);
    const face = (pts: [number, number][], fill: string) => {
      g.beginPath();
      pts.forEach(([px, py], k) => (k ? g.lineTo(px, py) : g.moveTo(px, py)));
      g.closePath();
      g.fillStyle = fill;
      g.fill();
      g.strokeStyle = ink;
      g.lineWidth = Math.max(0.5, 0.06 * m);
      g.stroke();
    };
    // hanger from the pin
    const pin = P(0, y, zz), hang = P(0, y, top);
    g.strokeStyle = css(shade);
    g.lineWidth = lw(0.15);
    g.beginPath(); g.moveTo(pin[0], pin[1]); g.lineTo(hang[0], hang[1]); g.stroke();
    // the faces the camera sees: the one towards +x, the one towards -y, and the roof
    face([corner(gx, -gy, top), corner(gx, gy, top), corner(gx, gy, bot), corner(gx, -gy, bot)], css(col, 0.8));
    face([corner(-gx, -gy, top), corner(gx, -gy, top), corner(gx, -gy, bot), corner(-gx, -gy, bot)], css(col, 0.68));
    // windows: a band on both faces, dark glass by day, warm light at night
    const win = mix(GLASS, LIT, n);
    const wt = top - 0.35, wb = top - 1.15;
    face([corner(gx, -gy * 0.75, wt), corner(gx, gy * 0.75, wt), corner(gx, gy * 0.75, wb), corner(gx, -gy * 0.75, wb)], css(win));
    face([corner(-gx * 0.75, -gy, wt), corner(gx * 0.75, -gy, wt), corner(gx * 0.75, -gy, wb), corner(-gx * 0.75, -gy, wb)], css(win, 0.9));
    const roof = mix(STEEL, nightOf(STEEL), n);
    face([corner(-gx * 1.08, -gy * 1.08, top + 0.25), corner(gx * 1.08, -gy * 1.08, top + 0.25),
      corner(gx * 1.08, gy * 1.08, top + 0.25), corner(-gx * 1.08, gy * 1.08, top + 0.25)], css(roof));
  };

  const bulbs = (x: number) => {
    if (n < 0.02) return;
    const glow = v.glow;
    g.globalCompositeOperation = "lighter";
    // the rim's string of bulbs reads as a warm line from afar, the spokes as fainter rays
    const line = (rr: number, width: number, alpha: number) => {
      g.beginPath();
      for (let i = 0; i <= SEG; i++) {
        const p = rimPoint(theta + (i / SEG) * Math.PI * 2, x * 1.04, rr);
        const q = P(p[0], p[1], p[2]);
        if (i) g.lineTo(q[0], q[1]); else g.moveTo(q[0], q[1]);
      }
      g.strokeStyle = `rgba(255,206,130,${alpha * n})`;
      g.lineWidth = width;
      g.stroke();
    };
    line(r, Math.max(1.5, 0.5 * m), 0.85);
    line(r * 0.86, Math.max(1, 0.25 * m), 0.45);
    g.strokeStyle = `rgba(255,214,150,${0.35 * n})`;
    g.lineWidth = Math.max(0.8, 0.15 * m);
    g.beginPath();
    const c = P(x * 0.35, 0, h);
    for (let i = 0; i < N; i++) {
      const p = rimPoint(theta + ((i + 0.5) / N) * Math.PI * 2, x);
      const q = P(p[0], p[1], p[2]);
      g.moveTo(c[0], c[1]); g.lineTo(q[0], q[1]);
    }
    g.stroke();
    const size = Math.max(2, 0.9 * m);
    // a slow wave of light running round the rim and out along the spokes; never a hard flash
    const wave = (k: number) => 0.6 + 0.4 * Math.sin(v.sec * 0.9 - k * 0.5);
    const RIM_BULBS = detail ? 72 : 36;
    for (let i = 0; i < RIM_BULBS; i++) {
      const ang = theta + (i / RIM_BULBS) * Math.PI * 2;
      const p = rimPoint(ang, x * 1.08);
      const q = P(p[0], p[1], p[2]);
      g.globalAlpha = Math.min(1, n * 0.95 * wave(i));
      g.drawImage(glow, q[0] - size, q[1] - size, size * 2, size * 2);
    }
    if (detail) {
      for (let i = 0; i < N; i++) {
        const ang = theta + ((i + 0.5) / N) * Math.PI * 2;
        for (const f of [0.3, 0.5, 0.7]) {
          const p = rimPoint(ang, x, r * f);
          const q = P(p[0], p[1], p[2]);
          g.globalAlpha = n * 0.7 * wave(f * 10 + i);
          g.drawImage(glow, q[0] - size * 0.8, q[1] - size * 0.8, size * 1.6, size * 1.6);
        }
      }
    }
    g.globalAlpha = 1;
    g.globalCompositeOperation = "source-over";
  };

  g.lineJoin = "round";
  g.lineCap = "round";
  // back half (x < 0 is further from the camera)
  support(-a - 0.4);
  rim(-a);
  if (detail) spokes(-a);
  bulbs(-a);
  // cross bars at the pins, then the gondolas, back to front
  g.strokeStyle = css(shade);
  g.lineWidth = lw(0.18);
  g.beginPath();
  for (const p of pins) {
    const b = P(-a, p.y, p.zz), f = P(a, p.y, p.zz);
    g.moveTo(b[0], b[1]); g.lineTo(f[0], f[1]);
  }
  g.stroke();
  for (const p of pins) gondola(p.y, p.zz, hex(spec.colours[p.i % spec.colours.length]));
  // front half
  rim(a);
  if (detail) spokes(a);
  bulbs(a);
  support(a + 0.4);
  // hub and axle
  const hb = P(-a - 0.6, 0, h), hf = P(a + 0.6, 0, h);
  tube([hb, hf], lw(1.1), css(shade));
  g.beginPath();
  g.arc(hf[0], hf[1], lw(0.9), 0, Math.PI * 2);
  g.fillStyle = css(steel);
  g.fill();
  g.strokeStyle = ink;
  g.lineWidth = Math.max(0.6, 0.08 * m);
  g.stroke();
  if (n > 0.02) {
    g.globalCompositeOperation = "lighter";
    g.globalAlpha = n * 0.9;
    const s = Math.max(3, 2.2 * m);
    g.drawImage(v.glow, hf[0] - s, hf[1] - s, s * 2, s * 2);
    g.globalAlpha = 1;
    g.globalCompositeOperation = "source-over";
  }
}
