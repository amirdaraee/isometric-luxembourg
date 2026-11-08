import { useState, type ReactNode } from "react";
import type { Season, SceneState } from "../scene";
import { on } from "../features";
import { activeEvents, EVENT_NAMES, EVENT_SEASON, RULES, SHOW_HOUR, type EventId } from "../calendar";

interface Props {
  scene: SceneState;
  live: boolean;
  onChange: (s: Partial<SceneState>) => void;
  onLive: () => void;
  sun: [number, number];
  /** More controls under the time and season rows (the weather picker). */
  extra?: ReactNode;
  /** "today", for the events on now */
  date?: Date;
}

const SEASONS: [Season, string][] = [["spring", "Spring"], ["summer", "Summer"], ["autumn", "Autumn"], ["winter", "Winter"]];

function hhmm(h: number) {
  const m = Math.round(h * 60) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

/** Events the picker offers: today's, plus every event when the events switch is on, each only with its switch. */
function pickable(date: Date): { id: EventId; today: boolean }[] {
  const today = new Set(activeEvents(date));
  return (Object.keys(RULES) as EventId[])
    .filter((id) => id !== "winterlights" && on(id as never) && (on("events") || today.has(id)))
    .map((id) => ({ id, today: today.has(id) }));
}

export function SceneControl({ scene, live, onChange, onLive, sun, extra, date = new Date() }: Props) {
  const [open, setOpen] = useState(false);
  const evs = on("events") ? pickable(date) : [];
  const pickEvent = (id: EventId | null) => {
    if (id === null) { onChange({ event: null }); return; }
    const season = EVENT_SEASON[id] ?? scene.season;
    onChange({ event: id, season, christmas: id === "newYear", ...(SHOW_HOUR[id] !== undefined ? { hour: SHOW_HOUR[id] } : {}) });
  };
  const icon = scene.hour < sun[0] - 0.5 || scene.hour > sun[1] + 0.5 ? "🌙" : Math.abs(scene.hour - (sun[1] - 0.6)) < 1 ? "🌇" : "☀️";
  return (
    <div className="scene glass" role="group" aria-label="Time of day and season">
      {on("timeOfDay") && <div className="scene-row">
        <span aria-hidden="true">{icon}</span>
        <input type="range" min={0} max={23.99} step={0.05} value={scene.hour} aria-label="Time of day"
          aria-valuetext={hhmm(scene.hour)} onChange={(e) => onChange({ hour: +e.target.value })} />
        <output className="scene-time">{hhmm(scene.hour)}</output>
        <button type="button" className={live ? "on" : ""} aria-pressed={live} onClick={onLive} aria-label="Live time"
          title="Follow Luxembourg's real clock">Live</button>
      </div>}
      {(on("seasons") || on("christmas")) && <div className="scene-row">
        {on("seasons") && SEASONS.map(([k, label]) => (
          <button key={k} type="button" className={scene.season === k ? "on" : ""} aria-pressed={scene.season === k}
            onClick={() => onChange({ season: k })}>{label}</button>
        ))}
        {on("christmas") && <button type="button" className={scene.christmas ? "on xmas" : "xmas"} aria-pressed={scene.christmas}
          onClick={() => onChange({ christmas: !scene.christmas })} title="Winterlights Christmas markets">🎄 Christmas</button>}
        {evs.length > 0 && <button type="button" className={scene.event ? "on" : ""} aria-expanded={open}
          onClick={() => setOpen((v) => !v)} title="City events through the year">Events</button>}
      </div>}
      {open && evs.length > 0 && <div className="scene-row scene-events" role="group" aria-label="City events">
        {evs.map(({ id, today }) => (
          <button key={id} type="button" className={scene.event === id ? "on" : ""} aria-pressed={scene.event === id}
            onClick={() => pickEvent(scene.event === id ? null : id)} title={today ? "On today" : "Preview"}>
            {EVENT_NAMES[id]}{today ? " •" : ""}
          </button>
        ))}
      </div>}
      {extra}
    </div>
  );
}
