import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/global.css";
import { startAnalytics } from "./analytics";

startAnalytics();

// ?spritelab: the sprite test page instead of the map (development and tests). Loaded on demand, so the map's
// own bundle doesn't carry it.
const SpriteLab = lazy(() => import("./dev/SpriteLab"));
const spritelab = new URLSearchParams(location.search).has("spritelab");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {spritelab ? <Suspense fallback={null}><SpriteLab /></Suspense> : <App />}
  </React.StrictMode>,
);
