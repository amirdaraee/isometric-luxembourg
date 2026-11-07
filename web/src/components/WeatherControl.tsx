import type { RefObject } from "react";
import type { MapHandle } from "./IsometricMap";
import type { Season } from "../scene";

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

/** Weather picker, shown as an extra row in SceneControl. Stream C fills it in. For now it renders nothing. */
export function WeatherControl(_props: WeatherControlProps) {
  return null;
}
