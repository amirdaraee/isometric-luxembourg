import type { RefObject } from "react";
import type { MapHandle } from "./IsometricMap";
import type { Season } from "../scene";

export interface EventLayerProps {
  map: RefObject<MapHandle>;
  /** 0 day .. 1 full night */
  night: number;
  /** hour of the day shown, 0 to 24 */
  hour: number;
  season: Season;
  /** "today" (the real date, or ?date= in tests) */
  date: Date;
}

/** Live effects of the events shown (rides, twinkling lights, fireworks, runners, bonfires). Stream B fills it in. For now it renders nothing. */
export function EventLayer(_props: EventLayerProps) {
  return null;
}
