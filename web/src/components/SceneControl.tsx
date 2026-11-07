import type { ReactNode } from "react";
import type { Season, SceneState } from "../scene";
import { on } from "../features";

interface Props {
  scene: SceneState;
  live: boolean;
  onChange: (s: Partial<SceneState>) => void;
  onLive: () => void;
  sun: [number, number];
  /** More controls under the time and season rows (the weather picker). */
  extra?: ReactNode;
}

const SEASONS: [Season, string][] = [["spring", "Spring"], ["summer", "Summer"], ["autumn", "Autumn"], ["winter", "Winter"]];

function hhmm(h: number) {
  const m = Math.round(h * 60) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

export function SceneControl({ scene, live, onChange, onLive, sun, extra }: Props) {
  const icon = scene.hour < sun[0] - 0.5 || scene.hour > sun[1] + 0.5 ? "🌙" : Math.abs(scene.hour - (sun[1] - 0.6)) < 1 ? "🌇" : "☀️";
  return (
    <div className="scene glass" role="group" aria-label="Time of day and season">
      {on("timeOfDay") && <div className="scene-row">
        <span aria-hidden="true">{icon}</span>
        <input type="range" min={0} max={23.99} step={0.05} value={scene.hour} aria-label="Time of day"
          aria-valuetext={hhmm(scene.hour)} onChange={(e) => onChange({ hour: +e.target.value })} />
        <output className="scene-time">{hhmm(scene.hour)}</output>
        <button type="button" className={live ? "on" : ""} aria-pressed={live} onClick={onLive} title="Follow Luxembourg's real clock">Live</button>
      </div>}
      {(on("seasons") || on("christmas")) && <div className="scene-row">
        {on("seasons") && SEASONS.map(([k, label]) => (
          <button key={k} type="button" className={scene.season === k ? "on" : ""} aria-pressed={scene.season === k}
            onClick={() => onChange({ season: k })}>{label}</button>
        ))}
        {on("christmas") && <button type="button" className={scene.christmas ? "on xmas" : "xmas"} aria-pressed={scene.christmas}
          onClick={() => onChange({ christmas: !scene.christmas })} title="Winterlights Christmas markets">🎄 Christmas</button>}
      </div>}
      {extra}
    </div>
  );
}
