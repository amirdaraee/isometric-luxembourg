import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { IsometricMap, type MapHandle, type MapMeta, type View } from "./components/IsometricMap";
import { Pins, type Place } from "./components/Pins";
import { Search } from "./components/Search";
import { Overlay } from "./components/Overlay";
import { Statues } from "./components/Statues";
import { Water } from "./components/Water";
import { Clouds } from "./components/Clouds";
import { LandmarkPanel, type Landmark } from "./components/LandmarkPanel";
import { SceneControl } from "./components/SceneControl";
import { Feedback, feedbackConfigured } from "./components/Feedback";
import { EventLayer } from "./components/EventLayer";
import { Sky } from "./components/Sky";
import { WeatherControl } from "./components/WeatherControl";
import { LayersPoc, layersPocOn } from "./components/LayersPoc";
import { changeScene, christmasOn, mix, seasonOf, sunFor, type SceneState, type Variant } from "./scene";
import { activeEvents, EVENT_SEASON, RULES, type EventId } from "./calendar";
import { eventManifest } from "./components/EventLayer";
import type { EventEffects } from "./components/eventEffects";
import { luxSeconds } from "./components/Transit";
import { asset, tilesBase } from "./config";
import { on } from "./features";
import { testParams, today } from "./testParams";

const FOCUS_ZOOM = 0.75;

/** The events shown: the one picked (or ?event=), else the calendar's, each only with its switches on. */
function shownEvents(s: SceneState, date: Date): string[] {
  const ok = (id: string) => id === "winterlights" ? on("christmas") : on("events") && on(id as never);
  const ids = s.event ? [s.event] : activeEvents(date).filter((id) => id !== "winterlights");
  const out = ids.filter(ok);
  if (s.christmas && !out.includes("winterlights")) out.unshift("winterlights");
  // each event's patches and effects belong to one season's art
  return out.filter((id) => (EVENT_SEASON[id as EventId] ?? s.season) === s.season);
}

/** The scene at start: "now" in Luxembourg (or the ?hour, ?season, ?date and ?event test parameters), limited to
 * the features that are switched on. */
function liveScene(): SceneState {
  const christmas = on("christmas") && (christmasOn() || testParams.event === "winterlights");
  const ev = testParams.event && testParams.event !== "winterlights" && testParams.event in RULES ? testParams.event : null;
  if (ev && on("events")) {
    return {
      hour: on("timeOfDay") ? testParams.hour ?? luxSeconds() / 3600 : 13,
      season: testParams.season ?? EVENT_SEASON[ev as EventId] ?? seasonOf(),
      christmas: christmas || ev === "newYear",
      event: ev,
    };
  }
  return {
    hour: on("timeOfDay") ? testParams.hour ?? luxSeconds() / 3600 : 13,
    // The Christmas markets are painted on the winter art, so Winterlights brings winter with it (late November
    // would otherwise still be autumn).
    season: on("seasons") && testParams.season ? testParams.season : christmas ? "winter" : on("seasons") ? seasonOf() : "summer",
    christmas,
  };
}
const OPENING_NAME = "Notre-Dame Cathedral";
const REPO_URL = "https://github.com/amirdaraee/isometric-luxembourg";

