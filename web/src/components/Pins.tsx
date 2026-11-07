import { useMemo } from "react";
import type { MapHandle, View } from "./IsometricMap";

export interface Place {
  n: string;
  c: string;
  x: number;
  y: number;
  d?: string;
  f?: 1;
  q?: 1;
  a?: string;
}

interface Props {
  places: Place[];
  view: View | null;
  map: React.RefObject<MapHandle>;
  active: Place | null;
  onPick: (p: Place) => void;
}

const LABEL_W = 150;
const LABEL_H = 34;

// Places in priority order, keeping only those whose labels don't collide.
export function Pins({ places, view, map, active, onPick }: Props) {
  const featured = useMemo(() => places.filter((p) => p.f || p.q), [places]);
  if (!view || !map.current) return null;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const quartersOnly = view.z < 0.09;
  const showPins = view.z >= 0.09;
  const placed: { x: number; y: number }[] = [];
  const out: JSX.Element[] = [];
  const ordered = [...(active ? [active] : []), ...featured.filter((p) => p !== active)];
  for (const p of ordered) {
    const isQuarter = !!p.q;
    if (p !== active) {
      if (quartersOnly && !isQuarter) continue;
      if (isQuarter && view.z > 0.3) continue;
      if (!isQuarter && !showPins) continue;
    }
    const s = map.current.toScreen(p.x, p.y);
    if (!s || s.x < -LABEL_W || s.x > vw + LABEL_W || s.y < -60 || s.y > vh + 60) continue;
    if (placed.some((o) => Math.abs(o.x - s.x) < LABEL_W && Math.abs(o.y - s.y) < LABEL_H)) continue;
    placed.push(s);
    out.push(
      isQuarter ? (
        <div key={p.n} className="quarter" style={{ transform: `translate(${s.x}px,${s.y}px)` }}>
          <span>{p.n}</span>
        </div>
      ) : (
        <button
          key={p.n}
          type="button"
          className={`pin cat-${p.c}${p === active ? " on" : ""}`}
          style={{ transform: `translate(${s.x}px,${s.y}px)` }}
          onClick={() => onPick(p)}
        >
          <span>{p.n}</span>
          <i aria-hidden="true" />
        </button>
      ),
    );
  }
  return <div className="pins">{out}</div>;
}
