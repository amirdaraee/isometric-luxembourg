import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/global.css";
import { startAnalytics } from "./analytics";
import { startMonitoring } from "./monitoring";

// Error reports: listening from the start, the SDK loads after the map has drawn (see monitoring.ts).
startMonitoring();
// Statistics start once the map's first view has drawn (or after 8 s), not before it.
let started = false;
const startStats = () => { if (!started) { started = true; startAnalytics(); } };
addEventListener("map-drawn", startStats, { once: true });
setTimeout(startStats, 8000);

// ?spritelab: the sprite test page instead of the map (development and tests). Loaded on demand, so the map's
// own bundle doesn't carry it.
const SpriteLab = lazy(() => import("./dev/SpriteLab"));
const spritelab = new URLSearchParams(location.search).has("spritelab");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {spritelab ? <Suspense fallback={null}><SpriteLab /></Suspense> : <App />}
  </React.StrictMode>,
);
