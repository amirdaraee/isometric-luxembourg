// Adapted from isometric-nyc by Andy Coenen (MIT, see LICENSE.isometric-nyc).
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import OpenSeadragon from "openseadragon";
import { tilesBase } from "../config";

export interface MapMeta {
  width: number;
  height: number;
  tileSize: number;
  mpp: number;
  art: "preview" | "painted" | "final";
  painted?: { file: string; x0: number; y0: number; w: number; h: number }[];
  /** Painted versions of the map (night, golden, seasons): variant -> tiles folder name under tilesBase. */
  variants?: Record<string, string>;
}

export interface View {
  x: number; // image pixels
  y: number;
  z: number; // screen pixels per image pixel
}

export interface MapHandle {
  flyTo: (x: number, y: number, z?: number) => void;
  zoomBy: (factor: number) => void;
  getView: () => View | null;
  toScreen: (x: number, y: number) => { x: number; y: number } | null;
  /** Show painted versions on top of the day map with these opacities (0 hides). */
  setLayers: (alpha: Record<string, number>) => void;
  /** Small painted patches (events) placed in map px, with opacities. */
  setPatches: (patches: { url: string; x0: number; y0: number; w: number; a: number }[]) => void;
}

interface Props {
  meta: MapMeta;
  initial: View;
  onViewChange: (v: View) => void;
  onReady: () => void;
}

