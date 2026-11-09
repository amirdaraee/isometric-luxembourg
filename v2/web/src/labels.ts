// Layer 15: labels and pins, never in the tiles (OTHERS P8), decluttered by priority and zoom, hidden when their
// ground point is behind a nearer surface (layer 8's depth).

export interface Label {
  name: string; cat: string; src: string; px: number; py: number; depth: number; prio: number; angle?: number;
  slug?: string; v1_px?: [number, number];
}
export interface Box { x0: number; y0: number; x1: number; y1: number }

/** Highest priority shown at a scale (device px per map px): landmarks first, then quarters, places, streets. */
export function maxPrio(scale: number): number {
  return scale < 0.07 ? 1 : scale < 0.14 ? 3 : scale < 0.35 ? 4 : 5;
}

export function overlaps(a: Box, b: Box): boolean {
  return a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
}

/**
 * Which labels to show: in priority order, each placed if its box overlaps none placed before (collision culling,
 * layer-15 rule 2) and its point is not hidden (`hidden(label)`). `toScreen` gives the anchor in screen px and
 * `measure` the text width.
 */
export function declutter(labels: Label[], scale: number, toScreen: (l: Label) => [number, number],
  measure: (l: Label) => number, hidden: (l: Label) => boolean, view: { w: number; h: number }): { l: Label; box: Box; x: number; y: number }[] {
  const out: { l: Label; box: Box; x: number; y: number }[] = [];
  const mp = maxPrio(scale);
  const sorted = [...labels].sort((a, b) => a.prio - b.prio || a.name.localeCompare(b.name));
  for (const l of sorted) {
    if (l.prio > mp) continue;
    const [x, y] = toScreen(l);
    if (x < -50 || y < -20 || x > view.w + 50 || y > view.h + 20) continue;
    const w = measure(l), h = l.prio <= 2 ? 22 : 16;
    const box = { x0: x - w / 2 - 3, y0: y - h - 6, x1: x + w / 2 + 3, y1: y + 2 };
    if (out.some((o) => overlaps(o.box, box))) continue;
    if (hidden(l)) continue;
    out.push({ l, box, x, y });
  }
  return out;
}
