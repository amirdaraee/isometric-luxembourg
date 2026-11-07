import { lazy, Suspense, useState } from "react";
import { asset } from "../config";
import { on } from "../features";

const Model3D = lazy(() => import("./Model3D").then((m) => ({ default: m.Model3D })));

export interface Photo { src: string; caption: string; author?: string; licence?: string; licence_url?: string; source?: string }
export interface Landmark {
  slug: string; name: string; local: string; category: string; x: number; y: number; about: string;
  photos: Photo[]; model: string | null; wikipedia: string | null; cutaway?: string; hero?: string;
  quarter?: string; facts?: string[]; visiting?: string; sources?: { title: string; url: string }[];
  interior: null | { architects?: string; dates?: string; style?: string; layout?: string; main_spaces?: string;
    materials_colours?: string; access?: string; official_site?: string; photos: Photo[] };
}

const CATEGORY: Record<string, string> = {
  landmark: "Landmark", culture: "Culture", history: "History", bridge: "Bridge", park: "Park", square: "Square",
  transport: "Transport", viewpoint: "Viewpoint", church: "Church", religion: "Place of worship", government: "Government",
  fortification: "Fortification", "eu-institution": "EU institution", education: "Education", sport: "Sport",
  modern: "Modern architecture", museum: "Museum",
};

type Tab = "story" | "inside" | "3d" | "photos";

function md(s: string) {
  // the research notes use **bold**; keep it, escape the rest
  const esc = s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  return { __html: esc.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>") };
}

function Credit({ p }: { p: Photo }) {
  if (!p.author && !p.licence) return null;
  return (
    <small className="credit">
      {p.source ? <a href={p.source} target="_blank" rel="noopener">{p.author || "source"}</a> : p.author}
      {p.licence && <> · {p.licence_url ? <a href={p.licence_url} target="_blank" rel="noopener">{p.licence}</a> : p.licence}</>}
    </small>
  );
}

export function LandmarkPanel({ lm, onClose }: { lm: Landmark; onClose: () => void }) {
  const tabs: [Tab, string][] = [["story", "Story"], ...(on("interiors") && (lm.interior || lm.cutaway) ? [["inside", "Inside"] as [Tab, string]] : []),
    ...(on("models3d") && lm.model ? [["3d", "3D"] as [Tab, string]] : []), ...(on("photos") && lm.photos.length ? [["photos", "Photos"] as [Tab, string]] : [])];
  const [tab, setTab] = useState<Tab>("story");
  const it = lm.interior;
  const hero = lm.hero ?? lm.photos[0]?.src;
  return (
    <aside className="landmark glass" role="dialog" aria-label={lm.name}>
      <button type="button" className="ibtn close" aria-label="Close" onClick={onClose}>×</button>
      {hero && <div className="lm-hero" style={{ backgroundImage: `url(${asset(hero)})` }} />}
      <header>
        <h2>{lm.name}</h2>
        {lm.local && lm.local !== lm.name && <p className="lm-local">{lm.local}</p>}
      </header>
      <nav className="lm-tabs" role="tablist">
        {tabs.map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{label}</button>
        ))}
      </nav>
      <div className="lm-body">
        {tab === "story" && (
          <>
            {(lm.category || lm.quarter) && <p className="lm-meta">{[CATEGORY[lm.category] ?? lm.category, lm.quarter].filter(Boolean).join(" · ")}</p>}
            <p>{lm.about}</p>
            {lm.facts && lm.facts.length > 0 && <ul className="lm-facts">{lm.facts.map((f) => <li key={f} dangerouslySetInnerHTML={md(f)} />)}</ul>}
            {it && (
              <dl>
                {it.dates && (<><dt>Dates</dt><dd dangerouslySetInnerHTML={md(it.dates)} /></>)}
                {it.architects && (<><dt>Architects</dt><dd dangerouslySetInnerHTML={md(it.architects)} /></>)}
                {it.style && (<><dt>Style</dt><dd dangerouslySetInnerHTML={md(it.style)} /></>)}
                {it.access && (<><dt>Visiting</dt><dd dangerouslySetInnerHTML={md(it.access)} /></>)}
              </dl>
            )}
            {lm.visiting && <p className="muted"><b>Visiting:</b> {lm.visiting}</p>}
            {lm.sources && lm.sources.length > 0 ? (
              <p className="lm-sources">Sources: {lm.sources.map((s, i) => <span key={s.url}>{i > 0 && " · "}<a href={s.url} target="_blank" rel="noopener">{s.title}</a></span>)}</p>
            ) : lm.wikipedia && <p><a href={lm.wikipedia} target="_blank" rel="noopener">Read more on Wikipedia</a></p>}
          </>
        )}
        {tab === "inside" && (
          <>
            {lm.cutaway && <img className="lm-cutaway" src={asset(lm.cutaway)} alt={`Cutaway illustration of the inside of ${lm.name}`} />}
            {it?.layout && <p dangerouslySetInnerHTML={md(it.layout)} />}
            {it?.main_spaces && <p dangerouslySetInnerHTML={md(it.main_spaces)} />}
            {it?.materials_colours && <p className="muted" dangerouslySetInnerHTML={md(it.materials_colours)} />}
            <div className="lm-grid">
              {it?.photos.map((p) => (
                <figure key={p.src}><img src={asset(p.src)} alt={p.caption} loading="lazy" /><figcaption>{p.caption}<Credit p={p} /></figcaption></figure>
              ))}
            </div>
          </>
        )}
        {tab === "3d" && lm.model && (
          <>
            <Suspense fallback={<div className="model3d" />}>
              <Model3D url={asset(lm.model)} />
            </Suspense>
            <p className="muted">The real building from Luxembourg's 3D city model (2023). Drag to turn it, scroll to zoom.</p>
          </>
        )}
        {tab === "photos" && (
          <div className="lm-grid">
            {lm.photos.map((p) => (
              <figure key={p.src}><img src={asset(p.src)} alt={p.caption} loading="lazy" /><figcaption>{p.caption}<Credit p={p} /></figcaption></figure>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
