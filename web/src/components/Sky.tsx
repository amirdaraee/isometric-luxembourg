import type { RefObject } from "react";
import type { MapHandle } from "./IsometricMap";
import type { Season } from "../scene";

export interface SkyProps {
  map: RefObject<MapHandle>;
  /** 0 day .. 1 full night */
  night: number;
  /** hour of the day shown, 0 to 24 */
  hour: number;
  season: Season;
  /** "today" (the real date, or ?date= in tests) */
  date: Date;
}

/** The sky over the map: weather (rain, storm, wind, snow), valley fog and aircraft. Stream C fills it in. For now it renders nothing. */
export function Sky(_props: SkyProps) {
  return null;
}
