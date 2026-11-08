import { useEffect, useState, type RefObject } from "react";
import type { MapHandle } from "./IsometricMap";
import type { Season } from "../scene";
import { on } from "../features";
import { onWeather, setWeatherMode, setWind, weather, weatherFixed, weatherMode, windSetting, type Mode } from "../weather";

export interface WeatherControlProps {
  map: RefObject<MapHandle>;
  /** 0 day .. 1 full night */
  night: number;
  /** hour of the day shown, 0 to 24 */
  hour: number;
  season: Season;
  /** "today" (the real date, or ?date= in tests) */
  date: Date;
}

const MODES: [Mode, string, string][] = [
  ["live", "Live", "The weather in Luxembourg now (Open-Meteo)"],
  ["clear", "Clear", "Clear sky"],
  ["rain", "Rain", "Rain"],
  ["storm", "Storm", "Thunderstorm, with lightning"],
  ["fog", "Fog", "Fog in the valleys"],
  ["snow", "Snow", "Snow"],
];

/** Weather picker, an extra row under the time and season rows: Live or a kind of weather, and the wind. */
export function WeatherControl(_props: WeatherControlProps) {
  const [, tick] = useState(0);
  useEffect(() => onWeather(() => tick((n) => n + 1)), []);
  if (!on("weather")) return null;
  const mode = weatherFixed ? weather().kind : weatherMode();
  const w = weather();
  const wind = windSetting() ?? Math.round(w.wind.speed);
  return (
    <>
      <div className="scene-row" role="group" aria-label="Weather">
        {MODES.map(([m, label, title]) => (
          <button key={m} type="button" className={mode === m ? "on" : ""} aria-pressed={mode === m} title={title}
            aria-label={m === "live" ? "Live weather" : undefined} disabled={weatherFixed}
            onClick={() => setWeatherMode(m)}>{label}</button>
        ))}
      </div>
      <div className="scene-row">
        <label className="scene-wind" htmlFor="wind">Wind</label>
        <input id="wind" type="range" min={0} max={20} step={1} value={wind} aria-valuetext={`${wind} metres per second`}
          disabled={weatherFixed} onChange={(e) => setWind(+e.target.value)} />
        <output className="scene-time" htmlFor="wind">{wind} m/s</output>
        <button type="button" className={windSetting() === null ? "on" : ""} aria-pressed={windSetting() === null} disabled={weatherFixed}
          title="The weather's own wind" onClick={() => setWind(null)}>Auto</button>
      </div>
    </>
  );
}