function readHash(): View | null {
  const m = location.hash.match(/^#(-?\d+),(-?\d+),([\d.]+)$/);
  return m ? { x: +m[1], y: +m[2], z: +m[3] } : null;
}

export default function App() {
  const [meta, setMeta] = useState<MapMeta | null>(null);
  const [places, setPlaces] = useState<Place[] | null>(null);
  const [error, setError] = useState(false);
  const [ready, setReady] = useState(false);
  const [view, setView] = useState<View | null>(null);
  const [active, setActive] = useState<Place | null>(null);
  const [toast, setToast] = useState("");
  const [about, setAbout] = useState(false);
  const [streets, setStreets] = useState(false);
  const [lm, setLm] = useState<Landmark | null>(null);
  const [marking, setMarking] = useState(false);
  // Marking a spot puts away the place cards, so the map and the note card have the room.
  useEffect(() => { if (marking) { setLm(null); setActive(null); } }, [marking]);
  useEffect(() => {
    fetch(asset("/data/landmarks.json")).then((r) => r.json()).then((l: Landmark[]) => { landmarksRef.current = l; }).catch(() => {});
  }, []);
  const [traffic, setTraffic] = useState(true);
  // Time of day and season: live (Luxembourg clock and date) until the person moves a control.
  // ?hour= fixes the clock for tests, as if the person had moved the slider.
  const [live, setLive] = useState(!(on("timeOfDay") && testParams.hour !== null));
  const [scene, setScene] = useState<SceneState>(liveScene);
  // Live follows Luxembourg's real clock (not ?hour=), and only the clock: the season, Christmas and the event
  // picked stay as they are.
  useEffect(() => {
    if (!live) return;
    const tick = () => setScene((s) => ({ ...s, hour: on("timeOfDay") ? luxSeconds() / 3600 : 13 }));
    const t = setInterval(tick, 20000);
    tick();
    return () => clearInterval(t);
  }, [live]);
  const date = useMemo(() => today(), []);
  const sun = useMemo(() => sunFor(scene.season, date), [scene.season, date]);
  const [xmas, setXmas] = useState<{ site: string; x0: number; y0: number; w: number }[]>([]);
  useEffect(() => { if (on("christmas")) fetch(asset("/events/xmas/xmas.json")).then((r) => r.json()).then(setXmas).catch(() => {}); }, []);
  const [events, setEvents] = useState<Record<string, EventEffects>>({});
  useEffect(() => { if (on("events")) eventManifest().then(setEvents); }, []);
  const shown = useMemo(() => shownEvents(scene, date), [scene, date]);
  const map = useRef<MapHandle>(null);
  const landmarksRef = useRef<Landmark[]>([]);
  const lastSurprise = useRef<Place | null>(null);

  useEffect(() => {
    Promise.all([fetch(`${tilesBase}/meta.json`).then((r) => r.json()), fetch(asset("/data/places.json")).then((r) => r.json())])
      .then(([m, p]) => {
        setMeta(m);
        setPlaces(p);
      })
      .catch(() => setError(true));
  }, []);

  const initial = useMemo<View | null>(() => {
    if (!meta || !places) return null;
    const fromLink = readHash();
    if (fromLink) return fromLink;
    const start = places.find((p) => p.n === OPENING_NAME);
    return start ? { x: start.x, y: start.y, z: 0.55 } : { x: meta.width / 2, y: meta.height / 2, z: 0.2 };
  }, [meta, places]);

  // Every view has a URL, so any view can be sent to someone.
  const hashTimer = useRef<ReturnType<typeof setTimeout>>();
  const onViewChange = useCallback((v: View) => {
    setView(v);
    clearTimeout(hashTimer.current);
    hashTimer.current = setTimeout(() => {
      history.replaceState(null, "", `#${Math.round(v.x)},${Math.round(v.y)},${v.z.toFixed(3)}`);
    }, 300);
  }, []);

  const pick = useCallback((p: Place) => {
    setActive(p);
    // A landmark with a full card: the nearest one within ~50 m of the pin.
    // Pins made from a landmark card carry its slug, which wins over distance in crowded places.
    let best: Landmark | null = (p.s && landmarksRef.current.find((l) => l.slug === p.s)) || null, bd = best ? -1 : 220;
    for (const l of landmarksRef.current) {
      const d = Math.hypot(l.x - p.x, l.y - p.y);
      if (d < bd) { bd = d; best = l; }
    }
    setLm(on("landmarks") ? best : null);
    map.current?.flyTo(p.x, p.y, p.c === "quarter" ? 0.3 : FOCUS_ZOOM);
  }, []);

  const surprise = useCallback(() => {
    const pool = (places ?? []).filter((p) => p.f && p !== lastSurprise.current);
    if (!pool.length) return;
    const p = pool[Math.floor(Math.random() * pool.length)];
    lastSurprise.current = p;
    pick(p);
  }, [places, pick]);

  const share = useCallback(async () => {
    const url = location.href;
    const title = active ? `${active.n}, Isometric Luxembourg` : "Isometric Luxembourg";
    try {
      if (navigator.share && matchMedia("(pointer: coarse)").matches) {
        await navigator.share({ title, url });
      } else {
        await navigator.clipboard.writeText(url);
        setToast("Link to this view copied");
        setTimeout(() => setToast(""), 2200);
      }
    } catch {
      /* The person closed the share sheet. */
    }
  }, [active]);

  const have = useMemo(() => new Set(Object.keys(meta?.variants ?? {}) as Variant[]), [meta]);
  const sceneMix = useMemo(() => mix(scene, have, sun), [scene, have, sun]);
  useEffect(() => {
    if (!ready) return;
    const alpha: Record<string, number> = {};
    for (const v of have) alpha[v] = 0;
    for (const l of sceneMix.layers) if (l.v !== "day") alpha[l.v] = l.a;
    if (scene.christmas) {
      const nightish = sceneMix.night;
      if (have.has("xmas_day" as Variant)) alpha["xmas_day"] = 1 - nightish;
      if (have.has("xmas_night" as Variant)) alpha["xmas_night"] = nightish;
    }
    map.current?.setLayers(alpha);
    // The patches are opaque cut-outs of the winter art with the markets in, so they show only over winter.
    const xmasShown = scene.christmas && scene.season === "winter";
    // The day patch stays fully on and the night patch fades in over it (both share one opaque region), so the
    // map never shows through a patch halfway through dusk.
    const n = sceneMix.night;
    // Other events: their patches, by the same rule (day patch on, night patch fading in over it). An event with
    // only a day patch (a daytime market) fades out at night instead. Events not shown are passed at 0, so a patch
    // shown before goes away.
    const others = Object.entries(events).filter(([id]) => id !== "winterlights" && id !== "newYear").flatMap(([id, e]) => {
      const on_ = shown.includes(id);
      return (e.patches ?? []).flatMap((p) => [
        ...(p.day ? [{ url: asset(p.day), x0: p.x0, y0: p.y0, w: p.w, a: on_ ? (p.night ? 1 : 1 - n) : 0 }] : []),
        ...(p.night ? [{ url: asset(p.night), x0: p.x0, y0: p.y0, w: p.w, a: on_ ? n : 0 }] : []),
      ]);
    });
    map.current?.setPatches([...xmas.flatMap((x) => [
      { url: asset(`/events/xmas/${x.site}_day.webp`), x0: x.x0, y0: x.y0, w: x.w, a: xmasShown ? 1 : 0 },
      { url: asset(`/events/xmas/${x.site}_night.webp`), x0: x.x0, y0: x.y0, w: x.w, a: xmasShown ? n : 0 },
    ]), ...others]);
  }, [sceneMix, ready, have, scene.christmas, scene.season, xmas, shown, events]);

  if (error) return <div className="splash">The map couldn't load. Please try refreshing.</div>;
  if (!meta || !places || !initial) return <div className="splash">Loading Luxembourg</div>;

  return (
    <div className="app">
      <div className="graded" style={{ filter: sceneMix.grade || undefined }}>
      <IsometricMap ref={map} meta={meta} initial={initial} onViewChange={onViewChange} onReady={() => setReady(true)} />
      </div>
      {ready && layersPocOn && <LayersPoc map={map} below />}
      {ready && on("water") && <Water map={map} night={sceneMix.night} />}
      {ready && on("statues") && <Statues map={map} night={sceneMix.night} season={scene.season} onPick={pick} />}
      {ready && <Overlay map={map} meta={meta} streets={streets} traffic={traffic} night={sceneMix.night} hour={live ? null : scene.hour} season={scene.season} />}
      {ready && layersPocOn && <LayersPoc map={map} below={false} />}
      {ready && <EventLayer map={map} night={sceneMix.night} hour={scene.hour} season={scene.season} date={date} active={shown} picked={scene.event ?? null} />}
      {ready && on("clouds") && <Clouds map={map} night={sceneMix.night} />}
      {ready && <Sky map={map} night={sceneMix.night} hour={scene.hour} season={scene.season} date={date} />}
      {(on("timeOfDay") || on("seasons") || on("christmas") || on("weather")) && <SceneControl scene={scene} live={live} sun={sun} onLive={() => setLive(true)}
        onChange={(c) => { if (c.hour !== undefined) setLive(false); setScene((s) => changeScene(s, c, EVENT_SEASON)); }}
        date={date} extra={<WeatherControl map={map} night={sceneMix.night} hour={scene.hour} season={scene.season} date={date} />} />}
      {ready && on("pins") && <Pins places={places} view={view} map={map} active={active} onPick={pick} />}
      {ready && on("comments") && feedbackConfigured && <Feedback map={map} marking={marking} setMarking={setMarking}
        onToast={(m) => { setToast(m); setTimeout(() => setToast(""), 3200); }} />}
      {on("search") && <Search places={places} onPick={pick} onSurprise={on("surprise") ? surprise : undefined} />}

      {lm && <LandmarkPanel key={lm.slug} lm={lm} onClose={() => { setLm(null); setActive(null); }} />}

      {active && !lm && (
        <div className="card glass" role="status">
          <button type="button" className="ibtn close" aria-label="Close" onClick={() => setActive(null)}>×</button>
          <b>{active.n}</b>
          {active.d && <p>{active.d}</p>}
        </div>
      )}

      {(on("streets") || on("traffic") || on("transit")) && (
        <div className="layers glass" role="group" aria-label="Map layers">
          {on("streets") && <button type="button" className={streets ? "on" : ""} aria-pressed={streets} onClick={() => setStreets((v) => !v)}>Streets</button>}
          {(on("traffic") || on("transit")) && <button type="button" className={traffic ? "on" : ""} aria-pressed={traffic} onClick={() => setTraffic((v) => !v)}>Traffic</button>}
        </div>
      )}

      <div className="tools">
        <button type="button" className="round glass" aria-label="Zoom in" onClick={() => map.current?.zoomBy(1.6)}>+</button>
        <button type="button" className="round glass" aria-label="Zoom out" onClick={() => map.current?.zoomBy(1 / 1.6)}>−</button>
        {on("comments") && feedbackConfigured && <button type="button" className={`round glass mark${marking ? " on" : ""}`}
          aria-label="Mark a spot and send a note" title="Mark a spot and send a note (M)" aria-pressed={marking}
          aria-keyshortcuts="M" onClick={() => setMarking((v) => !v)}>
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path d="M4 8V5a1 1 0 0 1 1-1h3m8 0h3a1 1 0 0 1 1 1v3m0 8v3a1 1 0 0 1-1 1h-3m-8 0H5a1 1 0 0 1-1-1v-3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <path d="M12 9v6m-3-3h6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>}
        {on("share") && <button type="button" className="round share" aria-label="Share this view" onClick={share}>
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path d="M12 15V4m0 0L8 8m4-4 4 4M5 13v6a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>}
        <a className="round glass gh" href={REPO_URL} target="_blank" rel="noopener" aria-label="Source code on GitHub" title="Source code on GitHub">
          <svg viewBox="0 0 16 16" width="20" height="20" aria-hidden="true">
            <path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
          </svg>
        </a>
      </div>

      <div className="foot">
        {on("previewBadge") && meta.art !== "final" && <span className="badge">{meta.art === "painted" ? ((meta.painted?.length ?? 0) > 1 ? "Preview: central Luxembourg City painted; more to come" : "Preview: old town painted, the rest is 3D data") : "Preview: 3D data, final art coming"}</span>}
        <button type="button" className="link" onClick={() => setAbout(true)}>About and credits</button>
      </div>

      {toast && <div className="toast glass" role="status">{toast}</div>}
      {on("tiltShift") && <><div className="tilt tilt-top" aria-hidden="true" /><div className="tilt tilt-bottom" aria-hidden="true" /></>}
      {on("previewBadge") && view && view.z >= 0.1 && meta.painted?.length &&
        !meta.painted.some((a) => view.x >= a.x0 && view.x <= a.x0 + a.w && view.y >= a.y0 && view.y <= a.y0 + a.h) && (
        <div className="unpainted glass" role="note">This part of the city is still being drawn: you're looking at the 3D model underneath.</div>
      )}

      {about && (
        <div className="about-wrap" onClick={() => setAbout(false)}>
          <section className="about glass" role="dialog" aria-label="About and credits" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="ibtn close" aria-label="Close" onClick={() => setAbout(false)}>×</button>
            <h1>Isometric Luxembourg</h1>
            <p>Luxembourg City seen from the south-east, from its gorges to Kirchberg, drawn as an inked illustration. This first release paints central Luxembourg City in summer, by day and by night, with golden hour in between; more of the city and the other seasons will follow.</p>
            <p>The art is painted tile by tile by an image model trained for this map on the real city: 3D buildings, terrain, streets, rail and rivers decide what goes where.</p>
            <h2>Data</h2>
            <ul>
              <li>3D buildings 2023 and orthophoto 2023: Administration du Cadastre et de la Topographie, CC0</li>
              <li>Places, streets and addresses: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap contributors</a>, ODbL</li>
              <li>LiDAR terrain 2019: data.public.lu, CC0</li>
              <li>Tram and train timetables (GTFS): data.public.lu, CC BY 4.0</li>
              <li>Live weather: Open-Meteo, CC BY 4.0</li>
              <li>Landmark photos: Wikimedia Commons, credited with author and licence on each card</li>
            </ul>
            <h2>Code</h2>
            <ul>
              <li>Viewer built from <a href="https://github.com/cannoneyed/isometric-nyc" target="_blank" rel="noopener">isometric-nyc</a> by Andy Coenen, MIT</li>
              <li><a href="https://openseadragon.github.io" target="_blank" rel="noopener">OpenSeadragon</a> and <a href="https://threejs.org" target="_blank" rel="noopener">three.js</a></li>
              <li><a href={REPO_URL} target="_blank" rel="noopener">Source on GitHub</a>: code MIT, art CC BY-NC 4.0</li>
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}