export const IsometricMap = forwardRef<MapHandle, Props>(function IsometricMap({ meta, initial, onViewChange, onReady }, ref) {
  const host = useRef<HTMLDivElement>(null);
  const viewer = useRef<OpenSeadragon.Viewer | null>(null);
  const layers = useRef<Record<string, OpenSeadragon.TiledImage | "loading">>({});
  const pending = useRef<Record<string, number>>({});
  const patches = useRef<Record<string, OpenSeadragon.TiledImage | "loading">>({});
  const patchAlpha = useRef<Record<string, number>>({});
  const tileSourceFor = (folder: string) => ({
    width: meta.width, height: meta.height, tileSize: meta.tileSize, tileOverlap: 0, minLevel: 9,
    maxLevel: Math.ceil(Math.log2(Math.max(meta.width, meta.height))),
    getTileUrl: (level: number, x: number, y: number) => `${tilesBase}/${folder}/${level}/${x}_${y}.webp`,
  });

  // With extra layers on the map, convert through the base (day) image, not the viewport.
  const base = () => viewer.current?.world.getItemAt(0) as OpenSeadragon.TiledImage | undefined;

  useImperativeHandle(ref, () => ({
    flyTo(x, y, z) {
      const v = viewer.current;
      if (!v) return;
      const vp = v.viewport;
      const b = base();
      if (!b) return;
      vp.panTo(b.imageToViewportCoordinates(new OpenSeadragon.Point(x, y)));
      if (z !== undefined) vp.zoomTo(b.imageToViewportZoom(z));
    },
    zoomBy(factor) {
      const vp = viewer.current?.viewport;
      if (vp) vp.zoomBy(factor);
    },
    getView() {
      const vp = viewer.current?.viewport;
      const b = base();
      if (!vp || !b) return null;
      const c = b.viewportToImageCoordinates(vp.getCenter(true));
      return { x: c.x, y: c.y, z: b.viewportToImageZoom(vp.getZoom(true)) };
    },
    setLayers(alpha) {
      const v = viewer.current;
      if (!v) return;
      for (const [name, a] of Object.entries(alpha)) {
        const folder = meta.variants?.[name];
        if (!folder) continue;
        let item = layers.current[name];
        if (!item && a > 0.001) {
          // added lazily, the first time a version is needed
          layers.current[name] = "loading";
          v.addTiledImage({
            tileSource: tileSourceFor(folder),
            opacity: 0,
            success: (e: { item: OpenSeadragon.TiledImage }) => {
              layers.current[name] = e.item; e.item.setOpacity(pending.current[name] ?? 0);
              // event patches (Christmas markets) must stay above every map version
              for (const pt of Object.values(patches.current))
                if (pt !== "loading") v.world.setItemIndex(pt, v.world.getItemCount() - 1);
            },
          } as unknown as OpenSeadragon.TiledImageOptions);
        }
        pending.current[name] = a;
        item = layers.current[name];
        if (item && item !== "loading") (item as OpenSeadragon.TiledImage).setOpacity(a);
      }
    },
    setPatches(list) {
      const v = viewer.current;
      if (!v) return;
      for (const p of list) {
        const item = patches.current[p.url];
        if (!item && p.a > 0.001) {
          patches.current[p.url] = "loading";
          v.addSimpleImage({
            url: p.url, x: p.x0 / meta.width, y: p.y0 / meta.width, width: p.w / meta.width,
            success: (e: { item: OpenSeadragon.TiledImage }) => { patches.current[p.url] = e.item; e.item.setOpacity(patchAlpha.current[p.url] ?? p.a); },
            error: () => { delete patches.current[p.url]; },
          } as unknown as OpenSeadragon.SimpleImageOptions);
        } else if (item && item !== "loading") (item as OpenSeadragon.TiledImage).setOpacity(p.a);
        patchAlpha.current[p.url] = p.a;
      }
    },
    toScreen(x, y) {
      const vp = viewer.current?.viewport;
      const b = base();
      if (!vp || !b) return null;
      const p = vp.pixelFromPoint(b.imageToViewportCoordinates(new OpenSeadragon.Point(x, y)), true);
      return { x: p.x, y: p.y };
    },
  }));

  useEffect(() => {
    if (!host.current || viewer.current) return;
    const { width, height, tileSize, art } = meta;
    const v = OpenSeadragon({
      element: host.current,
      prefixUrl: "",
      showNavigationControl: false,
      crossOriginPolicy: "Anonymous",
      showNavigator: window.innerWidth > 640,
      navigatorPosition: "TOP_RIGHT",
      navigatorSizeRatio: 0.14,
      navigatorMaintainSizeRatio: true,
      navigatorAutoFade: false,
      navigatorBackground: "#101828",
      navigatorBorderColor: "rgba(255,255,255,.2)",
      navigatorDisplayRegionColor: "#ef3340",
      animationTime: 0.45,
      springStiffness: 9,
      blendTime: 0.1,
      immediateRender: false,
      minZoomImageRatio: 0.8,
      // Never zoom past the painted detail (~0.22-0.29 m per painted pixel vs 0.25 m per map pixel).
      maxZoomPixelRatio: 1.25,
      visibilityRatio: 0.35,
      constrainDuringPan: true,
      preserveImageSizeOnResize: true,
      placeholderFillStyle: "#172033",
      gestureSettingsMouse: { scrollToZoom: true, clickToZoom: false, dblClickToZoom: true, flickEnabled: true },
      gestureSettingsTouch: { pinchToZoom: true, clickToZoom: false, dblClickToZoom: true, flickEnabled: true },
      // Crisp pixels suit the final pixel art; the 3D preview reads better smoothed.
      imageSmoothingEnabled: art !== "final",
      tileSources: {
        width,
        height,
        tileSize,
        tileOverlap: 0,
        minLevel: 9,
        maxLevel: Math.ceil(Math.log2(Math.max(width, height))),
        getTileUrl: (level: number, x: number, y: number) => `${tilesBase}/map_files/${level}/${x}_${y}.webp`,
      },
    } as OpenSeadragon.Options);

    v.addHandler("open", () => {
      const vp = v.viewport;
      const b = v.world.getItemAt(0);
      vp.zoomTo(b.imageToViewportZoom(initial.z), undefined, true);
      vp.panTo(b.imageToViewportCoordinates(new OpenSeadragon.Point(initial.x, initial.y)), true);
      onReady();
    });
    const report = () => {
      const vp = v.viewport;
      const b = v.world.getItemAt(0);
      if (!vp || !b) return;
      const c = b.viewportToImageCoordinates(vp.getCenter(true));
      onViewChange({ x: c.x, y: c.y, z: b.viewportToImageZoom(vp.getZoom(true)) });
    };
    v.addHandler("update-viewport", report);
    viewer.current = v;
    return () => {
      v.destroy();
      viewer.current = null;
    };
    // The viewer lives for the whole page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={host} className="map" role="region" aria-label="Isometric map of Luxembourg City" />;
});
